"""Gate V1 -- degeneracy: three configurations whose answers are computable on
paper (S1a-10, spec Sec9.2).

Every configuration below runs the REAL des.run_scenario against the REAL
corpus and reads the REAL resulting ledger. The "computed" side of each verdict
is measured from that ledger, never asserted into existence -- which is the
entire point of this gate: if the engine fabricates a cost, the fabricated cost
has to show up here.

(This replaces a version whose test asserted `0.0 == 0.0` on a local variable
and whose CLI printed `Computed: $0.00  [PASS]` as a string literal. Neither
constructed a Simulation, so neither could ever fail -- and a passing V1 is
precisely the artefact someone would cite to claim the engine does not
fabricate phantom costs.)
"""
from __future__ import annotations

from typing import Any

from .. import config
from ..engine import des
from ..engine.ledger import LedgerRow
from ..engine.policy import Policy, ReserveConfig, Stage1Config
from ..engine.roster_loader import load_rosters

# Ledger categories that only exist because a reserve pool exists. Configuration
# 3's whole claim is that these are ABSENT, so the set is named once here rather
# than being re-typed at the call site.
RESERVE_CATEGORIES = ("RESERVE_STAFFING", "RESERVE_UTILIZATION")


def scoped_headcount(cfg: config.BaseConfig) -> int:
    """Active crew inside cfg.scope -- the size "everyone is on reserve" means.

    Loaded with policy=None so no carve-out has happened yet: this is the
    denominator the configuration-2 policy has to meet or exceed.
    """
    active, _ = load_rosters(
        cfg, base=cfg.scope.base, fleet=cfg.scope.fleet, position=cfg.scope.position
    )
    return len(active)


def policy_with_reserve_count(base_policy: Policy, n_reserves: int, policy_id: str) -> Policy:
    """`base_policy` with its stage-1 reserve target replaced by exactly `n_reserves`.

    roster_loader.load_rosters carves out max(short_call + long_call) crew per
    (base, fleet, position) group, so one all-short-call entry at the scope's
    own key sets the pool size exactly, and an empty reserve list sets it to
    zero. Everything else -- costs_file, season, mode -- is inherited from a
    real policy file, so a degenerate run is priced off exactly the same cost
    table as a normal one. A hand-built Policy would let this gate drift away
    from the tariffs it is supposed to be checking.

    The one stage-2 exception is `allow_cross_base_reserve`, pinned False for
    the same reason `run_v1_gate` pins `displaced_flying`: this gate asks
    whether the engine fabricates cost when the RESERVE ESTABLISHMENT is
    degenerate, and R is the in-scope establishment. S1c-07 made cross-base
    dispatch real, so a policy carving zero reserves could still be covered by
    Toronto's -- correctly booking RESERVE_UTILIZATION and defeating the "zero
    reserves, therefore no reserve cost" premise with a cost that is genuinely
    justified. Real behaviour, wrong question: it belongs in a run, not in this
    gate's degenerate configurations.
    """
    if n_reserves > 0:
        template = base_policy.stage1.reserves[0]
        reserves = [
            ReserveConfig(
                base=template.base, fleet=template.fleet, position=template.position,
                dow=list(template.dow), short_call=n_reserves, long_call=0,
            )
        ]
    else:
        reserves = []
    return base_policy.model_copy(
        update={
            "policy_id": policy_id,
            "stage1": Stage1Config(reserves=reserves),
            "stage2": base_policy.stage2.model_copy(update={"allow_cross_base_reserve": False}),
        }
    )


