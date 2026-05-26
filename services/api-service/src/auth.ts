import fp from "fastify-plugin";
import fastifyJwt from "@fastify/jwt";
import jwksRsa from "jwks-rsa";
import type { FastifyInstance, FastifyRequest, FastifyReply } from "fastify";
import { config } from "./config";

const jwksClient = jwksRsa({
  jwksUri: config.keycloakJwksUrl,
  cache: true,
  cacheMaxAge: 600_000,   // 10 min
  rateLimit: true,
});

export const authPlugin = fp(async (fastify: FastifyInstance) => {
  // @fastify/jwt v8 plugin type doesn't align with fastify.register overloads — double-cast
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  await (fastify.register as unknown as (p: unknown, o: unknown) => Promise<void>)(fastifyJwt, {
    secret: (
      _req: FastifyRequest,
      token: { header: { kid?: string } },
      callback: (err: Error | null, secret: string) => void,
    ) => {
      const kid = token.header.kid;
      if (!kid) return callback(new Error("JWT missing kid header"), "");
      jwksClient.getSigningKey(kid, (err, key) => {
        if (err) return callback(err, "");
        callback(null, key!.getPublicKey());
      });
    },
    verify: {
      issuer: config.keycloakIssuer,
    },
  });

  fastify.decorate(
    "authenticate",
    async (request: FastifyRequest, reply: FastifyReply) => {
      try {
        await request.jwtVerify();
      } catch {
        reply.code(401).send({ error: "Unauthorized" });
      }
    }
  );
});

/** Extract Keycloak realm roles from the decoded token. */
export function getRoles(request: FastifyRequest): string[] {
  const user = request.user as Record<string, unknown>;
  const realmAccess = user?.realm_access as { roles?: string[] } | undefined;
  return realmAccess?.roles ?? [];
}

/** Extract tenant from token (sub claim used as fallback). */
export function getTenantId(request: FastifyRequest): string {
  const user = request.user as Record<string, unknown>;
  return (user?.tenant_id as string) ?? config.tenantId;
}

declare module "fastify" {
  interface FastifyInstance {
    authenticate: (req: FastifyRequest, rep: FastifyReply) => Promise<void>;
  }
}
