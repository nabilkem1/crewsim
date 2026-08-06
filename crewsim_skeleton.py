"""
crewsim_skeleton.py  (v3 -- Air Transat instantiation)
======================================================
SimPy DES core skeleton for the Crew Reserve & Drafting Policy Simulation,
with Common Random Numbers (CRN) scenario architecture built in.

MVP-fidelity skeleton: interfaces and control flow are production-shaped;
domain logic is deliberately simplified. Extend, don't rewrite.

WHAT IS IMPLEMENTED (and correct)
  - CRN: hierarchical SeedSequence streams + process-stable derived seeding.
  - Cost ledger: every cost is a row; RESERVE_STAFFING accrues PER DAY so the
    warm-up filter prorates it like every other category.
  - Legality surrogate: L0 (single assignment), L1 (max duty), L2 (min rest),
    L6 (qualification), L7 (base).
  - Draft selection: impact tier first, SENIOR-first within tier (Air Transat's
    mandated rule; there is no junior-first policy and no protected block).
  - Emergent cascades from the drafted crew's own calendar.

WHAT IS DELIBERATELY ABSENT (do not mistake omission for completeness)
  - Events E2 DELAY, E8 UNCOVERED_DEADLINE, E9 HORIZON_END terminal penalty.
    Cancellation is booked at decision time, not at the deadline, so an open
    item can never be rescued by a reserve that frees up later.
  - Sick calls are NOT bound to roster crew: they create open time but never
    remove the sick crew member from the available pool (spec 5.2 item 2
    specifies the correct behaviour; slice 1b implements it).
  - Headcount is NOT conserved: reserves are minted on top of the line-holder
    roster instead of being carved out of it (spec 4.1; slice 1b).
  - Reserve lines do not rotate (no on/off pattern, no SC/LC split) (spec 4.4).
  - Rules L3, L4, L5, L8 are not implemented. (There is no L9: Air Transat has
    no protected-block concept, so the rule v2 defined does not exist.)
  Consequences: reserve productivity is overstated, realized eligibility rate
  is understated, and E[C] is not yet expected to show an interior optimum in
  the reserve count. See SPEC_REVIEW.md.

Run:  python crewsim_skeleton.py
Deps: simpy>=4.1, numpy>=1.26, pyyaml>=6 (optional -- built-in defaults are
      used if configs/base.yaml or PyYAML is absent)
"""
from __future__ import annotations

import bisect
import hashlib
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

import numpy as np
import simpy

MIN_PER_DAY = 1440.0

# ----------------------------------------------------------------------------
# 0. CONFIGURATION
# ----------------------------------------------------------------------------
# Every scope/horizon/population value comes from configs/base.yaml. Nothing
# below may hard-code them (spec 4.4, parameter registry). Falls back to the
# defaults here so the file stays runnable standalone.

DEFAULTS = {
    "scope": {"base": "YUL", "fleet": "A321neoLR", "position": "FO"},
    "horizon": {"warmup_days": 7, "measurement_days": 28, "cooldown_days": 7},
    "population": {"roster_size": 120},
    "demand": {},
    "sensitivity": {"roster_size": [100, 120, 140]},
}

# Config keys the current code does not yet read. Declaring one is fine -- it
# records an answer from the business ahead of the slice that consumes it --
# but it must not look as though it is having an effect.
NOT_YET_CONSUMED = {
    ("demand", "pairings_per_bid_period"): "slice 1b (flying comes from D3)",
    ("demand", "credit_hours_per_bid_period"): "slice 1b (flying comes from D3)",
}


_CONFIG_NOTICES_SHOWN = False


