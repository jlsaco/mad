"""Unit tests for workspace base-directory resolution (#64).

``workspace_path`` anchors every session workspace. The base it resolves to
follows a 3-tier order — ``MAD_WORKSPACE_DIR`` (verbatim) → ``~/mad`` → the
system temp dir — and a wrong branch would silently send clones to the wrong
disk (the failure mode #64 was filed to fix). Each tier is pinned here along
with its negative twin (set-but-blank, set-but-not-expanded), so a regression
in the precedence cannot pass unnoticed.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mad.adapters.outbound.persistence.local_workspace_provisioner import (
    workspace_path,
)


def test_uses_mad_workspace_dir_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAD_WORKSPACE_DIR", "/data/mad-workspaces")

    assert workspace_path("sesn_abc") == Path("/data/mad-workspaces/mad_sesn_abc")


def test_mad_workspace_dir_value_is_used_verbatim_without_expansion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Negative twin of the happy path: the operator value is taken literally —
    # no ``~`` / ``$VAR`` expansion. A leading ``~`` must survive as a literal
    # path segment, never resolve to the home directory.
    monkeypatch.setenv("MAD_WORKSPACE_DIR", "~/somewhere")

    assert workspace_path("sesn_abc") == Path("~/somewhere") / "mad_sesn_abc"


def test_falls_back_to_home_mad_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAD_WORKSPACE_DIR", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/op")))

    assert workspace_path("sesn_abc") == Path("/home/op/mad/mad_sesn_abc")


def test_blank_mad_workspace_dir_is_treated_as_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Negative twin: a whitespace-only value must NOT win — it falls through to
    # the ``~/mad`` default exactly as an unset variable would.
    monkeypatch.setenv("MAD_WORKSPACE_DIR", "   ")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/op")))

    assert workspace_path("sesn_abc") == Path("/home/op/mad/mad_sesn_abc")


def test_falls_back_to_tempdir_when_home_unresolvable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Last resort: when the home directory cannot be resolved ``Path.home()``
    # raises ``RuntimeError`` and resolution must drop to the system temp dir.
    monkeypatch.delenv("MAD_WORKSPACE_DIR", raising=False)

    def _no_home(cls: type[Path]) -> Path:
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(Path, "home", classmethod(_no_home))

    assert workspace_path("sesn_abc") == Path(tempfile.gettempdir()) / "mad_sesn_abc"
