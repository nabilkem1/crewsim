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
    raw = yaml.safe_load((ROOT / "configs" / "base.yaml").read_text(encoding="utf-8"))
    del raw["scope"]
    with pytest.raises(ValidationError, match="scope"):
        config.BaseConfig.model_validate(raw)


def test_unknown_key_is_rejected_not_ignored() -> None:
    """extra='forbid' on every model: a YAML typo must fail loud."""
    raw = yaml.safe_load((ROOT / "configs" / "base.yaml").read_text(encoding="utf-8"))
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


def test_absent_demand_triggers_no_demand_notice() -> None:
    """Scoped to demand: with `demand` absent, its own fields cannot report an
    unconsumed notice (there is no section to have read them from)."""
    cfg = config.load().model_copy(update={"demand": None})
    notices = config.unconsumed_notices(cfg)
    assert not [n for n in notices if n.startswith("demand.")]


def test_open_question_warning_names_policies_buying_long_call() -> None:
    """IMP-117: when every standby shift is no longer than the long-call
    notice, the warning names the policies that still buy long-call reserves,
    and no longer claims they can never be called (cross-shift calls exist)."""
    cfg = config.load()
    lc_notice = max(s.hours for s in cfg.reserve_lines.shifts)
    cfg = cfg.model_copy(update={
        "legality": cfg.legality.model_copy(update={"long_call_notice_hours": float(lc_notice)}),
    })
    warnings = config.open_question_warnings(cfg)
    assert len(warnings) == 1
    buying = config.policies_buying_long_call(cfg)
    assert buying, "the shipped policies all buy long-call reserves"
    for name in buying:
        assert name in warnings[0]
    assert "can never be legally called" not in warnings[0]


def test_no_long_call_warning_when_a_shift_outlasts_the_notice() -> None:
    cfg = config.load()
    short = min(s.hours for s in cfg.reserve_lines.shifts) / 2
    cfg = cfg.model_copy(update={
        "legality": cfg.legality.model_copy(update={"long_call_notice_hours": short}),
    })
    assert config.open_question_warnings(cfg) == []


