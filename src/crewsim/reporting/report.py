import html
import pathlib
import re
import sys
from typing import Any

import numpy as np

_CONFIRM_RE = re.compile(r"\[CONFIRM:\s*([^\]]*)\]")

# Gates that are still hardcoded stubs (pre-existing, not fixed here -- their
# own backlog stories, not S1e-02's, own actually building a real check).
# The whole point of this report is "no black box" (spec Sec9.3) -- a report
# that silently prints their fake PASS text would violate that on its own
# front page, so they're always labelled STUB, never PASS/FAIL.
# Empty since S1a-10 and S1b-07: V1 and V2 were both hardcoded text and are now
# real gates reading real ledgers/simulations. Kept as a mechanism, not deleted --
# the report's whole premise is "no black box" (spec Sec9.3), so if a future gate
# ships as a stub it must be labelled STUB here rather than printing a fake PASS.
KNOWN_STUB_GATES: dict[str, str] = {}

# Prod-readiness review of 05_slice_1e (2026-08-11): this report's "Gate
# status" table used to list only V1/V2/V3/V4/V7/V9 -- 6 of the 9 gates spec
# Sec9's own top line requires ("No output... until all nine gates (V1-V9)
# are passed") and Sec9.3 item 3 requires this exact report to show. V5/V6/V8
# were simply absent, not shown as unevaluated -- indistinguishable, on this
# page, from "these gates don't exist". Each of the three genuinely cannot be
# computed from build_report's own inputs (policy names + scenario count):
# V5/V6 need a human SME session / real payroll data neither of which this
# repo has (see gates/v5_trace.py, gates/v6_backtest.py's own module
# docstrings), and V8 is a property-based invariant over the whole engine
# (`pytest tests/engine/test_legality.py`), not a per-run verdict. Shown here
# as NOT EVALUATED rather than silently omitted, so "only 6 gates" is never
# what a planner reading this page comes away believing.
NOT_EVALUATED_GATES: dict[str, str] = {
    "V5": "requires a real IOC duty manager SME walkthrough session -- run `crewsim gate v5` "
          "and hold that session; this report cannot self-certify a human verdict.",
    "V6": "requires real D7 payroll / D10 invoice data, which does not exist in this repo "
          "(mock corpus only) -- run `crewsim gate v6 --period YYYY-MM` for the mechanics; "
          "see its own MOCK CORPUS DATA caveat.",
    "V8": "a property-based invariant over the whole engine, not a per-run verdict -- "
          "run `pytest tests/engine/test_legality.py`.",
}


def extract_confirm_markers(paths: list[pathlib.Path]) -> list[dict[str, Any]]:
    """S1e-02: every outstanding `[CONFIRM: owner]` marker across the given
    config files (spec Sec9.3, item 5) -- these are YAML COMMENTS, invisible
    to a parsed config object, so this reads the raw file text directly.

    `scope: "key"` markers are attached to one line with a `key: value`
    before the comment; `scope: "section"` markers are standalone comment
    lines (e.g. costs_pilots.yaml's own file-level "EVERY VALUE HERE IS
    [CONFIRM: ...]" blanket, or a comment above a whole config block) and
    must not be rendered as if they were a single specific field. Lines
    documenting the `[CONFIRM: <owner>]` convention itself (a literal
    `<owner>` placeholder, not a real name) are skipped -- not an actual
    outstanding item.
    """
    markers = []
    for path in paths:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            m = _CONFIRM_RE.search(line)
            if not m:
                continue
            owner = m.group(1).strip()
            if "<" in owner:
                continue
            before_comment = line.split("#", 1)[0].strip()
            markers.append({
                "file": path.name,
                "line": lineno,
                "owner": owner,
                "context": line.strip(),
                "scope": "key" if before_comment else "section",
            })
    return markers


