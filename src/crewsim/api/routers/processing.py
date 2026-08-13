"""Simulation processing jobs.

This router runs real work: `run_processing_job` calls `reporting.grid.run_grid`
for CRN-paired scenarios across policies and reports the scoreboard it returns.

Four endpoints that did no real work have been removed. `/prediction` returned
`random.randint(60, 3600)` seconds and `random.uniform(0.5, 10.0)` dollars as a
cost estimate; `/profiling` returned a hardcoded bottleneck breakdown
("Database I/O 45%") measured from nothing; `/config/output` and
`/config/hardware` accepted settings, persisted nothing, and answered
`{"status": "success"}`.
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from crewsim.api.db import Job, SessionLocal, get_db
from crewsim.api.runlog import RunLog
from crewsim.api.streaming import stream_job

router = APIRouter(prefix="", tags=["Processing"])

_PERCENT = 100
_STATUS_LIMIT = 10
_PROCESSING_TYPES = ("processing_single", "processing_batch")

# The four steps the execution log reports. Structural, like the CRN master
# seed below, which matches the CLI's own default so a UI run and
# `crewsim grid --master-seed master` are the same run.
_TOTAL_STEPS = 4
_MASTER_SEED = "master"


class JobCancelled(RuntimeError):
    """Raised inside a progress callback when the job row has been cancelled.

    A distinct type, not a bare RuntimeError: the generic handler below turns
    any exception into status="failed", so a cancelled run used to be reported
    as a FAILURE with "Job cancelled" as its error. A user who pressed Cancel
    should not have to wonder whether something broke.
    """


def _pairwise_comparisons(raw_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Paired CRN difference for every policy pair in the run.

    Uses the per-scenario cost vectors `run_grid` now returns, through the same
    `reporting.paired.paired_diff` the CLI's `compare` command calls -- so the
    UI and the CLI cannot report different differences for the same inputs.
    """
    from crewsim.reporting.paired import format_paired_diff, paired_diff

    comparisons = []
    for i, a in enumerate(raw_results):
        for b in raw_results[i + 1 :]:
            costs_a = a.get("scenario_costs") or []
            costs_b = b.get("scenario_costs") or []
            if len(costs_a) != len(costs_b):
                continue
            result = paired_diff(costs_a, costs_b)
            comparisons.append(
                {
                    "policy_a": a["policy_name"],
                    "policy_b": b["policy_name"],
                    "summary": format_paired_diff(a["policy_name"], b["policy_name"], result),
                    **result,
                }
            )
    return comparisons


