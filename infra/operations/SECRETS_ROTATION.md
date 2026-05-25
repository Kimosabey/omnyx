# Secrets Rotation

## Scope

Rotate the following on every customer deployment and after any suspected exposure:

- `POSTGRES_PASSWORD`
- `KEYCLOAK_ADMIN_PASSWORD`
- Keycloak client secrets
- `ANTHROPIC_API_KEY`
- any replay / legacy source credentials

## Rotation order

1. rotate secrets in the customer vault or local secret store,
2. update `infra/compose/.env`,
3. restart affected services,
4. validate `/healthz`, login, and agent workflows,
5. record the change in the audit log or deployment ticket.

## Minimum cadence

- database and admin secrets: every 90 days
- external AI provider keys: every 90 days or immediately on suspicion
- site-specific replay credentials: at each onboarding / offboarding event
