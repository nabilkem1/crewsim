import csv
from collections.abc import Callable
from pathlib import Path
from typing import Any

import joblib
import yaml

from .. import config
from ..engine import des
from ..engine.policy import load_policy
from . import kpis


def load_grid_config(path: str | Path) -> list[str]:
    """The grid config's `policies:` list.

    S1e-04 scoped this to the R axis only -- reserve_selection and
    cross-base are confirmed inert at MVP scope (see configs/grid_mvp.yaml's
    own header comment and backlog story S1e-04b), so the grid has one real
    dimension: which policy file to run.
    """
    data = yaml.safe_load(Path(path).read_text())
    return list(data["policies"])


def _policy_path(name_or_path: str) -> Path:
    p = Path(name_or_path)
    if p.is_file():
        return p
    return config.repo_root() / "configs" / "policies" / f"{name_or_path}.yaml"


def _run_one_policy(
    cfg: config.BaseConfig, costs: Any, policy_name: str, n_scenarios: int, master_seed: str
) -> dict[str, Any]:
    policy = load_policy(_policy_path(policy_name))
    sims = des.run_policy_crn(cfg, costs, policy, n_scenarios, master_seed)
    result = kpis.compute_kpis(cfg, sims)
    result["policy_name"] = policy_name
    result["policy_id"] = policy.policy_id
    result["policy_hash"] = policy.get_hash()
    return result


def run_grid(
    cfg: config.BaseConfig,
    costs: Any,
    policy_names: list[str],
    n_scenarios: int,
    master_seed: str = "master",
    jobs: int = 1,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Every named policy run over the SAME CRN scenario set.

    "Paired" here needs no extra machinery: run_policy_crn already draws
    scenario i's sick-call arrivals from (master_seed, scenario_id) alone,
    never from the policy, so passing the same master_seed to every call in
    this loop is the whole pairing guarantee (S1d-04d) -- this is the
    property the story's fails_if is about (each combination regenerating
    its own scenarios would break it).

    Parallel across policies via joblib (jobs>1); each worker returns only
    a picklable KPI dict, never a Simulation, so nothing simpy-specific has
    to cross the process boundary. on_progress(done, total), if given, is
    called after each policy completes -- joblib doesn't stream partial
    results, so this fires from the main process after each result lands,
    not from inside the workers.
    """
    if jobs > 1:
        results = joblib.Parallel(n_jobs=jobs)(
            joblib.delayed(_run_one_policy)(cfg, costs, name, n_scenarios, master_seed)
            for name in policy_names
        )
        results = list(results)
        if on_progress is not None:
            on_progress(len(results), len(results))
    else:
        results = []
        for name in policy_names:
            results.append(_run_one_policy(cfg, costs, name, n_scenarios, master_seed))
            if on_progress is not None:
                on_progress(len(results), len(policy_names))
    return results


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
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow({k: row[k] for k in fieldnames})
    return path