def _v3_verdict(cfg: Any, raw_results: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Gate V3's verdict on the eligibility this run produced.

    S1c-05 AC3's rule -- "a number failing V3 must never reach a planner
    silently" -- applies to this surface exactly as it does to `crewsim run`,
    which prints the same verdict. Pooled across every policy in the grid: if
    any side's eligibility is unvalidated, comparisons between them are too.

    Returns None when the run produced no eligibility events at all, which is
    itself reported rather than shown as a pass.
    """
    from crewsim.gates.v3_eligibility import run_v3_gate

    fractions = [f for r in raw_results for f in (r.get("eligibility_fractions") or [])]
    if not fractions:
        return None

    result = run_v3_gate(cfg, fractions, window="holdout")
    band = f"[{result['ci_lower']:.2f}, {result['ci_upper']:.2f}]"
    if result["pass"]:
        message = (
            f"Gate V3 PASS: eligibility {result['sim_mean']:.2f} is within the "
            f"historical band {band} ({len(fractions):,} events)."
        )
    else:
        message = (
            f"eligibility rate {result['sim_mean']:.2f} is outside the validation "
            f"band {band} - see V3. These figures are UNVALIDATED. "
            f"Suspect mechanism: reserve rotation or L8 notice time."
        )
    return {
        "pass": bool(result["pass"]),
        "sim_mean": result["sim_mean"],
        "ci_lower": result["ci_lower"],
        "ci_upper": result["ci_upper"],
        "gap": result["gap"],
        "n_events": len(fractions),
        "message": message,
    }


def _v4_verdict(cfg: Any, raw_results: list[dict[str, Any]]) -> dict[str, Any] | None:
    """WN-006: gate V4's verdict on the cascade (domino) rate this run
    produced -- the other half of spec Sec9.3 item 4's "Usability AND Domino
    rates" reality-check pair, mirroring _v3_verdict's own pattern exactly so
    the two banners can share one component on the frontend.

    Returns None when no scenario in this run produced a single draft, which
    is itself reported rather than rendered as a pass -- run_v4_gate's own
    INCONCLUSIVE verdict already carries the real reason (see its blockers).
    """
    from crewsim.gates.v4_cascade import run_v4_gate

    rates = [r for res in raw_results for r in (res.get("cascade_rates") or [])]
    if not rates:
        return None

    result = run_v4_gate(cfg, rates, window="holdout")
    band = f"[{result['ci_lower']:.3f}, {result['ci_upper']:.3f}]"
    if result["verdict"] == "INCONCLUSIVE":
        message = (
            f"Gate V4 INCONCLUSIVE: no comparison could be made ({'; '.join(result['blockers'])}). "
            f"This is not a pass."
        )
    elif result["pass"]:
        message = (
            f"Gate V4 PASS: cascade rate {result['sim_mean']:.3f} is within the "
            f"historical band {band} ({result['n_hist_drafts']:,} reconstructed drafts)."
        )
    else:
        message = (
            f"cascade rate {result['sim_mean']:.3f} is outside the validation band {band} - see V4. "
            f"These figures are UNVALIDATED. Suspect mechanism: visibility lag, rule implementations, "
            f"or base composition."
        )
    return {
        "pass": bool(result["pass"]),
        "verdict": result["verdict"],
        "sim_mean": result["sim_mean"],
        "ci_lower": result["ci_lower"],
        "ci_upper": result["ci_upper"],
        "gap": result["gap"],
        "n_events": len(rates),
        "message": message,
    }


# joblib's convention: 1 = sequential, -1 = every core, -2 = all but one.
# Default 1 because these workers run inside the API process -- parallelism is
# the caller's explicit choice, not something to spend the server's cores on
# by default.
_JOBS_DESCRIPTION = "joblib parallelism across policies: 1 = sequential, -1 = all cores"


class RunRequest(BaseModel):
    config_id: str
    num_scenarios: int = Field(default=100, ge=1)
    season: str | None = None
    jobs: int = Field(default=1, description=_JOBS_DESCRIPTION)


class BatchRunRequest(BaseModel):
    config_ids: list[str] = Field(min_length=1)
    num_scenarios: int = Field(default=100, ge=1)
    season: str | None = None
    jobs: int = Field(default=1, description=_JOBS_DESCRIPTION)


def run_processing_job(
    job_id: str,
    config_ids: list[str],
    num_scenarios: int,
    season: str | None = None,
    jobs: int = 1,
) -> None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        job.status = "running"
        db.commit()

        from crewsim import config
        from crewsim.reporting.grid import parallel_hides_scenario_progress, run_grid
        from crewsim.reporting.provenance import format_params_provenance, params_provenance

        def flush(entries: list[dict[str, Any]]) -> None:
            # Reassign, don't mutate: SQLAlchemy's JSON column tracks identity,
            # so appending in place would not be detected as a change and the
            # stream would show nothing until the job ended.
            job.log = entries
            db.commit()

        runlog = RunLog(total_steps=_TOTAL_STEPS, flush=flush)

        # ---------------------------------------------------- [1/4] parameters
        runlog.start("loading parameter store")
        cfg = config.load()
        costs = config.load_costs(cfg)

        # An explicit season. This used to sniff substrings out of a filename
        # ("W26" in calibration_file), so any name not containing a known season
        # silently kept whatever the config already had.
        #
        # model_copy, not assignment: the config models are frozen
        # (config.py `ConfigDict(..., frozen=True)`), so `cfg.scope.season = ...`
        # raises. The previous code did exactly that, and the bare `except`
        # below turned it into a failed job with a pydantic error attached --
        # so passing a calibration file whose name did contain "W26" was the
        # one way to break this endpoint.
        if season is not None:
            cfg = cfg.model_copy(update={"scope": cfg.scope.model_copy(update={"season": season})})

        params_version, params_hash = params_provenance(cfg)
        runlog.done(
            f"{format_params_provenance(params_version, params_hash)} season={cfg.scope.season}"
        )
        if params_version == "MISSING":
            # Reported, not smoothed over: this is what a checkout looks like
            # before `crewsim calibrate --emit` has run for this season, and the
            # run below will fail on it. Saying so here makes that failure legible.
            runlog.note(f"No parameter store for season {cfg.scope.season}.", level="warning")

        # ------------------------------------------------------ [2/4] scenarios
        runlog.start(f"generating {num_scenarios} scenarios from master seed {_MASTER_SEED!r}")
        # Scenario generation is not a separate pass -- run_policy_crn draws
        # scenario i's arrivals inside the evaluation loop from
        # (master_seed, scenario_id). This step records the CRN configuration
        # the next step will use rather than timing a phase that does not exist
        # as one.
        runlog.done(
            f"{num_scenarios} CRN-paired scenario(s); arrivals keyed on "
            f"(master_seed, scenario_id) only, so every policy sees the same set"
        )

        # ----------------------------------------------------- [3/4] evaluation
        parallel = parallel_hides_scenario_progress(jobs)
        total_scenarios = len(config_ids) * num_scenarios
        runlog.start(
            f"evaluating {len(config_ids)} polic{'y' if len(config_ids) == 1 else 'ies'} "
            f"x {num_scenarios} scenarios"
            + ("" if jobs == 1 else f" (joblib, n_jobs={jobs})"),
            detail=(
                f"per-scenario progress is unavailable under joblib "
                f"(n_jobs={jobs}); {total_scenarios:,} scenarios total"
                if parallel
                else f"scenario 0 of {total_scenarios:,}"
            ),
        )

        def scenario_progress(done: int, total: int) -> None:
            """Per-scenario progress across the whole grid.

            This is the signal a progress bar needs. Policy-level progress
            cannot drive one in the common single-policy case: one policy over
            100 scenarios sits at 0% for the entire run and then jumps to 100%.
            """
            db.refresh(job)
            if job.status == "cancelled":
                # Raised from inside run_grid's scenario loop, so the DES stops
                # at the next scenario boundary rather than finishing the grid.
                raise JobCancelled(f"Cancelled after {done:,} of {total:,} scenarios")
            job.progress = int((done / total) * _PERCENT)
            runlog.progress(done, total, f"scenario {done:,} of {total:,}")
            db.commit()

        def policy_progress(done: int, total: int) -> None:
            db.refresh(job)
            if job.status == "cancelled":
                raise JobCancelled(f"Cancelled after {done:,} of {total:,} policies")
            job.progress = int((done / total) * _PERCENT)
            db.commit()

        raw_results = run_grid(
            cfg=cfg,
            costs=costs,
            policy_names=config_ids,
            n_scenarios=num_scenarios,
            master_seed=_MASTER_SEED,
            jobs=jobs,
            on_progress=policy_progress,
            # Dropped by run_grid under joblib -- workers are separate
            # processes and this closes over a database session. The step's
            # detail says so, rather than showing a bar that cannot move.
            on_scenario_progress=None if parallel else scenario_progress,
        )
        runlog.done(
            f"{len(raw_results)} polic{'y' if len(raw_results) == 1 else 'ies'} evaluated "
            f"({'sequential' if jobs == 1 else 'joblib'}, n_jobs={jobs})"
        )

        # -------------------------------------------------- [4/4] scoreboard
        runlog.start("building scoreboard")
        scoreboard = [
            {
                "policy": r["policy_name"],
                "policy_id": r.get("policy_id"),
                "policy_hash": r.get("policy_hash"),
                "costs_version": r.get("costs_version"),
                "expected_cost": r.get("expected_cost"),
                "cvar95": r.get("cvar95"),
                "elig": r.get("eligibility_mean"),
                "casc": r.get("cascade_rate_mean"),
                "uncovered": r.get("uncovered_legs_mean"),
                # WN-002: real ledger-category breakdown -- see kpis.py's own
                # note on why this always sums back to expected_cost.
                "cost_by_category": r.get("cost_by_category"),
                # WN-003: dispatches / real RESERVE_STAFFING rows booked, not
                # a headcount parsed from the policy filename.
                "reserve_dispatches_mean": r.get("reserve_dispatches_mean"),
                "reserve_staffing_days_mean": r.get("reserve_staffing_days_mean"),
                "utilization_rate": r.get("utilization_rate"),
                # WN-004: None until configs/base.yaml's service_level is a
                # real (non-[CONFIRM]) figure -- kpis.py already refuses to
                # fabricate a verdict when cfg.service_level is unset.
                "service_level": r.get("service_level"),
                # The per-scenario cost vector, in scenario_id order. Already
                # computed for the paired comparison and previously discarded
                # after it; kept so a reader can see the DISTRIBUTION behind
                # E[C] and CVaR95 rather than only their two summary values.
                # 50 floats per policy -- small next to the rest of this row.
                "scenario_costs": r.get("scenario_costs"),
                # Per-scenario, per-day counts of drafts / cascading drafts /
                # uncovered legs. Aggregated during the run (grid.py) because
                # deriving it afterwards would mean re-running every scenario.
                "daily_outcomes": r.get("daily_outcomes"),
                # Same per-scenario-vector convention, for the scenario
                # distribution view (GET /scenarios below): real per-scenario
                # cascading-draft and uncovered-legs counts, not just the
                # grid-wide means above.
                "scenario_cascading_drafts": r.get("scenario_cascading_drafts"),
                "scenario_uncovered_legs": r.get("scenario_uncovered_legs"),
                # Chain-level cascade economics for the Cascade Analytics tab
                # (reporting/cascade_analytics.py). Rides along with this job
                # rather than getting a job type of its own: it needs the same
                # CRN scenario set the scoreboard's own numbers came from, and
                # recomputing it separately would both cost a second full run
                # and risk quoting cascade figures from a different draw than
                # the E[C] displayed beside them.
                "cascade_analytics": r.get("cascade_analytics"),
            }
            for r in raw_results
        ]
        comparisons = _pairwise_comparisons(raw_results)
        v3 = _v3_verdict(cfg, raw_results)
        v4 = _v4_verdict(cfg, raw_results)

        # Computed here, with THIS run's costs, not lazily on read: the
        # recommendation is a function of costs.disruption.terminal_penalty_multiple,
        # which is a versioned config value that can change between when this
        # job ran and when someone later opens Results & Reports. Recomputing
        # on read would silently pair today's terminal_penalty with
        # yesterday's mean/cvar figures -- the exact provenance break this
        # project's costs_file@version convention exists to prevent.
        from crewsim.reporting.recommendation import compute_r_recommendation

        recommendation = compute_r_recommendation(
            cfg, costs.disruption.terminal_penalty_multiple, scoreboard
        )
        runlog.done(
            f"{len(scoreboard)} row(s), {len(comparisons)} paired comparison(s)"
        )

        if v3 is not None and not v3["pass"]:
            runlog.note(v3["message"], level="warning")
        if v4 is not None and not v4["pass"]:
            runlog.note(v4["message"], level="warning")

        # WN-005: V1/V2/V7 (their own small real simulation runs, see
        # gate_status.py) plus V3/V4/V9 already computed above, and every
        # outstanding [CONFIRM: owner] flag -- spec Sec9.3 items 3 and 5,
        # both mandatory on "every single recommendation report" and
        # previously only reachable through the separate HTML report.
        from crewsim.engine.policy import load_policy
        from crewsim.reporting.gate_status import compute_core_gates
        from crewsim.reporting.report import extract_confirm_markers

        representative_policy_name = config_ids[0]
        representative_policy = load_policy(
            config.repo_root() / "configs" / "policies" / f"{representative_policy_name}.yaml"
        )
        gates = compute_core_gates(cfg, costs, representative_policy, _MASTER_SEED)
        gates.append({
            "gate": "V3",
            "verdict": "PASS" if (v3 is not None and v3["pass"]) else ("FAIL" if v3 is not None else "N/A"),
            "detail": v3["message"] if v3 is not None else "no eligibility events in window",
        })
        gates.append({
            "gate": "V4",
            "verdict": "PASS" if (v4 is not None and v4["pass"]) else ("FAIL" if v4 is not None else "N/A"),
            "detail": v4["message"] if v4 is not None else "no drafts in any scenario",
        })
        if recommendation is not None:
            gates.append({
                "gate": "V9",
                "verdict": "STABLE" if recommendation["stable"] else "UNSTABLE",
                "detail": (
                    "R* per lambda: "
                    + ", ".join(f"{c['lambda']}->R{c['recommended_r']}" for c in recommendation["curve"])
                ),
            })
        confirm_markers = extract_confirm_markers([
            config.repo_root() / "configs" / "base.yaml",
            config.repo_root() / "configs" / "costs_pilots.yaml",
        ])
        runlog.note(f"{len(gates)} gate(s) evaluated, {len(confirm_markers)} outstanding [CONFIRM:] flag(s)")

        job.results = {
            "scoreboard": scoreboard,
            "comparisons": comparisons,
            "v3": v3,
            "v4": v4,
            "recommendation": recommendation,
            "gates": gates,
            "confirm_markers": confirm_markers,
            "num_scenarios": num_scenarios,
            "season": cfg.scope.season,
            "master_seed": _MASTER_SEED,
            "params_version": params_version,
            "params_hash": params_hash,
        }
        job.status = "completed"
        job.progress = _PERCENT
        db.commit()
    except JobCancelled as exc:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            # Stays "cancelled" -- the status the user set is the outcome, and
            # overwriting it with "failed" would report their own action as a
            # malfunction. No error_message for the same reason.
            job.status = "cancelled"
            entries = list(job.log or [])
            if entries and entries[-1].get("status") == "running":
                # "warning", not "failed": the step in flight was stopped, not
                # broken, and colouring it red would say the run went wrong.
                entries[-1] = {**entries[-1], "status": "warning"}
            entries.append(
                {
                    "step": None,
                    "total": _TOTAL_STEPS,
                    "message": str(exc),
                    "detail": "Stopped at a scenario boundary; partial work discarded.",
                    "status": "warning",
                    "duration_ms": None,
                    "progress_done": None,
                    "progress_total": None,
                    "artifact": None,
                }
            )
            job.log = entries
            db.commit()
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller via the job row
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            # Record the failure in the log too, so the stream shows where it
            # stopped rather than just going quiet.
            entries = list(job.log or [])
            if entries and entries[-1].get("status") == "running":
                entries[-1] = {**entries[-1], "status": "failed"}
            entries.append(
                {
                    "step": None,
                    "total": _TOTAL_STEPS,
                    "message": str(exc),
                    "detail": None,
                    "status": "error",
                    "duration_ms": None,
                }
            )
            job.log = entries
            db.commit()
    finally:
        db.close()


# WN-008: on-demand per-policy drill-down. Not run synchronously inside every
# batch job -- a full traced drill-down (5 costliest + 5 typical, trace=True)
# is real extra memory/time cost (S1e-03's own measured note), and most
# scoreboard rows never get clicked. A separate job type instead, launched
# only when a planner actually asks "why this R?".
_DRILLDOWN_JOB_TYPE = "processing_drilldown"
_DRILLDOWN_TOTAL_STEPS = 3


def run_drilldown_job(
    job_id: str, policy_name: str, num_scenarios: int, season: str,
) -> None:
    """Costliest + typical exemplar scenarios for ONE policy, traced.

    `season`/`num_scenarios` are the ORIGINATING batch job's own values, not
    re-entered by the caller -- scenario generation is a pure function of
    (season, master_seed, n_scenarios) (see scenarios/generator.py), so
    reusing them means this drill-down hits the exact same cached CRN
    scenario set the scoreboard's own numbers came from, not a fresh,
    unrelated draw that happens to share a policy name.
    """
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        job.status = "running"
        db.commit()

        from dataclasses import asdict

        from crewsim import config
        from crewsim.engine import des
        from crewsim.engine.policy import load_policy
        from crewsim.reporting.drilldown import build_scenario_drilldown, select_exemplar_scenarios

        def flush(entries: list[dict[str, Any]]) -> None:
            job.log = entries
            db.commit()

        runlog = RunLog(total_steps=_DRILLDOWN_TOTAL_STEPS, flush=flush)

        runlog.start("loading policy and parameter store")
        cfg = config.load()
        cfg = cfg.model_copy(update={"scope": cfg.scope.model_copy(update={"season": season})})
        costs = config.load_costs(cfg)
        policy = load_policy(config.repo_root() / "configs" / "policies" / f"{policy_name}.yaml")
        runlog.done(f"policy {policy.policy_id}, season {season}")

        runlog.start(f"tracing {num_scenarios} scenario(s)")
        sims = des.run_policy_crn(
            cfg, costs, policy, num_scenarios, master_seed=_MASTER_SEED, trace=True,
        )
        runlog.done(f"{len(sims)} scenario(s) traced")

        runlog.start("selecting exemplar scenarios")
        costliest, typical = select_exemplar_scenarios(cfg, sims, k=5)
        scenarios = []
        for label, pairs in (("costliest", costliest), ("typical", typical)):
            for sim, cost in pairs:
                d = build_scenario_drilldown(cfg, sim, cost)
                scenarios.append({
                    "label": label,
                    "scenario_id": d["scenario_id"],
                    "cost": d["cost"],
                    "trace": d["trace"],
                    "chains": [
                        {
                            "root_event_uid": chain["root_event_uid"],
                            "rows": [asdict(r) for r in chain["rows"]],
                            "trace_lines": chain["trace_lines"],
                        }
                        for chain in d["chains"]
                    ],
                })
        runlog.done(f"{len(scenarios)} exemplar scenario(s) ({len(costliest)} costliest, {len(typical)} typical)")

        job.results = {"policy": policy_name, "season": season, "scenarios": scenarios}
        job.status = "completed"
        job.progress = _PERCENT
        db.commit()
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller via the job row
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            db.commit()
    finally:
        db.close()


@router.post("/{job_id}/drilldown/{policy_name}")
def launch_drilldown(
    job_id: str,
    policy_name: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Launch an on-demand drill-down for one policy from an already-completed
    batch job, reusing that job's own season/num_scenarios (see
    run_drilldown_job's own docstring for why)."""
    source = db.query(Job).filter(Job.id == job_id, Job.type == "processing_batch").first()
    if source is None:
        raise HTTPException(status_code=404, detail="Batch job not found")
    if source.status != "completed" or not source.results:
        raise HTTPException(status_code=400, detail="Source batch job has not completed yet")
    if not any(row.get("policy") == policy_name for row in source.results.get("scoreboard", [])):
        raise HTTPException(
            status_code=400,
            detail=f"Policy {policy_name!r} was not part of batch job {job_id}'s scoreboard",
        )

    job = Job(id=str(uuid.uuid4()), type=_DRILLDOWN_JOB_TYPE, status="queued", progress=0)
    db.add(job)
    db.commit()
    background_tasks.add_task(
        run_drilldown_job, job.id, policy_name, source.results["num_scenarios"], source.results["season"],
    )
    return {"job_id": job.id, "status": "queued"}


def _validate_season(season: str | None) -> None:
    """Reject an unknown season at the request, not inside the worker.

    Without this the job is accepted, queued, and fails later with a pydantic
    error in `error_message` -- which is how the old filename-sniffing version
    behaved for every name it did not recognise.
    """
    if season is None:
        return
    from crewsim import config
    from crewsim.data.loaders import load_seasons

    known = load_seasons(config.load())
    if season not in known:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown season {season!r}. Known seasons: {', '.join(sorted(known))}",
        )


