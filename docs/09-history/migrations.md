---
service: mad
domain: backend
section: history
source_of_truth: repo
---

# Migrations

Migrations log (what changed, when, reversibility). Mad has no schema-migration
framework (the store is an append-only JSONL event log, no DB), so this states
`not applicable` until that changes.

## Status: not applicable

Mad has no database and no schema-migration tooling. There is no Alembic, no
Flyway, no Django-style migrations, and no migration directory anywhere in the
tree. The only persistence is an **append-only, per-session JSONL event log**
written through `EventEmitter.emit()` (hard rule 11) and persisted by
`JsonlSessionRepository`. The log is the source of truth (hard rule 6); there is
no normalized relational schema to evolve, so the concept of a versioned,
reversible migration does not apply.

(The strings `migration` that appear in the repo are unrelated to a migration
framework: `pyproject.toml` defines a pytest marker — `smoke: hard-rule
invariants that must stay green across migration phases` — and
`src/mad/adapters/outbound/events/jsonl_event_log_query.py` carries a doc comment
referencing the ADR-0004 *migration path* to a future streaming/indexed store.
Neither is a schema-migration tool.)

## How Mad copes without migrations

Because there is no schema to migrate, Mad relies on the event log being
**append-only and forward-compatible**, and on readers that **tolerate
unknown/legacy event shapes** rather than rewriting history:

- **Free-form event `type`.** The event entity leaves `type` as a plain string
  on purpose so new vocabulary can be added without touching the entity or
  rewriting existing lines — see `src/mad/core/events/domain/event.py` (module
  docstring and the `Event` dataclass).
- **Legacy lines are read as-is.** `event_from_persisted` in the same file
  tolerates older records: lines written before UUIDv7 `event_id` minting
  (ADR-0005) surface with `event_id=None`, and lines without a `timestamp`
  default to the Unix epoch so they sort first. No backfill or rewrite is
  required; old lines simply age out.
- **Replay rebuilds state, ignoring what it does not recognize.**
  `rehydrate_from_events` in
  `src/mad/core/sessions/domain/rehydrate.py` reconstructs a `Session` by
  folding the event stream. It only acts on the event types it knows
  (`session.created`, `session.status_*`, `session.error`, `session.deleted`,
  `dispatch_policy.updated`/`cleared`, `dispatch_priority.updated`); any other
  or future event type is skipped harmlessly, and malformed policy/priority
  payloads fall back to the current value rather than failing the replay.

The practical consequence: a "schema change" in Mad is a **projection / replay
change**, not a destructive data migration. To evolve how state is derived, you
change the reader (the rehydrate fold or a use case) and let it reinterpret the
existing, untouched log — never an in-place transform of stored records.

## What would go here if a migration framework were ever adopted

This page would become the migrations log only if Mad introduces a real backing
store that needs versioned schema evolution (for example, a relational or
indexed event store — the streaming/indexed direction noted in ADR-0004, or any
future store under a new bounded context). At that point, each migration would
be recorded here with:

- A migration identifier / revision and the date it landed.
- What changed (tables, columns, indexes, or the on-disk event format).
- The forward step and its reverse (downgrade) step, i.e. whether and how it is
  reversible.
- Any data backfill performed and how running sessions were handled during the
  transition.

Until such a store exists, this page stays `not applicable`.
