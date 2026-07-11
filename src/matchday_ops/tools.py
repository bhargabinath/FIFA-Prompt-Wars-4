"""Grounded tools — the retrieval + computation layer.

Pure functions that turn the knowledge base and live telemetry into structured,
cited results. They are what keep the GenAI honest: Claude reasons and decides
*which* tools to call, but the facts (crowd numbers, routes, incidents, egress)
come from here, each carrying its citations. The offline engine calls the very
same functions, so behaviour is identical with or without the LLM.
"""

from __future__ import annotations

import heapq

from . import knowledge, telemetry
from .models import (
    CrowdReading,
    DispatchItem,
    EgressPlan,
    Incident,
    Route,
    RouteLeg,
)

_HOTSPOT_STATUSES = ("crowded", "critical")


# --- Crowd -----------------------------------------------------------------


def crowd_status(minute: int) -> list[CrowdReading]:
    """Live crowd density, queue wait, and status for every zone."""
    return telemetry.snapshot(minute)


def hotspots(minute: int) -> list[CrowdReading]:
    """Zones at 'crowded' or 'critical', worst first."""
    readings = [r for r in telemetry.snapshot(minute) if r.status in _HOTSPOT_STATUSES]
    return sorted(readings, key=lambda r: r.density_pct, reverse=True)


# --- Routing (accessibility-aware) -----------------------------------------


def _graph(accessible: bool) -> dict[str, list[tuple[str, int, bool]]]:
    """Undirected walk graph. In accessible mode, non-step-free links are dropped."""
    graph: dict[str, list[tuple[str, int, bool]]] = {k: [] for k in knowledge.zone_keys()}
    for a, b, walk_min, step_free in knowledge.links():
        if accessible and not step_free:
            continue
        graph[a].append((b, walk_min, step_free))
        graph[b].append((a, walk_min, step_free))
    return graph


def plan_route(origin: str, destination: str, accessible: bool = False) -> Route:
    """Shortest walking route between two zones (Dijkstra on walk-minutes).

    With ``accessible=True`` the route is guaranteed step-free — stairs and any
    non-step-free link are excluded from the graph.
    """
    knowledge.get_zone(origin)  # validate, raises KnowledgeError if unknown
    knowledge.get_zone(destination)
    if origin == destination:
        raise knowledge.KnowledgeError("Origin and destination are the same zone.")

    graph = _graph(accessible)
    prev: dict[str, tuple[str, int, bool]] = {}
    dist = {origin: 0}
    pq: list[tuple[int, str]] = [(0, origin)]
    while pq:
        d, node = heapq.heappop(pq)
        if node == destination:
            break
        if d > dist.get(node, 1 << 30):
            continue
        for nxt, walk_min, step_free in graph[node]:
            nd = d + walk_min
            if nd < dist.get(nxt, 1 << 30):
                dist[nxt] = nd
                prev[nxt] = (node, walk_min, step_free)
                heapq.heappush(pq, (nd, nxt))

    if destination not in dist:
        mode = "step-free " if accessible else ""
        raise knowledge.KnowledgeError(
            f"No {mode}route from '{origin}' to '{destination}'."
        )

    # Reconstruct the path back to front.
    legs: list[RouteLeg] = []
    node = destination
    while node != origin:
        came_from, walk_min, step_free = prev[node]
        legs.append(
            RouteLeg(
                from_zone=came_from,
                to_zone=node,
                walk_minutes=walk_min,
                step_free=step_free,
            )
        )
        node = came_from
    legs.reverse()

    sources = ["venue_ops_manual"] + (["ada_guidance"] if accessible else [])
    return Route(
        origin=origin,
        destination=destination,
        accessible=accessible,
        legs=tuple(legs),
        total_minutes=dist[destination],
        congestion_note=None,  # plan_route is time-independent; see plan_route_at
        citations=knowledge.citations(*sources),
    )


def plan_route_at(origin: str, destination: str, minute: int, accessible: bool = False) -> Route:
    """Like :func:`plan_route`, but overlays live congestion for ``minute``."""
    route = plan_route(origin, destination, accessible)
    worst: CrowdReading | None = None
    for leg in route.legs:
        reading = telemetry.reading_for(leg.to_zone, minute)
        if reading.status in _HOTSPOT_STATUSES and (
            worst is None or reading.density_pct > worst.density_pct
        ):
            worst = reading
    note = None
    if worst is not None:
        note = (
            f"Route passes {worst.zone_name} ({worst.status}, {worst.density_pct}% full) — "
            "allow extra time or ask a steward for a quieter path."
        )
    return Route(
        origin=route.origin,
        destination=route.destination,
        accessible=route.accessible,
        legs=route.legs,
        total_minutes=route.total_minutes,
        congestion_note=note,
        citations=route.citations,
    )


# --- Incidents -------------------------------------------------------------