def test_delay_per_minute_no_longer_declared_unconsumed() -> None:
    """Same precedent as test_positioning.py's positioning.deadhead/.hotel
    assertions: a field that gets wired into a real code path (here,
    engine/costs.py::book_flight_delays) must leave
    config.DECLARED_NOT_YET_CONSUMED, not linger there documenting a gap
    that no longer exists."""
    assert "disruption.delay_per_minute" not in config.DECLARED_NOT_YET_CONSUMED


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
    "src/crewsim/config.py": {2, 24, 60},
    # ^ 24 and 60 are hours-per-day and minutes-per-hour, formatting a
    #   configured on-call window as a local clock range ("06:00-18:00") --
    #   the same time-conversion category already allowlisted in
    #   legality.py/state.py/des.py, not a business input.
    # content_hash display truncation (8 hex chars), json.dump indent (2),
    # and `.str.slice(0, 10)` (the fixed length of an ISO "YYYY-MM-DD" date)
    # -- technical/formatting conventions. GMM components/seed and regime
    # quantiles were moved to configs/base.yaml -> calibration; these three
    # modules keep only the structural literals left over from that move.
    "src/crewsim/calibration/delays.py": {8, 2, 10},
    # 1e-8 is sample_count()'s NB2-to-Poisson numerical-stability threshold
    # (n = 1/alpha diverges as alpha -> 0, which IS the Poisson limit) --
    # a closed-form-adjacent numerical-stability constant, not a business
    # or calibration input.
    "src/crewsim/calibration/nhpp.py": {8, 2, 10, 1e-8, 200, 10000},
    # ^ 200/10000 (AUD-28e) are MLE optimizer iteration caps for the NB fit
    #   and its derivative-free retry -- solver-procedure invariants, not
    #   business or calibration inputs (the FIT ITSELF is what config governs).
    # F-42: regime.py no longer slices ISO date strings (10 gone) -- it works on
    # typed dates; 8 (receipt hash truncation) and 2 (json indent) remain.
    "src/crewsim/calibration/regime.py": {8, 2},
    # F-42: 2 is the number of flight-outcome probabilities per HMM state
    # (delayed q_k, cancelled r_k) in the BIC parameter count -- structural.
    "src/crewsim/calibration/hmm.py": {2},
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
    "src/crewsim/engine/eligibility.py": {0.3, 0.2},
    # ^ 0.2 is DEFAULT_P_CASCADE (AUD-21), the spec 5.7 stated default --
    #   same last-resort-fallback category as DEFAULT_P_ELIG 0.3; the real
    #   value lives in configs/base.yaml -> reduced_mode.p_cascade.
    # S1c-05: reconstruct_eligibility is now a real historical
    # reconstruction (replacing the fake np.random.binomial(pool_size, 0.30)
    # mock this entry used to cover -- see the story's note for why). 60.0
    # is the same seconds-to-minutes conversion already allowlisted for
    # roster_loader.py above; 0.975 is the two-sided 95% CI's t-distribution
    # quantile, a closed-form statistical constant, not a business input; 2
    # is the minimum sample size needed to compute a sample stdev at all.
    "src/crewsim/data/eligibility_target.py": {60.0, 0.975, 2},
    # quality_score()'s PASS=1/MARGINAL=0.5/FAIL=0 weighting and the 100x it
    # scales to a /100 display figure -- a closed-form aggregate of the real
    # per-check PASS/MARGINAL/FAIL verdicts computed above, not a separate
    # business or calibration input.
    "src/crewsim/data/quality.py": {0.5, 100},
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
    # draft_cost's own {3, 5} (train_reschedule applies to tier 3 and 5) are
    # the same tier numbers, already covered by this set -- draft_cost is
    # the single shared formula des.py's real ledger booking and
    # counterfactuals.py's ranking both call, not two copies of it.
    "src/crewsim/engine/drafting.py": {2, 3, 4, 5, 6},
    # ^ 6 is the exclusive loop bound over the five spec tiers (AUD-14 made
    #   tier 5 reachable) -- same tier-number category as 2..5.
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
    # itself. The sick-call duration floor that used to be a literal here is
    # now calibration.sick_call_min_duration_days in configs/base.yaml.
    # S1d-04d: 0.05 is CVaR95's own definition (mean of the worst 5% tail) --
    # a closed-form statistic, not a tunable business input.
    # S1a-02/S1a-07: 11/10 gone -- des.py calls min_rest_minutes for the figure
    # it passes to events.assign_reserve rather than computing its own.
    # Prod-readiness review of 05_slice_1e (2026-08-11): the draft-tier
    # numbers 3/5 that used to live here (train_reschedule applies to tier 3
    # and 5) are gone -- des.py now calls drafting.draft_cost, the single
    # shared formula, instead of carrying its own copy.
    "src/crewsim/engine/des.py": {1440.0, 60.0, 0.05},
    # ^ 16 is gone (AUD-07): the duplicated blake2b cache-key computation was
    #   removed -- des.py now delegates to generator.scenario_set_path.
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
    # S1b-07: 1440.0/60.0 are minutes-per-day/-hour, the same time-conversion
    # category as des.py/sick_calls.py above; 62 is the report separator width
    # (presentation, same category as v5_trace.py's own 78 below).
    "src/crewsim/gates/v2_erlang.py": {1440.0, 60.0, 62},
    "src/crewsim/gates/v5_trace.py": {7, 78, 2},
    # 4 is the 4-state regime Markov chain's own dimension (CALM/NORMAL/
    # DISRUPTED/SEVERE, matching regime.py's own STATES list); 16 is
    # blake2b digest_size, same convention as crn.py's own {16} entry.
    # (5 and 10 -- the fabricated base_sick/base_delay constants -- are gone:
    # sick-call counts now come from the fitted NHPP GLM via
    # calibration.nhpp.predict_intensity/sample_count, not a hardcoded mean.)
    "src/crewsim/scenarios/generator.py": {4, 16},
    "src/crewsim/engine/policy.py": {12},
    # ---------------------------------------------------------------- web API
    # src/crewsim/api/ used to be exempt from this guard wholesale (EXCLUDED_TREES
    # in tests/workstreams.py, now deleted). The carve-out's stated reason was
    # that results.py and provenance.py returned fabricated simulation figures --
    # "Baseline Simulation", 12,500 events, a 0.98 success rate. Those routers
    # are gone, along with analytics.py's invented cascade costs and data.py's
    # hardcoded data-quality score of 95: an endpoint with nothing real to report
    # now returns an empty collection and an `implemented: false` flag rather
    # than a plausible number (see api/mocks.py).
    #
    # What is left below is HTTP and presentation, never a business or
    # calibration input:
    #   400/404  - HTTP status codes (protocol constants)
    #   100      - percent, for progress arithmetic
    #   10/20    - how many rows a dashboard endpoint returns
    #   1024/3/2 - bytes->MB/GB arithmetic and round() precision
    # (404 left calibration.py and jobs.py with IMP-612: their not-found path
    # is the shared api/db.get_job_or_404, which uses HTTPStatus.NOT_FOUND.)
    "src/crewsim/api/routers/calibration.py": {400, 100},
    "src/crewsim/api/routers/config.py": {404},
    # 400/404 are HTTP status codes, same category as this section's other
    # entries. This router computes nothing -- it reads cascade figures a
    # completed batch job already stored (see the module docstring on why it
    # must not run its own scenarios), so it has no business constants to hide.
    "src/crewsim/api/routers/analytics.py": {400, 404, 25},
    # 404/422/503 are HTTP status codes (503 = the corpus/params store is not
    # available), same category as this section's other 400/404 entries. 50/500
    # are the corpus grid's default and maximum page size -- presentation, and
    # the cap is what stops one request asking the server to serialise all
    # 511,664 rows of d3_pairing_legs into a single JSON body. 2 is how many
    # parsed datasets the LRU holds.
    #
    # NB this was briefly two separate entries for the same key, added by two
    # people at once. A dict literal keeps only the last, so the first one's
    # values silently stopped being exempt -- merged, and worth remembering
    # the next time this list grows.
    "src/crewsim/api/routers/data.py": {404, 422, 503, 50, 500, 2},
    "src/crewsim/api/routers/jobs.py": {400, 10, 100},
    "src/crewsim/api/routers/platform.py": {100, 1024, 3, 2},
    # 4 is the number of steps the batch job's execution log reports (a
    # property of the log format, like a progress bar's segment count); 3 is
    # the same thing for the drill-down job (WN-008), which has one fewer
    # phase. The SSE poll interval and timeout moved to api/streaming.py when
    # the calibration router started sharing them; the digest-display width
    # lives in reporting/provenance.py. 5 is the costliest/typical exemplar
    # count passed to select_exemplar_scenarios -- same structural constant
    # as reporting/drilldown.py's own {5} entry below.
    "src/crewsim/api/routers/processing.py": {400, 404, 409, 10, 100, 4, 3, 5, 8},
    # 1440/60 are minutes-per-day and minutes-per-hour -- the same
    # time-conversion category already allowlisted for engine/legality.py,
    # state.py and des.py. The tape renders a simulated minute as "day 26
    # 09:23", which is the only arithmetic in this module.
    "src/crewsim/reporting/tape.py": {1440, 60},
    # Minutes-per-day again, for bucketing a ledger row's sim_time into the
    # horizon day the fingerprint strip draws. Same time-conversion category.
    "src/crewsim/reporting/grid.py": {1440.0},
    # 0.5s is how often the SSE endpoint re-reads the job row and 3600s is its
    # hard timeout -- transport timings, not simulation parameters.
    "src/crewsim/api/streaming.py": {0.5, 3600},
    # The number of hex characters of a blake2b content_hash shown for display.
    # Same category as crn.py's own {16} digest_size entry: a hash/format
    # convention, not a business input. The full digest stays in the payload.
    "src/crewsim/reporting/provenance.py": {8},
    # Milliseconds-per-second, for displaying a measured wall-clock duration.
    # 0.4 (progress()'s default min_interval_s) is an SSE-flush throttle, same
    # category as processing.py's own {0.5, 3600} transport timings above.
    "src/crewsim/api/runlog.py": {1000, 0.4},
    # 0.975 is the two-sided 95% quantile of the t distribution -- the same
    # closed-form statistical constant already allowlisted for
    # data/eligibility_target.py, and for the same reason: a property of the
    # distribution, not a tunable business or reporting input. (It moved here
    # from cli.py when `compare`'s inline t-test was extracted so the CLI and
    # the web API share one implementation.) 2 is the minimum number of paired
    # scenarios needed for a variance to exist at all.
    "src/crewsim/reporting/paired.py": {0.975, 2},
    # 8 = how many exemplar chains the drill-down carries, a display cap in the
    # same category as results.py's 20-row limit -- not a cascade threshold.
    # Every actual cascade quantity in this module is derived from the ledger;
    # there is deliberately no cascade probability or rate constant here (§5.7:
    # cascades are emergent, never parameterised).
    "src/crewsim/reporting/cascade_analytics.py": {8},
    "src/crewsim/api/routers/results.py": {404, 20, 1024, 2},
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
    # S1b-07 (P0): 0.098 (the stubbed DES shortfall), 1.5/5.0 (its invented
    # service time and arrival rate) and 86400.0 (the seconds-per-day divisor
    # that made reserve-pattern report 3.7 days where the truth is 223.0) are
    # all gone -- gate v2 measures a real simulation now and reserve-pattern
    # divides by 1440. 0.05/40 went with the same block.
    "src/crewsim/cli.py": {
        2, 10, 240, 100, 20, 50,
        200.0, 150.0, 1000, 203,
        # 0.975 is GONE from here: `compare`'s inline paired t-test moved to
        # reporting/paired.py so the CLI and the web API compute one difference
        # rather than two. The quantile is allowlisted there now.
        960.0, 1560.0, 60.0, 600.0, 250.0, 28, 7, 24, 5,
        # S1c-05: 74 is the V3 warning banner's width in terminal characters --
        # presentation, same category as v5_trace.py's 78 and v2_erlang.py's 62.
        74,
        900.0, 1050.0, 1100.0, 800.0, 700.0, 1400.0, 2000.0, 502, 1440,
    },
    # S0-09b: cascade.py's mandatory-rest hours (11h base / 10h away) and the
    # 60.0 minutes-conversion duplicate legality.py's already-allowlisted L2
    # min-rest constants above (same reasoning as des.py's own {11, 10, 60}
    # entry: compute_draft_delta must derive the same figure independently).
    # S1a-02/S1a-07: cascade.py no longer re-derives L2 rest at all (it calls
    # min_rest_minutes), so its entire entry is gone. 60.0 below is the
    # deadline offset, still local to this module.
    # cascade.py: no allowlisted literals left (AUD-20 -- the hardcoded
    # 60-minute cascade deadline now comes from demand.uncovered_deadline_hours
    # via the shared sick_calls.uncovered_deadline_minutes helper).
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
    "src/crewsim/reporting/kpis.py": {2, 1440.0, 3},
    # ^ 1440.0 is minutes-per-day (Welch queue sampling at day boundaries,
    #   AUD-12), same time-conversion category as des.py/sick_calls.py;
    #   3 is round()'s display precision for the diagnostic's daily means
    #   -- presentation, same category as profile_html.py's styling.
    # compute_r_recommendation()'s own "a recommendation needs at least 2
    # options" floor -- a structural minimum, not a business input, same
    # category as paired.py's own `n < 2` CI-needs-2-scenarios entry above.
    "src/crewsim/reporting/recommendation.py": {2},
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
    # (20 removed: it was the hardcoded n_scenarios on the old free-of-charge
    # run_v7_gate call, replaced by gate_status.py's V7_SCENARIOS.)
    # WN-005: V1/V2/V7's own cost knob (the old 2 here) moved to
    # reporting/gate_status.py's own {2} entry below, which build_report()
    # now calls instead of running them inline -- see that module's
    # docstring. 3 remains: it is unrelated -- the R* line's plotly width
    # (line={"width": 3} in the lambda-curve figure), a styling literal, same
    # category as this file's own 450/0.6 chart-height/opacity entries.
    "src/crewsim/reporting/report.py": {450, 0.6, 0.02, 5, 3},
    # WN-005: V2_SCENARIOS/V7_SCENARIOS/V7_JOBS -- how much real simulation
    # V1/V2/V7's gate rows buy, now that V7 hashes real ledgers rather than
    # synthetic draws (S1a-11) and V2 measures a real Erlang-B shortfall
    # (S1b-07). A report-shape cost knob shared by reporting/report.py's HTML
    # table and api/routers/processing.py's native gates, not a business input.
    "src/crewsim/reporting/gate_status.py": {2},
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


