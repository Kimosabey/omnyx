import Keycloak from "keycloak-js";
import { config } from "@/config";

const kc = new Keycloak({
  url:      config.keycloakUrl,
  realm:    config.keycloakRealm,
  clientId: config.keycloakClient,
});

export interface AuthUser {
  sub:      string;
  name:     string;
  email:    string;
  roles:    string[];
  token:    string;
}

export async function initKeycloak(): Promise<AuthUser | null> {
  try {
    const authenticated = await kc.init({
      onLoad:          "login-required",
      checkLoginIframe: false,
      pkceMethod:      "S256",
    });

    if (!authenticated) return null;

    // Auto-refresh token 60 s before expiry
    setInterval(() => {
      kc.updateToken(60).catch(() => kc.logout());
    }, 30_000);

    return buildUser();
  } catch {
    return null;
  }
}

function buildUser(): AuthUser | null {
  if (!kc.authenticated || !kc.tokenParsed || !kc.token) return null;
  const p = kc.tokenParsed as Record<string, unknown>;
  return {
    sub:   p.sub as string,
    name:  (p.name as string) ?? (p.preferred_username as string) ?? "User",
    email: (p.email as string) ?? "",
    roles: ((p.realm_access as { roles?: string[] })?.roles) ?? [],
    token: kc.token,
  };
}

export function getToken(): string | undefined {
  return kc.token;
}

export function logout() {
  return kc.logout({ redirectUri: window.location.origin });
}

export function hasRole(role: string): boolean {
  return kc.hasRealmRole(role);
}
