"""des — SimPy dispatch loop driving the real engine end-to-end (S1d-04c).

Single-scenario recovery pipeline: sick-call arrivals -> reserve/draft/cascade/
hold/cancel resolution -> terminal penalties at horizon end. Control-flow shape
is ported from crewsim_skeleton.py's IOCSimulation (reserve-first -> draft ->
cascade re-enqueue -> cancel); every simplified inline piece there (legality,
eligibility, draft selection, cascade, cost ledger) is replaced by the real
engine/* module. The multi-scenario CRN loop and the crewsim CLI rewiring are
S1d-04d, not here -- this proves the pipeline shape on one scenario first.

Only this module may import simpy (S0-00b's dependency rule).
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import importlib.metadata
import json
import math
import random
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import simpy
from scipy import stats

from .. import config
from . import crn
from .cascade import apply_delta, compute_draft_delta
from .costs import book_reserve_staffing
from .counterfactuals import select_myopic_total_cost
from .drafting import determine_tier, select_draft_candidate
from .eligibility import EligibilityEngine
from .events import assign_reserve
from .ledger import CostLedger, LedgerRow
from .legality import is_legal_assignment, min_rest_minutes
from .policy import Policy
from .sick_calls import apply_named_absence, apply_sick_call
from .state import BlockType, CrewMember, OpenTimeItem
from .terminal import evaluate_terminal_penalties


def _package_version() -> str:
    try:
        return importlib.metadata.version("crewsim")
    except Exception:  # noqa: BLE001 - a version-lookup failure must not crash the sim
        return "unknown"


def _load_sick_call_duration_params(cfg: config.BaseConfig) -> tuple[float, float]:
    """(shape, scale) of the S0-07 lognormal absence-duration fit for cfg.scope.season.

    Real calibrated data, not an invented constant -- see
    output/params/params_v*_<season>.json -> sick_call_nhpp.
    """
    params_dir = config.resolve(cfg, "params_dir")
    path = params_dir / f"params_v{_package_version()}_{cfg.scope.season}.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing calibrated parameter store for season {cfg.scope.season!r} at {path}. "
            "Run calibration first (S0-06/S0-07)."
        )
    store = json.loads(path.read_text())
    nhpp = store["sick_call_nhpp"]
    return nhpp["duration_lognorm_shape"], nhpp["duration_lognorm_scale"]


def _scenario_cache_path(cfg: config.BaseConfig, season: str, master_seed: str, n_scenarios: int) -> Path:
    """Same cache-key computation as scenarios/generator.py::generate_scenarios,
    duplicated rather than imported into: that function returns None on a cache
    hit instead of the path, so callers that just want "the file, generated if
    needed" have to reconstruct the path themselves either way."""
    from ..scenarios.generator import generate_scenarios

    generate_scenarios(cfg, season, master_seed, n_scenarios)  # ensures the cache exists

    params_dir = config.resolve(cfg, "params_dir")
    params_path = params_dir / f"params_v{_package_version()}_{season}.json"
    store = json.loads(params_path.read_text())
    content_hash = store.get("content_hash", "missing")
    # n_scenarios is part of the key -- see the matching comment in
    # generate_scenarios (S1d-04d) for why.
    cache_key = f"{master_seed}_{n_scenarios}_{content_hash}"
    h = hashlib.blake2b(cache_key.encode(), digest_size=16).hexdigest()
    return params_dir / "scenarios" / f"scenario_set_{h}.parquet"


def _load_daily_sick_calls(
    cfg: config.BaseConfig, season: str, master_seed: str, n_scenarios: int, scenario_id: int
) -> list[int]:
    """Real calibrated per-day sick-call counts for one scenario (scenarios/generator.py),
    not an inline re-derivation -- one count per horizon day, 0 where the cache has no row."""
    path = _scenario_cache_path(cfg, season, master_seed, n_scenarios)
    df = pl.read_parquet(path).filter(pl.col("scenario") == scenario_id).sort("day")
    horizon_days = cfg.horizon.horizon_days
    counts = [0] * horizon_days
    for row in df.iter_rows(named=True):
        if row["day"] < horizon_days:
            counts[row["day"]] = int(row["sick_calls"])
    return counts


