# ROSTERID  (Table)  - Per-crew roster header (one row per crew member: identity, seniority, roster publish/schedule window, change counter)

## 1. Purpose & business meaning

`TSC.dbo.ROSTERID` is the **header record of each crew member's roster** in AIMS. Where `ROSTER` holds the many daily/leg rows, `ROSTERID` holds exactly **one row per crew member** (6,151 rows = 6,151 distinct `ID`; the same 6,151 `ID`s exist in the crew master view `vvCREWDB`, 0 missing). It carries:

* the crew identity as used by the rostering screens (`ID`, display `NAME`, `SHORTNAME`, `SWIPECARD` badge, mailbox `BOX`): **personal data, not documented by value**;
* the **seniority** used to rank crew (`SENIOR`, `SENGRP`) - R0 outputs it as `SENIORITY` and uses it for draft ordering;
* the **roster window / state of the crew's schedule**: `SCHEBEG`, `SCHEEND` (schedulable range), `PUBLISH` (roster published up to this day), `TRACKUNTIL`, `ACTUALROSTERSTARTDAY`;
* a **change counter** `TRANSCOUNTER` (incremented by AIMS whenever the crew's roster/header is changed - used for optimistic locking / incremental sync; inference from name and values);
* language preferences (`LANG`, `TRNPRFLANG`), a hashed credential (`PASSWORD_`, never to be read) and a packed record `DATA_BEGIN_END` (818 bytes, undecoded).

Grain: one row per crew member (all crew with a roster, active and historical: 2,823 have `SCHEEND >= today`; 2,935 had roster rows in 2026). Lifecycle: created when a crew member is added to AIMS, updated by AIMS on every roster change/publish; planner-assist only reads it (R0 for the name and seniority of candidates).

## 2. Physical facts

* `TSC.dbo.ROSTERID`, user table, **6,151 rows**, 18 columns, collation `SQL_Latin1_General_CP1_CI_AS` for the 4 nchar columns (`NAME`, `SHORTNAME`, `SWIPECARD`, `BOX`).
* **Primary key** (clustered, unique) `ROSTERID_INDEX_0` on `(ID)`.
* **Unique** `ROSTERID_INDEX_1` on `(ID, TRANSCOUNTER)` - covers the "latest version of a crew header" access of AIMS clients.
* Tiny table: scans are cheap. No partitioning.

## 3. Column dictionary

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| ID | int | NO | **Crew member id** (internal AIMS crew id, primary key). Same id as `ROSTER.ID`, `CREWQUAL.ID`, `CREWCATEG.ID`, `vvCREWDB.ID`. | 5..999999 (6,151 distinct). `999999` is the highest value (probably a dummy/system crew; not verified). | R0 `JOIN ROSTERID AS rid ON rid.ID = q.ID` (lines 425 and 677); profiled |
| TRANSCOUNTER | smallint | NO | **Transaction / version counter** of the header: increments on each change of the crew's roster record (inference). | 6..31692, 4,644 distinct values (so it is not a 1..n row version per crew in a fixed range; values are crew specific counters). Not used by any procedure. | naming inference; unique index `(ID, TRANSCOUNTER)`; profiled |
| ACTUALROSTERSTARTDAY | smallint | YES | **First day of the crew's "actual" roster period** (inference): day number since 1980-01-01. All 6,151 rows have a value between 16881 (2026-03-21) and 17097 (2026-10-23); never NULL. Exact business definition unclear (cut-off between actualised/frozen past and open future?). | Day number (`DATEADD(DAY, n, '1980-01-01')`). | naming inference; profiled; not used by any procedure |
| NAME | nchar(100) | YES | Crew member's full display name (surname, first name). **Personal data - not profiled.** Returned by R0 as `Crew_Name`; also the crew-name filter `@CrewNameFilter` (`rid.NAME = @CrewNameFilter`). | free text, space padded | R0 `rid.NAME AS Crew_Name`, `rid.NAME = @CrewNameFilter` |
| SHORTNAME | nchar(12) | YES | Short name / initials used on rosters. **Personal data - not profiled.** | free text | naming inference; present in `vvCREWDB` |
| SWIPECARD | nchar(36) | YES | Badge / swipe-card identifier of the crew member. **Personal identifier - not profiled.** | free text | naming inference; present in `vvCREWDB` |
| SENIOR | smallint | YES | **Seniority number** (rank in the seniority list; lower = more senior is the usual airline convention, not verified here). `9999` = no seniority assigned (484 rows); 5,586 rows have a real value (2,325 distinct, so ranks are shared between categories/groups), `0` for 81 rows. Output by R0 as `SENIORITY` (`rid.SENIOR AS SENIORITY`). | 0..9999 | R0 lines 418/641; profiled (aggregates only) |
| SENGRP | smallint | YES | **Seniority group** (naming inference). Value 0 for 6,136 rows; the 15 other rows carry 15 distinct large values (1, 8088, 8925, 9999, 11462..11489, 12994) that look like day numbers or ids, **not** a small group code. Meaning unclear. | unknown - not used by any procedure | profiled (aggregates) |
| LANG | binary(12) | YES | **Language-skills bitmap** of the crew member (same family as `ROSTER.LANG`, which stores a 10-byte copy). Not decoded here. | bitmap | naming inference |
| TRNPRFLANG | binary(4) | YES | **Preferred training language** (naming inference: "TRN" = training, "PRF" = preferred). | bitmap/code, not decoded | naming inference |
| BOX | nchar(16) | YES | Crew **mailbox / pigeon-hole / box number** (naming inference). Blank for 5,326 of 6,151 rows. | free text | naming inference; profiled (blank count only) |
| PASSWORD_ | binary(32) | YES | Stored credential (hash) for crew self-service access. **Secret - never read, never select.** | binary | naming inference |
| SCHEBEG | smallint | YES | **Start of the schedulable period** of the crew member (day number). `0` on all 6,151 rows (= no lower bound). | day number, 0 = open | naming inference; profiled |
| SCHEEND | smallint | YES | **End of the schedulable period / last scheduled day** of the crew member (day number). `0` for 42 rows (no end), max 17166 = 2026-12-31 (end of the current scheduling year); 2,823 rows have `SCHEEND >= 17108` (today, 2026-11-03), i.e. crew still scheduled. | day number | naming inference; profiled |
| ACTDATA | smallint | YES | Activation / data date (inference). `0` for 4,348 rows, otherwise up to 10714 (2009-05-02): looks like a legacy date. Meaning unclear. | day number | profiled; unknown - not used by any procedure |
| PUBLISH | smallint | YES | **Roster published up to this day** (day number): the last day of the crew member's published roster. Max 17136 = 2026-12-01 (= today + 28 days, i.e. rosters are published 28 days ahead); `0` for 36 crew; 6,115 positive (min 7456 = 2000-05-31). | day number | naming inference; profiled |
| TRACKUNTIL | smallint | YES | **Roster changes are tracked (change-notified) until this day** (inference): `0` for 617 rows, max 17094 (2026-10-20 = about 14 days before today), min positive 9404. Semantics unclear. | day number | naming inference; profiled |
| DATA_BEGIN_END | binary(818) | YES | Packed AIMS record with the remaining roster-header attributes (preferences, limits, etc.). Not decoded by any procedure. | unknown - not used by any procedure | columns.json |

All 18 columns of `columns.json` are covered (ID, TRANSCOUNTER, ACTUALROSTERSTARTDAY, NAME, SHORTNAME, SWIPECARD, SENIOR, SENGRP, LANG, TRNPRFLANG, BOX, PASSWORD_, SCHEBEG, SCHEEND, ACTDATA, PUBLISH, TRACKUNTIL, DATA_BEGIN_END).

## 4. Keys & relationships

* **Natural/primary key**: `ID` (unique, clustered).
* **ROSTERID 1 : N ROSTER** on `ROSTERID.ID = ROSTER.ID`. Every one of the 2,935 crew with 2026 roster rows has a header (0 missing). Used with the exact predicate `INNER JOIN TSC.dbo.ROSTERID AS rid ON rid.ID = q.ID` (R0 425, 677) where `q` = `CREWQUAL`.
* **ROSTERID 1 : N CREWQUAL** on `rid.ID = q.ID` (crew qualifications/base/aircraft/position ranges).
* **ROSTERID 1 : 1 vvCREWDB** on `ID` (the crew master view exposes `NAME`, `SHORTNAME`, `SWIPECARD`, ... and personal data; all 6,151 ids match).
* **ROSTERID 1 : N CREWCATEG** (`ccSub.ID = q.ID`, crew categories).
* `TRANSCOUNTER` is part of the unique index `(ID, TRANSCOUNTER)` only; it is not a foreign key.
* Cardinality ROSTERID.ID -> HOTAC.CREWID is 1:N for positive `CREWID`.

## 5. Encoding conventions & gotchas

1. **Day numbers** (`ACTUALROSTERSTARTDAY`, `SCHEBEG`, `SCHEEND`, `ACTDATA`, `PUBLISH`, `TRACKUNTIL`): days since 1980-01-01; `0` = unset / unbounded, not 1980-01-01.
2. **Personal data**: `NAME`, `SHORTNAME`, `SWIPECARD`, `BOX`, `PASSWORD_`, `LANG` must not be selected into reports or logs; use `ID` as the crew key in all planner-assist output unless a display name is required (R0 returns `Crew_Name` for the draft list).
3. **`SENIOR = 9999` is "unset"** (484 crew), not the least senior real rank; filter `SENIOR BETWEEN 1 AND 9998` for real ranks. `SENIOR = 0` also occurs (81 crew).
4. **Header exists for ex-crew too** (6,151 total vs ~2,900 active): filter on `SCHEEND >= @today OR SCHEEND = 0` or on `ROSTER`/`CREWQUAL` activity ranges to restrict to current crew; R0 restricts through `CREWQUAL.ACTIVBEG/ACTIVEND` instead.
5. **PUBLISH is a horizon, not a flag**: ROSTER has no "published" column; a roster row is visible to crew when `LEG_DAY <= ROSTERID.PUBLISH` (inference), so rows beyond `PUBLISH` are working drafts of planners.
6. No soft-delete column; no ACTIVEBEG/ACTIVEEND columns.
7. `LANG` is `binary(12)` here but `binary(10)` in `ROSTER`.

## 6. How the planner-assist procedures use it

* **dbo.R0_GetDraftList** (only user): (a) candidate pool `#CrewPool` = `CREWQUAL q JOIN ROSTERID rid ON rid.ID = q.ID` ... filtered by base, aircraft, position, activity range, optional `rid.NAME = @CrewNameFilter`; the pool selects `rid.NAME AS Crew_Name` and `rid.SENIOR`; (b) `OnLegs`: `INNER JOIN ROSTERID AS rid ON rid.ID = q.ID` to output `Crew_Name` and `rid.SENIOR AS SENIORITY` on every roster row. `SENIORITY` is the tie-breaker of the PNT/PNC draft order (call order).
* R3/R3_Batch/R4/R5/`rpt.*`: do **not** read ROSTERID; they validate crew existence against `vvCREWDB` (`CREW_NOT_FOUND`).

## 7. Typical query patterns

```sql
-- 1. Seniority of a set of crew ids (no personal columns)
SELECT rid.ID, rid.SENIOR
FROM TSC.dbo.ROSTERID rid
WHERE rid.ID IN (@id1, @id2) AND rid.SENIOR BETWEEN 1 AND 9998;

-- 2. Crew still schedulable on a date, with their roster publish horizon
SELECT rid.ID, DATEADD(DAY, rid.PUBLISH, '1980-01-01') AS published_until
FROM TSC.dbo.ROSTERID rid
WHERE (rid.SCHEEND = 0 OR rid.SCHEEND >= DATEDIFF(DAY, '1980-01-01', @date));

-- 3. Crew with roster rows in a window (restricting ROSTER with the mandatory LEG_DAY range)
SELECT DISTINCT r.ID
FROM TSC.dbo.ROSTER r
JOIN TSC.dbo.ROSTERID rid ON rid.ID = r.ID
WHERE r.LEG_DAY BETWEEN DATEDIFF(DAY,'1980-01-01',@from) AND DATEDIFF(DAY,'1980-01-01',@to);
```

## 8. Data profile (measured 2026-11-03)

* 6,151 rows, 6,151 distinct `ID` (5..999999); 6,151 / 6,151 present in `vvCREWDB`; 2,935 / 2,935 crew of the 2026 roster present here.
* `TRANSCOUNTER`: 6..31,692, 4,644 distinct.
* `ACTUALROSTERSTARTDAY`: min 16881 (2026-03-21), max 17097 (2026-10-23), no NULL.
* `SENIOR`: 5,586 rows with a real rank (1..9998, 2,325 distinct), 484 with 9999, 81 with 0. `SENGRP`: 6,136 zeros + 15 distinct non-zero singletons.
* `SCHEBEG` = 0 on all rows; `SCHEEND` max 17166 (2026-12-31), 42 zeros, 2,823 `>= 17108`.
* `PUBLISH`: max 17136 (2026-12-01), 36 zeros; `TRACKUNTIL`: max 17094 (2026-10-20), 617 zeros; `ACTDATA`: 4,348 zeros, max 10714 (2009-05-02).
* `BOX` blank on 5,326 rows.

## 9. Open questions / confidence

* **High**: grain (one row per crew), `ID` key, joins to `ROSTER`/`CREWQUAL`/`vvCREWDB`, use of `NAME` and `SENIOR` by R0.
* **Medium (inferred from names and value ranges)**: `PUBLISH` = published-through day (28 days ahead of today supports it), `SCHEEND` = end of schedulable period, `TRANSCOUNTER` = change counter, `TRACKUNTIL`, `ACTUALROSTERSTARTDAY`.
* **Unknown**: `SENGRP` (15 odd large values), `ACTDATA`, `LANG`/`TRNPRFLANG` bit layouts, `BOX`, `DATA_BEGIN_END` content, whether `SENIOR` is ascending-is-senior (R0 uses it as given).
* `ACTUALROSTERSTARTDAY` being >= 2026-03-21 for every crew suggests a periodic/global process sets it (the same cut-off per crew); this is a guess.
