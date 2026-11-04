# fn_GetCivilTwilight  (Multi-statement table-valued function, CrewSchedAI)  - Civil twilight start/end (local clock) at a latitude/longitude on a date

## 1. Purpose & business meaning
`CrewSchedAI.dbo.GetCivilTwilight(@LatStr, @LonStr, @CalcDate, @ManualOffset)` computes the **times of civil twilight** at a geographic point on a given date: `Civil_Twilight_Start` = the **morning** time at which the sun is 6 degrees below the horizon
(zenith 96 deg; "civil dawn"), `Civil_Twilight_End` = the **evening** time at which it returns to 6 degrees below the horizon ("civil dusk"). The result is shifted by a **UTC offset in hours** (`@ManualOffset`) so the returned times are on the local clock of that offset.
The inputs are the airport coordinates exactly as AIMS stores them (`vvAirports.LATITUDE` / `LONGITUD` text, e.g. `N45280500`, `W073442900`), so the function can be applied directly to a station.

Business use: `rpt.Get_Detailed_Pairing` calls it for the **departure airport of every flight leg** to output `Twilight_Start` / `Twilight_End` and the flag `Is_Overnight` (local scheduled departure time later than the evening civil twilight and no night-stop at the arrival station),
used by the custom-rule engine (rules about night/day flying, e.g. "departure after civil twilight"). The "offset" it applies is the **plain station UTC offset** (from `GetEffectiveOffset`), not the crew's biological-clock (acclimatised) offset; the crew bio-clock is a different computation in R3/R4
(see `fn_GetEffectiveOffsetUtc.md` Section 6).

**Type note**: despite being listed with the "inline" offset functions, this one is a **multi-statement TVF** (`sys.objects.type = 'TF'`, `RETURNS @Output TABLE ... BEGIN ... RETURN END`). It returns exactly one row per call and is evaluated row by row (the optimiser assumes a fixed row estimate).

## 2. Physical facts
- Database `CrewSchedAI`, schema `dbo`, type `TF` (SQL_TABLE_VALUED_FUNCTION, multi-statement). Source `dbo.GetCivilTwilight.sql` (`CREATE OR ALTER FUNCTION`). Pure computation: **no table access** (it reads no tables).
- Deterministic mathematics (NOAA-style solar algorithm, floating point `FLOAT`), always exactly one output row.
- Called per row via `CROSS APPLY`, so cost is per-leg scalar maths (no I/O) - acceptable but not set-based.

## 3. Inputs and output columns
### Inputs
| Parameter | Type | Meaning | Encoding / allowed values | Evidence |
|---|---|---|---|---|
| @LatStr | varchar(20) | Latitude in AIMS text form `H DD MM SSss`: hemisphere letter `N`/`S` (lower-case `s` accepted) + 2 digits degrees + 2 digits minutes + seconds in hundredths | `N45280500` = 45 deg 28 min 05.00 s N; parsed as `DD + MM/60 + (SSss/100)/3600`, negated for `S` | `dbo.GetCivilTwilight.sql:38-41` |
| @LonStr | varchar(20) | Longitude `H DDD MM SSss`: `E`/`W` (lower-case `w` accepted) + 3 digits + 2 + hundredths of seconds | `W073442900` = 73 deg 44 min 29.00 s W, negative for `W` | `:44-47` |
| @CalcDate | datetime | Date for which twilight is computed. **Only the date part is used for the astronomy and for the output `Date`, but the time-of-day of the argument is added to the result (see gotcha)** | pass **midnight** (`CAST(d AS DATE)`) | `:50`, `:166-171` |
| @ManualOffset | float, default NULL | Offset in **hours** added to the UTC result to get local time; NULL = 0 (result in UTC). Reported back as `Applied_Offset` | e.g. `-5`, `-4`, `+1`, `+5.5` | `:7, :166-173` |

### Output (one row)
| Column | Type | Null | Meaning | Encoding / values | Evidence |
|---|---|---|---|---|---|
| Date | date | yes | `CAST(@CalcDate AS DATE)` | | `:154-175` |
| Civil_Twilight_Start | time(0) | yes | Morning civil dawn, local clock (UTC + offset), whole seconds. NULL when `Calculation_Status` is not `Normal` | `06:06:14` for Montreal 2026-11-03 with offset -5 | tested |
| Civil_Twilight_End | time(0) | yes | Evening civil dusk, local clock; NULL when not `Normal`. May wrap past midnight modulo 24 h (a `TIME` cannot exceed 23:59:59) | `17:10:13` same example | tested |
| Applied_Offset | float | yes | `ISNULL(@ManualOffset, 0)` | hours | `:173` |
| Calculation_Status | varchar(20) | yes | `Normal`; `Polar Night` (sun never rises above -6 deg that day: `CosHA > 1`, so no start/end); `Midnight Sun` (sun never sinks below -6 deg: `CosHA < -1`, so no civil night) | start/end NULL for the two polar cases | `:82-91`; tested |