class Simulation:
    """One scenario, one policy. Owns the ledger and the mutated crew copies,
    and drives one recovery-pipeline SimPy process per OpenTimeItem."""

    def __init__(
        self,
        env: simpy.Environment,
        cfg: config.BaseConfig,
        costs: Any,
        policy_id: str,
        scenario_id: int,
        roster: list[CrewMember],
        reserves: list[CrewMember],
        rng: np.random.Generator,
        horizon_minutes: float,
        trace: bool = False,
        draft_mode: str = "mandated",
        verbose_trace: bool = False,
        cascades_enabled: bool = True,
        cross_base_reserves: list[CrewMember] | None = None,
    ) -> None:
        if cfg.cascade is None:
            raise ValueError("Simulation requires cfg.cascade (visibility_lag_hours) to be configured")
        if cross_base_reserves and cfg.positioning is None:
            raise ValueError(
                "cross-base reserves were supplied but cfg.positioning is not configured -- "
                "dispatching one costs a deadhead seat and consumes duty time, and neither the "
                "duration nor the hotel rule may be assumed (configs/base.yaml -> positioning)"
            )
        self.env = env
        self.cfg = cfg
        # Narrows CascadeConfig | None to CascadeConfig once, here, rather than
        # re-asserting it in every method that needs visibility_lag_hours.
        self._cascade_cfg = cfg.cascade
        self.costs = costs
        self.policy_id = policy_id
        self.scenario_id = scenario_id
        self.roster = roster  # draftable line holders (own copies, mutated)
        self.reserves = reserves  # reserve pool (own copies, mutated)
        # S1c-07: reserves at OTHER bases, reachable only by deadheading them in
        # (§5.3's XB -> DH). Held separately from self.reserves on purpose --
        # they are not part of this policy's Stage-1 commitment, so they must not
        # be paid RESERVE_STAFFING here, must not be drawn for sick calls (the
        # arrival rate is calibrated for the in-scope population), and must not
        # count as servers in gate V2's Erlang-B comparison, whose offered load
        # `a` is measured against the in-scope establishment alone.
        self.cross_base_reserves = cross_base_reserves or []
        self.rng = rng
        self.horizon_minutes = horizon_minutes
        self.trace_enabled = trace
        self.trace: list[str] = []
        # S1e-06 (V5 trace export): recomputes and logs the FULL candidate
        # pool and rejection reasons for every reserve/draft decision, not
        # just the outcome -- real cost (extra is_legal_assignment calls per
        # decision), so it's a separate opt-in from `trace`, never set by
        # run_scenario/run_policy_crn's existing callers (report/drilldown's
        # trace=True must stay exactly as fast and as formatted as before).
        # Only replay.py's direct Simulation construction sets this True.
        self.verbose_trace = verbose_trace
        # S1e-05: NOT A RECOMMENDATION -- one of "mandated" (default, the
        # real senior-first tier order), "junior_first", or
        # "myopic_total_cost" (see counterfactuals.py). Never read from
        # Policy/Stage2Config (extra="forbid" keeps it off every policy
        # YAML), only ever set by the counterfactual analysis path.
        if draft_mode not in ("mandated", "junior_first", "myopic_total_cost"):
            raise ValueError(f"unknown draft_mode {draft_mode!r}")
        self.draft_mode = draft_mode

        self.ledger = CostLedger()
        # S1c-01 AC4: the mode comes from configs/base.yaml, not a literal.
        # It was hardcoded "FULL", which made REDUCED unreachable from every
        # real path and left `mode:` in base.yaml documenting a mode that did
        # not exist. p_elig likewise comes from config, not a default argument.
        self.elig = EligibilityEngine.from_config(cfg)
        self._uid = 0
        self.open_items: dict[int, OpenTimeItem] = {}
        self.n_drafts = 0
        self.n_cascading_drafts = 0
        # S1b-07 (gate V2): cascades disabled turns the recovery pipeline into a
        # pure loss system -- no secondary arrivals feeding back into the queue --
        # which is the configuration the Erlang-B comparison is defined against.
        self.cascades_enabled = cascades_enabled
        # Erlang-B observables, counted at the ARRIVAL instant only. "Blocked"
        # means an arriving item found no eligible reserve, which is the
        # loss-system event B(s, a) predicts; what happens next (draft, hold,
        # cancel) is the recovery pipeline's business, not the queue's.
        self.n_arrivals = 0
        self.n_blocked_on_arrival = 0
        self.n_reserve_assignments = 0
        self.reserve_service_minutes = 0.0
        # S1c-07: counted separately from n_reserve_assignments for the same
        # reason the pool is separate -- gate V2 divides assignments by the
        # in-scope establishment's on-call time, and folding cross-base rescues
        # into that numerator would inflate the offered load of a pool that
        # never served them.
        self.n_cross_base_assignments = 0

        self._book_reserve_staffing()

    def next_uid(self) -> int:
        self._uid += 1
        return self._uid

    def log(self, msg: str) -> None:
        if self.trace_enabled:
            self.trace.append(f"[t={self.env.now:.0f}] {msg}")

    # -- structural cost, booked once at construction, not event-driven -----
    def _book_reserve_staffing(self) -> None:
        """Delegates to engine/costs.py, the §4.2 module that owns cost booking.

        Thin on purpose: this class decides WHEN structural cost is booked (once,
        here, at construction); costs.py decides WHAT gets booked. Keeping the
        rule there is what lets tests/engine/test_costs.py exercise the same code
        the engine runs, rather than a second copy of it (S1a-04).
        """
        book_reserve_staffing(
            ledger=self.ledger,
            scenario_id=self.scenario_id,
            policy_id=self.policy_id,
            reserves=self.reserves,
            rates=self.costs.reserve.guarantee_per_day,
            horizon_minutes=self.horizon_minutes,
        )

    # -- processes ------------------------------------------------------------
    def sick_call_source(self, daily_counts: list[int]) -> Generator[simpy.Event, None, None]:
        """Drives sick-call arrivals from the real calibrated per-day counts.

        Per-event time-of-day and absence duration are CRN-derived (this
        scenario's own rng / a stable per-event seed), not fixed constants.
        """
        duration_shape, duration_scale = _load_sick_call_duration_params(self.cfg)
        all_crew = self.roster + self.reserves
        for day, count in enumerate(daily_counts):
            day_start = day * 1440.0
            if day_start > self.env.now:
                yield self.env.timeout(day_start - self.env.now)
            for i in range(count):
                current_time = day_start + float(self.rng.uniform(0, 1440.0))
                if current_time > self.env.now:
                    yield self.env.timeout(current_time - self.env.now)
                duration_days = float(
                    stats.lognorm.rvs(duration_shape, loc=0, scale=duration_scale, random_state=self.rng)
                )
                duration_days = max(self.cfg.calibration.sick_call_min_duration_days, duration_days)
                # apply_sick_call (S1b-04) samples via the stdlib random module,
                # not an injected Generator -- seed it from this scenario's CRN
                # stream so the draw stays reproducible without editing that module.
                seed = crn.stable_seed((self.scenario_id, "sick_call", day, i))
                random.seed(seed)
                sick_crew, items = apply_sick_call(
                    self.cfg, all_crew, current_time, duration_days, self._uid + 1
                )
                # sick_crew is None when no crew had a pairing to break; items is
                # then empty too, but narrow explicitly rather than relying on that.
                if items and sick_crew is not None:
                    self._uid += len(items)
                    for item in items:
                        self.log(f"SICK_CALL: {sick_crew.crew_id} -> item {item.uid} ({item.pairing_id})")
                        self.env.process(self.recovery_pipeline(item))

    def displaced_flying_source(
        self, displaced: list[tuple[CrewMember, Any]]
    ) -> Generator[simpy.Event, None, None]:
        """S1b-02 AC2: the flying reserve bidders gave up, offered as open time.

        Routed through _delayed_pipeline, so each item surfaces when the IOC
        would actually work it -- cascade.visibility_lag_hours before its own
        pairing -- rather than all at t=0.

        Emitting at t=0 was the first implementation and is wrong on two counts.
        Operationally, it means re-deciding a known-open trip at every reserve
        block start for weeks; the E8 hold exists for unexpected disruption, not
        for flying that has been open since the bid closed. Mechanically, it
        made each item retry across the whole horizon, which multiplied the
        legality checks per scenario by roughly two orders of magnitude and took
        the test suite from 4 minutes to 18.

        Before any of this the blocks were simply discarded, so a higher R
        carried no opportunity cost at all and R* was biased upward.
        """
        for crew, block in displaced:
            dl_hours = 0.0
            if self.cfg.demand is not None:
                raw = self.cfg.demand.uncovered_deadline_hours
                dl_hours = raw.get("default", 0.0) if isinstance(raw, dict) else float(raw)
            item = OpenTimeItem(
                uid=self.next_uid(),
                pairing_id=block.pairing_id or "UNKNOWN",
                base=crew.base,
                fleet=next(iter(crew.fleet_quals)) if crew.fleet_quals else "UNKNOWN",
                position=crew.position,
                start=block.start, end=block.end,
                deadline=block.start - (dl_hours * 60.0),
                origin="DISPLACED_LINE",
                root_event_uid=0,   # structural: caused by the bid, not by an event
                flight_mins=block.flight_mins,
            )
            self.log(f"DISPLACED_LINE: {crew.crew_id} bid reserve -> item {item.uid} ({item.pairing_id})")
            self.env.process(self._delayed_pipeline(item))
        return
        yield  # pragma: no cover - generator protocol; nothing to wait for

    def real_absence_source(self, absences: list[dict[str, Any]]) -> Generator[simpy.Event, None, None]:
        """S1e-06 (V5 replay): drives arrivals from REAL D4 absences (a
        real crew_id, a real [start_min, end_min) window) instead of
        sick_call_source's NHPP-drawn counts + random crew selection --
        only des.py may touch simpy (S0-00b), so this generator lives here
        even though replay.py owns loading the real absences themselves.
        """
        all_crew = self.roster + self.reserves
        for absence in sorted(absences, key=lambda a: a["notified_min"]):
            if absence["notified_min"] > self.env.now:
                yield self.env.timeout(absence["notified_min"] - self.env.now)
            crew, items = apply_named_absence(
                self.cfg, all_crew, absence["crew_id"], absence["start_min"], absence["end_min"], self._uid + 1
            )
            if items and crew is not None:
                self._uid += len(items)
                for item in items:
                    self.log(
                        f"REAL ABSENCE {absence['absence_id']} ({absence['absence_type']}): "
                        f"{crew.crew_id} -> item {item.uid} ({item.pairing_id})"
                    )
                    self.env.process(self.recovery_pipeline(item))
            elif crew is None:
                self.log(f"REAL ABSENCE {absence['absence_id']}: crew {absence['crew_id']} not in this window's roster")

    def recovery_pipeline(self, item: OpenTimeItem) -> Generator[simpy.Event, None, None]:
        self.open_items[item.uid] = item
        if self._attempt_resolution(item, first_attempt=True):
            return

        # E8: hold until the deadline, re-checking as reserves free up.
        # Re-check times are the reserve pool's own future RESERVE-block start
        # times up to the deadline -- derived from calendar data already
        # loaded, not an arbitrary polling interval.
        retry_times = sorted(
            {
                b.start
                for r in self.reserves
                for b in r.calendar
                if b.btype == BlockType.RESERVE and self.env.now < b.start <= item.deadline
            }
        )
        if not retry_times or retry_times[-1] < item.deadline:
            retry_times.append(item.deadline)

        for t in retry_times:
            if t > self.env.now:
                yield self.env.timeout(t - self.env.now)
            if item.uid not in self.open_items:
                return
            if self._attempt_resolution(item):
                return

        self.open_items.pop(item.uid, None)
        self.ledger.book(
            scenario_id=self.scenario_id, policy_id=self.policy_id,
            sim_time=self.env.now, event_uid=item.uid, root_event_uid=item.root_event_uid,
            crew_id=None, category="CANCELLATION", amount=self.costs.disruption.cancellation,
        )
        # S1b-06 AC2: statutory passenger compensation books at the deadline
        # alongside the airline's own cancellation cost -- a separate category
        # because it is a different payee and a different tariff. Which APPR
        # band a cancellation attracts is named in costs_pilots.yaml rather
        # than assumed here (passenger re-accommodation is not modelled).
        self.ledger.book(
            scenario_id=self.scenario_id, policy_id=self.policy_id,
            sim_time=self.env.now, event_uid=item.uid, root_event_uid=item.root_event_uid,
            crew_id=None, category="APPR_COMPENSATION",
            amount=self.costs.appr_compensation.on_cancellation,
        )
        self.log(f"item {item.uid} ({item.pairing_id}) CANCELLED at deadline, still uncovered")

    # -- S1c-07: cross-base dispatch and the positioning cost it incurs -------
    def _dispatch_cross_base(self, item: OpenTimeItem, now: float) -> bool:
        """§5.3's `XB` -> `DH`: borrow a reserve from another base, and pay for it.

        Returns True if the item was covered this way.

        The positioning trip is modelled by widening the assignment window
        rather than by bolting a cost onto an otherwise-unchanged assignment.
        Every legality question is then asked about the trip the crew member
        actually makes: L1 max duty counts the deadhead hours, L3/L4's rolling
        counters accumulate them, the RESERVE block has to cover the positioning
        as well as the flying, and L8 notice is measured to the POSITIONING
        report time -- so a call that arrives four hours before departure can no
        longer be answered from Toronto, which is the operationally right
        answer and one a cost-only implementation would get wrong.

        `self.cross_base_reserves` is empty unless the policy allows cross-base
        (run_scenario is the one place that knows the Policy, and it only loads
        the pool when stage2.allow_cross_base_reserve is set), so the emptiness
        check below IS the policy gate.
        """
        pos = self.cfg.positioning
        if not self.cross_base_reserves or pos is None:
            return False

        lead = pos.deadhead_duration_hours * 60.0
        positioned = dataclasses.replace(item, start=item.start - lead)
        if positioned.start < now:
            # No time left to fly them in. Not a legality failure -- the trip
            # would have to start in the past.
            return False

        # record=False: this pool's eligibility rate is another base's, and V3
        # measures cfg.scope's. See EligibilityEngine.eligible_reserves.
        elig = self.elig.eligible_reserves(
            self.cross_base_reserves, positioned, now, self.rng,
            record=False, is_deadhead=True,
        )
        if not elig:
            return False

        def remaining(r: CrewMember) -> float:
            covering = [
                b for b in r.blocks_in(positioned.start, positioned.end)
                if b.btype == BlockType.RESERVE
            ]
            return min((b.end for b in covering), default=float("inf"))

        elig.sort(key=lambda r: (remaining(r), r.seniority))
        chosen = elig[0]
        # min_rest is the AWAY figure by construction here (chosen.base is not
        # item.base), which min_rest_minutes already handles -- passing the real
        # bases rather than hardcoding keeps that one definition authoritative.
        min_rest = min_rest_minutes(self.cfg, chosen.base, item.base)
        assign_reserve(
            chosen, item.start, item.end, min_rest, item.pairing_id,
            deadhead_start=positioned.start,
        )
        self.n_cross_base_assignments += 1
        self.ledger.book(
            scenario_id=self.scenario_id, policy_id=self.policy_id,
            sim_time=now, event_uid=item.uid, root_event_uid=item.root_event_uid,
            crew_id=chosen.crew_id, category="RESERVE_UTILIZATION",
            amount=self.costs.reserve.utilisation,
        )
        positioning_cost = self._book_positioning(chosen, item, now)
        self.open_items.pop(item.uid, None)
        self.log(
            f"item {item.uid} ({item.pairing_id}) -> CROSS-BASE RESERVE "
            f"{chosen.crew_id} from {chosen.base} (deadhead {lead/60:.1f}h, "
            f"+${positioning_cost:,.0f} positioning)"
        )
        return True

    def _book_positioning(self, crew: CrewMember, item: OpenTimeItem, now: float) -> float:
        """Book §4.4.2's `q^pos` for a crew member who is not where the flight is.

        One rule for both paths §7.3 applies it to -- a deadheaded reserve and a
        drafted crew member away from the flight's station -- because it is one
        coefficient in the objective, not two.

        Returns the total booked, 0.0 when the crew member is already there.

        Known limit, stated rather than papered over: "away" is decided by
        `crew.base != item.base`, the only location this engine actually knows.
        That is exact for a cross-base reserve. It is NOT exact for §7.3's third
        worked example, the tier-1 draftee sitting in Punta Cana, because a
        draftee is always in-scope (drafting is base-local, §5.6) and therefore
        always scores 0 here. Making that case real needs down-route location
        tracking -- D3 carries `layover_stations` per pairing, so the data is
        there -- and that is a separate story, not an assumption to invent
        inside this one. The wiring is shared so that story only has to change
        how "away" is computed, not where the cost is booked.
        """
        pos = self.cfg.positioning
        if pos is None or crew.base == item.base:
            return 0.0

        # All three of §5.8's positioning categories. TRANSPORT was nameable but
        # unpriceable until the coefficient was added (§4.4.2 listed only the
        # first two), so the engine had a ledger category it could never book.
        total = 0.0
        for category, amount in (
            ("DEADHEAD", self.costs.positioning.deadhead),
            ("HOTEL", self.costs.positioning.hotel if pos.hotel_on_every_deadhead else 0.0),
            ("TRANSPORT",
             self.costs.positioning.transport if pos.transport_on_every_deadhead else 0.0),
        ):
            if amount <= 0.0:
                continue
            self.ledger.book(
                scenario_id=self.scenario_id, policy_id=self.policy_id,
                sim_time=now, event_uid=item.uid, root_event_uid=item.root_event_uid,
                crew_id=crew.crew_id, category=category, amount=amount,
            )
            total += amount
        return total

    def _attempt_resolution(self, item: OpenTimeItem, first_attempt: bool = False) -> bool:
        """Reserve-first, then draft. Returns True if the item is resolved.

        `first_attempt` marks the call made at the item's arrival instant, which
        is the only one gate V2 counts: Erlang B is about whether an ARRIVING
        call finds a free server, not whether a held one eventually does.
        """
        now = self.env.now

        elig = self.elig.eligible_reserves(self.reserves, item, now, self.rng)
        if first_attempt:
            self.n_arrivals += 1
            if not elig:
                self.n_blocked_on_arrival += 1
        if elig:
            def remaining(r: CrewMember) -> float:
                covering = [b for b in r.blocks_in(item.start, item.end) if b.btype == BlockType.RESERVE]
                return min((b.end for b in covering), default=float("inf"))

            elig.sort(key=lambda r: (remaining(r), r.seniority))
            chosen = elig[0]
            if self.verbose_trace and self.trace_enabled:
                self._log_reserve_alternatives(item, now, elig, chosen, remaining)
            min_rest = min_rest_minutes(self.cfg, chosen.base, item.base)
            assign_reserve(chosen, item.start, item.end, min_rest, item.pairing_id)
            # Occupancy this assignment costs the pool: the duty plus the rest it
            # obliges. That product with the arrival rate is the offered load `a`.
            self.n_reserve_assignments += 1
            self.reserve_service_minutes += (item.end - item.start) + min_rest
            self.ledger.book(
                scenario_id=self.scenario_id, policy_id=self.policy_id,
                sim_time=now, event_uid=item.uid, root_event_uid=item.root_event_uid,
                crew_id=chosen.crew_id, category="RESERVE_UTILIZATION",
                amount=self.costs.reserve.utilisation,
            )
            self.open_items.pop(item.uid, None)
            self.log(f"item {item.uid} ({item.pairing_id}) -> RESERVE {chosen.crew_id}")
            return True

        # S1c-07 / §5.3 `XB`: the local pool is empty. Before drafting, ask
        # whether the policy allows borrowing a reserve from another base and
        # whether one is actually available there. Deliberately AFTER the
        # blocked-on-arrival count above: V2's Erlang-B comparison is about the
        # in-scope establishment, and a cross-base rescue does not mean the
        # local pool had a free server.
        if self._dispatch_cross_base(item, now):
            return True

        if self.draft_mode == "myopic_total_cost":
            candidate = select_myopic_total_cost(self.roster, item, self.costs, self.cfg, now=now)
        else:
            candidate = select_draft_candidate(
                self.roster, item, junior_first=(self.draft_mode == "junior_first"), cfg=self.cfg, now=now
            )
        if candidate is not None:
            tier = determine_tier(candidate, item, self.cfg)
            if self.verbose_trace and self.trace_enabled:
                self._log_draft_alternatives(item, now, candidate, tier)
            delta, cascaded = compute_draft_delta(candidate, item, self.cfg, now)
            if not self.cascades_enabled:
                cascaded = []
            apply_delta(candidate, delta)
            self.n_drafts += 1
            if cascaded:
                self.n_cascading_drafts += 1
            # costs_pilots.yaml has 5 draft tiers (VACATION=4, SIMULATOR=5,
            # priced very differently: 2500 vs 4000); drafting.py's
            # determine_tier only distinguishes 4 (VACATION and SIMULATOR
            # both return tier 4). Known pre-existing mismatch (S1a-08 vs the
            # cost table) -- not resolved here, just not silently hidden:
            # SIMULATOR drafts are under-costed at today's tier-4 rate.
            cost = self.costs.draft.base_premium + self.costs.draft.tier.get(tier, 0.0)
            if tier in (3, 5):
                cost += self.costs.draft.train_reschedule
            self.ledger.book(
                scenario_id=self.scenario_id, policy_id=self.policy_id,
                sim_time=now, event_uid=item.uid, root_event_uid=item.root_event_uid,
                crew_id=candidate.crew_id, category=f"DRAFT_TIER{tier}", amount=cost,
            )
            # §7.3's draft term is `q^base + q^tier_k + q^pos`, not the first
            # two: a draftee who is not at the flight's station has to be
            # positioned like anyone else. Books $0 today for the reason set out
            # in _book_positioning -- shared wiring so it starts costing the
            # moment down-route location becomes knowable.
            cost += self._book_positioning(candidate, item, now)
            self.open_items.pop(item.uid, None)
            self.log(f"item {item.uid} ({item.pairing_id}) -> DRAFT {candidate.crew_id} tier{tier} (${cost:,.0f})")
            for casc in cascaded:
                # cascade.py creates these with uid=0 by design ("engine must
                # re-assign uid") -- give each a real one before it enters the
                # pipeline, or every cascade from this draft would collide.
                cascade_item = dataclasses.replace(casc, uid=self.next_uid())
                self.env.process(self._delayed_pipeline(cascade_item))
            return True

        if self.verbose_trace and self.trace_enabled:
            self.log(
                f"item {item.uid} ({item.pairing_id}): 0 eligible reserves, 0 legal draft candidates "
                f"at this check -- unresolved for now"
            )
        return False

    def _log_reserve_alternatives(
        self,
        item: OpenTimeItem,
        now: float,
        elig: list[CrewMember],
        chosen: CrewMember,
        remaining: Callable[[CrewMember], float],
    ) -> None:
        """S1e-06 (V5): who else was on-call and why they weren't chosen.

        `elig` (already legality-filtered by EligibilityEngine) is who was
        AVAILABLE; the pool of everyone structurally on-call (RESERVE block
        covering the whole duty window) minus `elig` is who was on-call but
        legally rejected -- recomputed here rather than exposed from
        EligibilityEngine, so its tested return shape is untouched.
        """
        pool = [
            r for r in self.reserves
            if any(
                b.btype == BlockType.RESERVE and b.start <= item.start and b.end >= item.end
                for b in r.blocks_in(item.start, item.end)
            )
        ]
        elig_ids = {r.crew_id for r in elig}
        considered = "; ".join(
            f"{r.crew_id} (remaining={remaining(r) / 60.0:.1f}h, seniority={r.seniority})" for r in elig
        )
        rejected_parts = []
        for r in pool:
            if r.crew_id in elig_ids:
                continue
            verdict = is_legal_assignment(r, item, now=now, cfg=self.cfg)
            rejected_parts.append(f"{r.crew_id} ({verdict.fail_rule}: {verdict.reason})")
        self.log(
            f"RESERVE alternatives for item {item.uid}: {len(pool)} on-call, {len(elig)} legally eligible "
            f"[{considered}] -> chose {chosen.crew_id} (shortest remaining window, seniority tiebreak); "
            f"rejected (on-call but illegal): {'; '.join(rejected_parts) if rejected_parts else 'none'}"
        )

    def _log_draft_alternatives(
        self, item: OpenTimeItem, now: float, chosen: CrewMember, chosen_tier: int
    ) -> None:
        """S1e-06 (V5): the tier breakdown considered before this draft --
        recomputes select_draft_candidate's own legality+tier grouping
        rather than changing its return type, matching how S1e-05's
        myopic_total_cost was kept out of drafting.py's own signature.

        Reports tier SIZES, not every candidate's name: a tier can hold
        dozens of legal day-off crew, and listing all of them tells an SME
        nothing an operational timeline should spend their hour on -- what
        matters is which tier was reached, how many were in it, and this
        candidate's rank within it (senior-first, so rank 1 of N means the
        most senior of N day-off candidates).
        """
        legal = [c for c in self.roster if is_legal_assignment(c, item, now=now, cfg=self.cfg).legal]
        by_tier: dict[int, list[CrewMember]] = {}
        for c in legal:
            by_tier.setdefault(determine_tier(c, item, self.cfg), []).append(c)
        sizes = ", ".join(f"tier{t}={len(by_tier[t])}" for t in sorted(by_tier))
        chosen_pool = sorted(by_tier[chosen_tier], key=lambda c: c.seniority)
        rank = chosen_pool.index(chosen) + 1 if chosen in chosen_pool else "?"
        empty_before = [t for t in range(1, chosen_tier) if t not in by_tier]
        skip_note = f"; tier(s) {empty_before} had no legal candidate" if empty_before else ""
        self.log(
            f"DRAFT alternatives for item {item.uid}: {len(legal)} legal candidates across "
            f"{len(by_tier)} tier(s) [{sizes}] -> chose {chosen.crew_id}, rank {rank} of "
            f"{len(chosen_pool)} in tier {chosen_tier} (lowest reachable tier, most senior first; "
            f"draft_mode={self.draft_mode!r}){skip_note}"
        )

    def _delayed_pipeline(self, item: OpenTimeItem) -> Generator[simpy.Event, None, None]:
        """Cascade items surface when the IOC would see them, per
        cascade.visibility_lag_hours -- not immediately (S1d-01's config
        existed but was never consumed anywhere until this story)."""
        lag_min = self._cascade_cfg.visibility_lag_hours * 60.0
        visible_at = max(self.env.now, item.start - lag_min)
        if visible_at > self.env.now:
            yield self.env.timeout(visible_at - self.env.now)
        self.log(f"cascade item {item.uid} ({item.pairing_id}) now visible")
        yield from self.recovery_pipeline(item)


