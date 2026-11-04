# CrewIdList  (User-defined table type, CrewSchedAI)  - List of crew ids passed as a table-valued parameter

## 1. Purpose & business meaning
`CrewSchedAI.dbo.CrewIdList` is **not a table that stores data**: it is a **user-defined table type** (`CREATE TYPE dbo.CrewIdList AS TABLE`) used as a **table-valued parameter (TVP)** to pass a set of crew ids from one procedure to another in a single call.
It exists so that the draft-list procedure can check the rest-time rules (R3) of **all candidate crew members in one call** instead of one call per crew member: `dbo.R0_GetDraftList` fills a `@Batch dbo.CrewIdList` with the
candidate crew ids and calls `dbo.R3_Get_Violations_RestTime_Batch @CrewBatch = @Batch, ...` (a rule-engine run for many crew, "STREAMING/BATCH" version of R3).
Grain of an instance: one row per crew id (the AIMS internal crew id as text). Lifecycle: the type is created once by `dbo.CrewIdList.sql` (`IF TYPE_ID(N'dbo.CrewIdList') IS NULL CREATE TYPE ...`; a table type cannot be altered in place, so
only created when missing). Instances live in memory/tempdb for the duration of the call.

## 2. Physical facts
- `CrewSchedAI.dbo.CrewIdList`, object type `TABLE_TYPE` (`sys.types.is_table_type = 1`, confirmed 2026-11-03). Not in `sys.tables`; it has no rows of its own and no row count.
- Definition: `Crew_ID NVARCHAR(10) NOT NULL PRIMARY KEY` (clustered/unique index on `Crew_ID` inside each instance, so duplicates are rejected and lookups are by `Crew_ID`).
- Must be created before `dbo.R0_GetDraftList` and `dbo.R3_Get_Violations_RestTime_Batch` are deployed. Passed `READONLY`.
- Not present in `crewschedai_columns.json` (types are not tables); columns documented from the script.

## 3. Column dictionary
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| Crew_ID | nvarchar(10) | no (PK) | AIMS crew id of a crew member to evaluate, **as text** (e.g. the digits of `vvCREWDB.ID`) | up to 10 characters; numeric text; unique within the list; the batch procedure validates every entry with `TRY_CAST(cb.Crew_ID AS INT)` against `vvCREWDB.ID` (unknown or non-numeric -> `CREW_NOT_FOUND`, error 50003) and joins it to the integer `ROSTER.ID` by implicit conversion | `dbo.CrewIdList.sql:5-8`; `dbo.R0_GetDraftList.sql:830-835`; `dbo.R3_Get_Violations_RestTime_Batch.sql:10,146` |

## 4. Keys & relationships
- Within an instance: `Crew_ID` unique. Logical relation: `CrewIdList.Crew_ID` (text) = `TSC.dbo.ROSTER.ID` / `vvCREWDB.ID` (integer): joined with `JOIN @CrewBatch cb ON cb.Crew_ID = r.ID` (implicit conversion of the nvarchar to int in `dbo.R3_Get_Violations_RestTime_Batch.sql:146`) and `h.CREWID IN (SELECT Crew_ID FROM @CrewBatch)` for the hotel rows (`:385,419`).
- Producer: `dbo.R0_GetDraftList` (`:830-835`): `INSERT INTO @Batch (Crew_ID) SELECT DISTINCT CAST(cr.Crew_Id AS NVARCHAR(10)) FROM #CrewRoster cr WHERE cr.Local_ARR_DATETIME < @Pairing_Start_DateTime OR cr.Local_DEP_DATETIME >= @Pairing_End_DateTime` - i.e. every crew member of the candidate roster that is not overlapped by the drafted pairing.
- Consumer: `dbo.R3_Get_Violations_RestTime_Batch(@CrewBatch dbo.CrewIdList READONLY, @PAIRING_ID, @PairingDate)`.

## 5. Encoding conventions & gotchas
- The ids are **strings** (`NVARCHAR(10)`) although AIMS crew ids are integers; callers must `CAST(id AS NVARCHAR(10))` (R0 does); inside the batch procedure the text is compared with the integer `ROSTER.ID` (implicit conversion) and copied into temp tables as `NVARCHAR(10)`. An id that is not a number or not in `vvCREWDB` makes the procedure fail with `CREW_NOT_FOUND: Crew <ids> does not exist.` (`dbo.R3_Get_Violations_RestTime_Batch.sql:24-36`) instead of being ignored.
- Crew ids with more than 10 characters would be truncated/rejected; AIMS ids are far shorter.
- A TVP is `READONLY`: the procedure cannot modify it. Table types cannot be `ALTER`ed: changes require dropping dependent procedures first.
- When calling the batch from an ad-hoc client, declare `DECLARE @CrewBatch dbo.CrewIdList; INSERT INTO @CrewBatch (Crew_ID) VALUES ('<id>');` (commented example at `dbo.R3_Get_Violations_RestTime_Batch.sql:13-17`).
- Because the batch procedure also accepts the negative hotel pseudo-ids `-1, -2, -3` (vacancy placeholders of an unfilled pairing complement) in the HOTAC read, those values are not expected in the list itself.

## 6. How the planner-assist procedures use it
| Procedure | Use |
|---|---|
| `dbo.R0_GetDraftList` (`:830-841`) | builds `@Batch dbo.CrewIdList` from the candidate roster (not overlapped by the drafted pairing) and calls `R3_Get_Violations_RestTime_Batch` once; the rows with `Is_Compliant = 0` of the drafted pairing day produce the `X1` ("blocked by R3") bucket for crew who would break a rest rule |
| `dbo.R3_Get_Violations_RestTime_Batch` (`:10,30,127,146,162,182,385,419`) | restricts every roster/leg/hotel read to the crew in `@CrewBatch` and runs the rest-time/acclimatisation/WOCL/block-time rules for all of them |
Single-crew R3 (`dbo.R3_Get_Violations_RestTime`) does not use the type.

## 7. Typical query patterns
```sql
-- run the batch rest-time check for two crew members (ids are crew numbers as text)
DECLARE @CrewBatch dbo.CrewIdList;
INSERT INTO @CrewBatch (Crew_ID) VALUES ('1001'), ('1002');   -- placeholders: use real ids
EXEC CrewSchedAI.dbo.R3_Get_Violations_RestTime_Batch @CrewBatch = @CrewBatch, @PAIRING_ID = 'C0290', @PairingDate = '2026-11-05';
```
(An `EXEC` is not allowed through the read-only helper; the pattern is for the MCP/service layer.)

## 8. Data profile (measured 2026-11-03)
- Object type `TABLE_TYPE`; no persistent rows. Verified through `sys.types` (name `CrewIdList`, `is_table_type = True`) in database CrewSchedAI.

## 9. Open questions / confidence
- High: purpose and shape (script + callers).
- Validation of the ids is explicit (`TRY_CAST`), but the later joins rely on implicit nvarchar -> int conversion; harmless for validated numeric ids.