## 4. Keys & relationships
- No database objects are read. Logical inputs: `TSC.dbo.vvAirports.LATITUDE` and `LONGITUD` (text, see `vvAirports.md`) and a UTC offset from `GetEffectiveOffset` (hours).
- Joined in `rpt.Get_Detailed_Pairing` as `CROSS APPLY CrewSchedAI.dbo.GetCivilTwilight(dep_arp.LATITUDE, dep_arp.LONGITUD, <local STD datetime>, ISNULL(dyn_offset.Effective_UTC_Offset, 0)) cts` (`rpt.Get_Detailed_Pairing.sql:316`), `dep_arp` = `vvAirports` of the departure station.

## 5. Encoding conventions & gotchas
**How the time is computed**
1. Parse coordinates: `Lat = (DD + MM/60 + SSss/100/3600) * (S ? -1 : 1)`; `Lon = (DDD + MM/60 + SSss/100/3600) * (W ? -1 : 1)`. `SUBSTRING(@LatStr, 6, LEN)` takes **everything after the minutes** as hundredths of a second.
2. `JD_Midnight` = Julian Day at 00:00 UTC of the date: `CAST(CAST(CAST(@CalcDate AS DATE) AS DATETIME) AS FLOAT) + 2415020.5` (datetime day 0 = 1900-01-01 = JD 2415020.5).
3. **Pass 1** at local noon (`JD + 0.5`): Julian centuries `T`; sun mean longitude `L0`, mean anomaly `M`, obliquity, equation of centre `C`, apparent longitude `Omega`; declination `Delta = ASIN(sin(Eps)*sin(Omega))`, right ascension `RA` (`ATN2`), equation of time `EqTime = 4*(L0 - 0.0057183 - RA)` minutes. Hour angle for zenith **96 deg** (`COS(96)`): `CosHA = (cos96 - sin(Lat)sin(Delta)) / (cos(Lat)cos(Delta))`.
   If `CosHA > 1` -> row `Polar Night`; `< -1` -> `Midnight Sun`; both return NULL times.
4. Estimates: `SolarNoon_UTC = 0.5 - Lon/360 - EqTime/1440`, `SemiDuration = DEGREES(ACOS(CosHA))/360`; `JD_Rise`, `JD_Set` = midnight JD + noon -/+ semi-duration.
5. **Pass 2 (refinement)**: recompute `T`, `Delta`, `RA`, `EqTime` and the hour angle at `JD_Rise` (for sunrise side) and at `JD_Set` (sunset side) separately, clamping `CosHA` to [-1, 1].
6. Local clock: `Start = (720 - 4*Lon - EqTime_rise - 4*HA_rise)` minutes after 00:00 UTC; `End = (720 - 4*Lon - EqTime_set + 4*HA_set)`; then `+ @ManualOffset*60` minutes; cast to `TIME(0)`.
   (720 = minutes to solar noon at lon 0; `4*Lon` minutes per degree; `HA` in degrees = minutes/4.)

**Gotchas**
- **BUG (verified): the time-of-day of `@CalcDate` is added to the result.** The final expression is `DATEADD(SECOND, ..., CAST(@CalcDate AS DATETIME))`, so a non-midnight `@CalcDate` shifts both times by its time-of-day (then `TIME(0)` keeps only the clock part).
  Executed 2026-11-03: Montreal (`N45280500`, `W073442900`), offset -5: `@CalcDate = '2026-11-03T00:00:00'` -> **06:06:14 / 17:10:13**; `@CalcDate = '2026-11-03T08:00:00'` -> **14:06:14 / 01:10:13** (+8 h).
  `rpt.Get_Detailed_Pairing` passes the **local scheduled departure date-time** (`DATEADD(MINUTE, offset*60, DATEADD(MINUTE, STD, DATEADD(DAY, DAY, @BaseDate)))`), i.e. with its time of day, so its `Twilight_Start`, `Twilight_End` and therefore `Is_Overnight` (which compares the local departure time with `Twilight_End`) are shifted by the departure time-of-day and are **unreliable** unless the caller passes `CAST(... AS DATE)`. (Observation from code + function test; the procedure itself was not executed.)