def run_scenario(
    cfg: config.BaseConfig,
    costs: Any,
    policy: Policy,
    scenario_id: int = 0,
    master_seed: str = "master",
    n_scenarios: int = 1,
    trace: bool = False,
    draft_mode: str = "mandated",
    verbose_trace: bool = False,
    daily_sick_calls: list[int] | None = None,
    cascades_enabled: bool = True,
) -> Simulation:
    """Runs one CRN scenario for one policy through the real recovery pipeline.

    daily_sick_calls overrides the calibrated per-day arrival counts with a
    caller-supplied one-per-horizon-day list (S1a-10): gate V1's degeneracy
    configurations need a scenario with provably ZERO arrivals, which no
    master_seed is guaranteed to produce, and only this module may construct a
    simpy.Environment (S0-00b) so the gate cannot assemble one itself. None
    (the default, and every pre-existing caller) loads the real calibrated
    counts exactly as before.

    verbose_trace is forwarded to Simulation -- `explain-event` (S1b-04/S1b-06)
    needs the per-attempt "unresolved for now" lines to show that an item was
    HELD across retries rather than cancelled on arrival.
    """
    from .roster_loader import load_cross_base_reserves, load_rosters

    active, _ = load_rosters(
        cfg, base=cfg.scope.base, fleet=cfg.scope.fleet, position=cfg.scope.position, policy=policy
    )
    # copy.deepcopy, not dataclasses.replace: apply_delta/assign_reserve/
    # apply_sick_call all mutate crew.calendar in place, and replace() was
    # confirmed to silently drop roster_loader's dynamic _is_reserve attribute.
    active = copy.deepcopy(active)
    roster = [c for c in active if not getattr(c, "_is_reserve", False)]
    reserves = [c for c in active if getattr(c, "_is_reserve", False)]

    # S1c-07: §5.3's cross-base branch, and the ONLY place the policy's
    # allow_cross_base_reserve flag is read -- an empty pool downstream means
    # "not permitted" and "none exist" alike, which is the same no-op either way.
    cross_base: list[CrewMember] = []
    if policy.stage2.allow_cross_base_reserve:
        cross_base = copy.deepcopy(
            load_cross_base_reserves(
                cfg, home_base=cfg.scope.base, fleet=cfg.scope.fleet, position=cfg.scope.position
            )
        )

    streams = crn.generate_streams(master_seed, max(n_scenarios, scenario_id + 1))
    rng = np.random.default_rng(streams[scenario_id])

    if daily_sick_calls is not None:
        daily_counts = list(daily_sick_calls)
    else:
        daily_counts = _load_daily_sick_calls(cfg, cfg.scope.season, master_seed, n_scenarios, scenario_id)
    horizon_minutes = cfg.horizon.horizon_days * 1440.0

    env = simpy.Environment()
    sim = Simulation(
        env, cfg, costs, policy.policy_id, scenario_id, roster, reserves, rng, horizon_minutes,
        trace=trace, draft_mode=draft_mode, verbose_trace=verbose_trace,
        cascades_enabled=cascades_enabled, cross_base_reserves=cross_base,
    )
    # S1b-02 AC2: reserve bidders' displaced flying, if configured as open time.
    # Registered BEFORE the sick-call source so it is already on the queue when
    # the first absence arrives -- it was known weeks earlier.
    if cfg.population.displaced_flying == "open_time":
        displaced = [
            (crew, block)
            for crew in reserves
            for block in getattr(crew, "_displaced_pairings", [])
        ]
        if displaced:
            env.process(sim.displaced_flying_source(displaced))

    env.process(sim.sick_call_source(daily_counts))
    env.run(until=horizon_minutes)

    residual = list(sim.open_items.values())
    for category, amount, root_uid in evaluate_terminal_penalties(residual, costs):
        sim.ledger.book(
            scenario_id=scenario_id, policy_id=policy.policy_id, sim_time=horizon_minutes,
            event_uid=0, root_event_uid=root_uid, crew_id=None, category=category, amount=amount,
        )
    return sim


