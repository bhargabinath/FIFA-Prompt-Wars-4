"""The reasoning layer — where GenAI is the brain.

``ClaudeReasoningEngine`` runs an agentic tool-use loop: Claude reads the live
match state and a free-form question (in any language, from staff / volunteer /
fan), decides which grounded tools to call, and writes a cited answer in the
asker's language. It never states a crowd number, route, incident, or egress
fact from its own memory — those come from the tools.

``OfflineReasoningEngine`` is a deterministic fallback that calls the *same*
tools through the *same* :class:`OpsToolbox` to assemble a persona-specific
briefing, so the product still works (and stays testable) with no API key or
network. Crucially, both engines share one toolbox: there is a single place
where a tool is run and its citations are recorded — no logic is duplicated.
"""

from __future__ import annotations

import json
from typing import Protocol

from . import knowledge, telemetry, tools
from .config import Settings
from .models import Answer, Citation, Persona

_MAX_TURNS = 8


class OpsToolbox:
    """Binds the grounded tools to one live snapshot (match minute) and records
    every source touched, so citations attach to the final answer regardless of
    how the model (or the offline engine) phrases things. Both engines drive the
    tools exclusively through :meth:`run`."""

    def __init__(self, minute: int) -> None:
        self.minute = minute
        self.used_tools: list[str] = []
        self._citations: dict[str, Citation] = {}

    @property
    def citations(self) -> list[Citation]:
        return list(self._citations.values())

    def _remember(self, *citations: Citation) -> None:
        for c in citations:
            self._citations.setdefault(c.source_id, c)

    def specs(self) -> list[dict]:
        zone_enum = knowledge.zone_keys()
        transit_enum = list(knowledge.transit())
        return [
            {
                "name": "get_crowd_status",
                "description": "Live crowd density, queue wait, and status (calm/busy/crowded/critical) for every zone right now.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "find_hotspots",
                "description": "Just the zones that are crowded or critical right now, worst first. Use for crowd-management decisions.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "plan_route",
                "description": "Step-by-step walking route between two zones, with live congestion overlaid. Set accessible=true for a guaranteed step-free route (avoids stairs).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "origin": {"type": "string", "enum": zone_enum},
                        "destination": {"type": "string", "enum": zone_enum},
                        "accessible": {"type": "boolean"},
                    },
                    "required": ["origin", "destination"],
                },
            },
            {
                "name": "incident_brief",
                "description": "Active incidents right now (scheduled + live crowd-driven), each with its response protocol.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "egress_plan",
                "description": "Least-congested exit gate and best outbound transit for leaving now. Set accessible=true for step-free options.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "accessible": {"type": "boolean"},
                        "transit_preference": {"type": "string", "enum": transit_enum},
                    },
                },
            },
            {
                "name": "dispatch_board",
                "description": "Prioritised steward/volunteer deployment suggestions derived from live hotspots and incidents.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "key_phrases",
                "description": "Essential wayfinding/safety phrases (exit, first aid, accessible route, help, water, gate) in a requested language.",
                "input_schema": {
                    "type": "object",
                    "properties": {"language": {"type": "string"}},
                    "required": ["language"],
                },
            },
        ]

    def run(self, name: str, tool_input: dict) -> dict:
        self.used_tools.append(name)

        if name == "get_crowd_status":
            readings = tools.crowd_status(self.minute)
            for r in readings:
                self._remember(*r.citations)
            return {"zones": [r.to_dict() for r in readings]}

        if name == "find_hotspots":
            readings = tools.hotspots(self.minute)
            for r in readings:
                self._remember(*r.citations)
            return {"hotspots": [r.to_dict() for r in readings], "count": len(readings)}

        if name == "plan_route":
            route = tools.plan_route_at(
                tool_input["origin"],
                tool_input["destination"],
                self.minute,
                bool(tool_input.get("accessible", False)),
            )
            self._remember(*route.citations)
            return route.to_dict()

        if name == "incident_brief":
            incidents = tools.incident_brief(self.minute)
            for inc in incidents:
                self._remember(*inc.citations)
            return {"incidents": [i.to_dict() for i in incidents], "count": len(incidents)}

        if name == "egress_plan":
            plan = tools.egress_plan(
                self.minute,
                bool(tool_input.get("accessible", False)),
                tool_input.get("transit_preference"),
            )
            self._remember(*plan.citations)
            return plan.to_dict()

        if name == "dispatch_board":
            board = tools.dispatch_board(self.minute)
            self._remember(knowledge.citation("green_guide"))
            return {"dispatch": [d.to_dict() for d in board], "count": len(board)}

        if name == "key_phrases":
            result = tools.key_phrases(tool_input["language"])
            self._remember(knowledge.citation("venue_ops_manual"))
            return result

        raise knowledge.KnowledgeError(f"Unknown tool '{name}'.")


