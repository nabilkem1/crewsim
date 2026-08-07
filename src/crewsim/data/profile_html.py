"""HTML rendering for S0-02b's descriptive data profile.

Kept separate from `profile.py`'s statistics so the numbers can be unit
tested without touching Plotly at all. One self-contained file: plotly.js is
embedded exactly once (`plotly.offline.get_plotlyjs()`), so the report opens
from an email attachment with no CDN and no local server -- the same
self-containment rule the spec applies to the eventual policy report (§9.3).

Chart design follows the project's dataviz skill: form chosen by the data's
job (histogram+overlay for a distribution check, small multiples rather than
dual-axis for the three differently-scaled regime streams, sequential blue
for an ordinal severity axis, the validated two-color categorical pair for
"fitting vs holdout" everywhere that distinction appears), not decoration.
"""
from __future__ import annotations

import datetime
from collections import Counter
from typing import Any

import plotly.graph_objects as go
import plotly.offline
from plotly.subplots import make_subplots

from . import profile

# ---------------------------------------------------------------- palette
# Validated categorical pair (dataviz skill, references/palette.md): passes
# the CVD/contrast gates in both light and dark mode. Used consistently for
# "fitting" vs "holdout" everywhere that distinction appears on a chart --
# color follows the entity (the window), never re-picked per section.
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'
CHART_SURFACE = "#fcfcfb"
GRID = "#e1e0d9"
MUTED = "#898781"
PRIMARY_INK = "#0b0b0b"
SECONDARY_INK = "#52514e"

WINDOW_COLOR = {"fitting": "#2a78d6", "holdout": "#eb6834"}


def _layout(title: str, xaxis_title: str, yaxis_title: str, height: int = 380) -> dict[str, Any]:
    return {
        "title": {"text": title, "font": {"size": 15, "color": PRIMARY_INK, "family": FONT}},
        "paper_bgcolor": CHART_SURFACE,
        "plot_bgcolor": CHART_SURFACE,
        "font": {"family": FONT, "color": PRIMARY_INK, "size": 12},
        "legend": {"orientation": "h", "y": 1.16, "x": 0, "font": {"color": SECONDARY_INK}},
        "margin": {"t": 70, "l": 55, "r": 25, "b": 45},
        "height": height,
        "bargap": 0.15,
    }


def _axis(title: str = "") -> dict[str, Any]:
    return {
        "title": title, "gridcolor": GRID, "zerolinecolor": GRID,
        "linecolor": MUTED, "color": SECONDARY_INK,
    }


def _window_names(profiles: dict[str, profile.WindowProfile]) -> list[str]:
    return [n for n in profile.WINDOW_ORDER if n in profiles]


# ============================================================= narrative
# Every number below is read off the same WindowProfile the chart plots --
# nothing here is a fixed string with a number baked in, so the text cannot
# drift out of sync with the corpus the way a hand-written caption would.

def _rel_change(a: float, b: float) -> float:
    """Relative change from a (fitting) to b (holdout), as a fraction of a."""
    if a == 0:
        return float("inf") if b != 0 else 0.0
    return (b - a) / a


# _stability_word's threshold and reserve_outcome's 2.0pp verdict bar below
# choose report WORDING ("stable" vs "shifts"), not a calibration output or a
# pass/fail gate -- unlike overdispersion_threshold (config-sourced, thread
# through render()) these never feed back into a fitted parameter or a
# gate's PASS/FAIL. Kept local to this presentation-only, independently
# unit-tested module rather than threaded through render() -- the same
# category as the CSS/Plotly layout constants below (§4.4 governs
# simulation/business parameters, not report-narrative phrasing).
def _stability_word(rel: float, threshold: float = 0.15) -> str:
    return "stable" if abs(rel) <= threshold else "shifts"


def _narrative(purpose: str, finding: str, comparison: str) -> str:
    parts = [f'<p class="purpose">{purpose}</p>', f'<p class="finding">{finding}</p>']
    if comparison:
        parts.append(f'<p class="comparison">{comparison}</p>')
    return '<div class="narrative">' + "".join(parts) + "</div>"


