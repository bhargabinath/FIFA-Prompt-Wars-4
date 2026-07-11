# Data points & provenance

Every fact an answer states is traceable to `data/sources.json`. The typed
domain model in `models.py` mirrors this document.

## Static knowledge (`data/*.json`)

| File | Contents |
| --- | --- |
| `stadium.json` | Venue identity, levels, kickoff, control room / emergency line. |
| `zones.json` | ~19 zones (name, category, level, capacity, `base_load`, `accessible`, amenities) **plus** the undirected walk graph `_links` = `[a, b, walk_minutes, step_free]`. |
| `transit.json` | Outbound transit options with `base_wait` / `egress_wait` and accessibility. |
| `incidents.json` | Scheduled incidents with an active match-minute window + response protocol. |
| `phrases.json` | Six-language wayfinding/safety phrasebook for offline multilingual output. |
| `sources.json` | Citation registry (SGSA Green Guide, NFPA 101, ADA, FTA, FIFA). |

## The live crowd model (`telemetry.py`) — an honest simulation

There is no real sensor feed here, so crowd state is a **pure, deterministic
function** of the match minute and the static data:

```
density% = min(100, round(zone.base_load × phase_multiplier[phase][zone.category] × 100))
status   = calm (<50) · busy (<75) · crowded (<90) · critical (≥90)
wait_min = density / 8   (gates/transit/plaza)   or   density / 15  (elsewhere)
```

`phase` is derived from the match minute: ingress (`<0`) → first half → half-time
→ second half → egress (`≥90`). No RNG, no wall-clock — fully reproducible and
testable. Swapping in a real feed is a change **behind this module only**.

## Grounded tool outputs (`models.py`)

- `CrowdReading` — per-zone occupancy, density%, wait, status (+ citations).
- `Route` / `RouteLeg` — Dijkstra path with per-leg `step_free`, total minutes,
  live congestion note (+ citations). Accessible mode drops non-step-free links.
- `Incident` — scheduled (in-window) + live crowd-driven, each with a protocol.
- `EgressPlan` — least-congested exit + best transit for leaving now.
- `DispatchItem` — prioritised steward/volunteer action derived from hotspots +
  incidents.
- `Answer` — final text + persona + language + citations + tools used + `used_llm`.

## Provenance rule

Tools attach citations to their results; `OpsToolbox` records them centrally, so
the final answer's sources are exactly the sources of the facts it used — whether
the answer was written by Claude or the offline engine.
