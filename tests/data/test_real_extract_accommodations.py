"""Reading a REAL extract (Pierre's v3) without changing how the mock reads.

Each test pins one accommodation made so the real files load, and the guard that
keeps the mock's behaviour exactly as it was:

  * a fleet fallback widens the scope only when D1 holds more pilots for it
  * a D4 row with no notification time is replayed, not a crash
  * D8 self-loop rows are dropped only when configured
  * ABSENCE is a valid D2 block type; a deadhead leg is duty without flying
  * V6 compares the pay codes the config registers, not hard-coded ones
  * the limitations the reports show are computed, and the real config loads
"""
from __future__ import annotations

import datetime
import pathlib

import polars as pl

from crewsim import config
from crewsim.data import clean, limitations, loaders, quality
from crewsim.engine import replay, roster_loader
from crewsim.gates import v6_backtest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = config.load(quiet=True)


def _cfg(tmp_path: pathlib.Path, *, scope: dict | None = None, data: dict | None = None) -> config.BaseConfig:
    paths = BASE.paths.model_copy(update={"corpus_dir": tmp_path})
    cfg = BASE.model_copy(update={"paths": paths})
    if scope:
        cfg = cfg.model_copy(update={"scope": cfg.scope.model_copy(update=scope)})
    if data:
        cfg = cfg.model_copy(update={"data": cfg.data.model_copy(update=data)})
    return cfg


def _csv(path: pathlib.Path, header: list[str], rows: list[list[str]]) -> None:
    path.write_text("\n".join([",".join(header), *(",".join(r) for r in rows)]) + "\n", encoding="utf-8")


def _d1(tmp_path: pathlib.Path, rows: list[tuple[str, str, str]]) -> None:
    """rows: (crew_id, fleet, position) -- all YUL, ACTIVE pilots."""
    header = list(loaders.DATASET_SCHEMAS["d1_crew_master"])
    body = []
    for crew_id, fleet, position in rows:
        rec = dict.fromkeys(header, "")
        rec.update(crew_id=crew_id, base="YUL", crew_group="PILOT", position=position, fleet=fleet,
                   seniority_number="1", employment_status="ACTIVE")
        body.append([rec[h] for h in header])
    _csv(tmp_path / "d1_crew_master.csv", header, body)


# ------------------------------------------------------------------- fleet fallback
def test_the_fallback_fleet_is_used_when_d1_holds_more_pilots_for_it(tmp_path):
    _d1(tmp_path, [("P1", "A321", "FO"), ("P2", "A321", "FO"), ("P3", "A321", "FO"), ("P4", "A321neoLR", "FO")])
    cfg = config.resolve_scope_fleet(_cfg(tmp_path, scope={"fleet": "A321neoLR", "fleet_fallback": "A321"}))
    assert cfg.scope.fleet == "A321"
    assert cfg.scope.fleet_resolution is not None and "A321neoLR has 1" in cfg.scope.fleet_resolution


def test_the_configured_fleet_is_kept_when_it_has_at_least_as_many_pilots(tmp_path):
    _d1(tmp_path, [("P1", "A321neoLR", "FO"), ("P2", "A321neoLR", "FO"), ("P3", "A321", "FO")])
    cfg = config.resolve_scope_fleet(_cfg(tmp_path, scope={"fleet": "A321neoLR", "fleet_fallback": "A321"}))
    assert cfg.scope.fleet == "A321neoLR" and cfg.scope.fleet_resolution is None


def test_no_fallback_configured_changes_nothing(tmp_path):
    _d1(tmp_path, [("P1", "A321", "FO"), ("P2", "A321", "FO")])
    cfg = _cfg(tmp_path, scope={"fleet": "A321neoLR"})
    assert config.resolve_scope_fleet(cfg) is cfg


def test_the_mock_scope_is_not_widened():
    assert BASE.scope.fleet_fallback is None and BASE.scope.fleet_resolution is None


