---
service: mad
domain: backend
section: decisions
source_of_truth: repo
---

# Architecture Decisions

Service-scoped ADR index. Mad already keeps ADRs under `docs/adr/` — this page is the catalog/entry-point for them (filename convention `NNNN-kebab-slug.md`); link each ADR with its one-line decision.

## Convention

- Filenames are `NNNN-kebab-slug.md`, zero-padded and sequential (`0001`, `0002`, …). The canonical format and review rules live in [`../adr/README.md`](../adr/README.md).
- ADRs use a slim Nygard format: **Context → Decision → Consequences → Alternatives considered**.
- Decisions are immutable once **Accepted** and merged to `main`. To change one, write a new ADR and mark the old one **Superseded by ADR-XXXX** — supersede rather than diverge silently, never delete.
- ADRs record *decisions*, not behavior. Behavior lives in code, in `CLAUDE.md` hard rules, or in the operational guides under `docs/`.

## Index

| ADR | Decision |
|---|---|
| [ADR-0001](../adr/0001-testing-strategy.md) | Adopt a layered testing heuristic: unit tests target `src/mad/core/` only (no I/O), integration tests cover adapters and end-to-end HTTP, never the real `claude` CLI or GitHub. |
| [ADR-0002](../adr/0002-quality-tooling-bundle.md) | Standardize the quality bundle — ruff, mypy (strict on `core/`), import-linter, pre-commit, gitleaks, pip-audit — all configured in `pyproject.toml` and wired through `Makefile` + CI. |
| [ADR-0003](../adr/0003-package-layout.md) | Use a hexagonal ports-and-adapters layout under `src/mad/`, organized domain-first: each bounded context owns its own `domain/`, `ports/`, and `use_cases/`. |
| [ADR-0004](../adr/0004-events-module-vocabulary-and-scope.md) | The events module accepts and emits Mad's event vocabulary verbatim — no superclass, enum, or translators; translation is deferred until a second event source exists. |
| [ADR-0005](../adr/0005-uuidv7-event-id.md) | Mint a UUIDv7 `event_id` per event so lexicographic ordering matches mint-time order, enabling `Last-Event-ID` catch-up across files and processes. |
| [ADR-0006](../adr/0006-multi-tenancy-deferred.md) | Defer multi-tenancy: no `tenant_id` on `Event`, no tenant filter on subscribe/query in v1. |
| [ADR-0007](../adr/0007-single-write-gateway-event-emitter.md) | Introduce `EventEmitter` as the single write gateway over a narrow `EventStore` port; every use case calls `emit()` rather than the persistence/bus ports directly. |
| [ADR-0008](../adr/0008-internal-hook-adapter-and-vocabulary.md) | Run a separate internal FastAPI app on a Unix Domain Socket for claude-cli hook ingestion, emitting `agent.<provider>.hook.*` events. |
| [ADR-0009](../adr/0009-orchestration-module.md) | Establish `core/orchestration/` as the control-plane home for session-lifecycle work (queue/dispatch/coordinate), bounded against `core/events`. |
| [ADR-0010](../adr/0010-mcp-mounted-http-inbound-adapter.md) | Expose MCP as a Streamable-HTTP ASGI app mounted at `/mcp` on the public FastAPI app — a peer inbound adapter whose tools call use cases in-process (Decision 3 superseded by ADR-0012). |
| [ADR-0011](../adr/0011-launcher-working-directory.md) | Align launcher cwd with the cloned repo via a hybrid rule: explicit `working_directory` > auto-derived single-github-mount path > workspace root. |
| [ADR-0012](../adr/0012-http-mcp-tool-parity.md) | Require full HTTP↔MCP parity: every request/response `/v1` route has exactly one MCP tool calling the same use case (CLAUDE.md hard rule 13); SSE streaming is the only carve-out. |

Note: ADR-0008 and ADR-0009 are listed in numeric order above; the source [`../adr/README.md`](../adr/README.md) index happens to list 0009 before 0008.