def run_historical_replay(
    cfg: config.BaseConfig,
    costs: Any,
    policy: Policy,
    roster: list[CrewMember],
    reserves: list[CrewMember],
    absences: list[dict[str, Any]],
    horizon_minutes: float,
    trace: bool = True,
    verbose_trace: bool = True,
    cross_base_reserves: list[CrewMember] | None = None,
) -> Simulation:
    """The historical-replay analogue of run_scenario -- same Simulation
    class, same recovery_pipeline, but the arrival source is
    real_absence_source (real D4 absences) instead of sick_call_source (NHPP
    draws). roster/reserves/absences are prepared by replay.py (real
    calendar-anchored data has no CRN scenario_id/master_seed to key off),
    which must not import simpy itself (S0-00b) -- so the env/Simulation
    construction and the actual env.run() live here.

    Period-agnostic: horizon_minutes is whatever span roster/reserves/
    absences were prepared for -- S1e-06 (V5) uses one real week, S1e-07
    (V6) uses one real calendar month (aligned to D7's pay_period), same
    function either way.

    trace/verbose_trace default True (S1e-06's original behaviour,
    unaffected by this generalisation): replaying one specific real week
    for an SME walkthrough is exactly the "show every alternative
    considered" use case verbose_trace exists for, at a scale where the
    extra legality recomputation cost is negligible. S1e-07's month-long
    backtest only needs ledger totals, not a readable timeline, so it
    passes both False.
    """
    env = simpy.Environment()
    rng = np.random.default_rng(0)  # FULL-mode EligibilityEngine (the only mode this replay uses) never draws from it
    sim = Simulation(
        env, cfg, costs, policy.policy_id, scenario_id=0, roster=roster, reserves=reserves,
        rng=rng, horizon_minutes=horizon_minutes, trace=trace, verbose_trace=verbose_trace,
        # S1c-07: without this the replay path silently has no cross-base pool,
        # so gate V6's simulated positioning total would be a structural $0.00
        # printed next to D10's real invoices -- a line that looks like a
        # measurement and can never be non-zero.
        cross_base_reserves=cross_base_reserves,
    )
    env.process(sim.real_absence_source(absences))
    env.run(until=horizon_minutes)

    residual = list(sim.open_items.values())
    for category, amount, root_uid in evaluate_terminal_penalties(residual, costs):
        sim.ledger.book(
            scenario_id=0, policy_id=policy.policy_id, sim_time=horizon_minutes,
            event_uid=0, root_event_uid=root_uid, crew_id=None, category=category, amount=amount,
        )
    return sim


