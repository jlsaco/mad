---
service: mad
domain: backend
section: overview
source_of_truth: repo
---

# Glossary

The domain language used across these docs. One term, one definition. Where a
term maps to a concrete file, type, or ADR, the entry says so; definitions are
faithful to how `CLAUDE.md` and `src/mad/` use the word, not to general usage.

## Adapter

An I/O implementation that lives outside `mad.core` under `src/mad/adapters/`.
Inbound adapters drive Mad (HTTP, MCP, the internal UDS hook receiver);
outbound adapters are driven by Mad (persistence, agent launchers, the event
bus). Each adapter implements or consumes a `port` (see *Port*). This is the
"adapters" half of the hexagonal layout in [ADR-0003](../adr/0003-package-layout.md).

## Agent

An external, autonomous coding harness (Claude Code, OpenCode, Codex) that Mad
launches against a provisioned workspace. The agent brings its own loop, tools,
and LLM calls; Mad only spawns it, streams its stdout, and reports completion.
Mad never parses the agent's tool calls or runs its conversation loop (hard
rule 1).

## Agent launcher

See *Launcher*.

## Auto-sync

A second, fixed agent run that Mad always fires after the primary user-prompt
run finishes (success or failure), in the same workspace. The prompt
(`src/mad/core/sessions/use_cases/auto_sync_prompt.py`) instructs the agent to
branch, commit pending work, push, and open a PR, always excluding
`.claude/settings.local.json` and `.claude/settings.json`. Mad only orchestrates
"always run this second prompt"; all decision logic lives in the prompt (issue #8).

## Base branch

The git ref a session's work (and its auto-sync) branches from. Carried on the
`Session` entity as `base_branch`; defaults to the current `HEAD` when omitted.

## Composition root

`src/mad/adapters/inbound/http/dependencies.py` — the single place that builds
the production defaults for every outbound dependency (repository, provisioner,
event store, `EventEmitter`, launcher factory) and hands them to `create_app(...)`.
Tests bypass it by injecting doubles directly into `create_app`.

## Conversation ID

The identifier an external agent returns for a resumable conversation. Stored
transiently on the `Session` as `last_conversation_id` and recorded
authoritatively in the event log as `agent.conversation_started`. A task may
request `conversation_mode` of `new` or `resume`.

## Deployment policy

A process-global default that every session inherits unless it pins its own
override. Mad has no first-class `Workspace` entity (multi-tenancy is deferred,
[ADR-0006](../adr/0006-multi-tenancy-deferred.md)), so "deployment-wide" means
one default for the whole instance. Concretely: `DeploymentDispatchPolicy`
(default dispatch policy), `DeploymentModelConfig`, and `DeploymentEffortConfig`.
Each is persisted under a reserved session log (e.g. `__deployment__`) via the
normal `EventEmitter` path so it survives restart.

## Dispatch policy

The rule that decides when a session's queued tasks are dispatched. Resolution
order is the session's own override, else the deployment default, else
`ImmediatePolicy` (`src/mad/core/orchestration/domain/deployment_policy.py`).

## Dispatcher

The orchestration loop that turns queued tasks into launcher runs
(`src/mad/core/orchestration/use_cases/dispatcher.py`). A lifespan-managed
asyncio task that subscribes to all bus events, keeps the task projection
current, and runs a single task in-flight at a time (serial across all sessions
in v1; cross-session parallelism is deferred).

## Effort config

The reasoning-effort hint passed to a launcher (`effort` on the `Session` /
`Task`). Resolved per session with the same precedence pattern as model config;
`None` means omit it and let the provider decide.

## Event

A single immutable observation in Mad's log (`src/mad/core/events/domain/event.py`):
`event_id`, `session_id`, `type`, `data`, `timestamp`. The `type` is a free-form
string carrying Mad's vocabulary verbatim (e.g. `session.created`, `user.message`,
`agent.output`, `session.status_idle`, `session.error`, `task.queued`).

## Event bus

The pub/sub port (`src/mad/core/events/ports/event_bus.py`) that delivers live
events to subscribers via an async iterator, filtered by `EventFilter`. The
reference `InMemoryEventBus` disconnects slow subscribers whose queues fill,
expecting them to reconnect with `Last-Event-ID` and catch up via the query
surface ([ADR-0004](../adr/0004-events-module-vocabulary-and-scope.md)).

## Event ID

A UUIDv7 minted per event ([ADR-0005](../adr/0005-uuidv7-event-id.md)). Its
time-ordering enables `Last-Event-ID` catch-up after an SSE reconnect. Legacy
events written before minting was introduced may have `event_id = None`.

## Event log

The append-only, per-session JSONL file that records every action. It is the
source of truth: if the process crashes, state is rebuilt by replaying the log
(hard rule 6). Written by `JsonlSessionRepository`; there is no database.

## EventEmitter

The single write gateway to the event log
(`src/mad/core/events/emitter.py`). `emit()` appends to the `EventStore` then
publishes to the `EventBus`. Use cases receive it injected and call `emit()`;
they MUST NOT call `EventStore.append` or `EventBus.publish` directly (hard
rule 11, [ADR-0007](../adr/0007-single-write-gateway-event-emitter.md)).

## EventStore

