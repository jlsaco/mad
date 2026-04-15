# CHANGELOG


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
