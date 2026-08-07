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
    # exit code 2 (usage error, argparse convention) and CLI display
    # defaults/widths (`--rows` default, terminal table width) -- UX, not a
    # simulation/business parameter.
    "src/crewsim/cli.py": {2, 10, 240},
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
    "src/crewsim/data/profile_html.py": {
        380, 0.15, 12, 1.16, 70, 55, 25, 45, 3, 15, 100, 2.0, 420, 0.5, 6,
    },
}


def test_no_numeric_constant_outside_configs() -> None:
    offenders = []
    for py in sorted(SRC.rglob("*.py")):
        rel = py.relative_to(ROOT).as_posix()
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
