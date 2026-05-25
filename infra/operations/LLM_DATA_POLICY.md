# LLM Data Policy

## Default stance

Phase 1 remains on customer premises. Only the minimum workflow context required for an approved agent task may be sent to an external model provider.

## Allowed

- summarized alert context
- sanitized equipment metadata
- approved workflow payloads with no credentials or raw personal data

## Not allowed

- database credentials
- customer secrets
- raw operator personal data
- full telemetry histories unless the customer explicitly approves the policy

## Controls

- provider selection is explicit via `LLM_BACKEND`
- workflow prompts must be logged with sensitive fields redacted
- all agent actions remain approval-gated unless policy says otherwise
