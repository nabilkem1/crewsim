# FtcLegalLimit  (Table, CrewSchedAI)  - Maximum Flight Time Credit (FTC) per period by crew category and mini-bloc status

## 1. Purpose & business meaning
`CrewSchedAI.dbo.FtcLegalLimit` holds the **legal/contractual maximum Flight Time Credit (FTC) a crew member may accumulate in one pay/scheduling period**, in hours, for each combination of
**crew category** (`PNT` pilot / `PNC` cabin crew) and **block type** (`Is_Mini_Bloc`: 0 = full block, 1 = "mini-bloc" = the crew member has blocked dates (e.g. vacation/leave) in the period, so a reduced limit applies).
It is the single source of limits for both `rpt.CalculateCrewFTC` and `dbo.R5_Get_Violation_FTC` (R5-10), so the report and the draft check always agree. Changing a limit is an `UPDATE` on this table; no procedure redeploy.
The regulation/agreement article of each limit is "still to be confirmed" - the `Reference` column is intentionally empty. Values were "confirmed as the correct ones on 2026-10-08" (script comment).

Grain: one row per (`Pos_Category`, `Is_Mini_Bloc`); 4 rows. Lifecycle: seeded by `dbo.FtcLegalLimit.sql` (insert-if-missing); edited by the planner-assist owner.

## 2. Physical facts
- `CrewSchedAI.dbo.FtcLegalLimit`, user table, **4 rows** (2026-11-03). Primary key `PK_FtcLegalLimit` on (`Pos_Category`, `Is_Mini_Bloc`); check constraint `CK_FtcLegalLimit_Category` (`Pos_Category IN ('PNT','PNC')`).
- Types: `Pos_Category VARCHAR(3) NOT NULL`, `Is_Mini_Bloc BIT NOT NULL`, `Max_FTC_Hours FLOAT NOT NULL`, `Reference NVARCHAR(200) NULL` (columns.json shows 400 bytes).

## 3. Column dictionary
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| Pos_Category | varchar(3) | no (PK part) | Crew category the limit applies to | `'PNT'` = flight deck (pilots), `'PNC'` = cabin crew; same codes as `position_category.Category` | `dbo.FtcLegalLimit.sql:9,14` |
| Is_Mini_Bloc | bit | no (PK part) | 0 = full block (regular period), 1 = mini-bloc (crew has blocked-date ranges overlapping the period) | procedures compute it from `vvCREWDB.TSC_BLOCKDATES_1_BEGD1/ENDD1, _BEGD2/ENDD2, TSC_BLOCKDATES_3_BEGD1/ENDD1, _BEGD2/ENDD2` overlapping the period (days since 1980-01-01, > 0) | `rpt.CalculateCrewFTC.sql:112-129`, `dbo.R5_Get_Violation_FTC.sql:121-135` |
| Max_FTC_Hours | float | no | Maximum FTC of the period, **in hours** (decimal hours) | 90.0 / 65.0 (PNT), 95.0 / 47.5 (PNC) - compared to `SUM(FTC)` where FTC is in hours | `dbo.R5_Get_Violation_FTC.sql:779,827`; `rpt.CalculateCrewFTC.sql:370` |
| Reference | nvarchar(200) | yes | Regulation / collective-agreement article of the limit | empty (NULL) for all rows: "to be confirmed" | `dbo.FtcLegalLimit.sql:3,12` |

## 4. Keys & relationships
- Natural key (`Pos_Category`, `Is_Mini_Bloc`).
- `Pos_Category` shares the domain of `position_category.Category` (the category of the crew member = category of the activity rows of the period, else of the crew member's latest roster row).
- Lookup predicate (both procedures): `SELECT Max_FTC_Hours FROM dbo.FtcLegalLimit WHERE Pos_Category = @LimitCategory AND Is_Mini_Bloc = @IS_CREW_MINI_BLOC` (`dbo.R5_Get_Violation_FTC.sql:779`, `rpt.CalculateCrewFTC.sql:370`).
- `@IS_CREW_MINI_BLOC` is derived from `TSC.dbo.vvCREWDB` blocked-date columns, not stored here.

## 5. Encoding conventions & gotchas
- **Hours**, not minutes: the procedures sum FTC in hours (`Sum(CREDIT_HRS)/60.0` for alternate credits, `Trip_FTC = minutes/60`) and compare to this value.
- If no row matches, the procedures raise `FTC_LIMIT_NOT_CONFIGURED` (error 50005) instead of defaulting.
- The category used is `ISNULL(MAX(Pos_Category), <crew member's category>)` of the period's result rows (alphabetical `MAX`: `PNT` > `PNC`): a crew member with mixed-category activity rows is evaluated as `PNT`.
- The caller's `@IS_CREW_MINI_BLOC` parameter of `R5_Get_Violation_FTC` is **ignored**; the status is derived inside from the blocked dates, exactly as `rpt.CalculateCrewFTC` does.
- `Reference` is blank: do not cite a regulation article from this table.

## 6. How the planner-assist procedures use it
- `rpt.CalculateCrewFTC` (`:368-375`, result set 2 `LEGAL_LIMIT`, `IS_CREW_MINI_BLOC`): FTC report of a crew member for a period `YYYY-MM`.
- `dbo.R5_Get_Violation_FTC` (`:777-784, :824-828`): after adding the drafted pairing to the period, `Rule_Violation = 'Max FTC exceeded'` when `TOTAL_PERIOD_FTC > LEGAL_LIMIT` (rule R5 "FTC maximum per period"; the regulation reference is open).
- No other object reads it.

## 7. Typical query patterns
```sql
-- the limits
SELECT Pos_Category, Is_Mini_Bloc, Max_FTC_Hours FROM CrewSchedAI.dbo.FtcLegalLimit ORDER BY Pos_Category, Is_Mini_Bloc;

-- limit for a pilot with blocked dates in the period
SELECT Max_FTC_Hours FROM CrewSchedAI.dbo.FtcLegalLimit WHERE Pos_Category = 'PNT' AND Is_Mini_Bloc = 1;
```

## 8. Data profile (measured 2026-11-03)
| Pos_Category | Is_Mini_Bloc | Max_FTC_Hours | Reference |
|---|---|---|---|
| PNC | 0 | 95.0 | NULL |
| PNC | 1 | 47.5 | NULL |
| PNT | 0 | 90.0 | NULL |
| PNT | 1 | 65.0 | NULL |

## 9. Open questions / confidence
- High: structure and use; values per script and live data.
- Open: legal reference of each limit (blank on purpose); whether mini-bloc status should also depend on the length of the blocked range (code only tests overlap with the period).
- The period over which the limit applies is the custom FTC calendar (Jan 1-30, Jan 31-Mar 1, Mar 2-31, then calendar months), defined in the procedures, not in this table.
