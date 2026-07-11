"""The live-signal layer — deterministic, reproducible "telemetry".

There is no real sensor feed in this environment, so crowd state is modelled as
a *pure function of the match clock and the static zone data*: a base occupancy
per zone, modulated by a per-category multiplier for the current match phase.
This is honest (it is clearly a simulation of live signals), fully deterministic
(no RNG, no wall-clock), and therefore completely testable and runnable offline.

The Claude reasoning core never invents these numbers — it reads them through
the grounded tools that call this module.
"""

from __future__ import annotations

from . import knowledge
from .models import Citation, CrowdReading

# Match phases keyed by the match minute. Negative minutes are pre-match
# ingress; 90+ is full-time egress.
PHASES = ("ingress", "first_half", "halftime", "second_half", "egress")

# Per-phase, per-zone-category load multiplier applied to a zone's base_load.
_MULT: dict[str, dict[str, float]] = {
    "ingress": {"gate": 1.7, "transit": 1.6, "plaza": 1.5, "concourse": 1.2, "seating": 0.4, "amenity": 0.9, "accessibility": 1.3, "first_aid": 0.6, "vertical": 1.2},
    "first_half": {"gate": 0.2, "transit": 0.3, "plaza": 0.3, "concourse": 0.4, "seating": 1.4, "amenity": 0.6, "accessibility": 0.7, "first_aid": 0.9, "vertical": 0.5},
    "halftime": {"gate": 0.2, "transit": 0.4, "plaza": 0.5, "concourse": 1.8, "seating": 0.6, "amenity": 1.7, "accessibility": 1.1, "first_aid": 1.1, "vertical": 1.6},
    "second_half": {"gate": 0.2, "transit": 0.4, "plaza": 0.3, "concourse": 0.5, "seating": 1.4, "amenity": 0.7, "accessibility": 0.7, "first_aid": 1.0, "vertical": 0.6},
    "egress": {"gate": 1.8, "transit": 1.9, "plaza": 1.6, "concourse": 1.5, "seating": 0.3, "amenity": 0.8, "accessibility": 1.3, "first_aid": 0.9, "vertical": 1.7},
}


def match_phase(minute: int) -> tuple[str, str]:
    """Return ``(phase_key, human_label)`` for a match minute."""
    if minute < 0:
        return "ingress", "Pre-match ingress"
    if minute < 45:
        return "first_half", "First half"
    if minute < 60:
        return "halftime", "Half-time"
    if minute < 90:
        return "second_half", "Second half"
    return "egress", "Full-time egress"


def _status(density_pct: int) -> str:
    if density_pct >= 90:
        return "critical"
    if density_pct >= 75:
        return "crowded"
    if density_pct >= 50:
        return "busy"
    return "calm"


def _wait_minutes(category: str, density_pct: int) -> int:
    # Queue-prone areas (gates, transit, plaza) build waits faster.
    divisor = 8 if category in ("gate", "transit", "plaza") else 15
    return round(density_pct / divisor)


def reading_for(zone_key: str, minute: int) -> CrowdReading:
    """Crowd reading for one zone at ``minute``. Deterministic."""
    zone = knowledge.get_zone(zone_key)
    phase, _ = match_phase(minute)
    category = zone["category"]
    mult = _MULT[phase].get(category, 1.0)
    density = min(100, round(zone["base_load"] * mult * 100))
    capacity = int(zone["capacity"])
    occupancy = round(capacity * density / 100)
    cite = _crowd_citation()
    return CrowdReading(
        zone_key=zone_key,
        zone_name=zone["name"],
        category=category,
        occupancy=occupancy,
        capacity=capacity,
        density_pct=density,
        wait_minutes=_wait_minutes(category, density),
        status=_status(density),
        citations=(cite,),
    )


def snapshot(minute: int) -> list[CrowdReading]:
    """Crowd readings for every zone at ``minute``, ordered by zone key."""
    return [reading_for(k, minute) for k in knowledge.zone_keys()]


def _crowd_citation() -> Citation:
    return knowledge.citation("green_guide")
