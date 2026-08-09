import datetime

import polars as pl

from crewsim import config
from crewsim.data import loaders
from crewsim.engine.policy import load_policy
from crewsim.gates.v6_backtest import (
    MOCK_DATA_CAVEAT,
    SPEC_BIAS_DECOMPOSITION,
    compute_actual_cost,
    month_bounds,
    print_v6_report,
    run_v6_gate,
)


def test_month_bounds():
    assert month_bounds("2026-01") == (datetime.date(2026, 1, 1), datetime.date(2026, 2, 1))
    assert month_bounds("2026-12") == (datetime.date(2026, 12, 1), datetime.date(2027, 1, 1))


def test_compute_actual_cost_matches_manual_d7_sum():
    """Cross-check against an independent manual aggregation over the same
    scope-filtered D7 rows, for a real period known to have data."""
    cfg = config.load()
    period = "2026-01"

    d1 = loaders.load_dataset(cfg, "d1_crew_master").filter(
        (pl.col("base") == cfg.scope.base) & (pl.col("fleet") == cfg.scope.fleet)
        & (pl.col("position") == cfg.scope.position)
    )
    scope_ids = set(d1.get_column("crew_id"))
    d7 = loaders.load_dataset(cfg, "d7_pay_register").filter(
        (pl.col("pay_period") == period) & (pl.col("crew_id").is_in(list(scope_ids)))
    )
    expected = {
        "RESERVE_GTE": float(d7.filter(pl.col("pay_code") == "RESERVE_GTE").get_column("amount_cad").sum() or 0.0),
        "RESERVE_UTIL": float(d7.filter(pl.col("pay_code") == "RESERVE_UTIL").get_column("amount_cad").sum() or 0.0),
        "DRAFT_PREM": float(d7.filter(pl.col("pay_code") == "DRAFT_PREM").get_column("amount_cad").sum() or 0.0),
    }

    result = compute_actual_cost(cfg, period)
    for code, amount in expected.items():
        assert result["by_pay_code"].get(code, 0.0) == amount
    assert result["comparable_total"] == sum(expected.values())
    assert result["n_crew"] == len(scope_ids)


def test_run_v6_gate_produces_a_real_comparable_gap():
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")

    result = run_v6_gate(cfg, costs, policy, "2026-01")
    assert result["period"] == "2026-01"
    assert result["actual"]["comparable_total"] >= 0.0
    assert result["simulated"]["comparable_total"] >= 0.0
    assert result["gap"] == result["simulated"]["comparable_total"] - result["actual"]["comparable_total"]
    # A real disruption month must produce SOME simulated draft/reserve
    # cost, or this comparison is vacuous.
    assert result["simulated"]["comparable_total"] > 0.0


def test_draft_costs_are_not_silently_dropped_from_the_comparison():
    """Regression test: DRAFT_TIER{n} (des.py's dynamic per-tier category
    name) must map to D7's single DRAFT_PREM pay_code -- an earlier draft
    of this gate matched sim categories against a flat dict that had no
    DRAFT_TIER* key at all, silently excluding every draft cost from BOTH
    the comparable total AND the excluded-costs breakdown."""
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")

    result = run_v6_gate(cfg, costs, policy, "2026-01")
    sim_by_category = result["simulated"]["by_category"]
    draft_categories = [c for c in sim_by_category if c.startswith("DRAFT_TIER")]
    assert draft_categories, "a real disruption month must produce at least one draft"

    draft_total = sum(sim_by_category[c] for c in draft_categories)
    reserve_total = sum(
        sim_by_category.get(c, 0.0) for c in ("RESERVE_STAFFING", "RESERVE_UTILIZATION")
    )
    assert result["simulated"]["comparable_total"] == draft_total + reserve_total


def test_excluded_costs_are_reported_not_hidden():
    """CANCELLATION/TERMINAL_PENALTY (simulated, no payroll counterpart) and
    D10 positioning invoices (actual, not modelled by the engine) must be
    visible in the result, not silently dropped from both sides."""
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")

    result = run_v6_gate(cfg, costs, policy, "2026-01")
    assert result["simulated"]["excluded_total"] > 0.0, (
        "a real disruption month must produce at least one CANCELLATION/TERMINAL_PENALTY"
    )
    assert "positioning_total" in result["actual"]


def test_print_v6_report_labels_mock_data_and_shows_bias_decomposition(capsys):
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")

    result = run_v6_gate(cfg, costs, policy, "2026-01")
    print_v6_report(result)
    out = capsys.readouterr().out

    assert out.count(MOCK_DATA_CAVEAT) == 2, "the caveat must appear at both the top and bottom"
    for row in SPEC_BIAS_DECOMPOSITION:
        assert row["mechanism"] in out
        assert row["direction"] in out
