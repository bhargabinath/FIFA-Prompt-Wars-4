# 🏟️ MatchDay Ops

**A GenAI real-time stadium operations & experience assistant for the FIFA World Cup 2026.**

During a World Cup match, three groups need answers *now* — **venue staff**
making crowd-management calls, **volunteers** deciding where to go, and **fans**
finding their way, avoiding queues, and getting home. MatchDay Ops answers all
three, in their own language, grounded in the live state of the stadium.

Ask, at any minute of the match:

> **Staff:** *"Concourse looks packed at the break — where are we overcrowded, any incidents, and are we ready for full-time egress?"*
> **Fan (in Spanish):** *"¿Cuál es la salida más tranquila y la ruta sin escaleras a la sección 320?"*

Claude **reasons about the current match state**, calls grounded tools for the
facts (crowd density, queues, routes, incidents, egress), and returns a clear,
**cited** answer — the right one for who's asking.

---

## For evaluators (read me first)

**No API key is required to evaluate this project.** The GenAI value is visible
from the source and docs, and the whole thing runs offline:

- **GenAI is the reasoning core, not a wrapper.** [`reasoning.py`](src/matchday_ops/reasoning.py)
  runs a real Anthropic **tool-use agent loop** (`claude-opus-4-8`, adaptive
  thinking): Claude reads a free-form question in **any language**, decides which
  grounded tools to call over the **live match snapshot**, and writes a cited,
  persona-specific answer. See a representative output in
  [`docs/example-genai-answer.md`](docs/example-genai-answer.md).
- **The offline engine is a resilience fallback, not the product.** With no key,
  the app degrades gracefully to a deterministic version of the *same grounded
  tools*, driven through the *same shared toolbox* — so it always runs and every
  layer is testable without a network.
- **Everything runs with zero setup:** `pip install -e ".[dev]" && pytest`
  (34 tests), `python -m matchday_ops --demo`, or just open
  [`web/index.html`](web/index.html).

| Criterion (impact) | Where it shows up |
| --- | --- |
| **Problem-statement alignment · High** | In-stadium and **during the match** (crowd/incidents/egress driven by a match clock); serves **staff, volunteers, and fans**; targets crowd management, navigation, accessibility, transportation, multilingual assistance, operational intelligence & real-time decision support — the problem statement's own focus areas. |
| **Code quality · High** | Layered package (`data → knowledge → telemetry → tools → reasoning → ops → cli`), typed + documented. Both engines drive tools through **one** `OpsToolbox` — no duplicated logic, no reaching into internals. |
| **Security · Medium** | Key from env only, never logged; inputs validated (persona parsed, zones/tools are closed enums); no `eval`/shell; minimal payload to the LLM. |
| **Efficiency · Medium** | Knowledge cached (`lru_cache`); crowd model is a pure O(1) function; routing is Dijkstra on a ~19-node graph; bounded agent-loop turns + `max_tokens`. |
| **Testing · Low** | 34 `pytest` tests across every layer — including the **Claude tool-use loop itself**, driven by a mocked SDK (not just the SDK-absent fallback). |
| **Accessibility · Low** | Any language via the LLM + an offline multilingual phrasebook; **step-free routing** as a first-class tool; plain, screen-reader-friendly CLI; theme-aware, keyboard-accessible, reduced-motion-safe web console. |

---

## 1. Chosen vertical

**In-stadium, match-time operations & fan experience.** The assistant works
*during* the game at a host venue and improves, directly and by name, the
problem statement's focus areas:

- **Crowd management & operational intelligence** — live hotspots, incident
  briefs, and a prioritised steward dispatch board for staff and volunteers.
- **Navigation & accessibility** — step-by-step walking routes with live
  congestion, and a first-class **step-free** routing mode that avoids stairs.
- **Transportation** — an egress plan that picks the least-congested exit and
  the best outbound transit for leaving *now*.
- **Multilingual assistance** — Claude answers in any language; even offline,
  fans get essential wayfinding/safety phrases in six languages.
- **Real-time decision support** — every answer is anchored to the current match
  minute, so the advice changes as the match does (ingress → halves → egress).

## 2. Approach and logic

**GenAI is the brain; grounded tools keep it honest.**

```
 staff / volunteer / fan  ─▶  question + match minute + language
                                        │
        ┌───────────────────────────────────────────────────────────────┐
        │  reasoning.ClaudeReasoningEngine   (the GenAI core)             │
        │  Claude reads the live match state, decides which tools to      │
        │  call, and writes a cited answer for this persona & language.   │
        └───────────────┬───────────────────────────────────────────────┘
                        │  one OpsToolbox — the single place a tool runs
                        ▼
   tools:  crowd_status · find_hotspots · plan_route · incident_brief
           egress_plan · dispatch_board · key_phrases
                        │
   telemetry (deterministic live crowd model)  +  data/*.json (+ citations)
```

