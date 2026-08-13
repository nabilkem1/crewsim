"""reporting/tape.py -- one scenario, one policy, as an event tape.

The tape is the only surface that claims to show what the engine *did* rather
than what it cost, so the tests that matter are the ones that would catch it
quietly showing something else:

  * the regexes. They parse `sim.trace`, which is prose the engine formats for
    humans. A reworded log line would empty the tape of arrivals without any
    error at all, and the tape would still render -- just starting at a draft
    with no visible cause. These assert against a REAL run, so they fail the
    moment the format moves.
  * reconciliation. The tape's measured cost must equal the number the
    scoreboard reports for the same scenario, or the two views disagree about
    the same run.
"""

from __future__ import annotations

import pytest

from crewsim import config
from crewsim.engine import des
from crewsim.engine.policy import load_policy
from crewsim.reporting import tape as tape_mod
from crewsim.reporting.grid import _policy_path

SEED = "master"
N_SCENARIOS = 4
POLICY = "R10"

# Which scenario the tape is built from. NOT pinned to 0: this file asserts
# that every trace regex still matches real engine output, which requires a
# scenario that actually PRODUCES each kind of line -- and whether any given
# scenario drafts (and therefore cascades) is a property of the corpus and the
# reserve pool, not of the log format under test. Pinning 0 made the suite fail
# the moment reserve availability changed (the 2026-08-12 corpus fix gave
# reserves a real 12h daily window instead of 24h/day, so scenario 0's items
# are now all covered by reserves and it never drafts). Resolved once, lazily,
# by scanning for a scenario that exercises all three patterns.
_REQUIRED_MARKERS = ("SICK_CALL", "DISPLACED_LINE", "CASCADE")
_scenario_cache: dict[str, int] = {}


def _cfg():
    cfg = config.load()
    return cfg, config.load_costs(cfg)


def _scenario() -> int:
    """The scenario in the CRN set exercising the most trace markers.

    Best-effort, not all-or-nothing. Since the 2026-08-12 report-time
    eligibility and duty-cap fixes, ~100% of drafts are tier 1 (the day-off
    pool is never exhausted), so almost nothing cascades and CASCADE lines are
    genuinely rare -- see the audit's OPEN-6. Individual tests skip the
    markers a run does not contain rather than the whole file failing, so the
    patterns that ARE exercised still get asserted.
    """
    if "id" in _scenario_cache:
        return _scenario_cache["id"]
    cfg, costs = _cfg()
    policy = load_policy(_policy_path(POLICY))
    best, best_n = 0, -1
    for sid in range(N_SCENARIOS):
        sim = des.run_scenario(
            cfg, costs, policy, scenario_id=sid, master_seed=SEED,
            n_scenarios=N_SCENARIOS, trace=True,
        )
        n = sum(1 for m in _REQUIRED_MARKERS if any(m in line for line in sim.trace))
        if n > best_n:
            best, best_n = sid, n
        if n == len(_REQUIRED_MARKERS):
            break
    _scenario_cache["id"] = best
    return best


def _sim():
    cfg, costs = _cfg()
    return cfg, costs, des.run_scenario(
        cfg, costs, load_policy(_policy_path(POLICY)), scenario_id=_scenario(),
        master_seed=SEED, n_scenarios=N_SCENARIOS, trace=True,
    )


def _tape():
    cfg, costs = _cfg()
    return tape_mod.build_tape(
        cfg, costs, load_policy(_policy_path(POLICY)), _scenario(), SEED, N_SCENARIOS
    )


# ------------------------------------------------------------ the fragile part
def test_every_trace_pattern_still_matches_real_output() -> None:
    """The regexes are pinned to the engine's actual log format.

    Asserted per pattern rather than "the tape is non-empty": a single broken
    pattern would otherwise hide behind the others.
    """
    *_, sim = _sim()
    patterns = {
        "SICK_CALL": tape_mod._RE_SICK_CALL,
        "DISPLACED_LINE": tape_mod._RE_DISPLACED,
        "CASCADE": tape_mod._RE_CASCADE,
    }
    exercised = 0
    for name, pattern in patterns.items():
        matches = [line for line in sim.trace if pattern.match(line)]
        candidates = [line for line in sim.trace if name in line]
        if not candidates:
            # The phenomenon did not occur in this run, so this pattern is
            # untested here -- stated, not silently passed over (OPEN-6).
            continue
        exercised += 1
        assert matches, (
            f"{name} pattern matched none of {len(candidates)} candidate trace lines -- "
            f"the engine's log format changed. Example: {candidates[0]!r}"
        )
    assert exercised, "no trace pattern was exercised at all; the test proves nothing"