def load_config(path: str = "configs/base.yaml") -> dict:
    global _CONFIG_NOTICES_SHOWN
    quiet = _CONFIG_NOTICES_SHOWN
    _CONFIG_NOTICES_SHOWN = True
    cfg = {k: dict(v) for k, v in DEFAULTS.items()}
    try:
        import yaml                                   # optional dependency
        with open(path) as fh:
            loaded = yaml.safe_load(fh) or {}
        for section, values in loaded.items():
            if isinstance(values, dict):
                cfg.setdefault(section, {}).update(values)
            else:
                cfg[section] = values
    except (ImportError, FileNotFoundError) as exc:
        if not quiet:
            print(f"[config] {path} not loaded ({type(exc).__name__}); "
                  f"using defaults")
    for (section, key), slice_name in NOT_YET_CONSUMED.items():
        if not quiet and cfg.get(section, {}).get(key) is not None:
            print(f"[config] NOTE: {section}.{key} is set but not yet consumed "
                  f"-- it takes effect at {slice_name}.")
    return cfg

# ----------------------------------------------------------------------------
# 1. CRN SCENARIO ARCHITECTURE
# ----------------------------------------------------------------------------
# Master seed -> SeedSequence.spawn(N) -> one child per scenario.
# Each scenario child spawns NAMED streams. Policy-dependent draws use
# per-event derived generators so random-number alignment across policies
# is preserved (the heart of CRN).

STREAMS = ("severity", "sick_calls", "delays", "recovery", "tiebreak")


def stable_seed(*parts) -> int:
    """Deterministic 64-bit seed from arbitrary parts.

    FIX (was D2): the previous version used Python's built-in hash(), which is
    salted per interpreter by PYTHONHASHSEED. Under joblib/Ray multiprocessing
    that silently broke reproducibility and gate V7. blake2b is stable across
    processes, machines and Python versions.
    """
    key = "|".join(str(p) for p in parts).encode("utf-8")
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


class ScenarioRNG:
    """Named, isolated RNG streams for one scenario (CRN discipline)."""

    def __init__(self, scenario_seed: np.random.SeedSequence):
        self._entropy = scenario_seed.entropy
        children = scenario_seed.spawn(len(STREAMS))
        self.streams = {name: np.random.default_rng(ss)
                        for name, ss in zip(STREAMS, children)}

    def stream(self, name: str) -> np.random.Generator:
        return self.streams[name]

    def event_rng(self, stream: str, event_uid: int) -> np.random.Generator:
        """Fresh generator keyed by (scenario, stream, event) -- use for any
        draw whose *call order* depends on policy decisions, so that two
        policies consuming different numbers of draws stay aligned."""
        return np.random.default_rng(
            np.random.SeedSequence(stable_seed(self._entropy, stream, event_uid))
        )


def make_scenario_seeds(master_seed: int, n_scenarios: int):
    return np.random.SeedSequence(master_seed).spawn(n_scenarios)


# ----------------------------------------------------------------------------
# 2. DOMAIN MODEL (Crew State Engine)
# ----------------------------------------------------------------------------

class BlockType(Enum):
    PAIRING = auto()
    RESERVE = auto()
    DAY_OFF = auto()
    VACATION = auto()
    TRAINING = auto()
    SIMULATOR = auto()
    DRAFTED_DUTY = auto()
    REST = auto()


# Blocks that physically occupy the crew member: nothing may be scheduled on
# top of these (rule L0). A PAIRING is NOT in this set because drafting someone
# off a pairing is legal -- it removes the pairing and cascades (tier 2).
OCCUPYING = {BlockType.DRAFTED_DUTY, BlockType.REST}

# Blocks consumed (deleted) when their holder is drafted over them.
# NOTE: this includes VACATION and SIMULATOR. Air Transat has no "protected
# block" concept in drafting -- there is no contractual carve-out making any
# block undraftable. Tier 4/5 are the most EXPENSIVE options, never forbidden
# ones. (v2 modelled a protection that does not exist; see spec 5.4.)
CONSUMED_BY_DRAFT = {BlockType.DAY_OFF, BlockType.VACATION,
                     BlockType.TRAINING, BlockType.SIMULATOR,
                     BlockType.RESERVE}