def incident_brief(minute: int) -> list[Incident]:
    """Active incidents: scheduled ones in their window + crowd-driven ones."""
    out: list[Incident] = []
    for inc in knowledge.scheduled_incidents():
        lo, hi = inc["active_minutes"]
        if lo <= minute <= hi:
            zone = knowledge.get_zone(inc["zone_key"])
            out.append(
                Incident(
                    id=inc["id"],
                    zone_key=inc["zone_key"],
                    zone_name=zone["name"],
                    type=inc["type"],
                    severity=inc["severity"],
                    summary=inc["summary"],
                    protocol=inc["protocol"],
                    citations=knowledge.citations(*inc.get("sources", ())),
                )
            )
    # Crowd-driven: any zone at 'critical' becomes a live crowding incident.
    for r in hotspots(minute):
        if r.status == "critical":
            out.append(
                Incident(
                    id=f"live_crowd_{r.zone_key}",
                    zone_key=r.zone_key,
                    zone_name=r.zone_name,
                    type="crowding",
                    severity="urgent",
                    summary=f"{r.zone_name} is critical ({r.density_pct}% full, ~{r.wait_minutes} min wait).",
                    protocol="Meter inflow, open alternative routes, and position stewards per the crowd-management plan.",
                    citations=knowledge.citations("green_guide"),
                )
            )
    return out


# --- Egress ----------------------------------------------------------------


def egress_plan(minute: int, accessible: bool = False, transit_preference: str | None = None) -> EgressPlan:
    """Recommend the least-congested exit gate and best outbound transit now."""
    phase, _ = telemetry.match_phase(minute)
    gates = [
        r for r in telemetry.snapshot(minute)
        if r.category == "gate" and (not accessible or knowledge.get_zone(r.zone_key)["accessible"])
    ]
    if not gates:  # accessible requested but somehow none flagged — fall back to all gates
        gates = [r for r in telemetry.snapshot(minute) if r.category == "gate"]
    best_gate = min(gates, key=lambda r: r.density_pct)

    options = knowledge.transit()
    if accessible:
        options = {k: v for k, v in options.items() if v["accessible"]}

    def wait(opt: dict) -> int:
        return opt["egress_wait"] if phase == "egress" else opt["base_wait"]

    if transit_preference and transit_preference in options:
        mode_key = transit_preference
    else:
        mode_key = min(options, key=lambda k: wait(options[k]))
    mode = options[mode_key]

    rationale = (
        f"{best_gate.zone_name} is the least-congested{' accessible' if accessible else ''} "
        f"exit right now ({best_gate.status}, {best_gate.density_pct}% full). "
        f"{mode['name']} has the shortest projected wait (~{wait(mode)} min)."
    )
    sources = ["nfpa_101", "transit_authority"] + (["ada_guidance"] if accessible else [])
    return EgressPlan(
        recommended_gate=best_gate.zone_name,
        gate_status=best_gate.status,
        transit_mode=mode["name"],
        est_transit_wait_minutes=wait(mode),
        accessible=accessible,
        rationale=rationale,
        citations=knowledge.citations(*sources),
    )


# --- Volunteer / steward dispatch ------------------------------------------


def dispatch_board(minute: int) -> list[DispatchItem]:
    """Prioritised deployment suggestions from hotspots + active incidents."""
    items: list[DispatchItem] = []
    for r in hotspots(minute):
        priority = "high" if r.status == "critical" else "medium"
        items.append(
            DispatchItem(
                zone_key=r.zone_key,
                zone_name=r.zone_name,
                priority=priority,
                action=f"Position stewards to meter flow at {r.zone_name}; open a secondary route.",
                reason=f"{r.status} — {r.density_pct}% full, ~{r.wait_minutes} min wait.",
            )
        )
    for inc in incident_brief(minute):
        if inc.severity == "urgent" and not inc.id.startswith("live_crowd_"):
            items.append(
                DispatchItem(
                    zone_key=inc.zone_key,
                    zone_name=inc.zone_name,
                    priority="high",
                    action=inc.protocol,
                    reason=inc.summary,
                )
            )
    # High priority first, then by zone for stable ordering.
    return sorted(items, key=lambda i: (i.priority != "high", i.zone_key))


# --- Multilingual key phrases ----------------------------------------------


def key_phrases(language: str) -> dict:
    """Essential wayfinding/safety phrases in a supported language.

    Falls back to English (with a note) for languages outside the fixed set —
    the Claude engine handles arbitrary languages itself.
    """
    langs = knowledge.phrase_languages()  # {code: display}
    code = _resolve_language(language, langs)
    fallback = code is None
    code = code or "en"
    table = {
        key: values.get(code, values["en"]) for key, values in knowledge.phrases().items()
    }
    cite = knowledge.citation("venue_ops_manual")
    return {
        "language": langs.get(code, "English"),
        "fallback_to_english": fallback,
        "phrases": table,
        "citations": [cite.to_dict()],
    }


def _resolve_language(language: str, langs: dict[str, str]) -> str | None:
    key = language.strip().lower()
    if key in langs:  # already a code
        return key
    for code, display in langs.items():
        if display.lower() == key:
            return code
    aliases = {"español": "es", "espanol": "es", "français": "fr", "francais": "fr",
               "português": "pt", "portugues": "pt", "عربي": "ar", "हिंदी": "hi"}
    return aliases.get(key)


# --- Reference -------------------------------------------------------------


def list_zones() -> dict:
    """Zone key -> 'Name (category, level)'. Helps map free text to a zone key."""
    return {
        k: f"{z['name']} ({z['category']}, {z['level']})"
        for k, z in knowledge.zones().items()
    }