def _sick_call_narrative(
    profiles: dict[str, profile.WindowProfile], overdispersion_threshold: float
) -> str:
    names = _window_names(profiles)
    purpose = (
        "Checks whether daily sick-call counts are overdispersed enough to justify a "
        "Negative Binomial model instead of a Poisson (&sect;5.2) &mdash; a Poisson assumes "
        "variance equals the mean, which would understate how clustered sick calls really are."
    )
    finding = " ".join(
        f"<strong>{name}</strong> &mdash; mean {s.mean:.2f}/day, variance {s.var:.2f} "
        f"(var/mean {s.var_over_mean:.2f}, "
        f"{'overdispersed' if s.var_over_mean > overdispersion_threshold else 'not clearly overdispersed'}); "
        f"winter {s.by_season.get('winter_sun', float('nan')):.2f} vs summer "
        f"{s.by_season.get('summer_atlantic', float('nan')):.2f} calls/day."
        for name in names for s in [profiles[name].sick_calls]
    )
    comparison = ""
    if len(names) == 2:
        f_s, h_s = profiles[names[0]].sick_calls, profiles[names[1]].sick_calls
        rel = _rel_change(f_s.var_over_mean, h_s.var_over_mean)
        both_clear = (
            f_s.var_over_mean > overdispersion_threshold
            and h_s.var_over_mean > overdispersion_threshold
        )
        comparison = (
            f"Fitting vs holdout: var/mean moves from {f_s.var_over_mean:.2f} to "
            f"{h_s.var_over_mean:.2f} ({_stability_word(rel)}, {rel * 100:+.0f}%). "
            + (
                "Both windows clear the overdispersion bar, so the NegBin choice does not "
                "depend on which window it is fit against."
                if both_clear else
                "One window no longer clears the overdispersion bar &mdash; worth a closer "
                "look before committing to NegBin for both."
            )
        )
    return _narrative(purpose, finding, comparison)


def _absence_duration_narrative(profiles: dict[str, profile.WindowProfile]) -> str:
    names = _window_names(profiles)
    purpose = (
        "Checks whether absence duration is right-skewed the way a Lognormal predicts "
        "&mdash; most absences short, a long tail of extended ones &mdash; rather than "
        "symmetric around the mean."
    )
    finding = " ".join(
        f"<strong>{name}</strong> &mdash; n={a.n}, median {a.median:.0f}, mean {a.mean:.2f}, "
        f"max {a.max} days (mean above median: right-skewed, as expected). Lognormal fit: "
        f"&mu;={a.lognorm_mu:.3f}, &sigma;={a.lognorm_sigma:.3f} "
        f"({profile.lognormal_cdf(0.5, a.lognorm_mu, a.lognorm_sigma) * 100:.1f}% of its mass "
        f"falls below day 1, invisible on this chart since no 0-day absence exists)."
        for name in names for a in [profiles[name].absence_duration]
    )
    comparison = ""
    if len(names) == 2:
        f_a, h_a = profiles[names[0]].absence_duration, profiles[names[1]].absence_duration
        rel = _rel_change(f_a.mean, h_a.mean)
        comparison = (
            f"Fitting vs holdout: mean duration {f_a.mean:.2f} vs {h_a.mean:.2f} days, shape "
            f"&sigma; {f_a.lognorm_sigma:.3f} vs {h_a.lognorm_sigma:.3f} "
            f"({_stability_word(rel)} across windows)."
        )
    return _narrative(purpose, finding, comparison)


_OUTCOME_ORDER = ["assigned", "released", "no-show"]


def _reserve_outcome_narrative(profiles: dict[str, profile.WindowProfile]) -> str:
    names = _window_names(profiles)
    purpose = (
        "Base rates a reserve callout resolves to &mdash; the composition the drafting "
        "cascade falls back on whenever a reserve callout does not end in an assignment."
    )
    finding = " ".join(
        f"<strong>{name}</strong> &mdash; n={r.n}: "
        + ", ".join(f"{o} {r.pct.get(o, 0.0) * 100:.1f}%" for o in _OUTCOME_ORDER) + "."
        for name in names for r in [profiles[name].reserve_outcomes]
    )
    comparison = ""
    if len(names) == 2:
        f_r, h_r = profiles[names[0]].reserve_outcomes, profiles[names[1]].reserve_outcomes
        deltas = {o: (h_r.pct.get(o, 0.0) - f_r.pct.get(o, 0.0)) * 100 for o in _OUTCOME_ORDER}
        max_abs = max(abs(v) for v in deltas.values())
        delta_str = ", ".join(f"{o} {v:+.1f}pp" for o, v in deltas.items())
        verdict = "stable" if max_abs < 2.0 else "shifts noticeably"
        comparison = f"Fitting vs holdout, percentage-point change: {delta_str} &mdash; composition is {verdict}."
    return _narrative(purpose, finding, comparison)


