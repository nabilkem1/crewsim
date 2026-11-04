# fn_GetEffectiveOffset  (Inline table-valued function, CrewSchedAI)  - UTC offset (hours, DST-aware) of a station at a given LOCAL date-time

## 1. Purpose & business meaning
`CrewSchedAI.dbo.GetEffectiveOffset(@Station_Code, @RefDate)` returns the **offset from UTC, in hours, that applies at an airport/station on a given date-time**, i.e. standard offset or daylight-saving offset depending on whether the date-time falls inside the
DST period of the station's time zone. The AIMS time-zone data (`vvAirports` -> `vvZONEIDX`) store UTC offsets in minutes and the DST rule as "n-th weekday of a month at a minute-of-day"; this function turns that rule into a number for a concrete date.
Callers use it to convert the UTC timestamps AIMS stores into **local station time** (`local = UTC + offset hours`), to decide the local calendar day, local-night rest and the WOCL (02:00-05:59 local), and to derive the crew's **biological-clock (acclimatisation)
offset** (see Section 6).

It returns **0 or 1 row**: one row for a known station that has a time-zone row; **no row** (so `OUTER APPLY` gives NULL) for an unknown station, for the 5 stations with `ZONENO = 0` (`ECP`, `YTM`, `BYJ`, `TSF`, `CAX`), and for station codes longer than 3 characters.
It is an **inline** TVF (`SQL_INLINE_TABLE_VALUED_FUNCTION`), so the optimiser expands it into the calling query.

**Which date-time to pass**: the function compares `@RefDate` with the DST change times stored in `vvZONEIDX` (`FROM_TIME`/`TO_TIME`), which are **local wall-clock readings**. Hence `@RefDate` is meant to be a **local** date-time of the station. For a UTC instant use
`dbo.GetEffectiveOffsetUtc` (see `fn_GetEffectiveOffsetUtc.md`). Procedures that must handle a UTC time with this function use a two-pass approximation (offset at midnight of the UTC date, then at UTC + that offset), see Section 6.

## 2. Physical facts
- Database: `CrewSchedAI`; schema `dbo`; object type `IF` (inline table-valued function). Source: `dbo.GetEffectiveOffset.sql` (`CREATE OR ALTER FUNCTION`).
- Reads cross-database: `TSC.dbo.vvAirports` and `TSC.dbo.vvZONEIDX` (read-only, no writes). Needs a deployment where both databases are on the same server and the caller has SELECT on the views.
- Parameters have defaults in the signature (`@Station_Code = 'AGP'`, `@RefDate = '2026-03-04'`) which are leftover test values (`sys.parameters.has_default_value` shows 0 for functions): always pass both explicitly.
- Cost: one `vvAirports` seek by `AIRPORT` + one `vvZONEIDX` join; many `CROSS APPLY/OUTER APPLY` calls per leg row in R3/R4. Its use with midnight of the leg day gave a wrong offset for 174 of 40,378 departures in 2026 (R3-15 item 8), which is why `GetEffectiveOffsetUtc` was created.

## 3. Inputs and output columns
### Inputs
| Parameter | Type | Meaning | Encoding / allowed values | Evidence |
|---|---|---|---|---|
| @Station_Code | nvarchar(3) | Station code of the airport (IATA/AIMS code = `vvAirports.AIRPORT`, 3 letters, e.g. `YUL`, `CDG`). Also used for a **crew base** (crew bases are station codes) | upper-case 3-letter code; **4-character codes (`CEP8`, `FCO1`, `FCO2`) cannot be used** (parameter is nvarchar(3)); a 4-letter ICAO code finds nothing | `sys.parameters`; `dbo.R3...sql:303` |
| @RefDate | datetime | Date-time at which the offset is wanted - treated as the **local** clock reading of the station. Only the calendar year, month, day and minute-of-day matter | e.g. `2026-03-08T03:00:00`; the year defines which DST dates are used (`YEAR(@RefDate)`) | function body |

### Output (single column)
| Column | Type | Null | Meaning | Encoding / units | Evidence |
|---|---|---|---|---|---|
| Effective_UTC_Offset | numeric(12,6) | yes | Offset of local time from UTC **in hours** (decimal): local time = UTC + this value. `-5.000000` for Eastern standard, `-4` Eastern daylight, `+2` Paris summer, `+5.5` India, `-3.5` Newfoundland winter | `TIMEDIFF/60.0` (standard) or `DSTDIFF/60.0` (daylight) of the zone | `sys.columns` (numeric(12,6)); tested |

## 4. Keys & relationships
- Reads `TSC.dbo.vvAirports vva` filtered `WHERE vva.AIRPORT = @Station_Code`, joined to `TSC.dbo.vvZONEIDX vvz ON vvz.COUNTRY = vva.COUNTRY AND vvz.ZONENO = vva.ZONENO AND vvz.ZONEAREA = vva.ZONEAREA` (inner join; N:1; no row if no zone).
- Zone columns used: `TIMEDIFF`, `DSTDIFF`, `DSTON`, `DSTRULE`, `FROM_MONTH`, `FROM_INMONTH`, `FROM_WEEKDAY`, `FROM_TIME`, `TO_MONTH`, `TO_INMONTH`, `TO_WEEKDAY`, `TO_TIME`.
- Not evaluated: `DSTMODE` (Ramadan), `DATE_EXCEPT`, `FROMSAMEDAY`/`TOSAMEDAY`, `FROM_UPTO_*`, `NEWZONENO`/`VALIDUNTIL` (future zone change), `RU_*`.

