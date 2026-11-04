# CREWCATEG  (Table)  - Crew-to-category assignments with validity period (who held which category, from when to when)

## 1. Purpose & business meaning
`TSC.dbo.CREWCATEG` is the AIMS **assignment (link) table between a crew member and a crew category** defined in `CREWCAT`. One row = "crew member `ID` belongs to category `CREWCATIDX` during the inclusive day range `ACTIVEBEG`..`ACTIVEEND`".
Grain: (crew, category, validity period). A crew member normally holds several categories at once (average 2.9, maximum 14 valid today) and the same category can be assigned again later in a separate period (measured: 4,009 (crew, category) pairs have more than one row).
Lifecycle: rows are created by crew administrators/AIMS crew-data maintenance (and probably by AIMS batch jobs for status categories); a category is ended by setting `ACTIVEEND` (rows are not deleted: 17,650 of 31,563 rows ended before today and are kept as history). The table is the source of the "Crew_Categories" / "Crew_Profile_Categories" strings the planner-assist procedures show and match rules against, and of the include/exclude filters of the draft list.
Business use: category membership drives which regulations / union rules / custom scheduling rules / certificate (expiry) rules apply to a crew member (e.g. "JUNIOR FO", "CPT en LI - RC", "BLOC INACTIF", "PNC - B", "FRANÇAIS").

## 2. Physical facts
- `TSC.dbo.CREWCATEG`, **USER_TABLE**, **31,563 rows** (rowcounts.json; measured identical, today = 2026-11-03), 4,884 distinct crew `ID`.
- Primary key `CREWCATEG_INDEX_0` (unique): (`ID`, `CREWCATIDX`, `ACTIVEEND`, `ACTIVEBEG`) - the natural key; a crew can hold the same category in several non-identical periods.
- Secondary index `CREWCATEG_INDEX_1` (non-unique): (`ID`, `ACTIVEEND`, `ACTIVEBEG`) - the access path "all categories of one crew member valid after date X". Always filter by `ID` first.
- Small table; the cost driver in the procedures is the repeated `FOR XML PATH` string aggregation per crew, not the table size.

## 3. Column dictionary
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| ID | int | N | Crew member internal AIMS id (the same `ID` as `ROSTER.ID`, `CREWQUAL.ID`, `vvCREWDB.ID`, `ROSTERID.ID`) | integer crew id; measured: every `ID` exists in `vvCREWDB` and `ROSTERID` (0 orphans) | profiled; `rpt.get_crew_categories.sql` (`WHERE Main.ID = @crew_id`); `R0_GetDraftList.sql` line 442 (`ccSub.ID = q.ID`) |
| CREWCATIDX | smallint | N | Category number = `CREWCAT.CREWCAT` (foreign key by convention, not declared) | 1..240; measured: 0 rows without a matching `CREWCAT` | profiled; `rpt.get_crew_categories.sql` line 20 |
| ACTIVEBEG | smallint | N | First day (inclusive) on which the crew member holds the category | AIMS day number = days since **1980-01-01** (`DATEADD(DAY, ACTIVEBEG, '1980-01-01')`); `0` = "since the beginning" (1980-01-01 placeholder, 8,355 rows); real values range from 1991-04-04 to 2027-03-01 | profiled; `rpt.get_crew_categories.sql` lines 12-13, 25-26 |
| ACTIVEEND | smallint | N | Last day of the validity period. **Inclusive** in AIMS (see gotchas) | same day-number encoding; `32767` = open-ended sentinel (= 2069-09-17), 13,739 rows; earliest value 2006-08-31; latest finite end 2027-11-15 | profiled; `R2_Get_Violations_Schedule_WithWithNot.sql` line 182 comment ("ACTIVEBEG and ACTIVEEND are inclusive day numbers") |

## 4. Keys & relationships
- Natural key: (`ID`, `CREWCATIDX`, `ACTIVEEND`, `ACTIVEBEG`) = PK.
- `CREWCATEG.ID` -> `vvCREWDB.ID` / `ROSTERID.ID` / `CREWQUAL.ID` / `ROSTER.ID` (N:1 per crew; all consistent, 0 orphans measured against `vvCREWDB` and `ROSTERID`).
- `CREWCATEG.CREWCATIDX` -> `CREWCAT.CREWCAT` (N:1). Exact predicate used: `INNER JOIN TSC.dbo.CREWCAT AS cc ON cc.CREWCAT = Main.CREWCATIDX` (`rpt.get_crew_categories.sql` lines 19-20; same in `R0_GetDraftList.sql` lines 440, 452, 508; `R1_Get_Violations_CertainFlightsCrew.sql` line 216; `R2_Get_Violations_Schedule_WithWithNot.sql` lines 180, 312).
- Cardinality: crew 1:N categories; (crew, category) 1:N periods (non-overlapping in a sample check of crew IDs 1-2000: 0 overlaps).