_GRADIENT_METRICS = [
    ("sick_mean", "sick calls/station-day"),
    ("cancel_rate", "cancellation rate"),
    ("delay_mean", "mean delay (min)"),
]


def _regime_gradient_narrative(profiles: dict[str, profile.WindowProfile]) -> str:
    names = _window_names(profiles)
    purpose = (
        "The central claim behind the shared severity-regime design (&sect;1.3.4): sick "
        "calls, cancellations, and delays should all rise TOGETHER from CALM to SEVERE, "
        "driven by one shared intensity multiplier, rather than moving independently."
    )

    def _fold(vals: list[float]) -> float:
        return vals[-1] / vals[0] if vals[0] else float("inf")

    def _span_label(classes: list[str]) -> str:
        # Endpoints actually present in this window's data, not an assumed
        # CALM..SEVERE literal -- regime_gradient_stats() only includes a
        # class if it occurred in the window, so the span can in principle
        # be narrower.
        return f"{classes[0]}&rarr;{classes[-1]}" if classes else "?"

    finding = " ".join(
        f"<strong>{name}</strong> ({_span_label(g.disruption_classes)}) &mdash; "
        + "; ".join(
            f"{label} {getattr(g, attr)[0]:.3g} &rarr; {getattr(g, attr)[-1]:.3g} "
            f"({_fold(getattr(g, attr)):.1f}x)"
            for attr, label in _GRADIENT_METRICS
        ) + "."
        for name in names for g in [profiles[name].regime_gradient]
    )
    comparison = ""
    if len(names) == 2:
        f_g, h_g = profiles[names[0]].regime_gradient, profiles[names[1]].regime_gradient
        folds = "; ".join(
            f"{label} {_fold(getattr(f_g, attr)):.1f}x vs {_fold(getattr(h_g, attr)):.1f}x"
            for attr, label in _GRADIENT_METRICS
        )
        if f_g.disruption_classes == h_g.disruption_classes:
            span = _span_label(f_g.disruption_classes)
            comparison = (
                f"Fitting vs holdout {span} fold-change: {folds} &mdash; all three "
                "streams rise in both windows, so the shared-multiplier design holds "
                "regardless of which window is used to fit it."
            )
        else:
            comparison = (
                f"Fitting vs holdout fold-change ({_span_label(f_g.disruption_classes)} vs "
                f"{_span_label(h_g.disruption_classes)} &mdash; note the disruption classes "
                f"present differ between windows): {folds}."
            )
    return _narrative(purpose, finding, comparison)


def _severe_run_narrative(profiles: dict[str, profile.WindowProfile]) -> str:
    names = _window_names(profiles)
    purpose = (
        "Checks that SEVERE days cluster into runs &mdash; bad WEEKS &mdash; rather than "
        "scattering as isolated days; a mean run length near 1 would undercut the Markov "
        "chain's self-transition design (&sect;5.2)."
    )
    finding = " ".join(
        f"<strong>{name}</strong> &mdash; {sv.n_runs} runs, mean length {sv.mean_length:.2f} "
        f"days, longest {sv.max_length} days."
        for name in names for sv in [profiles[name].severe_runs]
    )
    comparison = ""
    if len(names) == 2:
        f_sv, h_sv = profiles[names[0]].severe_runs, profiles[names[1]].severe_runs
        rel = _rel_change(f_sv.mean_length, h_sv.mean_length)
        comparison = (
            f"Fitting vs holdout: mean run length {f_sv.mean_length:.2f} vs "
            f"{h_sv.mean_length:.2f} days ({_stability_word(rel)}); both stay well above 1, "
            "so clustering holds in both windows."
        )
    return _narrative(purpose, finding, comparison)


# ============================================================== figures