# The src/crewsim/api/ carve-out (tests/workstreams.py::EXCLUDED_TREES, plus the
# matching `exclude` in pyproject.toml's [tool.ruff]) is GONE as of 2026-08-09.
# It was added on 2026-08-08 so slice-1a CI would not go red on another
# workstream's in-flight files, with test_api_exclusion_is_still_necessary
# standing by to delete the excuse once the tree was clean.
#
# It is worth recording what the carve-out cost while it lasted, because the
# case for the next one should have to clear this bar: behind it sat a health
# endpoint that returned HTTP 500 whenever any job was queued (a naive/aware
# datetime subtraction -- exactly what ruff's DTZ rule, enabled for this repo
# and excluded for that tree, exists to catch), six endpoints the front end
# called at the wrong path, and four routers of fabricated figures served over
# the same JSON shape as real results.
#
# Every file in src/ is guarded now; there is no is_excluded() any more.
def _guarded_files():
    for py in sorted(SRC.rglob("*.py")):
        yield py, py.relative_to(ROOT).as_posix()


def test_no_numeric_constant_outside_configs() -> None:
    offenders = []
    for py, rel in _guarded_files():
        allowed = ALLOWLIST.get(rel, set())
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
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
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        found = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)
        }
        stale = values - found
        assert not stale, f"{rel}: ALLOWLIST values no longer present in the file: {stale}"