# Draft impact tiers (policy: exhaust tier k before tier k+1)
TIER_OF_STATUS = {
    BlockType.DAY_OFF: 1,        # no duty -> least disruptive
    BlockType.PAIRING: 2,        # has a pairing -> cascade candidate
    BlockType.TRAINING: 3,
    BlockType.VACATION: 4,
    BlockType.SIMULATOR: 5,
}


@dataclass(frozen=True)
class Block:
    start: float                 # sim minutes
    end: float
    btype: BlockType
    pairing_id: Optional[str] = None


@dataclass
class Crew:
    crew_id: str
    base: str
    fleet: str
    position: str                # "CA" / "FO"
    seniority: int               # 1 = most senior
    blocks: list[Block] = field(default_factory=list)   # sorted by start
    drafts_this_month: int = 0

    # -- calendar queries ---------------------------------------------------
    def block_at(self, t: float) -> Optional[Block]:
        i = bisect.bisect_right([b.start for b in self.blocks], t) - 1
        if i >= 0 and self.blocks[i].start <= t < self.blocks[i].end:
            return self.blocks[i]
        return None

    def blocks_in(self, start: float, end: float) -> list[Block]:
        return [b for b in self.blocks if b.start < end and b.end > start]

    def status_tier(self, start: float, end: float) -> int:
        """Impact tier over a window = worst tier of any overlapping block;
        empty window -> tier 1 (no duty)."""
        overlapping = [b for b in self.blocks_in(start, end)
                       if b.btype in TIER_OF_STATUS]
        if not overlapping:
            return 1
        return max(TIER_OF_STATUS[b.btype] for b in overlapping)

    # -- atomic mutations (all state changes go through these) ---------------
    def remove_block(self, block: Block) -> "StateDelta":
        self.blocks.remove(block)
        return StateDelta(self.crew_id, removed=[block], inserted=[])

    def insert_block(self, block: Block) -> "StateDelta":
        keys = [b.start for b in self.blocks]
        self.blocks.insert(bisect.bisect_left(keys, block.start), block)
        return StateDelta(self.crew_id, removed=[], inserted=[block])


@dataclass
class StateDelta:
    """Audit record of a mutation -- consumed by the Cascade Engine."""
    crew_id: str
    removed: list[Block]
    inserted: list[Block]


@dataclass(frozen=True)
class OpenTimeItem:
    uid: int
    pairing_id: str
    base: str
    fleet: str
    position: str
    start: float                 # report time (sim minutes)
    end: float                   # release time
    deadline: float              # must be covered by this time or cancel
    origin: str = "SICK_CALL"    # or "CASCADE"


# ----------------------------------------------------------------------------
# 3. LEGALITY SURROGATE  (simplified, conservatively biased -- see spec 5.4)
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class LegalityResult:
    legal: bool
    failed_rule: Optional[str] = None


class LegalitySurrogate:
    MAX_DUTY_MIN = 13 * 60          # L1
    MIN_REST_MIN = 11 * 60          # L2 (home-base value, conservative)

    def check(self, crew: Crew, duty_start: float, duty_end: float,
              o: OpenTimeItem) -> LegalityResult:
        # L0: single assignment. A crew member cannot hold two duties at once.
        # FIX (was D3): this rule did not exist in v2, in the surrogate or in
        # the spec's L1-L9 list. Without it the same reserve could be booked
        # into overlapping duties repeatedly.
        # The span checked is the duty PLUS the rest it obliges, because that
        # rest is as physically binding as the duty itself.
        for b in crew.blocks_in(duty_start, duty_end + self.MIN_REST_MIN):
            if b.btype in OCCUPYING:
                return LegalityResult(False, "L0_double_assignment")
        if duty_end - duty_start > self.MAX_DUTY_MIN:                 # L1
            return LegalityResult(False, "L1_max_duty")
        # L2: min rest before duty vs. previous duty-type block.
        # Note the filter is b.end <= duty_start; blocks that STRADDLE
        # duty_start are caught by L0 above, not here.
        prev = [b for b in crew.blocks
                if b.end <= duty_start
                and b.btype in (BlockType.PAIRING, BlockType.DRAFTED_DUTY)]
        if prev and duty_start - max(b.end for b in prev) < self.MIN_REST_MIN:
            return LegalityResult(False, "L2_min_rest")
        if crew.fleet != o.fleet or crew.position != o.position:      # L6
            return LegalityResult(False, "L6_qualification")
        if crew.base != o.base:                                       # L7 (MVP: no cross-base)
            return LegalityResult(False, "L7_base")
        # L3/L4/L5/L8 omitted in skeleton -- same pattern, add here.
        return LegalityResult(True)