def _category_totals(rows: list[LedgerRow]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in rows:
        totals[row.category] = totals.get(row.category, 0.0) + row.amount
    return totals


def _money(amount: float) -> str:
    return f"${amount:,.2f}"


def run_v1_gate(
    cfg: config.BaseConfig,
    costs: Any,
    base_policy: Policy,
    master_seed: str = "master",
    scenario_id: int = 0,
) -> dict[str, Any]:
    """Runs all three degeneracy configurations and returns their verdicts.

    Returns {"pass": bool, "configurations": [{name, expected, computed, pass,
    detail}, ...]} -- `expected` and `computed` are formatted strings so the
    CLI can print them side by side, which is what this story's acceptance
    criterion actually asks for.
    """
    headcount = scoped_headcount(cfg)
    zero_arrivals = [0] * cfg.horizon.horizon_days
    # Pin displaced_flying for all three configurations rather than inheriting
    # base.yaml. This gate asks one question -- does the engine fabricate cost
    # in a degenerate case -- and reserve bidders' displaced flying (S1b-02 AC2)
    # is a real, correctly-booked cost that would drown it out: with everyone on
    # reserve and displaced_flying=open_time, ALL the flying becomes open time,
    # so configuration 2 books utilisation and cancellations and its "staffing
    # only" claim stops being about staffing at all. Isolating it here keeps the
    # gate deterministic regardless of how base.yaml is set; configurations 1
    # and 3 carve out zero reserves, so for them this is a no-op either way.
    cfg = cfg.model_copy(
        update={"population": cfg.population.model_copy(update={"displaced_flying": "absorb"})}
    )
    configurations: list[dict[str, Any]] = []

    # -- 1: no reserves, no sick calls -> nothing to pay for at all ----------
    no_reserves = policy_with_reserve_count(base_policy, 0, "V1-zero-reserves")
    sim1 = des.run_scenario(
        cfg, costs, no_reserves, scenario_id=scenario_id, master_seed=master_seed,
        daily_sick_calls=zero_arrivals,
    )
    total1 = sim1.ledger.total_cost()
    configurations.append({
        "name": "0 reserves, 0 sick calls",
        "expected": _money(0.0),
        "computed": _money(total1),
        "pass": total1 == 0.0 and not sim1.ledger.rows,
        "detail": (
            f"{len(sim1.reserves)} reserves, {len(sim1.roster)} line holders, "
            f"{sum(zero_arrivals)} arrivals -> {len(sim1.ledger.rows)} ledger rows"
        ),
        "categories": _category_totals(sim1.ledger.rows),
    })

    # -- 2: everyone on reserve -> staffing, and nothing else ----------------
    # Reserves carry a real reserve line with its PAIRING blocks stripped
    # (roster_loader), so with nobody flying there is no pairing for a sick
    # call to break: no open-time items, therefore no drafts and no
    # cancellations. Real calibrated arrivals, not zeroed ones -- the claim is
    # that arrivals produce nothing to recover, not that none arrive.
    all_reserve = policy_with_reserve_count(base_policy, headcount, "V1-all-reserve")
    sim2 = des.run_scenario(
        cfg, costs, all_reserve, scenario_id=scenario_id, master_seed=master_seed,
    )
    totals2 = _category_totals(sim2.ledger.rows)
    non_staffing = sorted(c for c in totals2 if c != "RESERVE_STAFFING")
    staffing2 = totals2.get("RESERVE_STAFFING", 0.0)
    # Counted from rows, never inferred by dividing a dollar total by a unit
    # price -- that would silently misreport the moment a category's per-row
    # amount stops being constant, and inferring counts from money is the exact
    # habit this gate was rewritten to stop.
    n_cancellations = sum(1 for r in sim2.ledger.rows if r.category == "CANCELLATION")
    # sim2._uid is the number of OpenTimeItems ever created. Reporting it keeps
    # this verdict honest about WHY there are no drafts: with nobody flying a
    # line there is no pairing for a sick call to break, so the draft selector
    # is never reached. "0 drafts" alone would read as the selector having been
    # exercised and having declined -- a stronger claim than this run supports.
    n_items = sim2._uid
    staffing_rows = [r for r in sim2.ledger.rows if r.category == "RESERVE_STAFFING"]
    # Per-rate reserve-day counts, so the staffing total can be reconstructed
    # on paper (and asserted in the test) rather than merely checked non-zero.
    staffing_by_rate: dict[float, int] = {}
    for r in staffing_rows:
        staffing_by_rate[r.amount] = staffing_by_rate.get(r.amount, 0) + 1
    configurations.append({
        "name": "everyone on reserve",
        "expected": "0 drafts, 0 cancellations, RESERVE_STAFFING only",
        "computed": (
            f"{sim2.n_drafts} drafts, {n_cancellations} cancellations, "
            f"categories={sorted(totals2) or ['(none)']}"
        ),
        "pass": (sim2.n_drafts == 0 and n_cancellations == 0
                 and not non_staffing and staffing2 > 0.0),
        "detail": (
            f"{len(sim2.reserves)} reserves, {len(sim2.roster)} line holders, "
            f"{n_items} open-time item(s) created (no line flying -> no pairing to break, "
            f"so the draft selector is never reached); staffing {_money(staffing2)} over "
            f"{len(staffing_rows)} reserve-day(s) in a {cfg.horizon.horizon_days}-day horizon "
             "(" + " + ".join(f"{n} @ {_money(rate)}" for rate, n in sorted(staffing_by_rate.items())) + ")"
        ),
        "categories": totals2,
        "staffing_reserve_days": len(staffing_rows),
        "staffing_by_rate": staffing_by_rate,
    })

    # -- 3: no reserves, normal sick calls -> reserve categories never appear -
    sim3 = des.run_scenario(
        cfg, costs, no_reserves, scenario_id=scenario_id, master_seed=master_seed,
    )
    totals3 = _category_totals(sim3.ledger.rows)
    present = sorted(c for c in RESERVE_CATEGORIES if c in totals3)
    configurations.append({
        "name": "0 reserves, normal sick calls",
        "expected": f"{list(RESERVE_CATEGORIES)} absent from the ledger",
        "computed": f"present: {present or ['(none)']}",
        # A ledger with no rows at all would satisfy "absent" vacuously, so
        # require that this configuration actually produced cost -- otherwise
        # a broken arrival path would read as a PASS.
        "pass": not present and bool(sim3.ledger.rows),
        "detail": (
            f"{len(sim3.reserves)} reserves, {len(sim3.roster)} line holders, "
            f"{sim3.n_drafts} drafts, {len(sim3.ledger.rows)} ledger rows totalling "
            f"{_money(sim3.ledger.total_cost())}"
        ),
        "categories": totals3,
    })

    return {
        "pass": all(c["pass"] for c in configurations),
        "headcount": headcount,
        "base_policy_id": base_policy.policy_id,
        "configurations": configurations,
    }


def print_v1_report(result: dict[str, Any]) -> None:
    print(
        f"Gate V1: The Extremes (Degeneracy Check) -- {result['headcount']} active crew in scope, "
        f"cost table from {result['base_policy_id']}\n"
    )
    for i, c in enumerate(result["configurations"], start=1):
        verdict = "PASS" if c["pass"] else "FAIL"
        print(f"Configuration {i}: {c['name']}")
        print(f"  Expected: {c['expected']}")
        print(f"  Computed: {c['computed']}  [{verdict}]")
        print(f"  Measured: {c['detail']}")
        if c["categories"]:
            for category, amount in sorted(c["categories"].items()):
                print(f"    {category:<22} {_money(amount)}")
        print()
    print("Verdict: [PASS] no configuration fabricated a cost." if result["pass"]
          else "Verdict: [FAIL] a degenerate configuration produced cost it cannot justify.")
