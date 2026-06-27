---
service: mad
domain: backend
section: meta
source_of_truth: repo
---

# Mad — Documentation

The local docs manual. Explains the /docs structure and what each section
contains. Hand-authored once; rarely changes.

This is the entry point for Mad's `/docs` tree. It is a navigational map, not a
copy of the content — read it to find the right page, then open that page. The
structure below is driven by `docs/.docs-manifest.yaml` (the source of truth for
what exists and how each page stays current); project rules and the key-files map
live in `CLAUDE.md` at the repo root.

## How the tree is organized

The tree is a fixed set of nine numbered sections. Lower numbers are the
why/what (intent, architecture, contracts); higher numbers are the how
(operations, history). Numbered prefixes keep the reading order stable.

## Section map

### 01-overview — what the service is and is not

- `passport.md` — one-page service card: `service`/`domain`, the interface
  profile (http + sse + mcp + cli), and which optional sections this repo
  declares.
- `context.md` — upstream and downstream systems (who calls Mad; what Mad
  calls), with a context diagram.
- `domain.md` — the entities and business rules Mad owns (Session, Event, Task,
  MountPath, orchestration policies).
- `operations.md` — catalog of operations (one row per use case) with its input
  surface and observable side effects.
- `scope.md` — explicit non-goals: Mad launches external agents and streams
  stdout; it never parses tool calls, executes tools, or runs an agent loop
  (hard rule 1).
- `glossary.md` — the domain language; one term, one definition.

### 02-architecture — how it is built

- `overview.md` — architecture narrative and a C4 container diagram; names the
  hexagonal ports-and-adapters style.
- `components.md` — internal modules and boundaries: the core bounded contexts
  (sessions, events, orchestration), the adapter groups, and the ports between
  them.
- `data-model.md` — the persistent model and storage strategy. Mad has no DB;
  the store is an append-only per-session JSONL event log (hard rule 6).
- `source-tree.md` — exact ASCII tree of `src/mad` (generated).
- `test-tree.md` — exact ASCII tree of `tests/` (generated).

### 03-contracts — the surfaces other systems depend on

- `api.md` — the HTTP API as an OpenAPI document, dumped from the app.
- `events-published.md` — events Mad emits (`agent.output`,
  `session.status_idle`, `session.error`, `agent.<provider>.hook.*`).
- `events-consumed.md` — events Mad ingests: the claude-cli hook callbacks
  POSTed to the internal UDS adapter.
- `jobs.md` — background/scheduled work: the orchestration dispatcher loop and
  auto-sync (no classic cron).
- `external-dependencies.md` — third parties Mad relies on (the agent CLIs,
  GitHub, the runtime SDKs) and their quirks.

### 04-conventions — the rules code follows

- `api-design.md` — the `/v1` prefix, typed Pydantic request/response models,
  HTTP↔MCP tool parity.
- `auth.md` — the auth model: no in-app auth; authentication happens at the
  Cloudflare edge.
- `error-handling.md` — the error taxonomy and how domain exceptions map to HTTP
  responses.
- `logging.md` — observability: the JSONL event log plus stdout (dual write
  path; no central logger).
- `quality.md` — linters and quality gates (ruff, mypy, import-linter,
  pre-commit, gitleaks, pip-audit).
- `testing-strategy.md` — test layers, the eight testing heuristics, coverage,
  and the fakes-in-`tests/support` convention.

### 05-operations — how it runs

- `ci-cd.md` — pipeline stages and what each one gates.
- `configuration.md` — configuration keys (never values): purpose, type,
  default, required.
- `deployment.md` — how Mad ships and runs (container image, compose, PyPI
  release, Cloudflare Tunnel).
- `local-dev.md` — running and debugging locally (`make install` / `make
  serve`, the dual uvicorn).
- `scripts.md` — inventory of Makefile targets and helper scripts (generated).
- `known-issues.md` — known tech debt and current limitations.
- `slos.md` — SLOs / targets, or the implicit expectations if none are formal.
- `runbooks/README.md` — operational procedures, one file per procedure.

### 06-flow-participation — Mad's seat in end-to-end flows

- `README.md` — Mad's role in each cross-service flow (inputs, outputs,
  ordering); one file per flow.

### 07-decisions — architecture decisions

- `README.md` — service-scoped ADR index. The ADRs themselves live in
  `docs/adr/` (filename convention `NNNN-kebab-slug.md`); this page links each
  one with its one-line decision.

### 08-rfcs — proposals before a decision

- `README.md` — free-form proposals and trade-offs; index plus one file per RFC.

### 09-history — what changed over time

- `changelog.md` — released versions, mirrored from the semantic-release
  `CHANGELOG.md` (not a raw git log).
- `migrations.md` — migrations log; `not applicable` for Mad (append-only JSONL
  log, no schema-migration framework).

## The living-docs model

The tree is driven by `docs/.docs-manifest.yaml`: it lists every page, the
section it belongs to, how it is kept current, and (for generated pages) the
exact command that produces it. Each page declares one of three kinds:

- `deterministic` — generated byte-for-byte by `gen_docs` and diffed in CI; never
  hand-edited (e.g. `source-tree.md`, `test-tree.md`, `scripts.md`).
- `heuristic` — derived from the code but authored as prose; refreshed when its
  trigger paths drift (e.g. `api.md`, `configuration.md`, `changelog.md`).
- `manual` — intent-level prose with no code trigger; age-checked via
  `max_age_days` (e.g. most of `01-overview`, the ADR/RFC/flow indexes, this
  file).

ADRs are kept outside this generated tree under `docs/adr/` (indexed from
`docs/adr/README.md` and from `07-decisions/README.md`). When the structure
itself changes, edit `docs/.docs-manifest.yaml` first — it is the source of
truth, and this README is the human-readable view of it.
