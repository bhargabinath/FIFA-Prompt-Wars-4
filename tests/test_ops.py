"""The orchestrator selects the right engine and routes by persona."""

from matchday_ops.config import Settings
from matchday_ops.models import Answer, Persona
from matchday_ops.ops import MatchDayOps


def test_no_key_uses_offline_engine():
    ops = MatchDayOps(settings=Settings(api_key=None, model="claude-opus-4-8"))
    ans = ops.advise(Persona.STAFF, "", minute=48)
    assert isinstance(ans, Answer)
    assert not ans.used_llm


def test_injected_engine_is_used():
    class StubEngine:
        def answer(self, persona, question, minute, language):
            return Answer(text="stub", persona=persona.value, language=language, used_llm=True)

    ops = MatchDayOps(engine=StubEngine())
    ans = ops.advise(Persona.FAN, "hi", 10, "French")
    assert ans.text == "stub"
    assert ans.persona == "fan"
    assert ans.language == "French"


def test_persona_parse_aliases():
    assert Persona.parse("ops") is Persona.STAFF
    assert Persona.parse("spectator") is Persona.FAN
    assert Persona.parse("Steward") is Persona.VOLUNTEER
