# Representative GenAI answer

What the **Claude reasoning core** produces once `ANTHROPIC_API_KEY` is set.
This shows the agentic tool-use loop in action — Claude reads the live match
state, decides which tools to call, and writes a persona-specific, cited answer.
The facts (crowd numbers, incidents, egress) come from the tools; the reasoning
and language handling are Claude's.

---

## Staff · minute 48 (half-time)

**Question:** *"Concourse looks packed at the break — where are we overcrowded,
any incidents, and are we ready for full-time egress?"*

**Tools Claude called:** `find_hotspots` → `incident_brief` → `egress_plan`
→ `dispatch_board`

> **Half-time crowding — act now on the East side.**
>
> **Overcrowded (worst first):**
> - **Lower Concourse East — CRITICAL (90%, ~6 min).** Meter inflow and open the
>   East↔West link so fans can spread to the calmer West concourse.
> - **Upper Concourse East — CRITICAL (90%, ~6 min).** Same treatment; watch the
>   stair core feeding it.
> - Lower & Upper Concourse West — crowded (81%) but absorbing overflow.
>
> **Incidents:**
> - **[URGENT] Section 128 — medical assist.** Nearest first-aid team dispatched;
>   keep a step-free path clear to Main First Aid for wheelchair/stretcher access.
> - **[ADVISORY] Family Area — unaccompanied minor.** Safeguarding reunification
>   under way.
>
> **Egress readiness:** ready. **Gate C (accessible)** is calm (7%) and will be
> your cleanest release point; **Metro** is the shortest onward wait (~6 min now,
> rising at full time). Pre-stage stewards at Gate C before the whistle.
>
> If anything escalates to life-safety, call it in to the Venue Operations
> Centre / emergency line — this is decision support, not a dispatch authority.
>
> **Sources:** SGSA Guide to Safety at Sports Grounds · NFPA 101 (egress) ·
> ADA accessible-assembly standards · FTA transit guidance.

---

## Fan · minute 92 (full-time egress) · answered in Spanish

**Question:** *"¿Cuál es la salida más tranquila y una ruta sin escaleras a la
salida?"*

**Tools Claude called:** `get_crowd_status` → `egress_plan` (accessible)
→ `plan_route` (accessible) → `key_phrases`

> **La salida más tranquila ahora mismo es la Puerta C (accesible).** Está menos
> congestionada que las Puertas B y D. Para salir sin escaleras desde la
> tribuna: toma el **núcleo de ascensores** hasta el concourse inferior y sigue
> hacia la Puerta C (unos 8 minutos). Para transporte, el **autobús lanzadera**
> tiene la espera más corta (~15 min) en este momento.
>
> Frases útiles: **Salida**, **Ruta accesible**, **Ayuda**.
>
> **Fuentes:** NFPA 101 · normas de accesibilidad ADA · orientación de transporte FTA.

---

*Answers are generated live, so exact wording varies. The offline engine (no key)
produces the same grounded facts as a structured English briefing plus a
multilingual phrasebook — run `python -m matchday_ops --demo`.*
