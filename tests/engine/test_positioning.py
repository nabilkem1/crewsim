"""S1c-07: cross-base reserve dispatch (§5.3's XB -> DH) and its q^pos cost.

Acceptance (backlog/mvp/03_slice_1c_eligibility.md):
  - an out-of-scope reserve pool, LOADED, not constructed here
  - the XB branch fires only when the policy allows it
  - DEADHEAD/HOTEL/TRANSPORT book from configs/costs_pilots.yaml with real attribution
  - the deadheaded crew member gets a real DEADHEAD block that legality sees
  - positioning.deadhead / .hotel leave config.DECLARED_NOT_YET_CONSUMED

The story's own "Fails if" is the design constraint on this file: the
multi-base pool must come through the loader. Every test below that needs a
cross-base crew member gets one from `load_cross_base_reserves` reading D2, so
a regression in the loader fails these tests instead of hiding behind a
hand-built stand-in. That is the defect class this project keeps finding
(S1a-04's duplicate staffing implementation, S1b-07's stubbed shortfall,
S0-04's fabricated eligibility target), and it is the one this story is most
exposed to, because the real corpus reaches the branch only rarely.
"""
from __future__ import annotations

import dataclasses
import re

import pytest

from crewsim import config
from crewsim.engine import des
from crewsim.engine.events import assign_reserve
from crewsim.engine.legality import is_legal_assignment
from crewsim.engine.policy import load_policy
from crewsim.engine.roster_loader import load_cross_base_reserves
from crewsim.engine.state import Block, BlockType, CrewMember, OpenTimeItem


@pytest.fixture(scope="module")
def cfg():
    return config.load()


@pytest.fixture(scope="module")
def costs(cfg):
    return config.load_costs(cfg)


@pytest.fixture(scope="module")
def policy():
    return load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")


@pytest.fixture(scope="module")
def cross_base_pool(cfg):
    """The real out-of-scope reserve pool, from D1/D2 via the real loader."""
    return load_cross_base_reserves(
        cfg, home_base=cfg.scope.base, fleet=cfg.scope.fleet, position=cfg.scope.position
    )


# ======================================================= the pool is real ====
def test_the_pool_is_loaded_from_d2_and_is_actually_out_of_scope(cfg, cross_base_pool):
    """AC1: load_rosters can supply a pool wider than cfg.scope.base.

    Before S1c-07 every loader call passed base=cfg.scope.base, so the reserve
    pool was single-base and there was nothing for a cross-base branch to
    dispatch. This is the test that would have failed then.
    """
    assert cross_base_pool, "no cross-base reserves loaded -- the XB branch cannot fire"
    bases = {c.base for c in cross_base_pool}
    assert cfg.scope.base not in bases, "in-scope crew must not appear in the cross-base pool"
    assert bases, "cross-base crew must carry their real home base"
    for c in cross_base_pool:
        assert c._is_cross_base and c._is_reserve
        assert any(b.btype == BlockType.RESERVE for b in c.calendar), (
            f"{c.crew_id} has no RESERVE block -- a line holder at another base has no "
            f"availability to offer and is not draftable from here"
        )
        assert c.position == cfg.scope.position
        assert cfg.scope.fleet in c.fleet_quals


def test_cross_base_crew_keep_the_flying_that_makes_them_unavailable(cfg, cross_base_pool):
    """The design decision, pinned so it cannot be quietly reversed.

    In-scope reserves are MINTED -- load_rosters strips their pairings, because
    a reserve bidder gives up their line (S1b-02). Cross-base crew are not:
    what Toronto staffed is not this planner's Stage-1 decision, so they are
    the real crew with their real calendars. Stripping their pairings would
    invent availability that never existed and make cross-base coverage look
    far more reliable than it is.
    """
    with_flying = [c for c in cross_base_pool if any(b.btype == BlockType.PAIRING for b in c.calendar)]
    assert with_flying, (
        "every cross-base reserve came back with no PAIRING blocks -- either the "
        "corpus changed or the loader started minting pure reserve lines, which "
        "would invent out-of-base availability"
    )


