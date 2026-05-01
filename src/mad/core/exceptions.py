"""DEPRECATED shim — will be removed in Phase 6.

Re-exports DomainError and PathTraversalError from the canonical location
in mad.core.domain.exceptions so existing imports continue to work.
"""
from __future__ import annotations

from mad.core.domain.exceptions.base import DomainError, PathTraversalError, SessionNotFound

__all__ = ["DomainError", "PathTraversalError", "SessionNotFound"]