The narrow persistence port `EventEmitter` depends on
(`src/mad/core/events/ports/event_store.py`): `append(session_id, type, data)
-> Event`. The only persistence surface the emitter knows about.

## Hexagonal / ports and adapters

The architectural style of the repo: a framework-free `mad.core` of domain,
ports, and use cases, surrounded by `mad.adapters` that implement the ports.
`mad.core` may not import FastAPI, `subprocess`, or any adapter (hard rule 4,
[ADR-0003](../adr/0003-package-layout.md)).

## Hook

A callback that the claude-cli agent fires during its run. Mad materializes a
`forward.sh` and `settings.local.json` into each workspace; the script POSTs the
hook payload to an internal Unix-domain socket, where the internal inbound
adapter ingests it and re-emits it as an `agent.<provider>.hook.*` event
([ADR-0008](../adr/0008-internal-hook-adapter-and-vocabulary.md)). The hook list
is closed. (Distinct from the optional `on_emit` callback inside `EventEmitter`.)

## Launcher

An outbound `AgentLauncher` implementation that spawns an external agent with
`cwd=workspace`, streams its stdout line-by-line as `agent.output` events, and
emits `session.status_idle` (exit 0) or `session.error` (non-zero / timeout) on
completion. Selected by name via
`mad.adapters.outbound.agents.factory.get_launcher`. The protocol's `run(...)`
receives the resolved wall-clock `timeout_s` from the use case; launchers never
read a timeout env var themselves (issue #61).

## Model / effort config

The optional `model` and `effort` hints attached to a session or task.
`DeploymentModelConfig` (`src/mad/core/orchestration/domain/model_config.py`)
holds the process-global model default; `None` everywhere means omit `--model`
and let the provider use its own default. See also *Effort config*.

## Mount path

A request-supplied path mapped to a subdirectory of the session workspace,
modeled by the `MountPath` value object
(`src/mad/core/sessions/domain/value_objects/mount_path.py`). Construction
rejects any path that would escape `/workspace`, enforcing path-traversal
prevention (hard rule 3) before any filesystem operation.

## MCP

Model Context Protocol — a first-class consumer of Mad, mounted as a
Streamable-HTTP ASGI app at `/mcp`
([ADR-0010](../adr/0010-mcp-mounted-http-inbound-adapter.md)). Every JSON
request/response `/v1` route has exactly one mirrored MCP tool that calls the
same use case with the same in-process dependencies and returns the same
Pydantic model (parity, hard rule 13). The streaming SSE surface is the only
carve-out.

## Port

A `Protocol` interface in `mad.core` that defines a boundary the domain depends
on without knowing its implementation. Outbound ports include
`SessionRepository`, `WorkspaceProvisioner`, `AgentLauncher`, `EventStore`,
`EventBus`, and `TaskQueue`. Adapters implement them; see *Adapter*.

## Provider

A named launcher backend dispatched by `get_launcher`. Current production
providers are `claude_cli` (spawns `claude --dangerously-skip-permissions -p`,
configurable via `MAD_CLAUDE_CLI_BIN`) and `opencode` (spawns `opencode run`,
configurable via `MAD_OPENCODE_BIN`). The provider name is also the `<provider>`
segment in `agent.<provider>.hook.*` event types.

## Rehydrate

Rebuilding an in-memory `Session` entity by replaying its persisted events
(`src/mad/core/sessions/domain/rehydrate.py`). A pure domain helper with no I/O;
used by `GetSession` and `ListSessions` to recover sessions absent from the live
index, and by orchestration to recover pending sessions on restart (hard rule 6).

## Session

The primary aggregate root (`src/mad/core/sessions/domain/entities/session.py`),
tracking one agent invocation through `created -> running -> idle | error` (and
`deleted` from any state). Holds the agent spec, workspace and working
directory, model/effort/timeout, mounted resources, dispatch policy, and
priority.

## SSE

Server-Sent Events — the live event stream at `GET /v1/events/stream`
(`StreamEventsUseCase`). Treated as operator telemetry, not a request/response
tool, so it is the one surface exempt from HTTP↔MCP tool parity (hard rule 13).
Reconnecting clients resume with `Last-Event-ID`.

## Task

A unit of orchestrated work submitted via `POST /v1/sessions/{id}/tasks`
(`src/mad/core/orchestration/domain/task.py`). Its `content` is opaque — the
orchestration module never inspects it and the launcher receives it verbatim.
State is not carried on the entity: the projection holds `queued` / `in_flight`,
and the full history (`task.queued` -> `task.dispatched` ->
`task.{completed,cancelled,failed}`) lives in the event log.

## Use case

Application logic in `mad.core/**/use_cases/` that orchestrates ports to fulfill
a request (e.g. `CreateSessionUseCase`, `SendUserMessageUseCase`,
`QueryEventsUseCase`). Use cases receive their dependencies — including the
`EventEmitter` — injected; they never reach for production adapters directly.

## Workspace

The isolated, per-session directory Mad provisions on disk (via
`LocalWorkspaceProvisioner`), into which it clones repositories and materializes
hook files. The launcher's effective `cwd` — the cloned repo path for a
single-GitHub-mount session, the workspace root otherwise, or a caller-specified
`working_directory` ([ADR-0011](../adr/0011-launcher-working-directory.md)).
There is no first-class multi-tenant `Workspace` entity; see *Deployment policy*.
