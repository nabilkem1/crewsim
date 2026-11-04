# fn_GetEffectiveOffset_v1  (Inline table-valued function, CrewSchedAI)  - Superseded first version of GetEffectiveOffset (no "last weekday of month" support)

## 1. Purpose & business meaning
`CrewSchedAI.dbo.GetEffectiveOffset_v1(@Station_Code, @RefDate)` is the **first iteration of the station UTC-offset function**. It has the same signature and the same output column as `dbo.GetEffectiveOffset` (hours from UTC, DST-aware, for a local
date-time at a station) but computes the DST start/end date with a simpler formula that **cannot express "last <weekday> of the month"** (`INMONTH = 0` in `vvZONEIDX`). Since the European rule (last Sunday of March -> last Sunday of October) and many other
rules use `INMONTH = 0`, the v1 result is **wrong for most European zones** (and every zone with a "last" rule). It was replaced by `dbo.GetEffectiveOffset` (which has the `EOMONTH`-based "last occurrence" branch) and is kept in the database but **no procedure in
the repository references it** (searched all `dbo/*.sql` and `rpt/*.sql`: 0 hits). Treat it as deprecated; do not use it for new work.

## 2. Physical facts
- Database `CrewSchedAI`, schema `dbo`, object type `IF` (inline table-valued function). Source file `dbo.GetEffectiveOffset_v1.sql` (`CREATE OR ALTER FUNCTION`).
- Reads `TSC.dbo.vvAirports` and `TSC.dbo.vvZONEIDX` (cross-database, read-only). Parameter types: `@Station_Code NVARCHAR(3)`, `@RefDate DATETIME`; output `Effective_UTC_Offset numeric(12,6)`.
- Fewer APPLY steps than the current version (two CROSS APPLYs: first-of-month/weekday alignment and start/end datetimes).

## 3. Inputs and output columns
| Item | Type | Meaning | Notes | Evidence |
|---|---|---|---|---|
| @Station_Code | nvarchar(3) | station code (`vvAirports.AIRPORT`) | same restrictions as the current function (3 chars, must have a zone row) | `sys.parameters` |
| @RefDate | datetime | local date-time of the station | year, month, day, minute-of-day used | function body |
| Effective_UTC_Offset (output) | numeric(12,6), nullable | offset from UTC in hours (`TIMEDIFF/60.0` or `DSTDIFF/60.0`) | 0 or 1 row | `sys.columns` |

## 4. Keys & relationships
- Same join as the current function: `vvAirports (AIRPORT = @Station_Code)` INNER JOIN `vvZONEIDX` on `COUNTRY`, `ZONENO`, `ZONEAREA`.
- Zone columns read: `TIMEDIFF`, `DSTDIFF`, `DSTON`, `DSTRULE`, `FROM_MONTH/FROM_INMONTH/FROM_WEEKDAY/FROM_TIME`, `TO_MONTH/TO_INMONTH/TO_WEEKDAY/TO_TIME`.

## 5. Encoding conventions & gotchas
**Difference from `GetEffectiveOffset`**: the DST start/end date is
`DATEADD(DAY, (INMONTH - 1) * 7 + (WEEKDAY - weekday_of_first_of_month + 7) % 7, first_of_month)` + `FROM_TIME/TO_TIME` minutes.
- For `INMONTH` 1..4 this is correct (first..fourth occurrence).
- For **`INMONTH = 0` (last occurrence)** it gives `first occurrence - 7 days` - one week before the first occurrence, i.e. the **wrong date**.
Consequence (executed 2026-11-03):

| Station | RefDate | v1 | current function (correct) |
|---|---|---|---|
| BRU (Belgium, last-Sunday rule) | 2026-03-10 | +2.00 (wrong) | +1.00 |
| BRU | 2026-10-10 | +1.00 (wrong) | +2.00 |
| YUL (2nd/1st-Sunday rule, `INMONTH` 2 and 1) | 2026-03-08 03:00 | -4.00 | -4.00 (same) |

For 2026 the EU rule gives start Feb 22 (first Sunday of March = Mar 1 minus 7 days) and end Sep 27 (first Sunday of October = Oct 4 minus 7), so Europe is shifted by ~5 weeks in spring and ~4 weeks in autumn. North American zones (`INMONTH` 2 and 1) are unaffected.
Other gotchas are the same as the current function: local-clock input, no row for `ZONENO = 0`/unknown/4-char codes, `DSTDIFF` is the absolute DST offset in minutes, stale zone data for `Y*`, `MM 1..3`, `YWG`.

## 6. How the planner-assist procedures use it
- Not used by any procedure or view in the repository. Use `dbo.GetEffectiveOffset` (local date-time input) or `dbo.GetEffectiveOffsetUtc` (UTC input).

## 7. Typical query patterns
```sql
-- do NOT use for European stations; shown only to reproduce the difference
SELECT 'v1' AS Version, Effective_UTC_Offset FROM CrewSchedAI.dbo.GetEffectiveOffset_v1(N'BRU', CAST('2026-10-10' AS DATETIME))
UNION ALL
SELECT 'current', Effective_UTC_Offset FROM CrewSchedAI.dbo.GetEffectiveOffset(N'BRU', CAST('2026-10-10' AS DATETIME));
```

## 8. Data profile (test results)
- BRU 2026-10-10: v1 = 1.00, current = 2.00; BRU 2026-03-10: v1 = 2.00, current = 1.00; YUL 2026-03-08 03:00: both -4.00 (executed 2026-11-03).

## 9. Open questions / confidence
- High: v1 is incorrect for `INMONTH = 0` zones (reproduced); unused in code.
- Unknown: whether other external callers (reports outside this repository) still call `_v1`.
