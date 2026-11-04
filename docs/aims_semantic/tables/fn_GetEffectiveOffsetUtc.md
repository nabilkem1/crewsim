# fn_GetEffectiveOffsetUtc  (Inline table-valued function, CrewSchedAI)  - UTC offset (hours, DST-aware) of a station at a given UTC instant

## 1. Purpose & business meaning
`CrewSchedAI.dbo.GetEffectiveOffsetUtc(@Station_Code, @UtcInstant)` returns the **offset from UTC, in hours, in force at a station at a UTC instant** (R3-15 item 8). It is the version of the offset function for **UTC inputs**, which is what the
rest-time rule engine (R3) works with: all AIMS times (`LEGMAIN.STD/STA`, `ROSTER` times, `LEGTIMES`) are UTC minutes since the day start.

Why it exists: `dbo.GetEffectiveOffset` compares its date-time with the DST change time stored in the AIMS zone table (`vvZONEIDX.FROM_TIME/TO_TIME`), which are **local clock readings** and are **not stored in one convention** (checked against the IANA tz database, 2026):
the American zones store the clock reading just *before* the change; European-rule zones store either the standard or the daylight reading of the same instant (Belgium 02:00/02:00, Germany 03:00/03:00, UK 02:00/02:00). R3 previously asked at midnight of the leg day, so a leg after
the DST change time of its day got the wrong offset (**174 of 40,378 departures in 2026**). This function instead rebuilds the **UTC instant of each change** and compares the UTC input with it, so the answer is right on the change day too.

Returns 0 or 1 row (no row for unknown station, `ZONENO = 0` station, or station codes longer than 3 characters), like the other versions. Inline TVF.

## 2. Physical facts
- Database `CrewSchedAI`, schema `dbo`, type `IF` (inline TVF); source `dbo.GetEffectiveOffsetUtc.sql`. Must be deployed **before** `dbo.R3_Get_Violations_RestTime` and `_Batch`.
- Reads `TSC.dbo.vvAirports` and `TSC.dbo.vvZONEIDX` (cross-database, read-only). Five CROSS APPLY stages (months/days -> weekdays -> occurrences -> change day -> UTC instants).
- Verified for the 29 DST zones of the 2026 flights against IANA (header comment, `architecture/bug-r3.md` R3-15 item 8).

## 3. Inputs and output columns
| Item | Type | Meaning | Notes | Evidence |
|---|---|---|---|---|
| @Station_Code | nvarchar(3) | station code (`vvAirports.AIRPORT`) or crew base | 3 chars; `CEP8`, `FCO1`, `FCO2` cannot be passed | `sys.parameters` |
| @UtcInstant | datetime | **a UTC date-time** (NOT a local one) | e.g. `DATEADD(MINUTE, lm.STD, DATEADD(DAY, lm.DAY, '1980-01-01'))` | function header |
| Effective_UTC_Offset (output) | numeric(12,6), nullable | offset from UTC in hours: local = UTC + offset | `TIMEDIFF/60.0` or `DSTDIFF/60.0`; `-5`, `-4`, `+1`, `+2`, `+5.5`... | `sys.columns` |

## 4. Keys & relationships
- `vvAirports (AIRPORT = @Station_Code)` INNER JOIN `vvZONEIDX` ON `COUNTRY`, `ZONENO`, `ZONEAREA` (as the other versions) - zone columns `TIMEDIFF`, `DSTDIFF`, `DSTON`, `DSTRULE`, `FROM_*`, `TO_*`.
- Not evaluated: `DATE_EXCEPT`, `DSTMODE`, `FROMSAMEDAY`/`TOSAMEDAY`, `NEWZONE*` (as in `GetEffectiveOffset`).

## 5. Encoding conventions & gotchas
**Algorithm** (`dbo.GetEffectiveOffsetUtc.sql`):
1. DST is evaluated only if `DSTON = 1 AND DSTRULE = 1`; otherwise `TIMEDIFF/60.0`.
2. The **day** of the DST start and end is computed exactly as in `GetEffectiveOffset`: n-th weekday of the month (`INMONTH`: 0 = last, 1..4), weekday 1 = Monday ... 7 = Sunday, from `YEAR(@UtcInstant)`.
3. The **UTC instant of the change**:
   - **European rule** (`FROM_MONTH = 3, FROM_INMONTH = 0, FROM_WEEKDAY = 7` and `TO_MONTH = 10, TO_INMONTH = 0, TO_WEEKDAY = 7`, i.e. last Sunday of March to last Sunday of October): **01:00 UTC** for both start and end, for every country using it (the stored clock times differ by country).
   - **Every other zone**: the stored time is the local clock just before the change, so `DST_Start_UTC = start day + (FROM_TIME - TIMEDIFF) minutes` (the standard-time clock) and `DST_End_UTC = end day + (TO_TIME - DSTDIFF) minutes` (the daylight clock).
4. Northern hemisphere (`start < end`): DST iff `@UtcInstant >= start_UTC AND < end_UTC`; southern (`start > end`): DST iff `>= start_UTC OR < end_UTC`.
5. Result: `DSTDIFF/60.0` in DST, else `TIMEDIFF/60.0`.

