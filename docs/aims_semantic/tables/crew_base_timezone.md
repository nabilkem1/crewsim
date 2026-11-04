# crew_base_timezone  (Table, CrewSchedAI)  - Time zone (Windows zone name, labels, standard offset) of each crew base

## 1. Purpose & business meaning
`CrewSchedAI.dbo.crew_base_timezone` is a **planner-assist configuration table** (R0-2) that maps a **crew base** (a station code such as `YUL`, `YYZ`) to the time zone in which the draft-list procedure
`dbo.R0_GetDraftList` must express times: the calendar day on which a pairing starts and ends for crew of that base, the local times printed in `Conflict_List`, and the label (`EST`/`EDT`...) shown after a time.
Before R0-2 the procedure treated every base as Eastern time; now a base **without a row fails** (`TIMEZONE_NOT_CONFIGURED`) instead of being silently converted as Eastern.

Grain: one row per crew base; 10 rows. Lifecycle: seeded by `dbo.crew_base_timezone.sql` (insert-if-missing); changed by `UPDATE`/`INSERT` by the planner-assist owner when a base is added (no redeploy of the procedure). Read-only for procedures.
This table drives only R0 and uses SQL Server `AT TIME ZONE`; the rest-time/FDP procedures instead use the AIMS zone tables through `GetEffectiveOffset*` (see those function docs) - the two mechanisms are independent.

## 2. Physical facts
- `CrewSchedAI.dbo.crew_base_timezone`, user table, **10 rows** (2026-11-03). Primary key `PK_crew_base_timezone` on `Base`. No other indexes.
- DDL types: `Base NVARCHAR(50)`, `Time_Zone_Name NVARCHAR(100)`, `Std_Label VARCHAR(10)`, `Dst_Label VARCHAR(10)`, `Std_Offset_Min INT` (columns.json lengths are bytes: 100 / 200).
- All columns NOT NULL.

## 3. Column dictionary
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| Base | nvarchar(50) | no (PK) | Crew base station code, as in `CREWQUAL.CWBASE` and the `@CrewMainBase` parameter of R0 | IATA station code in upper case: YUL, YYZ, YMX, YOW, YHM, YWG, YYC, YVR, YHZ, PRG | `dbo.crew_base_timezone.sql:14`; `dbo.R0_GetDraftList.sql:48-50` |
| Time_Zone_Name | nvarchar(100) | no | **Windows time-zone id** (a name in `sys.time_zone_info`), used with `AT TIME ZONE` so DST is handled by SQL Server | e.g. `Eastern Standard Time` (also used for the DST period), `Central Standard Time`, `Mountain Standard Time`, `Pacific Standard Time`, `Atlantic Standard Time`, `Central Europe Standard Time` | `dbo.R0_GetDraftList.sql:44,131,145,180,191,733-751` |
| Std_Label | varchar(10) | no | Label of the standard time, printed after local times in the conflict list | EST, CST, MST, PST, AST, CET | `dbo.R0_GetDraftList.sql:1086` |
| Dst_Label | varchar(10) | no | Label of the daylight-saving time | EDT, CDT, MDT, PDT, ADT, CEST | same |
| Std_Offset_Min | int | no | UTC offset of the STANDARD time of the zone, in minutes (negative = west of UTC). R0 prints `Std_Label` when the offset of a departure equals this value, `Dst_Label` otherwise | -300 (Eastern), -360 (Central), -420 (Mountain), -480 (Pacific), -240 (Atlantic), +60 (CET) | `dbo.R0_GetDraftList.sql:47-48,1086` |

## 4. Keys & relationships
- Natural key `Base` (unique). `crew_base_timezone.Base` = `TSC.dbo.CREWQUAL.CWBASE` (blank-padded `char`; `=` compares ignore trailing blanks) = the `@CrewMainBase` parameter. Predicate: `FROM dbo.crew_base_timezone WHERE Base = @CrewMainBase` (`dbo.R0_GetDraftList.sql:48-50`).
- `Time_Zone_Name` must exist in `sys.time_zone_info` (not a foreign key; no constraint enforces it).
- `Base` values are also valid first parameters of `GetEffectiveOffset*` (`vvAirports.AIRPORT`), but those functions do not read this table.