## 5. Encoding conventions & gotchas
- **Dates are integer day numbers since 1980-01-01** (not yyyymmdd). Convert with `DATEADD(DAY, n, '1980-01-01')`; to compare with today use `DATEDIFF(DAY, '1980-01-01', GETDATE())`.
- **Sentinels:** `ACTIVEBEG = 0` means "from the beginning of time"; `ACTIVEEND = 32767` means "no end" (2069-09-17). Never print 2069-09-17 as a real date; say "open-ended".
- **Active-period test.** The correct "valid on day D" predicate is `ACTIVEBEG <= D AND ACTIVEEND >= D` (both inclusive; confirmed by `R2` comment and by the data: consecutive periods of the same crew+category start the day after the previous end, gap = 1 in 28 of the 41 re-assignments with a gap of 1..3 days).
  The procedures are **not consistent**:
  - `R0_GetDraftList`: window overlap `ACTIVEBEG <= @EndDateNum AND ACTIVEEND >= @StartDateNum` (inclusive, over the search window);
  - `R2_Get_Violations_Schedule_WithWithNot`: valid on the pairing date, inclusive both ends (R2-7);
  - `rpt.get_crew_categories`: `ACTIVEBEG <= today AND ACTIVEEND > today` (treats `ACTIVEEND` as exclusive: a category ending today is not shown; 6 rows end exactly today);
  - `R1_Get_Violations_CertainFlightsCrew` (line ~219) and `rpt.get_crew_certifications` (line 122): only `ACTIVEEND > today`, **no `ACTIVEBEG` test and not tied to the pairing date**, so categories that start in the future (40 rows) and categories that were valid on the pairing date but have since ended are mis-handled. These are behaviours of existing code, not properties of the table.
- Crew who left the company keep rows (category 222 "No longer with Air Transat" has 325 assignments) and ended rows are never purged; always restrict by validity date before counting crew.
- Not every crew has a row: 4,884 distinct crew in the table vs 6,151 crew in `vvCREWDB`; 4,721 crew have at least one category valid today.
- Multiple periods of the same category: always `DISTINCT`/`GROUP BY` before concatenating names (R0 builds `#CrewCatMap` with `SELECT DISTINCT`).
- The `STUFF(... FOR XML PATH)` pattern in the procedures orders by `ACTIVEEND, ACTIVEBEG, CREWCATIDX` - ordering by validity end, not by category name.

## 6. How the planner-assist procedures use it
- `dbo.R0_GetDraftList`:
  - pool filter by category names (`@CategoryIncludeList` = crew must hold at least one listed category during the window; `@CategoryExcludeList` = crew must hold none), lines 435-458;
  - `#CrewCatMap` of the pool (`cc.ACTIVEBEG <= @EndDateNum AND cc.ACTIVEEND >= @StartDateNum`), lines 503-512, then `Crew_Categories` string per candidate;
  - certificate applicability: a crew member's category names are intersected with `#CertCatInc` / `#CertCatExc` (EXPI bitmaps) to decide whether an expired certificate applies to him (lines 574-586).
- `dbo.R1_Get_Violations_CertainFlightsCrew` and `dbo.R2_Get_Violations_Schedule_WithWithNot`: compute `Crew_Profile_Categories` of the drafted crew member (and, in R2, of the other crew members of the pairing on the pairing date) and compare with the category lists of the custom scheduling rules (SPEFREC2/SPEFREC3). A match makes the rule apply ("are to be scheduled only" / "are not to be scheduled").
- `rpt.get_crew_categories`: returns, for `@crew_id`, the valid categories with real dates (`CAST(DATEADD(DAY, ACTIVEBEG, '1980-01-01') AS DATE)`), `Category_Name`, `QUAL`, `ISFORECREW`.
- `rpt.get_crew_certifications`: concatenated `Crew_Categories` per crew used to evaluate include/exclude lists of each certificate type.

