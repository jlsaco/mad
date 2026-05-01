"""DEPRECATED shim — implementation moved to mad.adapters.inbound.http.app.

This module re-exports create_app for backwards compatibility until Phase 6.
Do not import this module in new code.
"""
from __future__ import annotations

from mad.adapters.inbound.http.app import create_app

__all__ = ["create_app"]
