"""Command-line entry point.

Only `doctor` is implemented at S0-00 — it is the manual check for the project
structure story. The remaining commands are declared so the surface is visible
and stubbed so they fail honestly rather than silently doing nothing.
"""
from __future__ import annotations

import argparse
import importlib
import sys

from . import config

# The §4.2 layout, as data. The structure test and `doctor` read the same list,
# so the specification and the check cannot drift apart.
EXPECTED_MODULES = [
    "crewsim.data",
    "crewsim.calibration",
    "crewsim.scenarios",
    "crewsim.engine",
    "crewsim.engine.state",
    "crewsim.engine.legality",
    "crewsim.engine.eligibility",
    "crewsim.engine.drafting",
    "crewsim.engine.cascade",
    "crewsim.engine.costs",
    "crewsim.engine.des",
    "crewsim.optimize",
    "crewsim.reporting",
]

EXPECTED_DATASETS = [
    "d1_crew_master", "d2_rosters", "d3_pairings", "d3_pairing_legs",
    "d4_absences", "d5_reserve_callouts", "d6_schedule_changes",
    "d7_pay_register", "d8_flight_movements", "d9_station_days",
    "d10_positioning_invoices", "d11_training_sessions",
]

OK, BAD = "\033[32m✓\033[0m", "\033[31m✗\033[0m"

# The policy an `explain-*` command simulates when the caller names none. Every
# explain command shares it so two of them can't quietly explain different runs.
DEFAULT_EXPLAIN_POLICY = "R10"


def _money(amount: float) -> str:
    return f"${amount:,.2f}"


def _params_provenance(cfg) -> tuple[str, str]:
    """(params_version, content_hash) of the frozen parameter store this run reads.

    Real values off the store calibration actually emitted (calibration/
    pipeline.py writes `params_version` and a blake2b `content_hash` receipt
    into output/params/params_v<ver>_<season>.json), not the literal "v1"
    placeholder this used to print with the note "param loading isn't
    implemented yet" -- it has been implemented since S0-06/S0-07.

    A missing store is reported as missing rather than defaulted: a provenance
    chain that invents a version is worse than one that admits a gap, because
    the entire point is regenerating this result a year from now.
    """
    import json

    from .engine import des

    params_dir = config.resolve(cfg, "params_dir")
    path = params_dir / f"params_v{des._package_version()}_{cfg.scope.season}.json"
    if not path.is_file():
        return "MISSING", f"no parameter store at {path.name} -- run `crewsim calibrate --emit`"
    store = json.loads(path.read_text())
    return store.get("params_version", "unknown"), store.get("content_hash", "unknown")


def _print_provenance(cfg, policy, master_seed: str, ledger_hash: str | None = None) -> None:
    """The §2.3/C3 provenance chain: data window -> params version -> master
    seed -> costs version -> policy hash -> results.

    `ledger_hash` is the "-> results" link, and is what makes the chain
    regenerable rather than merely descriptive. Printed by `--print-provenance`
    and as a footer on every normal `run`, so a number a planner reads always
    carries the provenance that produced it (S1a-09's "recorded in run
    metadata"), instead of it being available only from a separate command that
    exits before running anything.
    """
    data_window = (f"{cfg.windows.fitting.start} to {cfg.windows.holdout.end}"
                   if cfg.windows else "unknown")
    costs_ver = policy.costs_file.split("@")[1] if "@" in policy.costs_file else "unknown"
    params_ver, params_hash = _params_provenance(cfg)

    print("\nProvenance chain:")
    print(f"  data window    : {data_window}")
    print(f"  params version : {params_ver}  ({params_hash})")
    print(f"  master seed    : {master_seed!r}")
    print(f"  costs version  : {costs_ver}")
    print(f"  policy hash    : {policy.get_hash()}")
    print(f"  results        : {ledger_hash if ledger_hash else '(not computed -- no run)'}")


def doctor() -> int:
    """Report the project structure and resolve every configured path."""
    problems = 0
    print("\ncrewsim doctor\n")

    print("  modules (§4.2)")
    for name in EXPECTED_MODULES:
        try:
            importlib.import_module(name)
            print(f"    {OK} {name}")
        except Exception as exc:  # noqa: BLE001 - a diagnostic must survive any
            problems += 1         # import failure and report it, not re-raise
            print(f"    {BAD} {name}  ({exc})")

    print("\n  paths (§4.4.1b) — resolved from configs/base.yaml, never hard-coded")
    try:
        cfg = config.load()
    except Exception as exc:  # noqa: BLE001 - report, do not crash the doctor
        print(f"    {BAD} {exc}")
        return 1
    for key in ("corpus_dir", *config.OUTPUT_PATH_KEYS):
        try:
            p = config.resolve(cfg, key)
        except KeyError as exc:
            problems += 1
            print(f"    {BAD} {exc}")
            continue
        # Only the corpus must exist: it is an input and ships with the package.
        # Output directories are created by the run that writes them, so a
        # missing one is the normal state of a fresh checkout, not a fault.
        optional = key in config.OUTPUT_PATH_KEYS
        ok = p.is_dir() or optional
        if not ok:
            problems += 1
        note = "" if p.is_dir() else "  (created on first write)"
        print(f"    {OK if ok else BAD} {key:<12} {p.relative_to(config.repo_root())}{note}")

    print("\n  datasets (§6.1)")
    try:
        corpus = config.resolve(cfg, "corpus_dir")
    except KeyError:
        return 1
    found = [config.dataset_path(cfg, n) is not None for n in EXPECTED_DATASETS]
    n = sum(found)
    mark = OK if n == len(EXPECTED_DATASETS) else BAD
    if n != len(EXPECTED_DATASETS):
        problems += 1
    print(f"    {mark} {n}/{len(EXPECTED_DATASETS)} datasets found in {corpus.name}/")
    for name, hit in zip(EXPECTED_DATASETS, found, strict=True):
        if not hit:
            print(f"      {BAD} missing: {name}")
    d12 = corpus / "d12_agreement_rules.yaml"
    if d12.is_file():
        print(f"    {OK} D12 agreement rules present ({d12.name})")

    print(f"\n  {'all checks passed' if not problems else f'{problems} problem(s)'}\n")
    return 0 if not problems else 1


def _config_show() -> int:
    """S1a-02 manual check: `crewsim config show`."""
    try:
        cfg = config.load()
    except Exception as exc:  # noqa: BLE001 - report, do not crash the CLI
        print(f"error: {exc}")
        return 1

    s = cfg.scope
    print("\ncrewsim config show\n")
    print("  scope")
    print(f"    base={s.base} fleet={s.fleet} position={s.position} "
          f"crew_group={s.crew_group} season={s.season} bid_period={s.bid_period}")

    h = cfg.horizon
    print("\n  horizon")
    print(f"    warmup={h.warmup_days}d measurement={h.measurement_days}d "
          f"cooldown={h.cooldown_days}d -> horizon_days={h.horizon_days}d")

    print("\n  population")
    print(f"    roster_size={cfg.population.roster_size}")

    print("\n  paths")
    print(f"    corpus_dir={cfg.paths.corpus_dir}")

    print(f"\n  mode={cfg.mode}  costs_file={cfg.costs_file}")

    for notice in config.unconsumed_notices(cfg):
        print(f"\n  [NOTICE] {notice}")

    markers = config.all_confirm_markers(cfg)
    print(f"\n  [CONFIRM] outstanding ({len(markers)})")
    for m in markers:
        print(f"    {m.file.relative_to(config.repo_root())}:{m.line}  owner={m.owner}")
        print(f"      {m.text}")

    print()
    return 0


def _todo(name: str) -> int:
    print(f"`crewsim {name}` is not implemented yet — see backlog/stories.yaml")
    return 2


def _resolve_policy_path(name_or_path: str) -> str:
    """`compare`/`gate v3`/`gate v4` already accept a bare policy name (R10)
    and resolve it under configs/policies/; `run` historically required a
    full path. S1c-01's own manual check (`run --policy R10`) uses the bare
    form, so `run` needs the same resolution -- a path that exists as given
    still works unchanged."""
    from pathlib import Path

    if Path(name_or_path).is_file():
        return name_or_path
    return str(config.repo_root() / "configs" / "policies" / f"{name_or_path}.yaml")


def _stderr_progress(label: str = "scenario"):
    """A des.run_policy_crn on_progress callback that prints to stderr, not
    stdout -- several callers/tests parse stdout's last line (e.g.
    `report`'s "wrote <path>"), and a run of hundreds of scenarios has no
    other visible output otherwise, which is indistinguishable from stuck."""
    def _progress(done: int, total: int) -> None:
        print(f"\r  {label} {done}/{total}", end="", file=sys.stderr, flush=True)
    return _progress


def _data_head(dataset: str, rows: int) -> int:
    """S0-01 manual check: `crewsim data head --dataset d2_rosters --rows 5`."""
    from .data import loaders

    try:
        cfg = config.load()
        df = loaders.load_dataset(cfg, dataset)
    except (FileNotFoundError, KeyError, loaders.SchemaError) as exc:
        print(f"error: {exc}")
        return 1

    import polars as pl

    with pl.Config(tbl_cols=-1, tbl_width_chars=240, tbl_rows=rows):
        print(df.head(rows))
    return 0


def _data_profile(open_after: bool) -> int:
    """S0-02b manual check: `crewsim data profile --open`."""
    import webbrowser

    from .data import loaders, profile

    try:
        cfg = config.load()
        path = profile.write_report(cfg)
    except (FileNotFoundError, KeyError, loaders.SchemaError) as exc:
        print(f"error: {exc}")
        return 1

    print(f"wrote {path}")
    if open_after:
        webbrowser.open(path.as_uri())
    return 0


def _data_quality_report() -> int:
    """S0-02 manual check: `crewsim data quality-report`."""
    from .data import loaders, quality
    try:
        cfg = config.load()
        return quality.run_quality_report(cfg)
    except (FileNotFoundError, KeyError, loaders.SchemaError) as exc:
        print(f"error: {exc}")
        return 1


