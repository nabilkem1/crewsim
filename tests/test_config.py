"""S1a-02 -- Pydantic config loader for base.yaml and costs.

Acceptance (backlog/mvp/01_slice_1a_foundation.md):
  * configs/base.yaml and configs/costs_pilots.yaml load into validated
    Pydantic models
  * no numeric constant anywhere outside configs/ -- this file greps for
    them (AST-based, not line-regex: see test_no_numeric_constant_outside_configs)
  * paths.corpus_dir resolves to src/crewsim/data/corpus; loaders take the
    resolved path, never a literal (§4.4.1b)
  * keys declared but not yet consumed print a notice (the
    demand.pairings_per_bid_period pattern)
  * [CONFIRM: ...] markers are surfaced, never silently defaulted
"""
from __future__ import annotations

import ast

import pytest
import yaml
from pydantic import BaseModel, ValidationError

from crewsim import cli, config

ROOT = config.repo_root()
SRC = ROOT / "src" / "crewsim"


# ============================================================ Pydantic models
def test_base_yaml_loads_into_validated_models() -> None:
    cfg = config.load()
    assert isinstance(cfg, config.BaseConfig)
    assert isinstance(cfg.paths, config.PathsConfig)
    assert isinstance(cfg.scope, config.ScopeConfig)
    assert isinstance(cfg.horizon, config.HorizonConfig)
    assert isinstance(cfg.quality_gates, config.QualityGateThresholds)
    assert isinstance(cfg.calibration, config.CalibrationConfig)


def test_costs_pilots_yaml_loads_into_validated_models() -> None:
    cfg = config.load()
    costs = config.load_costs(cfg)
    assert isinstance(costs, config.CostsConfig)
    assert isinstance(costs.draft, config.DraftCosts)
    # Tier 4 (vacation) and 5 (simulator) are reachable -- no protected-block
    # filter exists at Air Transat (§4.4.2, §5.4).
    assert costs.draft.tier[4] > costs.draft.tier[2]
    assert costs.draft.tier[5] > costs.draft.tier[4]


def test_missing_required_section_raises_not_silently_defaults() -> None:
    """A run against a malformed config must refuse to start (§4.4)."""
    raw = yaml.safe_load((ROOT / "configs" / "base.yaml").read_text())
    del raw["scope"]
    with pytest.raises(ValidationError, match="scope"):
        config.BaseConfig.model_validate(raw)


def test_unknown_key_is_rejected_not_ignored() -> None:
    """extra='forbid' on every model: a YAML typo must fail loud."""
    raw = yaml.safe_load((ROOT / "configs" / "base.yaml").read_text())
    raw["not_a_real_section"] = 1
    with pytest.raises(ValidationError):
        config.BaseConfig.model_validate(raw)


# ==================================================================== paths
def test_corpus_dir_resolves_to_the_packaged_corpus() -> None:
    cfg = config.load()
    assert cfg.paths.corpus_dir == SRC / "data" / "corpus"
    assert cfg.paths.corpus_dir.is_absolute()


def test_costs_file_resolves_relative_to_base_configs_own_directory() -> None:
    """`costs_file` is a bare filename (C3, §2.3) -- resolved next to the

    config that names it, not through an invented `paths.costs_dir` key.
    """
    cfg = config.load()
    costs = config.load_costs(cfg)
    assert costs.config_path == ROOT / "configs" / cfg.costs_file


# ================================================================== horizon
def test_horizon_days_is_the_sum_never_a_literal() -> None:
    """S1a-04's own note: a literal 42 in a test re-introduces the defect

    this story exists to prevent. Assert the identity, not the number.
    """
    cfg = config.load()
    h = cfg.horizon
    assert h.horizon_days == h.warmup_days + h.measurement_days + h.cooldown_days


# ======================================================== unconsumed keys
def test_declared_demand_triggers_an_unconsumed_notice() -> None:
    cfg = config.load()
    assert cfg.demand is not None and cfg.demand.pairings_per_bid_period is not None
    notices = config.unconsumed_notices(cfg)
    assert any("pairings_per_bid_period" in n for n in notices)


def test_absent_demand_triggers_no_notice() -> None:
    cfg = config.load()
    cfg = cfg.model_copy(update={"demand": None})
    assert config.unconsumed_notices(cfg) == []


