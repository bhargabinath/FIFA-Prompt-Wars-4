"""Typed domain model for MatchDay Ops.

Grounded tool results carry the citations that back them, so every fact an
answer states can be traced to an authoritative source (``sources.json``).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

# The one place category labels are defined; telemetry and tools import these.
CROWD_STATUSES = ("calm", "busy", "crowded", "critical")
SEVERITIES = ("info", "advisory", "urgent")


class Persona(str, Enum):
    """Who is asking. Drives tool selection and how the answer is framed."""

    STAFF = "staff"
    VOLUNTEER = "volunteer"
    FAN = "fan"

    @property
    def label(self) -> str:
        return {
            "staff": "Venue Operations",
            "volunteer": "Volunteer",
            "fan": "Fan",
        }[self.value]

    @classmethod
    def parse(cls, value: str) -> "Persona":
        key = value.strip().lower()
        aliases = {
            "ops": cls.STAFF, "operations": cls.STAFF, "staff": cls.STAFF,
            "steward": cls.VOLUNTEER, "volunteer": cls.VOLUNTEER,
            "fan": cls.FAN, "spectator": cls.FAN, "supporter": cls.FAN,
        }
        if key not in aliases:
            raise ValueError(
                f"Unknown persona '{value}'. Use one of: staff, volunteer, fan."
            )
        return aliases[key]


def _cite_list(citations: tuple["Citation", ...]) -> list[dict]:
    return [c.to_dict() for c in citations]


@dataclass(frozen=True)
class Citation:
    """A reference to an authoritative source, resolved from ``sources.json``."""

    source_id: str
    title: str
    url: str

    def to_dict(self) -> dict:
        return asdict(self)


# --- Grounded tool results --------------------------------------------------


@dataclass(frozen=True)
class CrowdReading:
    """Live crowd state for one zone at the current match minute."""

    zone_key: str
    zone_name: str
    category: str
    occupancy: int
    capacity: int
    density_pct: int
    wait_minutes: int
    status: str  # one of CROWD_STATUSES
    citations: tuple[Citation, ...]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["citations"] = _cite_list(self.citations)
        return d


@dataclass(frozen=True)
class RouteLeg:
    from_zone: str
    to_zone: str
    walk_minutes: int
    step_free: bool


@dataclass(frozen=True)
class Route:
    origin: str
    destination: str
    accessible: bool
    legs: tuple[RouteLeg, ...]
    total_minutes: int
    congestion_note: str | None
    citations: tuple[Citation, ...]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["citations"] = _cite_list(self.citations)
        return d


@dataclass(frozen=True)
class Incident:
    id: str
    zone_key: str
    zone_name: str
    type: str
    severity: str  # one of SEVERITIES
    summary: str
    protocol: str
    citations: tuple[Citation, ...]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["citations"] = _cite_list(self.citations)
        return d


@dataclass(frozen=True)
class DispatchItem:
    zone_key: str
    zone_name: str
    priority: str  # "high" | "medium"
    action: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class EgressPlan:
    recommended_gate: str
    gate_status: str
    transit_mode: str
    est_transit_wait_minutes: int
    accessible: bool
    rationale: str
    citations: tuple[Citation, ...]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["citations"] = _cite_list(self.citations)
        return d


# --- Final answer -----------------------------------------------------------


@dataclass(frozen=True)
class Answer:
    """The assistant's response to a persona's question."""

    text: str
    persona: str
    language: str
    citations: tuple[Citation, ...] = ()
    tools_used: tuple[str, ...] = ()
    used_llm: bool = False

    @property
    def unique_citations(self) -> list[Citation]:
        seen: dict[str, Citation] = {}
        for c in self.citations:
            seen.setdefault(c.source_id, c)
        return list(seen.values())
