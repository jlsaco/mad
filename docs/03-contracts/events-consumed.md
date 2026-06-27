---
service: mad
domain: backend
section: contracts
source_of_truth: repo
---

# Events Consumed

The events/callbacks Mad ingests from outside: the claude-cli hook callbacks
POSTed to the internal UDS adapter (`POST /_internal/hooks`), with the expected
payload and handling semantics (ADR-0008). If a surface has none, mark
`not applicable`.

Mad is infrastructure-only (hard rule 1): it launches external agents and
streams their stdout. The single class of event it *consumes* from the outside
world is the lifecycle hook stream emitted by **claude-cli** running inside a
provisioned workspace. claude-cli delivers each hook to a user-supplied script
on stdin; Mad materializes that script (`forward.sh`) into the workspace, which
forwards the payload to a private ingestion endpoint. No other inbound
callbacks, webhooks, or schedulers are consumed (per ADR-0004, translation and
orchestration of external payloads are explicitly deferred).

## Ingestion endpoint

- **Route:** `POST /_internal/hooks`
  (`src/mad/adapters/inbound/internal/hooks_router.py`).
- **Transport:** a **separate** internal FastAPI app
  (`src/mad/adapters/inbound/internal/app.py`, `create_internal_app`), bound
  **exclusively to a Unix Domain Socket** — never mounted on the public TCP app.
  The UDS path comes from `MAD_HOOK_SOCKET` (default
  `${XDG_RUNTIME_DIR}/mad/hooks.sock` or `/tmp/mad/hooks.sock`; resolved by
  `src/mad/adapters/outbound/agents/hook_socket.py`). `mad serve` runs two
  uvicorn servers — one on the public TCP bind, one on this UDS.
- **Schema-hidden / no docs:** the internal app sets `openapi_url=None`,
  `docs_url=None`, `redoc_url=None`, and the route is registered with
  `include_in_schema=False`. It does not appear in `/docs` or `/openapi.json`.
- **Access control (v0.1):** the UDS file permissions (`0600`) are the sole
  boundary — only the Mad process owner can connect. HMAC was considered and
  deferred (ADR-0008, Alternatives).
- **Status code:** `202 Accepted`.
- **Why separate:** putting a write-side ingestion route on the public TCP bind
  would risk exposing it to network peers on an auth slip. The UDS moves that
  residual risk from network-access to physical-access territory (ADR-0008,
  Context).

## Expected request payload

The body is the typed Pydantic model `HookIngestRequest`
(`src/mad/adapters/inbound/internal/hooks_router.py`):

| Field | Type | Constraint | Meaning |
|---|---|---|---|
| `session_id` | `str` | `min_length=1` | Session attribution; injected by the launcher via `MAD_SESSION_ID`. |
| `type` | `str` | pattern `^agent\.[a-z_]+\.hook\.[A-Za-z]+$` | The event type to emit (see vocabulary below). |
| `data` | `dict[str, Any] \| None` | optional | The verbatim hook payload from claude-cli (`hook_event_name` plus hook-specific fields). |

The response model is `HookIngestResponse` with a single field `event_id: str`
(the id of the event appended to the session log).

`forward.sh` constructs this body. It reads the hook JSON from stdin, extracts
`.hook_event_name` (defaulting to `Unknown`), and builds:

```json
{
  "session_id": "<MAD_SESSION_ID>",
  "type": "agent.<MAD_PROVIDER>.hook.<hook_event_name>",
  "data": <the raw hook payload>
}
```

It then `curl`s the body over `--unix-socket "$MAD_HOOK_SOCKET"` to
`http://mad/_internal/hooks`. If `MAD_HOOK_SOCKET` or `MAD_SESSION_ID` is
absent, `forward.sh` exits 0 without posting (it never blocks the agent).

## Mapping a hook to an event

Each hook becomes one event of type:

```
agent.<provider>.hook.<EventName>
```

- `<provider>` is supplied verbatim from `MAD_PROVIDER` (currently
  `claude_cli`).
- `<EventName>` is the verbatim `hook_event_name` claude-cli emits
  (e.g. `PreToolUse`, `PostToolUse`, `Stop`, `SubagentStop`). No translation,
  no classification, no Mad-native rename — per ADR-0004's verbatim-vocabulary
  mandate. If Claude Code renames a hook upstream, the Mad event type changes
  automatically.
- **Session attribution** is carried by `session_id` (from `MAD_SESSION_ID`,
  exported by the launcher to the subprocess before spawning), not derived from
  the payload.

The launcher exports three env vars to the spawned agent so this mapping works
end to end:

| Variable | Value | Purpose |
|---|---|---|
| `MAD_SESSION_ID` | current session UUID | hook payload attribution (`session_id`) |
| `MAD_HOOK_SOCKET` | resolved UDS path | where `forward.sh` posts |
| `MAD_PROVIDER` | `claude_cli` | the `<provider>` segment in the event type |

## Closed set of forwarded hooks

The hook list is **closed** — enumerated at ship time in
`src/mad/adapters/outbound/agents/hooks/settings.local.json`, which the launcher
materializes into each workspace. Unknown/new Claude Code hooks are deliberately
not captured until the list is extended (ADR-0008, Consequences). The forwarded
hooks are:

- `SessionStart`
- `SessionEnd`
- `UserPromptSubmit`
- `Stop`
- `StopFailure`
- `PreToolUse` (matcher `.*`)
- `PostToolUse` (matcher `.*`)
- `PostToolUseFailure` (matcher `.*`)
- `SubagentStart`
- `SubagentStop`
- `TaskCreated`
- `TaskCompleted`
- `Notification`

Each entry runs `bash $CLAUDE_PROJECT_DIR/.claude/hooks/forward.sh`.

## Handling semantics

1. **Validate.** FastAPI parses the body into `HookIngestRequest`; a malformed
   body or a `type` that fails the regex is rejected with `422` at the boundary.
2. **Scrub credentials.** `_scrub_credentials` walks `data` recursively (without
   mutating the input) and replaces values for credential-shaped keys
   (`token`, `authorization`, `api_key`, `password`, `secret`) with
   `[REDACTED]`, and substitutes any `sk-ant-...`-shaped substring in string
   values with `[REDACTED]`. This upholds token hygiene (hard rule 2) at the
   ingestion boundary.
3. **Emit through the single write gateway.** The router fetches the shared
   `EventEmitter` from `request.app.state.event_emitter` and calls
   `emit(session_id, type, scrubbed_data)`. It does NOT touch
   `SessionRepository` or `EventBus` directly (hard rule 11, ADR-0007). The
   internal app shares the **same `EventEmitter` instance** as the public app,
   so ingested hooks are appended to the session log and become immediately
   visible to live subscribers of `GET /v1/events/stream` — no second bus, no
   bridging adapter.
4. **Respond.** Returns `202` with `HookIngestResponse(event_id=...)`.

`forward.sh` treats the POST as fire-and-forget (`--max-time 5`, errors
swallowed with `|| true`): a slow or down ingestion endpoint never blocks or
fails the agent run.

## OpenCode

`not applicable` today. OpenCode hook capture is out of scope: the launcher
sets the same three env vars (including `MAD_HOOK_SOCKET`) on OpenCode runs for
future compatibility, but OpenCode does not currently read the socket or forward
hooks. Only `claude_cli` produces consumed hook events at present.