# ----------------------------------------------------------------------------
# 4. POLICY OBJECT  (serializable candidate: Stage-1 vector + Stage-2 params)
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Policy:
    policy_id: str
    n_reserves: int                     # Stage-1 (skeleton: single base/fleet/pos)
    # Air Transat drafts SENIOR FIRST, always. This is not a decision variable:
    # it is the operating rule. "junior_first" exists solely to price the
    # mandated rule against the alternative in counterfactual analysis, and
    # must never appear in a candidate policy. [CONFIRM: Labour Relations]
    seniority_order: str = "senior_first"
    counterfactual: bool = False       # True only for non-recommendation runs
    # Stage-2 tier cost coefficients (CAD; see costs.yaml in the full system).
    # Index 0 unused so tier k reads as tier_cost[k].
    tier_cost: tuple = (0., 300., 900., 2500., 4000., 6000.)
    base_draft_cost: float = 500.0
    reserve_day_cost: float = 250.0     # kappa (reserve guarantee per DAY)
    reserve_util_cost: float = 150.0
    cancel_cost: float = 25000.0


# ----------------------------------------------------------------------------
# 5. ENGINES: eligibility, draft selection, cascade, cost ledger
# ----------------------------------------------------------------------------

class CostLedger:
    def __init__(self):
        self.rows: list[tuple] = []   # (sim_time, event_uid, crew_id, category, amount)

    def book(self, t, uid, crew_id, category, amount):
        self.rows.append((t, uid, crew_id, category, float(amount)))

    def total(self, warmup_end: float = 0.0) -> float:
        return sum(a for (t, *_, a) in self.rows if t >= warmup_end)

    def by_category(self, warmup_end: float = 0.0) -> dict:
        out: dict[str, float] = {}
        for (t, _uid, _cid, cat, amt) in self.rows:
            if t >= warmup_end:
                out[cat] = out.get(cat, 0.0) + amt
        return out


class EligibilityEngine:
    """FULL mode: eligibility is EMERGENT from state + surrogate rules.
    The realized eligible fraction is logged for validation vs. ~30%."""

    def __init__(self, legality: LegalitySurrogate):
        self.legality = legality
        self.samples: list[float] = []   # realized eligibility fractions

    def eligible_reserves(self, reserves_on_call: list[Crew],
                          o: OpenTimeItem, now: float) -> list[Crew]:
        # A reserve is "on call" if a RESERVE block covers the *duty window*
        # (not merely the moment of the phone call).
        pool = [r for r in reserves_on_call
                if any(b.btype == BlockType.RESERVE
                       for b in r.blocks_in(o.start, o.end))]
        elig = [r for r in pool if self.legality.check(r, o.start, o.end, o).legal]
        if pool:
            self.samples.append(len(elig) / len(pool))
        return elig


