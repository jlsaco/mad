---
service: mad
domain: backend
section: operations
source_of_truth: repo
---

# CI/CD

Mad's automation lives in six GitHub Actions workflows under `.github/workflows/`.
This page documents each one as a **gate**: what triggers it, what jobs run in
order, and — the part that matters — **what each stage actually enforces**. The
job/step skeleton in this file is regenerated from the workflow YAML by the docs
generator; the narrative of what each stage gates is authored here and traced to
the workflow files, `pyproject.toml`, ADR-0002, and CLAUDE.md hard rule 12.

Two checks gate every PR (`ci`, `docs-validate`), one publishes a per-PR preview
artifact (`testpypi-preview`), two run only after merge to `main` (`release`,
`docs-sync`), and one is event-driven on labeled issues (`ai-develop-on-issue`).

## `ci.yml` — the merge gate

**Trigger:** `push` to `main` and `pull_request` against `main`.

Four jobs run; `build` waits on `quality` and `test`, the rest run in parallel.

### Job `quality` — lint, types, architecture

1. Checkout + `setup-python` 3.11 (pip cache).
2. `pip install -e '.[dev]'`.
3. **ruff** — `ruff check .` then `ruff format --check .`. Gates style and the
   lint rule set declared in `[tool.ruff.lint]`: pycodestyle/pyflakes (`E`/`F`/`W`),
   isort (`I`), pyupgrade (`UP`), bugbear (`B`), simplifications (`SIM`),
   ruff-specific (`RUF`), asyncio bug patterns (`ASYNC`), and the bandit security
   subset (`S`) — `S` matters because Mad spawns subprocesses.
4. **mypy** — `mypy` with `[tool.mypy]` `strict = true` scoped to `files =
   ["src/mad/core"]`. The framework-free domain is type-checked under full strict;
   adapters and HTTP are deliberately excluded (they wrap dynamic framework
   surfaces; strict there hides domain bugs in noise) and lean on tests +
   import-linter instead.
5. **import-linter** — `lint-imports` runs the single forbidden-import contract in
   `[tool.importlinter]`: `mad.core` may not import `fastapi`, `mad.adapters`,
   `mad.api`, `mad.providers`, `subprocess`, `shutil`, `httpx`, or `boto3`. This is
   the executable form of CLAUDE.md hard rule 4 (the hexagonal boundary).
6. **pre-commit** — `pre-commit run --all-files` runs the full hook battery
   (hygiene hooks, ruff check + format, mypy, and **gitleaks**). gitleaks
   reinforces hard rule 2 by blocking accidentally committed secrets.

### Job `test` — behavior and coverage

Runs on a matrix of Python 3.11 and 3.12.

1. Checkout + `setup-python` (matrix version, pip cache) + `pip install -e '.[dev]'`.
2. Configure a git identity — the clone-based tests need `user.email`/`user.name`.
3. **Unit + core coverage** — `pytest -q tests/unit --cov=mad.core
   --cov-fail-under=94`. The unit suite must hold at least 94% line coverage on
   the framework-free domain.
4. **Full suite + tree coverage** — `pytest -q --cov=mad --cov-fail-under=90`. The
   whole suite must hold at least 90% coverage across the package.

   Note: these are the **live CI thresholds** (94 core / 90 full). A comment
   elsewhere in the repo quotes an older 95/92 pair — the workflow values above
   are authoritative.

### Job `audit` — supply chain

Checkout + `setup-python` 3.11 + install, then `pip-audit --strict --skip-editable .`
scans declared dependencies against the PyPA Advisory Database. `--strict` fails
the job on any advisory; `--skip-editable` skips the editable Mad checkout itself.

### Job `build` — packaging (gated on `quality` + `test`)

Only runs once quality and tests are green. Installs `build` + `twine`, runs
`python -m build` to produce the sdist + wheel, then `twine check dist/*` to
validate the artifacts' metadata. This catches packaging regressions before they
can reach a release — the same class of bug that motivated `testpypi-preview`.

The four-job split (rationale in ADR-0002) keeps PR feedback fast and makes it
obvious which gate broke: lint, types, behavior, supply chain, and packaging have
genuinely different failure modes.

## `testpypi-preview.yml` — published-artifact round-trip per PR

**Trigger:** `pull_request` against `main`, plus manual `workflow_dispatch`.

