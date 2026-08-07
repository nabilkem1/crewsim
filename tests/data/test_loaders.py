"""S0-01 — typed corpus loader for D1-D12.

Acceptance (backlog/mvp/00_phase0_data_foundation.md):
  * reads from paths.corpus_dir, resolved from config, never a literal
  * Polars-backed loader per dataset, with a declared schema; unknown or
    missing columns raise
  * timestamps parsed as UTC and station local
  * crew_id stays an opaque surrogate key -- no name/employee-number column
    anywhere (Law 25)
  * reads both .csv and .csv.gz
"""
from __future__ import annotations

import gzip
import pathlib

import polars as pl
import pytest

from crewsim import config
from crewsim.data import loaders

CORPUS = pathlib.Path(__file__).resolve().parents[2] / "src/crewsim/data/corpus"
_BASE_CFG = config.load()
REAL_CFG = _BASE_CFG.model_copy(
    update={"paths": _BASE_CFG.paths.model_copy(update={"corpus_dir": CORPUS})}
)


def _tmp_cfg(tmp_path: pathlib.Path) -> config.BaseConfig:
    return _BASE_CFG.model_copy(
        update={"paths": _BASE_CFG.paths.model_copy(update={"corpus_dir": tmp_path})}
    )


def _write_csv(path: pathlib.Path, header: list[str], rows: list[list[str]]) -> None:
    lines = [",".join(header)]
    lines += [",".join(row) for row in rows]
    path.write_text("\n".join(lines) + "\n")


# --------------------------------------------------------------------------- real corpus
@pytest.mark.parametrize("name", loaders.DATASET_NAMES)
def test_every_declared_dataset_loads_from_the_real_corpus(name: str) -> None:
    df = loaders.load_dataset(REAL_CFG, name)
    assert df.height > 0
    assert set(df.columns) == set(loaders.DATASET_SCHEMAS[name])


def test_d2_rosters_utc_and_local_differ_by_the_base_offset() -> None:
    """The exact manual check for this story: YUL is UTC-4 in the mock data."""
    df = loaders.load_dataset(REAL_CFG, "d2_rosters")
    yul = df.filter(pl.col("base") == "YUL").head(50)
    assert yul.height > 0
    # Series.all() is vacuously True on an all-null column (ignore_nulls
    # defaults True) -- a total parse failure must not make this pass.
    assert yul["start_utc"].null_count() == 0
    assert yul["start_local"].null_count() == 0
    delta = (yul["start_utc"] - yul["start_local"]).dt.total_hours()
    assert (delta == 4).all()


def test_timestamp_columns_are_typed_not_strings() -> None:
    df = loaders.load_dataset(REAL_CFG, "d2_rosters")
    assert df.schema["start_utc"] == pl.Datetime
    assert df.schema["start_local"] == pl.Datetime


def test_date_only_columns_are_typed_date() -> None:
    df = loaders.load_dataset(REAL_CFG, "d1_crew_master")
    assert df.schema["hire_date"] == pl.Date
    # nullable date column: most crew have no termination_date
    assert df["termination_date"].null_count() > 0


def test_numeric_columns_are_cast() -> None:
    df = loaders.load_dataset(REAL_CFG, "d1_crew_master")
    assert df.schema["seniority_number"] == pl.Int64
    df9 = loaders.load_dataset(REAL_CFG, "d9_station_days")
    assert df9.schema["intensity_multiplier"] == pl.Float64


def test_d12_agreement_rules_load_as_a_document_not_a_table() -> None:
    rules = loaders.load_agreement_rules(REAL_CFG)
    assert rules["pilots"]["agreement"] == "ALPA"
    assert rules["pilots"]["drafting"]["order"] == "tier_then_senior_first"


# --------------------------------------------------------------------------- error paths
def test_unknown_dataset_name_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        loaders.load_dataset(REAL_CFG, "d99_nonexistent")


def test_missing_dataset_file_raises_filenotfounderror(tmp_path: pathlib.Path) -> None:
    with pytest.raises(FileNotFoundError):
        loaders.load_dataset(_tmp_cfg(tmp_path), "d1_crew_master")


def test_missing_column_raises_schemaerror(tmp_path: pathlib.Path) -> None:
    schema = loaders.DATASET_SCHEMAS["d9_station_days"]
    header = [c for c in schema if c != "intensity_multiplier"]  # drop one
    _write_csv(tmp_path / "d9_station_days.csv", header, [["YUL", "2023-08-01", "CALM", "winter_sun"]])
    with pytest.raises(loaders.SchemaError, match="missing"):
        loaders.load_dataset(_tmp_cfg(tmp_path), "d9_station_days")


