"""Knowledge base loads, citations resolve, and the walk graph is coherent."""

import pytest

from matchday_ops import knowledge


def test_zones_and_links_are_coherent():
    zones = knowledge.zones()
    assert len(zones) >= 15
    keys = set(zones)
    for a, b, walk_min, step_free in knowledge.links():
        assert a in keys and b in keys, f"link references unknown zone: {a}/{b}"
        assert walk_min > 0
        assert isinstance(step_free, bool)


def test_graph_is_fully_connected():
    # Every zone must be reachable from any other (BFS over the full walk graph).
    adj: dict[str, set[str]] = {k: set() for k in knowledge.zones()}
    for a, b, *_ in knowledge.links():
        adj[a].add(b)
        adj[b].add(a)
    start = knowledge.zone_keys()[0]
    seen = {start}
    stack = [start]
    while stack:
        for nxt in adj[stack.pop()]:
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    assert seen == set(knowledge.zones())


def test_citations_resolve_and_dedupe():
    cites = knowledge.citations("green_guide", "green_guide", "ada_guidance")
    assert [c.source_id for c in cites] == ["green_guide", "ada_guidance"]
    assert all(c.url.startswith("http") for c in cites)


def test_unknown_source_and_zone_raise():
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.citation("does_not_exist")
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.get_zone("nowhere")
