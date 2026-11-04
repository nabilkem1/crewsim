"""What a run could NOT do properly, stated where the reader will look (data load + calibration).

A real extract is never as clean as the corpus the code was built on. Some of its
defects are accommodated (an extra column is ignored, a null notification time is
assumed, a fleet name is widened) and some cannot be: one winter in a fitting
window, a week of D8 flagged cancelled, a regime state that never sees a
cancellation. None of that may disappear into a passing exit code. This module
turns each such finding into a `Limitation` -- an id, a severity and a sentence --
that `crewsim data readiness`, the data-profile HTML, the calibration store
(`diagnostics.limitations`) and the calibration API job all show.

Every check reads the data and the configuration; none assumes the mock or the
real corpus. A check that finds nothing reports nothing, so on the mock corpus
the list is (nearly) empty.
"""
from __future__ import annotations

import datetime
from dataclasses import asdict, dataclass
from typing import Any

import polars as pl

from .. import config
from . import clean, coverage, loaders

HIGH, MEDIUM, INFO = "HIGH", "MEDIUM", "INFO"
_SEVERITIES = (HIGH, MEDIUM, INFO)


@dataclass(frozen=True)
class Limitation:
    id: str
    severity: str  # HIGH | MEDIUM | INFO
    title: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _rank(severity: str) -> int:
    return _SEVERITIES.index(severity) if severity in _SEVERITIES else len(_SEVERITIES)


def sort_limitations(items: list[Limitation]) -> list[Limitation]:
    return sorted(items, key=lambda x: (_rank(x.severity), x.id))


def format_limitations(items: list[Limitation]) -> str:
    """Plain text, one block per limitation, most severe first."""
    if not items:
        return "  none found"
    lines = []
    for x in sort_limitations(items):
        lines.append(f"  [{x.severity}] {x.title}")
        lines.append(f"         {x.detail}")
    return "\n".join(lines)


def limitations_html(items: list[dict[str, str]] | list[Limitation]) -> str:
    """The section the data-profile page opens with (empty string when none)."""
    import html

    rows = [x.as_dict() if isinstance(x, Limitation) else x for x in items]
    if not rows:
        return ""
    rows.sort(key=lambda r: (_rank(r["severity"]), r["id"]))
    colour = {HIGH: "#b3261e", MEDIUM: "#b26a00", INFO: "#5f6368"}
    body = "".join(
        f"<tr><td style='color:{colour.get(r['severity'], '#000')};font-weight:600;white-space:nowrap'>"
        f"{html.escape(r['severity'])}</td><td><strong>{html.escape(r['title'])}</strong><br>"
        f"{html.escape(r['detail'])}</td></tr>"
        for r in rows
    )
    return (
        '<div class="section"><h2>Limitations of this data load</h2>'
        "<p>What the extract could not support, or what the code assumed to read it. "
        "These bound what any result built on it can claim.</p>"
        f'<table class="stats"><tr><th>Severity</th><th>Limitation</th></tr>{body}</table></div>'
    )


# ------------------------------------------------------------------ season episodes
def season_episodes(
    months: set[int], start: datetime.date, end: datetime.date
) -> list[tuple[datetime.date, datetime.date, int]]:
    """Runs of consecutive in-season days inside [start, end]: (first, last, n_days)."""
    runs: list[tuple[datetime.date, datetime.date, int]] = []
    first = prev = None
    n = 0
    day = start
    while day <= end:
        if day.month in months:
            if prev is not None and (day - prev).days == 1:
                n += 1
            else:
                if first is not None and prev is not None:
                    runs.append((first, prev, n))
                first, n = day, 1
            prev = day
        day += datetime.timedelta(days=1)
    if first is not None and prev is not None:
        runs.append((first, prev, n))
    return runs


def complete_season_episodes(
    months: set[int], start: datetime.date, end: datetime.date
) -> list[tuple[datetime.date, datetime.date, int]]:
    """Season runs that are whole: they begin on the first day of the season's first
    month and end on the last day of its last month, so neither the window nor the
    data cut them short."""
    one_day = datetime.timedelta(days=1)
    return [
        (first, last, n) for first, last, n in season_episodes(months, start, end)
        if first.day == 1 and (first - one_day).month not in months
        and (last + one_day).day == 1 and (last + one_day).month not in months
    ]