def test_extra_column_raises_schemaerror(tmp_path: pathlib.Path) -> None:
    schema = loaders.DATASET_SCHEMAS["d9_station_days"]
    header = [*schema, "unexpected_column"]
    _write_csv(
        tmp_path / "d9_station_days.csv",
        header,
        [["YUL", "2023-08-01", "CALM", "winter_sun", "0.5", "surprise"]],
    )
    with pytest.raises(loaders.SchemaError, match="extra"):
        loaders.load_dataset(_tmp_cfg(tmp_path), "d9_station_days")


@pytest.mark.parametrize("banned", sorted(loaders.BANNED_COLUMNS))
def test_a_name_shaped_column_is_refused_not_silently_loaded(
    tmp_path: pathlib.Path, banned: str
) -> None:
    """Law 25 (Sec 6.2): crew_id must stay an opaque surrogate key."""
    schema = dict(loaders.DATASET_SCHEMAS["d1_crew_master"])
    del schema["crew_id"]
    header = [banned, *schema]
    row = ["Jane Doe", *("x" for _ in schema)]
    _write_csv(tmp_path / "d1_crew_master.csv", header, [row])
    with pytest.raises(loaders.SchemaError, match="Law 25"):
        loaders.load_dataset(_tmp_cfg(tmp_path), "d1_crew_master")


def test_reads_gzipped_csv_identically_to_plain(tmp_path: pathlib.Path) -> None:
    plain = CORPUS / "d9_station_days.csv"
    gz_path = tmp_path / "d9_station_days.csv.gz"
    with gzip.open(gz_path, "wb") as fh:
        fh.write(plain.read_bytes())

    expected = loaders.load_dataset(REAL_CFG, "d9_station_days")
    actual = loaders.load_dataset(_tmp_cfg(tmp_path), "d9_station_days")
    assert actual.equals(expected)


def test_path_comes_from_config_not_a_literal(tmp_path: pathlib.Path) -> None:
    """A loader pointed at a different corpus_dir must read THAT corpus."""
    schema = loaders.DATASET_SCHEMAS["d9_station_days"]
    header = list(schema)
    _write_csv(
        tmp_path / "d9_station_days.csv",
        header,
        [["ZZZ", "2099-01-01", "SEVERE", "winter_sun", "3.5"]],
    )
    df = loaders.load_dataset(_tmp_cfg(tmp_path), "d9_station_days")
    assert df.height == 1
    assert df["station"][0] == "ZZZ"


def test_malformed_date_value_raises_rather_than_silently_nulling(
    tmp_path: pathlib.Path,
) -> None:
    """A wrong date FORMAT (not a missing/renamed column) must fail loudly too."""
    schema = loaders.DATASET_SCHEMAS["d9_station_days"]
    header = list(schema)
    _write_csv(
        tmp_path / "d9_station_days.csv",
        header,
        [["YUL", "01/08/2023", "CALM", "winter_sun", "0.5"]],  # DD/MM/YYYY, not ISO
    )
    with pytest.raises(loaders.SchemaError, match=r"d9_station_days\.date"):
        loaders.load_dataset(_tmp_cfg(tmp_path), "d9_station_days")


def test_dataset_path_resolves_relative_to_repo_root_not_cwd() -> None:
    """Same rule as S0-00: a relative corpus_dir resolves from the repo root.

    `PathsConfig`'s own validator does the resolving (config.py), so this
    must construct a fresh `PathsConfig` -- not `model_copy`, which does not
    re-run validation -- with a relative `corpus_dir` to exercise it.
    """
    new_paths = config.PathsConfig(
        corpus_dir="src/crewsim/data/corpus",
        params_dir=_BASE_CFG.paths.params_dir,
        reports_dir=_BASE_CFG.paths.reports_dir,
        seasons_file=_BASE_CFG.paths.seasons_file,
    )
    # The point of this test: the relative string above was actually resolved
    # against the repo root at validation time, not kept as-is and resolved
    # later (e.g. against cwd) by whatever happens to read it.
    assert new_paths.corpus_dir == config.repo_root() / "src/crewsim/data/corpus"
    cfg = _BASE_CFG.model_copy(update={"paths": new_paths})
    df = loaders.load_dataset(cfg, "d9_station_days")
    assert df.height > 0
