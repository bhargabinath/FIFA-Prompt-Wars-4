"""The live crowd model is deterministic and behaves sensibly by match phase."""

from matchday_ops import telemetry


def test_phase_boundaries():
    assert telemetry.match_phase(-30)[0] == "ingress"
    assert telemetry.match_phase(0)[0] == "first_half"
    assert telemetry.match_phase(44)[0] == "first_half"
    assert telemetry.match_phase(45)[0] == "halftime"
    assert telemetry.match_phase(59)[0] == "halftime"
    assert telemetry.match_phase(60)[0] == "second_half"
    assert telemetry.match_phase(90)[0] == "egress"


def test_readings_are_deterministic_and_bounded():
    first = telemetry.snapshot(48)
    second = telemetry.snapshot(48)
    assert [r.to_dict() for r in first] == [r.to_dict() for r in second]
    for r in first:
        assert 0 <= r.density_pct <= 100
        assert r.status in ("calm", "busy", "crowded", "critical")
        assert r.citations  # every reading is grounded


def test_egress_makes_a_gate_critical():
    gates = [r for r in telemetry.snapshot(92) if r.category == "gate"]
    assert any(r.status == "critical" for r in gates)


def test_halftime_crowds_a_concourse():
    concourses = [r for r in telemetry.snapshot(48) if r.category == "concourse"]
    assert any(r.status in ("crowded", "critical") for r in concourses)


def test_first_half_fills_seating_not_gates():
    snap = {r.zone_key: r for r in telemetry.snapshot(20)}
    assert snap["sec_112"].status in ("crowded", "critical")
    assert snap["gate_b"].status == "calm"
