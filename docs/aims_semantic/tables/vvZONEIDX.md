# vvZONEIDX  (View)  - Time-zone and daylight-saving-time (DST) rule table, 38 columns

## 1. Purpose & business meaning
`TSC.dbo.vvZONEIDX` is the AIMS "vv" view of the **time-zone index ("zone index") table**. One row = one time zone of one country, identified by (`COUNTRY`, `ZONENO`, `ZONEAREA`): the
**standard UTC offset** (`TIMEDIFF`), the **daylight-saving UTC offset** (`DSTDIFF`) and the **rule that says when DST starts and ends** ("n-th weekday of month at minute-of-day").
Airports point to a row through `vvAirports.COUNTRY / ZONENO / ZONEAREA`; AIMS itself uses it to convert the UTC times it stores everywhere into local station times.
Grain: one row per time zone; 220 rows (2026-11-03); static master data maintained in AIMS "Time Zones". Planner-assist reads it **only through the three functions
`CrewSchedAI.dbo.GetEffectiveOffset`, `GetEffectiveOffset_v1`, `GetEffectiveOffsetUtc`** (no procedure queries it directly).

## 2. Physical facts
- `TSC.dbo.vvZONEIDX`, view; 220 rows; `(COUNTRY, ZONENO, ZONEAREA)` is unique (220 distinct). No view definition / indexes available.
- 108 rows have `DSTON = 1`; 102 rows have `DSTON = 1 AND DSTRULE = 1` (the only rows for which the functions evaluate DST); 105 rows have no DST at all (`DSTON=0, DSTRULE=0`);
  17 of the DST rows are southern-hemisphere (DST period crosses the new year: `TO_MONTH < FROM_MONTH`); 15 rows have a standard offset that is not a whole hour (e.g. +5:30, -3:30, +9:30, +5:45).
- Type lengths: `nchar` in characters (columns.json gives bytes).
- Tiny (220 rows); cross-database cost comes from the functions, not from this view.

## 3. Column dictionary

### 3.1 Key
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| COUNTRY | nchar(2) | yes | Country of the zone = **ICAO location prefix** (same code as `vvAirports.COUNTRY`, `vvCountries.COUNTRY`): `CY`, `K`, `LF`, `Y`... A blank country exists (generic zone 1) | blank-padded; matches `vvAirports.COUNTRY` | `dbo.GetEffectiveOffset.sql:44-47`; profiled |
| ZONENO | tinyint | yes | Zone number inside the country (1..n; 0 never exists as a row) | e.g. Canada `CY`: 1 Newfoundland, 2 Atlantic, 3 Eastern, 4 Central, 5 Mountain, 6 Pacific | same; profiled (DESC_) |
| ZONEAREA | nchar(1) | yes | Sub-area of the zone with different rules: blank = main; `A`, `B` = special variants | e.g. `CY 4 A` Saskatchewan (-360, DSTON 0, DSTRULE 1), `CY 3 A` "Eastern2" (-300, no DST), `K 3 A` Arizona, `K 6 A` Hawaii, `Y 2 A` (same offsets as `Y 2` but DST starts on the first Sunday of October), `Y 2 B` (no DST) | same; profiled |
| DESC_ | nchar(60) | yes | Description of the zone (e.g. "CA 3 (Eastern)", "Newfoundland Time Zone", "RAMADAN") | free text, blank for many European rows | profiled |

### 3.2 Offsets (in minutes from UTC)
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| TIMEDIFF | smallint | yes | **Standard-time UTC offset in minutes** (negative = west of Greenwich) | -600 .. +765; `CY 3` = -300 (EST), `LF 1` = +60, `Y 2` = +600, `CY 1` = -210 (Newfoundland) | `dbo.GetEffectiveOffset.sql` (`vvz.TIMEDIFF / 60.0`) |
| DSTDIFF | smallint | yes | **Daylight-saving-time UTC offset in minutes** - the *total* offset during DST, **not** the one-hour delta (`CY 3` = -240, `LF 1` = +120). If DST does not apply the value is either 0 or equal to TIMEDIFF and is ignored | same units | same (`vvz.DSTDIFF / 60.0`) |

