import subprocess


def test_cli_compare():
    """Test that the compare command works and calculates paired statistics.

    S1d-04d wired this to the real CRN loop (des.run_policy_crn), so each
    scenario is now a real simulation (~1s) rather than an instant np.random
    draw -- kept small here (100 is the story's own manual-check scale, not
    an automated-suite one) so the suite stays fast.
    """
    result = subprocess.run(
        ["uv", "run", "crewsim", "compare", "--policies", "R6", "R10", "--scenarios", "3"],
        capture_output=True, text=True, check=False
    )

    assert result.returncode == 0
    assert "Comparing R6 vs R10 over 3 scenarios (CRN):" in result.stdout
    assert "Mean Difference" in result.stdout
    assert "95% CI" in result.stdout
    assert "t-statistic" in result.stdout

def test_cli_explain_cost():
    """explain-cost --summary reports a MEASURED staffing figure (S1a-04).

    Checks the arithmetic, not just the wording: the printed reserve-day
    breakdown must actually add up to the printed measured-window total. The
    previous version of this command derived that total from three literals
    hardcoded in cli.py (6 reserves, $250/day, a 28-day horizon), so the old
    string assertion held no matter what the engine did.
    """
    import re

    result = subprocess.run(
        ["uv", "run", "crewsim", "explain-cost", "--policy", "R6",
         "--category", "RESERVE_STAFFING", "--summary"],
        capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert "RESERVE_STAFFING" in result.stdout

    total = re.search(r"measured window \(\d+d\): \$([\d,]+\.\d\d)", result.stdout)
    assert total, f"no measured-window total in:\n{result.stdout}"
    measured = float(total.group(1).replace(",", ""))

    # "41 reserve-day(s) @ $180.00 + 69 reserve-day(s) @ $250.00"
    parts = re.findall(r"(\d+) reserve-day\(s\) @ \$([\d,]+\.\d\d)", result.stdout)
    assert parts, f"no rate breakdown in:\n{result.stdout}"
    derived = sum(int(n) * float(rate.replace(",", "")) for n, rate in parts)
    assert derived == measured, (
        f"staffing breakdown {derived} does not reconstruct the reported total {measured}"
    )
    # Paid at the real SC/LC tariffs from costs_pilots.yaml, so the figure
    # cannot be a single flat rate typed into the CLI.
    assert measured > 0.0

def test_cli_explain_draft():
    """Test that explain-draft command works."""
    result = subprocess.run(
        ["uv", "run", "crewsim", "explain-draft"],
        capture_output=True, text=True, check=False
    )

    assert result.returncode == 0
    assert "Selected:" in result.stdout

def test_cli_explain_legality_l8():
    """S1c-02's manual check: a long-call reserve given 1h notice against a
    16:00 report is ILLEGAL_L8, with all other rules satisfied. Also proves
    S1a-07's fixture (crashed before this story: is_legal_assignment() was
    called with no cfg, and L3 raises without one) is fixed as a side effect
    of the shared code path."""
    illegal = subprocess.run(
        ["uv", "run", "crewsim", "explain-legality", "--crew", "R002", "--pairing", "TS156", "--call-at", "15:00"],
        capture_output=True, text=True, check=False
    )
    assert illegal.returncode == 0
    assert "ILLEGAL_L8" in illegal.stdout

    legal = subprocess.run(
        ["uv", "run", "crewsim", "explain-legality", "--crew", "R002", "--pairing", "TS156", "--call-at", "00:00"],
        capture_output=True, text=True, check=False
    )
    assert legal.returncode == 0
    # "LEGAL" in stdout would also match "ILLEGAL_L8" as a substring --
    # assert the actual verdict line instead.
    assert "] LEGAL" in legal.stdout
    assert "ILLEGAL" not in legal.stdout

    l6 = subprocess.run(
        ["uv", "run", "crewsim", "explain-legality", "--crew", "C0203", "--pairing", "TS156"],
        capture_output=True, text=True, check=False
    )
    assert l6.returncode == 0
    assert "ILLEGAL_L6" in l6.stdout

def test_cli_explain_crew_rolling_counters():
    """S1c-03's manual check: rolling duty/flight hours must both accumulate
    and decay over a real crew's calendar, proving the window actually
    rolls rather than only ever growing. P00002 is a real corpus crew_id
    (the story's own placeholder, C0041, predates the real corpus and
    doesn't match its P##### id scheme) with a >7-day gap between duty
    blocks, so its rolling-7d counter drops sharply across that gap --
    not just a small decrease, which noisy sampling could produce too."""
    result = subprocess.run(
        ["uv", "run", "crewsim", "explain-crew", "--crew", "P00002", "--show-counters"],
        capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "(accumulated)" in result.stdout
    assert "(decayed)" in result.stdout

    duty_7d_values = [
        float(line.split("rolling 7d duty=")[1].split("h")[0])
        for line in result.stdout.splitlines() if "rolling 7d duty=" in line
    ]
    # A genuine window-rolling decay is a sharp drop across the gap, not
    # merely "the number went down slightly" (which noisy sampling near a
    # sample boundary could produce even with a bug in the window logic).
    max_drop = max(
        duty_7d_values[i] - duty_7d_values[i + 1] for i in range(len(duty_7d_values) - 1)
    )
    assert max_drop > 30.0

    timeline = subprocess.run(
        ["uv", "run", "crewsim", "explain-crew", "--crew", "P00002", "--timeline"],
        capture_output=True, text=True, check=False
    )
    assert timeline.returncode == 0
    assert "Timeline for Crew P00002" in timeline.stdout
    assert "PAIRING" in timeline.stdout

    unknown = subprocess.run(
        ["uv", "run", "crewsim", "explain-crew", "--crew", "ZZZZZ"],
        capture_output=True, text=True, check=False
    )
    assert unknown.returncode == 1
    assert "not found" in unknown.stdout

def test_cli_explain_crew_scenario():
    """S1b-05b's manual check: --scenario must show a crew's calendar AFTER
    that scenario's real DES/drafting events, not the static D2/D3 roster.
    P00448 is a real reserve drafted at t=2484 in scenario 0 under policy
    R10 (found via `explain-recovery --scenario 0 --policy R10 --trace`).
    Its static calendar has a single unbroken RESERVE (SC) block
    [t=1680->10320]; the real post-sim calendar must show that block split
    by a DRAFTED_DUTY/REST pair, proving --scenario reads real simulated
    state, not a copy of the static roster with a different label."""
    static = subprocess.run(
        ["uv", "run", "crewsim", "explain-crew", "--crew", "P00448", "--timeline"],
        capture_output=True, text=True, check=False
    )
    assert static.returncode == 0
    assert "DRAFTED_DUTY" not in static.stdout

    scenario = subprocess.run(
        ["uv", "run", "crewsim", "explain-crew", "--crew", "P00448", "--scenario", "0",
         "--policy", "R10", "--timeline"],
        capture_output=True, text=True, check=False
    )
    assert scenario.returncode == 0
    assert "scenario 0, policy" in scenario.stdout
    assert "DRAFTED_DUTY" in scenario.stdout
    assert "REST" in scenario.stdout
    # the old S1b-05/S1c-03 stopgap notice must be gone now that --scenario
    # is genuinely wired to simulated state
    assert "not yet wired to simulated state" not in scenario.stdout

    unknown = subprocess.run(
        ["uv", "run", "crewsim", "explain-crew", "--crew", "ZZZZZ", "--scenario", "0"],
        capture_output=True, text=True, check=False
    )
    assert unknown.returncode == 1
    assert "not found" in unknown.stdout

def test_cli_report():
    """S1e-02's manual check, at small scale: one self-contained HTML file,
    written and openable."""
    result = subprocess.run(
        ["uv", "run", "crewsim", "report", "--policies", "R4", "R10", "--scenarios", "2"],
        capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "wrote " in result.stdout
    path = result.stdout.strip().splitlines()[-1].removeprefix("wrote ")
    assert path.endswith("policy_report.html")
    import pathlib
    assert pathlib.Path(path).is_file()

def test_cli_report_drilldown():
    """S1e-03's manual check: crewsim report --policy R6 --drilldown costliest."""
    result = subprocess.run(
        ["uv", "run", "crewsim", "report", "--policy", "R6", "--drilldown", "costliest", "--scenarios", "3"],
        capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "wrote " in result.stdout

    path = result.stdout.strip().splitlines()[-1].removeprefix("wrote ")
    import pathlib
    html = pathlib.Path(path).read_text()
    assert 'id="drilldown"' in html
    assert "costliest" in html
    assert "typical" in html

def test_cli_report_requires_a_policy():
    result = subprocess.run(
        ["uv", "run", "crewsim", "report", "--scenarios", "3"],
        capture_output=True, text=True, check=False
    )
    assert result.returncode == 1
    assert "needs --policies and/or --policy" in result.stdout

def test_cli_counterfactual():
    """S1e-05's manual check: crewsim counterfactual --vs-mandated."""
    result = subprocess.run(
        ["uv", "run", "crewsim", "counterfactual", "--vs-mandated", "--policy", "R6", "--scenarios", "3"],
        capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "NOT A RECOMMENDATION" in result.stdout
    assert "mandated" in result.stdout
    assert "junior_first" in result.stdout
    assert "myopic_total_cost" in result.stdout
    assert "vs mandated" in result.stdout


def test_cli_gate_v5():
    """S1e-06's manual check: crewsim gate v5 --format timeline (--week
    omitted -- default auto-picks the mock corpus's peak-disruption week)."""
    result = subprocess.run(
        ["uv", "run", "crewsim", "gate", "v5", "--format", "timeline", "--policy", "R6"],
        capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "V5 Trace Walkthrough" in result.stdout
    assert "MOCK CORPUS DATA" in result.stdout
    assert "would you have actually done this" in result.stdout


def test_cli_gate_v6():
    """S1e-07's manual check: crewsim gate v6 --period 2026-01."""
    result = subprocess.run(
        ["uv", "run", "crewsim", "gate", "v6", "--period", "2026-01", "--policy", "R6"],
        capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "MOCK CORPUS DATA" in result.stdout
    assert "Gate V6" in result.stdout
    assert "Bias decomposition" in result.stdout
    assert "OVERSTATES" in result.stdout
    assert "UNDERSTATES" in result.stdout


def test_cli_gate_v6_requires_period():
    result = subprocess.run(
        ["uv", "run", "crewsim", "gate", "v6", "--policy", "R6"],
        capture_output=True, text=True, check=False
    )
    assert result.returncode == 2
    assert "requires --period" in result.stdout


def test_cli_grid():
    """S1e-04's manual check, at small scale: the R-axis grid runner writes
    a CSV summary and prints a table for every combination."""
    result = subprocess.run(
        ["uv", "run", "crewsim", "grid", "--scenarios", "2", "--jobs", "2"],
        capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "Grid report" in result.stdout
    assert "CRN-paired" in result.stdout
    for name in ("R4", "R6", "R8", "R10", "R14"):
        assert name in result.stdout

    path = result.stdout.strip().splitlines()[-1].removeprefix("wrote ")
    import pathlib
    p = pathlib.Path(path)
    assert p.is_file()
    assert p.name == "grid_results.csv"
    rows = p.read_text().strip().splitlines()
    assert len(rows) == 6  # header + 5 policies


def test_cli_gate_v7():
    """S1e-02 found and fixed gate v7: it crashed with a NameError on every
    invocation (streams_seq/master_key/n_scen referenced but never
    defined) -- must now actually run and pass."""
    result = subprocess.run(
        ["uv", "run", "crewsim", "gate", "v7", "--jobs", "2"],
        capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "PASS" in result.stdout
    assert "NameError" not in result.stderr

def test_cli_run_assert_invariants_l5():
    """S1c-04's manual check: --assert-invariants must verify L5 held for
    real, as a DELTA (streak containment, not raw count or exact-span
    equality) against the pre-simulation baseline -- a raw post-sim count
    would always report violations, since the real static roster already
    has pre-existing L5 "violations" per policy scope (real multi-day trips
    with <24h gaps between duties; L5 is deliberately conservative per spec
    5.4, not a corpus bug -- see S1c-04b). Exact-span comparison was tried
    and rejected: a sick call removing a block from the middle of a
    baseline streak shrinks its span (an improvement) but produces a
    different tuple, which exact matching wrongly flagged as "new".

    returncode is 1, not 0: the V3 gate section (printed by this same
    --assert-invariants path) fails independently and unrelated to L5 --
    documented since S1d-04d/S1d-05 as a known, separate gate-reliability
    issue against the historical holdout band. This test is about L5's own
    verdict specifically, not the combined exit code.
    """
    result = subprocess.run(
        ["uv", "run", "crewsim", "run", "--policy", "R6", "--scenarios", "3", "--assert-invariants"],
        capture_output=True, text=True, check=False
    )
    assert result.returncode == 1
    assert "L5 Duty-Free-Day Invariant" in result.stdout
    assert "PASS: no scenario introduced or extended an L5 streak" in result.stdout

def test_cli_run_report_eligibility():
    """S1c-01's manual check: a histogram, not a mean. Also exercises `run`'s
    bare-policy-name resolution (R10, not a path) -- kept small, the story's
    own bar is --scenarios 200."""
    result = subprocess.run(
        ["uv", "run", "crewsim", "run", "--policy", "R10", "--scenarios", "3", "--report-eligibility"],
        capture_output=True, text=True, check=False
    )

    assert result.returncode == 0
    assert "Eligibility distribution" in result.stdout
    assert "mean = " in result.stdout
    assert "E[cost]" in result.stdout

def test_cli_run_kpis():
    """S1e-01's manual check: every KPI, with the measurement window
    explicitly excluded/stated."""
    result = subprocess.run(
        ["uv", "run", "crewsim", "run", "--policy", "R6", "--scenarios", "3", "--kpis"],
        capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "KPI report" in result.stdout
    assert "Measurement window:" in result.stdout
    assert "warm-up excluded" in result.stdout
    assert "E[cost]" in result.stdout
    assert "CVaR95" in result.stdout
    assert "Uncovered legs" in result.stdout
    assert "Reserve utilisation" in result.stdout
    assert "Eligibility" in result.stdout
    assert "Cascade rate" in result.stdout
    assert "Draft distribution" in result.stdout
    assert "Gini" in result.stdout
    assert "premium earnings" in result.stdout


# ===================== S1c-05 AC3: V3 must not be silent on any run =========
def test_plain_run_surfaces_the_v3_verdict():
    """AC3: "Every run surfaces this ... a number failing V3 must never reach a
    planner silently."

    Until this was wired, `crewsim run` printed an E[cost] of several million
    with no mention of V3 at all, while the gate was failing by more than 4x.
    """
    result = subprocess.run(
        ["uv", "run", "crewsim", "run", "--policy", "R6", "--scenarios", "1"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert "E[cost]" in result.stdout, "sanity: the run must still report a cost"
    assert "GATE V3" in result.stdout, (
        "a cost figure reached the user with no V3 verdict attached"
    )


def test_compare_surfaces_the_v3_verdict():
    """`compare` prints a paired difference a planner may act on directly, so it
    carries the same verdict."""
    result = subprocess.run(
        ["uv", "run", "crewsim", "compare", "--policies", "R6", "R10", "--scenarios", "1"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert "Mean Difference" in result.stdout
    assert "GATE V3" in result.stdout


def test_failing_v3_marks_the_figures_unvalidated():
    """A verdict the reader can miss is not a verdict. When V3 fails the banner
    must say so in terms that stop someone quoting the number."""
    result = subprocess.run(
        ["uv", "run", "crewsim", "run", "--policy", "R6", "--scenarios", "1"],
        capture_output=True, text=True, check=False,
    )
    if "GATE V3 FAILED" not in result.stdout:
        import pytest
        pytest.skip("V3 passes on this corpus -- nothing to assert about the failure banner")
    assert "UNVALIDATED" in result.stdout
    assert "gate v3" in result.stdout, "the banner must point at the full report"


def test_v3_verdict_reports_pass_when_the_distribution_is_in_band(capsys):
    """The PASS branch is unreachable against the current corpus (V3 fails by
    design there), so it is exercised directly with an in-band distribution --
    otherwise only the failure path would ever be executed."""
    import types

    from crewsim import config
    from crewsim.cli import _print_v3_verdict
    from crewsim.data.eligibility_target import reconstruct_eligibility

    cfg = config.load()
    hist = reconstruct_eligibility(cfg, "holdout")
    sims = [types.SimpleNamespace(
        elig=types.SimpleNamespace(get_distribution=lambda: [hist["mean"]] * 50)
    )]

    assert _print_v3_verdict(cfg, sims) is True
    out = capsys.readouterr().out
    assert "GATE V3 PASS" in out
    assert "FAILED" not in out


def test_v3_verdict_says_not_evaluated_rather_than_failing_on_no_events(capsys):
    """Zero eligibility events would give a mean of 0.0, which is below the
    historical band and would read as a FAIL. Absence of evidence is not a
    failing gate -- it has to say which one it is."""
    import types

    from crewsim import config
    from crewsim.cli import _print_v3_verdict

    sims = [types.SimpleNamespace(
        elig=types.SimpleNamespace(get_distribution=list)
    )]
    assert _print_v3_verdict(config.load(), sims) is False
    out = capsys.readouterr().out
    assert "not evaluated" in out
    assert "FAILED" not in out
