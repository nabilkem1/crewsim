"""S1b-02 -- headcount conservation, and what a reserve bid costs.

Parametrised over the real candidate policy set, because the AC says "for every
candidate R" and the previous version checked only R10 -- with an assertion that
could not fail:

    lines_marked + reserves_marked == total_with_policy

which partitions one list by a boolean and asserts the parts sum to the whole.
"""
from __future__ import annotations

import pytest

from crewsim import config
from crewsim.engine import roster_loader
from crewsim.engine.policy import load_policy
from crewsim.engine.state import BlockType

# The shipped candidate set -- "every candidate R" in the AC's words.
CANDIDATE_POLICIES = ("R4", "R6", "R8", "R10", "R14")


def _scope(cfg):
    return {"base": cfg.scope.base, "fleet": cfg.scope.fleet, "position": cfg.scope.position}


@pytest.fixture(scope="module")
def cfg():
    return config.load()


@pytest.fixture(scope="module")
def baseline(cfg):
    """The active population with no policy applied -- the conserved quantity."""
    active, _ = roster_loader.load_rosters(cfg, **_scope(cfg))
    return active


@pytest.mark.parametrize("policy_name", CANDIDATE_POLICIES)
def test_headcount_is_conserved_at_every_candidate_r(cfg, baseline, policy_name) -> None:
    """Carving out reserves must not change how many people exist.

    Compared against the SAME population loaded without a policy -- an external
    reference, not a re-partition of the list under test. The v2 defect minted
    reserves, so the total grew with R.
    """
    pol = load_policy(config.repo_root() / "configs" / "policies" / f"{policy_name}.yaml")
    active, _ = roster_loader.load_rosters(cfg, **_scope(cfg), policy=pol)

    assert len(active) == len(baseline), (
        f"{policy_name}: population changed from {len(baseline)} to {len(active)} -- "
        "reserves are being minted, not carved out"
    )
    assert {c.crew_id for c in active} == {c.crew_id for c in baseline}, (
        f"{policy_name}: the same people must be present, not merely the same count"
    )


@pytest.mark.parametrize("policy_name", CANDIDATE_POLICIES)
def test_reserve_count_matches_the_policy_target(cfg, baseline, policy_name) -> None:
    """The carve-out size is the policy's own peak daily target, and the split
    is exhaustive: nobody is both, nobody is neither."""
    pol = load_policy(config.repo_root() / "configs" / "policies" / f"{policy_name}.yaml")
    active, _ = roster_loader.load_rosters(cfg, **_scope(cfg), policy=pol)

    reserves = [c for c in active if c._is_reserve]
    lines = [c for c in active if not c._is_reserve]
    expected = pol.total_reserves(**_scope(cfg))

    assert len(reserves) == expected, f"{policy_name}: expected {expected} reserves"
    assert len(lines) == len(baseline) - expected
    assert not ({c.crew_id for c in reserves} & {c.crew_id for c in lines})


@pytest.mark.parametrize("policy_name", CANDIDATE_POLICIES)
def test_reserves_and_line_holders_get_the_right_block_types(cfg, policy_name) -> None:
    pol = load_policy(config.repo_root() / "configs" / "policies" / f"{policy_name}.yaml")
    active, _ = roster_loader.load_rosters(cfg, **_scope(cfg), policy=pol)
    for c in active:
        if c._is_reserve:
            assert all(b.btype != BlockType.PAIRING for b in c.calendar)
            assert any(b.btype == BlockType.RESERVE for b in c.calendar)
        else:
            assert all(b.btype != BlockType.RESERVE for b in c.calendar)


def test_carving_more_reserves_displaces_more_flying(cfg) -> None:
    """S1b-02 AC2's premise: the opportunity cost must grow with R. If displaced
    flying were still being discarded silently this would be zero everywhere."""
    displaced = {}
    for name in CANDIDATE_POLICIES:
        pol = load_policy(config.repo_root() / "configs" / "policies" / f"{name}.yaml")
        active, _ = roster_loader.load_rosters(cfg, **_scope(cfg), policy=pol)
        displaced[name] = sum(len(c._displaced_pairings) for c in active if c._is_reserve)

    assert all(v > 0 for v in displaced.values()), f"no flying displaced at all: {displaced}"
    assert displaced["R14"] > displaced["R4"], (
        f"displaced flying must grow with R, got {displaced}"
    )


