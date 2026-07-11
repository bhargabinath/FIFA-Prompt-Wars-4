# Requirements

## Problem statement (verbatim)

> Build a GenAI-enabled solution that enhances **stadium operations and the
> overall tournament experience** for fans, organizers, volunteers, or venue
> staff. The solution must leverage Generative AI to improve navigation, crowd
> management, accessibility, transportation, sustainability, multilingual
> assistance, operational intelligence, or real-time decision support **during
> the FIFA World Cup 2026.**

## What we build

MatchDay Ops — an **in-stadium, match-time** assistant. Given the current match
minute, a persona (staff / volunteer / fan), and a free-form question in any
language, it returns a grounded, cited answer.

## Alignment (High-impact criterion — met head-on)

| Focus area in the brief | How MatchDay Ops addresses it |
| --- | --- |
| Crowd management | Live hotspots + prioritised steward dispatch board. |
| Operational intelligence | Persona-framed brief over the whole live snapshot. |
| Navigation | Step-by-step walking routes with live congestion. |
| Accessibility | First-class **step-free** routing; accessible gates/facilities. |
| Transportation | Egress plan: least-congested exit + best outbound transit. |
| Multilingual assistance | Any language via Claude; offline six-language phrasebook. |
| Real-time decision support | Everything is anchored to the current match minute. |

Personas served: **venue staff, volunteers, and fans** (organizers are covered
by the staff/ops view).

## Non-goals

- No command over emergency services — this is decision *support*.
- No ticketing, payments, or pre-trip/visa planning (out of scope, and the
  wrong end of the tournament).
- The crowd feed is a deterministic simulation, not real sensor data (see
  `data-points.md`).

## Quality bar (other scored criteria)

- **Code quality:** layered, typed, documented; one shared toolbox for both
  engines (no duplicated tool logic).
- **Security:** env-only secrets, validated inputs, closed enums, no `eval`/shell.
- **Efficiency:** cached data, pure crowd model, small-graph Dijkstra, bounded loop.
- **Testing:** every layer, including the LLM tool-use loop via a mocked SDK.
- **Accessibility:** step-free routing, multilingual output, screen-reader-
  friendly CLI, theme/keyboard/reduced-motion-safe web console.
