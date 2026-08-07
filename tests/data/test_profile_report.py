"""S0-02b -- descriptive data profile.

Acceptance (backlog/mvp/00_phase0_data_foundation.md):
  * generates one self-contained HTML file at paths.reports_dir
  * every figure states its n and its window
  * run separately for the fitting and holdout windows
  * every distribution the spec assumes a family for gets an explicit
    overlay of that family against the empirical data

fails_if: the variance-to-mean ratio is about 1.0 (falsifies the NegBin
choice), or the three regime streams do not move together across severity
classes (falsifies Sec 1.3.4's core assertion).
"""
from __future__ import annotations

import datetime
import math
import pathlib

import pytest

from crewsim import config
from crewsim.data import loaders, profile, profile_html


def _synthetic_profile(name: str, disruption_classes: list[str]) -> profile.WindowProfile:
    """A minimal, internally-consistent WindowProfile for testing profile_html
    in isolation from the real corpus -- only the shape matters here, not
    numerically-realistic values.
    """
    n = len(disruption_classes)
    return profile.WindowProfile(
        window=profile.Window(name, datetime.date(2024, 1, 1), datetime.date(2024, 1, 2)),
        sick_calls=profile.SickCallStats(
            n_days=2, mean=7.0, var=22.0, var_over_mean=22.0 / 7.0,
            by_season={"winter_sun": 9.0, "summer_atlantic": 5.0},
            negbin_r=1.0, negbin_p=0.5, daily_counts=[7, 7],
        ),
        absence_duration=profile.AbsenceDurationStats(
            n=10, median=1.0, mean=2.0, max=5, lognorm_mu=0.5, lognorm_sigma=0.6,
            durations=[1.0] * 10,
        ),
        reserve_outcomes=profile.ReserveOutcomeStats(
            n=100, pct={"assigned": 0.9, "released": 0.07, "no-show": 0.03},
        ),
        regime_gradient=profile.RegimeGradientStats(
            disruption_classes=disruption_classes,
            sick_mean=[0.1 * (i + 1) for i in range(n)],
            cancel_rate=[0.01 * (i + 1) for i in range(n)],
            delay_mean=[5.0 * (i + 1) for i in range(n)],
            n_station_days=[10] * n,
        ),
        severe_runs=profile.SevereRunStats(
            n_runs=5, mean_length=1.8, max_length=4, run_lengths=[1, 2, 3, 2, 1],
        ),
    )


@pytest.fixture(scope="module")
def real_cfg() -> config.BaseConfig:
    return config.load()


# --------------------------------------------------------------------- windows
def test_windows_load_from_config_not_a_default(real_cfg: config.BaseConfig) -> None:
    windows = profile.load_windows(real_cfg)
    names = [w.name for w in windows]
    assert names == ["fitting", "holdout"]
    assert windows[0].end < windows[1].start  # no overlap
    assert windows[1].end.year - windows[0].start.year <= 3


def test_missing_windows_config_raises_not_silently_defaults(real_cfg: config.BaseConfig) -> None:
    cfg = real_cfg.model_copy(update={"windows": None})  # no `windows` -- not a shared reference
    with pytest.raises(KeyError, match="windows"):
        profile.load_windows(cfg)


def test_seasons_load_from_the_single_source_of_truth(real_cfg: config.BaseConfig) -> None:
    seasons = loaders.load_seasons(real_cfg)
    assert seasons["winter_sun"] == [12, 1, 2, 3, 4]
    assert seasons["summer_atlantic"] == [6, 7, 8, 9]


# ------------------------------------------------------------- math helpers
def test_negbin_fit_matches_the_spec_formula() -> None:
    # sigma^2 = mu + alpha*mu^2  =>  alpha = (var-mean)/mean^2, r = 1/alpha
    mean, var = 7.0, 22.0
    r, p = profile.negbin_fit(mean, var)
    # reconstructed mean/var from (r, p) must round-trip
    recon_mean = r * (1 - p) / p
    recon_var = r * (1 - p) / p**2
    assert recon_mean == pytest.approx(mean, rel=1e-9)
    assert recon_var == pytest.approx(var, rel=1e-9)


def test_negbin_fit_refuses_when_not_overdispersed() -> None:
    with pytest.raises(ValueError, match="variance must exceed"):
        profile.negbin_fit(mean=5.0, var=4.0)


def test_negbin_pmf_sums_to_one() -> None:
    r, p = profile.negbin_fit(mean=7.0, var=22.0)
    total = sum(profile.negbin_pmf(k, r, p) for k in range(200))
    assert total == pytest.approx(1.0, abs=1e-6)


