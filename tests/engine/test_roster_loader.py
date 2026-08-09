import datetime
import types

import pytest

from crewsim import config
from crewsim.engine import roster_loader


def test_roster_loader():
    """Verify D1 and D2 load correctly into CrewMember and Blocks, applying exclusions."""
    cfg = config.load()

    # We test on YUL A321 FO as specified in the manual check, if the data has A321neoLR we use it,
    # otherwise we just assert the structural behavior.
    active, exclusions = roster_loader.load_rosters(cfg, base="YUL", position="FO", fleet="A321")

    assert len(active) > 0, "Should load some active crew"

    # Check that exclusion stats exist
    assert "LONG_TERM_ABSENCE" in exclusions

    # Check the first crew member's state
    c = active[0]
    assert c.base == "YUL"
    assert c.position == "FO"
    assert "A321" in str(c.fleet_quals) or "A321" in next(iter(c.fleet_quals))

    # Calendar should be populated
    # And it must be sorted
    if c.calendar:
        for i in range(1, len(c.calendar)):
            assert c.calendar[i-1].end <= c.calendar[i].start, "Blocks must not overlap and be sorted"

    # S1d-04b: block times must be minutes-since-template-window-start, not
    # Unix-epoch-seconds (~1.7 billion). A block can legitimately extend a
    # little past the horizon boundary (rest/rolling-limit context), but
    # never by orders of magnitude -- 10x the horizon is a generous bound
    # that still catches a regression back to `.timestamp()` immediately.
    window_start, window_end = roster_loader.select_template_window(cfg)
    horizon_minutes = cfg.horizon.horizon_days * 1440.0
    for c in active:
        for b in c.calendar:
            assert abs(b.start) < 10 * horizon_minutes, (
                f"block start {b.start} is not minutes-scale "
                f"(template window {window_start} to {window_end})"
            )
            assert abs(b.end) < 10 * horizon_minutes, (
                f"block end {b.end} is not minutes-scale "
                f"(template window {window_start} to {window_end})"
            )


def _fake_windows_cfg(holdout_start, holdout_end, season, horizon_days):
    """Minimal cfg stand-in for select_template_window's own inputs."""
    fake_holdout = types.SimpleNamespace(start=holdout_start, end=holdout_end)
    fake_windows = types.SimpleNamespace(get=lambda name: fake_holdout)
    cfg = types.SimpleNamespace()
    cfg.windows = fake_windows
    cfg.scope = types.SimpleNamespace(season=season)
    cfg.horizon = types.SimpleNamespace(horizon_days=horizon_days)
    return cfg


def test_select_template_window_picks_most_recent_matching_span(monkeypatch):
    """The window must be the LATEST horizon_days-length span whose every
    touched month is in season -- not just any matching span."""
    monkeypatch.setattr(roster_loader.loaders, "load_seasons", lambda cfg: {"jan_only": [1]})

    cfg = _fake_windows_cfg(
        holdout_start=datetime.date(2026, 1, 1),
        holdout_end=datetime.date(2026, 4, 11),  # holdout runs well past January
        season="jan_only",
        horizon_days=10,
    )
    start, end = roster_loader.select_template_window(cfg)

    # Jan has 31 days; the latest 10-day span fully inside January starts on
    # the 22nd (22..31). One day later (23) would touch February 1 -- outside
    # jan_only -- so 22 is the correct, non-off-by-one answer.
    assert start == datetime.date(2026, 1, 22)
    assert end == datetime.date(2026, 2, 1)


def test_select_template_window_raises_when_nothing_fits(monkeypatch):
    """No span inside holdout falls entirely within season -> a clear error,
    not a window silently anchored to the wrong months."""
    monkeypatch.setattr(roster_loader.loaders, "load_seasons", lambda cfg: {"june_only": [6]})

    cfg = _fake_windows_cfg(
        holdout_start=datetime.date(2026, 1, 1),
        holdout_end=datetime.date(2026, 1, 31),  # entirely January
        season="june_only",
        horizon_days=10,
    )
    with pytest.raises(ValueError, match="No 10-day window"):
        roster_loader.select_template_window(cfg)
