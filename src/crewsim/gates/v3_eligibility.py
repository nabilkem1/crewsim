import pathlib

import numpy as np

from crewsim import config
from crewsim.data.eligibility_target import reconstruct_eligibility


def run_v3_gate(cfg, sim_distribution, window="holdout"):
    """
    Validates a simulated distribution of eligibility fractions against the historical band.
    Returns a dict with pass/fail and metrics.
    """
    hist = reconstruct_eligibility(cfg, window)

    sim_mean = np.mean(sim_distribution) if len(sim_distribution) > 0 else 0.0
    gap = sim_mean - hist["mean"]

    passed = bool(hist["ci_lower"] <= sim_mean <= hist["ci_upper"])

    return {
        "pass": passed,
        "sim_mean": sim_mean,
        "hist_mean": hist["mean"],
        "ci_lower": hist["ci_lower"],
        "ci_upper": hist["ci_upper"],
        "gap": gap,
        # Kept for render_v3_report -- run_v3_gate already reconstructs the
        # historical side, so callers that also want to plot it don't need
        # to call reconstruct_eligibility a second time.
        "hist_distribution": hist["distribution"],
    }

def print_v3_report(result, window):
    print(f"Gate V3: Eligibility Holdout Validation ({window})")
    print(f"Historical Band: [{result['ci_lower']:.3f}, {result['ci_upper']:.3f}] (Mean: {result['hist_mean']:.3f})")
    print(f"Simulated Mean : {result['sim_mean']:.3f}")
    print(f"Gap            : {result['gap']:+.3f}")

    if result["pass"]:
        print("Verdict: [PASS] Simulated eligibility matches history.")
    else:
        print("Verdict: [FAIL] Simulated eligibility deviates significantly from history.")
        print("Suspect mechanism: Reserve rotation policies or L8 notice time constraints may be incorrectly modeled.")

def write_v3_report(cfg, result, sim_distribution, window: str) -> pathlib.Path:
    """S1c-05's own manual-check bar: 'both distributions plotted', not
    just numbers. A self-contained HTML file (same plotly convention as
    data/profile_html.py), written to reports_dir and returned as a path
    the CLI prints -- so `crewsim gate v3` produces something a reviewer
    can actually open and look at, not just terminal text.
    """
    import plotly.graph_objects as go

    fig = go.Figure()
    fig.add_trace(go.Histogram(x=sim_distribution, name="Simulated", opacity=0.6, histnorm="probability"))
    fig.add_trace(go.Histogram(x=result["hist_distribution"], name="Historical", opacity=0.6, histnorm="probability"))
    fig.add_vrect(
        x0=result["ci_lower"], x1=result["ci_upper"], fillcolor="green", opacity=0.15, line_width=0,
        annotation_text="Historical 95% CI", annotation_position="top left",
    )
    fig.add_vline(x=result["sim_mean"], line_color="blue",
                  annotation_text=f"Sim mean {result['sim_mean']:.3f}", annotation_position="top right")
    fig.add_vline(x=result["hist_mean"], line_color="green",
                  annotation_text=f"Hist mean {result['hist_mean']:.3f}", annotation_position="bottom right")

    verdict = "PASS" if result["pass"] else "FAIL"
    fig.update_layout(
        barmode="overlay",
        title=f"Gate V3: Eligibility Holdout Validation ({window}) -- Verdict: {verdict}",
        xaxis_title="Eligible fraction",
        yaxis_title="Probability",
        height=500,
    )

    out_dir = config.ensure_dir(cfg, "reports_dir")
    path = out_dir / f"gate_v3_{window}.html"
    path.write_text(fig.to_html(full_html=True, include_plotlyjs="inline"), encoding="utf-8")
    return path
