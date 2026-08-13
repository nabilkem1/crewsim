"""Regression + property tests for the 2026-08-11 audit fixes (AUD-01..28).

Each test names the finding it locks in. The hypothesis property test is the
§4.3 "torture test" V8 asks for: blocks_in must be exact on ANY calendar,
including the overlapping ones the engine itself creates after a draft.
"""
import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from crewsim import config
from crewsim.engine.des import measurement_window_bounds, rows_in_measurement_window
from crewsim.engine.drafting import determine_tier, select_draft_candidate
from crewsim.engine.ledger import CostLedger
from crewsim.engine.legality import (
    check_l0_single_assignment,
    check_l8_notice_time,
    find_duty_during_rest_violations,
    is_legal_assignment,
)
from crewsim.engine.sick_calls import apply_sick_call
from crewsim.engine.state import Block, BlockType, CrewMember, OpenTimeItem

DAY = 1440.0
_BTYPES = list(BlockType)


def _cfg():
    return config.load()


def _item(start: float, end: float, uid: int = 1) -> OpenTimeItem:
    return OpenTimeItem(
        uid=uid, pairing_id="PX", base="YUL", fleet="A321neoLR", position="FO",
        start=start, end=end, deadline=start, origin="SICK_CALL", root_event_uid=uid,
    )


# ---------------------------------------------------------------- AUD-01
@st.composite
def _calendars(draw):
    n = draw(st.integers(min_value=0, max_value=12))
    blocks = []
    for _ in range(n):
        start = draw(st.floats(min_value=0, max_value=10 * DAY, allow_nan=False))
        length = draw(st.floats(min_value=1.0, max_value=3 * DAY, allow_nan=False))
        btype = draw(st.sampled_from(_BTYPES))
        blocks.append(Block(start=start, end=start + length, btype=btype))
    blocks.sort(key=lambda b: b.start)
    return blocks


@settings(max_examples=200, deadline=None)
@given(_calendars(), st.floats(min_value=0, max_value=11 * DAY), st.floats(min_value=1, max_value=2 * DAY))
def test_blocks_in_is_exact_on_overlapping_calendars(calendar, q_start, q_len):
    """AUD-01: blocks_in == the naive overlap filter, for ANY calendar --
    overlapping blocks included, which the engine creates by design."""
    crew = CrewMember("H1", "YUL", {"A321neoLR"}, "FO", 1, calendar=calendar)
    q_end = q_start + q_len
    expected = [b for b in calendar if b.start < q_end and b.end > q_start]
    assert crew.blocks_in(q_start, q_end) == expected


def test_l0_rejects_duty_during_rest_behind_day_off():
    """AUD-01's reproduced failure: a REST spanning the query must fail L0
    even when a later-starting DAY_OFF sits between it and the query."""
    crew = CrewMember("C1", "YUL", {"A321neoLR"}, "FO", 1, calendar=[
        Block(start=540, end=1380, btype=BlockType.DRAFTED_DUTY, pairing_id="P1"),
        Block(start=1380, end=DAY + 600, btype=BlockType.REST),
        Block(start=DAY, end=DAY + 1439, btype=BlockType.DAY_OFF),
    ])
    verdict = check_l0_single_assignment(crew, DAY + 300, DAY + 480)
    assert not verdict.legal
    assert verdict.fail_rule == "ILLEGAL_L0"


# ---------------------------------------------------------------- AUD-02
def test_sick_crew_is_unavailable_for_their_own_broken_pairing():
    cfg = _cfg()
    rng = np.random.default_rng(0)
    sick = CrewMember("C9", "YUL", {"A321neoLR"}, "FO", 3, calendar=[
        Block(start=2 * DAY + 600, end=2 * DAY + 1200, btype=BlockType.PAIRING,
              pairing_id="P9", flight_mins=300),
    ])
    now = 2 * DAY + 300  # 5 h notice: L8 must not be what saves us
    crew, items = apply_sick_call(cfg, [sick], now, 2.0, 1, rng)
    assert crew is sick and len(items) == 1
    assert any(b.btype == BlockType.ABSENCE for b in sick.calendar)
    assert not is_legal_assignment(sick, items[0], now=now, cfg=cfg).legal
    assert select_draft_candidate([sick], items[0], cfg=cfg, now=now) is None