# ============================================= L7 is the gate that had to open
def test_l7_rejects_an_out_of_base_reserve_unless_deadheaded(cfg, cross_base_pool):
    """L7's own wording is "crew must start duty at own base unless deadheaded",
    and its `is_deadhead` parameter had existed unset since the rule was
    written -- so every cross-base candidate failed L7 by construction, which
    is why measuring this before the fix produced 0 legal assignments out of
    11,393 covering (crew, duty) pairs in the real corpus.
    """
    # Search the real pool for a slot that is legal WHEN deadheaded. Such slots
    # exist -- the end-to-end test below dispatches on them -- and finding one
    # by search rather than by assuming crew[0] is free keeps this test honest
    # against a corpus that may change.
    lead = cfg.positioning.deadhead_duration_hours * 60.0
    found = None
    for crew in cross_base_pool:
        for block in (b for b in crew.calendar if b.btype == BlockType.RESERVE):
            t = block.start
            while t + lead + 180.0 <= block.end and found is None:
                item = OpenTimeItem(
                    uid=1, pairing_id="XB", base=cfg.scope.base, fleet=cfg.scope.fleet,
                    position=cfg.scope.position, start=t, end=t + lead + 180.0,
                    deadline=t + lead, origin="SICK_CALL", root_event_uid=1,
                )
                now = t - 1440.0
                if now >= 0 and is_legal_assignment(
                    crew, item, is_deadhead=True, now=now, cfg=cfg
                ).legal:
                    found = (crew, item, now)
                t += 60.0
            if found:
                break
        if found:
            break

    assert found is not None, (
        "no cross-base slot is legal even when deadheaded -- the XB branch cannot "
        "fire at all, which would make the whole story inert"
    )
    crew, item, now = found

    # The ONLY thing changed is whether the crew is being flown in. Before
    # S1c-07 nothing ever passed is_deadhead=True, so this branch was dead:
    # measured on the real corpus, 0 of 11,393 covering (crew, duty) pairs were
    # legal, L7 rejecting every one that got past the rolling limits.
    not_positioned = is_legal_assignment(crew, item, is_deadhead=False, now=now, cfg=cfg)
    assert not not_positioned.legal
    assert not_positioned.fail_rule == "ILLEGAL_L7", not_positioned.reason


# ================================================ the assignment mechanics ===
def test_deadhead_block_is_real_and_carved_out_of_the_reserve_block():
    """AC5: positioning "costs a seat and consumes duty time" -- so it is a
    calendar block L1/L2/L3 and the L0 invariant all see, not a teleport.

    Calendar mechanics only, so this one builds its crew member directly: it is
    testing assign_reserve's block surgery, not the pool.
    """
    crew = CrewMember(
        crew_id="R_XB", base="YYZ", fleet_quals={"A321neoLR"}, position="FO", seniority=1,
        calendar=[Block(start=0.0, end=2000.0, btype=BlockType.RESERVE, reserve_call_type="SC")],
    )
    assign_reserve(crew, duty_start=500.0, duty_end=800.0, min_rest=600.0,
                   pairing_id="P1", deadhead_start=260.0)

    kinds = [(b.btype, b.start, b.end) for b in crew.calendar]
    assert (BlockType.DEADHEAD, 260.0, 500.0) in kinds, kinds
    assert (BlockType.DRAFTED_DUTY, 500.0, 800.0) in kinds
    assert (BlockType.REST, 800.0, 1400.0) in kinds
    # The reserve block is split around the WHOLE occupancy, positioning
    # included -- if it were split at duty_start the deadhead would overlap a
    # live RESERVE block and the L0 invariant would fire.
    assert (BlockType.RESERVE, 0.0, 260.0) in kinds
    for i in range(1, len(crew.calendar)):
        assert crew.calendar[i].start >= crew.calendar[i - 1].end, "overlapping blocks (L0)"