def test_lognormal_fit_recovers_known_parameters() -> None:
    mu, sigma = 0.5, 0.6
    # deterministic log-spaced sample with the target mean/std in log-space
    import random

    rng = random.Random(0)
    values = [math.exp(rng.normalvariate(mu, sigma)) for _ in range(20_000)]
    fit_mu, fit_sigma = profile.lognormal_fit(values)
    assert fit_mu == pytest.approx(mu, abs=0.02)
    assert fit_sigma == pytest.approx(sigma, abs=0.02)


def test_lognormal_pdf_integrates_to_one() -> None:
    mu, sigma = 0.456, 0.617
    step = 0.01
    xs = [step * i for i in range(1, 10_000)]
    total = sum(profile.lognormal_pdf(x, mu, sigma) for x in xs) * step
    assert total == pytest.approx(1.0, abs=0.01)


def test_discretised_lognormal_pmf_sums_to_one() -> None:
    """The absence-duration chart overlays this, not the raw PDF (duration_days is integer).

    Summed over its full domain (k=0 upward -- bin 0 is (0, 0.5], since the
    Lognormal has no support at or below 0). The chart itself only plots
    k>=1 (no 0-day absence exists in the data), so a few percent of the
    fitted mass sitting in bin 0 is expected and is not what this test
    checks -- this test checks that the discretisation scheme itself
    conserves probability, independent of which k-range a chart plots.
    """
    mu, sigma = 0.456, 0.617
    ks = range(60)
    total = sum(
        profile.lognormal_cdf(k + 0.5, mu, sigma) - profile.lognormal_cdf(max(k - 0.5, 0), mu, sigma)
        for k in ks
    )
    assert total == pytest.approx(1.0, abs=1e-6)


# -------------------------------------------------------- statistics, real corpus
@pytest.fixture(scope="module")
def profiles(real_cfg: config.BaseConfig) -> dict[str, profile.WindowProfile]:
    return profile.compute_profiles(real_cfg)


def test_both_windows_present(profiles: dict[str, profile.WindowProfile]) -> None:
    assert set(profiles) == {"fitting", "holdout"}


def test_sick_calls_are_overdispersed_in_every_window(
    real_cfg: config.BaseConfig, profiles: dict[str, profile.WindowProfile]
) -> None:
    """fails_if: var/mean is about 1.0 -- the NegBin choice is then unjustified."""
    threshold = real_cfg.calibration.overdispersion_threshold
    for name, p in profiles.items():
        assert p.sick_calls.var_over_mean > threshold, (
            f"{name}: var/mean={p.sick_calls.var_over_mean:.2f} is not clearly "
            f"overdispersed -- NegBin is unjustified"
        )
        assert p.sick_calls.negbin_r is not None


def test_winter_exceeds_summer_in_every_window(profiles: dict[str, profile.WindowProfile]) -> None:
    for name, p in profiles.items():
        winter = p.sick_calls.by_season["winter_sun"]
        summer = p.sick_calls.by_season["summer_atlantic"]
        assert winter > summer, f"{name}: winter ({winter:.2f}) should exceed summer ({summer:.2f})"


def test_absence_duration_is_right_skewed(profiles: dict[str, profile.WindowProfile]) -> None:
    for name, p in profiles.items():
        a = p.absence_duration
        assert a.median <= a.mean < a.max, f"{name}: not right-skewed as expected"
        assert a.n > 0


def test_reserve_outcomes_sum_to_one(profiles: dict[str, profile.WindowProfile]) -> None:
    for name, p in profiles.items():
        total = sum(p.reserve_outcomes.pct.values())
        assert total == pytest.approx(1.0, abs=1e-9), f"{name}: outcome percentages don't sum to 1"
        assert p.reserve_outcomes.pct["assigned"] > 0.5, f"{name}: assigned should dominate"


def test_regime_streams_move_together(profiles: dict[str, profile.WindowProfile]) -> None:
    """fails_if: the three streams do not move together across regimes --
    this would falsify Sec 1.3.4's whole justification for the shared
    severity-regime design.
    """
    for name, p in profiles.items():
        g = p.regime_gradient
        assert g.disruption_classes == ["CALM", "NORMAL", "DISRUPTED", "SEVERE"], name
        for attr in ("sick_mean", "cancel_rate", "delay_mean"):
            values = getattr(g, attr)
            assert values == sorted(values), (
                f"{name}.{attr} does not rise monotonically CALM->SEVERE: {values}"
            )
            assert values[-1] > values[0] * 2, (
                f"{name}.{attr} barely moves across regimes: {values}"
            )


def test_severe_runs_show_clustering_not_scattered_days(
    profiles: dict[str, profile.WindowProfile]
) -> None:
    """A mean run length near 1 would mean SEVERE days are isolated, not clustered."""
    for name, p in profiles.items():
        assert p.severe_runs.mean_length > 1.3, (
            f"{name}: mean SEVERE run length {p.severe_runs.mean_length:.2f} suggests "
            f"scattered days, not clustered bad weeks"
        )
        assert p.severe_runs.max_length >= 3


