"""Dated pairing ids (IMP-518).

D3 names a rotation by its code AND start date (`G0025_20260601`): one code
covers several different trips. Other datasets do not always say so. A real
extract's D4 and D5 quote the bare code (`G0025`), and its D6 sometimes spells
the date another way (`TS18@2026-05-18`). Matched literally, every such row is
an orphan; matched by code plus the row's own date, most are not.

Resolution is reported separately from exact matching and never silently
folded into it: `data.allow_resolved_ids` decides whether a gate accepts it.
A bare code that does not land on a known dated id on that day is left
unresolved -- it is never guessed to the nearest date.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import polars as pl

from .. import config

#: How a row's id was matched.
EXACT = "exact"
SPELLING = "other_spelling"
CODE_AND_DATE = "code_and_date"


def resolve_pairing_ids(
    ids: pl.Series,
    days: pl.Series | None,
    known: Iterable[str],
    forms: list[config.PairingIdForm],
) -> pl.DataFrame:
    """For each id: the known dated id it resolves to (null if none) and how.

    `days` is the date to pair a bare code with (the absence start, the call
    date, ...). It may be None or null per row: such rows resolve only by an
    exact match or another spelling.
    """
    known_series = pl.Series("known", sorted(set(known)), dtype=pl.String)
    canon = forms[0]
    n = ids.len()
    day = days.cast(pl.Date) if days is not None else pl.Series("day", [None] * n, dtype=pl.Date)
    df = pl.DataFrame({"id": ids.cast(pl.String), "day": day})

    ident = pl.col("id")
    exact = ident.is_in(known_series.implode())

    def canonical(code: pl.Expr, d: pl.Expr) -> pl.Expr:
        return code + pl.lit(canon.separator) + d.dt.strftime(canon.date_format)

    spellings: list[tuple[pl.Expr, pl.Expr]] = []
    for form in forms:
        parts = ident.str.split_exact(form.separator, 1)
        code = parts.struct.field("field_0")
        parsed = parts.struct.field("field_1").str.to_date(form.date_format, strict=False)
        candidate = canonical(code, parsed)
        spellings.append((parsed.is_not_null() & candidate.is_in(known_series.implode()), candidate))

    bare = canonical(ident, pl.col("day"))
    bare_ok = pl.col("day").is_not_null() & bare.is_in(known_series.implode())

    resolved = pl.coalesce(
        pl.when(exact).then(ident),
        *[pl.when(ok).then(cand) for ok, cand in spellings],
        pl.when(bare_ok).then(bare),
    )
    how = pl.coalesce(
        pl.when(exact).then(pl.lit(EXACT)),
        *[pl.when(ok).then(pl.lit(SPELLING)) for ok, _ in spellings],
        pl.when(bare_ok).then(pl.lit(CODE_AND_DATE)),
    )
    return df.select(resolved.alias("resolved"), how.alias("how"))


def linkage_rates(
    frame: pl.DataFrame,
    id_col: str,
    day_expr: pl.Expr | None,
    known: Iterable[str],
    forms: list[config.PairingIdForm],
) -> dict[str, Any]:
    """Exact and resolvable link rates for the non-empty ids of `frame[id_col]`.

    `total` counts rows with an id; `exact` those that match a known id as
    written; `resolvable` those that match once resolved (exact included).
    """
    has_id = frame.filter(pl.col(id_col).is_not_null() & (pl.col(id_col) != ""))
    total = has_id.height
    if total == 0:
        return {"total": 0, "exact": 0, "resolvable": 0, "exact_rate": 1.0, "resolvable_rate": 1.0}
    days = has_id.select(day_expr.alias("day"))["day"] if day_expr is not None else None
    res = resolve_pairing_ids(has_id[id_col], days, known, forms)
    exact = res.filter(pl.col("how") == EXACT).height
    resolvable = res.filter(pl.col("resolved").is_not_null()).height
    return {
        "total": total, "exact": exact, "resolvable": resolvable,
        "exact_rate": exact / total, "resolvable_rate": resolvable / total,
    }