# ================================ every declared config field must be consumed
# The runtime notice (config.unconsumed_notices) names ONE key by hand:
# demand.pairings_per_bid_period. Being hand-maintained, it missed two real
# cases -- `appr_compensation`, defined and costed but booked nowhere (found in
# slice 1b), and `mode`, which the engine ignored entirely while base.yaml
# documented a REDUCED mode that did not exist (S1c-01 AC4). This derives the
# answer from what the code actually reads instead.
#
# Method: collect every attribute name accessed anywhere in src/ (excluding
# config.py, which only DEFINES the fields), then require each config model
# field name to appear. Known limitation: a field whose name collides with an
# unrelated attribute elsewhere reads as consumed -- `mode` would now pass on
# EligibilityEngine.mode alone. So this catches a field nothing anywhere
# touches, which is the case that actually occurred twice, not every possible
# mis-wiring.
# Imported, not restated: config.DECLARED_NOT_YET_CONSUMED is the single source
# of truth that unconsumed_notices() also reads, so a key cannot be exempted
# here while staying invisible at runtime.
DECLARED_NOT_YET_CONSUMED = {k.split(".")[-1] for k in config.DECLARED_NOT_YET_CONSUMED}
# There used to be a hand-added `positioning` exemption here, because both
# fields in that section were unconsumed and so the section object was too.
# S1c-07 consumed them, and the exemption went with them -- an exemption that
# outlives its reason is a permanent hole in the guard, which is the whole
# failure mode this test exists to prevent.


