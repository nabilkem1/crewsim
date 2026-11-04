"""The CRN pairing guarantee, asserted against real scenarios.

`reporting/paired.py` subtracts two policies' cost vectors element-wise and
reports a t-statistic on the difference. That is only a PAIRED comparison if
scenario i presents the same arrival stream to both sides. `run_policy_crn`'s
docstring has always claimed it does; nothing checked, and it did not.

Measured before the fix, on scenario 0: R4 saw 86 sick-call arrivals and R10
saw 82, sharing only the first 44. Two couplings caused it, and only one was a
defect:

  * `sick_call_source` drew time-of-day and duration from `self.rng` -- the
    same Generator policy-dependent recovery draws from (eligibility,
    cross-base positioning). SimPy interleaves those with the arrival
    generator, so the arrival stream depended on how much work the policy had
    already done. THAT is what these tests pin.

  * which crew falls sick is drawn from those with a PAIRING in the window,
    and reserves are carved out of the roster with their pairings stripped
    (roster_loader) -- so the candidate pool is genuinely policy-dependent.
    That is a modelling property, not a bug, and is deliberately NOT asserted
    away here. See test_crew_selection_may_still_differ_by_policy.
"""

from __future__ import annotations

import re

from crewsim import config
from crewsim.engine import crn, des
from crewsim.engine.policy import load_policy

_SICK_CALL = re.compile(r"^\[t=(\d+)\] SICK_CALL: (\S+) ->")


def _run(policy_name: str, master_seed: str = "master", scenario_id: int = 0):
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.policy_path(policy_name))
    return des.run_scenario(
        cfg, costs, policy, scenario_id=scenario_id, master_seed=master_seed,
        n_scenarios=1, trace=True,
    )


def _arrival_times(sim) -> list[int]:
    """Distinct simulated minutes at which a sick call was logged.

    Distinct, because one absence can break several pairings and log a line
    per resulting item -- the arrival is the event, not the item.
    """
    return sorted({int(m.group(1)) for line in sim.trace if (m := _SICK_CALL.match(line))})


def _arrivals(sim) -> list[tuple[int, str]]:
    return [
        (int(m.group(1)), m.group(2)) for line in sim.trace if (m := _SICK_CALL.match(line))
    ]


def test_arrival_times_are_identical_across_policies() -> None:
    """The property the paired t-test depends on.

    Three policies with very different reserve counts (4, 10, 14) must see the
    same scenario -- same absences, at the same minutes.
    """
    times = {name: _arrival_times(_run(name)) for name in ("R4", "R10", "R14")}

    assert times["R4"] == times["R10"] == times["R14"], (
        "policies saw different arrival streams for the same scenario -- the "
        "paired comparison in reporting/paired.py is not paired:\n"
        + "\n".join(f"  {n}: {len(t)} arrivals" for n, t in times.items())
    )
    assert times["R4"], "scenario produced no arrivals at all; this test proves nothing"


def test_arrival_stream_is_derivable_without_running_the_simulation() -> None:
    """Arrivals depend only on (scenario stream, day, index).

    Reconstructing them outside the engine and finding every logged arrival in
    that set is what shows the stream is a pure function of the CRN key rather
    than of anything the policy did. It is also the property the proposed
    scenario-fingerprint view would rely on.
    """
    cfg = config.load()
    streams = crn.generate_streams("master", 1)
    counts = des._load_daily_sick_calls(cfg, cfg.scope.season, "master", 1, 0)

    expected = set()
    for day, count in enumerate(counts):
        for i in range(count):
            rng = crn.event_rng(streams[0], f"sick_call:{day}:{i}")
            expected.add(round(day * 1440.0 + float(rng.uniform(0, 1440.0))))

    for name in ("R4", "R14"):
        logged = set(_arrival_times(_run(name)))
        assert logged <= expected, (
            f"{name} logged arrivals at times the CRN key cannot produce: "
            f"{sorted(logged - expected)[:5]}"
        )
        assert logged, f"{name} logged no arrivals"


def test_intraday_order(monkeypatch) -> None:
    """IMP-101: arrivals are handled at their own drawn time, in time order.

    Before the fix a day's arrivals were processed in index order; whenever a
    later index drew an earlier time-of-day the timeout was skipped and the
    arrival was handled at the previous arrival's clock time while carrying
    its own earlier timestamp. Recording the `current_time` each arrival is
    applied with, alongside the simulation clock at that moment, pins both
    halves: the sequence is non-decreasing, and every arrival is applied at
    exactly env.now.
    """
    seen: list[tuple[float, float]] = []
    real_apply = des.apply_sick_call
    sims: list[des.Simulation] = []
    real_init = des.Simulation.__init__

    def recording_init(self, *args, **kwargs):
        real_init(self, *args, **kwargs)
        sims.append(self)

    def recording_apply(cfg, crew, current_time, *args, **kwargs):
        seen.append((current_time, sims[-1].env.now))
        return real_apply(cfg, crew, current_time, *args, **kwargs)

    monkeypatch.setattr(des.Simulation, "__init__", recording_init)
    monkeypatch.setattr(des, "apply_sick_call", recording_apply)
    _run("R10")

    times = [t for t, _ in seen]
    assert len(times) > 1, "scenario produced too few arrivals; this test proves nothing"
    assert times == sorted(times), "sick calls were processed out of time order"
    late = [(t, now) for t, now in seen if abs(t - now) > 1e-9]
    assert not late, f"arrivals applied at a clock time other than their own: {late[:5]}"


def test_master_seed_reaches_crew_selection() -> None:
    """Changing the master seed must change the scenario, not just its timing.

    The stdlib seed used to be keyed on (scenario_id, "sick_call", day, i) with
    no master seed in it, so WHICH crew fell sick was identical across every
    master seed -- two "independent" runs shared their casualty list.
    """
    a = _arrivals(_run("R10", master_seed="master"))
    b = _arrivals(_run("R10", master_seed="a-different-seed"))
    assert a != b, "master_seed had no effect on the arrival stream"


def test_same_policy_and_seed_replays_identically() -> None:
    """The control. Without this, the tests above could pass on noise."""
    assert _arrivals(_run("R10")) == _arrivals(_run("R10"))


def test_crew_selection_may_still_differ_by_policy() -> None:
    """Documents the residual, deliberate policy dependence.

    Reserves are carved out of the roster and have their PAIRING blocks
    stripped, so they cannot be selected for a sick call -- the candidate pool
    really is smaller under a higher R. Making the CASUALTY policy-independent
    would mean modelling "a reserve calls in sick", which the engine does not
    do and which is a modelling decision, not a reproducibility fix.

    This test asserts the arrival TIMES still line up even where the crew does
    not, so that the day someone implements reserve sickness, the failure here
    is a deliberate signal rather than a surprise.
    """
    a, b = _arrivals(_run("R4")), _arrivals(_run("R14"))
    assert _arrival_times(_run("R4")) == _arrival_times(_run("R14"))
    # Not asserting a != b: with a small corpus the same crew can legitimately
    # be picked throughout. The point is that differing crew is ALLOWED while
    # differing times is not.
    assert isinstance(a, list) and isinstance(b, list)
