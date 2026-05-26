import { config } from "@/config";
import { getToken } from "@/lib/keycloak";
import { useSnapshotStore } from "@/store/snapshot";

let socket: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let reconnectDelay = 1000;

export function connectWs() {
  if (socket?.readyState === WebSocket.OPEN) return;

  const token = getToken();
  if (!token) return;

  const url = `${config.wsBase}/ws?token=${encodeURIComponent(token)}`;
  socket = new WebSocket(url);

  socket.onopen = () => {
    reconnectDelay = 1000;
    useSnapshotStore.getState().setConnected(true);
  };

  socket.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data as string) as Record<string, unknown>;
      if (msg.type === "snapshot" && msg.data) {
        useSnapshotStore.getState().setSnapshot(msg.data as Parameters<typeof useSnapshotStore.getState>["0"]["snapshot"]);
      }
    } catch {
      // ignore malformed frames
    }
  };

  socket.onclose = () => {
    useSnapshotStore.getState().setConnected(false);
    socket = null;
    // Exponential backoff, cap at 30 s
    reconnectTimer = setTimeout(() => {
      reconnectDelay = Math.min(reconnectDelay * 2, 30_000);
      connectWs();
    }, reconnectDelay);
  };

  socket.onerror = () => {
    socket?.close();
  };
}

export function disconnectWs() {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  socket?.close();
  socket = null;
}

export function subscribeDevice(deviceId: string) {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "subscribe", device_id: deviceId }));
  }
}
