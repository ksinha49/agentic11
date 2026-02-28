# `docs/` — Technical Documentation

Design documents, implementation plans, and architecture decisions.

## Documents

| File | Purpose |
|------|---------|
| `ARCHITECTURE.md` | System architecture — agents, pipeline, data layer, infrastructure |
| `plans/` | Design documents and implementation plans |

## Plans

| File | Status |
|------|--------|
| `2026-02-27-bluestar-platform-design.md` | Initial platform design |
| `2026-02-28-persistence-layer-design.md` | Phase 1 persistence layer design (approved) |
| `2026-02-28-persistence-layer-plan.md` | Phase 1 implementation plan (completed) |

## Architecture Highlights

- **5 AI agents** — Orchestrator, IDP, Validator, Transform, Compliance
- **Hybrid model serving** — In-process SLMs for high-volume agents, Bedrock API for complex reasoning
- **27-step pipeline** — Defined in DynamoDB, executed by Orchestrator
- **Protocol-based abstractions** — Agents depend on interfaces, not implementations
- **Multi-layer caching** — Redis (L1) + DynamoDB (L2) with configurable TTLs

## Adding Documentation

Follow the naming convention: `YYYY-MM-DD-<topic>-{design|plan}.md`

- **Design docs** describe *what* and *why* — architecture decisions, trade-offs, alternatives considered
- **Plan docs** describe *how* — step-by-step TDD implementation with exact file paths and commands