## 7. Typical query patterns
```sql
-- categories valid today for one crew member (inclusive validity)
SELECT cc.CREWCATIDX,
       LTRIM(RTRIM(c.DESC_))                              AS Category_Name,
       CAST(DATEADD(DAY, cc.ACTIVEBEG, '1980-01-01') AS DATE) AS Valid_From,
       CASE WHEN cc.ACTIVEEND = 32767 THEN NULL
            ELSE CAST(DATEADD(DAY, cc.ACTIVEEND, '1980-01-01') AS DATE) END AS Valid_To   -- NULL = open-ended
FROM TSC.dbo.CREWCATEG AS cc
JOIN TSC.dbo.CREWCAT   AS c ON c.CREWCAT = cc.CREWCATIDX
WHERE cc.ID = @crew_id
  AND cc.ACTIVEBEG <= DATEDIFF(DAY, '1980-01-01', GETDATE())
  AND cc.ACTIVEEND >= DATEDIFF(DAY, '1980-01-01', GETDATE())
ORDER BY c.CREWCAT;

-- categories held on a given date (e.g. a pairing date)
DECLARE @d INT = DATEDIFF(DAY, '1980-01-01', '2026-06-23');
SELECT STRING_AGG(LTRIM(RTRIM(c.DESC_)), N' | ') WITHIN GROUP (ORDER BY c.CREWCAT) AS Crew_Categories
FROM (SELECT DISTINCT CREWCATIDX FROM TSC.dbo.CREWCATEG
      WHERE ID = @crew_id AND ACTIVEBEG <= @d AND ACTIVEEND >= @d) AS x
JOIN TSC.dbo.CREWCAT AS c ON c.CREWCAT = x.CREWCATIDX;

-- how many crew hold each category today (aggregate)
SELECT c.CREWCAT, LTRIM(RTRIM(c.DESC_)) AS Category_Name, COUNT(DISTINCT cc.ID) AS Crew_Count
FROM TSC.dbo.CREWCATEG AS cc
JOIN TSC.dbo.CREWCAT   AS c ON c.CREWCAT = cc.CREWCATIDX
WHERE DATEDIFF(DAY, '1980-01-01', GETDATE()) BETWEEN cc.ACTIVEBEG AND cc.ACTIVEEND
GROUP BY c.CREWCAT, c.DESC_
ORDER BY Crew_Count DESC;
```

## 8. Data profile (measured 2026-11-03)
- 31,563 rows; 4,884 distinct crew; 0 rows with `ACTIVEEND < ACTIVEBEG`; 73 zero-length rows (`ACTIVEBEG = ACTIVEEND`, single-day assignment), 167 rows of exactly 2 days.
- `ACTIVEBEG`: 8,355 rows = 0 (since beginning); otherwise min 1991-04-04, max 2027-03-01 (40 rows start in the future).
- `ACTIVEEND`: 13,739 rows = 32767 (open-ended); 17,824 finite ends, between 2006-08-31 and 2027-11-15; 17,650 rows ended before today.
- Valid today (inclusive test): 13,867 rows (13,739 open-ended + 128 finite); 4,721 distinct crew; 1..14 categories per crew, average 2.94.
- (crew, category) pairs with more than one period: 4,009.
- Most frequently held categories (all time): "PNC NON QUALIFIE" (4,502), "PNT NON QUALIFIE" (2,657), "FO en LI - RC" (1,955), "JUNIOR FO" (1,660), "NEW PNC" (1,457), "CPT en LI - RC" (1,388), "ANGLAIS" (1,387), "FRANÇAIS" (1,367). Per-category counts are in `CREWCAT.md`.

## 9. Open questions / confidence
- High: structure, join keys, day-number encoding, `32767`/`0` sentinels, inclusivity of `ACTIVEEND` (consistent with R2's documented assumption and the gap = 1 pattern).
- Medium: the writer of the rows (manual maintenance vs AIMS automatic status categories) is not visible in the repo (inference from the ended-rows pattern).
- Open: whether `rpt.get_crew_categories` (`ACTIVEEND > today`) and R1 (`ACTIVEEND > today` without `ACTIVEBEG`) should be aligned with the inclusive rule used by R2/R0; flagged here as an inconsistency, not changed.
