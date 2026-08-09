"""Typed corpus loaders for D1-D12 (spec Sec 6.1, story S0-01).

Every CSV dataset has a declared schema below. A file whose columns do not
match that schema exactly -- missing, extra, or renamed -- raises at load
time, so schema drift is caught here, loudly, rather than silently
corrupting a downstream fit (Sec 4.4.1b: "nothing may hard-code a path" has
a sibling rule that nothing may silently accept a wrong shape either).

Timestamp columns are parsed as Polars Date/Datetime, never left as strings.
D2 rosters carries both `start_utc`/`end_utc` and `start_local`/`end_local`
side by side: legality (Sec 5.4) evaluates duty windows in local time, while
everything else is stored and reasoned about in UTC (Sec 6.2).

`crew_id` is an opaque surrogate key throughout (Law 25, Sec 6.2). A dataset
whose CSV header carries a name or employee-number-shaped column is refused,
not merely undeclared.
"""
from __future__ import annotations

import csv
import gzip
import io
import pathlib
from typing import Any, Literal

import polars as pl

from .. import config

# One of "str" | "int" | "float" | "date" | "datetime" per declared column.
ColumnKind = Literal["str", "int", "float", "date", "datetime"]

# Column names that would identify a specific person. crew_id (a surrogate
# key like "P00001") is fine; anything below is not, in any dataset.
BANNED_COLUMNS = frozenset(
    {
        "name",
        "full_name",
        "first_name",
        "last_name",
        "employee_name",
        "employee_number",
        "employee_no",
        "ssn",
        "sin",
    }
)

# Declared schema per dataset. Keys are the CSV's exact column names; order
# does not matter, but the SET of columns must match the file exactly.
DATASET_SCHEMAS: dict[str, dict[str, ColumnKind]] = {
    "d1_crew_master": {
        "crew_id": "str",
        "base": "str",
        "crew_group": "str",
        "position": "str",
        "fleet": "str",
        "fleet_family": "str",
        "qual_valid_from": "date",
        "qual_valid_to": "date",
        "seniority_number": "int",
        "employment_status": "str",
        "hire_date": "date",
        "termination_date": "date",
    },
    "d2_rosters": {
        "crew_id": "str",
        "base": "str",
        "fleet": "str",
        "position": "str",
        "block_type": "str",
        "start_utc": "datetime",
        "end_utc": "datetime",
        "start_local": "datetime",
        "end_local": "datetime",
        "pairing_id": "str",
        "reserve_call_type": "str",
    },
    "d3_pairings": {
        "pairing_id": "str",
        "base": "str",
        "fleet": "str",
        "position_complement": "str",
        "duty_periods": "int",
        "credit_hours": "float",
        "layover_stations": "str",
        "start_date": "date",
        "days": "int",
    },
    "d3_pairing_legs": {
        "pairing_id": "str",
        "duty_period": "int",
        "leg_seq": "int",
        "flight_no": "str",
        "origin": "str",
        "destination": "str",
        "report_local": "datetime",
        "dep_local": "datetime",
        "arr_local": "datetime",
        "release_local": "datetime",
        "block_hours": "float",
    },
    "d4_absences": {
        "absence_id": "str",
        "crew_id": "str",
        "notification_ts": "datetime",
        "absence_start": "date",
        "absence_end": "date",
        "duration_days": "int",
        "absence_type": "str",
        "affected_pairing_id": "str",
        "base": "str",
        "fleet": "str",
        "position": "str",
    },
    "d5_reserve_callouts": {
        "callout_id": "str",
        "crew_id": "str",
        "call_ts": "datetime",
        "report_ts": "datetime",
        "assigned_pairing_id": "str",
        "outcome": "str",
        "base": "str",
        "fleet": "str",
    },
    "d6_schedule_changes": {
        "change_id": "str",
        "crew_id": "str",
        "change_ts": "datetime",
        "old_block_type": "str",
        "new_block_type": "str",
        "new_pairing_id": "str",
        "reason_code": "str",
        "initiator": "str",
    },
    "d7_pay_register": {
        "crew_id": "str",
        "pay_period": "str",  # "2023-12" -- a bid period, not a calendar date
        "pay_code": "str",
        "amount_cad": "float",
        "duty_date": "date",
        "linked_pairing_id": "str",
    },
    "d8_flight_movements": {
        "flight_no": "str",
        "date": "date",
        "origin": "str",
        "destination": "str",
        "fleet": "str",
        "sched_dep_local": "datetime",
        "sched_arr_local": "datetime",
        "actual_dep_local": "datetime",
        "actual_arr_local": "datetime",
        "delay_minutes": "int",
        "iata_delay_code": "str",
        "cancelled": "int",  # 0/1 flag
        "cancel_reason": "str",
    },
    "d9_station_days": {
        "station": "str",
        "date": "date",
        "disruption_class": "str",
        "season": "str",
        "intensity_multiplier": "float",
    },
    "d10_positioning_invoices": {
        "date": "date",
        "station": "str",
        "cost_type": "str",
        "amount_cad": "float",
        "crew_id": "str",
        "pairing_id": "str",
    },
    "d11_training_sessions": {
        "crew_id": "str",
        "session_type": "str",
        "start_date": "date",
        "end_date": "date",
        "requalification_deadline": "date",
        "reschedule_cost_cad_estimate": "float",
    },
}

DATASET_NAMES: tuple[str, ...] = tuple(sorted(DATASET_SCHEMAS))