Why this exists: a packaging bug (issue #50) only manifested in the **built**
sdist/wheel — `pip install -e .` or `git+https://…@branch` rebuilds from the
source tree and silently masks it. The only faithful check is
build → publish → install-from-index → import. This workflow is that check.

### Job `build`

Skipped for fork PRs (Trusted Publishing OIDC is never minted for forks, and
publish rights must never be handed to fork-authored code). For same-repo
branches it derives a unique PEP 440 dev version `<base>.dev<run_id>` (run_id is
globally unique and monotonic, so re-runs and concurrent PRs never collide on
TestPyPI's immutable version namespace — the edit is ephemeral, never committed),
builds the sdist + wheel, `twine check`s them, and uploads the artifact.

### Job `publish`

Gated on the operator opt-in `vars.TESTPYPI_ENABLED == 'true'` (so PRs stay green
before the TestPyPI Trusted Publisher is configured) and runs in the `testpypi`
environment with `id-token: write`. Publishes the built dist to TestPyPI via
OIDC Trusted Publishing.

### Job `verify`

Resolves the exact wheel URL from TestPyPI's JSON API (retrying because indexing
lags upload), installs **that wheel** into a clean venv while letting every
dependency resolve from real PyPI (pointing `--index-url` wholesale at TestPyPI
is unsafe — it hosts squats that shadow real deps), and runs the exact import
chain #50 broke: `from mad.core.sessions import SessionStore`, `create_app()`.
Finally it upserts a single PR comment with install instructions.

## `release.yml` — version, tag, publish (post-merge)

**Trigger:** `push` to `main`, **path-gated** to `src/mad/**`, `pyproject.toml`,
`README.md`, `LICENSE` — bytes that never reach a PyPI consumer (skills, docs,
tests, CI workflows, the Makefile, CLAUDE.md) must not move the version (hard
rule 12). Also `workflow_dispatch` with two inputs: `manual_publish` (boolean
escape hatch) and `release_kind` (`auto` | `minor` | `major`).

### Job `manual-publish-pypi`

Only when `workflow_dispatch` + `manual_publish == true`. Builds the current tree
and publishes straight to PyPI (Trusted Publishing, `pypi` environment),
bypassing semantic-release entirely — the operator's escape hatch.

### Job `release`

Runs on every version-relevant `push`, and on `workflow_dispatch` when
`manual_publish` was not chosen. Checks out full history, installs deps, runs
`pytest -q` as a final gate, then runs **python-semantic-release** v9. The action
parses Conventional Commits per `[tool.semantic_release]` and decides whether to
cut a release; if so it bumps `pyproject.toml:project.version` +
`src/mad/__init__.py:__version__`, builds, tags `v{version}`, writes the
changelog, and uploads the `dist/` artifact. `release_kind` maps to the action's
`force` input — on `push` (where the input doesn't exist) it evaluates to empty,
so behavior stays `auto`.

### Job `publish-pypi`

Runs only if `release` set `released == 'true'`. Downloads the `dist` artifact and
publishes to PyPI via OIDC Trusted Publishing in the `pypi` environment
(`id-token: write`, no long-lived token). A `publish-testpypi` job is present but
commented out.

## Versioning policy (CLAUDE.md hard rule 12)

The release pipeline enforces "versioning is for the package, not the repo" in
three coordinated places:

- **`pyproject.toml` demotes `feat` to a patch.** `[tool.semantic_release.commit_parser_options]`
  sets `minor_tags = []` and `patch_tags = ["feat", "fix", "perf"]`, with
  `major_on_zero = false`. So on `0.x`, ordinary `feat`/`fix`/`perf` commits
  auto-publish a **patch** — a minor or major bump is never derived from counting
  `feat`s. `allowed_tags` still parses `refactor`/`chore`/`docs`/`style`/`test`/
  `build`/`ci` (they bump versions per Conventional Commits but are filtered from
  the changelog by `exclude_commit_patterns`).
- **`release.yml` path-gates the trigger** so only changes under `src/mad/**`,
  `pyproject.toml`, `README.md`, or `LICENSE` can move the version.
- **`release_kind` dispatch input** lets an operator pick `minor` or `major`
  deliberately; otherwise minor/major requires a `BREAKING CHANGE:` footer or a
  `feat!:` / `fix!:` `!` marker.

Only the closed public scope set `{http, sse, cli, config, agents, deps}` is
eligible for `feat`/`fix`/`perf` (and thus the consumer-facing CHANGELOG).
Internal contexts (`core`, `events`, `sessions`, `domain`, `ports`) ship as
`refactor`/`chore`/`test` and are excluded from release notes by the
`exclude_commit_patterns` in `[tool.semantic_release.changelog]`.

## `docs-validate.yml` — docs lint gate (per PR)

**Trigger:** `pull_request` against `main`.

A thin caller that delegates to the reusable workflow
`mad-core/.github/.github/workflows/docs-validate.reusable.yml@main`, passing
`service_slug: mad`. It is a **lint-only** gate: docs are **not** generated in CI
(you regenerate `/docs` locally with the living-docs skill/commands). The
reusable installs only the `gen_docs` tooling and validates the `/docs` tree
against the manifest contract, blocking the PR on **both errors and warnings**.
The `api` section must be heuristic for the gate to pass; re-acknowledge the
manifest after source changes.

## `docs-sync.yml` — mirror /docs to mad-docs (post-merge)

**Trigger:** `push` to `main`.

Another thin caller, delegating to
`mad-core/.github/.github/workflows/docs-sync.reusable.yml@main` with
`service_slug: mad`. After a merge to `main`, it mirrors this repo's `/docs` tree
verbatim into the central `mad-core/mad-docs` repo under `raw/mad/` via a
correlated PR. It needs `DOCS_SYNC_TOKEN` (cross-repo PR) and `ANTHROPIC_API_KEY`
secrets, and `pull-requests: write`.

## `ai-develop-on-issue.yml` — allowlist-gated autonomous development

**Trigger:** `issues` `labeled` / `opened`. Concurrency is keyed per issue
(`cancel-in-progress: true`), so re-applying the label cancels any in-flight run.

### Job `gate` (author + label)

A cheap label gate runs first (`if: contains(... 'ai:auto-develop')`); without the
label the whole job — and the dependent `develop` job — is skipped. The step then
checks the issue author against the `AI_DEVELOP_ALLOWLIST` repository variable
(whole-token match), setting `eligible`. **Both** gates must pass, so arbitrary
contributors and unlabeled issues never trigger automated execution. It also
resolves the `/work`-convention branch name `<type>/<issue-number>-<slug>` from
the `type:` label and a slugified title.

### Job `develop`

Runs only when `gate` reports `eligible == 'true'`. Checks out full history,
configures a bot git identity, reuses-or-creates the issue branch, then runs
`anthropics/claude-code-action@v1` with `--dangerously-skip-permissions`. The
agent owns the full git flow (commit, push, open a non-draft PR with
`Closes #N`) inside the action while checkout-provided auth is live. The
`CLAUDE_CODE_OAUTH_TOKEN` is referenced only as a secret expression and never
echoed or written to the workspace (hard rule 2).
