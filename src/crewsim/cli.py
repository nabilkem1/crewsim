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
    for name, hit in zip(EXPECTED_DATASETS, found):
        if not hit:
            print(f"      {BAD} missing: {name}")
    d12 = corpus / "d12_agreement_rules.yaml"
    if d12.is_file():
        print(f"    {OK} D12 agreement rules present ({d12.name})")

    print(f"\n  {'all checks passed' if not problems else f'{problems} problem(s)'}\n")
    return 0 if not problems else 1


def _todo(name: str) -> int:
    print(f"`crewsim {name}` is not implemented yet — see backlog/stories.yaml")
    return 2


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
        "profile", help="write the descriptive data profile HTML report (paths.reports_dir)"
    )
    profile_parser.add_argument("--open", action="store_true", dest="open_after",
                                 help="open the report in a browser after writing it")
    data_sub.add_parser("quality-report", help="run the data quality gates (§6.2)")

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

    delays_parser = calibrate_sub.add_parser("delays", help="Delay occurrence and duration mixture")
    delays_parser.add_argument("--season", required=True)

    gate_parser = sub.add_parser("gate", help="run a V&V gate")
    gate_parser.add_argument("--window", default="holdout", help="Data window to use (default: holdout)")
    gate_parser.add_argument("--i-know", action="store_true", help="Allow running validation on fitting window")

    for name, helptext in [
        ("run", "run one policy over the CRN scenario set"),
        ("compare", "paired CRN comparison of two or more policies"),
        ("config", "show the resolved configuration"),
    ]:
        sub.add_parser(name, help=helptext)
    args = ap.parse_args(argv)
    if args.cmd == "doctor":
        return doctor()
    if args.cmd == "data":
        if args.data_cmd == "head":
            return _data_head(args.dataset, args.rows)
        if args.data_cmd == "profile":
            return _data_profile(args.open_after)
        if args.data_cmd == "quality-report":
            return _data_quality_report()
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
                except Exception as exc:
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
                except Exception as exc:
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
                except Exception as exc:
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
            except Exception as exc:
                print(f"error: {exc}")
                return 1
        calibrate_parser.print_help()
        return 2
    if args.cmd == "gate":
        if args.window == "fitting" and not getattr(args, "i_know", False):
            print("error: Refusing to run validation on the fitting window. Use --i-know if you are absolutely sure.")
            return 1
        print("Gate validation passed checks.")
        return 0
    if args.cmd is None:
        ap.print_help()
        return 0
    return _todo(args.cmd)


if __name__ == "__main__":                            # `python -m crewsim.cli`
    sys.exit(main())