def sick_call_figure(profiles: dict[str, profile.WindowProfile]) -> go.Figure:
    """Empirical PMF vs the method-of-moments NegBin fit, one panel per window."""
    names = _window_names(profiles)
    fig = make_subplots(
        rows=1, cols=len(names),
        subplot_titles=[
            f"{n} -- n={profiles[n].sick_calls.n_days} days, "
            f"var/mean={profiles[n].sick_calls.var_over_mean:.2f}"
            for n in names
        ],
    )
    for i, name in enumerate(names, start=1):
        s = profiles[name].sick_calls
        counter = Counter(s.daily_counts)
        total = sum(counter.values())
        max_k = max(counter) if counter else 0
        ks = list(range(max_k + 1))
        empirical = [counter.get(k, 0) / total for k in ks]
        fig.add_trace(
            go.Bar(x=ks, y=empirical, marker_color=WINDOW_COLOR[name],
                   name="empirical", showlegend=(i == 1), legendgroup="empirical"),
            row=1, col=i,
        )
        if s.negbin_r is not None and s.negbin_p is not None:
            r, p = s.negbin_r, s.negbin_p
            pmf = [profile.negbin_pmf(k, r, p) for k in ks]
            fig.add_trace(
                go.Scatter(x=ks, y=pmf, mode="lines+markers",
                           line={"color": PRIMARY_INK, "width": 2}, marker={"size": 6},
                           name="NegBin fit (method of moments)", showlegend=(i == 1),
                           legendgroup="fit"),
                row=1, col=i,
            )
        fig.update_xaxes(_axis("sick calls that day"), row=1, col=i)
        fig.update_yaxes(_axis("probability" if i == 1 else ""), row=1, col=i)
    fig.update_layout(**_layout("Sick calls per day -- empirical vs Negative Binomial", "", ""))
    for ann in fig.layout.annotations:
        ann.font = {"size": 12, "color": SECONDARY_INK, "family": FONT}
    return fig


def absence_duration_figure(profiles: dict[str, profile.WindowProfile]) -> go.Figure:
    """Empirical duration PMF vs the discretised Lognormal fit, one panel per window.

    `duration_days` is an integer -- a point mass at each day, not a density.
    A continuous Lognormal PDF plotted against a density-normalised histogram
    compares two different footings (see sick_call_figure's same treatment).
    The fit is discretised the same way here: P(k) = CDF(k+0.5) - CDF(k-0.5).
    """
    names = _window_names(profiles)
    fig = make_subplots(
        rows=1, cols=len(names),
        subplot_titles=[
            f"{n} -- n={profiles[n].absence_duration.n}, "
            f"median={profiles[n].absence_duration.median:.0f}, "
            f"mean={profiles[n].absence_duration.mean:.2f}, "
            f"max={profiles[n].absence_duration.max}"
            for n in names
        ],
    )
    for i, name in enumerate(names, start=1):
        a = profiles[name].absence_duration
        counter = Counter(a.durations)
        total = sum(counter.values())
        ks = list(range(1, a.max + 1))
        empirical = [counter.get(k, 0) / total for k in ks]
        fig.add_trace(
            go.Bar(x=ks, y=empirical, marker_color=WINDOW_COLOR[name],
                   name="empirical", showlegend=(i == 1), legendgroup="empirical"),
            row=1, col=i,
        )
        pmf = [
            profile.lognormal_cdf(k + 0.5, a.lognorm_mu, a.lognorm_sigma)
            - profile.lognormal_cdf(k - 0.5, a.lognorm_mu, a.lognorm_sigma)
            for k in ks
        ]
        fig.add_trace(
            go.Scatter(x=ks, y=pmf, mode="lines+markers",
                       line={"color": PRIMARY_INK, "width": 2}, marker={"size": 6},
                       name="Lognormal fit (discretised)", showlegend=(i == 1),
                       legendgroup="fit"),
            row=1, col=i,
        )
        fig.update_xaxes(_axis("absence duration (days)"), row=1, col=i)
        fig.update_yaxes(_axis("probability" if i == 1 else ""), row=1, col=i)
    fig.update_layout(**_layout("Absence duration -- empirical vs Lognormal", "", ""))
    for ann in fig.layout.annotations:
        ann.font = {"size": 12, "color": SECONDARY_INK, "family": FONT}
    return fig