def test_the_real_config_loads_and_widens_the_scope_on_the_real_extract():
    real = ROOT / "configs/real.yaml"
    cfg = config.load(real, quiet=True)
    assert config.corpus_kind(cfg) == "REAL"
    assert cfg.paths.params_dir != BASE.paths.params_dir, "real output must not overwrite the mock's"
    assert cfg.draft_reconstruction.premium_pay_codes == ["DRAFT_THX", "DRAFT_T2"]
    assert cfg.windows is not None and cfg.windows.fitting.start >= datetime.date(2024, 5, 1)
    if (cfg.paths.corpus_dir / "d1_crew_master.csv").is_file():
        assert cfg.scope.fleet == "A321" and cfg.scope.fleet_resolution


def test_a_versioned_real_data_folder_counts_as_real(tmp_path):
    folder = tmp_path / "real_datav2" / "v3"
    folder.mkdir(parents=True)
    cfg = _cfg(folder)
    assert config.corpus_kind(cfg) == "REAL"


# --------------------------------------------------------------- null notification
def _d4(tmp_path: pathlib.Path) -> None:
    header = list(loaders.DATASET_SCHEMAS["d4_absences"])
    base = dict.fromkeys(header, "")
    base.update(base="YUL", fleet="A321", position="FO", absence_type="SICK", duration_days="1")

    def row(aid: str, start: str, notified: str) -> list[str]:
        r = {**base, "absence_id": aid, "crew_id": "P1", "absence_start": start, "absence_end": start,
             "notification_ts": notified}
        return [r[h] for h in header]

    _csv(tmp_path / "d4_absences.csv", header,
         [row("A1", "2026-01-10", "2026-01-09T08:00"), row("A2", "2026-01-11", "")])


def test_a_null_notification_is_assumed_at_the_absence_start_not_a_crash(tmp_path):
    _d4(tmp_path)
    cfg = _cfg(tmp_path, scope={"fleet": "A321"})
    out = replay._load_real_absences(cfg, datetime.date(2026, 1, 1), datetime.date(2026, 2, 1))
    assert [a["absence_id"] for a in out] == ["A2", "A1"] or {a["absence_id"] for a in out} == {"A1", "A2"}
    a2 = next(a for a in out if a["absence_id"] == "A2")
    assert a2["notified_min"] == a2["start_min"], "assumed reported at 00:00 on the first day"


def test_a_null_notification_can_be_excluded_instead(tmp_path):
    _d4(tmp_path)
    cfg = _cfg(tmp_path, scope={"fleet": "A321"}, data={"null_notification_ts": "exclude"})
    out = replay._load_real_absences(cfg, datetime.date(2026, 1, 1), datetime.date(2026, 2, 1))
    assert [a["absence_id"] for a in out] == ["A1"]


# ----------------------------------------------------------------- D8 self loops
def _d8_frame() -> pl.DataFrame:
    day = datetime.date(2026, 1, 5)
    t = datetime.datetime(2026, 1, 5, 10, 0)  # noqa: DTZ001 - the corpus's timestamps are naive
    return pl.DataFrame({
        "flight_no": ["TS1", "TS1", "TS1"], "date": [day] * 3, "origin": ["YUL"] * 3,
        "destination": ["CDG", "YUL", "YUL"], "actual_dep_local": [t, t, None],
        "cancelled": [0, 0, 1], "delay_minutes": [5, 0, None],
    })


def test_self_loop_flights_are_dropped_only_when_configured():
    kept = clean.operated_flights_report(BASE, _d8_frame())
    assert kept[1]["self_loops"] == 0
    cfg = BASE.model_copy(update={"data": BASE.data.model_copy(update={"drop_self_loop_flights": True})})
    out, report = clean.operated_flights_report(cfg, _d8_frame())
    assert report["self_loops"] == 2 and out["destination"].to_list() == ["CDG"]


# -------------------------------------------------------- block types and deadhead
def test_absence_is_a_valid_block_type():
    assert "ABSENCE" in quality.valid_block_types(BASE)