class DraftSelector:
    """Tier-first (impact on drafted crew), seniority-within-tier policy."""

    def __init__(self, policy: Policy, legality: LegalitySurrogate):
        self.p = policy
        self.legality = legality

    def select(self, roster: list[Crew], o: OpenTimeItem) -> Optional[Crew]:
        # There is NO cap on drafts per crew per month. A crew member may be
        # drafted as often as legality and their schedule permit -- drafting is
        # premium-paid work, not a burden to be rationed. drafts_this_month is
        # retained as a KPI (who earns the premium), never as a constraint.
        cands = [c for c in roster
                 if self.legality.check(c, o.start, o.end, o).legal]
        by_tier: dict[int, list[Crew]] = {}
        for c in cands:
            # No protected-block filter: every tier is reachable (see above).
            by_tier.setdefault(c.status_tier(o.start, o.end), []).append(c)
        # FIX (was D6): v2 sorted twice with the sense inverted, so BOTH
        # orderings selected the most junior crew -- meaning the only rule
        # Air Transat actually uses, senior-first, was implemented backwards,
        # and the bit-identical results made it impossible to notice.
        # seniority == 1 is the MOST senior crew member, so senior-first is
        # ascending seniority number.
        junior_first = self.p.seniority_order == "junior_first"
        for tier in (1, 2, 3, 4, 5):
            tier_list = by_tier.get(tier, [])
            if tier_list:
                tier_list.sort(key=lambda c: c.seniority, reverse=junior_first)
                return tier_list[0]
        return None


class CascadeEngine:
    """EMERGENT cascades: consume the StateDelta of a draft. Any pairing of the
    drafted crew that the new duty overlaps, or that the post-duty rest makes
    illegal, is removed and becomes a new OpenTimeItem. Realized cascade
    frequency is logged for validation vs. ~20%."""

    def __init__(self, legality: LegalitySurrogate):
        self.legality = legality
        self.n_drafts = 0
        self.n_cascading_drafts = 0

    def evaluate(self, crew: Crew, drafted: Block) -> list[Block]:
        self.n_drafts += 1
        broken: list[Block] = []
        rest_until = drafted.end + LegalitySurrogate.MIN_REST_MIN
        for b in list(crew.blocks):
            if b.btype != BlockType.PAIRING:
                continue
            # (a) the pairing overlaps the drafted duty, or
            # (b) it starts inside the mandatory rest that follows it
            if b.start < rest_until and b.end > drafted.start:
                crew.remove_block(b)
                broken.append(b)
        if broken:
            self.n_cascading_drafts += 1
        return broken

    @property
    def cascade_rate(self) -> float:
        return self.n_cascading_drafts / self.n_drafts if self.n_drafts else 0.0


# ----------------------------------------------------------------------------
# 6. SIMPY DES CORE
# ----------------------------------------------------------------------------