def run_policy_crn(
    cfg: config.BaseConfig,
    costs: Any,
    policy: Policy,
    n_scenarios: int,
    master_seed: str = "master",
    on_progress: Callable[[int, int], None] | None = None,
    trace: bool = False,
    draft_mode: str = "mandated",
) -> list[Simulation]:
    """S1d-04d: one policy across n_scenarios CRN-paired scenarios.

    "Paired" means scenario i's sick-call arrival draws (day, time-of-day,
    duration) are identical for every policy run with this master_seed --
    crn.generate_streams/_load_daily_sick_calls key off (master_seed,
    scenario_id) only, never policy -- so a cost difference between two
    policies reflects the policy's roster/reserve composition, not luck.

    on_progress(done, total), if given, is called after every scenario --
    this loop has no other visible output, and a run of hundreds of
    scenarios (S1e-01's own manual check runs 500) can otherwise look
    identical whether it's progressing normally or stuck. Optional and
    None by default: every existing caller (gate v3/v4/v9, compare,
    report) is unaffected.

    trace=True (S1e-03: exemplar-scenario drill-down) records each
    Simulation's own readable event log (Simulation.trace) -- off by
    default since it's wasted memory for large N when nobody reads it
    (e.g. S1e-01's own 500-scenario KPI run).

    draft_mode (S1e-05): NOT A RECOMMENDATION -- "mandated" (default) is
    the only mode any real policy comparison (run/compare/grid/report) may
    use; "junior_first"/"myopic_total_cost" exist solely for the
    `counterfactual` CLI path to price the mandated drafting rule.
    """
    sims = []
    for i in range(n_scenarios):
        sims.append(run_scenario(cfg, costs, policy, scenario_id=i, master_seed=master_seed,
                                  n_scenarios=n_scenarios, trace=trace, draft_mode=draft_mode))
        if on_progress is not None:
            on_progress(i + 1, n_scenarios)
    return sims