def _validate_policy_seasons(policy_names: list[str], season: str) -> None:
    """Refuse a policy fitted for a different season than the run.

    Every policy declares its own `season` (a required field on the Policy
    model), and each season has its own independently fitted parameter store.
    Running a winter policy against summer parameters silently mixes two
    calibrations and produces a cost figure belonging to neither -- a wrong
    number rather than an error, which is the class of failure this project
    exists to keep out of a planner's hands.

    Checked at the request so the mismatch is never queued at all.
    """
    from crewsim.engine.policy import load_policy
    from crewsim.reporting.grid import _policy_path

    mismatched = []
    for name in policy_names:
        try:
            policy = load_policy(_policy_path(name))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Cannot load policy {name!r}: {exc}") from exc
        if policy.season != season:
            mismatched.append(f"{name} (season={policy.season})")

    if mismatched:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Policy/season mismatch for a {season!r} run: {', '.join(mismatched)}. "
                f"Each season has its own calibration; a policy must be run against "
                f"the season it was defined for."
            ),
        )


def _refuse_if_reduced_batch(season: str | None) -> None:
    """S1c-01 AC4, applied to the API: a batch run's scoreboard feeds a
    policy comparison/recommendation surface (Results & Reports), exactly
    what cli.py's `_refuse_if_reduced` exists to gate before `grid`/`report`/
    `gate v9`. `processing_single` is NOT gated here, matching the CLI's own
    `run`/`compare` precedent -- a one-policy smoke test reports a scenario's
    cost, not a reserve level to adopt.

    Checked at the request, before the job is even queued, same as
    `_validate_season` above -- so an unsafe run never appears as a job at
    all rather than failing inside the worker after looking queued.
    """
    from crewsim import config
    from crewsim.engine.eligibility import EligibilityEngine

    cfg = config.load()
    if season is not None:
        cfg = cfg.model_copy(update={"scope": cfg.scope.model_copy(update={"season": season})})
    try:
        EligibilityEngine.from_config(cfg).check_recommendation_safe()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=f"Batch run refused: {exc}") from exc