### 3.3 DST switch rules
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| DSTON | tinyint | yes | Zone observes DST (1) or not (0) | 1 = 108 rows, 0 = 112 | profiled |
| DSTRULE | tinyint | yes | Rule-based DST (1 = the nth-weekday rule below is valid and is evaluated) vs 0 = no rule (fixed/other). **The functions evaluate DST only when `DSTON = 1 AND DSTRULE = 1`** (102 rows); the 6 rows with `DSTON=1, DSTRULE=0` (generic `XX 2..5`, a blank-country zone, Iran `OI`) and the 6 with `DSTON=0, DSTRULE=1` (Saskatchewan `CY 4 A`, Indiana `K 1 A`, `LT`, `VH`, `MM 1`, `SB 1`) get standard time all year | 0/1 | `dbo.GetEffectiveOffset.sql` (`WHEN vvz.DSTON = 1 AND vvz.DSTRULE = 1`); profiled |
| FROM_MONTH | tinyint | yes | Month in which DST **starts** | 1..12, 0 = none (3 = March in North America/Europe, 10 = October in southern hemisphere) | same (`FROM_MONTH`) |
| FROM_INMONTH | tinyint | yes | Which occurrence of the weekday in that month: **0 = last, 1 = first, 2 = second, 3 = third, 4 = fourth** | `CY`: 2 (second Sunday of March); Europe: 0 (last Sunday of March) | `dbo.GetEffectiveOffset.sql:77-79`; profiled (0: 66, 1: 19, 2: 21, 3: 2 among DST rows) |
| FROM_WEEKDAY | tinyint | yes | Weekday of DST start: **1 = Monday ... 7 = Sunday** (0 = none). 91 of 102 DST rows use 7 (Sunday); 6 = Saturday (e.g. NZ `NZ`, `LR`), 5 = Friday (`LL` Lebanon), 4 = Thursday (`HE` Egypt, `OJ`) | ISO weekday | `dbo.GetEffectiveOffset.sql:59-62` (comment "1=Monday... 7=Sunday"); profiled |
| FROM_TIME | smallint | yes | **Local clock time of the DST start change, in minutes after midnight** (120 = 02:00, 180 = 03:00). Convention is NOT uniform: see Section 5 | 0..180 (a few rows 0 or 1) | `dbo.GetEffectiveOffset.sql` (`DATEADD(MINUTE, vvz.FROM_TIME, ...)`), `dbo.GetEffectiveOffsetUtc.sql:2-9` |
| TO_MONTH | tinyint | yes | Month in which DST **ends** | 1..12 (11 = November in North America, 10 = October in Europe, 3-4 = southern hemisphere) | same |
| TO_INMONTH | tinyint | yes | Occurrence of the weekday at DST end (0 = last ... 4) | as FROM_INMONTH | same |
| TO_WEEKDAY | tinyint | yes | Weekday of DST end (1 = Monday ... 7 = Sunday) | ISO weekday | same |
| TO_TIME | smallint | yes | Local clock time of the DST end change, in minutes after midnight | 0..180 | same |

### 3.4 Exceptions and special cases (never evaluated by the functions)
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| PRDIDX | tinyint | yes | Period index (links the zone to a period/season definition) | 0 for 143 rows, 1..17 for 77 | profiled; semantics unknown, not used |
| DSTMODE | tinyint | yes | DST mode: 1 only for the `GM` "RAMADAN" row (Morocco: DST suspended during Ramadan) | 0 for 219 rows | profiled; not evaluated (stated in `GetEffectiveOffsetUtc.sql`) |
| FROM_INMONTH2, FROM_WEEKDAY2, FROM_MONTH2 | tinyint | yes | Second DST-start rule | 0 for all rows | profiled |
| TORULEDATE | smallint | yes | Date from which the end rule applies | 0 for all rows | profiled |
| FROMSAMEDAY | smallint | yes | Fixed-date DST start (`GM` row: 45) | 1 row non-zero | profiled |
| TOSAMEDAY | smallint | yes | Fixed-date DST end (`GM` row: 81) | 1 row non-zero | profiled |
| DATE_EXCEPT | tinyint | yes | Date-exception list active (1 only for `MU` zone 1) | 1 row non-zero; not evaluated | profiled; stated in `GetEffectiveOffsetUtc.sql` |
| FROM_UPTO_1_1, FROM_UPTO_1_2, FROM_UPTO_2_1, FROM_UPTO_2_2, FROM_UPTO_3_1, FROM_UPTO_3_2, FROM_UPTO_4_1, FROM_UPTO_4_2 | smallint x8 | yes | Up to four date ranges (from/to) for the exception list | 0 for all rows | profiled |
| RU_CKFLAG, RU_TZDATE, RU_TZTIME, RU_NEWTZTIME | tinyint, smallint x3 | yes | Russia-specific permanent time-zone change (date/time of change and new time) | 0 for all rows | profiled; naming inference |
| FUTURE | varbinary(39) | yes | Reserved bytes | unused | naming inference |