def measurement_window_bounds(cfg: config.BaseConfig) -> tuple[float, float]:
    """(warmup_end, measurement_end) in engine minutes -- the boundary S1e-01's
    whole attribution rule is built around (spec Sec5.0.5)."""
    warmup_end = cfg.horizon.warmup_days * 1440.0
    measurement_end = (cfg.horizon.warmup_days + cfg.horizon.measurement_days) * 1440.0
    return warmup_end, measurement_end


def rows_in_measurement_window(cfg: config.BaseConfig, sim: Simulation) -> list[LedgerRow]:
    """The ledger rows attributed to `sim`'s measurement window (S1e-01,
    spec Sec5.0.5): a row counts if it's BOOKED inside the measurement window,
    or if it's booked during cool-down but its causal chain ORIGINATES inside
    the measurement window ("costs attributed back... if their causal chain
    originates there" -- root_event_uid is what makes that traceable).
    Warm-up-booked rows are always excluded; cool-down rows whose chain
    originates in warm-up or in cool-down itself are excluded too.

    A chain's origin is the earliest sim_time among all ledger rows sharing
    its root_event_uid -- derived purely from the ledger, no extra engine
    tracking needed (ledger.py's own stated design). root_event_uid == 0 is
    NOT a shared chain: it's the sentinel des.py uses for costs with no
    causal chain at all (e.g. RESERVE_STAFFING, booked daily regardless of
    any OpenTimeItem) -- grouping those together would wrongly collapse many
    independent background bookings into one fake shared origin, so each
    root_event_uid==0 row uses its own sim_time as its own origin instead.

    This is the single shared attribution rule behind both
    `measured_window_costs` (dollar totals) and the reporting KPIs (S1e-01:
    uncovered legs, reserve utilisation, draft distribution) -- one
    definition of "in the measurement window", not a dollar-only one and a
    separately-invented count-only one.
    """
    warmup_end, measurement_end = measurement_window_bounds(cfg)

    root_origin: dict[int, float] = {}
    for row in sim.ledger.rows:
        if row.root_event_uid == 0:
            continue
        prev = root_origin.get(row.root_event_uid)
        if prev is None or row.sim_time < prev:
            root_origin[row.root_event_uid] = row.sim_time

    result = []
    for row in sim.ledger.rows:
        if warmup_end <= row.sim_time < measurement_end:
            result.append(row)
        elif row.sim_time >= measurement_end:
            origin = row.sim_time if row.root_event_uid == 0 else root_origin[row.root_event_uid]
            if warmup_end <= origin < measurement_end:
                result.append(row)
    return result


