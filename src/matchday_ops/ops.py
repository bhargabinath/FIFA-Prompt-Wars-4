"""Top-level orchestration: persona + question + live minute → grounded answer."""

from __future__ import annotations

from .config import Settings, load_settings
from .models import Answer, Persona
from .reasoning import ClaudeReasoningEngine, OfflineReasoningEngine, ReasoningEngine


class MatchDayOps:
    """The single entry point a front end talks to. Selects the Claude engine
    when a key is present, otherwise the deterministic offline engine."""

    def __init__(
        self,
        settings: Settings | None = None,
        engine: ReasoningEngine | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        if engine is not None:
            self._engine = engine
        elif self._settings.llm_enabled:
            self._engine = ClaudeReasoningEngine(self._settings)
        else:
            self._engine = OfflineReasoningEngine()

    def advise(
        self,
        persona: Persona,
        question: str = "",
        minute: int = 48,
        language: str = "English",
    ) -> Answer:
        return self._engine.answer(persona, question, minute, language)
