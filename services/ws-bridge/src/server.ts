import http from "http";
import { WebSocket, WebSocketServer } from "ws";
import jwt from "jsonwebtoken";
import jwksRsa from "jwks-rsa";
import { config } from "./config";
import { get as getSnapshot } from "./snapshot";

const jwksClient = jwksRsa({
  jwksUri: config.keycloakJwksUrl,
  cache: true,
  cacheMaxAge: 600_000,
});

async function verifyToken(token: string): Promise<Record<string, unknown>> {
  const decoded = jwt.decode(token, { complete: true });
  if (!decoded || typeof decoded === "string") throw new Error("Invalid token");
  const kid = decoded.header.kid;
  if (!kid) throw new Error("Missing kid");
  const key = await jwksClient.getSigningKey(kid);
  return jwt.verify(token, key.getPublicKey(), {
    issuer: config.keycloakIssuer,
  }) as Record<string, unknown>;
}

interface AuthenticatedWS extends WebSocket {
  isAlive: boolean;
  userId?: string;
  roles?: string[];
  filter?: string;  // optional device_id filter
}

export function createWsServer(): http.Server {
  const httpServer = http.createServer((_req, res) => {
    if (_req.url === "/healthz") {
      res.writeHead(200);
      res.end("ok");
    } else {
      res.writeHead(404);
      res.end();
    }
  });

  const wss = new WebSocketServer({ server: httpServer, path: "/ws" });

  // Heartbeat — drop stale clients
  const heartbeat = setInterval(() => {
    wss.clients.forEach((ws) => {
      const client = ws as AuthenticatedWS;
      if (!client.isAlive) { client.terminate(); return; }
      client.isAlive = false;
      client.ping();
    });
  }, 30_000);

  wss.on("close", () => clearInterval(heartbeat));

  wss.on("connection", async (ws: AuthenticatedWS, req) => {
    ws.isAlive = true;
    ws.on("pong", () => { ws.isAlive = true; });

    // Extract token from ?token= query param or Authorization header
    const url = new URL(req.url ?? "/", "http://localhost");
    const token = url.searchParams.get("token") ??
      req.headers.authorization?.replace("Bearer ", "");

    if (!token) {
      ws.close(4001, "Token required");
      return;
    }

    try {
      const payload = await verifyToken(token);
      ws.userId = payload.sub as string;
      ws.roles  = ((payload.realm_access as { roles?: string[] })?.roles) ?? [];
    } catch {
      ws.close(4003, "Invalid token");
      return;
    }

    ws.send(JSON.stringify({ type: "connected", userId: ws.userId }));

    // Client can send {"type":"subscribe","device_id":"DDC01"} to filter snapshot
    ws.on("message", (raw) => {
      try {
        const msg = JSON.parse(raw.toString()) as Record<string, unknown>;
        if (msg.type === "subscribe" && typeof msg.device_id === "string") {
          ws.filter = msg.device_id;
          ws.send(JSON.stringify({ type: "subscribed", device_id: msg.device_id }));
        }
        if (msg.type === "ping") {
          ws.send(JSON.stringify({ type: "pong" }));
        }
      } catch {
        // ignore malformed messages
      }
    });
  });

  // Broadcast snapshot to all authenticated clients every N ms
  setInterval(() => {
    if (wss.clients.size === 0) return;
    const snapshot = getSnapshot(config.tenantId);

    wss.clients.forEach((ws) => {
      const client = ws as AuthenticatedWS;
      if (client.readyState !== WebSocket.OPEN || !client.userId) return;

      let payload = snapshot;
      // Apply device filter if subscribed
      if (client.filter) {
        payload = {
          ...snapshot,
          devices: { [client.filter]: snapshot.devices[client.filter] ?? {} },
        };
      }
      client.send(JSON.stringify({ type: "snapshot", data: payload }));
    });
  }, config.snapshotIntervalMs);

  return httpServer;
}
