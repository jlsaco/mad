---
service: mad
domain: backend
section: operations
source_of_truth: repo
---

# Service Level Objectives

Mad has **no formally-defined SLOs, SLIs, or error budgets** at this stage. There
is no availability target, no latency objective, no published uptime commitment,
and no alerting threshold encoded anywhere in the repo. Treating any number below
as a contractual guarantee would be wrong — they are *implicit operational
expectations* baked into code and configuration, captured here so operators know
what the system already promises itself.

Formalizing these into measured SLIs with error budgets is a deliberate future
exercise, not something the code does today.

## Implicit operational expectations

Each item below is an expectation that the running system enforces or assumes,
with its current value and where it is set. They are the closest thing Mad has to
"targets" — bound the behavior, but are not monitored against an objective.

### Agent wall-clock timeout

Every agent run has a hard wall-clock budget. The use case resolves it once and
passes the concrete value into the launcher's `run(timeout_s=...)`; launchers
never read a timeout env var themselves.

- **Precedence (most specific wins):** per-session `timeout_s` (from
  `CreateSessionRequest`) > `MAD_AGENT_TIMEOUT_S` env var (operator default) >
  hard-coded `600.0` s default.
- **Where set:** `src/mad/core/orchestration/domain/timeout_config.py`
  (`resolve_effective_timeout`, `DEFAULT_AGENT_TIMEOUT_S = 600.0`,
  `AGENT_TIMEOUT_ENV_VAR = "MAD_AGENT_TIMEOUT_S"`); enforced in
  `claude_cli.py` / `opencode.py` via `asyncio.timeout(timeout)`.
- **On breach:** the subprocess is killed and `session.error`
  (`"timed out after {timeout}s"`) is emitted. This is the implicit upper bound
  on how long a single dispatch can occupy the system.

### Single in-flight dispatch and tick cadence

The dispatcher is serial: it runs at most one launcher at a time across all
sessions (ADR-0009 Decision 4). There is no cross-session parallelism in v1.

- **Concurrency target:** exactly one in-flight task, tracked locally as
  `_in_flight = (session_id, task_id)`.
- **Tick cadence:** `_DEFAULT_TICK_INTERVAL_S = 30.0` s — the interval at which
  the dispatcher re-evaluates the queue (e.g. for work-window openings).
- **Where set:** `src/mad/core/orchestration/use_cases/dispatcher.py`.
- **Implication:** throughput is bounded by serial execution; queued tasks wait
  behind the current run. This is an intentional v1 simplification, not a tuned
  capacity target.

### Rate-limit retry / backoff schedule

When the agent CLI reports a transient signal (429 / 529 / transient 401,
`rate_limit`, `overloaded`, `authentication_failed`), the dispatcher retries with
exponential backoff instead of failing the task. These constants are fixed in v1
(a follow-up will make them configurable).

- **Base interval:** 30 s, **multiplier:** 2 (doubles per attempt),
  **per-interval cap:** 3600 s (1 h), **jitter:** +/-10 %.
- **Cumulative ceiling:** 18000 s (5 h) — after which the task is failed with
  `reason: "rate_limit_exhausted"`.
- **resetsAt floor:** if the CLI advertises a `resetsAt`, the wait is raised to
  that instant rather than hammering the API on the plain schedule.
- **Where set:** `src/mad/core/orchestration/domain/retry_schedule.py`
  (`backoff_s`, `exceeds_ceiling`, `CUMULATIVE_CEILING_S`); driven in
  `dispatcher.py::_run_task`.
- **Implication:** the implicit "maximum time a rate-limited task is kept alive"
  is ~5 h of cumulative wait before it is declared exhausted.

### Work-window deferral

A session pinned to a `work_window` dispatch policy only launches inside its open
windows. A rate-limit retry re-gates against the window: if the window has closed
mid-run, the task is deferred back to the queue (`task.deferred`,
`reason: "work_window_closed"`) and re-dispatched at the next opening rather than
busy-waiting.

- **Where set:** `dispatcher.py` (`_window_closed`, `_defer_to_window`);
  policy types in `src/mad/core/orchestration/domain/dispatch_policy.py`.
- **Default policy:** `immediate` (no window restriction) unless an operator or
  session pins otherwise.

### JSONL log retention TTL

The per-session JSONL event logs (the source of truth, hard rule 6) are kept
forever by default. An operator can opt into time-based purging.

- **Knob:** `MAD_SESSIONS_RETENTION_DAYS` (positive integer = days to keep).
  Unset, zero, negative, or non-integer all resolve to `None` = retention
  disabled / keep every log forever (the safe default).
- **Cutoff basis:** a log is purged when its **last** event `timestamp` is
  strictly older than `now - retention_days` (last, not first, so an actively
  appended log is never deleted under a live session). Reserved `__`-prefixed
  internal streams are never purged.
- **When applied:** once at app startup (`create_app` lifespan in
  `src/mad/adapters/inbound/http/app.py`), via
  `purge_expired_logs(datetime.now(UTC), retention_days)` — not on a recurring
  schedule.
- **Where set:** `src/mad/adapters/outbound/persistence/jsonl_session_repository.py`
  (`resolve_retention_days`, `purge_expired_logs`, `RETENTION_DAYS_ENV`).

### SSE slow-subscriber disconnect

The live event stream (`GET /v1/events/stream`) does not block the publisher or
silently drop events for a slow client — it disconnects the slow subscriber
(ADR-0004).

- **Per-subscriber buffer:** bounded `asyncio.Queue`, default size 256
  (`_DEFAULT_QUEUE_SIZE` in
  `src/mad/adapters/outbound/events/in_memory_event_bus.py`). When the queue
  fills (publisher faster than the subscriber drains), the bus disconnects that
  subscriber.
- **Recovery path:** the client reconnects with its last-seen `Last-Event-ID`
  and catches up via the JSONL log query (`GET /v1/events`); the live tail stays
  lossless from the subscriber's perspective without coupling throughput to the
  slowest consumer.
- **Heartbeat:** a comment-frame ping every `MAD_SSE_HEARTBEAT_S` seconds
  (default 15) keeps the connection alive behind buffering proxies
  (`src/mad/adapters/inbound/http/routes/events.py`).
- **Implicit expectation:** an "always-on" stream is **not** guaranteed for a
  consumer that cannot keep up; reconnect-with-`Last-Event-ID` is the contract.

## Future work

To turn the above into real SLOs, a future effort would need to: pick measured
SLIs (e.g. dispatch success rate, time-to-first-`agent.output`, stream
reconnect rate), define objectives and an error budget, and wire monitoring /
alerting — none of which exists in the repo today. Environment-variable
centralization (tracked in issue #97) would also give these knobs a single
source of truth instead of the current ad-hoc `os.environ` reads.
