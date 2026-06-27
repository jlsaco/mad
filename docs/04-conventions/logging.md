---
service: mad
domain: backend
section: conventions
source_of_truth: repo
---

# Logging and Observability

Logging/observability conventions. Mad's source of truth is the per-session JSONL event log written via the EventEmitter; every action is also printed to stdout (hard rule 6). There is no central logger module — document this dual write path and the event-log-as-truth model.

## There is no central logger

Mad deliberately has **no application logging framework** — no `logging.getLogger(...)`
config, no log-level hierarchy, no structured-logging library, no central logger module.
This is a design choice, not an omission: Mad's observability model is **event-log-as-truth**,
not app logs. What you would normally express as a log line is instead an *event* appended to
an append-only, per-session JSONL event log. That log is the single durable record of what
happened in a session, and the same vocabulary that drives behavior is what you observe
(ADR-0004 — the events module exposes the event vocabulary verbatim).

If you are looking for "where are the logs?", the answer is: the per-session JSONL files under
the sessions directory (`MAD_SESSIONS_DIR`, default `sessions/`), one file per session named
`<session_id>.jsonl`.

## The dual write path: log + stdout

Every action is recorded in two places at once:

1. **Appended to the per-session JSONL event log** — the durable, authoritative record.
2. **Printed to stdout** — for live process/console visibility.

Both writes happen in the same place. The durable write lives in
`src/mad/adapters/outbound/persistence/jsonl_session_repository.py`, in the module-level
`emit(...)` function:

```python
def emit(session_id, event_type, data=None):
    event = {
        "event_id": str(new_event_id()),
        "type": event_type,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if data:
        event.update(data)
    line = json.dumps(event)
    print(line)                         # (2) stdout
    ensure_sessions_dir()
    with log_path(session_id).open("a") as f:
        f.write(line + "\n")            # (1) durable JSONL append
    return event
```

The same JSON line is both `print`-ed and appended to `<session_id>.jsonl`. Each event carries:

- a UUIDv7 `event_id` (ADR-0005) — gives total cross-session ordering and powers SSE
  `Last-Event-ID` catch-up,
- a `type` string (the event vocabulary, e.g. `agent.output`, `session.status_idle`,
  `session.error`),
- an ISO-8601 UTC `timestamp`,
- plus any event-specific `data` fields merged in.

## EventEmitter is the single write gateway

Application code does **not** call the repository directly. The only sanctioned write path to
the event log is `EventEmitter.emit()` (`src/mad/core/events/emitter.py`, hard rule 11). Use
cases receive an `EventEmitter` as an injected dependency and call `emit()`; they MUST NOT call
`SessionRepository.append_event` or `EventBus.publish` themselves. Outbound adapters (e.g. the
launcher callback) receive an `emit` callable from the use case; inbound adapters (SSE, query)
only read.

`EventEmitter.emit()` does two things, in order:

```python
async def emit(self, session_id, type, data=None) -> Event:
    event = self._store.append(session_id, type, data)   # persist (the dual write above)
    await self._bus.publish(event)                        # publish to live subscribers
    if self._on_emit is not None:
        self._on_emit(event)
    return event
```

So a single `emit()` call: persists the event to JSONL (and stdout), then publishes it to the
in-process `EventBus` for live subscribers. Persist-before-publish is deliberate — the log is
written first, so a live subscriber can never observe an event that is not already durable.
Rationale and full scope live in ADR-0007.

## Why the log is authoritative (crash recovery / resume)

The session log is the **source of truth** (hard rule 6): if the process crashes, a new harness
reads the log and resumes from it. State is not held authoritatively in memory or in a database —
it is rebuilt by replaying the per-session JSONL. The repository exposes `read_events()` /
`get_events()` for exactly this replay, and a UUIDv7 `event_id` on every line makes the replay
deterministically ordered. Because the durable append happens before anything else acts on an
event, the log is always at least as complete as any observer's view.

This is why there is no separate "logs" concept to keep in sync with state: the log *is* the
state record.

## Observing a running session

Live and historical observation read the same event log — no separate logging pipeline:

- **SSE live tail — `GET /v1/events/stream`** (`StreamEventsUseCase`,
  `src/mad/core/events/use_cases/stream_events.py`). Subscribes to the `EventBus` first, then
  replays from the log for `Last-Event-ID` catch-up, then continues live — de-duplicating the
  overlap by `event_id`. Supports filtering by `session_id`, `kind`, and `agent`. This is the
  streaming surface and is the one carve-out from HTTP/MCP request-response parity (ADR-0004,
  hard rule 13).
- **Historical query — `GET /v1/events`** (`QueryEventsUseCase`,
  `src/mad/core/events/use_cases/query_events.py`). A request/response read over the log; it is
  also mirrored as the MCP tool `mad_query_events`.
- **Raw files** — the per-session `<session_id>.jsonl` files under `MAD_SESSIONS_DIR` can be
  read directly (each line is a complete JSON event).
- **Process stdout** — the same event lines are printed, so `make serve` / container logs show
  them inline.

Retention of the JSONL files is controlled by `MAD_SESSIONS_RETENTION_DAYS` (unset/zero/negative
= keep forever; see `resolve_retention_days` / `purge_expired_logs` in the repository).

## Credential scrubbing in streamed output

Because agent stdout/stderr is streamed verbatim into the event log, output is scrubbed for
secrets before it is recorded. The scrubber lives in
`src/mad/adapters/outbound/agents/_subprocess.py`:

```python
def _scrub(text: str) -> str:
    text = re.sub(r"sk-ant-[A-Za-z0-9_-]+", "[REDACTED]", text)
    text = re.sub(r"(?i)(token|key|secret|password)[=:\s]+\S+", r"\1=[REDACTED]", text)
    return text
```

It redacts Anthropic API keys (`sk-ant-...`) and `token`/`key`/`secret`/`password` assignments;
it is applied to captured launcher stderr before it is emitted on `session.error` (see
`claude_cli.py`). This complements token hygiene at the source (hard rule 2): GitHub tokens are
used only for `git clone` and then stripped from the remote with `git remote set-url`, and MUST
NOT be persisted to the workspace, the session log, or stdout. Since the log and stdout carry the
same lines, scrubbing once protects both halves of the dual write.

## Conventions summary

- Do **not** introduce a logging framework or a central logger. Record observable facts as events
  via `EventEmitter.emit()`.
- Never write the event log directly from a use case or inbound adapter — always go through
  `EventEmitter` (hard rule 11).
- Every emitted event is both persisted to per-session JSONL and printed to stdout; treat the
  JSONL log as authoritative (hard rule 6).
- Never let a credential reach the log or stdout — rely on `_scrub` for streamed output and on
  remote-URL stripping for tokens (hard rule 2).
- Observe sessions through `GET /v1/events/stream` (live) and `GET /v1/events` (historical),
  not through ad-hoc print statements.