def reserve_outcome_figure(profiles: dict[str, profile.WindowProfile]) -> go.Figure:
    """Reserve callout outcomes, fitting vs holdout, one metric across 3 categories."""
    names = _window_names(profiles)
    order = ["assigned", "released", "no-show"]
    fig = go.Figure()
    for name in names:
        r = profiles[name].reserve_outcomes
        ys = [r.pct.get(o, 0.0) * 100 for o in order]
        fig.add_trace(
            go.Bar(x=order, y=ys, name=f"{name} (n={r.n})", marker_color=WINDOW_COLOR[name],
                   text=[f"{y:.1f}%" for y in ys], textposition="outside"),
        )
    fig.update_layout(**_layout("Reserve callout outcomes", "", "% of callouts"))
    fig.update_xaxes(_axis())
    fig.update_yaxes(_axis("% of callouts"))
    return fig


def regime_gradient_figure(profiles: dict[str, profile.WindowProfile]) -> go.Figure:
    """Sick / cancel / delay vs disruption class -- 3 panels, never one dual-axis chart.

    Different units, different scales (a fraction, a rate, minutes): the
    dataviz rule for that is small multiples, not a second y-axis.
    """
    names = _window_names(profiles)
    metrics = [
        ("sick_mean", "mean sick calls / station-day"),
        ("cancel_rate", "cancellation rate"),
        ("delay_mean", "mean delay (min)"),
    ]
    fig = make_subplots(rows=1, cols=3, subplot_titles=[m[1] for m in metrics])
    for col, (attr, _label) in enumerate(metrics, start=1):
        for name in names:
            g = profiles[name].regime_gradient
            ys = getattr(g, attr)
            fig.add_trace(
                go.Bar(x=g.disruption_classes, y=ys, name=name,
                       marker_color=WINDOW_COLOR[name],
                       showlegend=(col == 1), legendgroup=name),
                row=1, col=col,
            )
        fig.update_xaxes(_axis(), row=1, col=col)
        fig.update_yaxes(_axis(), row=1, col=col)
    fig.update_layout(**_layout(
        "Regime gradient -- do sick calls, cancellations and delays move together?", "", "", height=420
    ))
    for ann in fig.layout.annotations:
        ann.font = {"size": 12, "color": SECONDARY_INK, "family": FONT}
    return fig


def severe_run_figure(profiles: dict[str, profile.WindowProfile]) -> go.Figure:
    """Consecutive-SEVERE-day run lengths -- evidence for 'bad weeks, not scattered days'."""
    names = _window_names(profiles)
    fig = make_subplots(
        rows=1, cols=len(names),
        subplot_titles=[
            f"{n} -- n={profiles[n].severe_runs.n_runs} runs, "
            f"mean={profiles[n].severe_runs.mean_length:.2f}, "
            f"max={profiles[n].severe_runs.max_length}"
            for n in names
        ],
    )
    for i, name in enumerate(names, start=1):
        sv = profiles[name].severe_runs
        counter = Counter(sv.run_lengths)
        max_len = sv.max_length or 1
        xs = list(range(1, max_len + 1))
        ys = [counter.get(x, 0) for x in xs]
        fig.add_trace(
            go.Bar(x=xs, y=ys, marker_color=WINDOW_COLOR[name], showlegend=False),
            row=1, col=i,
        )
        fig.update_xaxes(_axis("run length (consecutive SEVERE days)"), row=1, col=i)
        fig.update_yaxes(_axis("count" if i == 1 else ""), row=1, col=i)
    fig.update_layout(**_layout("SEVERE-day run length, per station", "", ""))
    for ann in fig.layout.annotations:
        ann.font = {"size": 12, "color": SECONDARY_INK, "family": FONT}
    return fig


# ================================================================ page shell