def test_positioning_must_finish_before_the_duty_it_positions_for():
    crew = CrewMember(
        crew_id="R_XB", base="YYZ", fleet_quals={"A321neoLR"}, position="FO", seniority=1,
        calendar=[Block(start=0.0, end=2000.0, btype=BlockType.RESERVE)],
    )
    with pytest.raises(ValueError, match="positioning must finish before"):
        assign_reserve(crew, duty_start=500.0, duty_end=800.0, min_rest=600.0,
                       pairing_id="P1", deadhead_start=600.0)


def test_the_reserve_block_must_cover_the_positioning_too():
    """A reserve cannot be positioned during hours they are not yet on call.

    Since OPEN-4 the duty may run PAST the end of the shift that authorised it,
    but it may not start BEFORE it: the occupancy still has to begin inside a
    RESERVE block, and for a cross-base dispatch that occupancy starts at the
    deadhead report, not the flight's.
    """
    crew = CrewMember(
        crew_id="R_XB", base="YYZ", fleet_quals={"A321neoLR"}, position="FO", seniority=1,
        # on call only from 400, but positioning would have to start at 260
        calendar=[Block(start=400.0, end=2000.0, btype=BlockType.RESERVE)],
    )
    with pytest.raises(ValueError, match="holds no RESERVE block covering"):
        assign_reserve(crew, duty_start=500.0, duty_end=800.0, min_rest=600.0,
                       pairing_id="P1", deadhead_start=260.0)


# ============================================== end to end, on real data =====
@pytest.fixture(scope="module")
def dispatched(cfg, costs, policy):
    """A real scenario, real loader, real pool, that actually reaches the branch.

    master_seed="master2", not "master": scenario generation now draws
    sick-call counts from the real fitted NHPP GLM (calibration.nhpp) instead
    of a flat Poisson(5) mock, so which seeds happen to produce enough
    in-scope demand to overflow the reserve pool changed too. "master2" is
    empirically confirmed (see this story's own note) to still reach the
    cross-base branch on the real corpus; "master" no longer does for
    scenario_id=0 -- that is the mock removal working, not a regression in
    this file."""
    return des.run_scenario(cfg, costs, policy, scenario_id=0, master_seed="master2", n_scenarios=4)


def test_cross_base_dispatch_fires_on_the_real_corpus(dispatched):
    """AC2/AC3: the branch is reachable end to end -- real D2 crew, real
    calibrated arrivals, no test-side construction anywhere in the path."""
    assert dispatched.n_cross_base_assignments > 0, (
        "no cross-base dispatch occurred in a real scenario. Either the pool stopped "
        "loading, or L7's is_deadhead wiring regressed (see "
        "test_l7_rejects_an_out_of_base_reserve_unless_deadheaded) -- both of which "
        "silently restore the $0 positioning cost this story exists to remove."
    )


POSITIONING_CATEGORIES = ("DEADHEAD", "HOTEL", "TRANSPORT")


def test_positioning_books_all_three_categories_with_real_attribution(cfg, costs, dispatched):
    """§5.8 names three positioning categories, and the ledger must be able to
    produce all three -- TRANSPORT was nameable but unpriceable until §4.4.2
    gained a coefficient, so the engine had a category it could never book."""
    rows = [r for r in dispatched.ledger.rows if r.category in POSITIONING_CATEGORIES]
    assert rows, "cross-base dispatch happened but booked no positioning cost"

    deadheads = [r for r in rows if r.category == "DEADHEAD"]
    hotels = [r for r in rows if r.category == "HOTEL"]
    transports = [r for r in rows if r.category == "TRANSPORT"]
    assert len(deadheads) == dispatched.n_cross_base_assignments
    assert cfg.positioning.hotel_on_every_deadhead, "this assertion assumes the configured rule"
    assert cfg.positioning.transport_on_every_deadhead, "likewise"
    assert len(hotels) == len(deadheads), "hotel_on_every_deadhead is set, so counts must match"
    assert len(transports) == len(deadheads), "transport_on_every_deadhead is set, likewise"

    # The amounts come from costs_pilots.yaml -> positioning, not from anywhere else
    assert {r.amount for r in deadheads} == {costs.positioning.deadhead}
    assert {r.amount for r in hotels} == {costs.positioning.hotel}
    assert {r.amount for r in transports} == {costs.positioning.transport}

    xb_ids = {c.crew_id for c in dispatched.cross_base_reserves}
    for r in rows:
        assert r.crew_id in xb_ids, "positioning booked against a crew member who was not deadheaded"
        # AC3: same root as the assignment, so explain-cost --trace-root attributes it
        assert r.root_event_uid, "positioning row has no causal chain to trace back"