def _queue(
    db: Session,
    background_tasks: BackgroundTasks,
    job_type: str,
    config_ids: list[str],
    num_scenarios: int,
    season: str | None,
    jobs: int,
) -> dict[str, str]:
    _validate_season(season)
    if job_type == "processing_batch":
        _refuse_if_reduced_batch(season)
    if jobs == 0:
        raise HTTPException(
            status_code=400,
            detail="jobs=0 is not a valid parallelism setting (1 = sequential, -1 = all cores)",
        )
    from crewsim import config as cfgmod

    resolved_season = season or cfgmod.load().scope.season
    # Against the RESOLVED season, so an unspecified season is checked against
    # the configured default rather than skipped.
    _validate_policy_seasons(config_ids, resolved_season)

    job = Job(
        id=str(uuid.uuid4()),
        type=job_type,
        status="queued",
        progress=0,
        season=resolved_season,
    )
    db.add(job)
    db.commit()
    background_tasks.add_task(run_processing_job, job.id, config_ids, num_scenarios, season, jobs)
    return {"job_id": job.id, "status": "queued"}


@router.post("/run")
def launch_single_run(
    req: RunRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> dict[str, str]:
    return _queue(
        db, background_tasks, "processing_single", [req.config_id], req.num_scenarios,
        req.season, req.jobs,
    )


@router.post("/batch")
def launch_batch_run(
    req: BatchRunRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> dict[str, str]:
    return _queue(
        db, background_tasks, "processing_batch", req.config_ids, req.num_scenarios,
        req.season, req.jobs,
    )


# response_model=None: Job is a SQLAlchemy model (see platform.py::get_audit_logs).
@router.get("/status", response_model=None)
def get_live_status(db: Session = Depends(get_db)) -> list[Job]:
    return (
        db.query(Job)
        .filter(Job.type.in_(_PROCESSING_TYPES))
        .order_by(Job.created_at.desc())
        .limit(_STATUS_LIMIT)
        .all()
    )


def _get_job_or_404(job_id: str, db: Session) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# One parsed tape per (scenario, policy, run parameters). A miss costs one
# re-run of a single scenario -- ~1.5s -- so a planner stepping between
# policies on the same scenario waits once, not every time. Small maxsize
# because each entry is a few hundred events and the access pattern is "the
# scenario I am currently looking at", not a broad sweep.
_TAPE_CACHE_SIZE = 8


@lru_cache(maxsize=_TAPE_CACHE_SIZE)
def _cached_tape(
    season: str, master_seed: str, n_scenarios: int, policy_name: str, scenario_id: int
) -> dict[str, Any]:
    """Deterministic by construction, which is what makes caching safe here:
    the same key reproduces byte-identical output (gate V7), so a cached tape
    can never disagree with a fresh run."""
    from crewsim import config as cfgmod
    from crewsim.engine.policy import load_policy
    from crewsim.reporting.grid import _policy_path
    from crewsim.reporting.tape import build_tape

    cfg = cfgmod.load()
    cfg = cfg.model_copy(update={"scope": cfg.scope.model_copy(update={"season": season})})
    policy = load_policy(_policy_path(policy_name))
    return build_tape(cfg, cfgmod.load_costs(cfg), policy, scenario_id, master_seed, n_scenarios)


@router.get("/{job_id}/scenario/{scenario_id}/events")
def get_scenario_events(
    job_id: str, scenario_id: int, policy: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """One scenario's event tape for one policy.

    Computed on demand rather than stored: the full event detail for a job is
    ~7 MB, wanted rarely, and reproducible exactly from
    (season, master_seed, n_scenarios, policy, scenario_id). Re-running one
    scenario costs ~1.5s and keeps the job row small.
    """
    job = _get_job_or_404(job_id, db)
    results = job.results or {}
    scoreboard = results.get("scoreboard") or []
    if not scoreboard:
        raise HTTPException(
            status_code=409, detail=f"Job {job_id} has no results yet (status: {job.status})."
        )

    known = [row["policy"] for row in scoreboard]
    if policy not in known:
        raise HTTPException(
            status_code=404,
            detail=f"Policy {policy!r} was not part of this run. Ran: {', '.join(known)}.",
        )

    n_scenarios = results.get("num_scenarios") or 0
    if not 0 <= scenario_id < n_scenarios:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario {scenario_id} is outside this run's 0..{n_scenarios - 1}.",
        )

    tape = _cached_tape(
        results.get("season") or job.season,
        results.get("master_seed", _MASTER_SEED),
        n_scenarios,
        policy,
        scenario_id,
    )
    return {"job_id": job_id, **tape}


@router.post("/{job_id}/cancel")
def cancel_processing_job(job_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Ask a running job to stop.

    Cooperative, not a kill: the worker runs in a background thread inside this
    process, and there is no safe way to interrupt SimPy mid-scenario without
    leaving a half-written ledger. Setting the status here is a request; the
    worker sees it at its next scenario boundary (`scenario_progress`) and
    raises out of the grid loop.

    So the job stops within roughly one scenario -- about 1.5s at the current
    corpus size -- not instantly. The response says `stopping` rather than
    `cancelled` for exactly that reason: claiming it had already stopped would
    be a promise this endpoint cannot keep.

    Under joblib (`jobs != 1`) the callback fires only between policies, so a
    cancel lands at the end of the policy in flight.
    """
    job = _get_job_or_404(job_id, db)
    if job.status not in ("queued", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"Job is {job.status}; only a queued or running job can be cancelled.",
        )
    job.status = "cancelled"
    db.commit()
    return {"job_id": job_id, "status": "stopping"}


@router.get("/{job_id}/scenarios")
def get_scenario_fingerprints(job_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """The exogenous demand this job's policies were run against, per scenario.

    This is the table `scenarios/generator.py` writes -- one row per
    scenario-day carrying the severity regime and the sick-call count -- joined
    to each policy's per-scenario cost. It answers a question the scoreboard
    structurally cannot: E[C] and CVaR95 are two numbers summarising fifty
    outcomes, and a planner cannot see from them whether a policy is uniformly
    mediocre or usually fine with a brutal tail.

    Cheap by construction. The demand is exogenous and already cached as a
    parquet keyed on (season, master_seed, n_scenarios, params hash), so this
    reads a file rather than re-running anything -- and because the same table
    feeds every policy, it is fetched once for the whole grid rather than per
    policy.

    Sent as parallel arrays, not a list of per-day objects: 50 scenarios x 42
    days is 2,100 cells, and `{"regime": "...", "sick_calls": n}` per cell
    would spend most of the payload on repeated key names.
    """
    job = _get_job_or_404(job_id, db)
    results = job.results or {}
    if not results:
        raise HTTPException(
            status_code=409,
            detail=f"Job {job_id} has no results yet (status: {job.status}).",
        )

    from crewsim import config as cfgmod
    from crewsim.scenarios.generator import load_scenario_set

    season = results.get("season") or job.season
    master_seed = results.get("master_seed", _MASTER_SEED)
    n_scenarios = results.get("num_scenarios")
    if not season or not n_scenarios:
        raise HTTPException(
            status_code=409, detail="Job result is missing the season/scenario count."
        )

    cfg = cfgmod.load()
    try:
        frame = load_scenario_set(cfg, season, master_seed, n_scenarios)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Per-policy vectors, keyed by policy so the UI can show one bar/figure
    # per policy against the same scenario row. cascading_drafts and
    # uncovered_legs are real simulation outcomes with continuous timestamps,
    # not a day-bucketed table like sick_calls -- they are exposed as one
    # figure per scenario (the whole 42-day period), not per day.
    costs_by_policy = {
        row["policy"]: row.get("scenario_costs") or []
        for row in results.get("scoreboard", [])
    }
    outcomes_by_policy = {
        row["policy"]: row.get("daily_outcomes") or []
        for row in results.get("scoreboard", [])
    }
    cascading_drafts_by_policy = {
        row["policy"]: row.get("scenario_cascading_drafts") or []
        for row in results.get("scoreboard", [])
    }
    uncovered_legs_by_policy = {
        row["policy"]: row.get("scenario_uncovered_legs") or []
        for row in results.get("scoreboard", [])
    }

    horizon_days = cfg.horizon.horizon_days
    scenarios = []
    for scenario_id, group in sorted(
        frame.sort("day").group_by("scenario"), key=lambda kv: kv[0][0]
    ):
        sid = int(scenario_id[0])
        regimes = list(group["regime"])
        sick = [int(v) for v in group["sick_calls"]]
        # Ambient flight delay, same shared/exogenous shape as sick_calls
        # above (not per-policy like "outcomes" below) -- real per-day
        # figures from scenarios/generator.py, present on every scenario set
        # generated after calibration/delays.py's per-regime fit landed;
        # absent (KeyError-safe via .get) on older cached sets.
        delayed = [int(v) for v in group["delayed_flights"]] if "delayed_flights" in group.columns else None
        delay_min = [float(v) for v in group["delay_minutes"]] if "delay_minutes" in group.columns else None
        scenarios.append(
            {
                "scenario": sid,
                "regimes": regimes,
                "sick_calls": sick,
                "total_sick_calls": sum(sick),
                "delayed_flights": delayed,
                "delay_minutes": delay_min,
                "total_delayed_flights": sum(delayed) if delayed is not None else None,
                "total_delay_minutes": sum(delay_min) if delay_min is not None else None,
                "costs": {
                    policy: (vec[sid] if sid < len(vec) else None)
                    for policy, vec in costs_by_policy.items()
                },
                # Outcomes are per POLICY -- the demand above is shared, what
                # each policy did with it is not.
                "outcomes": {
                    policy: (per_scenario[sid] if sid < len(per_scenario) else None)
                    for policy, per_scenario in outcomes_by_policy.items()
                },
                "cascading_drafts": {
                    policy: (vec[sid] if sid < len(vec) else None)
                    for policy, vec in cascading_drafts_by_policy.items()
                },
                "uncovered_legs": {
                    policy: (vec[sid] if sid < len(vec) else None)
                    for policy, vec in uncovered_legs_by_policy.items()
                },
            }
        )

    return {
        "job_id": job_id,
        "season": season,
        "master_seed": master_seed,
        "horizon_days": horizon_days,
        "n_scenarios": len(scenarios),
        "policies": list(costs_by_policy),
        # The vocabulary the regime strings come from, ordered by severity, so
        # the UI does not have to hardcode a scale that calibration owns.
        "regime_order": ["CALM", "NORMAL", "DISRUPTED", "SEVERE"],
        "scenarios": scenarios,
    }


@router.get("/{job_id}/logs")
def get_logs(job_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """The execution log as recorded so far.

    The non-streaming counterpart to `/stream` below -- for a job that has
    already finished, or a client that cannot hold a connection open.
    """
    job = _get_job_or_404(job_id, db)
    return {
        "job_id": job_id,
        "status": job.status,
        "progress": job.progress,
        "log": job.log or [],
        "error_message": job.error_message,
    }


@router.get("/{job_id}/stream")
async def stream_progress(job_id: str) -> StreamingResponse:
    """Server-sent events carrying this job's log and progress as it runs.

    The implementation is shared with the calibration router -- see
    `crewsim.api.streaming` for how it works and what it does not do.
    """
    return stream_job(job_id)


@router.delete("/{job_id}")
def delete_job(job_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    job = _get_job_or_404(job_id, db)
    db.delete(job)
    db.commit()
    return {"status": "success", "message": "Job deleted"}
