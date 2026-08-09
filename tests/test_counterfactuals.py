import pytest
from pydantic import ValidationError

from crewsim import config
from crewsim.engine import des
from crewsim.engine.counterfactuals import select_myopic_total_cost
from crewsim.engine.policy import Policy, load_policy
from crewsim.reporting.counterfactual import DRAFT_MODES, run_counterfactual_comparison


def test_draft_mode_rejected_by_policy_schema():
    """S1e-05's own AC: 'structurally impossible to select either as a
    candidate policy'. A policy YAML carrying a counterfactual flag must be
    REJECTED, not silently ignored -- Stage2Config's extra="forbid" (added
    this story) makes an unknown key a loud validation error rather than a
    landmine that quietly does nothing."""
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")
    data = policy.model_dump(mode="json")

    for bad_key in ("junior_first", "myopic_total_cost", "draft_mode"):
        data["stage2"][bad_key] = True
        with pytest.raises(ValidationError):
            Policy(**data)
        del data["stage2"][bad_key]


def test_junior_first_selects_a_different_candidate_within_tier():
    """The already-existing junior_first flag in drafting.py, now actually
    wired through Simulation/run_scenario -- must select a genuinely
    different crew member than mandated (senior-first) when a tier has more
    than one candidate, not merely accept the flag and ignore it."""
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")

    sim_mandated = des.run_scenario(cfg, costs, policy, scenario_id=0, master_seed="cf-test",
                                     n_scenarios=3, draft_mode="mandated")
    sim_junior = des.run_scenario(cfg, costs, policy, scenario_id=0, master_seed="cf-test",
                                   n_scenarios=3, draft_mode="junior_first")

    crews_mandated = [r.crew_id for r in sim_mandated.ledger.rows if r.category.startswith("DRAFT")]
    crews_junior = [r.crew_id for r in sim_junior.ledger.rows if r.category.startswith("DRAFT")]
    assert crews_mandated, "a real scenario must produce at least one draft"
    assert crews_mandated != crews_junior, (
        "senior-first and junior-first drafted the identical sequence of crew -- "
        "junior_first is not actually taking effect"
    )


def test_myopic_total_cost_prefers_the_cheaper_tier():
    """select_myopic_total_cost must never pick a strictly more expensive
    tier when a cheaper legal candidate exists -- proven with real fixture
    crew (not mocked cost/legality), matching drafting.py's own
    determine_tier and cascade.py's own compute_draft_delta."""
    from crewsim.engine.state import Block, BlockType, CrewMember, OpenTimeItem

    cfg = config.load()
    costs = config.load_costs(cfg)
    item = OpenTimeItem(
        uid=1, pairing_id="TESTPAIR", base="YUL", fleet="A321neoLR", position="FO",
        start=10_000.0, end=10_600.0, deadline=9_500.0, origin="TEST", root_event_uid=1,
    )
    # A tier-1 (day off, empty calendar) candidate and a tier-2 (holds a
    # conflicting future pairing) candidate, both otherwise legal.
    tier1 = CrewMember(crew_id="T1", seniority=500, base="YUL", position="FO",
                        fleet_quals={"A321neoLR"}, calendar=[])
    tier2 = CrewMember(crew_id="T2", seniority=1, base="YUL", position="FO",
                        fleet_quals={"A321neoLR"}, calendar=[
                            Block(start=10_000.0, end=10_600.0, btype=BlockType.PAIRING,
                                  pairing_id="OTHERPAIR", flight_mins=300.0),
                        ])

    chosen = select_myopic_total_cost([tier1, tier2], item, costs, cfg, now=0.0)
    assert chosen is not None and chosen.crew_id == "T1", (
        "myopic_total_cost picked the strictly more expensive tier-2 candidate "
        "over an available, cheaper tier-1 candidate"
    )


def test_run_counterfactual_comparison_all_three_modes_present():
    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")

    results = run_counterfactual_comparison(cfg, costs, policy, n_scenarios=2, master_seed="cf-shape")
    assert set(results) == set(DRAFT_MODES)
    for mode in DRAFT_MODES:
        assert "expected_cost" in results[mode]
        assert "tier_breakdown" in results[mode]


def test_counterfactual_runs_are_crn_paired_against_mandated():
    """All 3 draft_modes must draw from the same CRN scenario set -- proven
    the same way S1e-04's grid pairing test was: spy on
    des._load_daily_sick_calls across 3 REAL run_scenario calls, one per
    draft_mode, and confirm every call received identical
    (season, master_seed, n_scenarios, scenario_id) arguments."""
    import crewsim.engine.des as des_module

    cfg = config.load()
    costs = config.load_costs(cfg)
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")

    real = des_module._load_daily_sick_calls
    calls: list[tuple] = []

    def spy(cfg_, season, master_seed, n_scenarios, scenario_id):
        calls.append((season, master_seed, n_scenarios, scenario_id))
        return real(cfg_, season, master_seed, n_scenarios, scenario_id)

    des_module._load_daily_sick_calls = spy
    try:
        for mode in DRAFT_MODES:
            des.run_scenario(cfg, costs, policy, scenario_id=0, master_seed="cf-pairing-check",
                              n_scenarios=3, draft_mode=mode)
    finally:
        des_module._load_daily_sick_calls = real

    assert len(calls) == len(DRAFT_MODES)
    assert all(c == calls[0] for c in calls), "draft_mode changed the scenario arrival draw -- not paired"