def test_windows_do_not_leak_into_each_other(
    real_cfg: config.BaseConfig, profiles: dict[str, profile.WindowProfile]
) -> None:
    """A holdout-window stat must not be reachable by mutating the fitting profile."""
    windows = {w.name: w for w in profile.load_windows(real_cfg)}
    fitting_n = profiles["fitting"].sick_calls.n_days
    holdout_n = profiles["holdout"].sick_calls.n_days
    assert fitting_n != holdout_n  # different window lengths (24mo vs 12mo)
    assert fitting_n == (windows["fitting"].end - windows["fitting"].start).days + 1
    assert holdout_n == (windows["holdout"].end - windows["holdout"].start).days + 1


# --------------------------------------------------------------------------- HTML
def test_report_is_one_self_contained_file(
    real_cfg: config.BaseConfig, tmp_path: pathlib.Path
) -> None:
    cfg = real_cfg.model_copy(update={"paths": real_cfg.paths.model_copy(update={"reports_dir": tmp_path})})
    path = profile.write_report(cfg)
    assert path == tmp_path / "data_profile.html"
    html = path.read_text()

    assert "<script src=" not in html, "an external script tag means it is not self-contained"
    assert "<link " not in html, "an external stylesheet link means it is not self-contained"
    assert "Plotly.newPlot" in html, "plotly.js must be embedded, not merely referenced"


def test_every_chart_states_n_and_window(
    real_cfg: config.BaseConfig, tmp_path: pathlib.Path
) -> None:
    cfg = real_cfg.model_copy(update={"paths": real_cfg.paths.model_copy(update={"reports_dir": tmp_path})})
    html = profile.write_report(cfg).read_text()
    for name, p in profile.compute_profiles(real_cfg).items():
        assert name in html
        assert f"n={p.sick_calls.n_days}" in html or str(p.sick_calls.n_days) in html
        assert p.window.start.isoformat() in html
        assert p.window.end.isoformat() in html


def test_every_section_has_a_purpose_finding_and_comparison(
    profiles: dict[str, profile.WindowProfile]
) -> None:
    """S0-02b enhancement: each chart explains its own purpose, what the
    numbers show, and how the fitting and holdout windows compare -- computed
    from the same profile the chart plots, not a fixed caption.
    """
    html = profile_html.render(profiles, 1.5)
    assert html.count('class="purpose"') == 5
    assert html.count('class="finding"') == 5
    assert html.count('class="comparison"') == 5  # both windows present -> every section compares them
    assert "Fitting vs holdout" in html


def test_regime_gradient_narrative_labels_actual_endpoints_not_hardcoded() -> None:
    """A window whose data never reaches CALM must not be captioned CALM->SEVERE
    (code-review fix: the label was a hardcoded literal, not read from
    disruption_classes -- regime_gradient_stats() only includes a class if it
    actually occurred in the window, so the span is not guaranteed to be the
    full CALM..SEVERE list).
    """
    profiles = {
        "fitting": _synthetic_profile("fitting", ["NORMAL", "DISRUPTED", "SEVERE"]),
        "holdout": _synthetic_profile("holdout", ["NORMAL", "DISRUPTED", "SEVERE"]),
    }
    html = profile_html.render(profiles, 1.5)
    assert "NORMAL&rarr;SEVERE fold-change" in html
    assert "CALM&rarr;SEVERE" not in html


def test_regime_gradient_narrative_flags_mismatched_class_sets() -> None:
    """Fitting and holdout are not guaranteed to see the same disruption
    classes; the comparison text must say so rather than silently combining
    them under one label.
    """
    profiles = {
        "fitting": _synthetic_profile("fitting", ["CALM", "NORMAL", "DISRUPTED", "SEVERE"]),
        "holdout": _synthetic_profile("holdout", ["NORMAL", "DISRUPTED", "SEVERE"]),
    }
    html = profile_html.render(profiles, 1.5)
    assert "disruption classes present differ between windows" in html


def test_render_is_a_pure_function_of_the_profiles(
    profiles: dict[str, profile.WindowProfile]
) -> None:
    """Same profiles in -> byte-identical HTML out (no hidden timestamp-free state)."""
    html_a = profile_html.render(profiles, 1.5)
    html_b = profile_html.render(profiles, 1.5)

    def _strip_timestamp(html: str) -> str:
        # the one deliberately time-varying line: the "Generated ..." timestamp
        return "\n".join(line for line in html.splitlines() if "Generated" not in line)

    assert _strip_timestamp(html_a) == _strip_timestamp(html_b)