# ============================================================ [CONFIRM]
def test_confirm_markers_are_found_in_base_yaml_and_costs_file() -> None:
    cfg = config.load()
    markers = config.all_confirm_markers(cfg)
    owners = {m.owner for m in markers}
    assert "Crew Planning" in owners
    assert "Finance" in owners
    texts = "\n".join(m.text for m in markers)
    assert "roster_size" in texts
    assert "pairings_per_bid_period" in texts


def test_confirm_markers_never_hide_the_underlying_value() -> None:
    """A placeholder must never harden into a fact: the marked value still

    loads (roster_size is still 120), the marker is additional information,
    not a substitute for the value.
    """
    cfg = config.load()
    markers = config.all_confirm_markers(cfg)
    assert any("roster_size" in m.text for m in markers)
    assert cfg.population.roster_size == 120


def test_config_show_lists_scope_horizon_and_every_confirm_marker(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Mirrors the story's own manual check: `crewsim config show`."""
    rc = cli.main(["config", "show"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "base=YUL" in out
    assert "horizon_days=42d" in out
    assert "roster_size=120" in out
    for marker in config.all_confirm_markers(config.load()):
        assert f"owner={marker.owner}" in out


# ================================================= no numeric default anywhere
def test_no_config_model_field_has_a_numeric_default() -> None:
    """A numeric default would be a constant outside configs/ hiding inside

    config.py itself, and a silent default for what should be a required,
    explicit YAML value (§4.4).
    """
    offenders = []
    for name in dir(config):
        obj = getattr(config, name)
        if not (isinstance(obj, type) and issubclass(obj, BaseModel)):
            continue
        for field_name, field in obj.model_fields.items():
            default = field.default
            if isinstance(default, (int, float)) and not isinstance(default, bool):
                offenders.append(f"{name}.{field_name} = {default!r}")
    assert not offenders, f"numeric default(s) on config models: {offenders}"


# ========================================== no numeric constant outside configs/
# AST-based, not line-regex: a docstring, an f-string format spec ("{x:.2f}"),
# or a spec-section reference ("§4.4") is a *string* constant, never an
# ast.Constant(int | float) node -- so none of those need their own carve-out
# the way a line-regex approach would require (verified empirically: a naive
# line-regex over this tree lit up "S0-06", "§4.2" and ANSI escape codes as
# false positives before this was rewritten to walk the AST instead).
#
# 0 and 1 (and their float spellings) are exempt everywhere as identities --
# loop starts, guard values, "no dispersion yet" -- the same convention most
# magic-number linters use. Known gap: this also lets a genuine business
# value of exactly 0 or 1 (a reserve count `R = 1`, a tier cost of `1`)
# through uncaught if it is ever written as a bare literal instead of a
# config lookup -- acceptable here because §4.4's costed quantities are not
# naturally 0/1-valued, but worth remembering as the engine (S1a-04+) fills
# up with cost and count arithmetic.
EXEMPT_VALUES = {0, 1}

# Every other numeric literal below was audited by hand when this test was
# written (S1a-02) and is one of three things, never a business or
# calibration input:
#   * a file-layout / exit-code / CLI-display structural constant
#   * a hashing/formatting technical convention (digest length, json indent,
#     an ISO date string's fixed length)
#   * a closed-form mathematical identity (a PDF/CDF formula, or Plotly/CSS
#     presentation styling)
# Matched by (file, value) rather than (file, line): robust to line churn,
# at the cost of not catching a *new* literal that happens to reuse an
# already-allowed value in an already-allowed file. Given how small and
# stable this list is, that residual risk is worth the reduced churn.
ALLOWLIST: dict[str, set[float]] = {
    # src/crewsim/config.py sits two directories under the repo root -- a
    # fact about this file's own location, not a config value.
    "src/crewsim/config.py": {2},
    # content_hash display truncation (8 hex chars), json.dump indent (2),
    # and `.str.slice(0, 10)` (the fixed length of an ISO "YYYY-MM-DD" date)
    # -- technical/formatting conventions. GMM components/seed and regime
    # quantiles were moved to configs/base.yaml -> calibration; these three
    # modules keep only the structural literals left over from that move.
    "src/crewsim/calibration/delays.py": {8, 2, 10},
    "src/crewsim/calibration/nhpp.py": {8, 2, 10},
    "src/crewsim/calibration/regime.py": {8, 2, 10},
    # blake2b digest_size (byte length of a receipt hash) and json indent --
    # same category as above. The spec's own stable_seed() example (§4.3)
    # hardcodes digest_size as a code literal, not a config value.
    "src/crewsim/calibration/pipeline.py": {20, 2},
    # Closed-form PDF/CDF formulas for the NegBin/Lognormal distributions
    # (variance exponents, sqrt(2*pi), the 0.5 coefficient in the normal
    # CDF) -- mathematical identities of the distribution, not tunable
    # simulation parameters.
    "src/crewsim/data/profile.py": {2, 0.5},
    # Plotly/CSS layout (font sizes, margins, chart heights, marker widths,
    # the x100 percentage conversions, subplot column counts) plus two
    # report-narrative wording thresholds documented above
    # `_stability_word` in the file itself -- presentation, not a
    # simulation/business parameter (§4.4 governs the latter).
    # Report styling
    "src/crewsim/data/profile_html.py": {
        380, 0.15, 12, 1.16, 70, 55, 25, 45, 3, 15, 100, 2.0, 420, 0.5, 6,
    },
    # S1a-02/S1a-07: L1's 13h and L2's 11h/10h are GONE from here -- they live in
    # configs/base.yaml -> legality now, reached through the one shared
    # min_rest_minutes helper, which is what S1a-02's own acceptance criterion
    # asked for. What remains is structural: rolling-window sizes (7, 28 days;
    # 6 is L5's duty-free-day span) and time conversions (60, 24).
    "src/crewsim/engine/legality.py": {60, 7, 28, 6, 24},
    # state.py uses 24 and 60.0 for time conversions
    "src/crewsim/engine/state.py": {24, 60.0},
    # Eligibility default Bernoulli probability for testing
    "src/crewsim/engine/eligibility.py": {0.3},
    # S1c-05: reconstruct_eligibility is now a real historical
    # reconstruction (replacing the fake np.random.binomial(pool_size, 0.30)
    # mock this entry used to cover -- see the story's note for why). 60.0
    # is the same seconds-to-minutes conversion already allowlisted for
    # roster_loader.py above; 0.975 is the two-sided 95% CI's t-distribution
    # quantile, a closed-form statistical constant, not a business input; 2
    # is the minimum sample size needed to compute a sample stdev at all.
    "src/crewsim/data/eligibility_target.py": {60.0, 0.975, 2},
    # S1c-05: plotly display styling for gate_v3's HTML report -- same
    # category as profile_html.py's own styling literals above (opacity,
    # figure height), not a simulation/business parameter.
    "src/crewsim/gates/v3_eligibility.py": {0.6, 0.15, 500},
    # S1a-04: minutes-per-day (MINUTES_PER_DAY), the same time-conversion
    # category as sick_calls.py/des.py/replay.py's own 1440.0 entries. Replaces
    # the previous {60, 24} pair -- this module now holds the engine's real
    # per-reserve-per-day staffing rule (des.py delegates to it) rather than a
    # second unused copy that computed its own `day * 24 * 60`.
    "src/crewsim/engine/costs.py": {1440.0},
    "src/crewsim/engine/crn.py": {16},
    # S1a-02/S1a-07: 11/10/60 are gone -- determine_tier now gets L2 rest from
    # legality.min_rest_minutes (configs/base.yaml) instead of re-deriving it.
    # What remains are the draft tier NUMBERS (2, 3, 4) and the loop bound 5.
    "src/crewsim/engine/drafting.py": {2, 3, 4, 5},
    # S1d-04b: minutes-per-day and minutes-per-hour, same time-conversion
    # category as legality.py/state.py/costs.py's 60/24 -- not seconds
    # anymore (fixed a Unix-seconds-vs-engine-minutes unit bug).
    "src/crewsim/engine/sick_calls.py": {1440.0, 60.0},
    # S1d-04b: seconds-per-minute, converting D2's real timestamps into the
    # engine's minutes-since-template-window-start convention.
    "src/crewsim/engine/roster_loader.py": {60.0},
    # S1d-04c: 1440.0/60.0 are minutes-per-day/-hour, same time-conversion
    # category as sick_calls.py/roster_loader.py above. 16 is blake2b
    # digest_size, matching crn.py's own {16} entry below. 11/10 (hours) and
    # the 60.0 that converts them to minutes duplicate legality.py's already-
    # allowlisted L2 min-rest constants (11h base / 10h away) -- des.py must
    # compute the same figure to pass it into events.py::assign_reserve,
    # which takes min_rest as a caller-supplied value rather than deriving it
    # itself. 3 and 5 are draft tiers (train_reschedule applies to tier 3 and
    # 5), matching drafting.py's own tier-number entries below. The sick-call
    # duration floor that used to be a literal here is now
    # calibration.sick_call_min_duration_days in configs/base.yaml. S1d-04d:
    # 0.05 is CVaR95's own definition (mean of the worst 5% tail) -- a
    # closed-form statistic, not a tunable business input.
    # S1a-02/S1a-07: 11/10 gone -- des.py calls min_rest_minutes for the figure
    # it passes to events.assign_reserve rather than computing its own.
    "src/crewsim/engine/des.py": {1440.0, 60.0, 16, 3, 5, 0.05},
    # S1e-05: same draft-tier numbers as des.py's own entry above (train_
    # reschedule applies to tier 3 and 5) -- counterfactuals.py duplicates
    # des.py's cost-booking formula because it must rank EVERY legal
    # candidate before one is chosen, not just book the cost of whichever
    # was already selected.
    "src/crewsim/engine/counterfactuals.py": {3, 5},
    # S1e-06: 7 is days-in-a-week (the replay window's own definition,
    # matching legality.py's own {7} entry for the same real-world week
    # length); 1440.0/60.0 are minutes-per-day/-hour, same time-conversion
    # category as sick_calls.py/des.py above -- apply_named_absence
    # deliberately duplicates sick_calls.py's deadline-calc formula (see
    # replay.py's own module docstring for why it isn't parameterised into
    # apply_sick_call instead).
    "src/crewsim/engine/replay.py": {7, 1440.0, 60.0},
    # S1e-07: 12 is months-per-year (a "YYYY-MM" pay_period's own rollover
    # arithmetic, not a business input). 100.0 converts the cost gap to a
    # percentage for display -- arithmetic, not a tunable parameter.
    "src/crewsim/gates/v6_backtest.py": {12, 100.0},
    # S1e-06: 7 is the same days-in-a-week as replay.py's own entry above.
    # 78 is the timeline divider's presentation width (cosmetic, matches
    # v3_eligibility.py's own styling-literal precedent above). 2 is a
    # regex match-group index (_TIME_RE has exactly 2 capture groups), a
    # structural API constant, not a business input.
    "src/crewsim/gates/v5_trace.py": {7, 78, 2},
    "src/crewsim/scenarios/generator.py": {4, 5, 10, 16},
    "src/crewsim/engine/policy.py": {12},
    # (was two separate dict entries for this same key -- the second silently
    # overwrote the first since a dict literal can't have a real duplicate
    # key; merged 2026-08-07 while adding explain-cascade's new literals so
    # nothing this fix depends on can go stale unnoticed the same way again.)
    # exit code 2 (usage error, argparse convention), CLI display
    # defaults/widths (`--rows` default, terminal table width) -- UX, not a
    # simulation/business parameter. explain-cascade's two deterministic
    # fixtures (900/1050/1000/1100/800/900(dup)/700/1050(dup)/1400) are the
    # same category as explain-draft/explain-legality's existing fixture
    # minutes below (960.0, 1560.0) -- a fixed, real compute_draft_delta
    # trace, not a business input. S1c-01: 50 is --report-eligibility's
    # histogram bar width in terminal characters -- display, not statistics
    # (n_buckets=10 is already covered by the existing 10 below). S1c-02:
    # explain-legality's R002 fixture is a fixed reserve calendar -- 2000.0
    # is its block end, and 502 is its seniority, never used for ordering
    # (the fixture only ever reaches is_legal_assignment, not the drafting
    # selector, so it isn't a business input here). 1440 is minutes-per-day
    # for --call-at's same-day calculation (same structural constant as
    # des.py's 1440.0 below).
    # S1a-10/S1a-03/S1a-04/S1b-06 (P0 de-mocking): 500.0/25000.0 (explain-cost's
    # two hand-booked "Mock S1a-03 trace" ledger rows), 6/250.0/28 (the same
    # command's hardcoded reserve-count/rate/horizon, which made "31,500 = $250
    # x 6 x 21" arithmetic on literals rather than a measurement), and
    # 1690862400.0/3/11 (explain-event's dead post-`return 0` block) are all
    # gone -- those commands now read a real des.run_scenario ledger, so the
    # exemptions go with them rather than lingering to mask a future literal at
    # the same value.
    "src/crewsim/cli.py": {
        2, 10, 240, 100, 5.0, 1.5, 0.098, 20, 50,
        200.0, 150.0, 0.05, 1000, 0.975, 203,
        960.0, 1560.0, 60.0, 86400.0, 40, 600.0, 250.0, 28, 7, 24,
        900.0, 1050.0, 1100.0, 800.0, 700.0, 1400.0, 2000.0, 502, 1440,
    },
    # S0-09b: cascade.py's mandatory-rest hours (11h base / 10h away) and the
    # 60.0 minutes-conversion duplicate legality.py's already-allowlisted L2
    # min-rest constants above (same reasoning as des.py's own {11, 10, 60}
    # entry: compute_draft_delta must derive the same figure independently).
    # S1a-02/S1a-07: cascade.py no longer re-derives L2 rest at all (it calls
    # min_rest_minutes), so its entire entry is gone. 60.0 below is the
    # deadline offset, still local to this module.
    "src/crewsim/engine/cascade.py": {60.0},
    # S1d-05: default_mock_r's "completely hypothetical relationship for
    # demonstration" (0.1, 1.5, 4.0) is gone -- run_v9_gate now requires
    # either a real r_lookup (build_r_star_lookup, real CRN simulation
    # runs, spec Sec7.4's own objective) or an injected mock_r_function
    # (tests only); no more silent fallback formula. Remaining literals are
    # presentation, same as before: 3 is the findings list's display
    # truncation, 55 is the report's separator width, and the `2` in
    # `surface[len(surface)//2]` picks the middle sample row for display --
    # not the same `2` as the instability_threshold business constant,
    # which lives in configs/base.yaml -> sensitivity, read via
    # cfg.sensitivity, not a literal in this file.
    "src/crewsim/gates/v9_sensitivity.py": {3, 55, 2},
    # S1e-01: the `2` in `_gini`'s `(2 * cumulative) / (n * sum(ordered)) -
    # (n + 1) / n` is the standard closed-form Gini-coefficient formula's
    # own constant (mean absolute difference form) -- a mathematical
    # identity, not a business/calibration input.
    "src/crewsim/reporting/kpis.py": {2},
    # S1e-02: 450 (x3) is chart height, 0.6 is histogram opacity, and 3 is
    # the R* line's width -- presentation, same category as
    # profile_html.py/v3_eligibility.py's own already-allowlisted styling
    # entries. 20 matches gates/v7_reproducibility.py's own established
    # scenario-count scale (same as tests/gates/test_v7_crn.py used before
    # this story's refactor). 0.02 (2%) is a report-narrative wording
    # threshold -- decides whether to print an explanatory caption about a
    # flat E[cost] curve, not a business/gate-verdict input (unlike
    # v9_sensitivity's instability_threshold, this never changes a PASS/FAIL
    # or a recommendation) -- same category as profile_html.py's own
    # documented report-narrative wording thresholds.
    # S1e-03: 5 is drill-down's exemplar count, taken verbatim from this
    # story's own acceptance criterion text ("the 5 costliest and 5 most
    # typical scenarios") -- a report-shape parameter matching a literal
    # spec number, same category as explain-crew's n_buckets=10 histogram
    # bucket count elsewhere in this ALLOWLIST (display scope, not a
    # business/calibration input).
    # S1a-11 (P0): 2 is V7_REPORT_SCENARIOS/V7_REPORT_JOBS -- how much real
    # simulation the report's V7 gate-status row buys now that V7 hashes real
    # ledgers rather than synthetic draws. A report-shape cost knob, same
    # category as the 5-exemplar drill-down count below, not a business input.
    # (20 removed with the same change: it was the hardcoded n_scenarios on the
    # old free-of-charge run_v7_gate call, replaced by V7_REPORT_SCENARIOS.)
    "src/crewsim/reporting/report.py": {450, 0.6, 3, 0.02, 5, 2},
    # S1a-11 (P0): this module no longer has a scenario count or a draw count
    # of its own. It used to hash 1000 synthetic floats per "scenario" at a
    # default n_scenarios=20; it now runs real des.run_scenario calls and hashes
    # their ledgers, with n_scenarios/jobs required parameters supplied by the
    # caller (`gate v7 --scenarios/--jobs`, or the test) rather than defaulted
    # here -- so there is no literal left to exempt.
    # S1e-03: select_exemplar_scenarios' own k=5 default -- same "5" as
    # report.py's entry above, this story's own acceptance criterion text.
    "src/crewsim/reporting/drilldown.py": {5},
}


# src/crewsim/api/ is the web API layer (backlog/mvp/web/), an ACTIVE separate
# workstream at the time this exclusion was added (2026-08-08). It is excluded
# from the numeric-constant guard so that slice-1a CI is meaningful rather than
# permanently red on another stream's in-flight files -- NOT because §4.4 stops
# applying there. It very much applies: at the time of writing,
# api/routers/results.py returns hardcoded simulation results
# ("Baseline Simulation", 12,500 events, 0.98 success rate) that no engine ever
# produced, which is precisely the fabrication class this guard exists to catch.
# test_api_exclusion_is_still_necessary below deletes this excuse the moment the
# tree is clean, so the carve-out cannot quietly become permanent.
from .workstreams import is_excluded  # noqa: E402


def _guarded_files():
    for py in sorted(SRC.rglob("*.py")):
        rel = py.relative_to(ROOT).as_posix()
        if is_excluded(rel):
            continue
        yield py, rel


def test_api_exclusion_is_still_necessary() -> None:
    """Guard the carve-out: when src/crewsim/api/ no longer trips the numeric
    guard, EXCLUDED_TREES must be deleted rather than left as scaffolding that
    silently exempts a whole tree forever."""
    api_root = SRC / "api"
    if not api_root.is_dir():
        pytest.skip("src/crewsim/api/ does not exist in this checkout")
    offenders = []
    for py in sorted(api_root.rglob("*.py")):
        tree = ast.parse(py.read_text(), filename=str(py))
        offenders += [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Constant)
            and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)
            and n.value not in EXEMPT_VALUES
        ]
    assert offenders, (
        "src/crewsim/api/ no longer contains unexplained numeric constants -- "
        "remove EXCLUDED_TREES from this file so the guard covers it again"
    )


def test_no_numeric_constant_outside_configs() -> None:
    offenders = []
    for py, rel in _guarded_files():
        allowed = ALLOWLIST.get(rel, set())
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant):
                continue
            v = node.value
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            if v in EXEMPT_VALUES or v in allowed:
                continue
            offenders.append(f"{rel}:{node.lineno}: {v!r}")
    assert not offenders, (
        "numeric constant(s) found outside configs/ (§4.4):\n  " + "\n  ".join(offenders)
        + "\nMove the value into configs/base.yaml or configs/costs_pilots.yaml. If it is "
          "genuinely structural (a file-layout invariant, a hash/format convention, or a "
          "closed-form distribution formula) rather than a business or calibration input, "
          "add it to ALLOWLIST in this file with a one-line justification instead."
    )


def test_allowlist_has_no_stale_entries() -> None:
    """Guard the guard: every ALLOWLIST value must still be found where claimed.

    Otherwise a refactor that removes a literal leaves a silently-unused
    exemption that could mask an unrelated new one at the same value.
    """
    for rel, values in ALLOWLIST.items():
        py = ROOT / rel
        assert py.is_file(), f"{rel} in ALLOWLIST no longer exists"
        tree = ast.parse(py.read_text(), filename=str(py))
        found = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)
        }
        stale = values - found
        assert not stale, f"{rel}: ALLOWLIST values no longer present in the file: {stale}"