## 5. Encoding conventions & gotchas
- `Time_Zone_Name` for Eastern uses the Windows name `Eastern Standard Time`, which **includes daylight saving**; the "Standard" in the name does not mean no DST. `AT TIME ZONE 'UTC' AT TIME ZONE <name>` returns the right local time in both seasons.
- The offsets are **minutes**, label comparison is by exact `Std_Offset_Min` equality with `DATEPART(TZOFFSET, ...)`.
- Eastern bases (YUL, YYZ, YMX, YOW, YHM) keep the legacy behaviour; other zones are real zones "that have no active crew in 2026 (only history)" and "the business should confirm the zones" (script comment).
- **Known inconsistency with AIMS master data**: this table says Winnipeg `YWG` is Central (CST/CDT, -360) while `vvAirports`/`vvZONEIDX` place `YWG` in zone `CY 3 A` (-300, no DST) so `GetEffectiveOffset('YWG', ...)` returns -5 all year. The two sources are not reconciled (observation).
- A base missing here raises error 50011 listing the known bases (`THROW 50011, TIMEZONE_NOT_CONFIGURED`). The MCP layer maps that prefix to a validation error.

## 6. How the planner-assist procedures use it
- `dbo.R0_GetDraftList` (`:42-57`): `SELECT @LocalTimeZone = Time_Zone_Name, @LocalTimeZoneLabel = Std_Label, @LocalTimeZoneDstLabel = Dst_Label, @LocalTimeZoneStdOffsetMin = Std_Offset_Min FROM dbo.crew_base_timezone WHERE Base = @CrewMainBase`; if no row -> error. Then
  - UTC leg/activity timestamps are converted with `CAST(... AS DATETIME) AT TIME ZONE 'UTC' AT TIME ZONE @LocalTimeZone` (`:131,145,180,191,733-751`) to get `Local_DEP_DATETIME`, `Local_ARR_DATETIME`, activity start/end;
  - `DATEPART(TZOFFSET, ...)` of the departure gives `Local_DEP_Offset_Min`; if it equals `Std_Offset_Min` the label `Std_Label` is printed else `Dst_Label` (`:737,1086`).
  These local times decide which calendar day a pairing falls on for the candidate pool and the "touches another activity" logic of the draft order.
- Not used by R1-R5, `rpt.*` or the other functions.

## 7. Typical query patterns
```sql
-- known bases and their zones
SELECT Base, Time_Zone_Name, Std_Label, Dst_Label, Std_Offset_Min FROM CrewSchedAI.dbo.crew_base_timezone ORDER BY Base;

-- local time at a base for a UTC datetime (SQL Server time-zone support)
SELECT CAST(CAST('2026-11-05T14:30:00' AS DATETIME) AT TIME ZONE 'UTC' AT TIME ZONE t.Time_Zone_Name AS DATETIME) AS Local_Time
FROM CrewSchedAI.dbo.crew_base_timezone t WHERE t.Base = 'YUL';
```

## 8. Data profile (measured 2026-11-03)
| Base | Time_Zone_Name | Std/Dst label | Std_Offset_Min |
|---|---|---|---|
| YUL, YYZ, YMX, YOW, YHM | Eastern Standard Time | EST / EDT | -300 |
| YWG | Central Standard Time | CST / CDT | -360 |
| YYC | Mountain Standard Time | MST / MDT | -420 |
| YVR | Pacific Standard Time | PST / PDT | -480 |
| YHZ | Atlantic Standard Time | AST / ADT | -240 |
| PRG | Central Europe Standard Time | CET / CEST | +60 |

10 rows. Active crew qualifications on 2026-11-03 exist only for bases `YUL` (1,752 crew) and `YYZ` (1,071 crew); other bases appear only in history (CREWQUAL rows all-time: YYZ 58,007, YUL 44,109, YVR 17,516, YMX 10,709, YYC 518, YHZ 59, YOW 53, YHM 42, PRG 4, YWG 1) - every base ever used in CREWQUAL has a row here.

## 9. Open questions / confidence
- High: purpose and use in R0 (code + script comments).
- The business has not confirmed the non-Eastern zones (script note). YWG conflicts with AIMS zone data (see Section 5).
- A new base (e.g. `YQB` appears as a flight station but not as a crew base) needs a row before R0 can run for it.