def _th(cfg: config.BaseConfig) -> config.LimitationsConfig:
    if cfg.limitations is None:
        raise ValueError("configuration has no `limitations:` section (configs/base.yaml)")
    return cfg.limitations


def _span(cfg: config.BaseConfig) -> tuple[datetime.date, datetime.date] | None:
    """Days every one of D2, D4 and D8 is recorded."""
    ivs = coverage.all_intervals(cfg)
    return coverage.intersect(*(ivs[d] for d in ("d2_rosters", "d4_absences", "d8_flight_movements")))


# ---------------------------------------------------------------------- the checks
def _fleet(cfg: config.BaseConfig) -> list[Limitation]:
    if cfg.scope.fleet_resolution:
        return [Limitation(
            "scope_fleet_substituted", MEDIUM, "Scope fleet widened from the configured one",
            cfg.scope.fleet_resolution + ". The simulated cell therefore includes every pilot "
            "the extract files under that fleet name, whatever their exact aircraft sub-type.",
        )]
    return []


def _seasons(cfg: config.BaseConfig, span: tuple[datetime.date, datetime.date] | None) -> list[Limitation]:
    th = _th(cfg)
    if cfg.windows is None or span is None:
        return []
    months = set(loaders.load_seasons(cfg).get(cfg.scope.season, []))
    if not months:
        return []
    out: list[Limitation] = []
    for name in ("fitting", "holdout"):
        w = cfg.windows.get(name)
        start, end = max(w.start, span[0]), min(w.end, span[1])
        if start > end:
            continue
        found = complete_season_episodes(months, start, end)
        if len(found) >= th.min_season_episodes:
            continue
        days = sum(n for _first, _last, n in season_episodes(months, start, end))
        shown = ", ".join(f"{a}..{b}" for a, b, _ in found) or "none"
        out.append(Limitation(
            f"season_episodes_{name}",
            HIGH if name == "fitting" else MEDIUM,
            f"{cfg.scope.season}: {len(found)} complete season in the {name} window "
            f"({days} in-season days)",
            f"The {name} window {start}..{end} (the part the data covers) holds {len(found)} complete "
            f"{cfg.scope.season} season(s): {shown}. One season cannot separate the seasonal "
            f"effect from what was particular to that year, so seasonal parameters are weakly "
            f"identified and the {'regime HMM sees only that many days' if name == 'fitting' else 'holdout check is a single-season test'}. "
            f"Two complete seasons per window are the minimum; the extract needs to start earlier.",
        ))
    return out


def _d12(cfg: config.BaseConfig) -> list[Limitation]:
    named = cfg.paths.agreement_rules_file
    if named is None:
        return []
    try:
        rules = loaders.load_agreement_rules(cfg)
        markers = config.find_confirm_markers(named)
    except FileNotFoundError:
        return [Limitation("d12_missing", MEDIUM, "No D12 agreement rules", f"{named} not found")]
    pilots = rules.get("pilots", {})
    drafting, reserve = pilots.get("drafting", {}), pilots.get("reserve", {})
    owners = sorted({m.owner for m in markers})
    return [Limitation(
        "d12_from_mock", MEDIUM, "D12 agreement rules come from the mock corpus",
        f"The real extract has no D12; {named.name} is used as supplied with the mock "
        f"(marked [CONFIRM: {'; '.join(owners)}]). Still to be informed: "
        f"drafting.premium_pct={drafting.get('premium_pct')}, "
        f"reserve.guarantee_per_day_cad={reserve.get('guarantee_per_day_cad')}, "
        f"reserve.notice_hours={reserve.get('notice_hours')}, term={pilots.get('term')}. "
        "The engine reads none of D12 (costs come from costs_pilots.yaml, notices from "
        "legality.*), so no result changes -- but none of these figures is an Air Transat fact yet.",
    )]