## 4. Keys & relationships
- Natural key: (`COUNTRY`, `ZONENO`, `ZONEAREA`) - unique.
- `vvAirports (COUNTRY, ZONENO, ZONEAREA)` N:1 `vvZONEIDX`: `INNER JOIN TSC.dbo.vvZONEIDX vvz ON vvz.COUNTRY = vva.COUNTRY AND vvz.ZONENO = vva.ZONENO AND vvz.ZONEAREA = vva.ZONEAREA` (`dbo.GetEffectiveOffset.sql:44-47`, `_v1:35-38`, `GetEffectiveOffsetUtc.sql:48-51`). 774 of 779 airports match; 5 (`ZONENO = 0`) do not.
- `vvZONEIDX.COUNTRY = vvCountries.COUNTRY` (a country has one or more zones) - inferred from identical code domain; not used in code.

## 5. Encoding conventions & gotchas
- **Offsets are in minutes**, `TIMEDIFF` standard, `DSTDIFF` *absolute* DST offset (not a delta). The functions return hours = minutes / 60.0 (decimal(12,6): -5.000000, 5.500000...).
- **How DST start/end instants are computed** (all three functions; nth-weekday rule):
  1. first day of the month `FROM_MONTH` of the reference year (`YEAR(@RefDate)`);
  2. weekday of that 1st day: `(DATEDIFF(DAY,'1900-01-01', first) % 7) + 1` -> 1 = Monday ... 7 = Sunday (1900-01-01 was a Monday);
  3. first occurrence of `FROM_WEEKDAY` = first + `(FROM_WEEKDAY - weekday_of_first + 7) % 7` days; last occurrence (INMONTH = 0) = last day of month minus `(weekday_of_last - FROM_WEEKDAY + 7) % 7` days; n-th occurrence (INMONTH = 1..4) = first occurrence + `(INMONTH-1)*7` days (**`GetEffectiveOffset_v1` lacks the "last" branch and is wrong for INMONTH = 0**);
  4. DST start instant = that date + `FROM_TIME` minutes; end analogously with the `TO_*` columns;
  5. northern hemisphere (`start < end`): DST iff `start <= t < end`; southern hemisphere (`start > end`): DST iff `t >= start OR t < end`.
