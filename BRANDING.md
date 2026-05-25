# OMNYX — Brand & Naming Reference

> One page that fixes the names so every doc, slide, login screen, and email reads the same.

## 1 · Hierarchy

```
            Graylinx           ← Parent company / wordmark
              │
              ▼
            OMNYX              ← Universal IoT Operations Platform (the v1.1 product)
              │
   ┌──────────┼──────────┬──────────┬──────────┐
   ▼          ▼          ▼          ▼          ▼
THERMYNX   FORGYNX    AQUYNX    VOLTYNX    (future)
 HVAC       Factory    Water    Power
```

Vertical names with `-YNX` suffix are placeholders for later phases — only **THERMYNX** is committed today (Unicharm).

## 2 · Wordmark usage

| Surface | Lockup |
|---|---|
| Top of login | `OMNYX` (large) · `Universal IoT Operations Platform` (subhead) |
| Sidebar footer | `OMNYX · by Graylinx` |
| Browser tab title | `OMNYX — <page name>` |
| HVAC vertical chrome | `THERMYNX · by Graylinx` (kept exactly as today at Unicharm) |
| API health endpoint product field | `"product": "omnyx"` |

When OMNYX is rendered as plain text in body copy, set as small-caps where possible: `Omnyx`. Otherwise all-caps `OMNYX` is acceptable.

## 3 · Why OMNYX

- **`omni-`** = all / universal — aligns with the PRD §05 promise of being domain-agnostic and protocol-agnostic.
- **`-YNX`** mirrors the existing THERMYNX, so the family looks like a system.
- One token, two syllables, easy to say (om-niks).
- Available as `.com`, `.ai`, `.io`, and X handle at the time of this writing — verify before public launch.

## 4 · Visual language (inherited from THERMYNX design system)

Re-uses Graylinx Brand v2 tokens from [`d:/Harshan/HVAC AI Operations Intelligence Platform/THERMYNX Design System/colors_and_type.css`](../../HVAC%20AI%20Operations%20Intelligence%20Platform/THERMYNX%20Design%20System/colors_and_type.css):

- **Type:** Inter for body, Inter Display / Inter Tight for product wordmark
- **Casing:** Title Case for page titles, UPPERCASE 0.1em-tracked for eyebrows / badges, Sentence case for buttons
- **Voice:** technical, calm, declarative; second-person imperative when addressing the user; no marketing fluff
- **Empty-state phrasing:** factual and reassuring, no emoji

The brand assets copied from THERMYNX live in [`assets/brand/`](./assets/brand/); a clean OMNYX wordmark SVG should be commissioned during Phase 0 — placeholder is a wordmark composed from the inherited type stack.

## 5 · Voice — taglines per audience

| Audience | Tagline |
|---|---|
| CTO / Portfolio Manager | *"OMNYX — one platform for every plant, on your hardware."* |
| Site Operator | *"OMNYX gives you the next action, not just another alert."* |
| Maintenance Technician | *"OMNYX writes the work order before the call."* |
| AI Operations Specialist | *"OMNYX — Planner, Executor, Validator. Auditable autonomy."* |

## 6 · Don'ts

- Don't call it "CloudOps" externally — that's the internal PRD codename. Public name is **OMNYX**.
- Don't write "Graylinx OMNYX" as a product compound — it's "OMNYX by Graylinx".
- Don't introduce a new colour palette or font. Inherit Graylinx Brand v2 verbatim.
- Don't put exclamation marks anywhere in product copy.

## 7 · File and code references

- Project folder on disk: `omnyx/`
- npm scope / Python package prefix: `@omnyx/...` and `omnyx_*`
- Docker image tags: `graylinx/omnyx-<service>:<version>`
- Kafka client.id: `omnyx-<service>`
- Topic prefix: none — topics use canonical names (`raw.bacnet.*`, etc.) so the same topology fits any product family running on the same broker.