def build_provenance(cfg: Any, policy: Any, master_seed: str) -> dict[str, Any]:
    """The reproducibility chain (spec Sec9.3, item 2): data window, params
    version, master seed, costs version, policy hash -- same fields as the
    CLI's `run --print-provenance`, factored out so both share one source.

    That source is `reporting/provenance.py`. It used to be `cli._params_provenance`
    -- a reporting module reaching back into the CLI for a helper the CLI does
    not own -- which broke the moment the helper moved.
    """
    from .provenance import params_provenance

    data_window = f"{cfg.windows.fitting.start} to {cfg.windows.holdout.end}" if cfg.windows else "unknown"
    costs_ver = policy.costs_file.split("@")[1] if "@" in policy.costs_file else "unknown"
    params_ver, params_hash = params_provenance(cfg)
    return {
        "data_window": data_window,
        # Real params-store version + blake2b receipt, shared with the CLI's
        # own `run --print-provenance` (S1a-09) rather than restating a
        # placeholder that outlived the thing it was standing in for.
        "params_version": f"{params_ver} ({params_hash})",
        "master_seed": master_seed,
        "costs_version": costs_ver,
        "policy_hash": policy.get_hash(),
        "policy_id": policy.policy_id,
    }


def build_report(
    cfg: Any,
    costs: Any,
    policy_names: list[str],
    n_scenarios: int,
    master_seed: str = "master",
    representative_policy: str | None = None,
    drilldown_policy: str | None = None,
    drilldown_mode: str | None = None,
) -> pathlib.Path:
    """S1e-02/S1e-03: one self-contained HTML file -- cost distributions,
    the R trade-off curve (E[C]/CVaR95), the lambda curve (real R* per
    risk-dial value, spec Sec7.4), provenance chain, gate status,
    outstanding [CONFIRM:] flags, and (if drilldown_policy is given) the 5
    costliest and 5 most-typical scenario timelines for that policy, each
    traceable cost-row-by-cost-row back through root_event_uid (spec
    Sec9.3/Sec2.3-C2). No CDN, no local server -- plotly embedded inline
    once (same convention as gates/v3_eligibility.py::write_v3_report).

    drilldown_mode ("costliest"/"typical"/"both") does not filter which
    scenarios appear -- both groups are always shown, since that's this
    story's own acceptance bar ("the 5 costliest AND 5 most typical"). The
    mode is display-only (which group is listed first).
    """
    import plotly.graph_objects as go

    from .. import config
    from ..engine import des
    from ..engine.policy import load_policy
    from ..gates.v3_eligibility import run_v3_gate
    from ..gates.v4_cascade import run_v4_gate
    from ..gates.v9_sensitivity import real_r_recommender
    from .drilldown import build_scenario_drilldown, select_exemplar_scenarios
    from .gate_status import compute_core_gates
    from .kpis import reserve_usage_by_call_type, unused_paid_call_types

    representative_policy = representative_policy or policy_names[0]

    per_policy: dict[str, dict[str, Any]] = {}
    sims_by_policy: dict[str, list[Any]] = {}
    for i, name in enumerate(policy_names, start=1):
        print(f"  policy {name} ({i}/{len(policy_names)})...", file=sys.stderr)
        policy = load_policy(config.policy_path(name))

        def _progress(done: int, total: int) -> None:
            print(f"\r    scenario {done}/{total}", end="", file=sys.stderr, flush=True)

        # Trace only the policy the drilldown actually needs -- tracing
        # every policy here would waste memory when comparing several R
        # candidates but drilling into just one.
        sims = des.run_policy_crn(cfg, costs, policy, n_scenarios, master_seed,
                                   on_progress=_progress, trace=(name == drilldown_policy))
        print(file=sys.stderr)
        scenario_costs = des.measured_window_costs(cfg, sims)
        r_value = int(name.lstrip("R"))
        per_policy[name] = {
            "policy": policy,
            "r_value": r_value,
            "scenario_costs": scenario_costs,
            "mean_cost": float(np.mean(scenario_costs)),
            "cvar95": des.cvar95(scenario_costs),
            "reserve_by_call_type": reserve_usage_by_call_type(cfg, sims),
        }
        sims_by_policy[name] = sims

    # ---- gate status --------------------------------------------------
    rep_sims = sims_by_policy[representative_policy]
    v3_result = run_v3_gate(cfg, [f for sim in rep_sims for f in sim.elig.get_distribution()], window="holdout")
    v4_cascade_rates = [sim.n_cascading_drafts / sim.n_drafts for sim in rep_sims if sim.n_drafts > 0]
    v4_result = run_v4_gate(cfg, v4_cascade_rates, window="holdout")

    # V1/V2/V7 each need their own small, independent simulation run -- see
    # reporting/gate_status.py's own module docstring for why this is a
    # shared function rather than inline calls here: api/routers/processing.py
    # needs the exact same three gates on the native Results page, and two
    # copies of "run V1/V2/V7 and format the row" is exactly the kind of
    # drift-prone duplication this project keeps finding and fixing.
    core_gates = compute_core_gates(
        cfg, costs, per_policy[representative_policy]["policy"], master_seed
    )

    # V9: the real argmin-over-R lambda curve, from the SAME per-policy sims
    # already run above -- not a second simulation pass (build_r_star_lookup
    # would re-run these; reuse its formula (real_r_recommender) on data we
    # already have instead).
    term_pen = costs.disruption.terminal_penalty_multiple
    r_lookup = {(d["r_value"], term_pen): (d["mean_cost"], d["cvar95"]) for d in per_policy.values()}
    recommend = real_r_recommender(r_lookup)
    lambdas = cfg.sensitivity.lambda_risk_dial
    lambda_curve = [(lam, recommend(0, term_pen, lam)) for lam in lambdas]
    v9_unstable = (max(r for _, r in lambda_curve) - min(r for _, r in lambda_curve)) > cfg.sensitivity.instability_threshold

    gate_rows = [
        *[(row["gate"], row["verdict"], row["detail"]) for row in core_gates],
        ("V3", "PASS" if v3_result["pass"] else "FAIL",
         (f"sim mean {v3_result['sim_mean']:.3f} vs historical band "
         f"[{v3_result['ci_lower']:.3f}, {v3_result['ci_upper']:.3f}] (policy {representative_policy})")),
        ("V4", "PASS" if v4_result["pass"] else "FAIL",
         (f"sim mean {v4_result['sim_mean']:.3f} vs historical band "
         f"[{v4_result['ci_lower']:.3f}, {v4_result['ci_upper']:.3f}] (policy {representative_policy})")),
        ("V9", "UNSTABLE" if v9_unstable else "STABLE",
         (f"R* ranges {min(r for _, r in lambda_curve)}-{max(r for _, r in lambda_curve)} across "
         f"lambda={lambdas[0]}..{lambdas[-1]}")),
        *[(gate, "NOT EVALUATED", reason) for gate, reason in NOT_EVALUATED_GATES.items()],
    ]

    provenance = build_provenance(cfg, per_policy[representative_policy]["policy"], master_seed)
    confirm_markers = extract_confirm_markers([
        config.repo_root() / "configs" / "base.yaml",
        config.repo_root() / "configs" / "costs_pilots.yaml",
    ])

    # ---- S1e-03: exemplar-scenario drill-down --------------------------
    drilldown_sections: list[dict[str, Any]] = []
    if drilldown_policy:
        if drilldown_policy in sims_by_policy:
            # Already simulated (with trace=True, see the main loop above)
            # as part of policy_names -- reuse instead of re-simulating.
            dd_sims = sims_by_policy[drilldown_policy]
        else:
            print(f"  drilldown: policy {drilldown_policy} ({n_scenarios} scenario(s), traced)...", file=sys.stderr)
            dd_policy = load_policy(config.policy_path(drilldown_policy))

            def _dd_progress(done: int, total: int) -> None:
                print(f"\r    scenario {done}/{total}", end="", file=sys.stderr, flush=True)

            dd_sims = des.run_policy_crn(cfg, costs, dd_policy, n_scenarios, master_seed,
                                          on_progress=_dd_progress, trace=True)
            print(file=sys.stderr)
        costliest, typical = select_exemplar_scenarios(cfg, dd_sims, k=5)
        groups = [("costliest", costliest), ("typical", typical)]
        if drilldown_mode == "typical":
            groups.reverse()
        for label, pairs in groups:
            for sim, cost in pairs:
                drilldown_sections.append({"label": label, **build_scenario_drilldown(cfg, sim, cost)})

    # ---- figures --------------------------------------------------------
    cost_fig = go.Figure()
    for name, d in per_policy.items():
        cost_fig.add_trace(go.Histogram(x=d["scenario_costs"], name=name, opacity=0.6, histnorm="probability"))
    cost_fig.update_layout(barmode="overlay", title="Cost distribution per policy (measurement window)",
                            xaxis_title="Scenario cost ($)", yaxis_title="Probability", height=450)

    r_sorted = sorted(per_policy.values(), key=lambda d: d["r_value"])
    r_values = [d["r_value"] for d in r_sorted]
    means = [d["mean_cost"] for d in r_sorted]
    cvars = [d["cvar95"] for d in r_sorted]
    optimum_r = r_values[int(np.argmin(cvars))]
    e_c_spread = (max(means) - min(means)) / min(means) if means else 0.0

    tradeoff_fig = go.Figure()
    tradeoff_fig.add_trace(go.Scatter(x=r_values, y=means, mode="lines+markers", name="E[cost]"))
    tradeoff_fig.add_trace(go.Scatter(x=r_values, y=cvars, mode="lines+markers", name="CVaR95"))
    tradeoff_fig.add_vline(x=optimum_r, line_color="green", line_dash="dash",
                            annotation_text=f"CVaR95 optimum R={optimum_r}", annotation_position="top")
    tradeoff_fig.update_layout(title="Reserve-level trade-off curve", xaxis_title="Reserves (R)",
                                yaxis_title="Cost ($)", height=450)

    lambda_fig = go.Figure()
    for d in r_sorted:
        r = d["r_value"]
        objective = [d["mean_cost"] + lam * d["cvar95"] for lam in lambdas]
        lambda_fig.add_trace(go.Scatter(x=lambdas, y=objective, mode="lines+markers", name=f"R={r} objective"))
    lambda_fig.add_trace(go.Scatter(
        x=[lam for lam, _ in lambda_curve], y=[r for _, r in lambda_curve],
        mode="lines+markers", name="R* (right axis)", yaxis="y2", line={"color": "black", "width": 3},
    ))
    lambda_fig.update_layout(
        title="Lambda curve -- objective per R (spec Sec7.4: E[cost] + lambda*CVaR95) and recommended R*",
        xaxis_title="lambda (risk dial)", yaxis_title="Objective value ($)",
        yaxis2={"title": "Recommended R*", "overlaying": "y", "side": "right"},
        height=450,
    )

    # ---- assemble one self-contained HTML page ---------------------------
    def esc(v: Any) -> str:
        # quote=False: every use here is a text node (table cell, <p>, <h2>/
        # <h3>), never an HTML attribute value, so apostrophes/quotes don't
        # need escaping -- only "<"/">"/"&" (real crew ids, pairing ids, and
        # config comment text can contain either character legitimately).
        return html.escape(str(v), quote=False)

    def table(headers: list[str], rows: list[tuple]) -> str:
        head = "".join(f"<th>{esc(h)}</th>" for h in headers)
        body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in rows)
        return f'<table border="1" cellpadding="4" cellspacing="0"><tr>{head}</tr>{body}</table>'

    def render_drilldown_scenario(d: dict[str, Any]) -> str:
        anchor = f"scenario-{d['label']}-{d['scenario_id']}"
        chain_html = []
        for chain in d["chains"]:
            rows = table(
                ["sim_time", "category", "crew_id", "amount"],
                [(f"{r.sim_time:.0f}", r.category, r.crew_id or "-", f"${r.amount:,.2f}") for r in chain["rows"]],
            )
            trace_html = "<br>".join(esc(line) for line in chain["trace_lines"])
            chain_html.append(
                f"<div><b>Root event {chain['root_event_uid']}</b> -- full causal chain "
                f"({len(chain['rows'])} cost row(s)):{rows}<p>{trace_html}</p></div>"
            )
        full_trace = "<br>".join(esc(line) for line in d["trace"])
        return (
            f'<h3 id="{anchor}">Scenario {d["scenario_id"]} ({d["label"]}) -- '
            f'${d["cost"]:,.2f}</h3>'
            f"<details><summary>{len(d['chains'])} uncovered-leg causal chain(s) "
            f"(cancellation/terminal penalty traced back to root_event_uid)</summary>"
            f"{''.join(chain_html) if chain_html else '<p>No uncovered legs in this scenario.</p>'}"
            f"</details>"
            f"<details><summary>Full event timeline ({len(d['trace'])} lines)</summary>"
            f'<div style="max-height:400px;overflow-y:auto;font-family:monospace;font-size:0.85em;">'
            f"{full_trace}</div></details>"
        )

    parts = [
        # IMP-410: a real document head. Without <meta charset>, a browser
        # opening the file from disk guesses the encoding (cp1252 on Windows)
        # and renders the UTF-8 written below as mojibake.
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">',
        "<title>Crew Recovery Simulation -- Policy Comparison Report</title>",
        "</head><body>",
        "<h1>Crew Recovery Simulation -- Policy Comparison Report</h1>",
        f"<p>Policies: {esc(', '.join(policy_names))} &middot; {n_scenarios} scenario(s) &middot; "
        f"master_seed={esc(master_seed)} &middot; representative policy for V3/V4: {esc(representative_policy)}"
        + (f' &middot; <a href="#drilldown">Drill-down: costliest &amp; typical scenarios for '
           f'{esc(drilldown_policy)} &darr;</a>' if drilldown_sections else "")
        + "</p>",

        "<h2>Reproducibility chain</h2>",
        table(["field", "value"], [(k, v) for k, v in provenance.items()]),

        "<h2>Gate status</h2>",
        table(["gate", "verdict", "detail"], gate_rows),

        (f"<h2>Outstanding [CONFIRM:] flags ({len(confirm_markers)}, scanned configs/base.yaml, "
        f"configs/costs_pilots.yaml)</h2>"),
        table(["file", "line", "owner", "scope", "context"],
              [(m["file"], m["line"], m["owner"], m["scope"], m["context"]) for m in confirm_markers]),

        "<h2>Cost distributions</h2>",
        cost_fig.to_html(full_html=False, include_plotlyjs="inline"),

        "<h2>Reserve-level trade-off curve</h2>",
    ]
    if e_c_spread < 0.02:
        parts.append(
            f"<p><i>E[cost] varies by only {e_c_spread:.1%} across the swept R range -- effectively flat, "
            f"not a meaningful U-shape at this scale of data. CVaR95 is where the real trade-off is; "
            f"the marked optimum is CVaR95's minimum, not E[cost]'s.</i></p>"
        )
    # IMP-117: a reserve type that is paid for and never used is shown, not hidden.
    usage_rows = []
    unused_notes: list[str] = []
    for name, d in per_policy.items():
        usage = d["reserve_by_call_type"]
        for call_type, u in usage.items():
            usage_rows.append((
                name, call_type, f"{u['staffing_days_mean']:.2f}",
                f"${u['staffing_dollars_mean']:,.2f}", f"{u['assignments_mean']:.2f}",
            ))
        for call_type in unused_paid_call_types(usage):
            unused_notes.append(f"{name}: {call_type} reserves are paid for but never assigned")
    unused_warning = (
        f"<p><b>Warning:</b> {esc('; '.join(unused_notes))}. See configs/base.yaml "
        f"-&gt; legality.long_call_notice_hours and reserve_lines (IMP-117).</p>"
        if unused_notes else ""
    )
    parts.extend([
        tradeoff_fig.to_html(full_html=False, include_plotlyjs=False),
        "<h2>Reserve usage by call type (measurement window, mean per scenario)</h2>",
        table(["policy", "call type", "reserve-days paid", "staffing $", "assignments"], usage_rows),
        unused_warning,
        "<h2>Lambda curve</h2>",
        lambda_fig.to_html(full_html=False, include_plotlyjs=False),
    ])

    if drilldown_sections:
        parts.append(
            f'<h2 id="drilldown">Drill-down: exemplar scenarios for {esc(drilldown_policy)}</h2>'
            f"<p>The 5 costliest and 5 most-typical (closest to the median cost) of {n_scenarios} "
            f"simulated scenarios, each a real, auditable event timeline -- not an aggregate. Every "
            f"uncovered leg's cost is traced back through its root_event_uid to the sick call that "
            f"caused it (spec &sect;2.3/C2).</p>"
        )
        toc = "".join(
            f'<li><a href="#scenario-{d["label"]}-{d["scenario_id"]}">'
            f'{esc(d["label"])}: scenario {d["scenario_id"]} (${d["cost"]:,.2f})</a></li>'
            for d in drilldown_sections
        )
        parts.append(f"<ul>{toc}</ul>")
        for d in drilldown_sections:
            parts.append(render_drilldown_scenario(d))

    parts.append("</body></html>")

    out_dir = config.ensure_dir(cfg, "reports_dir")
    path = out_dir / "policy_report.html"
    path.write_text("\n".join(parts), encoding="utf-8")
    return path
