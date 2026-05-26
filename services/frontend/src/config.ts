export const config = {
  apiBase:       import.meta.env.VITE_API_BASE        ?? "http://localhost:8080",
  wsBase:        import.meta.env.VITE_WS_BASE         ?? "ws://localhost:8765",
  keycloakUrl:   import.meta.env.VITE_KEYCLOAK_URL    ?? "http://localhost:8282",
  keycloakRealm: import.meta.env.VITE_KEYCLOAK_REALM  ?? "omnyx",
  keycloakClient:import.meta.env.VITE_KEYCLOAK_CLIENT ?? "omnyx-frontend",
  tenantId:      import.meta.env.VITE_TENANT_ID       ?? "unicharm",
} as const;