def _attribute_names_used_in_src() -> set[str]:
    used: set[str] = set()
    for py, _rel in _guarded_files():
        # config.py is INCLUDED: field definitions are AnnAssign, not Attribute,
        # so they do not self-satisfy -- but genuine dynamic reads that live
        # there do count (e.g. APPRCompensation.on_cancellation resolves a band
        # via getattr(self, self.cancellation_band)).
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                used.add(node.attr)
            # cfg.model_copy(update={"population": ...}) and getattr(x, "name")
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                used.add(node.value)
    return used


def _config_field_names() -> set[str]:
    names: set[str] = set()
    for attr in dir(config):
        obj = getattr(config, attr)
        if isinstance(obj, type) and issubclass(obj, BaseModel):
            names |= set(obj.model_fields)
    return names


def test_every_config_field_is_read_by_some_code_path() -> None:
    """A declared, documented config key that nothing reads is a promise the
    software does not keep -- worse than an absent one, because it reads as a
    supported knob."""
    used = _attribute_names_used_in_src()
    orphans = sorted(
        name for name in _config_field_names()
        if name not in used and name not in DECLARED_NOT_YET_CONSUMED
    )
    assert not orphans, (
        "config field(s) declared but read nowhere in src/: " + ", ".join(orphans)
        + "\nEither consume them, remove them, or add them to "
          "DECLARED_NOT_YET_CONSUMED with a reason (and a runtime notice)."
    )


def test_the_consumption_guard_can_actually_fail() -> None:
    """Negative control: the scan must not report everything as used."""
    used = _attribute_names_used_in_src()
    assert "a_field_no_module_will_ever_reference" not in used