- **FROM_TIME/TO_TIME are not stored in one convention** (documented in `GetEffectiveOffsetUtc.sql:2-9`, verified against IANA 2026): American zones store the local clock reading just *before* the change (02:00 both ways), European-rule zones store either the standard-time or the daylight-time clock reading of the same instant (e.g. 02:00 or 03:00 for the EU 01:00 UTC switch; `LE 1`, `LF 1` and `ED 1` store 180/180, `EB 1`, `EG 1`, `LK 1`, `LP 1` store 120/120). Therefore **FROM_TIME/TO_TIME must not be compared with a UTC time or with midnight**: for UTC inputs use `GetEffectiveOffsetUtc` (which rebuilds the UTC instant as `FROM_TIME - TIMEDIFF` / `TO_TIME - DSTDIFF`, or fixed 01:00 UTC for the European last-Sunday-March/October rule).
- Weekday encoding is 1 = Monday ... 7 = Sunday (not SQL Server's `DATEPART(weekday)`): 91 of 102 rule rows use 7.
- Data staleness observed in the table: Australian rule (`Y 1..3`, `YM`) is encoded as "DST from last Sunday of October (or first for `Y 2 A`) to last Sunday of March", whereas real AEST/AEDT ends first Sunday of April since 2008 -> `GetEffectiveOffset('SYD', ...)` ends DST about one week early and starts it about three weeks late (observed: UTC 2026-04-04 15:59 -> 10.0, actual +11 until 16:00 UTC); Mexico `MM 1..3` still rule DST (abolished 2022; only `MM 4` Quintana Roo = Cancun is correct); `YWG` points to a no-DST zone (`CY 3 A`). Also documented in `GetEffectiveOffsetUtc.sql`: Haiti stores 00:00, Whitehorse still has DST, Morocco Ramadan. These do not affect the Canadian/European/Caribbean airports the operation flies.
- `DSTMODE`, `DATE_EXCEPT`, `FROMSAMEDAY`/`TOSAMEDAY`, `FROM_UPTO_*`, `FROM_*2`, `RU_*` exist but are never evaluated by any procedure/function.
- The effective year is taken from the supplied date-time: a time just after New Year at a southern-hemisphere station uses that year's FROM/TO dates; boundaries across the new year rely on the `OR` branch.

## 6. How the planner-assist procedures use it
Indirectly, only through the offset functions (CrewSchedAI):
- `dbo.R3_Get_Violations_RestTime(_Batch)`: `GetEffectiveOffsetUtc(station, UTC instant of the leg)` for departure/arrival stations and for the crew base (`cq.cwbase`) - local-night rest (LNR), WOCL (02:00-05:59 local acclimatised time), duty-start offset and the recursive acclimatisation ("bio") offset.
- `dbo.R4_Get_Violation_FDP`: two-pass `GetEffectiveOffset(station, local date-time)` (first at midnight of the UTC date, then at UTC + first offset) for dep/arr stations and crew base.
- `rpt.Get_Detailed_Pairing`: `GetEffectiveOffset(DEP, STD)` for `STD_Local`, and the same offset as input to `GetCivilTwilight`.
- `dbo.R0_GetDraftList` does **not** use this table: it uses `dbo.crew_base_timezone` + SQL Server `AT TIME ZONE`.

## 7. Typical query patterns
```sql
-- raw zone row of an airport (inspect rule; do not compute the offset by hand)
SELECT a.AIRPORT, z.TIMEDIFF, z.DSTDIFF, z.DSTON, z.DSTRULE, z.FROM_MONTH, z.FROM_INMONTH, z.FROM_WEEKDAY, z.FROM_TIME,
       z.TO_MONTH, z.TO_INMONTH, z.TO_WEEKDAY, z.TO_TIME, LTRIM(RTRIM(z.DESC_)) AS Zone_Description
FROM TSC.dbo.vvAirports a
JOIN TSC.dbo.vvZONEIDX z ON z.COUNTRY = a.COUNTRY AND z.ZONENO = a.ZONENO AND z.ZONEAREA = a.ZONEAREA
WHERE a.AIRPORT = 'YUL';

-- standard UTC offset in hours of a station (no DST)
SELECT a.AIRPORT, z.TIMEDIFF / 60.0 AS Std_Offset_Hours
FROM TSC.dbo.vvAirports a JOIN TSC.dbo.vvZONEIDX z ON z.COUNTRY = a.COUNTRY AND z.ZONENO = a.ZONENO AND z.ZONEAREA = a.ZONEAREA
WHERE a.AIRPORT IN ('YUL','CDG');

-- actual offset (with DST) at a UTC instant: use the function, not the table
SELECT Effective_UTC_Offset FROM CrewSchedAI.dbo.GetEffectiveOffsetUtc(N'YUL', CAST('2026-11-05T12:00:00' AS DATETIME));
```

## 8. Data profile (measured 2026-11-03)
- 220 zones; `DSTON` 1/0 = 108/112; `DSTON=1 and DSTRULE=1` = 102; 6 `DSTON=1, DSTRULE=0`; 6 `DSTON=0, DSTRULE=1`; 105 neither; `DSTMODE=1` 1 row.
- `TIMEDIFF` range -600..+765 minutes; 15 rows with a non-whole-hour standard offset; 17 southern-hemisphere rule rows; 85 northern rule rows.
- `FROM_INMONTH` among DST rows: 0 -> 66, 1 -> 19, 2 -> 21, 3 -> 2. `FROM_WEEKDAY`: 7 -> 91, 6 -> 8, 4 -> 2, 5 -> 1, 0 -> 6 (non-rule rows).
- Typical rows (zone: TIMEDIFF/DSTDIFF, start -> end, FROM_TIME/TO_TIME): `CY 3`: -300/-240, 2nd Sunday of March -> 1st Sunday of November, 120/120; `LF 1`: +60/+120, last Sunday of March -> last Sunday of October, 180/180; `EG 1`: 0/+60, same rule, 120/120; `Y 2`: +600/+660, last Sunday of October -> last Sunday of March, 120/120; `CY 4 A`: -360/-420 Saskatchewan (`DSTON=0, DSTRULE=1`: no DST); `MM 4`: -300, no DST.
- All the stations of the 2026-10-01..2026-11-30 legs resolve to a zone row.

## 9. Open questions / confidence
- High: key, offsets in minutes, `DSTDIFF` absolute, nth-weekday encoding with `INMONTH = 0 = last`, weekday 1 = Monday ... 7 = Sunday (verified by running the functions and by comparing with known cases YUL/BRU/SYD).
- Medium: exact meaning of `DSTRULE` (inferred as "rule-driven DST" from the function condition and rows where it is 0); inconsistent clock convention in `FROM_TIME`/`TO_TIME` (documented by the function author).
- Unknown: `PRDIDX`, `RU_*`, `FROM_UPTO_*`, `TORULEDATE` semantics; they are not evaluated anywhere.
- Master-data issues (`Y*`, `MM 1-3`, `YWG`) are observations, not business-confirmed.
