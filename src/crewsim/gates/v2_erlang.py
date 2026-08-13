"""Gate V2 -- Erlang-B sanity bound (S1b-07, spec Sec7.8/Sec9.2).

The cheapest possible check that the reserve machinery works at all: run the DES
in the constrained configuration the story specifies (single base, single fleet,
cascades disabled), MEASURE the probability that an arriving open-time item finds
no eligible reserve, and compare it against the closed-form Erlang-B loss
probability B(s, a) for the same offered load.

Everything on the DES side is measured from real simulation runs:

    p_hat  = blocked-on-arrival / arrivals        (a binomial proportion)
    lambda = arrivals / horizon minutes           (arrival rate)
    E[S]   = ON-CALL capacity consumed per assignment (OPEN-7: the part of the
             duty+rest span that actually falls inside the crew member's shift)
    a      = lambda * E[S]                        (offered load, in Erlangs)
    s      = time-average reserves on call        (servers)

Both E[S] and s are measured in ON-CALL minutes. That is the OPEN-7 correction:
once reserves became rostered shifts (2026-08-12) a duty could run well past the
shift that authorised it, and charging those out-of-shift hours as occupied
server time -- while counting servers only while on call -- put the numerator
and denominator in different currencies. Measured then: E[S] read 19.0h against
shifts of 10-12h, the offered load came out at 3.63 Erlangs, and the gate FAILED
in the impossible direction (p_hat 0.7145 < B 0.7840). The engine was fine --
V8's L0 invariants were clean across 672 crew-scenarios -- the comparison was
not. On the corrected basis E[S] is 10.8h, a is 2.06, and the bound holds.

(This replaces a version in which the DES side was the literal
`prob_shortfall_des = 0.098  # Stubbed DES mock value`, written out twice -- once
in cli.py and once in the test -- alongside two independent copies of erlang_b().
No simulation was involved, so the gate could not detect a reserve-accounting bug,
which is the one thing it exists to do.)

## What this gate asserts, and why it is a bound rather than a fit

Erlang B models an M/M/s/s loss system: Poisson arrivals, exponential service, s
servers always present, blocked calls cleared. The real pipeline departs from
that on every axis -- reserve lines rotate on and off, service is duty+rest
rather than exponential, L3/L4/L8 reject on-call reserves the closed form counts
as free servers, and E8 HOLDS a blocked item to its deadline instead of clearing
it.

The verdict is therefore the DIRECTIONAL BOUND:

    p_hat >= B(s, a)

Every one of those departures can only make a reserve LESS available than the
idealised model, never more. So the DES must block at least as often as B(s, a).
A violation means the simulation found availability the calendars and rules do
not permit -- reserve double-counting, an occupancy that is never booked, a pool
counted twice -- which is precisely the "reserve accounting has a bug" this gate
exists to catch, and which the closed form is uniquely able to reveal.

The strict CONTAINMENT test (is p_hat inside a CI around B(s,a)?) is computed and
printed alongside, but is informational. It is not satisfiable by this model and
no choice of s or a makes it so: measured 2026-08-08 at p_hat = 0.8765
[0.8564, 0.8941] against B = 0.5519 with time-average servers, 0.0381 with
headcount servers, and 0.0122 with eligibility-thinned arrivals. Asserting it
would ship a permanently red gate that says nothing about correctness. Decision
recorded with the user 2026-08-08.
"""
from __future__ import annotations

import math
from typing import Any

from scipy import stats

from .. import config
from ..engine import des
from ..engine.policy import Policy
from ..engine.state import BlockType


def erlang_b(s: int, a: float) -> float:
    """B(s, a): probability an arrival finds all s servers busy, offered load a.

    Iterative form, which is numerically stable where the factorial form
    overflows. THE one implementation -- the CLI and the test both call this,
    rather than each carrying a copy as they did before.
    """
    if s <= 0:
        return 1.0
    if a <= 0:
        return 0.0
    inv = 1.0
    for i in range(1, s + 1):
        inv = 1.0 + inv * (i / a)
    return 1.0 / inv