# ---------------------------------------------------------------- AUD-03
def test_cooldown_booked_chain_with_inwindow_marker_is_attributed():
    cfg = _cfg()
    _warmup_end, measurement_end = measurement_window_bounds(cfg)
    led = CostLedger()
    t_arrival = measurement_end - 2 * DAY   # in-window
    t_cancel = measurement_end + DAY        # cool-down
    led.book(0, "P", t_arrival, 7, 7, None, "OPEN_ITEM", 0.0)
    led.book(0, "P", t_cancel, 7, 7, None, "CANCELLATION", 25000.0)
    led.book(0, "P", t_cancel, 7, 7, None, "APPR_COMPENSATION", 700.0)

    class _Sim:
        ledger = led

    rows = rows_in_measurement_window(cfg, _Sim())
    assert sum(r.amount for r in rows) == 25700.0

    # and a chain that genuinely originates in cool-down stays excluded
    led2 = CostLedger()
    led2.book(0, "P", measurement_end + 60.0, 9, 9, None, "OPEN_ITEM", 0.0)
    led2.book(0, "P", measurement_end + DAY, 9, 9, None, "CANCELLATION", 25000.0)

    class _Sim2:
        ledger = led2

    assert rows_in_measurement_window(cfg, _Sim2()) == []


# ---------------------------------------------------------------- AUD-06
def test_block_equality_is_full_field():
    pairing = Block(start=100.0, end=200.0, btype=BlockType.PAIRING, pairing_id="PX")
    vacation = Block(start=100.0, end=500.0, btype=BlockType.VACATION)
    assert pairing != vacation
    cal = [vacation, pairing]
    cal.remove(pairing)
    assert cal == [vacation]


# ---------------------------------------------------------------- AUD-10
def test_l8_does_not_apply_to_line_holders():
    cfg = _cfg()
    line_holder = CrewMember("C7", "YUL", {"A321neoLR"}, "FO", 7, calendar=[
        Block(start=0, end=DAY, btype=BlockType.DAY_OFF),
    ])
    item = _item(start=60.0, end=500.0)  # 1 h notice, under the 2 h SC floor
    assert check_l8_notice_time(line_holder, item, now=0.0, cfg=cfg).legal

    reserve = CrewMember("R1", "YUL", {"A321neoLR"}, "FO", 9, calendar=[
        Block(start=0, end=DAY, btype=BlockType.RESERVE, reserve_call_type="SC"),
    ])
    verdict = check_l8_notice_time(reserve, item, now=0.0, cfg=cfg)
    assert not verdict.legal and verdict.fail_rule == "ILLEGAL_L8"


# ---------------------------------------------------------------- AUD-11
def test_duty_during_rest_scanner_flags_and_ignores_correctly():
    offender = CrewMember("C5", "YUL", {"A"}, "FO", 1, calendar=[
        Block(start=0.0, end=600.0, btype=BlockType.REST),
        Block(start=100.0, end=400.0, btype=BlockType.DRAFTED_DUTY),
    ])
    assert len(find_duty_during_rest_violations(offender)) == 1

    # rest overlapping a DAY_OFF is normal, and back-to-back duty->rest touches
    clean = CrewMember("C6", "YUL", {"A"}, "FO", 1, calendar=[
        Block(start=0.0, end=600.0, btype=BlockType.DRAFTED_DUTY),
        Block(start=600.0, end=1260.0, btype=BlockType.REST),
        Block(start=600.0, end=2 * DAY, btype=BlockType.DAY_OFF),
    ])
    assert find_duty_during_rest_violations(clean) == []