## 5. Encoding conventions & gotchas
**How the offset is computed (algorithm of the body, `dbo.GetEffectiveOffset.sql`):**
1. Find the station's zone row. If `DSTON = 1 AND DSTRULE = 1` the zone has an evaluable DST rule; otherwise the offset is always `TIMEDIFF/60.0` (this covers non-DST zones and the 12 zones where `DSTON` and `DSTRULE` disagree).
2. For the year of `@RefDate` build `FromMonthFirst` = 1st of `FROM_MONTH`, `FromMonthLast` = `EOMONTH`, and likewise `ToMonthFirst/Last` for `TO_MONTH`.
3. Weekday numbers 1 = Monday ... 7 = Sunday: `(DATEDIFF(DAY,'1900-01-01', d) % 7) + 1` (1900-01-01 was a Monday).
4. First occurrence of the target weekday in the month = first + `(WEEKDAY - weekday(first) + 7) % 7` days; last occurrence = last day - `(weekday(last) - WEEKDAY + 7) % 7` days.
5. Apply `INMONTH`: **0 = last occurrence**, 1..4 = first..fourth (`first occurrence + (INMONTH-1)*7` days). Then add `FROM_TIME` / `TO_TIME` minutes to get `DST_Start_DT` and `DST_End_DT` (local clock).
6. Northern hemisphere (`DST_Start_DT < DST_End_DT`): DST iff `@RefDate >= start AND @RefDate < end`. Southern hemisphere (start > end): DST iff `@RefDate >= start OR @RefDate < end`.
7. Return `DSTDIFF/60.0` inside DST (**`DSTDIFF` is the full DST offset in minutes, not a delta**), else `TIMEDIFF/60.0`.

Gotchas:
- **Local vs UTC input.** Passing a UTC instant misses the change by the offset (e.g. on a DST-change day the result is wrong for a few hours). `GetEffectiveOffsetUtc` exists for UTC inputs. Passing **midnight of the day** gives the pre-change offset all day on the change day (the R3 bug "174 of 40,378 departures" fixed in R3-15 item 8).
- **Stored change times are not in one convention** (American zones: clock before the change; European-rule zones: standard or daylight reading, e.g. 03:00 vs 02:00): the function treats `FROM_TIME/TO_TIME` as the local clock at which `@RefDate` flips. Wrong by up to 1 hour around the change for some European zones.
- **No row => NULL.** `ZONENO = 0` stations, unknown codes and 4-char codes return nothing; callers must `ISNULL` the offset (R3/R4 do for crew base: `ISNULL(duty_start_UTC_OFFSET, HomeBase_UTC_OFFSET)`).
- **Stale rules in master data**: `Y*` (Australia), `MM 1..3` (Mexico) and `YWG` (Winnipeg mapped to a no-DST zone) give wrong offsets; see `vvZONEIDX.md`. For the airports the operation flies (Canada, USA, Europe, Caribbean) the results were verified.
- Zones without DST have `FROM_MONTH = TO_MONTH = 0` (e.g. `MD 1` for `PUJ`); `DATEFROMPARTS(year, 0, 1)` would be invalid, but the call for `PUJ` ran without error and returned -4.00 (the CASE is only evaluated for rows with `DSTON = 1 AND DSTRULE = 1`; relies on the optimiser not evaluating the APPLY columns eagerly - not guaranteed by the language).
- Result is `numeric(12,6)`; multiply by 60 and `ROUND` before `DATEADD(MINUTE, ...)` (the procedures do `CAST(ROUND(offset * 60, 0) AS INT)`).
- The default parameter values in the DDL are test leftovers.

**Verified behaviour (executed 2026-11-03, `SELECT Effective_UTC_Offset FROM dbo.GetEffectiveOffset(...)`):**
| Station | RefDate (local) | Result |
|---|---|---|
| YUL | 2026-01-01 | -5.00 |
| YUL | 2026-07-01 | -4.00 |
| YUL | 2026-03-08 00:00 | -5.00 |
| YUL | 2026-03-08 01:59 | -5.00 |
| YUL | 2026-03-08 03:00 | -4.00 (DST start is 2nd Sunday of March, 02:00 stored) |
| YVR | 2026-07-01 | -7.00 |
| CDG | 2026-07-01 | +2.00 |
| BRU | 2026-03-10 / 2026-10-10 | +1.00 / +2.00 |
| BOM | 2026-07-01 | +5.50 |
| YYT | 2026-01-01 / 2026-07-01 | -3.50 / -2.50 |
| SYD | 2026-01-01 / 2026-07-01 | +11.00 / +10.00 |
| YWG | 2026-01-01 / 2026-07-01 | -5.00 / -5.00 (master-data issue) |
| RUN | 2026-07-01 | +2.00 (master-data issue: blank-country zone) |
| ECP (`ZONENO = 0`), ZZZ (unknown) | any | no row (NULL when OUTER APPLY) |