def _data_draft_events() -> int:
    """S0-03 manual check: `crewsim data draft-events`."""
    from .data import drafts, loaders

    try:
        cfg = config.load()
        df = drafts.reconstruct_drafts(cfg)
    except (FileNotFoundError, KeyError, loaders.SchemaError) as exc:
        print(f"error: {exc}")
        return 1

    print(f"\nReconstructed {df.height} draft events (D6 x D7, §6.3-1)\n")
    print("  prior-status distribution (-> tier mix)")
    for status, share in sorted(drafts.prior_status_distribution(df).items(), key=lambda kv: -kv[1]):
        print(f"    {status:<12} {share:.0%}")

    unknown_initiator = df["initiator"].null_count() / df.height if df.height else 0.0
    print(f"\n  draft events with unknown initiator: {unknown_initiator:.1%} (not dropped)")

    result = drafts.score_recall(cfg, df)
    if result is None:
        print(
            "\n  no _ground_truth.json in this corpus -- on real data, recall must be "
            "measured against a week an IOC duty manager has labelled by hand"
        )
        return 0

    status = "PASS" if result["gate_pass"] else "FAIL"
    print(
        f"\n  recall vs ground truth: {result['recall']:.1%} "
        f"({result['found']:,} of {result['true_n']:,}) [{status}] "
        f"(gate >= {result['gate']:.0%})"
    )
    return 0 if result["gate_pass"] else 1


