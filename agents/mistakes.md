# Mistakes & reversals (post-mortem)

Kept honest and public — the reasoning that got cut matters as much as the code
that shipped.

## 1. Wrong end of the tournament (the big one)

**What we did first.** An earlier version was a **pre-trip visa & cross-border
travel** assistant for fans. It was well-built, but it missed the problem
statement on the highest-impact axis: the brief asks for GenAI that enhances
**stadium operations and the tournament experience *during* the World Cup**, for
**fans, organizers, volunteers, or venue staff** — navigation, crowd management,
accessibility, transportation, real-time decision support *at the event*.

**Why it was wrong.**
- It operated **before** the tournament (booking/planning), not during it.
- It served **fans only** — three of the five named personas (organizers,
  volunteers, venue staff) were entirely out of scope.
- "Stadium operations" had no surface at all — no venue, gates, crowds, or
  incidents.

**The fix.** Rebuilt around **in-stadium, match-time operations**: a live crowd
model driven by the match clock, tools for hotspots/routing/incidents/egress/
dispatch, and three personas (staff, volunteer, fan). Alignment is now direct,
not argued.

## 2. Offline engine duplicating tool logic

**What we did first (in the prior codebase).** The offline engine re-implemented
the tool-calling + citation-gathering sequence separately from the online tool
runner, and reached into a `_remember` internal from outside the class. Same
logic in two places → drift risk.

**The fix.** A single `OpsToolbox` exposes `specs()` and `run(name, input)` and
records citations. **Both** the Claude engine and the offline engine drive tools
only through `run(...)`. There is exactly one place a tool executes and its
sources are recorded.

## 3. The GenAI core was under-tested

**What we did first.** Tests covered the offline path thoroughly but only
exercised the LLM engine's *SDK-absent fallback* — the actual tool-use loop
(message threading, tool-result round-trips, final-text extraction) had no test.

**The fix.** `test_reasoning.py` mocks the Anthropic SDK with a scripted client
(tool_use turn → end_turn turn) and asserts the loop executes the tool, threads
the result, attaches the tool's citations, and returns the final answer.

## 4. Over-claiming "gets sharper with use"

**What we considered.** Carrying over a per-user memory layer and calling it
"the model gets sharper." It doesn't retrain anything, and it added scope the
problem statement never asked for.

**The fix.** Dropped it. The product is focused on the live match; less code,
fewer honesty caveats, cleaner alignment.