- **GenAI-central:** Claude runs an agentic **tool-use loop** (`claude-opus-4-8`,
  adaptive thinking). It handles open-ended questions and **any language** —
  never a fixed rule tree.
- **Grounded, never invented:** the model is instructed to state **no** crowd
  number, queue, route, incident, or egress fact from its own memory — every
  fact comes from a tool result carrying a **source URL** (`data/sources.json`).
- **One shared toolbox:** the Claude engine *and* the offline engine both call
  tools only through `OpsToolbox.run(...)`, which is the single place a tool is
  executed and its citations recorded. There is no second copy of that logic.
- **Live by construction:** the crowd/queue state is a deterministic function of
  the **match minute** and the static venue data (see the honesty note below), so
  advice is match-phase-aware and fully reproducible/testable.
- **Persona-aware:** the same live state is framed as an ops decision (staff), a
  task list (volunteer), or plain wayfinding (fan).
- **Accessibility is built in:** routing has a step-free mode that excludes
  stairs; egress and facilities surface accessible options.
- **Safety framing:** the assistant supports human decision-makers and always
  points life-safety emergencies to the Venue Operations Centre / emergency line
  — it never commands emergency services.

## 3. How the solution works

### Install & run
```bash
git clone https://github.com/bhargabinath/FIFA-Prompt-Wars-4.git
cd FIFA-Prompt-Wars-4
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"          # Anthropic SDK optional: pip install -e ".[llm,dev]"

# Ready-made operations brief (staff, half-time):
python -m matchday_ops --demo

# Any persona / minute / language (offline works without a key):
python -m matchday_ops -p fan -m 92 -l Spanish -q "¿cuál es la salida más tranquila?"
python -m matchday_ops -p volunteer -m 48
python -m matchday_ops -p staff -m -30 -q "are we ready for the ingress surge?"

# Explore the venue and the live crowd model:
python -m matchday_ops --map
python -m matchday_ops --live
```

### Enable the GenAI core (optional but recommended)
```bash
cp .env.example .env             # set ANTHROPIC_API_KEY, or just export it
export ANTHROPIC_API_KEY=sk-ant-...
python -m matchday_ops -p fan -l Hindi -q "step-free route from Gate C to section 320?"
```
With a key, Claude answers your **exact** free-form question in **your language**,
grounded in the same cited tools. Without one, you get the deterministic grounded
briefing in English (plus multilingual key phrases).

### Visual console (zero setup)
Open [`web/index.html`](web/index.html) in a browser — no server, no key. Switch
persona, **scrub the match minute**, and watch the live crowd map, the
persona-specific brief, incidents, egress, and a **step-free route planner**
update in real time. It reimplements the deterministic offline engine in the
browser (the Python package is the canonical backend). Theme-aware,
keyboard-accessible, `prefers-reduced-motion`-safe. Original artwork only.

### Test
```bash
pytest                           # 34 tests, no network required
```

## 4. Project layout
```
agents/                       Design ledger — read this first
  persona.md requirements.md data-points.md mistakes.md
src/matchday_ops/
  models.py       Typed domain (Persona, CrowdReading, Route, Incident, Answer, Citation)
  config.py       Env-only settings (no secret hardcoded/logged)
  knowledge.py    Cached loader + citation resolver for data/*.json
  telemetry.py    Deterministic live crowd model (pure function of the match minute)
  tools.py        Grounded, cited tools (crowd, routing, incidents, egress, dispatch, phrases)
  reasoning.py    GenAI core: Claude tool-use loop + offline engine, sharing one OpsToolbox
  ops.py          Orchestration (persona + question + minute → answer)
  cli.py          Multi-persona, accessible command line
  data/*.json     Stadium, zones+graph, transit, incidents, phrases, sources
web/index.html    Self-contained live ops console (open in a browser)
tests/            pytest suite for every layer (incl. the mocked LLM loop)
```

## 5. Assumptions

- **Decision support, not command-and-control.** The assistant advises humans;
  admission, medical, and life-safety calls stay with venue staff and emergency
  services. Every fact ships with its authoritative source.
- **Deterministic crowd model stands in for a live feed.** There is no real
  sensor feed in this environment, so crowd state is modelled as a *pure,
  reproducible function of the match minute* and the venue data. This is
  deliberately honest: it is clearly a simulation of live telemetry, and it makes
  every layer testable and runnable offline. Swapping in a real feed is a change
  behind the `telemetry` module only — the tools and reasoning are unaffected.
- **Representative host venue.** The stadium layout and SOPs are original and
  labelled representative; standards cited (SGSA/Green Guide, NFPA 101, ADA, FTA,
  FIFA) are real and public.
- **Curated, extensible data.** Zones, links, transit, and incidents live in
  `data/*.json`; extending the venue is a data-only change.

---

_Built with [Claude Code](https://claude.com/claude-code) for the Prompt Wars FIFA 2026 challenge._
