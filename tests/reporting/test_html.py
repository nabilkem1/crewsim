import pathlib
import re

from crewsim import config
from crewsim.reporting.report import (
    KNOWN_STUB_GATES,
    build_provenance,
    build_report,
    extract_confirm_markers,
)


def test_extract_confirm_markers_classifies_key_vs_section(tmp_path):
    fixture = tmp_path / "fixture.yaml"
    fixture.write_text(
        "# Marker convention:\n"
        "#   [CONFIRM: <owner>]  a placeholder, not a real value.\n"
        "\n"
        "# EVERY VALUE HERE IS [CONFIRM: Finance + Crew Planning].\n"
        "block:\n"
        "  short_call: 250   # [CONFIRM: Finance]\n"
        "  long_call: 180    # [CONFIRM: Finance]\n"
    )
    markers = extract_confirm_markers([fixture])

    # The doc-comment describing the <owner> convention itself must be excluded.
    assert not any("<" in m["owner"] for m in markers)
    assert len(markers) == 3

    section = [m for m in markers if m["scope"] == "section"]
    assert len(section) == 1
    assert section[0]["owner"] == "Finance + Crew Planning"

    key_markers = [m for m in markers if m["scope"] == "key"]
    assert len(key_markers) == 2
    assert all(m["owner"] == "Finance" for m in key_markers)


def test_extract_confirm_markers_real_configs():
    """Real files, not a fixture -- must find the markers this report's own
    manual check depends on being visible."""
    markers = extract_confirm_markers([
        config.repo_root() / "configs" / "base.yaml",
        config.repo_root() / "configs" / "costs_pilots.yaml",
    ])
    assert len(markers) > 5
    assert any(m["file"] == "costs_pilots.yaml" and m["scope"] == "section" for m in markers)


def test_build_provenance_fields():
    from crewsim.engine.policy import load_policy

    cfg = config.load()
    policy = load_policy(config.repo_root() / "configs" / "policies" / "R6.yaml")
    prov = build_provenance(cfg, policy, master_seed="master")

    assert prov["master_seed"] == "master"
    assert prov["policy_id"] == policy.policy_id
    assert prov["policy_hash"] == policy.get_hash()
    assert "to" in prov["data_window"]  # "<fitting.start> to <holdout.end>"


def test_build_report_self_contained_and_honest(tmp_path):
    """S1e-02's own acceptance criteria, exercised end to end at small
    scale: one file, no external assets, real gate status (V1/V2 must be
    labelled STUB, never PASS -- the report's whole premise is 'no black
    box')."""
    cfg = config.load()
    costs = config.load_costs(cfg)

    path = build_report(cfg, costs, policy_names=["R4", "R10"], n_scenarios=2, master_seed="master")

    assert isinstance(path, pathlib.Path)
    assert path.is_file()
    html = path.read_text()

    # Self-contained: no tag that would make the browser fetch an external
    # resource. (The bundled plotly.js library itself contains literal
    # "https://..." strings for unused map-attribution features -- those are
    # not <script src=>/<link href=> tags and don't need network access to
    # render; write_v3_report's already-shipped output has the same
    # characteristic.)
    assert not re.search(r'<script[^>]*\bsrc="[^"]*"', html)
    assert not re.search(r'<link[^>]*\bhref="[^"]*"', html)

    assert "Gate status" in html
    for gate, reason in KNOWN_STUB_GATES.items():
        assert f"<td>{gate}</td><td>STUB</td>" in html
        assert reason in html
    # V3/V4/V7/V9 must report a real verdict, never STUB.
    for gate in ("V3", "V4", "V7", "V9"):
        assert re.search(rf"<td>{gate}</td><td>(PASS|FAIL|STABLE|UNSTABLE)</td>", html)

    assert "Reproducibility chain" in html
    assert "Outstanding [CONFIRM:] flags" in html
    assert "Cost distribution per policy" in html
    assert "Reserve-level trade-off curve" in html
    assert "Lambda curve" in html


def test_build_report_with_drilldown():
    """S1e-03: the drill-down section is reachable from the recommendation
    itself (an anchor link near the top), contains both exemplar groups,
    and reuses the comparison run instead of re-simulating (drilldown_policy
    is one of policy_names here)."""
    cfg = config.load()
    costs = config.load_costs(cfg)

    path = build_report(
        cfg, costs, policy_names=["R6"], n_scenarios=3, master_seed="master",
        drilldown_policy="R6", drilldown_mode="costliest",
    )
    html = path.read_text()

    assert 'href="#drilldown"' in html
    assert 'id="drilldown"' in html
    assert "costliest" in html
    assert "typical" in html
    assert "root_event_uid" in html.lower() or "Root event" in html