# ---------------------------------------------------------------- AUD-14
def test_simulator_draft_is_tier_5():
    cfg = _cfg()
    crew = CrewMember("C4", "YUL", {"A321neoLR"}, "FO", 2, calendar=[
        Block(start=3 * DAY, end=3 * DAY + 1439, btype=BlockType.SIMULATOR),
    ])
    assert determine_tier(crew, _item(3 * DAY + 600, 3 * DAY + 1200), cfg) == 5

    on_vacation = CrewMember("C3", "YUL", {"A321neoLR"}, "FO", 2, calendar=[
        Block(start=0.0, end=7 * DAY, btype=BlockType.VACATION),
        Block(start=DAY, end=DAY + 240, btype=BlockType.TRAINING),
    ])
    assert determine_tier(on_vacation, _item(3 * DAY + 600, 3 * DAY + 1200), cfg) == 4


# ============================================================================
# Post-fix code review, 2026-08-12. Six findings against the remediation
# itself; these lock in their fixes.
# ============================================================================

def _sim_with_open_items(spans):
    """A minimal stand-in carrying only what the Welch diagnostic reads:
    (created, resolved_or_None) per item, as ledger rows."""
    led = CostLedger()
    for uid, (created, resolved) in enumerate(spans, start=1):
        led.book(0, "P", created, uid, uid, None, "OPEN_ITEM", 0.0)
        if resolved is not None:
            led.book(0, "P", resolved, uid, uid, None, "CANCELLATION", 1.0)

    class _Sim:
        ledger = led

    return _Sim()


def test_welch_rejects_a_warmup_that_had_not_settled_at_the_measurement_boundary():
    """REVIEW-1: per_day[d] samples the queue at the END of day d, so the
    sample at the instant measurement opens is index warmup_days-1. A run
    that only settles at index warmup_days was still climbing when
    measurement began and must NOT read OK."""
    from crewsim.reporting.kpis import welch_warmup_diagnostic

    cfg = _cfg()
    w = cfg.horizon.warmup_days
    # 9 items open until just after the warm-up boundary, 1 open throughout:
    # queue is 10 through day w-1 (incl. the boundary sample) then 1.
    spans = [(0.0, (w + 1) * DAY - 100.0)] * 9 + [(0.0, None)]
    result = welch_warmup_diagnostic(cfg, [_sim_with_open_items(spans)])

    assert result["daily_mean_open_items"][w - 1] == 10.0, "queue still high at the boundary"
    assert result["stabilized_day"] == w
    assert result["ok"] is False, "a warm-up that settles only AFTER the boundary is not adequate"


def test_welch_accepts_a_warmup_that_settled_before_the_boundary():
    from crewsim.reporting.kpis import welch_warmup_diagnostic

    cfg = _cfg()
    w = cfg.horizon.warmup_days
    spans = [(0.0, (w - 1) * DAY - 100.0)] * 9 + [(0.0, None)]
    result = welch_warmup_diagnostic(cfg, [_sim_with_open_items(spans)])
    assert result["stabilized_day"] is not None
    assert result["stabilized_day"] <= w - 1
    assert result["ok"] is True


def test_a_state_with_no_outgoing_transition_backs_off_to_the_marginal_not_identity(monkeypatch):
    """REVIEW-2: an identity fallback row makes the state ABSORBING -- any
    scenario entering it stays there for the whole horizon, inflating
    E[C]/CVaR95 with a pure modelling artifact. The AUD-18 rewrite (one
    station, season+window filtered) makes such sparse states reachable."""
    import polars as pl

    from crewsim.calibration import regime

    days = [f"2024-01-{i:02d}" for i in range(1, 11)]
    # SEVERE appears only on the LAST day, so it has no successor at all.
    classes = ["CALM"] * 9 + ["SEVERE"]

    def fake_load(cfg, name):
        if name == "d9_station_days":
            return pl.DataFrame({
                "station": ["YUL"] * 10, "date": days,
                "disruption_class": classes, "season": ["winter_sun"] * 10,
            })
        if name == "d4_absences":
            return pl.DataFrame({"absence_start": days, "base": ["YUL"] * 10})
        if name == "d8_flight_movements":
            return pl.DataFrame({
                "date": days, "delay_minutes": [0] * 10,
                "cancelled": [0] * 10, "origin": ["YUL"] * 10,
            })
        return pl.DataFrame()

    monkeypatch.setattr(regime.loaders, "load_dataset", fake_load)
    monkeypatch.setattr(regime.config, "ensure_dir", lambda cfg, key: __import__("pathlib").Path("/tmp"))

    res = regime.fit_regime(_cfg(), "winter_sun")

    assert "SEVERE" in res["transition_rows_backed_off"], "the sparse row must be recorded, not silent"
    assert res["matrix"]["SEVERE"]["SEVERE"] != 1.0, "identity row = absorbing state"
    assert res["matrix"]["SEVERE"] == res["pi0"]
    for row in res["matrix"].values():
        assert abs(sum(row.values()) - 1.0) < 1e-9


