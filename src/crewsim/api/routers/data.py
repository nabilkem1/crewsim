"""The D1-D12 corpus: quality gates, profiling, and a paged table view."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

if TYPE_CHECKING:  # pragma: no cover - import cost, not behaviour
    import polars as pl

router = APIRouter(prefix="", tags=["Data Quality"])

# Page sizes for the grid. Presentation, not simulation parameters: `le` exists
# so one request cannot ask the server to serialise 511,664 rows of
# d3_pairing_legs into a single JSON body.
_DEFAULT_PAGE = 50
_MAX_PAGE = 500

# Two datasets held at a time. The corpus is ~130 MB on disk and the largest
# single table (d3_pairing_legs, 511k rows) parses in about 0.15s, so this is a
# paging convenience rather than a necessity -- it keeps clicking through pages
# instant without pinning the whole corpus in the API process.
_DATASET_CACHE_SIZE = 2


def _corpus_fingerprint(name: str) -> tuple[int, int] | None:
    """(mtime_ns, size) of a dataset file, or None when it is absent.

    Part of the cache key so a regenerated corpus invalidates by itself --
    `tools/generate_mock_corpus.py` is run often enough here that a cache
    needing an API restart to notice would be a trap.
    """
    from crewsim import config as cfgmod

    path = cfgmod.dataset_path(cfgmod.load(), name)
    if path is None:
        return None
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=_DATASET_CACHE_SIZE)
def _load_dataset_cached(name: str, _fingerprint: tuple[int, int] | None) -> pl.DataFrame:
    from crewsim import config as cfgmod
    from crewsim.data import loaders

    return loaders.load_dataset(cfgmod.load(), name)


def _cached_dataset(name: str) -> pl.DataFrame:
    """`loaders.load_dataset` with a small, self-invalidating cache."""
    return _load_dataset_cached(name, _corpus_fingerprint(name))


@router.get("/quality-report")
def get_data_quality_report() -> dict[str, Any]:
    """Runs the real Sec6.2 quality gates (crewsim.data.quality) against the
    configured corpus and returns the same check results `crewsim data
    quality-report` prints -- one computation, not a second copy that could
    drift from it. This endpoint used to return a hardcoded overall score of
    95 with four invented check results; that fallback is gone, not relabeled.
    """
    from crewsim.config import load
    from crewsim.data import loaders, quality

    cfg = load()
    try:
        checks = quality.compute_quality_checks(cfg)
    except (FileNotFoundError, KeyError, loaders.SchemaError) as exc:
        raise HTTPException(status_code=503, detail=f"Failed to load datasets: {exc}") from exc

    # web_ui's QualityCheck.status is 'passed' | 'warning' | 'failed' (a CSS/
    # display vocabulary); quality.py's is 'PASS' | 'MARGINAL' | 'FAIL' (the
    # gate vocabulary from spec Sec6.2). Translated here, at the API boundary,
    # rather than picking one vocabulary for both layers to share.
    _STATUS_TO_DISPLAY = {"PASS": "passed", "MARGINAL": "warning", "FAIL": "failed"}

    return {
        "report": {
            "overall_score": quality.quality_score(checks),
            "checks": [
                {"name": c.name, "status": _STATUS_TO_DISPLAY[c.status], "details": c.details}
                for c in checks
            ],
        }
    }


@router.get("/datasets")
def list_datasets() -> dict[str, Any]:
    """The D1-D12 corpus tables, from the schema registry rather than a glob.

    `loaders.DATASET_SCHEMAS` is the single authority on what a dataset is and
    what columns it has, so this reports the declared set and marks each one
    present or missing. A glob would only ever show what happens to be on disk,
    which cannot distinguish "no such dataset" from "dataset not extracted yet"
    -- and a missing file has to render as missing, not as an empty grid.

    No row counts here: that would mean parsing all twelve files (~130 MB) to
    draw a sidebar. The count comes back with the rows, where the file has been
    read anyway.
    """
    from crewsim import config as cfgmod
    from crewsim.data import loaders

    cfg = cfgmod.load()
    tables = [
        {
            "name": name,
            "columns": list(schema),
            "present": cfgmod.dataset_path(cfg, name) is not None,
            "tabular": True,
        }
        for name, schema in sorted(loaders.DATASET_SCHEMAS.items(), key=_dataset_sort_key)
    ]

    # D12 ships in the corpus but is not in DATASET_SCHEMAS: it is the
    # agreement-rules YAML, read by loaders.load_agreement_rules, not a table.
    # Listed rather than dropped -- it is one of "the D's" and its absence from
    # the sidebar would read as an oversight. Presence is decided by asking the
    # loader, so this file does not restate where the corpus keeps it.
    try:
        loaders.load_agreement_rules(cfg)
        rules_present = True
    except (FileNotFoundError, KeyError):
        rules_present = False
    tables.append(
        {
            "name": "d12_agreement_rules",
            "columns": [],
            "present": rules_present,
            "tabular": False,
            "note": "Agreement rules (YAML), not a table -- no grid view.",
        }
    )
    return {"datasets": tables}


def _dataset_sort_key(item: tuple[str, Any]) -> tuple[int, str]:
    """Order d1, d2, d3, ... d11 numerically rather than lexically.

    Plain `sorted()` puts d10 and d11 between d1 and d2, which reads as a bug
    in a sidebar that is meant to mirror the spec's own D-numbering.
    """
    name = item[0]
    digits = "".join(c for c in name.split("_")[0] if c.isdigit())
    return (int(digits) if digits else 0, name)


@router.get("/datasets/{name}/rows")
def get_dataset_rows(
    name: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=_DEFAULT_PAGE, ge=1, le=_MAX_PAGE),
) -> dict[str, Any]:
    """One page of a dataset, typed exactly as every other consumer sees it.

    Goes through `loaders.load_dataset`, which validates the columns against
    the declared schema and casts them -- a second, lighter read path here
    (a bare `scan_csv`, say) could disagree with the engine about a column's
    type, which is the drift this project keeps paying for.
    """
    from crewsim.data import loaders

    try:
        df = _cached_dataset(name)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown dataset {name!r}. Known: {', '.join(loaders.DATASET_NAMES)}",
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except loaders.SchemaError as exc:
        raise HTTPException(status_code=422, detail=f"Schema mismatch: {exc}") from exc

    page = df.slice(offset, limit)
    return {
        "name": name,
        "columns": df.columns,
        "dtypes": [str(d) for d in df.dtypes],
        "total": df.height,
        "offset": offset,
        "limit": limit,
        # write_json, not to_dicts: polars Date/Datetime/Decimal values are not
        # JSON-serialisable by the default encoder, and d4_absences alone has
        # both a Datetime and two Dates. Letting polars serialise keeps the
        # rendered value identical to what polars itself considers the value.
        "rows": json.loads(page.write_json()),
    }


@router.get("/profile-report", response_class=HTMLResponse)
def get_data_profile_report() -> str:
    """Generate and return the S0-02b data profile HTML report."""
    from crewsim.config import load
    from crewsim.data.profile import compute_profiles
    from crewsim.data.profile_html import render

    cfg = load()
    profiles = compute_profiles(cfg)
    return render(profiles, cfg.calibration.overdispersion_threshold)