def measured_window_costs(cfg: config.BaseConfig, sims: list[Simulation]) -> list[float]:
    """Per-scenario total cost attributed to the measurement window --
    sum(amount) over `rows_in_measurement_window` (see its docstring for the
    attribution rule).

    Fixed 2026-08-07 (S1e-01): the previous version (min_time=warmup_end, no
    max_time) treated EVERY cool-down-booked row as in-window, including
    ones whose root event is a brand-new sick call that itself arrived
    during cool-down (cfg.horizon.horizon_days worth of arrivals are
    generated for every scenario, cool-down included -- a known, separate
    S1d-04c limitation, not fixed here, see its own note). Measured directly
    against real data before fixing: 15-33% of the old figure, across 5 real
    R6 scenarios, was cool-down-originated cost that should never have
    counted -- not a rounding difference.
    """
    return [sum(row.amount for row in rows_in_measurement_window(cfg, sim)) for sim in sims]


def cvar95(scenario_costs: list[float]) -> float:
    """Conditional Value at Risk at 95%: mean of the worst 5% of scenario
    costs. A closed-form tail statistic (this function's own definition), not
    a business input. Needs enough scenarios that "worst 5%" is more than one
    point -- meaningless much below ~20 scenarios."""
    if not scenario_costs:
        return 0.0
    ordered = sorted(scenario_costs, reverse=True)
    tail_n = max(1, math.ceil(len(ordered) * 0.05))
    return sum(ordered[:tail_n]) / tail_n