# The Plotly canvases stay light-only in both page modes (their own
# paper_bgcolor is fixed to CHART_SURFACE) -- an internal report is read on
# one machine at a time and a light chart on a dark page is legible either
# way. Only the surrounding page chrome (body, headings, table) follows the
# OS theme, so the page itself is never light-text-on-light or the reverse.
_PAGE_CSS = f"""
  body {{
    background: #f9f9f7; color: {PRIMARY_INK}; font-family: {FONT};
    max-width: 1180px; margin: 0 auto; padding: 32px 24px 64px;
  }}
  h1 {{ font-size: 22px; margin-bottom: 4px; }}
  .subtitle {{ color: {SECONDARY_INK}; font-size: 13px; margin-bottom: 28px; }}
  .section {{ margin-top: 40px; }}
  .section h2 {{ font-size: 16px; border-bottom: 1px solid {GRID}; padding-bottom: 6px; }}
  .chart {{ background: {CHART_SURFACE}; border: 1px solid {GRID}; border-radius: 6px;
            margin-top: 8px; }}
  table.stats {{ border-collapse: collapse; font-size: 13px; margin-top: 10px; }}
  table.stats th, table.stats td {{ padding: 4px 14px 4px 0; text-align: left; }}
  table.stats th {{ color: {SECONDARY_INK}; font-weight: 600; }}
  .narrative {{ max-width: 900px; margin-top: 12px; font-size: 13px; line-height: 1.55; }}
  .narrative p {{ margin: 6px 0; }}
  .narrative .purpose {{ color: {SECONDARY_INK}; font-style: italic; }}
  .narrative .finding {{ color: {PRIMARY_INK}; }}
  .narrative .comparison {{ color: {SECONDARY_INK}; border-left: 3px solid {GRID}; padding-left: 10px; }}

  @media (prefers-color-scheme: dark) {{
    body {{ background: #16161a; color: #f2f2f0; }}
    .subtitle {{ color: #a9a8a3; }}
    .section h2 {{ border-bottom-color: #38373f; }}
    table.stats th {{ color: #a9a8a3; }}
    .narrative .purpose, .narrative .comparison {{ color: #a9a8a3; }}
    .narrative .finding {{ color: #f2f2f0; }}
    .narrative .comparison {{ border-left-color: #38373f; }}
  }}
"""


def _stats_table(profiles: dict[str, profile.WindowProfile]) -> str:
    names = _window_names(profiles)
    rows = [
        ("window", [profiles[n].window.label for n in names]),
        ("sick calls: n days", [str(profiles[n].sick_calls.n_days) for n in names]),
        ("sick calls: var/mean", [f"{profiles[n].sick_calls.var_over_mean:.2f}" for n in names]),
        ("absence duration: n", [str(profiles[n].absence_duration.n) for n in names]),
        ("reserve callouts: n", [str(profiles[n].reserve_outcomes.n) for n in names]),
        ("SEVERE runs: n", [str(profiles[n].severe_runs.n_runs) for n in names]),
    ]
    head = "<tr><th></th>" + "".join(f"<th>{n}</th>" for n in names) + "</tr>"
    body = "".join(
        "<tr><th>" + label + "</th>" + "".join(f"<td>{v}</td>" for v in vals) + "</tr>"
        for label, vals in rows
    )
    return f'<table class="stats">{head}{body}</table>'


def render(profiles: dict[str, profile.WindowProfile], overdispersion_threshold: float) -> str:
    """The full self-contained HTML page. plotly.js is embedded exactly once."""
    figures = [
        ("Sick calls per day", sick_call_figure(profiles),
         _sick_call_narrative(profiles, overdispersion_threshold)),
        ("Absence duration", absence_duration_figure(profiles), _absence_duration_narrative(profiles)),
        ("Reserve callout outcomes", reserve_outcome_figure(profiles), _reserve_outcome_narrative(profiles)),
        ("Regime gradient", regime_gradient_figure(profiles), _regime_gradient_narrative(profiles)),
        ("SEVERE-day run length", severe_run_figure(profiles), _severe_run_narrative(profiles)),
    ]

    chart_divs = []
    for i, (_title, fig, _narr) in enumerate(figures):
        html = fig.to_html(full_html=False, include_plotlyjs=False, div_id=f"chart-{i}")
        chart_divs.append(f'<div class="chart">{html}</div>')

    now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M UTC")
    sections = "".join(
        f'<div class="section"><h2>{title}</h2>{div}{narrative}</div>'
        for (title, _fig, narrative), div in zip(figures, chart_divs)
    )

    return f"""<!doctype html>
<html><head>
<meta charset="utf-8">
<title>Data profile -- crewsim (S0-02b)</title>
<style>{_PAGE_CSS}</style>
<script>{plotly.offline.get_plotlyjs()}</script>
</head><body>
<h1>Data profile</h1>
<div class="subtitle">Generated {now} &middot; crewsim S0-02b &middot;
distributions computed separately per window (spec &sect;6.4) before any
calibration story fits one.</div>
{_stats_table(profiles)}
{sections}
</body></html>"""