def _columns(cfg: config.BaseConfig) -> list[Limitation]:
    rep = loaders.column_report(cfg)
    ignored = {n: r["ignored"] for n, r in rep.items() if r["ignored"]}
    used = {n: r["used_optional"] for n, r in rep.items() if r["used_optional"]}
    if not ignored:
        return []
    text = "; ".join(f"{n}: {', '.join(c)}" for n, c in sorted(ignored.items()))
    used_text = "; ".join(f"{n}: {', '.join(c)}" for n, c in sorted(used.items()))
    return [Limitation(
        "columns_ignored", INFO, "Columns in the extract that the code does not read",
        f"Left unread: {text}." + (f" Read when present: {used_text}." if used_text else ""),
    )]


def _d4(cfg: config.BaseConfig) -> list[Limitation]:
    th = _th(cfg)
    d4 = clean.load_absences(cfg)
    out: list[Limitation] = []
    if cfg.windows is not None:
        w0, w1 = cfg.windows.fitting.start, cfg.windows.holdout.end
        d4 = d4.filter((pl.col("absence_start") >= w0) & (pl.col("absence_start") <= w1))
    if not d4.height:
        return out
    nulls = d4["notification_ts"].null_count()
    if nulls / d4.height > th.null_notification_share:
        rule = (
            "assumed reported at 00:00 on the first day of the absence"
            if cfg.data.null_notification_ts == "at_absence_start" else "left out of the replay and gate V3"
        )
        out.append(Limitation(
            "d4_null_notification", MEDIUM, f"{nulls / d4.height:.0%} of absences have no notification time",
            f"{nulls} of {d4.height} D4 rows have no notification_ts, so the notice given for them is "
            f"unknown. They are {rule} (data.null_notification_ts). The sick-call COUNT calibration "
            f"is unaffected; any notice-time analysis and the V3 eligibility target are.",
        ))
    long_n = d4.filter(pl.col("duration_days") > th.long_absence_days).height
    if long_n:
        out.append(Limitation(
            "d4_long_absences", MEDIUM, f"{long_n} 'sick' absences last more than {th.long_absence_days} days",
            f"Longest {int(d4['duration_days'].max())} days (median {d4['duration_days'].median():.0f}). "
            "Those are leaves recorded as absences; they stretch the fitted duration distribution "
            "and are counted as sick calls on their first day.",
        ))
    with_pairing = d4.filter(pl.col("affected_pairing_id").is_not_null())
    if with_pairing.height:
        roster = (
            loaders.load_dataset(cfg, "d2_rosters").select("crew_id", "pairing_id").drop_nulls().unique()
        )
        in_roster = with_pairing.join(
            roster, left_on=["crew_id", "affected_pairing_id"], right_on=["crew_id", "pairing_id"],
            how="inner",
        ).height
        if in_roster / with_pairing.height < th.min_roster_link_share:
            out.append(Limitation(
                "d4_pairing_not_in_roster", MEDIUM,
                f"Only {in_roster} of {with_pairing.height} sick calls name a pairing that is in the sick pilot's roster",
                "D2 no longer holds the pairing a pilot called in sick on (it was reassigned), so the "
                "historical eligible-reserve fraction (gate V3's target) cannot be rebuilt from D4 x D2: "
                f"it rests on {in_roster} event(s). The published roster BEFORE the absence is needed.",
            ))
    other = d4.filter(pl.col("absence_type") != "SICK")
    if other.height:
        kinds = ", ".join(f"{r['absence_type']} {r['len']}" for r in other.group_by("absence_type").len().to_dicts())
        out.append(Limitation(
            "d4_non_sick_types", INFO, "Absence types other than SICK are counted as sick calls",
            f"{other.height} of {d4.height} rows ({kinds}). The calibration has no absence-type filter yet.",
        ))
    return out


