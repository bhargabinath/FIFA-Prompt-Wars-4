"""Cached, read-only access to the grounded knowledge base in ``data/*.json``.

All data is parsed once per process. Citations are resolved centrally so every
grounded fact can point at an authoritative source.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources

from .models import Citation

_DATA_PACKAGE = "matchday_ops.data"


class KnowledgeError(LookupError):
    """Raised on a missing knowledge-base entry, with a helpful message."""


def _load(filename: str) -> object:
    with resources.files(_DATA_PACKAGE).joinpath(filename).open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=None)
def _file(filename: str) -> dict:
    return _load(filename)  # type: ignore[return-value]


def _strip_meta(data: dict) -> dict:
    return {k: v for k, v in data.items() if not k.startswith("_")}


# --- Sources & citations ----------------------------------------------------


def citation(source_id: str) -> Citation:
    sources = _file("sources.json")
    entry = sources.get(source_id)
    if not entry or source_id.startswith("_"):
        raise KnowledgeError(f"Unknown source id '{source_id}'.")
    return Citation(source_id=source_id, title=entry["title"], url=entry["url"])


def citations(*source_ids: str) -> tuple[Citation, ...]:
    """Resolve a set of source ids to citations, de-duplicated, order-preserving."""
    seen: dict[str, Citation] = {}
    for sid in source_ids:
        if sid and sid not in seen:
            seen[sid] = citation(sid)
    return tuple(seen.values())


# --- Stadium & zones --------------------------------------------------------


def stadium() -> dict:
    return _file("stadium.json")


def zones() -> dict[str, dict]:
    return _strip_meta(_file("zones.json"))


def get_zone(key: str) -> dict:
    try:
        return zones()[key]
    except KeyError:
        raise KnowledgeError(
            f"Unknown zone '{key}'. Known: {', '.join(zone_keys())}."
        ) from None


def zone_keys() -> list[str]:
    return sorted(zones())


def links() -> list[list]:
    """Undirected walk graph: ``[zone_a, zone_b, walk_minutes, step_free]``."""
    return _file("zones.json")["_links"]


# --- Transit, incidents, phrases --------------------------------------------


def transit() -> dict[str, dict]:
    return _strip_meta(_file("transit.json"))


def scheduled_incidents() -> list[dict]:
    return _file("incidents.json")["scheduled"]


def phrases() -> dict[str, dict]:
    return _strip_meta(_file("phrases.json"))


def phrase_languages() -> dict[str, str]:
    return _file("phrases.json")["_meta"]["languages"]
