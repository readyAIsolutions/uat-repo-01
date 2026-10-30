"""Module 10 — small env helpers (additive; does not touch MVP settings).

``env_flag`` follows the repo convention that empty strings mean 'unset'
(see config.py blank_is_unset) so a blank .env entry degrades to None.
"""
from __future__ import annotations

import os


def env_flag(name: str) -> str | None:
    value = os.environ.get(name, "")
    return None if value == "" else value


def env_float(name: str, default: float) -> float:
    value = env_flag(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def env_int(name: str, default: int) -> int:
    value = env_flag(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default