def _data_cascade_target() -> int:
    """S0-05 manual check: `crewsim data cascade-target`."""
    from .data import cascades, loaders

    try:
        cfg = config.load()
        result = cascades.cascade_target(cfg)
    except (FileNotFoundError, KeyError, loaders.SchemaError) as exc:
        print(f"error: {exc}")
        return 1

    print(f"\nCascade rate (D6, {cfg.cascade_reconstruction.window_days}-day follow-on scan, §6.3-3)\n")
    print(
        f"  {result['rate']:.1%}  [{result['ci_low']:.1%}, {result['ci_high']:.1%}] "
        f"{result['confidence_level']:.0%} CI  "
        f"({result['count']:,} of {result['n_drafts']:,} reconstructed drafts)"
    )
    # "Cascades outnumber drafts" can't happen here, not just "didn't happen
    # this run": count is a sum of at-most-one-per-row booleans over
    # n_drafts rows (reconstruct_cascades emits exactly one row per draft),
    # so it is bounded by n_drafts by construction. Verified by
    # test_cascades_never_outnumber_drafts_on_the_real_corpus, which is
    # where that acceptance criterion actually lives.

    recall = result["draft_recall"]
    if recall is not None:
        print(
            f"\n  inherits S0-03's recall limitation: drafts reconstructed at "
            f"{recall['recall']:.1%} of ground truth -- a cascade following a draft "
            f"S0-03 missed is invisible to this rate"
        )
    else:
        print(
            "\n  no _ground_truth.json in this corpus -- S0-03's recall against real data "
            "is unknown, so treat this rate as a lower bound"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="crewsim")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("doctor", help="report project structure and resolve paths")

    data_parser = sub.add_parser("data", help="inspect the D1-D12 corpus")
    data_sub = data_parser.add_subparsers(dest="data_cmd")
    head_parser = data_sub.add_parser("head", help="print the first N rows of a dataset")
    head_parser.add_argument("--dataset", required=True, help="e.g. d2_rosters")
    head_parser.add_argument("--rows", type=int, default=10)
    profile_parser = data_sub.add_parser(
        "profile", help="summarise dataset size, schema, and basic stats"
    )
    profile_parser.add_argument("--dataset", required=True)
    profile_parser.add_argument("--open", action="store_true", dest="open_after",
                                 help="open the report in a browser after writing it")
    
    eligibility_parser = data_sub.add_parser(
        "eligibility-target", help="reconstruct the real historical eligible-fraction distribution (S0-04)"
    )
    eligibility_parser.add_argument(
        "--window", required=True, choices=["fitting", "holdout"],
        help="fitting or holdout (S0-09) -- reconstruct_eligibility's actual key; "
        "season is already fixed by cfg.scope.season, not a per-call choice"
    )
    
    data_sub.add_parser("quality-report", help="run the data quality gates (§6.2)")
    data_sub.add_parser("draft-events", help="reconstruct draft events from D6 x D7 (§6.3-1)")
    data_sub.add_parser("cascade-target", help="reconstruct the cascade rate, 7-day D6 follow-on scan (§6.3-3)")

    calibrate_parser = sub.add_parser("calibrate", help="fit the parameter store from the corpus")
    calibrate_parser.add_argument("--season", help="Season to calibrate (required for full pipeline)")
    calibrate_parser.add_argument("--emit", action="store_true", help="Run full pipeline and emit parameter store")
    calibrate_parser.add_argument("--window", default="fitting", help="Data window to use (default: fitting)")
    calibrate_sub = calibrate_parser.add_subparsers(dest="cal_cmd")
    regime_parser = calibrate_sub.add_parser("regime", help="Severity-regime labelling and Markov fit")
    regime_parser.add_argument("--season", required=True)
    regime_parser.add_argument("--show-matrix", action="store_true")
    regime_parser.add_argument("--show-multipliers", action="store_true")

    nhpp_parser = calibrate_sub.add_parser("sick-calls", help="Sick-call NHPP with covariates")
    nhpp_parser.add_argument("--show-coefficients", action="store_true")

    scenarios_parser = sub.add_parser("scenarios", help="scenario management")
    scen_sub = scenarios_parser.add_subparsers(dest="scen_cmd")
    gen_parser = scen_sub.add_parser("generate", help="generate CRN scenarios from frozen params")
    gen_parser.add_argument("--scenarios", type=int, default=100)
    gen_parser.add_argument("--master-seed", required=True)
    gen_parser.add_argument("--season", default="winter_sun")
    
    delays_parser = sub.add_parser("fit-delays", help="fit the delay model")
    delays_parser.add_argument("--season", required=True)

    gate_parser = sub.add_parser("gate", help="run a V&V gate")
    gate_parser.add_argument("gate_id", nargs="?", default=None,
                              help="e.g. v1, v2, v7; omit to only check the fitting/holdout guard (S0-09)")
    gate_parser.add_argument("--show-comparison", action="store_true", help="Show Erlang B vs DES comparison (for v2)")
    
    roster_parser = sub.add_parser("roster", help="roster loading and analysis")
    roster_sub = roster_parser.add_subparsers(dest="roster_cmd")
    summary_parser = roster_sub.add_parser("summary", help="summarize loaded roster")
    summary_parser.add_argument("--base", help="Filter by base")
    summary_parser.add_argument("--fleet", help="Filter by fleet")
    summary_parser.add_argument("--position", help="Filter by position")
    summary_parser.add_argument("--policy", help="Apply a parameter policy (S1b-02+)")
    summary_parser.add_argument("--show-split", action="store_true", help="Show Line vs Reserve split (S1b-02+)")
    summary_parser.add_argument("--all-scopes", action="store_true",
                                 help="load every base/fleet/position instead of defaulting to cfg.scope")
    
    pattern_parser = roster_sub.add_parser("reserve-pattern", help="show reserve pattern statistics")
    pattern_parser.add_argument("--base", help="Filter by base")
    pattern_parser.add_argument("--fleet", help="Filter by fleet")
    pattern_parser.add_argument("--position", help="Filter by position")
    pattern_parser.add_argument("--policy", required=True, help="Apply a parameter policy (S1b-02+)")

    gate_parser.add_argument("--window", default="holdout", help="Data window to use (default: holdout)")
    gate_parser.add_argument("--i-know", action="store_true", help="Allow running validation on fitting window")
    gate_parser.add_argument("--jobs", type=int, default=1, help="Number of parallel jobs for v7")
    gate_parser.add_argument("--surface", action="store_true", help="Report recommended R as a surface (for v9)")
    gate_parser.add_argument("--policy", default="R10", help="Policy to simulate for v3/v4 (default: R10)")
    gate_parser.add_argument("--scenarios", type=int, default=20, help="CRN scenarios to simulate for v3/v4 (default: 20)")
    gate_parser.add_argument("--master-seed", default="master", help="CRN master seed for v3/v4")
    gate_parser.add_argument("--week", default=None,
                              help="ISO date (any day of the week) to replay for v5; default: the mock "
                                   "corpus's own peak-disruption week")
    gate_parser.add_argument("--format", default="timeline", choices=["timeline"], help="v5 output format")
    gate_parser.add_argument("--period", default=None, help="'YYYY-MM' calendar month to backtest for v6")

    config_parser = sub.add_parser("config", help="inspect the resolved configuration")
    config_sub = config_parser.add_subparsers(dest="config_cmd")
    config_sub.add_parser("show", help="print scope, horizon, population and outstanding [CONFIRM] markers")

    run_parser = sub.add_parser("run", help="run one policy over the CRN scenario set")
    run_parser.add_argument("--policy", required=True, help="Policy configuration file")
    run_parser.add_argument("--scenarios", type=int, default=1, help="Number of scenarios to simulate")
    run_parser.add_argument("--master-seed", default="master", help="CRN master seed")
    run_parser.add_argument("--print-hash", action="store_true", help="Print the ledger hash and exit")
    run_parser.add_argument("--print-provenance", action="store_true", help="Print provenance chain and exit")
    run_parser.add_argument("--assert-invariants", action="store_true", help="Assert legality invariants during the run")
    run_parser.add_argument("--report-eligibility", action="store_true",
                             help="Print the realized eligibility-fraction distribution (S1c-01)")
    run_parser.add_argument("--kpis", action="store_true",
                             help="Print the full KPI report over the measurement window (S1e-01)")

    compare_parser = sub.add_parser("compare", help="paired CRN comparison of two or more policies")
    compare_parser.add_argument("--policies", nargs="+", required=True)
    compare_parser.add_argument("--scenarios", type=int, default=1)
    compare_parser.add_argument("--master-seed", default="master", help="CRN master seed")

    explain_parser = sub.add_parser("explain-legality", help="explain legality check for a crew member and pairing")
    explain_parser.add_argument("--crew", required=True)
    explain_parser.add_argument("--pairing", required=True)
    explain_parser.add_argument(
        "--call-at", type=str, default=None,
        help="HH:MM (24h) reserve call time, same day as the duty's report time (S1c-02, rule L8)"
    )

    explain_event_parser = sub.add_parser("explain-event", help="explain an event's consequences")
    explain_event_parser.add_argument("--scenario", type=int, required=True)
    explain_event_parser.add_argument("--event", required=True,
                                       help="SICK_CALL (S1b-04) or UNCOVERED_DEADLINE (S1b-06)")
    explain_event_parser.add_argument("--first", action="store_true",
                                       help="trace the first such event end to end")
    explain_event_parser.add_argument("--policy", type=str, default=DEFAULT_EXPLAIN_POLICY)
    explain_event_parser.add_argument("--master-seed", type=str, default="master")
    
    explain_crew_parser = sub.add_parser("explain-crew", help="explain a crew's timeline")
    explain_crew_parser.add_argument("--scenario", type=int, default=None,
                                      help="if given, show the crew's calendar AFTER this scenario's "
                                           "DES/drafting events (S1b-05b), not the static pre-simulation roster")
    explain_crew_parser.add_argument("--crew", required=True)
    explain_crew_parser.add_argument("--timeline", action="store_true")
    explain_crew_parser.add_argument("--show-counters", action="store_true")
    explain_crew_parser.add_argument("--policy", type=str, default="R10", help="policy to simulate when --scenario is given")
    explain_crew_parser.add_argument("--master-seed", type=str, default="master")

    cascade_parser = sub.add_parser("explain-cascade", help="explain cascade resolution")
    cascade_parser.add_argument("--scenario", type=int, default=0)
    cascade_parser.add_argument("--first", action="store_true")
    cascade_parser.add_argument("--type", type=str)

    draft_parser = sub.add_parser("explain-draft", help="explain draft selection")
    draft_parser.add_argument("--scenario", type=int, default=0)
    draft_parser.add_argument("--event", type=int, default=1)

    cost_parser = sub.add_parser("explain-cost", help="explain cost trace")
    cost_parser.add_argument("--scenario", type=int, default=0)
    cost_parser.add_argument("--trace-root", action="store_true")
    cost_parser.add_argument("--summary", action="store_true")
    cost_parser.add_argument("--policy", type=str)
    cost_parser.add_argument("--category", type=str)
    cost_parser.add_argument("--master-seed", type=str, default="master")

    recovery_parser = sub.add_parser(
        "explain-recovery", help="run one scenario through the real recovery pipeline (S1d-04c)"
    )
    recovery_parser.add_argument("--scenario", type=int, default=0)
    recovery_parser.add_argument("--policy", type=str, default="R10")
    recovery_parser.add_argument("--master-seed", type=str, default="master")
    recovery_parser.add_argument("--trace", action="store_true", help="print the step-by-step resolution trace")

    report_parser = sub.add_parser("report", help="self-contained HTML policy-comparison report (S1e-02/S1e-03)")
    report_parser.add_argument("--policies", nargs="+", default=None,
                                help="compare these policies (cost distributions, trade-off/lambda curves)")
    report_parser.add_argument("--policy", type=str, default=None,
                                help="single policy for --drilldown (shorthand for --policies <one>)")
    report_parser.add_argument("--scenarios", type=int, default=20)
    report_parser.add_argument("--master-seed", type=str, default="master")
    report_parser.add_argument("--representative-policy", type=str, default=None,
                                help="which policy's sims back gates V3/V4 (default: first --policies/--policy entry)")
    report_parser.add_argument("--drilldown", nargs="?", const="both", default=None,
                                choices=["costliest", "typical", "both"],
                                help="S1e-03: embed the 5 costliest and 5 most-typical scenario timelines "
                                     "for --policy (or --representative-policy)")
    report_parser.add_argument("--open", action="store_true", help="open the report in the default browser")

    grid_parser = sub.add_parser("grid", help="CRN-paired policy grid runner (S1e-04)")
    grid_parser.add_argument("--config", type=str, default=None,
                              help="grid config YAML with a `policies:` list (default: configs/grid_mvp.yaml)")
    grid_parser.add_argument("--scenarios", type=int, default=20)
    grid_parser.add_argument("--master-seed", type=str, default="master")
    grid_parser.add_argument("--jobs", type=int, default=1, help="joblib parallelism across policies")

    counterfactual_parser = sub.add_parser(
        "counterfactual", help="NOT A RECOMMENDATION -- price the mandated drafting rule (S1e-05)"
    )
    counterfactual_parser.add_argument("--vs-mandated", action="store_true", required=True,
                                        help="required -- names what this compares against")
    counterfactual_parser.add_argument("--policy", type=str, default="R6",
                                        help="which policy's stage1 reserves to hold fixed while draft_mode varies")
    counterfactual_parser.add_argument("--scenarios", type=int, default=20)
    counterfactual_parser.add_argument("--master-seed", type=str, default="master")

    args = ap.parse_args(argv)
    if args.cmd == "doctor":
        return doctor()
    if args.cmd == "scenarios":
        if args.scen_cmd == "generate":
            cfg = config.load()
            from .scenarios.generator import generate_scenarios
            print(f"Generating {args.scenarios} scenarios (season={args.season}, seed={args.master_seed})...")
            out_file = generate_scenarios(cfg, args.season, args.master_seed, args.scenarios)
            if out_file is None:
                print("Cache hit! Scenarios already exist for these frozen parameters and seed. Skipping generation.")
            else:
                print(f"Generated scenarios successfully to: {out_file}")
            return 0
        scenarios_parser.print_help()
        return 2
    if args.cmd == "roster":
        if args.roster_cmd == "summary":
            cfg = config.load()
            from .engine.roster_loader import load_rosters, select_template_window

            pol = None
            if args.policy:
                from .engine.policy import load_policy
                # Policies live in configs/policies/
                pol_path = config.repo_root() / "configs" / "policies" / f"{args.policy}.yaml"
                pol = load_policy(pol_path)

            # Default to cfg.scope when no filter is given, matching what every
            # simulation path does (des.run_scenario loads the scope, never the
            # whole corpus). Without this, S1b-02's own manual check --
            # `roster summary --policy R10 --show-split`, which passes no
            # filters -- loaded all 1,975 crew across every base, fleet and
            # position, and compared that against a scoped roster_size of 120.
            # `--all-scopes` keeps the corpus-wide view available deliberately.
            scoped = not args.all_scopes
            base = args.base or (cfg.scope.base if scoped else None)
            fleet = args.fleet or (cfg.scope.fleet if scoped else None)
            position = args.position or (cfg.scope.position if scoped else None)

            active_crew, exclusions = load_rosters(
                cfg, base=base, fleet=fleet, position=position, policy=pol
            )
            window_start, window_end = select_template_window(cfg)

            total_active = len(active_crew)
            total_excluded = sum(exclusions.values())

            print("Roster Summary:")
            print(f"Template Window: {window_start} to {window_end} (season={cfg.scope.season}, "
                  f"{cfg.horizon.horizon_days} days, holdout-sourced)")
            scope_desc = ("all bases/fleets/positions" if args.all_scopes
                          else f"base={base} fleet={fleet} position={position}")
            print(f"Scope: {scope_desc}")
            print(f"Rostered Crew: {total_active}")
            if args.show_split and pol:
                n_reserves = sum(getattr(c, "_is_reserve", False) for c in active_crew)
                n_lines = total_active - n_reserves
                print(f"  Line Holders: {n_lines}")
                print(f"  Reserves: {n_reserves}")
                # S1b-02's actual claim, stated as the identity it is. The
                # conserved quantity is the ACTIVE population, not
                # population.roster_size: roster_size is the establishment, and
                # the difference between the two is exactly the non-ACTIVE crew
                # listed below. Printing both stops the two being conflated,
                # which is what made the story's stated expectation
                # ("= roster_size exactly") unmeetable.
                ok = "OK" if (n_lines + n_reserves) == total_active else "FAILED"
                print("\nHeadcount conservation (S1b-02):")
                print(f"  line holders + reserves = {n_lines} + {n_reserves} = "
                      f"{n_lines + n_reserves}  vs  active in scope = {total_active}   [{ok}]")
                print(f"  establishment (population.roster_size) = {cfg.population.roster_size}"
                      f"  -- {total_excluded} excluded as non-ACTIVE")
                if (n_lines + n_reserves) != total_active:
                    print("  ERROR: reserves are being minted, not carved out (the v2 defect).")
                print()
            print(f"Excluded: {total_excluded}")
            print(f"Exclusion Reasons: {exclusions}")
            return 0
        if args.roster_cmd == "reserve-pattern":
            cfg = config.load()
            from .engine.policy import load_policy
            from .engine.roster_loader import load_rosters
            from .engine.state import BlockType
            
            pol_path = config.repo_root() / "configs" / "policies" / f"{args.policy}.yaml"
            pol = load_policy(pol_path)
            
            active_crew, _ = load_rosters(cfg, base=args.base, fleet=args.fleet, position=args.position, policy=pol)
            
            reserves = [c for c in active_crew if getattr(c, "_is_reserve", False)]
            if not reserves:
                print("No reserves found for this policy.")
                return 1
                
            sc_count = 0
            lc_count = 0
            on_days = 0
            off_days = 0
            
            for c in reserves:
                for b in c.calendar:
                    # Engine time is MINUTES since the template-window start
                    # (S1d-04b). This divided by 86400 (seconds per day) and so
                    # reported every figure 60x low: 3.7 reserve-days across 12
                    # reserves, where the real total is 223.0.
                    dur = (b.end - b.start) / 1440.0
                    if b.btype == BlockType.RESERVE:
                        on_days += dur
                        if b.reserve_call_type == "SC": sc_count += 1
                        elif b.reserve_call_type == "LC": lc_count += 1
                    elif b.btype == BlockType.DAY_OFF:
                        off_days += dur
                        
            total_calls = sc_count + lc_count
            sc_pct = (sc_count / total_calls * 100) if total_calls > 0 else 0
            lc_pct = (lc_count / total_calls * 100) if total_calls > 0 else 0
            
            print("Reserve Pattern Summary:")
            print(f"Total Reserves: {len(reserves)}")
            print(f"Total Reserve Days: {on_days:.1f}")
            print(f"Total Off Days: {off_days:.1f}")
            print(f"SC: {sc_pct:.1f}% | LC: {lc_pct:.1f}%")
            return 0
            
        roster_parser.print_help()
        return 2
    if args.cmd == "explain-event":
        # S1b-04 (`--event SICK_CALL`) and S1b-06 (`--event UNCOVERED_DEADLINE`)
        # both document this command as their manual check, so it explains a
        # real scenario's real trace: run with verbose_trace so every failed
        # resolution attempt is logged, then show one event's whole life.
        # (Replaces a hand-typed four-line timeline followed by 22 lines of
        # unreachable code that sat after an unconditional `return 0`.)
        from .engine import des
        from .engine.policy import load_policy

        known = ("SICK_CALL", "UNCOVERED_DEADLINE")
        if args.event not in known:
            print(f"error: --event must be one of {list(known)}, got {args.event!r}")
            return 2

        cfg = config.load()
        costs = config.load_costs(cfg)
        policy = load_policy(_resolve_policy_path(args.policy))
        sim = des.run_scenario(
            cfg, costs, policy, scenario_id=args.scenario, master_seed=args.master_seed,
            n_scenarios=args.scenario + 1, trace=True, verbose_trace=True,
        )
        print(f"Scenario {args.scenario}, policy {policy.policy_id} -- "
              f"{len(sim.trace)} traced events\n")

        marker = "SICK_CALL:" if args.event == "SICK_CALL" else "CANCELLED at deadline"
        hits = [line for line in sim.trace if marker in line]
        if not hits:
            print(f"No {args.event} occurred in scenario {args.scenario}. "
                  f"Try another --scenario.")
            return 1
        if not args.first:
            print(f"{len(hits)} {args.event} event(s) in this scenario; "
                  f"pass --first to trace one end to end.")
            for line in hits:
                print(f"  {line}")
            return 0

        # Every trace line for the item(s) this event touches. Item uids appear
        # as "item <uid>" (and "cascade item <uid>"), so a uid match pulls the
        # arrival, each held retry, and the resolution into one timeline.
        import re

        first = hits[0]
        uids = set(re.findall(r"item (\d+)", first))
        if not uids:
            print(first)
            return 0
        related = [
            line for line in sim.trace
            if any(re.search(rf"item {uid}\b", line) for uid in uids)
        ]
        print(f"Tracing {args.event} -> item(s) {sorted(uids, key=int)}:\n")
        for line in related:
            print(f"  {line}")

        booked = [r for r in sim.ledger.rows if str(r.event_uid) in uids]
        if booked:
            print("\n  Ledger rows for these item(s):")
            for r in booked:
                print(f"    [t={r.sim_time:>9,.0f}] {r.category:<22} {_money(r.amount):>14} "
                      f"crew {r.crew_id or '-'}")
        if args.event == "UNCOVERED_DEADLINE":
            attempts = sum(1 for line in related if "unresolved for now" in line)
            # Report the MEASURED hold window rather than asserting the item was
            # held: `deadline = pairing.start - uncovered_deadline_hours` is
            # absolute, so an item whose pairing has already begun is born at or
            # past its own deadline and every retry fires at the arrival instant.
            # sick_calls.py documents that shape for apply_named_absence; it
            # reaches apply_sick_call too, and a check that printed "HELD"
            # regardless would hide exactly the case S1b-06 needs to see.
            times = [float(m) for line in related
                     for m in re.findall(r"^\[t=(-?[\d.]+)\]", line)]
            held_for = (max(times) - min(times)) if times else 0.0
            print(f"\n  Verification: {attempts} failed resolution attempt(s), "
                  f"held {held_for:,.0f} min from arrival to cancellation.")
            if held_for <= 0.0:
                print("  [WARNING] zero hold window -- this item's pairing had already started "
                      "when the absence was notified, so its deadline was already past on "
                      "arrival. It was NOT held; re-run with another --scenario for a case "
                      "that exercises the hold path.")
        return 0
    if args.cmd == "data":
        if args.data_cmd == "head":
            return _data_head(args.dataset, args.rows)
        if args.data_cmd == "profile":
            return _data_profile(args.open_after)
        if args.data_cmd == "quality-report":
            return _data_quality_report()
        if args.data_cmd == "draft-events":
            return _data_draft_events()
        if args.data_cmd == "cascade-target":
            return _data_cascade_target()
        if args.data_cmd == "eligibility-target":
            cfg = config.load()
            from .data.eligibility_target import reconstruct_eligibility
            res = reconstruct_eligibility(cfg, args.window)
            print(f"Historical Eligibility Target ({args.window}, season={cfg.scope.season}):")
            print(f"Mean Eligible Fraction: {res['mean']:.1%}")
            print(f"95% CI: [{res['ci_lower']:.1%}, {res['ci_upper']:.1%}]")
            print(f"Distribution samples recorded: {len(res['distribution'])}")
            return 0
            
        data_parser.print_help()
        return 2
    if args.cmd == "calibrate":
        if args.window == "holdout":
            print("error: Refusing to calibrate on the holdout window. The parameter store must only be fit on the fitting window.")
            return 1
            
        if args.cal_cmd:
            if args.cal_cmd == "regime":
                try:
                    cfg = config.load()
                    # Override window in config if we support it later? Currently fitters don't even use config window except pipeline.py
                    from .calibration import regime
                    res = regime.fit_regime(cfg, args.season)
                    print("Transition Matrix:")
                    for s in regime.STATES:
                        print(f"{s:<10} [{res['matrix'][s]['CALM']:.3f} {res['matrix'][s]['NORMAL']:.3f} {res['matrix'][s]['DISRUPTED']:.3f} {res['matrix'][s]['SEVERE']:.3f}]")
                    if args.show_multipliers:
                        print("Intensity Multipliers:")
                        for s in regime.STATES:
                            print(f"{s:<10} {res['multipliers'][s]:.3f}")
                    print(f"\n[DIGITAL RECEIPT] content_hash: {res['content_hash']}")
                    print(f"Saved parameter file to: {res['_saved_path']}")
                    return 0
                except Exception as exc:  # noqa: BLE001 - a CLI reports the failure, never a traceback
                    print(f"error: {exc}")
                    return 1
            if args.cal_cmd == "sick-calls":
                try:
                    cfg = config.load()
                    from .calibration import nhpp
                    res = nhpp.fit_sick_calls(cfg)
                    if args.show_coefficients:
                        print("Coefficients:")
                        for k, v in res["coefficients"].items():
                            print(f"{k:<30} {v:+.4f}")
                        print(f"\nDispersion: {res['dispersion']:.4f}")
                        print(f"Lognorm (shape, scale): {res['duration_lognorm_shape']:.4f}, {res['duration_lognorm_scale']:.4f}")
                    print(f"\n[DIGITAL RECEIPT] content_hash: {res['content_hash']}")
                    print(f"Saved parameter file to: {res['_saved_path']}")
                    return 0
                except Exception as exc:  # noqa: BLE001 - a CLI reports the failure, never a traceback
                    print(f"error: {exc}")
                    return 1
            if args.cal_cmd == "delays":
                try:
                    cfg = config.load()
                    from .calibration import delays
                    res = delays.fit_delays(cfg, args.season)
                    print(f"Base Probability (NORMAL): {res['base_delay_probability']:.4f}\n")
                    print("Duration Mixture Components:")
                    for i, comp in enumerate(res['components']):
                        print(f"Component {i+1}: weight={comp['weight']:.2f}, mean={comp['mean_mins']:.1f}m, std={comp['std_dev']:.1f}m")
                    print(f"\n[DIGITAL RECEIPT] content_hash: {res['content_hash']}")
                    print(f"Saved parameter file to: {res['_saved_path']}")
                    return 0
                except Exception as exc:  # noqa: BLE001 - a CLI reports the failure, never a traceback
                    print(f"error: {exc}")
                    return 1
        elif args.emit:
            if not args.season:
                print("error: --season is required when using --emit")
                return 1
            try:
                cfg = config.load()
                # pass window to pipeline to use the correct config and stamp it
                from .calibration import pipeline
                res = pipeline.run_pipeline(cfg, args.season, window_name=args.window)
                print(f"Successfully generated parameter store for {args.season}")
                print(f"Saved to: {res['_saved_path']}")
                print(f"[DIGITAL RECEIPT] content_hash: {res['content_hash']}")
                return 0
            except Exception as exc:  # noqa: BLE001 - a CLI reports the failure, never a traceback
                print(f"error: {exc}")
                return 1
        calibrate_parser.print_help()
        return 2

    if args.cmd == "explain-crew":
        from .engine.legality import DUTY_BLOCKS
        from .engine.roster_loader import load_rosters

        cfg = config.load()
        scenario = getattr(args, "scenario", None)

        if scenario is not None:
            # S1b-05b: a crew's calendar AFTER a specific scenario's real
            # DES/drafting events have run, not the static D2/D3 roster --
            # this is what S1b-05's own manual check actually needs (a
            # RESERVE block split by a drafted duty only exists post-sim).
            from .engine import des
            from .engine.policy import load_policy

            costs = config.load_costs(cfg)
            pol_path = config.repo_root() / "configs" / "policies" / f"{args.policy}.yaml"
            policy = load_policy(pol_path)
            sim = des.run_scenario(
                cfg, costs, policy, scenario_id=scenario, master_seed=args.master_seed,
                n_scenarios=scenario + 1,
            )
            crew_by_id = {c.crew_id: c for c in sim.roster + sim.reserves}
            source_desc = f"scenario {scenario}, policy {policy.policy_id}"
        else:
            crew_list, _ = load_rosters(cfg)
            crew_by_id = {c.crew_id: c for c in crew_list}
            source_desc = "static template-window roster"

        if args.crew not in crew_by_id:
            print(f"error: crew {args.crew!r} not found among {len(crew_by_id)} active crew in the {source_desc}")
            return 1

        crew = crew_by_id[args.crew]
        calendar = sorted(crew.calendar, key=lambda b: b.start)

        show_timeline = getattr(args, "timeline", False) or not getattr(args, "show_counters", False)
        if show_timeline:
            print(f"Timeline for Crew {crew.crew_id} ({crew.base}, {crew.position}, seniority {crew.seniority}) "
                  f"-- {source_desc}:")
            if not calendar:
                print("  (no blocks in the template window)")
            for b in calendar:
                detail = f" ({b.pairing_id})" if b.pairing_id else (f" ({b.reserve_call_type})" if b.reserve_call_type else "")
                print(f"  [t={b.start:.0f} -> t={b.end:.0f}] {b.btype.value}{detail}")

        if getattr(args, "show_counters", False):
            print("\n--- Rolling Counters (L3/L4), sampled at the end of each duty block ---")
            duty_blocks = [b for b in calendar if b.btype in DUTY_BLOCKS]
            if not duty_blocks:
                print("  (no duty blocks in the template window)")
            prev_duty7 = None
            for b in duty_blocks:
                duty7, flight7 = crew.get_rolling_counters(b.end, 7)
                duty28, _ = crew.get_rolling_counters(b.end, 28)
                trend = ""
                if prev_duty7 is not None:
                    trend = "  (accumulated)" if duty7 >= prev_duty7 else "  (decayed)"
                print(
                    f"  t={b.end:.0f} (after {b.btype.value}): "
                    f"rolling 7d duty={duty7/60:.1f}h flight={flight7/60:.1f}h, "
                    f"rolling 28d duty={duty28/60:.1f}h{trend}"
                )
                prev_duty7 = duty7

        return 0

    if args.cmd == "config":
        if args.config_cmd == "show":
            return _config_show()
        config_parser.print_help()
        return 2
    if args.cmd == "gate":
        if args.window == "fitting" and not getattr(args, "i_know", False):
            print("error: Refusing to run validation on the fitting window. Use --i-know if you are absolutely sure.")
            return 1

        if args.gate_id is None:
            print(f"Gate validation passed (window={args.window}: fitting/holdout guard only, no gate_id given).")
            return 0

        if args.gate_id == "v1":
            from .engine.policy import load_policy
            from .gates.v1_degeneracy import print_v1_report, run_v1_gate

            cfg = config.load()
            costs = config.load_costs(cfg)
            base_policy = load_policy(_resolve_policy_path(args.policy))
            print("Running Gate V1: three real degeneracy scenarios "
                  "(0 reserves / all reserve / 0 reserves + arrivals)...", file=sys.stderr)
            result = run_v1_gate(cfg, costs, base_policy, master_seed=args.master_seed)
            print_v1_report(result)
            return 0 if result["pass"] else 1

        if args.gate_id == "v2":
            from .engine.policy import load_policy
            from .gates.v2_erlang import print_v2_report, run_v2_gate

            cfg = config.load()
            costs = config.load_costs(cfg)
            policy = load_policy(_resolve_policy_path(args.policy))
            print(f"Running Gate V2: {args.scenarios} real scenario(s) of {policy.policy_id}, "
                  f"cascades disabled...", file=sys.stderr)
            result = run_v2_gate(cfg, costs, policy, n_scenarios=args.scenarios,
                                  master_seed=args.master_seed)
            print_v2_report(result)
            # Returns a real exit code. This branch used to fall through to the
            # unknown-gate handler below, so `gate v2 --show-comparison` printed
            # [PASS] and then exited 2; without the flag it printed only the
            # error. --show-comparison is now accepted and ignored: the
            # comparison IS the gate, so there is nothing to withhold.
            return 0 if result["pass"] else 1

        if args.gate_id == "v3":
            cfg = config.load()
            costs = config.load_costs(cfg)
            from .engine import des
            from .engine.policy import load_policy
            from .gates.v3_eligibility import print_v3_report, run_v3_gate, write_v3_report

            pol_path = config.repo_root() / "configs" / "policies" / f"{args.policy}.yaml"
            policy = load_policy(pol_path)
            sims = des.run_policy_crn(cfg, costs, policy, args.scenarios, args.master_seed,
                                       on_progress=_stderr_progress())
            print(file=sys.stderr)
            # Flattened per-event eligibility fractions across all scenarios --
            # same granularity as reconstruct_eligibility's historical side
            # (per-absence-event fractions, not per-scenario averages).
            sim_fractions = [f for sim in sims for f in sim.elig.get_distribution()]
            print(f"Simulating {args.scenarios} scenarios of policy {policy.policy_id} "
                  f"({len(sim_fractions)} eligibility events)...")
            result = run_v3_gate(cfg, sim_fractions, window=args.window)
            print_v3_report(result, args.window)
            report_path = write_v3_report(cfg, result, sim_fractions, args.window)
            print(f"wrote {report_path}")
            if not result["pass"]:
                return 1
            return 0

        if args.gate_id == "v4":
            cfg = config.load()
            costs = config.load_costs(cfg)
            from .engine import des
            from .engine.policy import load_policy
            from .gates.v4_cascade import print_v4_report, run_v4_gate

            pol_path = config.repo_root() / "configs" / "policies" / f"{args.policy}.yaml"
            policy = load_policy(pol_path)
            sims = des.run_policy_crn(cfg, costs, policy, args.scenarios, args.master_seed,
                                       on_progress=_stderr_progress())
            print(file=sys.stderr)
            # cascade_target's historical rate is count(cascaded drafts) / count(all
            # drafts) (crewsim/data/cascades.py::cascade_rate) -- n_cascading_drafts
            # / n_drafts is the same construct per scenario. A scenario with zero
            # drafts has no rate to report, not a 0.0 that would pull the mean down
            # for a reason unrelated to cascading.
            sim_cascade_rates = [sim.n_cascading_drafts / sim.n_drafts for sim in sims if sim.n_drafts > 0]
            print(f"Simulating {args.scenarios} scenarios of policy {policy.policy_id} "
                  f"({len(sim_cascade_rates)} scenarios with drafts)...")
            result = run_v4_gate(cfg, sim_cascade_rates, window=args.window)
            print_v4_report(result, args.window)
            if not result["pass"]:
                return 1
            return 0

        if args.gate_id == "v7":
            from .engine.policy import load_policy
            from .gates.v7_reproducibility import print_v7_report, run_v7_gate

            cfg = config.load()
            costs = config.load_costs(cfg)
            policy = load_policy(_resolve_policy_path(args.policy))
            print(f"Running Gate V7: {args.scenarios} real scenario(s) of {policy.policy_id}, "
                  f"sequentially then across {args.jobs} worker(s)...", file=sys.stderr)
            result = run_v7_gate(
                cfg, costs, policy, master_seed=args.master_seed,
                n_scenarios=args.scenarios, jobs=args.jobs,
            )
            print_v7_report(result)
            return 0 if result["pass"] else 1


        if args.gate_id == "v9":
            from .gates.v9_sensitivity import (
                R_CANDIDATE_POLICIES,
                build_r_star_lookup,
                print_v9_report,
                run_v9_gate,
            )

            cfg = config.load()
            costs = config.load_costs(cfg)
            n_valid_tp = len([tp for tp in cfg.sensitivity.terminal_penalty if tp > 1.0])
            print(f"Gate V9: simulating {len(R_CANDIDATE_POLICIES)} reserve policies "
                  f"({', '.join(R_CANDIDATE_POLICIES)}) x {n_valid_tp} terminal_penalty values "
                  f"x {args.scenarios} scenarios each ({len(R_CANDIDATE_POLICIES) * n_valid_tp * args.scenarios} "
                  f"real simulation runs)...")
            print("[NOTICE] roster_size is swept in the reported surface but has no effect on the "
                  "result: cfg.population.roster_size is not consumed anywhere in the engine, so R* "
                  "is identical across roster_size values -- real per-roster_size sensitivity needs the "
                  "mock corpus generator to emit multiple population sizes (out of S1d-05's scope).")
            r_lookup = build_r_star_lookup(cfg, costs, args.scenarios, args.master_seed)
            result = run_v9_gate(cfg, r_lookup=r_lookup)
            print_v9_report(result)
            return 0

        if args.gate_id == "v5":
            import datetime

            from .engine.policy import load_policy
            from .gates.v5_trace import run_v5_gate

            cfg = config.load()
            costs = config.load_costs(cfg)
            policy = load_policy(_resolve_policy_path(args.policy))
            week_start = datetime.date.fromisoformat(args.week) if args.week else None
            _sim, _week_used, timeline = run_v5_gate(cfg, costs, policy, week_start)
            print(timeline)
            return 0

        if args.gate_id == "v6":
            from .engine.policy import load_policy
            from .gates.v6_backtest import print_v6_report, run_v6_gate

            if not args.period:
                print("error: gate v6 requires --period 'YYYY-MM'")
                return 2
            cfg = config.load()
            costs = config.load_costs(cfg)
            policy = load_policy(_resolve_policy_path(args.policy))
            result = run_v6_gate(cfg, costs, policy, args.period)
            print_v6_report(result)
            return 0

        print(f"error: unknown gate_id {args.gate_id!r} (known: v1, v2, v3, v4, v5, v6, v7, v9)")
        gate_parser.print_help()
        return 2
    if args.cmd == "run":
        if getattr(args, "print_hash", False):
            from .engine import des
            from .engine.ledger import CostLedger
            from .engine.policy import load_policy

            cfg = config.load()
            costs = config.load_costs(cfg)
            policy = load_policy(_resolve_policy_path(args.policy))
            seed = getattr(args, "master_seed", "master")
            sims = des.run_policy_crn(cfg, costs, policy, args.scenarios, seed,
                                       on_progress=_stderr_progress())
            print(file=sys.stderr)
            # The hash of every scenario's rows concatenated in scenario order,
            # not a hash of per-scenario hashes: a row that migrates between
            # scenarios has to change this figure. --policy and --master-seed
            # both feed it (they were parsed and then ignored before S1a-05's
            # own manual check was rebuilt), so two different policies cannot
            # print the same "ledger hash".
            merged = CostLedger()
            for sim in sims:
                merged.rows.extend(sim.ledger.rows)
            print(f"policy: {policy.policy_id}  master_seed: {seed!r}  "
                  f"scenarios: {args.scenarios}  rows: {len(merged.rows)}")
            print(f"ledger_hash: {merged.content_hash()}")
            return 0
        if getattr(args, "print_provenance", False):
            from .engine import des
            from .engine.ledger import CostLedger
            from .engine.policy import load_policy

            cfg = config.load()
            costs = config.load_costs(cfg)
            p = load_policy(_resolve_policy_path(args.policy))
            seed = getattr(args, "master_seed", "master")
            # Actually runs, so the chain terminates in a real result digest.
            # This used to return before simulating anything, which left the
            # "-> results" link -- the only one that makes the chain
            # regenerable -- permanently unfilled.
            sims = des.run_policy_crn(cfg, costs, p, args.scenarios, seed,
                                       on_progress=_stderr_progress())
            print(file=sys.stderr)
            merged = CostLedger()
            for sim in sims:
                merged.rows.extend(sim.ledger.rows)
            _print_provenance(cfg, p, seed, ledger_hash=merged.content_hash())
            return 0


        from .engine import des
        from .engine.policy import load_policy

        cfg = config.load()
        costs = config.load_costs(cfg)
        policy = load_policy(_resolve_policy_path(args.policy))
        master_seed = getattr(args, "master_seed", "master")

        sims = des.run_policy_crn(cfg, costs, policy, args.scenarios, master_seed,
                                   on_progress=_stderr_progress())
        print(file=sys.stderr)

        if getattr(args, "report_eligibility", False):
            # S1c-01: a histogram, not a mean -- V3 compares distributions.
            # Pool is reserves whose RESERVE block covers the duty window
            # (EligibilityEngine.eligible_reserves), not the moment of the
            # call -- get_distribution() is exactly that per-event fraction.
            fractions = [f for sim in sims for f in sim.elig.get_distribution()]
            print(f"\nEligibility distribution ({len(fractions)} events, pool = reserves "
                  f"whose RESERVE block covers the full duty window):")
            n_buckets = 10
            bar_width = 50  # terminal display width, not a statistical parameter
            counts = [0] * n_buckets
            for f in fractions:
                counts[min(int(f * n_buckets), n_buckets - 1)] += 1
            largest = max(counts) if counts else 0
            for i, c in enumerate(counts):
                lo, hi = i / n_buckets, (i + 1) / n_buckets
                bar_len = round(c / largest * bar_width) if largest else 0
                print(f"  [{lo:.1f}, {hi:.1f}) {c:5d} {'#' * bar_len}")
            if fractions:
                print(f"  mean = {sum(fractions) / len(fractions):.3f}\n")

        if getattr(args, "kpis", False):
            from .reporting.kpis import compute_kpis, print_kpi_report

            result = compute_kpis(cfg, sims)
            print_kpi_report(cfg, result)
            return 0

        if getattr(args, "assert_invariants", False):
            from .engine.legality import (
                find_l0_violations,
                find_l5_regressions,
                find_l5_streak_spans,
            )
            from .engine.roster_loader import load_rosters
            from .gates.v3_eligibility import print_v3_report, run_v3_gate

            invariants_failed = False

            # S1a-06 (defect D3): the invariant this flag's own story asks for
            # -- "0 overlapping duty blocks across N scenarios", v2 produced
            # 1,030. Checked on the REALIZED post-simulation calendars, so it
            # catches an overlap however it was introduced (drafting, reserve
            # assignment, cascade re-assignment), not only one that some
            # is_legal_assignment call would have rejected on the way in.
            print("--- L0 Single-Assignment Invariant (realized calendars) ---")
            l0_offenders: list[str] = []
            n_crew_checked = 0
            for sim in sims:
                for crew in sim.roster + sim.reserves:
                    n_crew_checked += 1
                    for a, b in find_l0_violations(crew):
                        l0_offenders.append(
                            f"scenario {sim.scenario_id}, {crew.crew_id}: "
                            f"{a.btype.value} [{a.start:.0f}, {a.end:.0f}] overlaps "
                            f"{b.btype.value} [{b.start:.0f}, {b.end:.0f}]"
                        )
            if l0_offenders:
                print(f"FATAL: {len(l0_offenders)} overlapping duty block(s) across "
                      f"{len(sims)} scenario(s) -- a crew is in two places at once:")
                for line in l0_offenders[:10]:
                    print(f"  {line}")
                if len(l0_offenders) > 10:
                    print(f"  ... and {len(l0_offenders) - 10} more")
                invariants_failed = True
            else:
                print(f"PASS: 0 overlapping duty blocks across {len(sims)} scenario(s) "
                      f"({n_crew_checked} crew-scenarios checked).")
            print("-----------------------------------------------------------\n")

            # Same construction as `gate v3`: flattened per-event eligibility
            # fractions from these real sims, not a Gaussian centred on the
            # historical mean by definition -- that mock could never fail.
            sim_fractions = [f for sim in sims for f in sim.elig.get_distribution()]
            print("\n--- Gate V3 Pre-Planner Verification ---")
            result = run_v3_gate(cfg, sim_fractions, window="holdout")
            print_v3_report(result, "holdout")
            if not result["pass"]:
                print("FATAL: V3 Gate failed! A number failing V3 must never reach a planner silently.")
                invariants_failed = True
            print("----------------------------------------\n")

            # S1c-04: L5 as a DELTA invariant -- compares each scenario's
            # post-simulation crew STREAKS (not just a violation count --
            # a crew can heal one streak and gain a different one while the
            # count stays flat, which a count comparison would miss)
            # against the pre-simulation static roster baseline, and fails
            # only on streaks the drafting/reserve-assignment path itself
            # introduces or extends. A raw post-sim count would always
            # fail: the real static roster already has ~450 L5
            # "violations" per policy scope on its own (real multi-day
            # trips whose duty periods are separated by under 24h -- L5 is
            # deliberately conservative per spec 5.4, not a corpus bug),
            # which would make this check permanently unable to
            # distinguish an actual regression from pre-existing data.
            # Tracked separately: S1c-04b (corpus/rule conservative-bias
            # finding). Note: L5 already runs inside is_legal_assignment
            # on every assignment, so this is a regression tripwire (it
            # fires if that guard is ever removed or bypassed), not an
            # independent discovery mechanism -- a PASS here confirms the
            # guard is still wired in, not that L5 was newly verified.
            print("--- L5 Duty-Free-Day Invariant (delta vs. pre-simulation baseline) ---")
            baseline_active, _ = load_rosters(
                cfg, base=cfg.scope.base, fleet=cfg.scope.fleet, position=cfg.scope.position, policy=policy
            )
            baseline_spans: dict[str, list[tuple[float, float]]] = {
                crew.crew_id: find_l5_streak_spans(crew) for crew in baseline_active
            }

            new_or_worse: list[str] = []
            for sim in sims:
                for crew in sim.roster + sim.reserves:
                    post_spans = find_l5_streak_spans(crew)
                    regressions = find_l5_regressions(baseline_spans.get(crew.crew_id, []), post_spans)
                    for s, e in regressions:
                        new_or_worse.append(
                            f"scenario {sim.scenario_id}, {crew.crew_id}: "
                            f"streak ({s:.0f} to {e:.0f}) extends beyond every baseline streak for this crew"
                        )

            if new_or_worse:
                print(f"FATAL: drafting/reserve-assignment introduced or extended "
                      f"{len(new_or_worse)} L5 streak(s) beyond the pre-simulation baseline:")
                for line in new_or_worse[:10]:
                    print(f"  {line}")
                if len(new_or_worse) > 10:
                    print(f"  ... and {len(new_or_worse) - 10} more")
                invariants_failed = True
            else:
                n_crew = sum(len(sim.roster) + len(sim.reserves) for sim in sims)
                n_baseline_violations = sum(len(spans) for spans in baseline_spans.values())
                n_baseline_crew = sum(1 for spans in baseline_spans.values() if spans)
                print(f"PASS: no scenario introduced or extended an L5 streak beyond "
                      f"the pre-simulation baseline ({n_crew} crew-scenarios checked; "
                      f"baseline itself already has {n_baseline_violations} pre-existing "
                      f"streak(s) across {n_baseline_crew} crew -- see S1c-04b).")
            print("-----------------------------------------------------------------\n")

            if invariants_failed:
                return 1

        scenario_costs = des.measured_window_costs(cfg, sims)
        mean_cost = sum(scenario_costs) / len(scenario_costs)

        print(f"Policy {policy.policy_id} -- {args.scenarios} CRN scenario(s), master_seed={master_seed!r}")
        print(f"  E[cost]  (measured window) = ${mean_cost:,.2f}")
        print(f"  CVaR95   (measured window) = ${des.cvar95(scenario_costs):,.2f}")
        print(f"  min/max                    = ${min(scenario_costs):,.2f} / ${max(scenario_costs):,.2f}")

        # S1a-09: every number this command prints leaves with the provenance
        # needed to regenerate it. Cheap -- the run already happened.
        from .engine.ledger import CostLedger

        merged = CostLedger()
        for sim in sims:
            merged.rows.extend(sim.ledger.rows)
        _print_provenance(cfg, policy, master_seed, ledger_hash=merged.content_hash())
        return 0
    if args.cmd == "compare":
        if len(args.policies) != 2:
            print("error: compare requires exactly two policies")
            return 1

        import numpy as np
        from scipy import stats

        from .engine import des
        from .engine.policy import load_policy

        n = args.scenarios
        master_seed = getattr(args, "master_seed", "master")
        cfg = config.load()
        costs = config.load_costs(cfg)

        # CRN pairing: both policies run with the SAME master_seed/scenario_id
        # set, so scenario i's sick-call arrivals (day, time, duration -- see
        # des.py::run_policy_crn) are identical across policies. The cost
        # difference reflects roster/reserve composition, not draw luck.
        pol_a = load_policy(config.repo_root() / "configs" / "policies" / f"{args.policies[0]}.yaml")
        pol_b = load_policy(config.repo_root() / "configs" / "policies" / f"{args.policies[1]}.yaml")

        sims_a = des.run_policy_crn(cfg, costs, pol_a, n, master_seed, on_progress=_stderr_progress(args.policies[0]))
        print(file=sys.stderr)
        sims_b = des.run_policy_crn(cfg, costs, pol_b, n, master_seed, on_progress=_stderr_progress(args.policies[1]))
        print(file=sys.stderr)
        costs_a = np.array(des.measured_window_costs(cfg, sims_a))
        costs_b = np.array(des.measured_window_costs(cfg, sims_b))

        diff = costs_b - costs_a
        mean_diff = np.mean(diff)
        std_diff = np.std(diff, ddof=1) if n > 1 else 0
        se = std_diff / np.sqrt(n) if n > 1 else float('inf')

        if n > 1:
            t_stat, p_val = stats.ttest_rel(costs_b, costs_a)
            ci_half = stats.t.ppf(0.975, n-1) * se
            ci_lower = mean_diff - ci_half
            ci_upper = mean_diff + ci_half
        else:
            t_stat, p_val = float('nan'), float('nan')
            ci_lower, ci_upper = float('nan'), float('nan')

        print(f"Comparing {args.policies[0]} vs {args.policies[1]} over {n} scenarios (CRN):")
        print(f"Mean Difference: ${mean_diff:,.2f}")
        if n > 1:
            print(f"95% CI: [${ci_lower:,.2f}, ${ci_upper:,.2f}]")
            print(f"t-statistic: {t_stat:.2f} (p={p_val:.4f})")
        else:
            print("Not enough scenarios to compute CI and t-statistic.")
        return 0

    if args.cmd == "explain-legality":
        from .engine.legality import is_legal_assignment
        from .engine.state import Block, BlockType, CrewMember, OpenTimeItem

        cfg = config.load()

        # TS156: a fixed synthetic duty period shared by S1a-07's and
        # S1c-02's own manual checks -- YUL-CDG, FO, report Tuesday 16:00,
        # release Wednesday 02:00 (16:00 = 960 min, 02:00 next day = 1560 min).
        duty = OpenTimeItem(
            uid=1, pairing_id="TS156", base="YUL", fleet="A321neoLR", position="FO",
            start=960.0, end=1560.0, deadline=960.0 - 600.0, origin="SICK_CALL", root_event_uid=1
        )

        # Same convention as explain-cascade's deterministic fixtures
        # (S1d-01/02): real is_legal_assignment(), not a print statement --
        # a regression in that function changes this output too. Each
        # fixture is built so exactly one rule is the binding failure.
        fixtures = {
            # S1a-07: A330-rated FO against an A321neoLR duty -- ILLEGAL_L6.
            "C0203": CrewMember(
                crew_id="C0203", base="YUL", fleet_quals={"A330"}, position="FO", seniority=203, calendar=[],
            ),
            # S1c-02: long-call reserve on-call through the whole duty
            # window -- every other rule is satisfied, so an insufficient
            # --call-at is the sole binding failure (L8).
            "R002": CrewMember(
                crew_id="R002", base="YUL", fleet_quals={"A321neoLR"}, position="FO", seniority=502,
                calendar=[Block(start=0.0, end=2000.0, btype=BlockType.RESERVE, reserve_call_type="LC")],
            ),
        }

        if args.pairing != "TS156" or args.crew not in fixtures:
            print(
                f"error: explain-legality only knows pairing=TS156 against crew in "
                f"{sorted(fixtures)} (S1a-07/S1c-02's own fixtures)"
            )
            return 1

        now = None
        if args.call_at is not None:
            try:
                hh_s, mm_s = args.call_at.split(":")
                hh, mm = int(hh_s), int(mm_s)
                if not (0 <= hh < 24 and 0 <= mm < 60):
                    raise ValueError
            except ValueError:
                print(f"error: --call-at must be HH:MM (24h), got {args.call_at!r}")
                return 1
            # Same calendar day as the duty's report time -- S1c-02's own
            # manual check ("--call-at 15:00" against a 16:00 report) is 1h
            # of notice, which fixes this as "same day", not "before".
            day_start = (int(duty.start) // 1440) * 1440
            now = float(day_start + hh * 60 + mm)

        # Make the same-day --call-at convention self-documenting in the
        # output, not just in a comment a reviewer running this may never read.
        call_ctx = ""
        if now is not None:
            notice_h = (duty.start - now) / 60.0
            call_ctx = f" (called at t={now:.0f}, report t={duty.start:.0f}, {notice_h:.1f}h notice)"

        crew = fixtures[args.crew]
        res = is_legal_assignment(crew, duty, now=now, cfg=cfg)
        if not res.legal:
            print(f"[{args.crew} -> {args.pairing}] {res.fail_rule}: {res.reason}{call_ctx}")
        else:
            print(f"[{args.crew} -> {args.pairing}] LEGAL{call_ctx}")
        return 0
        
    if args.cmd == "explain-cascade":
        from .engine.cascade import apply_delta, compute_draft_delta
        from .engine.state import Block, BlockType, CrewMember, OpenTimeItem

        cfg = config.load()

        if getattr(args, "first", False):
            # A small deterministic case, not a live corpus scenario: S1d-04c/
            # S1d-04d found real cascades are rare at production roster scale
            # (n_cascading_drafts == 0 across 20 seeds at R10), so drawing
            # --scenario N from a real run would make this manual check
            # flaky-to-vacuous. Same real compute_draft_delta/apply_delta as
            # tests/engine/test_cascade.py, not a print statement -- if that
            # function's behavior regresses, this output changes too.
            crew = CrewMember(
                crew_id="C1", base="YUL", fleet_quals={"A330"}, position="CA", seniority=1,
                calendar=[Block(start=1000.0, end=1100.0, btype=BlockType.PAIRING, pairing_id="P_FUTURE")],
            )
            item = OpenTimeItem(
                uid=1, pairing_id="P_DRAFT", base="YUL", fleet="A330", position="CA",
                start=900.0, end=1050.0, deadline=800.0, origin="SICK_CALL", root_event_uid=1,
            )
            print(f"Tracing Cascade Generation (Scenario {args.scenario}):")
            print(f"  [t={item.start:.0f}] {crew.crew_id} drafted for pairing {item.pairing_id} "
                  f"[{item.start:.0f}, {item.end:.0f}]")
            delta, cascades = compute_draft_delta(crew, item, cfg, now=item.start)
            for b in delta.removed_blocks:
                print(f"  [t={item.start:.0f}] draft's mandatory rest overlaps future pairing "
                      f"{b.pairing_id} at [{b.start:.0f}, {b.end:.0f}]")
                print(f"  [t={item.start:.0f}] {b.pairing_id} removed from {crew.crew_id}'s calendar")
            apply_delta(crew, delta)
            for casc in cascades:
                lag_min = cfg.cascade.visibility_lag_hours * 60.0
                visible_at = max(item.start, casc.start - lag_min)
                print(f"  [t={item.start:.0f}] OpenTimeItem for {casc.pairing_id} placed on queue, "
                      f"visible at t={visible_at:.0f} ({cfg.cascade.visibility_lag_hours:.0f}h before "
                      f"{casc.pairing_id}'s start)")
            print("\nVerification: draft -> later pairing removed -> new open item at that pairing's time.")
        elif getattr(args, "type", None) == "reserve_loss":
            crew = CrewMember(
                crew_id="C1", base="YUL", fleet_quals={"A330"}, position="CA", seniority=1,
                calendar=[Block(start=1050.0, end=1400.0, btype=BlockType.RESERVE)],
            )
            item = OpenTimeItem(
                uid=1, pairing_id="P_DRAFT", base="YUL", fleet="A330", position="CA",
                start=800.0, end=900.0, deadline=700.0, origin="SICK_CALL", root_event_uid=1,
            )
            print(f"Tracing Reserve Loss Cascade (Scenario {args.scenario}):")
            print(f"  [t={item.start:.0f}] {crew.crew_id} drafted for pairing {item.pairing_id} "
                  f"[{item.start:.0f}, {item.end:.0f}]")
            delta, cascades = compute_draft_delta(crew, item, cfg, now=item.start)
            for b in delta.removed_blocks:
                if b.btype == BlockType.RESERVE:
                    print(f"  [t={item.start:.0f}] draft's mandatory rest pushes into "
                          f"{crew.crew_id}'s RESERVE block [{b.start:.0f}, {b.end:.0f}]")
                    print(f"  [t={item.start:.0f}] RESERVE block removed from {crew.crew_id}'s calendar")
            apply_delta(crew, delta)
            print(f"  [t={item.start:.0f}] {len(cascades)} open item(s) generated "
                  f"(a reserve loss is a capacity loss, not an uncovered flight)")
            print("\nVerification: reserve pool structurally reduced, no open item generated.")
        return 0

    if args.cmd == "explain-draft":
        from .engine.drafting import select_draft_candidate
        from .engine.state import Block, BlockType, CrewMember, OpenTimeItem

        cfg = config.load()

        # S1a-08 specific test case
        duty = OpenTimeItem(
            uid=args.event, pairing_id="TS156", base="YUL", fleet="A321neoLR", position="FO",
            start=100.0, end=200.0, deadline=0.0, origin="SICK_CALL", root_event_uid=args.event
        )
        
        roster = [
            # Tier 1, sen 10
            CrewMember(crew_id="C0001", base="YUL", fleet_quals={"A321neoLR"}, position="FO", seniority=10, calendar=[]),
            # Tier 1, sen 5 (Most senior in Tier 1)
            CrewMember(crew_id="C0002", base="YUL", fleet_quals={"A321neoLR"}, position="FO", seniority=5, calendar=[]),
            # Tier 2, sen 1 (Most senior overall, but Tier 2)
            CrewMember(crew_id="C0003", base="YUL", fleet_quals={"A321neoLR"}, position="FO", seniority=1, 
                       calendar=[Block(start=150.0, end=250.0, btype=BlockType.PAIRING)]),
        ]
        
        chosen = select_draft_candidate(roster, duty, cfg=cfg)
        if chosen:
            print(f"Selected: {chosen.crew_id} (seniority {chosen.seniority})")
        else:
            print("No candidate found")
        return 0
    if args.cmd == "explain-cost":
        from .engine import des
        from .engine.ledger import LedgerRow
        from .engine.policy import load_policy

        cfg = config.load()
        costs = config.load_costs(cfg)
        policy = load_policy(_resolve_policy_path(args.policy or DEFAULT_EXPLAIN_POLICY))
        sim = des.run_scenario(
            cfg, costs, policy, scenario_id=args.scenario, master_seed=args.master_seed,
            n_scenarios=args.scenario + 1,
        )
        rows = sim.ledger.rows
        print(f"Scenario {args.scenario}, policy {policy.policy_id}, master_seed={args.master_seed!r} "
              f"-- {len(rows)} real ledger rows, {_money(sim.ledger.total_cost())} total\n")

        if getattr(args, "trace_root", False):
            # Group the real ledger by causal chain. root_event_uid == 0 is
            # des.py's sentinel for cost with no causal chain at all (daily
            # RESERVE_STAFFING), so those rows are not a chain and are skipped.
            chains: dict[int, list[LedgerRow]] = {}
            for r in rows:
                if r.root_event_uid == 0:
                    continue
                chains.setdefault(r.root_event_uid, []).append(r)
            if not chains:
                print("No causally-rooted cost in this scenario -- every row is structural "
                      "(root_event_uid 0). Try another --scenario.")
                return 1

            # Prefer the DEEPEST chain that reaches a cancellation -- the trace
            # this command exists to show is a cancellation walked back through
            # its cascade to the originating sick call, and a single expensive
            # row demonstrates nothing about traversal. Depth first, cost as the
            # tiebreak; fall back to the deepest chain of any shape, and always
            # name the rule used rather than quietly showing something else.
            def chain_rank(item: tuple[int, list[LedgerRow]]) -> tuple[int, float]:
                return len(item[1]), sum(r.amount for r in item[1])

            with_cancellation = {u: c for u, c in chains.items()
                                 if any(r.category == "CANCELLATION" for r in c)}
            if with_cancellation:
                root_uid, chain = max(with_cancellation.items(), key=chain_rank)
                selection = "deepest chain ending in a CANCELLATION"
            else:
                root_uid, chain = max(chains.items(), key=chain_rank)
                selection = ("deepest chain (no chain in this scenario reached a "
                             "CANCELLATION -- every item was covered)")
            chain = sorted(chain, key=lambda r: r.sim_time)
            origin = chain[0].sim_time
            depths: dict[int, int] = {}
            for c in chains.values():
                depths[len(c)] = depths.get(len(c), 0) + 1
            print(f"Tracing root event {root_uid} -- {selection}.")
            print(f"  origin: t={origin:,.0f} min (day {origin / 1440:.1f}), "
                  f"{len(chains)} causal chain(s) in this scenario")
            # Chain depth is real information about this corpus, not a detail to
            # bury: S1d-04c/S1d-04d already found cascades are rare at
            # production roster scale, so most chains here are a single row and
            # a reader should see that rather than infer depth from one example.
            print("  chain depth: " + ", ".join(
                f"{n} row(s) x{count}" for n, count in sorted(depths.items())) + "\n")
            for r in chain:
                crew = r.crew_id or "-"
                print(f"  [t={r.sim_time:>9,.0f}  day {r.sim_time / 1440:>5.1f}]  "
                      f"{r.category:<22} {_money(r.amount):>14}  event {r.event_uid:<5} crew {crew}")
            print(f"\n  Total attributable to root event {root_uid}: "
                  f"{_money(sum(r.amount for r in chain))}")
            return 0

        if getattr(args, "summary", False):
            measured = des.rows_in_measurement_window(cfg, sim)
            wanted = [args.category] if args.category else None
            all_cats = sorted({r.category for r in rows})
            if wanted and wanted[0] not in all_cats:
                print(f"error: category {wanted[0]!r} not in this scenario's ledger "
                      f"(present: {all_cats})")
                return 1
            for category in (wanted or all_cats):
                cat_all = [r for r in rows if r.category == category]
                cat_measured = [r for r in measured if r.category == category]
                print(f"{category}")
                print(f"  measured window ({cfg.horizon.measurement_days}d): "
                      f"{_money(sum(r.amount for r in cat_measured))} over {len(cat_measured)} row(s)")
                print(f"  whole horizon   ({cfg.horizon.horizon_days}d): "
                      f"{_money(sum(r.amount for r in cat_all))} over {len(cat_all)} row(s)")
                if category == "RESERVE_STAFFING" and cat_measured:
                    # Show the derivation so the figure is checkable on paper,
                    # from the rows themselves -- reserves are paid at that
                    # day's own SC/LC rate (des.py::_book_reserve_staffing), so
                    # there is no single "rate x reserves x days" to quote.
                    n_crew = len({r.crew_id for r in cat_measured})
                    n_days = len({int(r.sim_time // 1440) for r in cat_measured})
                    by_rate: dict[float, int] = {}
                    for r in cat_measured:
                        by_rate[r.amount] = by_rate.get(r.amount, 0) + 1
                    breakdown = " + ".join(
                        f"{n} reserve-day(s) @ {_money(rate)}" for rate, n in sorted(by_rate.items())
                    )
                    print(f"  derivation: {n_crew} reserve(s) x {n_days} measured day(s) "
                          f"= {len(cat_measured)} reserve-day(s)")
                    print(f"              {breakdown}")
            return 0

        for category, amount in sorted(sim.ledger.sum_by_category().items()):
            print(f"  {category:<22} {_money(amount)}")
        print("\n(--trace-root walks one cost back to its originating sick call; "
              "--summary [--category X] breaks totals down by measurement window)")
        return 0
    if args.cmd == "explain-recovery":
        from .engine import des
        from .engine.policy import load_policy

        cfg = config.load()
        costs = config.load_costs(cfg)
        pol_path = config.repo_root() / "configs" / "policies" / f"{args.policy}.yaml"
        policy = load_policy(pol_path)

        sim = des.run_scenario(
            cfg, costs, policy, scenario_id=args.scenario, master_seed=args.master_seed,
            n_scenarios=args.scenario + 1, trace=args.trace,
        )

        print(f"Recovery pipeline -- scenario {args.scenario}, policy {policy.policy_id}")
        if args.trace:
            print()
            for line in sim.trace:
                print(f"  {line}")
        totals = sim.ledger.sum_by_category()
        print("\nLedger totals:")
        for category, amount in sorted(totals.items()):
            print(f"  {category:24s} ${amount:,.2f}")
        print(f"\nTotal cost: ${sim.ledger.total_cost():,.2f}")
        print(f"Drafts: {sim.n_drafts} ({sim.n_cascading_drafts} cascading)")
        return 0
    if args.cmd == "report":
        from .reporting.report import build_report

        policy_names = args.policies
        if args.policy and not policy_names:
            policy_names = [args.policy]
        elif args.policy and args.policy not in policy_names:
            policy_names = [*policy_names, args.policy]
        if not policy_names:
            print("error: report needs --policies and/or --policy")
            return 1

        cfg = config.load()
        costs = config.load_costs(cfg)
        print(f"Building report: {len(policy_names)} polic(y/ies) x {args.scenarios} scenario(s) each...")
        path = build_report(
            cfg, costs, policy_names, args.scenarios, args.master_seed,
            representative_policy=args.representative_policy or args.policy,
            drilldown_policy=args.policy or args.representative_policy or policy_names[0] if args.drilldown else None,
            drilldown_mode=args.drilldown,
        )
        print(f"wrote {path}")
        if getattr(args, "open", False):
            import webbrowser
            webbrowser.open(path.as_uri())
        return 0
    if args.cmd == "grid":
        from .reporting.grid import load_grid_config, print_grid_report, run_grid, write_grid_csv

        grid_path = args.config or str(config.repo_root() / "configs" / "grid_mvp.yaml")
        policy_names = load_grid_config(grid_path)
        cfg = config.load()
        costs = config.load_costs(cfg)
        print(f"Running grid: {len(policy_names)} combination(s) x {args.scenarios} scenario(s) "
              f"each (CRN-paired, master_seed={args.master_seed!r})...")
        results = run_grid(cfg, costs, policy_names, args.scenarios, args.master_seed,
                            jobs=args.jobs, on_progress=_stderr_progress("policy"))
        print(file=sys.stderr)
        print_grid_report(results)
        out_path = write_grid_csv(cfg, results)
        print(f"wrote {out_path}")
        return 0
    if args.cmd == "counterfactual":
        from .engine.policy import load_policy
        from .reporting.counterfactual import (
            print_counterfactual_report,
            run_counterfactual_comparison,
        )

        cfg = config.load()
        costs = config.load_costs(cfg)
        policy = load_policy(_resolve_policy_path(args.policy))
        print(f"Running counterfactual comparison: policy {policy.policy_id}, "
              f"{args.scenarios} scenario(s), 3 draft_modes (CRN-paired)...", file=sys.stderr)
        results = run_counterfactual_comparison(cfg, costs, policy, args.scenarios, args.master_seed)
        print_counterfactual_report(policy.policy_id, results)
        return 0
    if args.cmd is None:
        ap.print_help()
        return 0
    return _todo(args.cmd)

if __name__ == "__main__":                            # `python -m crewsim.cli`
    sys.exit(main())