class ReasoningEngine(Protocol):
    def answer(self, persona: Persona, question: str, minute: int, language: str) -> Answer: ...


# --- Offline (deterministic) ------------------------------------------------


class OfflineReasoningEngine:
    """Assembles a persona-specific briefing from the tools without an LLM.
    Writes in English (it cannot translate arbitrary prose) and says so, but
    still serves multilingual key phrases via the ``key_phrases`` tool."""

    def answer(self, persona: Persona, question: str, minute: int, language: str) -> Answer:
        box = OpsToolbox(minute)
        phase_key, phase_label = telemetry.match_phase(minute)
        stadium = knowledge.stadium()

        lines: list[str] = [
            f"MatchDay Ops — {persona.label} briefing",
            "=" * 40,
            f"{stadium['name']} · minute {minute} · {phase_label}",
            "",
        ]
        if question.strip():
            lines += [f'Your question: "{question.strip()}"', ""]

        if persona is Persona.STAFF:
            self._staff(box, lines)
        elif persona is Persona.VOLUNTEER:
            self._volunteer(box, lines)
        else:
            self._fan(box, lines, language)

        cites = box.citations
        if cites:
            lines += ["", "Sources", "-" * 7]
            lines += [f"• {c.title}: {c.url}" for c in cites]
        lines += [
            "",
            "(Offline briefing in English. Set ANTHROPIC_API_KEY for a conversational",
            " answer to your exact question, in any language.)",
        ]

        return Answer(
            text="\n".join(lines),
            persona=persona.value,
            language="English",
            citations=tuple(cites),
            tools_used=tuple(box.used_tools),
            used_llm=False,
        )

    # Each helper drives tools *through the shared toolbox* — same path the LLM
    # uses — and reads the returned dicts. No tool logic is re-implemented here.

    def _staff(self, box: OpsToolbox, lines: list[str]) -> None:
        hotspots = box.run("find_hotspots", {})["hotspots"]
        lines += ["Crowd hotspots", "-" * 14]
        if not hotspots:
            lines.append("• All zones calm/busy — no crowded or critical areas.")
        for h in hotspots:
            lines.append(
                f"• {h['zone_name']}: {h['status'].upper()} "
                f"({h['density_pct']}% full, ~{h['wait_minutes']} min wait)"
            )
        lines.append("")

        incidents = box.run("incident_brief", {})["incidents"]
        lines += ["Active incidents", "-" * 16]
        lines += ([f"• [{i['severity'].upper()}] {i['zone_name']}: {i['summary']}" for i in incidents]
                  or ["• None active."])
        lines.append("")

        egress = box.run("egress_plan", {"accessible": False})
        lines += ["Egress readiness", "-" * 16, f"• {egress['rationale']}", ""]

        board = box.run("dispatch_board", {})["dispatch"]
        lines += ["Recommended actions", "-" * 19]
        lines += ([f"• [{d['priority'].upper()}] {d['zone_name']}: {d['action']}" for d in board]
                  or ["• No deployments needed right now."])

    def _volunteer(self, box: OpsToolbox, lines: list[str]) -> None:
        board = box.run("dispatch_board", {})["dispatch"]
        lines += ["Your dispatch board (act on HIGH first)", "-" * 39]
        if not board:
            lines.append("• Nothing urgent — assist fans with wayfinding and accessibility.")
        for d in board:
            lines.append(f"• [{d['priority'].upper()}] {d['zone_name']}: {d['action']}")
            lines.append(f"    Why: {d['reason']}")
        lines.append("")

        incidents = box.run("incident_brief", {})["incidents"]
        lines += ["Active incidents", "-" * 16]
        lines += ([f"• [{i['severity'].upper()}] {i['zone_name']}: {i['summary']} — {i['protocol']}"
                   for i in incidents] or ["• None active."])

    def _fan(self, box: OpsToolbox, lines: list[str], language: str) -> None:
        zones = box.run("get_crowd_status", {})["zones"]
        busy = sorted(
            (z for z in zones if z["status"] in ("crowded", "critical")),
            key=lambda z: z["density_pct"], reverse=True,
        )[:4]
        calm_concourses = [z for z in zones if z["category"] == "concourse" and z["status"] in ("calm", "busy")]
        lines += ["How busy it is right now", "-" * 24]
        if busy:
            lines.append("Avoid if you can:")
            lines += [f"  • {z['zone_name']} ({z['status']}, ~{z['wait_minutes']} min)" for z in busy]
        if calm_concourses:
            lines.append("Quieter concourses: " + ", ".join(z["zone_name"] for z in calm_concourses))
        lines.append("")

        egress = box.run("egress_plan", {"accessible": False})
        lines += ["Leaving the stadium", "-" * 19, f"• {egress['rationale']}",
                  "• Need step-free? Ask for the accessible egress plan (Gate C, elevator core).", ""]

        lines += ["Accessibility", "-" * 13,
                  "• Accessibility Services (North Plaza): wheelchair loan, sensory kits, assistance.",
                  "• Step-free routes to every level exist via the elevator and ramp cores.", ""]

        phrases = box.run("key_phrases", {"language": language})
        lines += [f"Key phrases ({phrases['language']})", "-" * 20]
        lines += [f"  {k.replace('_', ' ').title()}: {v}" for k, v in phrases["phrases"].items()]
        if phrases["fallback_to_english"]:
            lines.append("  (Requested language not in the offline set — showing English.)")