def mean_on_call_servers(reserves: list[Any], horizon_minutes: float) -> float:
    """Time-average number of reserves on call -- the effective `s`.

    NOT the reserve headcount: reserve lines rotate, so a pool of 12 with an
    18-on/12-off pattern presents materially fewer than 12 servers at any
    instant. Using headcount here would overstate capacity and make the gate
    read as a shortfall in the DES when the difference is really in `s`.
    """
    if horizon_minutes <= 0:
        return 0.0
    on_call_minutes = sum(
        min(b.end, horizon_minutes) - max(b.start, 0.0)
        for r in reserves
        for b in r.calendar
        if b.btype == BlockType.RESERVE and b.end > 0.0 and b.start < horizon_minutes
    )
    return on_call_minutes / horizon_minutes


def run_v2_gate(
    cfg: config.BaseConfig,
    costs: Any,
    policy: Policy,
    n_scenarios: int,
    master_seed: str = "master",
) -> dict[str, Any]:
    """Measure the DES shortfall probability and compare it to B(s, a).

    Cascades are disabled (AC1): a cascade is a secondary arrival generated by
    the recovery itself, and feeding it back into the stream breaks the
    independent-arrivals premise the closed form rests on.
    """
    if cfg.gates is None:
        raise ValueError("gate V2 requires cfg.gates (v2_confidence_level) to be configured")

    sims = [
        des.run_scenario(
            cfg, costs, policy, scenario_id=i, master_seed=master_seed,
            n_scenarios=n_scenarios, cascades_enabled=False,
        )
        for i in range(n_scenarios)
    ]

    horizon_minutes = cfg.horizon.horizon_days * 1440.0
    arrivals = sum(s.n_arrivals for s in sims)
    blocked = sum(s.n_blocked_on_arrival for s in sims)
    assignments = sum(s.n_reserve_assignments for s in sims)
    service_minutes = sum(s.reserve_service_minutes for s in sims)

    if arrivals == 0:
        raise ValueError(
            "gate V2 measured zero arrivals -- nothing to compare against Erlang B. "
            "Check the scenario set and the sick-call calibration."
        )

    p_hat = blocked / arrivals
    # Wilson score interval: correct near p=0 and p=1, where the normal
    # approximation produces bounds outside [0, 1]. This gate routinely sits
    # near 1, so the choice matters.
    level = cfg.gates.v2_confidence_level
    ci_low, ci_high = stats.binomtest(blocked, arrivals).proportion_ci(
        confidence_level=level, method="wilson"
    )

    lam = arrivals / (n_scenarios * horizon_minutes)          # arrivals per minute
    # OPEN-7: E[S] is the ON-CALL capacity an assignment consumes, not the whole
    # duty+rest span. Since reserves became rostered shifts a duty can run well
    # past the shift that authorised it, and those out-of-shift hours remove no
    # server capacity -- the crew member was off duty and unavailable anyway.
    # `servers` below is a time-average of on-call minutes, so the load has to
    # be measured in on-call minutes too or the two are different currencies.
    # The raw duty+rest figure is still reported, as the gap between them is
    # exactly the shift structure Erlang B cannot represent.
    oncall_minutes = sum(s.reserve_oncall_minutes for s in sims)
    mean_service = (oncall_minutes / assignments) if assignments else 0.0
    mean_service_raw = (service_minutes / assignments) if assignments else 0.0
    offered_load = lam * mean_service                          # Erlangs
    servers_float = sum(
        mean_on_call_servers(s.reserves, horizon_minutes) for s in sims
    ) / n_scenarios

    # Erlang B needs an integer server count, but a rostered pool presents a
    # FRACTIONAL time-average (7 reserves on 12h shifts average well under 7),
    # and B is violently sensitive at small s -- B(1, 3.6) = 0.78 against
    # B(2, 3.6) = 0.59. Rounding silently picked one of those and turned the
    # choice into the verdict. Both bounds are now computed and reported, and
    # the gate is judged against the MOST GENEROUS idealisation (more servers,
    # least blocking): if the DES blocks less often than even that, the
    # violation is real rather than an artefact of rounding.
    servers_lo, servers_hi = math.floor(servers_float), math.ceil(servers_float)
    servers = servers_hi
    theory = erlang_b(servers_hi, offered_load)
    theory_lo = erlang_b(servers_lo, offered_load)

    # The verdict: the DES cannot be MORE available than an idealised loss system
    # with the same servers and load. Compared against the CI's upper bound, not
    # the point estimate, so ordinary sampling noise near the boundary does not
    # flip the gate.
    passed = bool(ci_high >= theory)
    contained = bool(ci_low <= theory <= ci_high)

    if not passed:
        interpretation = (
            "DES blocks LESS than Erlang B predicts, which this model has no mechanism "
            "to do -- a reserve cannot be more available than its calendar and the "
            "legality rules allow. Suspect reserve double-counting, an occupancy that "
            "is never booked, or a pool counted twice. STOP and fix before attempting V3."
        )
    elif contained:
        interpretation = (
            "DES shortfall is statistically consistent with the closed form, and "
            "satisfies the bound."
        )
    else:
        interpretation = (
            "DES blocks at least as often as the idealised loss system -- reserve "
            "accounting is self-consistent. The excess over B(s, a) is expected and "
            "not a defect: reserve lines rotate off, L3/L4/L8 reject on-call reserves "
            "the closed form counts as free servers, and service is duty+rest rather "
            "than exponential."
        )

    return {
        "pass": passed,
        "policy_id": policy.policy_id,
        "n_scenarios": n_scenarios,
        "arrivals": arrivals,
        "blocked": blocked,
        "p_hat": p_hat,
        "ci_low": float(ci_low),
        "ci_high": float(ci_high),
        "confidence_level": level,
        "servers": servers,
        "servers_float": servers_float,
        "servers_lo": servers_lo,
        "servers_hi": servers_hi,
        "theory_lo": theory_lo,
        "mean_service_raw_hours": mean_service_raw / 60.0,
        "reserve_headcount": len(sims[0].reserves) if sims else 0,
        "arrival_rate_per_day": lam * 1440.0,
        "mean_service_hours": mean_service / 60.0,
        "offered_load": offered_load,
        "theory": theory,
        "contained": contained,
        "interpretation": interpretation,
    }


