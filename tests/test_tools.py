"""Grounded tools return correct, cited, connected results."""

import pytest

from matchday_ops import knowledge, tools


def test_crowd_status_covers_all_zones():
    readings = tools.crowd_status(48)
    assert {r.zone_key for r in readings} == set(knowledge.zones())


def test_hotspots_are_only_crowded_or_critical_and_sorted():
    hs = tools.hotspots(48)
    assert all(r.status in ("crowded", "critical") for r in hs)
    assert hs == sorted(hs, key=lambda r: r.density_pct, reverse=True)


def test_route_legs_connect_origin_to_destination():
    route = tools.plan_route("gate_c", "sec_320")
    assert route.legs[0].from_zone == "gate_c"
    assert route.legs[-1].to_zone == "sec_320"
    for a, b in zip(route.legs, route.legs[1:]):
        assert a.to_zone == b.from_zone
    assert route.total_minutes == sum(leg.walk_minutes for leg in route.legs)


def test_accessible_route_is_step_free_and_avoids_stairs():
    route = tools.plan_route("gate_c", "sec_320", accessible=True)
    assert route.accessible
    assert all(leg.step_free for leg in route.legs)
    assert all("stairs_core" not in (leg.from_zone, leg.to_zone) for leg in route.legs)


def test_route_congestion_note_appears_at_busy_times():
    # At half-time the concourse is critical; a route through it should be flagged.
    route = tools.plan_route_at("gate_b", "sec_320", minute=48)
    assert route.congestion_note is not None


def test_same_origin_destination_rejected():
    with pytest.raises(knowledge.KnowledgeError):
        tools.plan_route("gate_a", "gate_a")


def test_egress_plan_picks_a_gate_and_transit():
    plan = tools.egress_plan(92)
    assert "Gate" in plan.recommended_gate
    assert plan.est_transit_wait_minutes > 0
    assert plan.citations


def test_accessible_egress_uses_accessible_gate_and_transit():
    plan = tools.egress_plan(92, accessible=True)
    assert plan.accessible
    # Accessible gates in the data are Gate A and Gate C.
    assert any(g in plan.recommended_gate for g in ("Gate A", "Gate C"))


def test_dispatch_board_prioritises_high_first():
    board = tools.dispatch_board(48)
    assert board  # half-time has hotspots
    priorities = [d.priority for d in board]
    assert priorities == sorted(priorities, key=lambda p: p != "high")


def test_key_phrases_supported_and_fallback():
    es = tools.key_phrases("Spanish")
    assert es["language"] == "Spanish"
    assert es["phrases"]["exit"] == "Salida"
    assert not es["fallback_to_english"]

    unknown = tools.key_phrases("Klingon")
    assert unknown["fallback_to_english"]
    assert unknown["phrases"]["exit"] == "Exit"