def test_the_deadheaded_crew_carry_a_deadhead_block(dispatched, cfg):
    blocks = [
        (c, b) for c in dispatched.cross_base_reserves
        for b in c.calendar if b.btype == BlockType.DEADHEAD
    ]
    assert blocks, "positioning was charged but no DEADHEAD block was written"
    expected = cfg.positioning.deadhead_duration_hours * 60.0
    for _crew, b in blocks:
        assert b.end - b.start == pytest.approx(expected), (
            "the DEADHEAD block must be the configured positioning duration -- it is "
            "what makes L1/L3 count the trip"
        )


def test_cross_base_assignments_stay_out_of_the_v2_erlang_counters(dispatched):
    """Gate V2 divides in-scope reserve assignments by the in-scope
    establishment's on-call time. A cross-base rescue is served by a pool whose
    on-call time is not in that denominator, so counting it in the numerator
    would inflate the measured offered load of a pool that never served it.
    """
    assert dispatched.n_cross_base_assignments > 0
    util_rows = [r for r in dispatched.ledger.rows if r.category == "RESERVE_UTILIZATION"]
    xb_ids = {c.crew_id for c in dispatched.cross_base_reserves}
    n_xb_util = sum(1 for r in util_rows if r.crew_id in xb_ids)
    assert n_xb_util == dispatched.n_cross_base_assignments
    # ...and they are NOT in the in-scope assignment count that V2 reads
    assert dispatched.n_reserve_assignments == len(util_rows) - n_xb_util


def test_cross_base_eligibility_does_not_pollute_the_v3_distribution(cfg, costs, policy):
    """V3 compares the eligibility distribution against a historical
    reconstruction for cfg.scope alone. The cross-base pool is a different
    population at different bases; sampling it into the same series would move
    V3's number with no in-scope mechanism having changed.
    """
    sim = des.run_scenario(cfg, costs, policy, scenario_id=0, master_seed="master2", n_scenarios=4)
    n_samples = len(sim.elig.get_distribution())
    # One sample per in-scope resolution attempt that had a non-empty pool, and
    # none from the cross-base attempts, which happened.
    assert sim.n_cross_base_assignments > 0
    assert n_samples > 0
    sim.elig.eligible_reserves(
        sim.cross_base_reserves,
        dataclasses.replace(
            next(iter(sim.open_items.values()), None)
            or OpenTimeItem(uid=1, pairing_id="X", base=cfg.scope.base, fleet=cfg.scope.fleet,
                            position=cfg.scope.position, start=100.0, end=400.0, deadline=100.0,
                            origin="SICK_CALL", root_event_uid=1),
        ),
        now=0.0, record=False, is_deadhead=True,
    )
    assert len(sim.elig.get_distribution()) == n_samples, "record=False still recorded a sample"


# ============================================== the policy flag is honoured ==
def test_policy_flag_gates_the_whole_branch(cfg, costs, policy):
    """AC2: if and only if stage2.allow_cross_base_reserve."""
    forbidden = policy.model_copy(
        update={"stage2": policy.stage2.model_copy(update={"allow_cross_base_reserve": False})}
    )
    sim = des.run_scenario(cfg, costs, forbidden, scenario_id=0, master_seed="master", n_scenarios=4)
    assert sim.cross_base_reserves == []
    assert sim.n_cross_base_assignments == 0
    assert not [r for r in sim.ledger.rows if r.category in POSITIONING_CATEGORIES]