## 6. How the planner-assist procedures use it
- `dbo.R4_Get_Violation_FDP` (`:404-408, :416-417, :426-427, :715-716`): **two-pass** pattern to apply a local-clock function to UTC data:
  `OUTER APPLY dbo.GetEffectiveOffset(station, CAST(CAST(utc AS DATE) AS DATETIME)) AS o0` (offset at midnight of the UTC date) then `OUTER APPLY dbo.GetEffectiveOffset(station, DATEADD(MINUTE, CAST(ROUND(o0.Effective_UTC_Offset*60,0) AS INT), utc)) AS o1` (offset at the approximate local time); `o1` is the offset used for departure station, arrival station and crew base (`cq.cwbase`). The offsets feed the duty-start/duty-end UTC offsets, the crew **bio (acclimatisation) offset** and WOCL/local-night calculations of the FDP rule.
- `rpt.Get_Detailed_Pairing` (`:313`): `CrewSchedAI.dbo.GetEffectiveOffset(DEP, DATEADD(MINUTE, STD, DATEADD(DAY, DAY, @BaseDate)))` - **passes the UTC STD** (not local) to give `UTC_Offset`, `STD_Local` and `STD_Time_Local`; accurate except on DST-change days. The same offset is the 4th parameter of `GetCivilTwilight`.
- `dbo.R3_Get_Violations_RestTime(_Batch)` used this function until R3-15 item 8, now `GetEffectiveOffsetUtc` (see `fn_GetEffectiveOffsetUtc.md`).
- **Bio-clock offset (context, downstream of this function)**: R3/R4 keep a recursive `Crew_bio_UTC_OFFSET` per duty. Start: the crew base offset (`HomeBase_UTC_OFFSET`) if the rest before the first duty >= 5,760 min (96 h) else the duty-start station offset. At each next duty: (a) if the duty is flagged manually acclimatised and cumulative rest >= 1 day at a different station, the bio offset moves toward the duty-start offset by `FLOOR(rest_days)` hours, capped at the target; (b) otherwise it jumps to the duty-start station offset when the station changed and cumulative rest >= 72 h (offset difference < 4 h) or >= 96 h (difference >= 4 h) (state `Acclimatized = 1`); (c) else it stays. `Acclim_begin/end = duty time + ROUND(bio_offset*60) minutes` are the "acclimatised local" times used for WOCL and FDP tables. All offsets come from `GetEffectiveOffset*`.

## 7. Typical query patterns
```sql
-- offset of a station at a local date-time (hours)
SELECT Effective_UTC_Offset FROM CrewSchedAI.dbo.GetEffectiveOffset(N'YUL', CAST('2026-07-01T12:00:00' AS DATETIME));

-- convert a UTC time to the local time of a station (use GetEffectiveOffsetUtc for a UTC input; this form is the two-pass approximation used by R4)
DECLARE @utc DATETIME = '2026-11-05T14:30:00';
SELECT DATEADD(MINUTE, CAST(ROUND(o1.Effective_UTC_Offset * 60, 0) AS INT), @utc) AS Local_Time
FROM (SELECT 1 AS x) d
OUTER APPLY CrewSchedAI.dbo.GetEffectiveOffset(N'CDG', CAST(CAST(@utc AS DATE) AS DATETIME)) AS o0
OUTER APPLY CrewSchedAI.dbo.GetEffectiveOffset(N'CDG', DATEADD(MINUTE, CAST(ROUND(o0.Effective_UTC_Offset * 60, 0) AS INT), @utc)) AS o1;

-- per-leg local departure (always LEFT/OUTER APPLY: unknown stations return no row)
SELECT lm.DEP, dep_tz.Effective_UTC_Offset
FROM TSC.dbo.LEGMAIN lm
OUTER APPLY CrewSchedAI.dbo.GetEffectiveOffset(lm.DEP, DATEADD(MINUTE, lm.STD, DATEADD(DAY, lm.DAY, CAST('1980-01-01' AS DATETIME)))) AS dep_tz
WHERE lm.DAY = DATEDIFF(DAY,'1980-01-01','2026-11-05') AND lm.CANCELLED = 0;
```

## 8. Data profile (test results)
- Executed 2026-11-03 against live data: see the table in Section 5. 102 of 220 zones have an evaluable DST rule (`DSTON = 1 AND DSTRULE = 1`); 774 of 779 stations resolve to a zone (5 with `ZONENO = 0` do not).

## 9. Open questions / confidence
- High: algorithm (read from the body and confirmed by execution); local-time input semantics; no-row behaviour.
- Medium: no error was observed for non-DST zones (month 0), but this depends on lazy evaluation of the APPLY columns by the optimiser.
- `dbo.GetEffectiveOffset_v1` and `dbo.GetEffectiveOffsetUtc` are the sibling versions (no "last occurrence" branch / UTC input).
