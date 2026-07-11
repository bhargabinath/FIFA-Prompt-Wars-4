"""Runtime configuration, sourced from the environment only.

No secret is hardcoded or logged. Without ``ANTHROPIC_API_KEY`` the assistant
runs its deterministic offline engine (see :mod:`matchday_ops.reasoning`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_MODEL = "claude-opus-4-8"


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    model: str

    @property
    def llm_enabled(self) -> bool:
        return bool(self.api_key)


def load_settings() -> Settings:
    return Settings(
        api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        model=os.environ.get("MATCHDAY_MODEL", DEFAULT_MODEL),
    )
