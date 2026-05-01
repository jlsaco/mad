"""DEPRECATED shim — will be removed in Phase 6.

Use mad.adapters.inbound.http instead.
"""
from __future__ import annotations

from mad.adapters.inbound.http import create_app

__all__ = ["create_app"]