def test_recall_is_undefined_not_zero_when_the_window_holds_no_ground_truth(tmp_path):
    """REVIEW-5: a window with no drafts to find used to report recall 0.0 --
    a hard FAIL -- for a vacuously perfect reconstruction."""
    import polars as pl

    from crewsim.data import drafts
    from crewsim.gates.v4_cascade import _recall_of

    cfg = _cfg()
    (tmp_path / "_ground_truth.json").write_text('{"drafts_true": 2584}')
    patched = cfg.model_copy(update={"paths": cfg.paths.model_copy(update={"corpus_dir": tmp_path})})

    empty = pl.DataFrame({"change_id": [], "crew_id": [], "timestamp": []})
    result = drafts.score_recall(patched, empty, true_n=0)
    assert result["recall"] is None, "no ground truth in window -> undefined, not 0.0"
    assert result["gate_pass"] is True
    assert _recall_of(result) is None, "a present None must pass through, not become 0.0"

    # ...and a real denominator still scores normally
    scored = drafts.score_recall(patched, empty, true_n=10)
    assert scored["recall"] == 0.0 and scored["gate_pass"] is False


def test_d9_completeness_charges_each_station_only_for_its_own_reporting_span():
    """REVIEW-6: a seasonal outstation reporting 3 of 10 days is complete,
    not 30% -- but an interior gap in a station's own span is still caught."""
    import polars as pl

    from crewsim.data.quality import d9_completeness

    full = [f"2024-01-{i:02d}" for i in range(1, 11)]
    seasonal = [f"2024-01-{i:02d}" for i in range(1, 4)]
    complete = pl.DataFrame({
        "station": ["YUL"] * 10 + ["YQB"] * 3,
        "date": full + seasonal,
    })
    assert d9_completeness(complete) == 1.0

    # drop one interior day from YUL's own span -> genuinely incomplete
    gapped = pl.DataFrame({
        "station": ["YUL"] * 9 + ["YQB"] * 3,
        "date": [d for d in full if d != "2024-01-05"] + seasonal,
    })
    assert d9_completeness(gapped) == 12 / 13


def test_an_unfittable_delay_mixture_names_the_scope_instead_of_raising_from_sklearn(monkeypatch):
    """REVIEW-3: too few delayed flights in the scoped window aborted the
    whole pipeline with sklearn's opaque 'Expected n_samples >= n_components'."""
    import polars as pl
    import pytest

    from crewsim.calibration import delays

    cfg = _cfg()

    def fake_load(cfg_, name):
        if name == "d9_station_days":
            return pl.DataFrame({
                "date": ["2024-01-01"], "station": [cfg.scope.base],
                "disruption_class": ["NORMAL"], "season": ["winter_sun"],
            })
        if name == "d8_flight_movements":
            return pl.DataFrame({
                "date": ["2024-01-01"], "origin": [cfg.scope.base],
                "fleet": [cfg.scope.fleet], "delay_minutes": [0], "cancelled": [0],
            })
        return pl.DataFrame()

    monkeypatch.setattr(delays.loaders, "load_dataset", fake_load)
    with pytest.raises(ValueError, match="delay-duration mixture needs at least"):
        delays.fit_delays(cfg, "winter_sun")