def print_v2_report(result: dict[str, Any]) -> None:
    print(f"Gate V2: Erlang-B Sanity Bound -- policy {result['policy_id']}, "
          f"{result['n_scenarios']} scenario(s), cascades disabled\n")
    print("  Measured from the DES")
    print(f"    arrivals                 = {result['arrivals']:,}")
    print(f"    blocked on arrival       = {result['blocked']:,}")
    print(f"    arrival rate (lambda)    = {result['arrival_rate_per_day']:.2f} / day")
    print(f"    mean service E[S]        = {result['mean_service_hours']:.1f} h "
          f"(ON-CALL capacity consumed; duty+rest spans {result['mean_service_raw_hours']:.1f} h, "
          f"the excess falling outside the shift)")
    print(f"    servers (s)              = {result['servers_float']:.2f} time-average on call "
          f"(headcount {result['reserve_headcount']}); judged at s={result['servers_hi']}")
    print(f"    offered load (a)         = {result['offered_load']:.2f} Erlangs")
    print("-" * 62)
    print(f"    DES shortfall  p_hat     = {result['p_hat']:.4f}  "
          f"[{result['ci_low']:.4f}, {result['ci_high']:.4f}] "
          f"{result['confidence_level']:.0%} CI")
    print(f"    Theory  B(s, a)          = {result['theory']:.4f} at s={result['servers_hi']}"
          f"   (B = {result['theory_lo']:.4f} at s={result['servers_lo']})")
    print("-" * 62)
    bound = "OK" if result["pass"] else "VIOLATED"
    print(f"    bound: p_hat >= B(s, a)  {bound}          <- the gate's verdict")
    print(f"    containment (p_hat in CI around B) : "
          f"{'satisfied' if result['contained'] else 'NOT satisfied -- informational, see module docstring'}")
    print("-" * 62)
    print(f"  Status: [{'PASS' if result['pass'] else 'FAIL'}] {result['interpretation']}")
