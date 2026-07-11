"""Command-line interface for MatchDay Ops.

Modes:
  * ``--demo``          a ready-made operations brief (staff, half-time)
  * ``--interactive``   guided, plain-language questions
  * one-shot flags      scriptable: pass persona + minute + question
  * ``--map``           show the stadium zones by level
  * ``--live``          scan crowd status across the whole match

Output is plain text with clear section labels (screen-reader friendly). The
answer is written in the asker's language when Claude is enabled.
"""

from __future__ import annotations

import argparse
import sys

from . import knowledge, telemetry
from .knowledge import KnowledgeError
from .models import Persona
from .ops import MatchDayOps


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="matchday",
        description="MatchDay Ops — real-time GenAI stadium operations & experience assistant for FIFA World Cup 2026.",
    )
    p.add_argument("--demo", action="store_true", help="Run a ready-made operations brief and exit.")
    p.add_argument("--interactive", "-i", action="store_true", help="Answer a few guided questions.")
    p.add_argument("--map", action="store_true", help="Show stadium zones by level and exit.")
    p.add_argument("--live", action="store_true", help="Scan crowd status across the match and exit.")

    p.add_argument("--persona", "-p", default="fan", help="Who is asking: staff, volunteer, or fan.")
    p.add_argument("--minute", "-m", type=int, default=48, help="Match minute (negative = pre-match, 90+ = egress).")
    p.add_argument("--language", "-l", default="English", help="Answer language (any language, e.g. Spanish).")
    p.add_argument("--question", "-q", default="", help="Your free-form question (any language).")
    return p


def _print_map() -> None:
    stadium = knowledge.stadium()
    print(f"{stadium['name']} — capacity {stadium['capacity']:,}\n")
    for level in stadium["levels"]:
        print(f"[{level.upper()}]")
        for key, z in knowledge.zones().items():
            if z["level"] == level:
                acc = " ♿" if z["accessible"] else ""
                print(f"  {key:<24} {z['name']} ({z['category']}){acc}")
        print()


def _print_live() -> None:
    print("Crowd status across the match (density% · status):\n")
    minutes = [-30, 15, 48, 75, 92]
    zones = knowledge.zone_keys()
    header = "zone".ljust(24) + "".join(f"m{m}".rjust(9) for m in minutes)
    print(header)
    print("-" * len(header))
    for zk in zones:
        row = zk.ljust(24)
        for m in minutes:
            r = telemetry.reading_for(zk, m)
            row += f"{r.density_pct:>3} {r.status[:4]:>5}"
        print(row)


def _prompt(question: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    return input(f"{question}{suffix}: ").strip() or default


def _interactive() -> tuple[Persona, str, int, str]:
    print("MatchDay Ops. Press Enter to accept a default in brackets.\n")
    persona = Persona.parse(_prompt("Who are you (staff / volunteer / fan)", "fan"))
    minute = int(_prompt("Match minute (negative = pre-match, 90+ = egress)", "48"))
    language = _prompt("Answer in which language", "English")
    question = _prompt("Your question (optional)", "")
    return persona, question, minute, language


def _demo() -> tuple[Persona, str, int, str]:
    return (
        Persona.STAFF,
        "Concourse looks packed at the break — where are we overcrowded, any incidents, "
        "and are we ready for full-time egress?",
        48,
        "English",
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.map:
        _print_map()
        return 0
    if args.live:
        _print_live()
        return 0

    try:
        if args.demo:
            persona, question, minute, language = _demo()
        elif args.interactive:
            persona, question, minute, language = _interactive()
        else:
            persona = Persona.parse(args.persona)
            question, minute, language = args.question, args.minute, args.language
    except (ValueError, KnowledgeError) as err:
        print(f"Sorry — {err}", file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.", file=sys.stderr)
        return 130

    answer = MatchDayOps().advise(persona, question, minute, language)

    mode = "Claude-powered" if answer.used_llm else "offline"
    _, phase_label = telemetry.match_phase(minute)
    print(f"\n[{mode} · {persona.label} · minute {minute} ({phase_label}) · {answer.language}]\n")
    print(answer.text)

    # In LLM mode, surface the grounded sources explicitly (offline text lists them already).
    if answer.used_llm and answer.unique_citations:
        print("\nSources\n-------")
        for c in answer.unique_citations:
            print(f"• {c.title}: {c.url}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
