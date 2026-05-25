# Incident Response

## Severity levels

- `SEV1`: platform down, safety-critical workflow blocked, or data corruption suspected
- `SEV2`: partial workflow outage or major latency degradation
- `SEV3`: non-critical degradation or single integration issue

## First 15 minutes

1. confirm customer impact,
2. capture timestamps, affected services, and last known good deploy,
3. collect logs, compose status, and support bundle,
4. pause RL or agentic workflows if autonomy is implicated,
5. communicate status to the customer operator.

## Containment actions

- `docker compose restart <service>` for single-service crashes
- disable agent workflows if approval or loop-guard behavior is suspect
- pause RL agents before investigating control anomalies
- switch to simulator / replay mode if a live source is unstable

## Evidence to capture

- `docker compose ps`
- service logs
- Grafana screenshots
- Kafka lag / topic health
- recent audit events