def _with_bid_rule(cfg, rule: str):
    return cfg.model_copy(
        update={"population": cfg.population.model_copy(update={"reserve_bid_rule": rule})}
    )


def test_reserve_bid_rule_default_is_senior_first(cfg) -> None:
    """IMP-118: the configured default is senior_first, and it means reserves
    come from the TOP of the seniority list (lowest seniority number)."""
    assert cfg.population.reserve_bid_rule == "senior_first"
    pol = load_policy(config.repo_root() / "configs" / "policies" / "R10.yaml")
    active, _ = roster_loader.load_rosters(cfg, **_scope(cfg), policy=pol)

    reserves = [c for c in active if c._is_reserve]
    lines = [c for c in active if not c._is_reserve]
    # Lower seniority NUMBER = more senior.
    assert max(c.seniority for c in reserves) < min(c.seniority for c in lines), (
        "senior_first must take the most senior crew, with no overlap"
    )


def test_junior_first_bid_rule_inverts_the_selection(cfg) -> None:
    """The knob has to actually do something -- otherwise AC3 is satisfied in
    name only."""
    pol = load_policy(config.repo_root() / "configs" / "policies" / "R10.yaml")
    active, _ = roster_loader.load_rosters(_with_bid_rule(cfg, "junior_first"), **_scope(cfg), policy=pol)

    reserves = [c for c in active if c._is_reserve]
    lines = [c for c in active if not c._is_reserve]
    # Higher seniority NUMBER = more junior.
    assert min(c.seniority for c in reserves) > max(c.seniority for c in lines)


def test_reserve_shortfall_raises(cfg, baseline) -> None:
    """IMP-119: a policy asking for more reserves than the group has active
    crew fails loudly, naming the group and both counts -- it is never
    silently simulated with fewer reserves."""
    from crewsim.gates.v1_degeneracy import policy_with_reserve_count

    base = load_policy(config.repo_root() / "configs" / "policies" / "R10.yaml")
    too_many = policy_with_reserve_count(base, len(baseline) + 1, "R-too-many")
    with pytest.raises(roster_loader.ReserveShortfallError) as exc:
        roster_loader.load_rosters(cfg, **_scope(cfg), policy=too_many)
    msg = str(exc.value)
    assert f"{cfg.scope.base}/{cfg.scope.fleet}/{cfg.scope.position}" in msg
    assert f"{len(baseline) + 1} requested" in msg
    assert f"{len(baseline)} active crew available" in msg


def test_reserve_count_equal_to_headcount_is_not_a_shortfall(cfg, baseline) -> None:
    """The boundary gate V1 relies on: every active crew member on reserve."""
    from crewsim.gates.v1_degeneracy import policy_with_reserve_count

    base = load_policy(config.repo_root() / "configs" / "policies" / "R10.yaml")
    everyone = policy_with_reserve_count(base, len(baseline), "R-all")
    active, _ = roster_loader.load_rosters(cfg, **_scope(cfg), policy=everyone)
    assert sum(1 for c in active if c._is_reserve) == len(baseline)


def test_reserves_never_share_a_calendar_object(cfg) -> None:
    """Above the number of distinct authentic reserve patterns (18 in this
    scope) the pattern cycle repeats. Without a copy, several crew shared ONE
    list -- and copy.deepcopy preserves that sharing, so run_scenario's
    defensive copy did not break it and drafting one reserve mutated others."""
    import copy

    from crewsim.gates.v1_degeneracy import policy_with_reserve_count

    base = load_policy(config.repo_root() / "configs" / "policies" / "R10.yaml")
    pol = policy_with_reserve_count(base, 20, "R20-aliasing")
    active, _ = roster_loader.load_rosters(cfg, **_scope(cfg), policy=pol)

    reserves = [c for c in copy.deepcopy(active) if c._is_reserve]
    assert len(reserves) == 20
    assert len({id(c.calendar) for c in reserves}) == len(reserves), (
        "two reserves share one calendar object -- drafting one will mutate the other"
    )