class SchemaError(ValueError):
    """A corpus file's columns do not match its declared schema."""


def _peek_columns(path: pathlib.Path) -> list[str]:
    """Read just the header row, without pulling the whole file into memory."""
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", newline="") as fh:
        header = next(csv.reader(fh))
    return header


def _validate_columns(name: str, actual: list[str], schema: dict[str, ColumnKind]) -> None:
    actual_set = set(actual)

    banned = actual_set & BANNED_COLUMNS
    if banned:
        raise SchemaError(
            f"{name}: column(s) {sorted(banned)} look like identifying fields. "
            f"crew_id must stay an opaque surrogate key (Sec 6.2, Law 25) -- "
            f"no name or employee number may appear in any dataset."
        )

    expected = set(schema)
    missing = expected - actual_set
    extra = actual_set - expected
    if missing or extra:
        raise SchemaError(
            f"{name}: schema drift against the declared schema. "
            f"missing={sorted(missing)} extra={sorted(extra)}. "
            f"Declared columns: {sorted(expected)}"
        )


def _read_source(path: pathlib.Path) -> bytes | str:
    """Bytes for .csv.gz (decompressed in memory); the path itself for .csv."""
    if path.name.endswith(".gz"):
        with gzip.open(path, "rb") as fh:
            return fh.read()
    return str(path)


# The corpus's declared wire format -- ISO 8601, minute precision, no seconds.
# Pinned explicitly rather than left to Polars' auto-detection: an
# unformatted `str.to_date` guesses across several patterns and will accept
# an ambiguous string like "01/08/2023" as a plausible-looking wrong date
# instead of raising. A real Air Transat extract in a different format must
# fail loudly here, not parse into a silently incorrect value.
_DATE_FORMAT = "%Y-%m-%d"
_DATETIME_FORMAT = "%Y-%m-%dT%H:%M"


def _column_expr(col: str, kind: ColumnKind) -> pl.Expr:
    c = pl.col(col)
    if kind == "str":
        return c
    if kind == "int":
        return c.cast(pl.Int64)
    if kind == "float":
        return c.cast(pl.Float64)
    if kind == "date":
        return c.str.to_date(_DATE_FORMAT, strict=True)
    if kind == "datetime":
        return c.str.to_datetime(_DATETIME_FORMAT, strict=True)
    raise AssertionError(f"unhandled column kind {kind!r}")  # pragma: no cover


def _cast(name: str, df: pl.DataFrame, schema: dict[str, ColumnKind]) -> pl.DataFrame:
    """Cast one column at a time, strictly.

    `null_values=[""]` already turns a genuinely empty field into null before
    this runs, and a strict `str.to_date`/`str.to_datetime` passes nulls
    through untouched -- so strict parsing only ever raises on a malformed
    NON-empty value. That is exactly the signal this loader exists to
    surface: silently nulling an unparseable date is how a format mismatch
    in a real Air Transat extract turns into a wrong NHPP fit three stories
    downstream, with the loader itself reporting success throughout.
    """
    out = df
    for col, kind in schema.items():
        try:
            out = out.with_columns(_column_expr(col, kind))
        except pl.exceptions.PolarsError as exc:
            raise SchemaError(
                f"{name}.{col}: value(s) do not parse as {kind!r} -- {exc}"
            ) from exc
    return out.select(list(schema))


def load_dataset(cfg: config.BaseConfig, name: str) -> pl.DataFrame:
    """Load one CSV dataset (D1-D11) as a schema-validated, typed DataFrame.

    Raises `KeyError` for an undeclared dataset name, `FileNotFoundError` if
    it is not present under the configured corpus, and `SchemaError` if its
    columns do not match the declared schema exactly.
    """
    if name not in DATASET_SCHEMAS:
        raise KeyError(f"unknown dataset {name!r}. Known datasets: {list(DATASET_NAMES)}")

    path = config.dataset_path(cfg, name)
    if path is None:
        corpus = config.resolve(cfg, "corpus_dir")
        raise FileNotFoundError(f"{name} not found under {corpus}")

    schema = DATASET_SCHEMAS[name]
    columns = _peek_columns(path)
    _validate_columns(name, columns, schema)

    source = _read_source(path)
    raw = pl.read_csv(
        io.BytesIO(source) if isinstance(source, bytes) else source,
        schema_overrides=dict.fromkeys(columns, pl.Utf8),
        null_values=[""],
    )
    return _cast(name, raw, schema)


def load_agreement_rules(cfg: config.BaseConfig) -> dict[str, Any]:
    """D12 -- the collective agreement rules. A document, not tabular data."""
    import yaml

    corpus = config.resolve(cfg, "corpus_dir")
    path = corpus / "d12_agreement_rules.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"D12 agreement rules not found at {path}")
    return yaml.safe_load(path.read_text()) or {}


def load_seasons(cfg: config.BaseConfig) -> dict[str, list[int]]:
    """Season -> month-list mapping from configs/seasons.yaml (Sec 4.5.2).

    The single source of truth for season boundaries: every story that needs
    to bucket a date by season (this one, and later the calibration stories)
    reads it from here rather than restating the month lists.
    """
    import yaml

    path = config.resolve(cfg, "seasons_file")
    if not path.is_file():
        raise FileNotFoundError(f"seasons file not found at {path}")
    raw = yaml.safe_load(path.read_text()) or {}
    return {name: spec["months"] for name, spec in raw.get("seasons", {}).items()}