def _d8(cfg: config.BaseConfig) -> list[Limitation]:
    th = _th(cfg)
    out: list[Limitation] = []
    raw = loaders.load_dataset(cfg, "d8_flight_movements")
    report = clean.operated_flights_report(cfg, raw)[1]
    if report.get("self_loops"):
        out.append(Limitation(
            "d8_self_loops", MEDIUM, f"{report['self_loops']} D8 rows have origin equal to destination",
            "Not flights; dropped before any count (data.drop_self_loop_flights). A real flight is "
            "sometimes repeated as such a row, flagged cancelled.",
        ))
    if report.get("duplicates"):
        out.append(Limitation(
            "d8_duplicates", INFO, f"{report['duplicates']} repeated D8 flight rows removed",
            "Same flight number, day, origin and destination more than once; the first is kept.",
        ))
    daily = (
        raw.group_by("date").agg(pl.len().alias("n"), (pl.col("cancelled").fill_null(0) == 1).sum().alias("c"))
        .filter(pl.col("n") >= th.artefact_min_flights)
        .filter(pl.col("c") / pl.col("n") > th.artefact_cancel_share)
        .sort("date")
    )
    if daily.height:
        first, last = daily["date"].min(), daily["date"].max()
        inside = False
        if cfg.windows is not None:
            for name in ("fitting", "holdout"):
                w = cfg.windows.get(name)
                inside = inside or bool(daily.filter((pl.col("date") >= w.start) & (pl.col("date") <= w.end)).height)
        out.append(Limitation(
            "d8_cancel_artefact", HIGH if inside else MEDIUM,
            f"D8 {first}..{last}: {daily.height} day(s) with most flights flagged cancelled",
            f"More than {th.artefact_cancel_share:.0%} of the day's flights are cancelled on {daily.height} day(s) -- "
            "far above any real disruption, and the row count per day is several times the normal level: "
            "an extraction artefact (probably scheduled-only flights flagged cancelled). "
            + ("They fall INSIDE a configured window and will read as SEVERE days." if inside else
               "The configured windows start after them, so they are not used."),
        ))
    # Do cancellations at the crew bases carry any signal?
    if cfg.windows is not None:
        d1 = loaders.load_dataset(cfg, "d1_crew_master")
        bases = clean.active_pilot_bases(d1, cfg.scope.base)
        w = cfg.windows.fitting
        flights = clean.operated_flights(cfg, raw).filter(
            pl.col("origin").is_in(bases) & (pl.col("date") >= w.start) & (pl.col("date") <= w.end)
        )
        if flights.height:
            cancelled = flights.filter(pl.col("cancelled") == 1).height
            if cancelled < th.min_base_cancellations:
                out.append(Limitation(
                    "d8_few_base_cancellations", MEDIUM,
                    f"Only {cancelled} cancellation(s) departing the crew bases in the fitting window",
                    f"{cancelled} of {flights.height} departures from {', '.join(bases)} "
                    f"({cancelled / flights.height:.2%}). The regime model's cancellation stream "
                    "cannot separate regimes on that, so regimes rest on delays and sick calls. "
                    "Cancellations are mostly at outstations, which no crew-base model sees.",
                ))
    fleets = set(loaders.load_dataset(cfg, "d1_crew_master")["fleet"].drop_nulls().unique())
    base_flights = raw.filter(pl.col("origin").is_in(clean.active_pilot_bases(
        loaders.load_dataset(cfg, "d1_crew_master"), cfg.scope.base)))
    foreign = base_flights.filter(~pl.col("fleet").is_in(sorted(fleets)))
    if foreign.height:
        codes = ", ".join(f"{r['fleet']} {r['len']}" for r in foreign.group_by("fleet").len().sort("len", descending=True).to_dicts())
        out.append(Limitation(
            "d8_unknown_fleets", INFO, f"{foreign.height} departures from the crew bases are on fleets no pilot is rated on",
            f"{codes}. They count in the regime model's daily flight totals (not in the delay model, "
            "which filters on the scope fleet).",
        ))
    return out