Gotchas:
- **Pass UTC** here. For a local date-time use `GetEffectiveOffset`.
- Known data issues the function **does not hide** (header): Haiti (`PAP`) stores 00:00 for the change, Mexico (`SJD`) still has DST, Whitehorse (`YXY`) no DST since 2020, Morocco (`CMN`, `RAK`) Ramadan. `DATE_EXCEPT` and `DSTMODE` are not evaluated.
- Stale Australian rule (last Sunday of March/October in the zone table; `SYD` returns +10 already at 2026-04-04 15:59 UTC although real AEDT (+11) lasts until 16:00 UTC), and `YWG` mapped to a no-DST zone (-5 all year): master-data issues, not function bugs.
- Station without zone => no row => `NULL` in `OUTER APPLY` (R3 then uses `ISNULL` fallbacks).
- The effective year is `YEAR(@UtcInstant)`; near New Year the southern-hemisphere `OR` branch handles the wrap.
- Numeric result: multiply by 60 and `ROUND` before `DATEADD(MINUTE, ...)`.

**Verified behaviour (executed 2026-11-03):**
| Station | UTC instant | Result | Explanation |
|---|---|---|---|
| YUL | 2026-03-08 06:59 | -5.00 | DST starts 2nd Sunday of March 02:00 EST = 07:00 UTC |
| YUL | 2026-03-08 07:00 | -4.00 | |
| YUL | 2026-11-01 05:59 | -4.00 | DST ends 1st Sunday of November 02:00 EDT = 06:00 UTC |
| YUL | 2026-11-01 06:00 | -5.00 | |
| BRU | 2026-03-29 00:59 | +1.00 | EU rule: last Sunday of March 01:00 UTC |
| BRU | 2026-03-29 01:00 | +2.00 | |
| SYD | 2026-04-04 15:59 / 16:00 | +10.00 / +10.00 | stale Australian rule (see above) |
| ZZZ (unknown) | any | no row | |

## 6. How the planner-assist procedures use it
- `dbo.R3_Get_Violations_RestTime` (`:303-307, :554`) and `dbo.R3_Get_Violations_RestTime_Batch` (`:286-289, :502`): `OUTER APPLY dbo.GetEffectiveOffsetUtc(r.LEG_DEP, <UTC departure instant>) AS dep_tz` and `... (ISNULL(lm.ARR, r.LEG_DEP), <UTC arrival instant>) AS arr_tz`; for ground activities (`LEG_FLT < 0`) the instants are `GRDDUTYBEG/GRDDUTYEND`; for the crew base the call is `GetEffectiveOffsetUtc(cq.cwbase, duty_start_with_Report)` -> `HomeBase_UTC_OFFSET`.
  Used for: `DEP_STATION_UTC_OFFSET` / `ARR_STATION_UTC_OFFSET` of every leg; duty start/end UTC offsets (`duty_start_UTC_OFFSET`, `duty_end_UTC_OFFSET`); the **recursive biological-clock offset** `Crew_bio_UTC_OFFSET` (`Recursive_Bio_Offset`), `Acclim_begin`/`Acclim_end` (= UTC time + `ROUND(offset*60)` minutes), **WOCL** (02:00-05:59 acclimatised) and **local night rest (LNR)** counts, and the early/late-start tests of the rest-time rules (R3), incl. FD-CAR-2557 consecutive-WOCL-FDP checks (pilots).
- Bio-clock rules in R3/R4 that consume these offsets: start with the crew-base offset if the rest before the first duty >= 5,760 min (96 h), else the duty-start station offset; moving to a new station the bio offset jumps to the station offset after 72 h of cumulative rest when the offset difference is < 4 h, or after 96 h when it is >= 4 h; with a manual acclimatisation flag it shifts toward the target by `FLOOR(rest_days)` hours (capped at the target). (R3: `dbo.R3_Get_Violations_RestTime.sql:573-606`.)
- `dbo.R4_Get_Violation_FDP` still uses the local-time `GetEffectiveOffset` with a two-pass approximation; `rpt.Get_Detailed_Pairing` uses `GetEffectiveOffset`.

## 7. Typical query patterns
```sql
-- offset at a UTC instant
SELECT Effective_UTC_Offset FROM CrewSchedAI.dbo.GetEffectiveOffsetUtc(N'YUL', CAST('2026-11-05T14:30:00' AS DATETIME));

-- local departure time of the legs of a day (UTC minutes since midnight in LEGMAIN.STD)
SELECT lm.FLT, lm.DEP,
       DATEADD(MINUTE, lm.STD, DATEADD(DAY, lm.DAY, CAST('1980-01-01' AS DATETIME)))                                          AS STD_UTC,
       DATEADD(MINUTE, CAST(ROUND(o.Effective_UTC_Offset * 60, 0) AS INT), DATEADD(MINUTE, lm.STD, DATEADD(DAY, lm.DAY, CAST('1980-01-01' AS DATETIME)))) AS STD_Local
FROM TSC.dbo.LEGMAIN lm
OUTER APPLY CrewSchedAI.dbo.GetEffectiveOffsetUtc(lm.DEP, DATEADD(MINUTE, lm.STD, DATEADD(DAY, lm.DAY, CAST('1980-01-01' AS DATETIME)))) AS o
WHERE lm.DAY = DATEDIFF(DAY,'1980-01-01','2026-11-05') AND lm.CANCELLED = 0;
```

## 8. Data profile (test results)
- Verified instants listed in Section 5; the header states a check against IANA for the 29 DST zones of the 2026 flights.
- The R3 comment counts 40,378 departures in 2026 of which 174 had the wrong offset under the old midnight-based call.

## 9. Open questions / confidence
- High: algorithm, UTC semantics, European 01:00 UTC rule (confirmed by BRU/YUL tests).
- Medium: correctness for non-European zones relies on the stored `FROM_TIME/TO_TIME` being the clock before the change (the author's IANA check for 29 zones; not re-verified here for zones outside the 2026 operation).
- Master-data defects (Australia, Mexico, Winnipeg, Haiti, Whitehorse, Morocco) remain visible by design.
