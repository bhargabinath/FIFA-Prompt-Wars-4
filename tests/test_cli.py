"""The CLI runs its offline modes end-to-end and fails gracefully."""

from matchday_ops import cli


def test_map_mode(capsys):
    assert cli.main(["--map"]) == 0
    out = capsys.readouterr().out
    assert "East Metro Stadium" in out
    assert "PLAZA" in out and "LOWER" in out


def test_live_mode(capsys):
    assert cli.main(["--live"]) == 0
    out = capsys.readouterr().out
    assert "Crowd status across the match" in out


def test_demo_mode(capsys):
    assert cli.main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Venue Operations" in out
    assert "offline" in out  # no key in the test environment


def test_one_shot_fan(capsys):
    assert cli.main(["-p", "fan", "-m", "92", "-q", "how do I leave?"]) == 0
    out = capsys.readouterr().out
    assert "Leaving the stadium" in out


def test_bad_persona_exits_2(capsys):
    assert cli.main(["-p", "referee"]) == 2
    err = capsys.readouterr().err
    assert "Unknown persona" in err
