import csv
from collections.abc import Callable
from pathlib import Path
from typing import Any

import joblib
import yaml

from .. import config
from ..engine import des
from ..engine.policy import load_policy
from . import cascade_analytics, kpis


def load_grid_config(path: str | Path) -> list[str]:
    """The grid config's `policies:` list.

    S1e-04 scoped this to the R axis only -- reserve_selection and
    cross-base are confirmed inert at MVP scope (see configs/grid_mvp.yaml's
    own header comment and backlog story S1e-04b), so the grid has one real
    dimension: which policy file to run.
    """
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return list(data["policies"])


def _run_one_policy(
    cfg: config.BaseConfig,
    costs: Any,
    policy_name: str,
    n_scenarios: int,
    master_seed: str,
    on_scenario: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    policy = load_policy(config.policy_path(policy_name))
    sims = des.run_policy_crn(
        cfg, costs, policy, n_scenarios, master_seed, on_progress=on_scenario
    )
    result = kpis.compute_kpis(cfg, sims)
    result["policy_name"] = policy_name
    result["policy_id"] = policy.policy_id
    result["policy_hash"] = policy.get_hash()
    # WN-007: the other half of the reproducibility chain a policy_hash alone
    # doesn't carry -- which costs table this run priced against. IMP-612: the
    # file and version actually LOADED, not the policy's pin label (a bare pin
    # such as "costs_pilots.yaml" carries no version at all).
    result["costs_version"] = f"{cfg.costs_file}@{costs.version}"
    # The per-scenario vector, in scenario_id order, so callers can compute a
    # PAIRED difference between two policies (reporting/paired.py). The
    # aggregate KPIs above cannot support that -- a mean tells you nothing
    # about the scenario-by-scenario spread the pairing is designed to cancel.
    # A plain list[float]: picklable, so it survives the joblib boundary below.
    result["scenario_costs"] = des.measured_window_costs(cfg, sims)
    # Eligibility fractions, pooled, for the V3 verdict a caller reports
    # alongside the numbers (see cli.py::_print_v3_verdict for why every
    # surface that shows a cost must also show whether V3 validated it).
    result["eligibility_fractions"] = [f for sim in sims for f in sim.elig.get_distribution()]
    # Same construct kpis.py's cascade_rate_mean is built from (whole-simulation
    # counters, not window-filtered -- see its own comment for why), but as the
    # raw per-scenario list rather than just the mean, for a V4 verdict the same
    # way eligibility_fractions above feeds V3's.
    # Per-day outcome counts, one row per scenario. Aggregated HERE, while the
    # Simulation objects are still in memory: deriving them later would mean
    # re-running every scenario (~1.4s each), which is why the scenario
    # fingerprint strip could only show demand before this existed.
    #
    # Drafts and uncovered come from the ledger (a DRAFT_TIERn / CANCELLATION /
    # TERMINAL_PENALTY row IS the event). Cascades cannot: the ledger books the
    # same DRAFT_TIERn row whether or not the draft went on to break anything,
    # so the engine records the minute at the point it increments
    # n_cascading_drafts, and this only buckets it.
    result["daily_outcomes"] = [_daily_outcomes(cfg, sim) for sim in sims]
    result["cascade_rates"] = [
        sim.n_cascading_drafts / sim.n_drafts for sim in sims if sim.n_drafts > 0
    ]
    # Per-scenario raw counts (not rates/means) in scenario_id order, same
    # picklable-list convention as scenario_costs above -- what the scenario
    # distribution view (api/routers/processing.py's /scenarios endpoint)
    # needs to show a real per-scenario cascading-draft and uncovered-legs
    # figure next to each row, rather than only the grid-wide mean.
    result["scenario_cascading_drafts"] = [sim.n_cascading_drafts for sim in sims]
    # kpis.py's own uncovered_counts collapses this same per-scenario list to
    # a mean and discards it -- kpis.count_uncovered keeps the definition
    # (CANCELLATION at deadline, or TERMINAL_PENALTY still open at horizon
    # end) in one place while this keeps the list.
    result["scenario_uncovered_legs"] = [
        kpis.count_uncovered(des.rows_in_measurement_window(cfg, sim)) for sim in sims
    ]
    # Chain-level cascade economics (§5.7's amplification claim, measured).
    # Computed HERE for the same reason daily_outcomes above is: it needs
    # every scenario's full ledger, and the Simulation objects only exist
    # inside this function -- deriving it later would mean re-running the
    # whole scenario set. Returns plain dicts/floats, so it survives the
    # joblib boundary like every other key here.
    result["cascade_analytics"] = cascade_analytics.compute_cascade_analytics(cfg, sims)
    return result


_MINUTES_PER_DAY = 1440.0


def _daily_outcomes(cfg: config.BaseConfig, sim: Any) -> dict[str, list[int]]:
    """Per-horizon-day counts of what happened in one scenario.

    Parallel arrays of length `horizon_days`, not a list of per-day objects:
    50 scenarios x 42 days x 2 policies is 4,200 cells, and repeating the key
    names would be most of the payload.
    """
    days = cfg.horizon.horizon_days
    drafts = [0] * days
    cascading = [0] * days
    uncovered = [0] * days

    def bucket(minute: float) -> int | None:
        day = int(minute // _MINUTES_PER_DAY)
        # A terminal penalty is booked AT the horizon boundary, which floors to
        # one day past the last index; clamp rather than drop it.
        if day >= days:
            day = days - 1
        return day if day >= 0 else None

    for row in sim.ledger.rows:
        day = bucket(row.sim_time)
        if day is None:
            continue
        if row.category.startswith("DRAFT_TIER"):
            drafts[day] += 1
        elif row.category in kpis.UNCOVERED_CATEGORIES:
            uncovered[day] += 1

    for minute in sim.cascading_draft_minutes:
        day = bucket(minute)
        if day is not None:
            cascading[day] += 1

    return {"drafts": drafts, "cascading_drafts": cascading, "uncovered": uncovered}


def run_grid(
    cfg: config.BaseConfig,
    costs: Any,
    policy_names: list[str],
    n_scenarios: int,
    master_seed: str = "master",
    jobs: int = 1,
    on_progress: Callable[[int, int], None] | None = None,
    on_scenario_progress: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Every named policy run over the SAME CRN scenario set.

    "Paired" here needs no extra machinery: run_policy_crn already draws
    scenario i's sick-call arrivals from (master_seed, scenario_id) alone,
    never from the policy, so passing the same master_seed to every call in
    this loop is the whole pairing guarantee (S1d-04d) -- this is the
    property the story's fails_if is about (each combination regenerating
    its own scenarios would break it).

    Parallel across policies via joblib whenever `jobs != 1` (joblib's own
    convention: -1 = every core, -2 = all but one); each worker returns only
    a picklable KPI dict, never a Simulation, so nothing simpy-specific has
    to cross the process boundary. on_progress(done, total), if given, is
    called after each policy completes -- joblib doesn't stream partial
    results, so this fires from the main process after each result lands,
    not from inside the workers. Under parallelism it therefore reports one
    single jump to 100%, not per-policy progress.

    on_scenario_progress(done, total) is the FINER signal: it counts scenarios
    across the whole grid, not policies. Policy-level progress is useless for
    the common single-policy case -- one policy over 100 scenarios reports 0%
    for the entire run and then 100% -- because `_run_one_policy` never passed
    a callback down to run_policy_crn, which has reported per-scenario progress
    all along.

    It fires only on the sequential path. joblib pickles each delayed call into
    a separate process, so a callback closing over a database session or a
    stderr handle cannot cross that boundary; rather than silently dropping it,
    `parallel_hides_scenario_progress()` lets a caller check and say so.
    """
    # `jobs != 1`, not `jobs > 1`: joblib's own convention is that a NEGATIVE
    # n_jobs means "all cores" (-1) or "all but one" (-2), and `> 1` sent every
    # one of those down the sequential branch instead -- so `crewsim grid
    # --jobs -1`, which the flag's own help text advertises as "joblib
    # parallelism across policies", silently ran single-process. Zero is not a
    # valid n_jobs for joblib and is rejected rather than quietly treated as
    # sequential.
    if jobs == 0:
        raise ValueError("jobs=0 is not a valid parallelism setting (1 = sequential, -1 = all cores)")
    if jobs != 1:
        results = joblib.Parallel(n_jobs=jobs)(
            joblib.delayed(_run_one_policy)(cfg, costs, name, n_scenarios, master_seed)
            for name in policy_names
        )
        results = list(results)
        if on_progress is not None:
            on_progress(len(results), len(results))
    else:
        results = []
        total_scenarios = len(policy_names) * n_scenarios
        for name in policy_names:
            scenario_cb = None
            if on_scenario_progress is not None:
                # `already` is bound per policy, so scenario 7 of policy 2 in a
                # 3x100 grid reports 107/300 rather than restarting at 7.
                already = len(results) * n_scenarios

                def scenario_cb(done: int, _total: int, _base: int = already) -> None:
                    on_scenario_progress(_base + done, total_scenarios)

            results.append(
                _run_one_policy(cfg, costs, name, n_scenarios, master_seed, on_scenario=scenario_cb)
            )
            if on_progress is not None:
                on_progress(len(results), len(policy_names))
    return results


def parallel_hides_scenario_progress(jobs: int) -> bool:
    """True when `jobs` will suppress per-scenario progress reporting.

    Callers that show a progress bar need to know this to avoid presenting a
    bar that cannot move: under joblib the only signal is one jump to 100%.
    """
    return jobs != 1


_TABLE_COLUMNS = [
    ("policy_name", "Policy"),
    ("expected_cost", "E[cost]"),
    ("cvar95", "CVaR95"),
    ("uncovered_legs_mean", "Uncovered/scn"),
    ("reserve_dispatches_mean", "Dispatches/scn"),
    ("cascade_rate_mean", "Cascade rate"),
]


def print_grid_report(results: list[dict[str, Any]]) -> None:
    print(f"Grid report -- {len(results)} combination(s), CRN-paired against the same scenario set")
    header = "  " + "  ".join(f"{label:>16}" for _, label in _TABLE_COLUMNS)
    print(header)
    for row in results:
        cells = []
        for key, _ in _TABLE_COLUMNS:
            v = row[key]
            if key == "policy_name":
                cells.append(f"{v:>16}")
            elif v is None:
                cells.append(f"{'n/a':>16}")
            elif key in ("expected_cost", "cvar95"):
                cells.append(f"${v:>15,.0f}")
            else:
                cells.append(f"{v:>16.3f}")
        print("  " + "  ".join(cells))


def write_grid_csv(cfg: config.BaseConfig, results: list[dict[str, Any]]) -> Path:
    out_dir = config.ensure_dir(cfg, "reports_dir")
    path = out_dir / "grid_results.csv"
    fieldnames = ["policy_name", "policy_id", "policy_hash"] + [key for key, _ in _TABLE_COLUMNS[1:]]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow({k: row[k] for k in fieldnames})
    return path
