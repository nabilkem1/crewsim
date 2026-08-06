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
    for key in ("corpus_dir", "params_dir", "reports_dir"):
        try:
            p = config.resolve(cfg, key)
        except KeyError as exc:
            problems += 1
            print(f"    {BAD} {exc}")
            continue
        mark = OK if p.is_dir() else BAD
        if not p.is_dir():
            problems += 1
        print(f"    {mark} {key:<12} {p.relative_to(config.repo_root())}")

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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="crewsim")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("doctor", help="report project structure and resolve paths")
    for name, helptext in [
        ("run", "run one policy over the CRN scenario set"),
        ("compare", "paired CRN comparison of two or more policies"),
        ("calibrate", "fit the parameter store from the corpus"),
        ("gate", "run a V&V gate"),
        ("config", "show the resolved configuration"),
    ]:
        sub.add_parser(name, help=helptext)
    args = ap.parse_args(argv)
    if args.cmd == "doctor":
        return doctor()
    if args.cmd is None:
        ap.print_help()
        return 0
    return _todo(args.cmd)


if __name__ == "__main__":                            # `python -m crewsim.cli`
    sys.exit(main())