def test_a_cross_base_pool_without_positioning_config_is_refused(cfg, costs, policy):
    """Neither the duration nor the hotel rule may be assumed: both are
    [CONFIRM: Crew Planning] figures that change the answer materially.
    """
    import numpy as np
    import simpy

    pool = load_cross_base_reserves(
        cfg, home_base=cfg.scope.base, fleet=cfg.scope.fleet, position=cfg.scope.position
    )
    no_pos = cfg.model_copy(update={"positioning": None})
    with pytest.raises(ValueError, match=re.escape("cfg.positioning is not configured")):
        des.Simulation(
            simpy.Environment(), no_pos, costs, policy.policy_id, 0, [], [],
            np.random.default_rng(0), 1440.0, cross_base_reserves=pool,
        )


# ================================================== the guard that certifies =
def test_positioning_costs_are_no_longer_declared_unconsumed():
    """The story's done-condition, and the one assertion that cannot be faked:
    the consumption guard added in S1c-01's P2 pass now proves these two keys
    are read by real code, so they must not be exempted from it any more.
    """
    from crewsim.config import DECLARED_NOT_YET_CONSUMED

    assert "positioning.deadhead" not in DECLARED_NOT_YET_CONSUMED
    assert "positioning.hotel" not in DECLARED_NOT_YET_CONSUMED


def test_hotel_can_be_switched_off_without_touching_code(cfg, costs, policy):
    """hotel_on_every_deadhead is a [CONFIRM: Crew Planning] decision, so it has
    to be a knob -- not a rule welded into des.py.
    """
    no_hotel = cfg.model_copy(
        update={"positioning": cfg.positioning.model_copy(update={"hotel_on_every_deadhead": False})}
    )
    sim = des.run_scenario(no_hotel, costs, policy, scenario_id=0, master_seed="master2", n_scenarios=4)
    assert sim.n_cross_base_assignments > 0
    assert [r for r in sim.ledger.rows if r.category == "DEADHEAD"]
    assert not [r for r in sim.ledger.rows if r.category == "HOTEL"]


# ================================== the replay path must have the pool too ===
def test_the_historical_replay_path_also_gets_a_cross_base_pool(cfg, costs, policy):
    """Gate V6 prints simulated positioning next to D10's real invoices.

    run_historical_replay constructs its own Simulation, so it defaulted
    cross_base_reserves to None -- which made that V6 line a structural $0.00
    that could never be non-zero, printed beside real money and reading as a
    measurement. Exactly the shape of defect this project keeps finding, and it
    would have shipped behind a correctly-implemented engine.
    """
    import datetime

    from crewsim.engine import replay

    sim = replay.run_historical_period(
        cfg, costs, policy, datetime.date(2026, 3, 1), datetime.date(2026, 4, 1),
        trace=False, verbose_trace=False,
    )
    assert sim.cross_base_reserves, "the replay path has no cross-base pool"
    positioning = [r for r in sim.ledger.rows if r.category in POSITIONING_CATEGORIES]

    # The regression this guards is a WIRING one: run_historical_replay used to
    # default cross_base_reserves to None, making V6's positioning line a
    # structural $0.00 that could never be non-zero. The pool assert above is
    # that guard. Whether any cross-base reserve is actually DISPATCHED in a
    # given month is a modelling outcome, not wiring -- and since the
    # 2026-08-12 reserve-shift fix it is frequently zero, because a reserve is
    # only eligible when their standby shift covers the WHOLE duty and most
    # duties are longer than a shift (see the audit's OPEN-4). So the booking
    # invariant is asserted as an implication, which holds either way and still
    # fails loudly if a dispatch ever books nothing.
    if sim.n_cross_base_assignments == 0:
        assert not positioning, (
            "positioning booked without any cross-base assignment to justify it"
        )
        return
    assert positioning, (
        "a real month replayed with cross-base allowed booked no positioning at all -- "
        "gate V6 would report $0.00 simulated against D10's real invoices"
    )