def test_named_groups_extract_the_join_key() -> None:
    """The item uid is what joins trace to ledger; a rename would break it."""
    *_, sim = _sim()
    line = next(line for line in sim.trace if tape_mod._RE_SICK_CALL.match(line))
    m = tape_mod._RE_SICK_CALL.match(line)
    assert m is not None
    assert m["item"].isdigit()
    assert m["t"].isdigit()
    assert m["crew"]


# ------------------------------------------------------------- reconciliation
def test_measured_cost_equals_the_scoreboard_figure() -> None:
    """The tape and the scoreboard must not disagree about the same run.

    `measured_cost` is the measurement-window total, which is exactly what
    `des.measured_window_costs` feeds into E[C].
    """
    cfg, _costs, sim = _sim()
    expected = des.measured_window_costs(cfg, [sim])[0]
    assert _tape()["totals"]["measured_cost"] == expected


def test_full_ledger_total_is_reported_separately_from_the_measured_one() -> None:
    """Both numbers exist, and they are not the same number.

    Warm-up costs are real and shown on the tape but excluded from E[C]; if
    these ever collapsed into one figure the dimmed rows would be lying.
    """
    t = _tape()
    assert t["totals"]["cost"] > t["totals"]["measured_cost"]


# ---------------------------------------------------------------- the tape
def test_events_are_chronological() -> None:
    t = _tape()
    times = [e["t"] for e in t["events"]]
    assert times == sorted(times)


def test_reserve_staffing_is_background_not_an_event() -> None:
    """264 identical daily accruals would bury the ~20 real decisions.

    Excluded from the tape, still counted in the cost total -- both halves
    asserted, because dropping it from the total would understate the run.
    """
    t = _tape()
    assert not [e for e in t["events"] if e["kind"] == "RESERVE_STAFFING"]
    assert t["background"]["rows"] > 0
    assert t["background"]["total"] > 0
    assert t["background"]["total"] <= t["totals"]["cost"]


def test_consequences_are_nested_under_their_cause() -> None:
    """The indent is the causal chain, not decoration."""
    t = _tape()
    descendants = [e for e in t["events"] if e["depth"] > 0]
    if not descendants:
        pytest.skip(
            "no cascaded events in this scenario -- since the 2026-08-12 fixes ~100% of "
            "drafts are tier 1, so nothing breaks a future pairing (audit OPEN-6). The "
            "nesting ALGORITHM is covered by test_depth_walks_the_parent_chain."
        )
    for e in descendants:
        assert e["root"] != e["item"], "a descendant must point at a different parent"


def test_depth_walks_the_parent_chain() -> None:
    """A three-link chain must read as depth 2, not depth 1.

    The engine currently produces chains one level deep, so this asserts the
    ALGORITHM on a constructed chain -- otherwise the code would look correct
    while only ever having been exercised on the trivial case.
    """
    parent = {3: 2, 2: 1}
    assert tape_mod._depth_of(1, parent) == 0
    assert tape_mod._depth_of(2, parent) == 1
    assert tape_mod._depth_of(3, parent) == 2


def test_depth_survives_a_cycle() -> None:
    """A cycle in the data must not hang the request."""
    assert tape_mod._depth_of(1, {1: 2, 2: 1}) == 1


def test_clock_formats_a_simulated_minute() -> None:
    assert tape_mod._clock(0) == (0, "00:00")
    assert tape_mod._clock(1440) == (1, "00:00")
    assert tape_mod._clock(1440 * 26 + 9 * 60 + 23) == (26, "09:23")


def test_draft_tiers_are_labelled_by_tier() -> None:
    assert tape_mod._label("DRAFT_TIER1") == "drafted (tier 1)"
    assert tape_mod._label("DRAFT_TIER5") == "drafted (tier 5)"
    assert "reserve" in tape_mod._label("RESERVE_UTILIZATION")


def test_rerunning_produces_an_identical_tape() -> None:
    """The property that makes on-demand re-runs safe to cache."""
    assert _tape()["events"] == _tape()["events"]