def _d5_d7(cfg: config.BaseConfig) -> list[Limitation]:
    out: list[Limitation] = []
    d5 = loaders.load_dataset(cfg, "d5_reserve_callouts")
    outcomes = set(d5["outcome"].drop_nulls().unique())
    missing = {"released", "no-show", "declined"} - outcomes
    if missing and outcomes:
        out.append(Limitation(
            "d5_outcomes", INFO, "D5 reserve outcomes are incomplete",
            f"Outcomes present: {', '.join(sorted(outcomes))}; absent: {', '.join(sorted(missing))}. "
            "Release and no-show rates read 0% by construction, not by observation.",
        ))
    d7 = loaders.load_dataset(cfg, "d7_pay_register")
    ignored = sorted(
        c for c in d7["pay_code"].drop_nulls().unique()
        if cfg.data.pay_codes.get(c) is not None and cfg.data.pay_codes[c].comparable_to == "IGNORE"
    )
    if ignored:
        out.append(Limitation(
            "d7_codes_unconfirmed", INFO, f"{len(ignored)} D7 pay codes are registered without a confirmed meaning",
            f"{', '.join(ignored)}. Gate V6 does not compare them. D7 has no pay code for reserve "
            "utilisation, so that side of the backtest has no actual to compare to.",
        ))
    return out


def collect(cfg: config.BaseConfig) -> list[Limitation]:
    """Every data-load limitation for this corpus and configuration."""
    if cfg.limitations is None:
        return []
    span = _span(cfg)
    items: list[Limitation] = []
    for check in (_fleet, _d12, _columns):
        items += check(cfg)
    items += _seasons(cfg, span)
    for check in (_d4, _d8, _d5_d7):
        try:
            items += check(cfg)
        except (FileNotFoundError, KeyError, loaders.SchemaError):
            continue  # a dataset the corpus does not have: the quality gates already say so
    return sort_limitations(items)


# --------------------------------------------------------------- calibration side
def from_store(cfg: config.BaseConfig, store: dict[str, Any]) -> list[Limitation]:
    """Limitations that only a fitted parameter store can show."""
    if cfg.limitations is None:
        return []
    out: list[Limitation] = []
    hmm = store.get("regime_hmm") or {}
    fit = hmm.get("fit") or {}
    selection = hmm.get("model_selection") or {}
    n_states = fit.get("n_states")
    preferred = selection.get("bic_preferred_n_states")
    if n_states and preferred and preferred != n_states:
        out.append(Limitation(
            "hmm_bic_prefers_fewer_states", MEDIUM,
            f"BIC prefers {preferred} regime states; the simulation uses {n_states}",
            f"Fitted on {fit.get('n_days')} informative days. The four named regimes (CALM..SEVERE) are "
            f"imposed by the simulation, not found by the data; the data supports {preferred}.",
        ))
    for warning in fit.get("stream_warnings", []) or []:
        out.append(Limitation("hmm_stream_warning", MEDIUM, "Regime fit warning", str(warning)))
    holdout = hmm.get("holdout") or {}
    if holdout.get("loglik_per_day") is not None and holdout.get("loglik_per_day_one_state") is not None:
        gain = holdout["loglik_per_day"] - holdout["loglik_per_day_one_state"]
        if gain < cfg.limitations.holdout_gain_min:
            out.append(Limitation(
                "hmm_holdout_gain_small", MEDIUM, "The regime model barely beats a one-state model out of sample",
                f"Holdout log-likelihood per day gains only {gain:.2f} over a single state "
                f"({holdout['loglik_per_day']:.2f} vs {holdout['loglik_per_day_one_state']:.2f}).",
            ))
    agreement = ((store.get("diagnostics") or {}).get("regime_label_agreement") or {})
    if agreement.get("agreement_rate") is None:
        out.append(Limitation(
            "regime_unvalidated", INFO, "Regime labels cannot be checked against a ground truth",
            "No D9 was supplied (it is no longer an input), so the inferred regimes have no "
            "independent check; on the mock their recovery was measured, on real data it is not.",
        ))
    nhpp = store.get("sick_call_nhpp") or {}
    if nhpp.get("dispersion") is not None and nhpp["dispersion"] < cfg.limitations.poisson_dispersion_max:
        out.append(Limitation(
            "nhpp_poisson", INFO, "The sick-call model is effectively Poisson",
            f"Fitted dispersion {nhpp['dispersion']:.3f}: no overdispersion beyond the regime effect.",
        ))
    return out