class IOCSimulation:
    def __init__(self, env: simpy.Environment, scenario: "Scenario",
                 policy: Policy, roster: list[Crew], reserves: list[Crew]):
        self.env = env
        self.scn = scenario
        self.p = policy
        self.roster = roster            # draftable line holders
        self.reserves = reserves        # reserve pool (Stage-1 sized)
        self.legality = LegalitySurrogate()
        self.elig = EligibilityEngine(self.legality)
        self.drafter = DraftSelector(policy, self.legality)
        self.cascade = CascadeEngine(self.legality)
        self.ledger = CostLedger()
        self._uid = 0
        self.uncovered = 0
        # Stage-1 cost: reserve guarantee, booked PER RESERVE PER DAY.
        # FIX (was D1): v2 booked the whole horizon as one row at t=0.0, which
        # the warm-up filter (t >= warmup_end) then discarded -- so the entire
        # fixed cost of the Stage-1 decision was missing from every reported
        # number, and E[C] fell monotonically in the reserve count.
        n_days = int(scenario.horizon_min // MIN_PER_DAY)
        for r in reserves:
            for d in range(n_days):
                self.ledger.book(d * MIN_PER_DAY, -1, r.crew_id,
                                 "RESERVE_STAFFING", policy.reserve_day_cost)

    def next_uid(self) -> int:
        self._uid += 1
        return self._uid

    # -- processes ------------------------------------------------------------
    def run(self):
        self.env.process(self.sick_call_source())
        self.env.run(until=self.scn.horizon_min)

    def sick_call_source(self):
        """Replays the scenario's pre-generated (CRN) sick-call event list."""
        for t_arrival, pairing in self.scn.sick_calls:
            yield self.env.timeout(max(0.0, t_arrival - self.env.now))
            o = OpenTimeItem(
                uid=self.next_uid(), pairing_id=pairing["id"],
                base=pairing["base"], fleet=pairing["fleet"],
                position=pairing["position"], start=pairing["start"],
                end=pairing["end"],
                deadline=pairing["start"],   # must cover by report time
                origin="SICK_CALL",
            )
            self.recovery_pipeline(o)

    def _assign(self, c: Crew, o: OpenTimeItem) -> Block:
        """Insert the duty + mandatory rest, consuming whatever non-duty block
        the crew member was on. Returns the inserted duty block.

        A RESERVE block is SPLIT around the duty + rest, not deleted: a reserve
        who flies one trip on day 3 is back on call on day 4. Deleting it would
        retire the reserve from the pool after a single use.
        """
        busy_until = o.end + LegalitySurrogate.MIN_REST_MIN
        for b in list(c.blocks_in(o.start, busy_until)):
            if b.btype == BlockType.RESERVE:
                c.remove_block(b)
                if b.start < o.start:
                    c.insert_block(Block(b.start, o.start, BlockType.RESERVE))
                if b.end > busy_until:
                    c.insert_block(Block(busy_until, b.end, BlockType.RESERVE))
            elif b.btype in CONSUMED_BY_DRAFT and b.start < o.end and b.end > o.start:
                c.remove_block(b)
        duty = Block(o.start, o.end, BlockType.DRAFTED_DUTY, o.pairing_id)
        c.insert_block(duty)
        c.insert_block(Block(o.end, busy_until, BlockType.REST))
        return duty

    def recovery_pipeline(self, o: OpenTimeItem):
        now = self.env.now
        # 1) try reserves (eligibility is emergent)
        elig = self.elig.eligible_reserves(self.reserves, o, now)
        if elig:
            # reserve-selection rule: shortest remaining on-call window
            def remaining(r: Crew) -> float:
                res = [b for b in r.blocks_in(o.start, o.end)
                       if b.btype == BlockType.RESERVE]
                return min(b.end for b in res)
            elig.sort(key=lambda r: (remaining(r), r.seniority))
            r = elig[0]
            self._assign(r, o)
            self.ledger.book(now, o.uid, r.crew_id, "RESERVE_UTILIZATION",
                             self.p.reserve_util_cost)
            return
        # 2) draft (tier-first, seniority-within-tier)
        c = self.drafter.select(self.roster, o)
        if c is not None:
            tier = c.status_tier(o.start, o.end)
            duty = self._assign(c, o)
            c.drafts_this_month += 1
            cost = self.p.base_draft_cost + self.p.tier_cost[tier]
            self.ledger.book(now, o.uid, c.crew_id, f"DRAFT_TIER{tier}", cost)
            # 3) emergent cascade: broken future pairings re-enter the queue
            for b in self.cascade.evaluate(c, duty):
                casc = OpenTimeItem(
                    uid=self.next_uid(), pairing_id=b.pairing_id or "casc",
                    base=o.base, fleet=o.fleet, position=o.position,
                    start=b.start, end=b.end, deadline=b.start,
                    origin="CASCADE",
                )
                self.env.process(self._delayed_pipeline(casc))
            return
        # 4) nothing feasible -> cancellation
        # (E8 not implemented: booked now, not held until the deadline.)
        self.uncovered += 1
        self.ledger.book(now, o.uid, None, "CANCELLATION", self.p.cancel_cost)

    def _delayed_pipeline(self, o: OpenTimeItem):
        # cascade disruptions surface when the IOC would see them (MVP: T-24h)
        visible_at = max(self.env.now, o.start - MIN_PER_DAY)
        yield self.env.timeout(visible_at - self.env.now)
        self.recovery_pipeline(o)


# ----------------------------------------------------------------------------
# 7. SCENARIO GENERATION (pre-materialized; identical across policies = CRN)
# ----------------------------------------------------------------------------

@dataclass
class Scenario:
    scenario_id: int
    horizon_min: float
    sick_calls: list[tuple]       # (arrival_time, pairing dict), time-ordered


def generate_scenario(scenario_id: int, seed: np.random.SeedSequence,
                      horizon_days: int = 28, base="YUL",
                      fleet="A321neoLR") -> Scenario:
    rng = ScenarioRNG(seed)
    sev = rng.stream("severity")
    sick = rng.stream("sick_calls")
    horizon = horizon_days * MIN_PER_DAY

    # daily severity regime (Markov chain, 4 states -> intensity multiplier)
    P = np.array([[.70, .25, .04, .01],
                  [.20, .60, .15, .05],
                  [.05, .30, .50, .15],
                  [.02, .18, .40, .40]])
    mult = np.array([0.5, 1.0, 2.0, 3.5])
    z = 1
    events = []
    for d in range(horizon_days):
        z = sev.choice(4, p=P[z])
        lam_day = 1.8 * mult[z]                      # calibrated in Phase 0
        n = sick.poisson(lam_day)
        for _ in range(n):
            t = d * MIN_PER_DAY + sick.uniform(0, MIN_PER_DAY)
            report = t + sick.uniform(2 * 60, 10 * 60)     # report 2-10h later
            events.append((t, {
                "id": f"P{scenario_id}-{len(events)}", "base": base,
                "fleet": fleet, "position": "FO",
                "start": report, "end": report + sick.uniform(6, 11) * 60,
            }))
    events.sort(key=lambda e: e[0])
    return Scenario(scenario_id, horizon, events)


def build_roster(seed: np.random.SeedSequence, n_line: int,
                 horizon_days=28, base="YUL", fleet="A321neoLR",
                 position="FO") -> list[Crew]:
    """Synthetic line-holder roster (replace with the D2 roster loader).
    NOTE: identical in every scenario by design -- the roster is a Stage-1
    given, so holding it fixed is part of the CRN pairing, not an oversight."""
    rng = np.random.default_rng(seed)
    roster = []
    for i in range(n_line):
        c = Crew(f"C{i:04d}", base, fleet, position, seniority=i + 1)
        t = 0.0
        while t < horizon_days * MIN_PER_DAY:
            btype = rng.choice(
                [BlockType.PAIRING, BlockType.DAY_OFF, BlockType.TRAINING,
                 BlockType.VACATION, BlockType.SIMULATOR],
                p=[.55, .33, .05, .05, .02])
            dur = rng.uniform(1, 4) * MIN_PER_DAY
            c.insert_block(Block(t, min(t + dur, horizon_days * MIN_PER_DAY),
                                 btype, pairing_id=f"L{i}-{int(t)}"))
            t += dur
        roster.append(c)
    return roster


def build_reserves(policy: Policy, horizon_days=28) -> list[Crew]:
    res = []
    for i in range(policy.n_reserves):
        r = Crew(f"R{i:03d}", "YUL", "A321neoLR", "FO", seniority=1000 + i)
        r.insert_block(Block(0.0, horizon_days * MIN_PER_DAY,
                             BlockType.RESERVE))
        res.append(r)
    return res


# ----------------------------------------------------------------------------
# 8. CRN POLICY EVALUATION LOOP
# ----------------------------------------------------------------------------

def evaluate_policy(policy: Policy, master_seed=20260704, n_scenarios=200,
                    horizon_days=28, warmup_days=7, cfg: Optional[dict] = None):
    """Evaluate one policy over the CRN scenario set. The SAME master seed
    (hence identical scenarios & rosters) must be used for every policy."""
    cfg = cfg or load_config()
    roster_size = cfg["population"]["roster_size"]
    scope = cfg["scope"]
    seeds = make_scenario_seeds(master_seed, n_scenarios)
    roster_seed = np.random.SeedSequence(master_seed + 1)  # shared across policies
    costs, elig_rates, casc_rates, uncov = [], [], [], []
    for i, s in enumerate(seeds):
        scn = generate_scenario(i, s, horizon_days)
        roster = build_roster(roster_seed, n_line=roster_size,
                              horizon_days=horizon_days,
                              base=scope["base"], fleet=scope["fleet"],
                              position=scope["position"])
        reserves = build_reserves(policy, horizon_days)
        sim = IOCSimulation(simpy.Environment(), scn, policy, roster, reserves)
        sim.run()
        costs.append(sim.ledger.total(warmup_end=warmup_days * MIN_PER_DAY))
        if sim.elig.samples:
            elig_rates.append(float(np.mean(sim.elig.samples)))
        casc_rates.append(sim.cascade.cascade_rate)
        uncov.append(sim.uncovered)
    c = np.array(costs)
    k = max(1, int(0.05 * len(c)))
    return {
        "policy_id": policy.policy_id,
        "E[cost]": float(c.mean()),
        "CVaR95": float(np.sort(c)[-k:].mean()),
        "std": float(c.std(ddof=1)),
        "mean_eligibility_rate": float(np.mean(elig_rates)) if elig_rates else None,
        "mean_cascade_rate": float(np.mean(casc_rates)),
        "mean_uncovered": float(np.mean(uncov)),
        "roster_size": roster_size,
        "costs": c,   # keep per-scenario vector for paired CRN comparison
    }


def compare_policies_crn(pa: Policy, pb: Policy, **kw):
    """Paired CRN comparison: identical scenarios -> low-variance difference."""
    kw.setdefault("cfg", load_config())
    ra, rb = evaluate_policy(pa, **kw), evaluate_policy(pb, **kw)
    diff = ra["costs"] - rb["costs"]              # PAIRED by scenario
    se = diff.std(ddof=1) / np.sqrt(len(diff))
    return ra, rb, {"mean_diff": float(diff.mean()),
                    "se_paired": float(se),
                    "t_stat": float(diff.mean() / se) if se > 0 else np.inf}


if __name__ == "__main__":
    cfg = load_config()
    A = Policy("R6-senior-first", n_reserves=6)
    B = Policy("R10-senior-first", n_reserves=10)
    ra, rb, cmp_ = compare_policies_crn(A, B, n_scenarios=100, cfg=cfg)
    print(f"scope={cfg['scope']['base']}/{cfg['scope']['fleet']}/"
          f"{cfg['scope']['position']}  roster_size={ra['roster_size']}")
    for r in (ra, rb):
        print(f"{r['policy_id']:>20}  E[C]={r['E[cost]']:>10,.0f}  "
              f"CVaR95={r['CVaR95']:>10,.0f}  "
              f"elig={r['mean_eligibility_rate']:.2f}  "
              f"cascade={r['mean_cascade_rate']:.2f}  "
              f"uncovered={r['mean_uncovered']:.1f}")
    print(f"\nPaired CRN diff (A-B): {cmp_['mean_diff']:,.0f} "
          f"± {1.96*cmp_['se_paired']:,.0f} (95% CI), t={cmp_['t_stat']:.1f}")

    # V9 sensitivity: is the recommendation stable in roster_size? (spec 9.2)
    print("\nroster_size sensitivity (V9):")
    for n in cfg["sensitivity"]["roster_size"]:
        probe = {**cfg, "population": {**cfg["population"], "roster_size": n}}
        best = min(((r, evaluate_policy(Policy(f"R{r}", n_reserves=r),
                                        n_scenarios=100, cfg=probe)["E[cost]"])
                    for r in (4, 6, 8, 10)), key=lambda t: t[1])
        print(f"  roster_size={n:>4}  ->  argmin E[C] at R={best[0]:>3}  "
              f"({best[1]:>9,.0f})")