def test_a_deadhead_leg_is_duty_but_not_flying(tmp_path):
    header = [*loaders.DATASET_SCHEMAS["d3_pairing_legs"], "deadhead"]
    common = ["P1", "1"]

    def leg(seq: str, block: str, deadhead: str) -> list[str]:
        return [*common, seq, "TS1", "YUL", "YYZ", "2026-01-05T08:00", "2026-01-05T09:00",
                "2026-01-05T11:00", "2026-01-05T11:30", block, deadhead]

    _csv(tmp_path / "d3_pairing_legs.csv", header, [leg("1", "0.0", "1"), leg("2", "2.0", "0")])
    periods, incomplete, estimated = roster_loader._load_pairing_duty_periods(_cfg(tmp_path))
    assert not incomplete and not estimated, "a deadhead leg's zero block time is not an estimate"
    ((_start, _end, flight_hours),) = periods["P1"]
    assert flight_hours == 2.0, "only the operated leg counts as flying"


def test_without_the_deadhead_column_a_zero_block_leg_is_still_estimated(tmp_path):
    header = list(loaders.DATASET_SCHEMAS["d3_pairing_legs"])
    row = ["P1", "1", "1", "TS1", "YUL", "YYZ", "2026-01-05T08:00", "2026-01-05T09:00",
           "2026-01-05T11:00", "2026-01-05T11:30", "0.0"]
    _csv(tmp_path / "d3_pairing_legs.csv", header, [row])
    periods, _, estimated = roster_loader._load_pairing_duty_periods(_cfg(tmp_path))
    assert "P1" in estimated and periods["P1"][0][2] == 2.0


# ----------------------------------------------------------------- V6 pay codes
def test_v6_compares_the_pay_codes_the_config_registers():
    assert v6_backtest.comparable_pay_codes(BASE) == {"DRAFT_PREM", "RESERVE_GTE", "RESERVE_UTIL"}
    real = config.load(ROOT / "configs/real.yaml", quiet=True)
    assert v6_backtest.pay_codes_for(real, "DRAFT") >= {"DRAFT_THX", "DRAFT_T2"}
    assert "CHV" not in v6_backtest.comparable_pay_codes(real), "an unconfirmed code is not compared"


def test_the_v6_caveat_names_the_corpus_it_is_about():
    assert "MOCK" in v6_backtest.caveat_for({"corpus_kind": "MOCK"})
    assert "REAL" in v6_backtest.caveat_for({"corpus_kind": "REAL"})


# ------------------------------------------------------------------ limitations
def test_season_episodes_count_only_complete_seasons():
    months = {12, 1, 2, 3, 4}
    d = datetime.date
    whole = limitations.complete_season_episodes(months, d(2024, 5, 1), d(2025, 7, 31))
    assert [(a, b) for a, b, _ in whole] == [(d(2024, 12, 1), d(2025, 4, 30))]
    two = limitations.complete_season_episodes(months, d(2023, 8, 1), d(2025, 7, 31))
    assert len(two) == 2
    assert limitations.complete_season_episodes(months, d(2024, 4, 1), d(2024, 4, 30)) == []


def test_limitations_render_as_text_and_html_most_severe_first():
    items = [
        limitations.Limitation("b", limitations.INFO, "minor", "detail b"),
        limitations.Limitation("a", limitations.HIGH, "major <x>", "detail a"),
    ]
    text = limitations.format_limitations(items)
    assert text.index("major") < text.index("minor")
    html = limitations.limitations_html([i.as_dict() for i in items])
    assert "&lt;x&gt;" in html and "Limitations of this data load" in html
    assert limitations.limitations_html([]) == ""


def test_a_store_that_barely_beats_one_state_is_flagged():
    store = {
        "regime_hmm": {
            "fit": {"n_states": 4, "n_days": 151},
            "model_selection": {"bic_preferred_n_states": 2},
            "holdout": {"loglik_per_day": -4.17, "loglik_per_day_one_state": -4.38},
        },
        "diagnostics": {"regime_label_agreement": {"agreement_rate": None}},
        "sick_call_nhpp": {"dispersion": 1.01},
    }
    ids = {x.id for x in limitations.from_store(BASE, store)}
    assert {"hmm_bic_prefers_fewer_states", "hmm_holdout_gain_small", "regime_unvalidated",
            "nhpp_poisson"} <= ids


def test_the_mock_corpus_reports_no_serious_limitation():
    found = limitations.collect(BASE)
    assert not [x for x in found if x.severity == limitations.HIGH], found