- **Blank coordinates are not an error**: 19 stations in `vvAirports` have blank `LATITUDE`/`LONGITUD` and 1 has zeros; the function returns a `Normal` result computed for latitude 0, longitude 0 (tested with empty strings: 05:43:14 / 18:31:05 UTC for 2026-03-21). Test the coordinates for blank before trusting the result.
- Irregular coordinate formats (21 stations with a dotted seconds field such as `N240500.00`, 3 short ones) are mis-scaled by up to a minute of arc: negligible for twilight.
- With `@ManualOffset = NULL` the result is **UTC** (Montreal example: 11:06:14 / 22:10:13); `Applied_Offset` is reported as 0.
- Results are scheduled to whole seconds (`TIME(0)`); the algorithm is accurate to about a minute; refraction is built into the 96 deg zenith.
- The offset parameter is a plain number; it is not a DST-aware lookup. `rpt.Get_Detailed_Pairing` feeds it with `GetEffectiveOffset` of the departure station computed on the UTC STD (accurate except on DST-change days).
- `Polar Night`/`Midnight Sun` here refer to **civil twilight** (-6 deg), not to the geometric sun: e.g. latitude 69 N on 2026-06-21 gives `Midnight Sun` (no civil night), on 2026-12-21 gives `Normal` (09:14:53 / 14:01:11 for offset +1).
- `TIME(0)` cannot exceed 24 h: with large positive offsets the evening time wraps modulo 24 h.

## 6. How the planner-assist procedures use it
- `rpt.Get_Detailed_Pairing` (`:294-299, :316`): outputs `Twilight_Start`, `Twilight_End` and `Is_Overnight = 'Yes'` when `local STD time > Twilight_End AND Night_Stops_Station IS NULL` (a leg that departs after evening civil twilight without a night stop at its arrival). Feeds the per-leg facts of a pairing that the MCP agent uses to evaluate custom rules.
- Not used by R0-R5 or any other procedure.

## 7. Typical query patterns
```sql
-- civil twilight at a station on a date, in UTC (offset NULL -> 0); always pass midnight as the date
SELECT a.AIRPORT, t.[Date], CONVERT(VARCHAR(8), t.Civil_Twilight_Start) AS Dawn_UTC, CONVERT(VARCHAR(8), t.Civil_Twilight_End) AS Dusk_UTC, t.Calculation_Status
FROM TSC.dbo.vvAirports a
CROSS APPLY CrewSchedAI.dbo.GetCivilTwilight(a.LATITUDE, a.LONGITUD, CAST('2026-11-05' AS DATETIME), NULL) t
WHERE a.AIRPORT = 'YUL' AND RTRIM(a.LATITUDE) <> '';

-- local clock with the station's DST offset at noon local time
SELECT t.[Date], CONVERT(VARCHAR(8), t.Civil_Twilight_Start) AS Dawn_Local, CONVERT(VARCHAR(8), t.Civil_Twilight_End) AS Dusk_Local
FROM TSC.dbo.vvAirports a
OUTER APPLY CrewSchedAI.dbo.GetEffectiveOffset(a.AIRPORT, CAST('2026-11-05T12:00:00' AS DATETIME)) o
CROSS APPLY CrewSchedAI.dbo.GetCivilTwilight(a.LATITUDE, a.LONGITUD, CAST('2026-11-05' AS DATETIME), CAST(o.Effective_UTC_Offset AS FLOAT)) t
WHERE a.AIRPORT = 'CDG';
```
(`TIME(0)` columns must be converted to text with `CONVERT(VARCHAR(8), col)` when the query goes through an ODBC client that cannot read the `TIME` type.)

## 8. Data profile (test results, executed 2026-11-03)
| Lat / Lon | CalcDate | Offset | Result |
|---|---|---|---|
| Montreal `N45280500` / `W073442900` | 2026-11-03 00:00 | -5 | 06:06:14 / 17:10:13, Normal |
| same | 2026-11-03 08:00 | -5 | 14:06:14 / 01:10:13 (bug: +8 h) |
| same | 2026-11-03 | NULL | 11:06:14 / 22:10:13 (UTC), Applied_Offset 0 |
| `N69000000` / `E020000000` | 2026-12-21 | +1 | 09:14:53 / 14:01:11, Normal |
| same | 2026-06-21 | +1 | NULL / NULL, Midnight Sun |
| Sydney `S33564600` / `E151103800` | 2026-01-15 | +11 | 05:31:05 / 20:37:37, Normal |
| '' / '' (blank) | 2026-03-21 | 0 | 05:43:14 / 18:31:05, Normal (computed for 0,0) |

## 9. Open questions / confidence
- High: algorithm (read in full, spot-checked: Montreal civil dawn 06:06 EST on 3 Nov is plausible), parameters, one-row output, the time-of-day bug (reproduced), blank-coordinate behaviour (reproduced).
- Not verified: the downstream effect on `Is_Overnight` in the real procedure output; whether the MCP layer post-corrects `Twilight_*`.
- The name "bio-clock offset" does not apply to this function: its offset parameter is a simple station UTC offset.
