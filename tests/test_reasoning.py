"""Reasoning layer: the shared toolbox, the offline engine, and the Claude
tool-use loop (driven with a mocked SDK — no network)."""

import builtins
import sys
import types
from types import SimpleNamespace

from matchday_ops.config import Settings
from matchday_ops.models import Persona
from matchday_ops.reasoning import (
    ClaudeReasoningEngine,
    OfflineReasoningEngine,
    OpsToolbox,
)


# --- shared toolbox ---------------------------------------------------------


def test_toolbox_records_tools_and_citations():
    box = OpsToolbox(minute=48)
    out = box.run("find_hotspots", {})
    assert out["count"] >= 1
    assert "find_hotspots" in box.used_tools
    assert box.citations  # crowd readings are grounded


def test_toolbox_bad_tool_raises():
    import pytest

    from matchday_ops import knowledge

    with pytest.raises(knowledge.KnowledgeError):
        OpsToolbox(48).run("no_such_tool", {})


# --- offline engine ---------------------------------------------------------


def test_offline_staff_brief_is_grounded_and_cited():
    ans = OfflineReasoningEngine().answer(Persona.STAFF, "", minute=48, language="English")
    assert not ans.used_llm
    assert ans.persona == "staff"
    assert "Crowd hotspots" in ans.text
    assert "Egress readiness" in ans.text
    assert "Sources" in ans.text and "http" in ans.text
    assert ans.citations


def test_offline_persona_shapes_differ():
    staff = OfflineReasoningEngine().answer(Persona.STAFF, "", 48, "English").text
    volunteer = OfflineReasoningEngine().answer(Persona.VOLUNTEER, "", 48, "English").text
    fan = OfflineReasoningEngine().answer(Persona.FAN, "", 48, "English").text
    assert "Recommended actions" in staff
    assert "dispatch board" in volunteer.lower()
    assert "Key phrases" in fan


def test_offline_fan_serves_requested_language_phrases():
    ans = OfflineReasoningEngine().answer(Persona.FAN, "", 48, "Spanish")
    assert "Salida" in ans.text  # 'Exit' in Spanish


# --- Claude engine: mocked tool-use loop ------------------------------------


def _block(**kw):
    return SimpleNamespace(**kw)


class _FakeMessages:
    """Scripted: first call asks for a tool, second returns the final text."""

    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return SimpleNamespace(
                stop_reason="tool_use",
                content=[_block(type="tool_use", name="find_hotspots", input={}, id="tool_1")],
            )
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[_block(type="text", text="At the break, Lower Concourse East is critical — meter inflow.")],
        )


class _FakeClient:
    def __init__(self, *args, **kwargs):
        self.messages = _FakeMessages()


def _install_fake_anthropic(monkeypatch):
    fake = types.ModuleType("anthropic")
    fake.Anthropic = _FakeClient
    monkeypatch.setitem(sys.modules, "anthropic", fake)


def test_claude_engine_runs_tool_use_loop(monkeypatch):
    _install_fake_anthropic(monkeypatch)
    engine = ClaudeReasoningEngine(Settings(api_key="test-key", model="claude-opus-4-8"))
    ans = engine.answer(Persona.STAFF, "Where are we overcrowded?", minute=48, language="English")

    assert ans.used_llm
    assert "find_hotspots" in ans.tools_used     # the model's tool call was executed
    assert "Lower Concourse East" in ans.text     # final assistant text is returned
    assert ans.citations                          # the executed tool's sources attached
    assert ans.language == "English"


def test_claude_engine_falls_back_when_sdk_missing(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "anthropic":
            raise ImportError("simulated: SDK not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    engine = ClaudeReasoningEngine(Settings(api_key="test-key", model="claude-opus-4-8"))
    ans = engine.answer(Persona.FAN, "How do I get out?", minute=92, language="English")
    assert not ans.used_llm                       # fell back to grounded offline brief
    assert "Leaving the stadium" in ans.text
