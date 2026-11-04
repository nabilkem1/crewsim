# position_category  (Table, CrewSchedAI)  - Classification of crew positions into pilots (PNT) and cabin crew (PNC)

## 1. Purpose & business meaning
`CrewSchedAI.dbo.position_category` is a small **planner-assist configuration table** (not an AIMS table). It decides, for every crew position id, whether the position belongs to the **flight deck (`PNT` = personnel navigant technique = pilots)** or to the **cabin
crew (`PNC` = personnel navigant commercial)**. Every crew-rule procedure needs this split because rule limits differ (rest and duty rules, FTC limits, report offsets, draft order, "pilots only" WOCL rule).
Before R0-3 the list was hard-coded as the literal `(1, 2, 4)` in six procedures; now they all read this table, so the list can be changed with an `UPDATE` without redeploying code.

Grain: one row per `Position_Id` (= `TSC.dbo.vvPositions.ID` = `ROSTER.POS` = `CREWQUAL.POS`); 8 rows, one per AIMS position. Lifecycle: created by the deployment script `dbo.position_category.sql` (insert-if-missing),
edited by the planner-assist owner; read-only for procedures.

## 2. Physical facts
- Database/schema: `CrewSchedAI.dbo.position_category`, user table. **8 rows** (2026-11-03).
- Primary key `PK_position_category` on `Position_Id`; check constraint `CK_position_category_Category` (`Category IN ('PNT','PNC')`). No other indexes (8 rows).
- DDL declares `Code NVARCHAR(10)` and `Description NVARCHAR(100)` (columns.json shows 20 / 200 bytes).

## 3. Column dictionary
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| Position_Id | int | no (PK) | AIMS crew position id | `vvPositions.ID`: 1 CM, 2 PO, 3 ME, 4 SP, 5 DV, 6 DA, 7 AB, 8 SU | `dbo.position_category.sql:8-9,14`; `vvPositions` profiled |
| Category | char(3) | no | Crew category of the position | `'PNT'` flight deck / `'PNC'` cabin crew (CHECK constraint) | `dbo.position_category.sql:15,18` |
| Code | nvarchar(10) | yes | Position code, "for the reader only" (not used in logic) | CM, PO, ME, SP, DV, DA, AB, SU (= `vvPositions.CODE`) | `dbo.position_category.sql:16` |
| Description | nvarchar(100) | yes | Readable description, "for the reader only" | Captain, First officer, Flight engineer (PNC so far, to be confirmed), Supervising pilot, Flight director, Assistant flight director, Flight attendant, Supervisor | `dbo.position_category.sql:17,26-33` |

## 4. Keys & relationships
- Natural key `Position_Id` (unique).
- `position_category.Position_Id = TSC.dbo.vvPositions.ID` (1:1), and = `TSC.dbo.ROSTER.POS` / `TSC.dbo.CREWQUAL.POS` (1:N; the position flown or qualified).
- Procedure pattern (identical in R3, R3 batch, R4, R5, CalculateCrewFTC): `DECLARE @PntPositionCodes TABLE (PosCode INT PRIMARY KEY); INSERT INTO @PntPositionCodes (PosCode) SELECT Position_Id FROM dbo.position_category WHERE Category = 'PNT';` then `CASE WHEN r.POS NOT IN (SELECT PosCode FROM @PntPositionCodes) THEN 'PNC' ELSE 'PNT' END` (`rpt.CalculateCrewFTC.sql:19-23,176`; `dbo.R3_Get_Violations_RestTime.sql:68-72`).
- R0 uses the same list as `@PntPositionIds` (`dbo.R0_GetDraftList.sql:66-69`).

## 5. Encoding conventions & gotchas
- **Absence = PNC**: any position id without a row (or with `Category = 'PNC'`) is treated as cabin crew, "as before". The procedures only fail (`THROW 50012 POSITION_CATEGORY_NOT_CONFIGURED`) when **no** position is PNT.
- Categories are the French-Canadian aviation abbreviations: `PNT` = pilots, `PNC` = cabin crew. The values are three characters exactly (`char(3)`), upper case.
- Position 3 (`ME`, flight engineer) is classified `PNC` to keep the old behaviour `(1,2,4) = PNT`; the script itself says "the business should confirm that". No active qualification uses it (see profile).
- Only the `PNT` rows matter for logic; `Code`/`Description` are cosmetic and can drift from `vvPositions`.
- Positions 9..12 in `vvPositions` are blank placeholders and have no row here.

## 6. How the planner-assist procedures use it
| Procedure | Use |
|---|---|
| `dbo.R0_GetDraftList` | `@PntPositionIds`: marks crew candidates as PNT/PNC; drives the PNT draft order (13 steps) vs the unchanged PNC ranking |
| `dbo.R3_Get_Violations_RestTime` / `_Batch` | pilot vs cabin: duty/rest rules, report offsets (-80 for overseas PNC), WOCL rule FD-CAR-2557 (pilots only) |
| `dbo.R4_Get_Violation_FDP` | flight duty period limits and report offsets by category (PNT vs PNC) |
| `dbo.R5_Get_Violation_FTC`, `rpt.CalculateCrewFTC` | FTC limits by category (`FtcLegalLimit.Pos_Category`), TAFB divisor 4 (PNT) vs 6 (PNC), duty-split 11 h (PNT) / 12 h (PNC), deadhead credits (cabin only) |

## 7. Typical query patterns
```sql
-- the pilot position ids
SELECT Position_Id, Code FROM CrewSchedAI.dbo.position_category WHERE Category = 'PNT';

-- category of the active qualifications of a base (aggregate; no names)
SELECT pc.Category, COUNT(DISTINCT q.ID) AS Crew_Members
FROM TSC.dbo.CREWQUAL q
LEFT JOIN CrewSchedAI.dbo.position_category pc ON pc.Position_Id = q.POS
WHERE q.CWBASE = 'YUL'
  AND q.ACTIVBEG <= DATEDIFF(DAY,'1980-01-01',GETDATE()) AND q.ACTIVEND >= DATEDIFF(DAY,'1980-01-01',GETDATE())
GROUP BY pc.Category;
```

## 8. Data profile (measured 2026-11-03)
| Position_Id | Category | Code | Description |
|---|---|---|---|
| 1 | PNT | CM | Captain |
| 2 | PNT | PO | First officer |
| 3 | PNC | ME | Flight engineer (PNC so far, to be confirmed) |
| 4 | PNT | SP | Supervising pilot |
| 5 | PNC | DV | Flight director |
| 6 | PNC | DA | Assistant flight director |
| 7 | PNC | AB | Flight attendant |
| 8 | PNC | SU | Supervisor |

Active qualifications on 2026-11-03 (CREWQUAL, period contains today): position 1 CM 904 rows / 349 crew (PNT); 2 PO 1,021 / 394 (PNT); 5 DV 1,709 / 345 (PNC); 7 AB 8,452 / 1,702 (PNC); 8 SU 160 / 33 (PNC); positions 3, 4, 6 have no active qualification.

## 9. Open questions / confidence
- High confidence on the table's role and the PNT/PNC semantics (script comments + code).
- Open: whether `ME` (flight engineer) and `SP` (supervising pilot) are correctly categorised (script says ME "to be confirmed"); `SP` is PNT as in the old literal list.
