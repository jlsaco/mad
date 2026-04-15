# Mad About

> That's mad!

**M**ulti **A**gent **D**evelop — a multi-agent system designed to build software autonomously. It takes an idea and drives it end-to-end: from the first line of code to a working product.

## What is this?

Mad About orchestrates a team of AI agents that collaborate to design, implement, test, and ship software without a human in the loop for every step. You give it a goal; it figures out the rest.

## Status

Early days. The first milestone is **Mad** — a self-hosted API that provisions workspaces, clones repos, and runs Claude agents autonomously against them. See [`specs/v0.1/`](specs/v0.1/README.md) for the full spec-driven package.

## Install

Mad ships as a pip-installable Python package (`mad`). From a checkout:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .            # editable install — uses pyproject.toml
pytest -q                   # run the test suite
mad serve                   # or: uvicorn mad.api.app:create_app --factory
```

## Project structure

```
mad/
├── pyproject.toml          # package metadata, deps, `mad` console script
├── src/mad/
│   ├── api/                # FastAPI app + routes (thin HTTP layer)
│   │   ├── app.py          # create_app(store=...) factory
│   │   └── routes/         # sessions, events, stream
│   ├── core/               # domain — session log, workspace, security, SessionStore
│   ├── agent/              # harness loop + tool execution
│   ├── providers/          # LLMProvider protocol + claude_cli / anthropic_api / fake
│   └── cli.py              # `mad` console entry-point
├── specs/v0.1/             # spec-driven package for the current milestone
└── tests/                  # pytest acceptance + security tests
```

Hard rules and conventions that govern every change live in [`CLAUDE.md`](CLAUDE.md).

## Documentation

- [`specs/v0.1/`](specs/v0.1/README.md) — spec-driven development package for v0.1 (requirements, design, API contract, implementation plan).
- [`docs/backlog.md`](docs/backlog.md) — known improvements deferred past v0.1.
- [`docs/sandbox-bwrap.md`](docs/sandbox-bwrap.md) — hardening guide for the execution sandbox using bubblewrap.

## License

See [`LICENSE`](LICENSE).
