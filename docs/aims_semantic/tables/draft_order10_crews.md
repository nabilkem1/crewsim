# draft_order10_crews  (Table, CrewSchedAI)  - Management pilots and their call order in the PNT draft (step 13)

## 1. Purpose & business meaning
`CrewSchedAI.dbo.draft_order10_crews` is a **planner-assist configuration table** listing the **management pilots** that are placed at **step 13** of the pilot (PNT) draft order and the order in which they are called (`Call_Order`).
Business context (from the script and `dbo.R0_GetDraftList`): when a pairing must be drafted (assigned to an available crew member), R0 ranks the candidate pool by a published 13-step order ("Procedure Draft PNT", clause 14.15 / article 14.5.3).
Management pilots (pilots who hold a management role in the airline) are called **last, at step 13, in `Call_Order`** (then seniority), unless the pilot is excluded by schedule code `CPP5` or `PECA` (shown as `X`, "not drafted") - and since 2026-10-30 a
management pilot is never blocked by an R3 rest-time violation (the agent checks R3/R4 afterwards; the R3 text is shown as information). Cabin crew (PNC) are not affected by this list.
The table name is historical ("priority 10" before R0-10). Base and aircraft are not stored: the candidate pool is already filtered on base, aircraft and position before this table is consulted.

Grain: one row per management pilot (crew id) with an explicit call order; 11 rows. Lifecycle: seeded/maintained by `dbo.draft_order10_crews.sql` (a `MERGE` that inserts, updates the call order and **deletes rows that are not in the script**);
business answer C-14 of 2026-10-29 fixed the 11 pilots and their order (one former entry was removed because he is not in the procedure). Editing the rows changes the draft list without redeploying R0.

## 2. Physical facts
- `CrewSchedAI.dbo.draft_order10_crews`, user table, **11 rows** (2026-11-03). Primary key `PK_draft_order10_crews` on `Crew_Id`. No other indexes.
- Types: `Crew_Id INT NOT NULL`, `Call_Order INT NULL` (the column was added later by `ALTER TABLE ... ADD`, hence nullable).
- Deploy before `dbo.R0_GetDraftList.sql` (the procedure reads `Call_Order`).

## 3. Column dictionary
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| Crew_Id | int | no (PK) | Internal AIMS crew id of the management pilot (`vvCREWDB.ID` = `ROSTERID.ID` = `CREWQUAL.ID`). Pseudonymous key; the individual ids and names are intentionally not documented here | integer; 11 distinct, all exist in `vvCREWDB` (11 of 11 matched) | `dbo.draft_order10_crews.sql:10`; `dbo.R0_GetDraftList.sql:1113`; profiled (match count only) |
| Call_Order | int | yes | Position of the pilot in the management call list: 1 is called first | 1..11, 11 distinct values, no NULLs; `R0` uses `ISNULL(Mgmt_Call_Order, 999)` so a NULL would sort last | `dbo.R0_GetDraftList.sql:1113-1121`; profiled |

## 4. Keys & relationships
- Natural key `Crew_Id`. `draft_order10_crews.Crew_Id = TSC.dbo.vvCREWDB.ID` (1:1; `CA.Crew_Id` in R0 is the integer crew id). Predicate: `LEFT JOIN dbo.draft_order10_crews mg ON mg.Crew_Id = CA.Crew_Id` (`dbo.R0_GetDraftList.sql:1113`) and `CA.Crew_Id IN (SELECT Crew_Id FROM dbo.draft_order10_crews)` (`:1204`).
- Not linked to base or aircraft: the 11 pilots hold (profiled on 2026-11-03): base `YUL` captains (position `CM`) qualified on 320 / 321 / 32Q (5 each) and 332 / 333 (8 each), plus base `YYZ` captains on 332 / 333 (2 each) - i.e. all are captains; the candidate-pool filter on base/aircraft/position still applies in R0.

## 5. Encoding conventions & gotchas
- `Call_Order` is the sub-sort inside step 13: `Pnt_Sub_Sort = ISNULL(s.Mgmt_Call_Order, 999)` (`dbo.R0_GetDraftList.sql:1121`).
- Step labels differ by category: pilots (PNT) use the new 13-step order where management is step `'13'` ("Step 13: management pilot, call order n of the management list. No double time or other premium (VA). ADM/ADMP on the draft day do not prevent the call."); the legacy `CPriority '10'` branch ("Explicitly requested addition (Priority 10 assignment)", `:1204,1236`) is only reached by a candidate that the PNT ranking (`pr`) did not rank.
- Priority among the exclusions: `CPP5` / `PECA` give `X` even for management pilots; `On_Drafted_Pairing` is `X`; otherwise a management pilot is step 13 even if an R3 violation exists (informational text) - changed on 2026-10-30.
- The table is a **MERGE-managed list**: any manual insert that is not in the script is deleted at the next deployment of the script (`WHEN NOT MATCHED BY SOURCE THEN DELETE`). Change the script and the table together.
- Personal data: although ids are internal numbers, they identify named individuals; do not output them in answers other than needed for a specific draft.

## 6. How the planner-assist procedures use it
- `dbo.R0_GetDraftList` only:
  - `PntRank` / `PntSteps` (`:1105-1121`): `Is_Mgmt` flag and `Mgmt_Call_Order`; step `13` sorts by `Call_Order` (`WHEN x.Step = '13' THEN ISNULL(s.Mgmt_Call_Order, 999)`);
  - `CPriority` (`:1204`) and the textual reason (`:1236`);
  - no other procedure reads it.
- Related business rules in the R0 header (`:936-945`): management pilots are step 13; CPP5 / PECA excluded; the 15 h first pass, the 12 h-3 h no-contact window and "on duty at the call" are not handled.

## 7. Typical query patterns
```sql
-- the call order list (ids only)
SELECT Call_Order, Crew_Id FROM CrewSchedAI.dbo.draft_order10_crews ORDER BY Call_Order;

-- is a crew member a management pilot? (aggregate answer)
SELECT CASE WHEN EXISTS (SELECT 1 FROM CrewSchedAI.dbo.draft_order10_crews WHERE Crew_Id = 0 /* crew id */) THEN 1 ELSE 0 END AS Is_Management_Pilot;
```

## 8. Data profile (measured 2026-11-03)
- 11 rows, 11 distinct `Crew_Id`, `Call_Order` 1..11 (11 distinct, 0 NULL). All 11 exist in `TSC.dbo.vvCREWDB`.
- Qualifications active on 2026-11-03 for these 11 crew (rows by base / position / aircraft): YUL CM 320 5; YUL CM 321 5; YUL CM 32Q 5; YUL CM 332 8; YUL CM 333 8; YYZ CM 332 2; YYZ CM 333 2.

## 9. Open questions / confidence
- High: role and ordering semantics (script + R0 code).
- The reason a pilot is a "management pilot" is only given by the business notes in the script ("management pilots"), not derivable from data.
- Whether `Call_Order` gaps or duplicates are allowed: the PK is on `Crew_Id` only, so duplicates in `Call_Order` are technically possible (none present).
