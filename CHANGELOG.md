# CHANGELOG


## v0.2.0 (2026-04-30)

### Continuous Integration

- **pypi**: Enable manual publishing via workflow dispatch
  ([`2e92c69`](https://github.com/jlsaco/mad/commit/2e92c692d88c35e3a483d6dd09c5c03166e997e6))

- **release**: Disable TestPyPI publishing and update dependencies
  ([`b261efb`](https://github.com/jlsaco/mad/commit/b261efb8bb876cd49e4344b1059a7bbfff66e450))

### Documentation

- **claude-cli**: Add comprehensive specification for provider implementation
  ([`4f2fb88`](https://github.com/jlsaco/mad/commit/4f2fb88435fcb3a8bacd2cad13078a66a88eb8dd))

Introduce detailed specs for the claude-cli provider feature, including README, requirements,
  design, and plan documents. These define the functional requirements, internal workings,
  subprocess lifecycle, error handling, and implementation guidelines to enable spec-driven
  development of the Claude CLI integration without modifying existing APIs or contracts. Covers
  authentication reuse, stream-json parsing, tool schema passthrough, and testing isolation
  constraints.

- **infra**: Rewrite spec to reflect infrastructure-only architecture
  ([`7eba26d`](https://github.com/jlsaco/mad/commit/7eba26dab64887a66017b1a849ecfb00e3a75c73))

- Remove FR-6 agent loop / FR-11 native tool use — Mad no longer manages conversation turns or
  executes tools on behalf of agents - FR-6 now describes launching an external agent process
  (Claude Code, etc.) that handles its own harness internally - FR-10 introduces the AgentLauncher
  protocol; claude_cli launches `claude --dangerously-skip-permissions -p "{prompt}"` in the
  workspace - design.md: replace Sandbox + Harness components with single Launcher; event vocabulary
  drops agent.message/tool_use/tool_result, adds agent.output - plan.md: Rule 8 documents
  AgentLauncher protocol; Rule 9 (native tool use) removed; out-of-scope section explicitly calls
  out task queue + scheduler as the next natural feature for Mad

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- **specs**: Rename v0.1 to infra, revise claude-cli spec, add /commit command
  ([`1c42453`](https://github.com/jlsaco/mad/commit/1c42453421d9a994adffc06d17a593acd0316f44))

- Rename specs/v0.1/ → specs/infra/ and update all references in CLAUDE.md, README.md, agents, and
  commands - Revise specs/claude-cli/ design, requirements, and plan - Add
  .claude/commands/commit.md as a standalone /commit slash command

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

### Features

- **claude-cli**: Implement ClaudeCLI provider with timeout and cancellation
  ([`96ecfe3`](https://github.com/jlsaco/mad/commit/96ecfe31dbe98482cfbfe8730aee6bbe2c687ecf))

- Spawns `claude --dangerously-skip-permissions -p {prompt}` in workspace (FR-1 through FR-8) -
  Streams stdout line-by-line as agent.output events; scrubs sk-ant-* tokens from stderr on error -
  Separates TimeoutError (returns after emitting session.error) from CancelledError (re-raises per
  design spec)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- **infra**: Realign codebase to infrastructure-only architecture
  ([`7471cb1`](https://github.com/jlsaco/mad/commit/7471cb13abebc182ad9d279944ad22ca3569a92c))

- Replace LLMProvider/ProviderResponse/ToolUse with AgentLauncher protocol - Implement
  ClaudeCLIProvider.run(): spawns claude --dangerously-skip-permissions, streams stdout as
  agent.output, handles timeout/error with token scrubbing - Replace FakeScriptedProvider with
  FakeLauncher for tests (scripted event sequences) - Replace run_agent_loop with _run_launcher in
  sessions route (background asyncio task) - Delete mad.agent.loop and mad.agent.tools (agent
  loop/tool execution removed from Mad) - Rewrite conftest, test_acceptance, test_security to use
  FakeLauncher - Add tests/unit/providers/test_claude_cli.py covering AC-1 through AC-5 - Update
  CLAUDE.md hard rules and AgentLauncher contract section

Covers FR-1 through FR-10 (specs/infra) and AC-1 through AC-5 (specs/claude-cli).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>


## v0.1.0 (2026-04-15)

### Build System

- **pypi**: Rename package to mad-bros
  ([`fbb828c`](https://github.com/jlsaco/mad/commit/fbb828cc0e8501fa846725bb1d2d430cecc479e4))

Update PyPI project name from 'mad' to 'mad-bros' across release workflows, documentation, and
  project configuration. Modify build command to ensure build dependency installation. This rename
  aligns with the new project identity.

BREAKING CHANGE: Package name change requires users to install 'mad-bros' instead of 'mad'

### Chores

- Add Makefile with common targets
  ([`73e33d5`](https://github.com/jlsaco/mad/commit/73e33d585ba36dd59e2997cc97a2184d6487570e))

Wraps the day-to-day commands (install, test, serve, clean) behind `make` so operators and future
  Claude runs have a single entry point. Targets honor HOST=/PORT= overrides for `make serve`.
  CLAUDE.md and README now point at the Makefile as the source of truth for commands.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

### Continuous Integration

- Implement automated release pipeline with semantic versioning
  ([`f8eb874`](https://github.com/jlsaco/mad/commit/f8eb87491f1fa80e98f9db9d0f56d31b09a30803))

Add GitHub Actions workflows for CI builds, artifact verification, and automated releases using
  python-semantic-release. Configure pyproject.toml for packaging, dependencies, and release
  settings. Include Makefile targets for building and dry-run releases. Add CHANGELOG.md for version
  tracking and docs/releasing.md for release process documentation. Update .gitignore to exclude
  venv directories.

### Documentation

- Add initial project documentation and v0.1 specs
  ([`ee74d08`](https://github.com/jlsaco/mad/commit/ee74d082c04d2aec421a0abcf4c64f77aa726426))

Introduce comprehensive documentation for the Mad project, including an overview in README.md,
  future improvements in docs/backlog.md, sandbox hardening guide in docs/sandbox-bwrap.md, and a
  complete spec-driven development package for v0.1 in specs/v0.1/ covering requirements, design,
  API contract, and implementation plan. This establishes the project's foundation and guides
  development towards the first functional version.

- **v0.1**: Mandate src/mad/ package layout
  ([`92d5d17`](https://github.com/jlsaco/mad/commit/92d5d17f8460ec7215d86305105bd7cc14c93d36))

- Rewrite CLAUDE.md hard rule #4 from "Single-file MVP" to a package layout split by concern (api,
  core, agent, providers) with create_app(store=...) and no module-level globals; update Key files,
  Commands, and LLMProvider sections accordingly. - Update specs/v0.1 requirements NFR-1, plan rule
  2, and the design diagram so the spec no longer contradicts the new convention. - Update the 4
  subagents and /implement command to point at src/mad/ instead of app.py and to enforce the layout
  in reviews. - Extend README with an Install section (pip install -e .) and a project structure
  tree.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

### Features

- Initialize project infrastructure for Mad v0.1
  ([`1494569`](https://github.com/jlsaco/mad/commit/1494569f02344b9b0a923446f765801e37f728ec))

Add core components including Claude agent definitions, slash commands, CI pipeline, FastAPI app
  skeleton, test fixtures, and security tests. Establish spec-driven development workflow with TDD
  support, enforcing hard rules for token hygiene, path traversal prevention, and native tool use.

BREAKING CHANGE: Introduces new project structure requiring spec-first development process.

- **api**: Implement session management and provider interfaces
  ([`b232a75`](https://github.com/jlsaco/mad/commit/b232a756af10e05e32bfd8e635380bdb3f6c2aff))

Introduce core session lifecycle handling including creation, logging, and SSE streaming. Add stub
  implementations for ClaudeCLIProvider and AnthropicAPIProvider. Expand acceptance tests to cover
  MVP criteria such as repo cloning, event handling, and session resumption. Enhance security tests
  with comprehensive path traversal validations and token hygiene checks.

BREAKING CHANGE: Updates session response structure to include workspace and resources_mounted
  details. Requires client adjustments for new fields.

### Refactoring

- **v0.1**: Migrate app.py into src/mad/ package
  ([`c652791`](https://github.com/jlsaco/mad/commit/c652791e55f4f333ecaeb597b483eebcb7f65bf8))

Split the monolithic app.py into a pip-installable src/mad/ package: - mad.api: FastAPI app factory
  (create_app) + routes/sessions.py. No module-level globals; per-process state lives on a
  SessionStore held in app.state.store so every create_app() call is isolated. - mad.core: log,
  security (path validation), workspace, resources, sessions (SessionStore). - mad.agent: loop and
  tools (run_agent_loop takes the store as a parameter). - mad.providers: base (Protocol +
  ProviderResponse + ToolUse), factory, claude_cli, anthropic_api, fake (FakeScriptedProvider moved
  out of conftest so tests and production share one implementation). - mad.cli: `mad serve` console
  entry-point.

pyproject.toml gains build-system (hatchling), [project] metadata and dependencies, a `mad` console
  script, and pytest pythonpath=["src"]. Tests now import from mad.* and TestClient wraps
  create_app().

All 35 tests green. No functional changes — this is a pure refactor; FR-7 recovery, FR-10 provider
  stubs, and the sse-starlette gap are carried over from the previous state as pre-existing debt.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

### Breaking Changes

- **api**: Updates session response structure to include workspace and resources_mounted details.
  Requires client adjustments for new fields.

- **pypi**: Package name change requires users to install 'mad-bros' instead of 'mad'
