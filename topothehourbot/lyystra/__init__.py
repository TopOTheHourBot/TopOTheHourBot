from __future__ import annotations

__all__ = ["suites"]

from collections.abc import Iterator

from ..api.client import SupportsClientCallback
from . import common


def suites() -> Iterator[SupportsClientCallback]:
    yield common