# --- Claude (GenAI core) ----------------------------------------------------


class ClaudeReasoningEngine:
    """Runs the agentic tool-use loop. Falls back to the offline engine on any
    SDK/network/API failure so the asker always gets a useful answer."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._offline = OfflineReasoningEngine()

    def answer(self, persona: Persona, question: str, minute: int, language: str) -> Answer:
        try:
            import anthropic
        except ImportError:
            return self._offline.answer(persona, question, minute, language)

        box = OpsToolbox(minute)
        try:
            client = anthropic.Anthropic(api_key=self._settings.api_key)
            messages = [{"role": "user", "content": _user_prompt(persona, question, minute, language)}]
            specs = box.specs()
            final = None

            for _ in range(_MAX_TURNS):
                resp = client.messages.create(
                    model=self._settings.model,
                    max_tokens=2048,  # operational briefs are deliberately short
                    thinking={"type": "adaptive"},
                    system=_system_prompt(persona, minute, language),
                    tools=specs,
                    messages=messages,
                )
                if resp.stop_reason == "tool_use":
                    messages.append({"role": "assistant", "content": resp.content})
                    results = []
                    for block in resp.content:
                        if block.type == "tool_use":
                            try:
                                out = box.run(block.name, dict(block.input))
                                results.append({
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": json.dumps(out),
                                })
                            except Exception as exc:  # a bad tool call shouldn't kill the turn
                                results.append({
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": f"error: {exc}",
                                    "is_error": True,
                                })
                    messages.append({"role": "user", "content": results})
                    continue
                final = resp
                break

            if final is None:
                return self._offline.answer(persona, question, minute, language)
            text = "".join(b.text for b in final.content if b.type == "text").strip()
            if not text:
                return self._offline.answer(persona, question, minute, language)

            return Answer(
                text=text,
                persona=persona.value,
                language=language,
                citations=tuple(box.citations),
                tools_used=tuple(box.used_tools),
                used_llm=True,
            )
        except Exception:
            return self._offline.answer(persona, question, minute, language)


def _system_prompt(persona: Persona, minute: int, language: str) -> str:
    phase_key, phase_label = telemetry.match_phase(minute)
    stadium = knowledge.stadium()
    persona_rules = {
        Persona.STAFF: "You advise venue operations. Lead with the decision: what to do, where, and why. Be crisp and prioritised.",
        Persona.VOLUNTEER: "You brief a volunteer/steward. Give a short, ordered task list; put safety and accessibility first.",
        Persona.FAN: "You help a spectator. Be warm, plain, and practical — wayfinding, waits, accessibility, and how to get home.",
    }[persona]
    return (
        f"You are MatchDay Ops, a real-time assistant during a FIFA World Cup 2026 match at "
        f"{stadium['name']}. It is match minute {minute} ({phase_label}). You are helping: {persona.label}.\n\n"
        f"{persona_rules}\n\n"
        "Non-negotiable rules:\n"
        f"1. Write your ENTIRE answer in {language}.\n"
        "2. NEVER state a crowd number, queue wait, route, incident, or egress fact from your own "
        "memory. Call the provided tools and base every operational claim on their results.\n"
        "3. You support human decision-makers — you do not command emergency services. For any "
        f"life-safety emergency, direct people to the {stadium['control_room']} / {stadium['emergency_line']}.\n"
        "4. For accessibility requests, use step-free routing (accessible=true) and name accessible facilities.\n"
        "5. Be clear and structured. End with the sources the tools returned."
    )


def _user_prompt(persona: Persona, question: str, minute: int, language: str) -> str:
    q = question.strip() or {
        Persona.STAFF: "Give me an operations brief for right now: hotspots, incidents, and egress readiness.",
        Persona.VOLUNTEER: "Where should I go right now and what should I do?",
        Persona.FAN: "How busy is it, and what's the easiest way out at full time?",
    }[persona]
    return (
        f"Persona: {persona.label}\n"
        f"Match minute: {minute}\n"
        f"Preferred language: {language}\n\n"
        f"Question: {q}"
    )
