"""Step-by-step review of a policy comparison.

Command debugged (default):
    crewsim compare --policies R6 R10 --scenarios 1

See tools/debug/stepper.py for the keys (F10/F11/Shift+F11) and env variables.
Extra variable for this driver:
    CREWSIM_BOOK_CATEGORIES  cost categories that make S19 stop (prefix match).
                             Default: CANCELLATION,TERMINAL_PENALTY,RESERVE_UTILIZATION,DRAFT_TIER
"""
from __future__ import annotations

import os
import sys

from stepper import Step, run  # tools/debug/ is on sys.path when this script is run

from crewsim.engine import (
    cascade,
    des,
    drafting,
    eligibility,
    events,
    ledger,
    legality,
    policy,
    roster_loader,
    sick_calls,
    terminal,
)
from crewsim.reporting import paired

# S19 is a hot path: only these categories stop (prefix match, so DRAFT_TIER
# covers DRAFT_TIER1..5). Scenario 0 often has no cancellation at all.
_BOOK_CATEGORIES = tuple(
    c.strip() for c in os.environ.get(
        "CREWSIM_BOOK_CATEGORIES", "CANCELLATION,TERMINAL_PENALTY,RESERVE_UTILIZATION,DRAFT_TIER",
    ).split(",") if c.strip()
)


def _interesting_cost(args: tuple, kwargs: dict) -> bool:
    # book(self, scenario_id, policy_id, sim_time, event_uid, root_event_uid, crew_id, category, amount)
    category = kwargs.get("category", args[7] if len(args) > 7 else None)
    return isinstance(category, str) and category.startswith(_BOOK_CATEGORIES)


STEPS: list[Step] = [
    Step("S01", policy, "load_policy",
         "Load a policy YAML (configs/policies/R*.yaml): how many SC/LC reserves per base/fleet/position."),
    Step("S02", des, "run_policy_crn",
         "Run ONE policy over N scenarios with common random numbers (same scenarios for both policies)."),
    Step("S03", des, "run_scenario",
         "Build and run one scenario: rosters, random streams, daily sick-call counts, SimPy run."),
    Step("S04", roster_loader, "load_rosters",
         "Read D1/D2/D3, convert to minute calendars, and carve the reserve pool out of the roster."),
    Step("S05", des, "_load_daily_sick_calls",
         "Daily sick-call counts for this scenario, from the scenario parquet (calibrated model)."),
    Step("S06", des.Simulation, "__init__",
         "Create the simulation: ledger, eligibility engine; books RESERVE_STAFFING and DELAY_AMBIENT."),
    Step("S07", sick_calls, "apply_sick_call",
         "A sick call: pick a crew member with a future pairing, break those pairings into open items."),
    Step("S08", des.Simulation, "recovery_pipeline",
         "An open item enters recovery: try now, else hold and retry, else cancel at the deadline."),
    Step("S09", des.Simulation, "_attempt_resolution",
         "One resolution attempt: local reserve -> cross-base reserve -> draft a line holder."),
    Step("S10", eligibility.EligibilityEngine, "eligible_reserves",
         "Which reserves are on call at report time AND legal for this item."),
    Step("S11", legality, "is_legal_assignment",
         "Legality rules L0..L8 for one crew member and one item (called many times)."),
    Step("S12", events, "assign_reserve",
         "Assign a reserve: split the RESERVE block, insert DRAFTED_DUTY + REST (+ DEADHEAD)."),
    Step("S13", des.Simulation, "_dispatch_cross_base",
         "No local reserve: try a reserve from another base, deadheaded in."),
    Step("S14", drafting, "select_draft_candidate",
         "No reserve at all: choose a line holder to draft (legal, lowest tier, senior-first)."),
    Step("S15", drafting, "determine_tier",
         "Impact tier 1..5 of drafting this crew member."),
    Step("S16", cascade, "compute_draft_delta",
         "Calendar change of the draft, and the future pairings it breaks (CASCADE items)."),
    Step("S17", cascade, "apply_delta",
         "Apply the draft to the crew calendar."),
    Step("S18", des.Simulation, "_delayed_pipeline",
         "A cascade/displaced item waits until it becomes visible, then enters recovery (S08)."),
    Step("S19", ledger.CostLedger, "book",
         "A cost row is booked (only the categories in CREWSIM_BOOK_CATEGORIES stop).",
         when=_interesting_cost),
    Step("S20", terminal, "evaluate_terminal_penalties",
         "End of horizon: items still open get a terminal penalty."),
    Step("S21", des, "measured_window_costs",
         "Per-scenario cost inside the measurement window (warm-up/cool-down excluded)."),
    Step("S22", paired, "paired_diff",
         "Paired difference between the two policies: mean, 95% CI, t-test."),
]


if __name__ == "__main__":
    sys.exit(run(STEPS, ["compare", "--policies", "R6", "R10", "--scenarios", "1"]))
