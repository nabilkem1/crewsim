# ROSTERDT  (Table)  - Roster detail records: typed attribute rows (RECTYPE / VALUE1 / VALUE2) attached to a roster element; carries the DRAFT marker (RECTYPE 21)

> Added 2026-11-03 from `c:\dev\crewsim\backlog\DRAFTPNCPNT.sql` (copy in `..\queries\DRAFTPNCPNT.original.sql`) plus catalog metadata and read-only aggregate profiling. This object is **not used by any procedure in `database\dbo` / `database\rpt`**; its meaning is established for RECTYPE 21 only. See also [`../drafts.md`](../drafts.md).

## 1. Purpose & business meaning

`TSC.dbo.ROSTERDT` ("roster detail") is an **entity-attribute-value side table of [ROSTER](ROSTER.md)**. Each row says: *for crew member `ID`, on roster element (`LEG_DAY, LEG_DEP, LEG_CARRIER, LEG_FLT, LEG_LEGCD`, duty instance `DUTYDAY/DUTYNO`, `GRDDUTYBEG`), the attribute of type `RECTYPE` has value `VALUE1` (and optionally `VALUE2`)*. The table has **26.9 million rows** (about twice ROSTER) because one roster element can carry several attributes at once (one row per `RECTYPE`).

**Grain:** one row per (roster element key, `RECTYPE`) - the primary key is the ROSTER key plus `RECTYPE`.

Two levels of rows exist, distinguished by `LEG_FLT`:

| Level | How to recognise | Meaning |
|---|---|---|
| **Element level** | `LEG_FLT <> 0` (positive = flight, negative = ground activity code) | attribute of one roster element: the full ROSTER key matches exactly one ROSTER row (verified: 645 of 645 January-2026 draft rows matched) |
| **Day level** | `LEG_FLT = 0` (`LEG_DEP` blank, `LEG_CARRIER = 0`, `LEG_LEGCD` blank, `DUTYNO = 0`, `DUTYDAY = LEG_DAY`, `GRDDUTYBEG = 0`) | attribute of the **crew-day** as a whole. There is **no ROSTER row with this key** (0 of 37 matched); the only link to ROSTER is `ID + LEG_DAY` |

**What is known about `RECTYPE`** (only from the backlog query and its Snowflake origin `DMT_CREW.DMT_DRAFTS_PNT_PNC`):

* `RECTYPE = 21` is the **"assignment / draft type" attribute of a roster element**, `VALUE1` being its code. The query decodes four values as drafts:

| `VALUE1` (RECTYPE 21) | Label in the query | Crew group (verified via `ROSTER.POS`) | Rows in 2026 |
|---|---|---|---|
| 15 | PNC DRAFT A LA BASE (cabin crew drafted at their base) | PNC only (71 of 71 sampled legs, `POS` not in 1,2,4) | 405 leg rows (+ day-level) |
| 16 | PNC DRAFT OUT OF BASE / HORS BASE | PNC only | 73 leg rows (+ day-level) |
| 19 | DRAFT PILOTE (pilot draft) | PNT only (`POS` in 1,2,4) | 6,250 leg rows (+ day-level) |
| 20 | DRAFT PILOTE SUR VACANCES (pilot drafted while on vacation) | PNT only | 60 leg rows (+ day-level) |

* Other `VALUE1` values of `RECTYPE 21` exist (1-14, 17, 18, 21-24, 27; e.g. 1 = 67k rows, 11 = 111k, 8 = 48k, 2 = 24k) but **no code or lookup in the repo or in `vvFMSCodes` decodes them**. They are most probably the other values of the same "how was this roster element assigned" list (company-defined), but that is an inference - **do not treat them as non-drafts or as anything else**.
* Every other `RECTYPE` (see section 8) is **undecoded**. Do not guess meanings from the number.

Lifecycle: written by AIMS when a planner assigns/changes a roster element (an AIMS trigger `ROSTERDT_TRIGGER` exists on the table, enabled, definition unreadable; sibling `ROSTER_TRIGGER` on ROSTER). planner-assist never writes it. History starts at day 6946 (1999-01) and runs to day 17652 (future planning rows, up to 2028).

## 2. Physical facts

* `TSC.dbo.ROSTERDT`, user table, **26,927,022 rows** (partition stats, 2026-11-03), 12 columns, no declared FKs, no descriptions.
* **Primary key (unique clustered) `ROSTERDT_INDEX_0`**: `(ID, LEG_DAY, LEG_DEP, LEG_CARRIER, LEG_FLT, LEG_LEGCD, DUTYNO, DUTYDAY, GRDDUTYBEG, RECTYPE)` = the ROSTER primary key plus `RECTYPE`.
* Secondary (non-unique) indexes and the access path each gives:
  * `ROSTERDT_INDEX_1 (ID, LEG_DAY, RECTYPE)` and `ROSTERDT_INDEX_5 (ID, RECTYPE, LEG_DAY)` - attributes of one crew in a date range.
  * `ROSTERDT_INDEX_2 (RECTYPE, LEG_DAY, ID)` and `ROSTERDT_INDEX_3 (LEG_DAY, RECTYPE, ID)` - **all crew having a given RECTYPE in a date range** (this is what the draft extraction needs).
  * `ROSTERDT_INDEX_4 (DUTYDAY, DUTYNO, ID)` - attributes of every crew member on one pairing instance.
* Always restrict by `RECTYPE` **and** an integer `LEG_DAY` range. The backlog query wraps `LEG_DAY` in `CAST(DATEADD(...))` which prevents the index seek (it works but scans); compare `LEG_DAY` with day numbers instead.

## 3. Column dictionary

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| ID | int | NO | Crew member identifier (same key as `ROSTER.ID`, `ROSTERID.ID`, `vvCREWDB.ID`). | internal crew id | backlog query `RO.ID = RDT1.ID`; same name/type as ROSTER |
| LEG_DAY | smallint | NO | Day (AIMS day number) of the roster element the attribute belongs to; for day-level rows, the crew-day. | days since 1980-01-01 (2026-01-01 = 16802, 2026-11-03 = 17108); range 6946..17652 | backlog query converts with `DATEADD(DAY, LEG_DAY, '1980-01-01')`; profiled |
| LEG_DEP | nchar(4) | NO | Departure airport of the element (ROSTER.LEG_DEP). Blank on ground activities and on day-level rows. | station code, blank | backlog join; profiled (blank on all day-level draft rows) |
| LEG_CARRIER | smallint | NO | Carrier id of the flight (ROSTER.LEG_CARRIER); 0 on day-level rows and activities. | 1 = home carrier (see `vvCarriers`) | backlog join; profiled |
| LEG_FLT | smallint | NO | Flight number (>0), activity code id (<0, = CRCODES.ID, which is itself <= 0) or **0 = day-level row**. The backlog query uses `LEG_FLT <> 0` vs `= 0` to split element-level from day-level rows. | >0 flight, <0 ground activity, 0 day-level | backlog `RDT1 / RDT2`; profiled |
| LEG_LEGCD | nchar(1) | NO | Leg code of the flight (ROSTER.LEG_LEGCD, A-D/blank). | blank on non-flights / day-level | backlog join |
| DUTYNO | bigint | NO | Duty / pairing number of the element = `CRROUTE.CROUTE`; negative = activity (stand-alone); **0 on day-level rows**. | see ROSTER.DUTYNO | profiled: DUTYNO > 0 on 642 of 645 January draft leg rows (3 are stand-alone activities with DUTYNO < 0), 0 on all day-level rows |
| DUTYDAY | smallint | NO | Start day (day number) of the pairing instance = `CRROUTE.CDATE`; equals `LEG_DAY` on day-level rows. | day number | profiled |
| GRDDUTYBEG | smallint | NO | Ground-duty begin of the ROSTER row (key part so that two same-day activities do not collide); 0 for flights and day-level rows. | UTC minutes of the day, 0 = none | PK of ROSTER; profiled (0 on 561 of 569 PNT leg draft rows incl. ground) |
| RECTYPE | smallint | NO | **Attribute type** (which property of the roster element this row holds). Only `21` (assignment/draft type) is decoded; ~50 distinct values exist. | see section 8; 21 = draft/assignment type | backlog `WHERE RECTYPE = 21` |
| VALUE1 | bigint | YES | Primary value of the attribute. For RECTYPE 21: the **draft/assignment code** (15, 16, 19, 20 = drafts). For other RECTYPEs the type (flag 0/1, minutes, codes, packed numbers) differs and is not decoded. | RECTYPE 21: 1..24, 27 | backlog `CASE WHEN VALUE1 = 15 ...`; profiled |
| VALUE2 | bigint | YES | Secondary value. For RECTYPE 21 it is **always 0** (never NULL in 2026 data). | RECTYPE 21: 0 | backlog selects it, never uses it; profiled |

Not null on every column except `VALUE1`/`VALUE2`; no rows with NULL `VALUE2` found in 2026.

## 4. Keys & relationships

* **Natural key:** the ROSTER key + `RECTYPE` (the PK). A roster element can have one row per `RECTYPE`; for `RECTYPE = 21` there is at most **one** `VALUE1` per element.
* **To [ROSTER](ROSTER.md)** (element-level rows, `LEG_FLT <> 0`) - **N:1 on the full ROSTER key**, verified 1:1 (645/645 matched):
  `r.ID = d.ID AND r.LEG_DAY = d.LEG_DAY AND r.LEG_DEP = d.LEG_DEP AND r.LEG_CARRIER = d.LEG_CARRIER AND r.LEG_FLT = d.LEG_FLT AND r.LEG_LEGCD = d.LEG_LEGCD AND r.DUTYNO = d.DUTYNO AND r.DUTYDAY = d.DUTYDAY AND r.GRDDUTYBEG = d.GRDDUTYBEG`.
  The backlog query joins on `ID + leg key` only (omits `DUTYNO, DUTYDAY, GRDDUTYBEG`). For flights this is still 1:1 in January 2026 (24,476 flight rows = 24,476 distinct `ID + leg key`), but ground activities (negative `LEG_FLT`) can repeat the same key with different `GRDDUTYBEG`, which would fan out.
* **To ROSTER (day-level rows, `LEG_FLT = 0`)** - only `ID + LEG_DAY` (**1:N** to that crew's roster rows of the day). The backlog query's `RF_2` does exactly this, so a day-level draft marker is **repeated on every roster row of the crew-day** (11 distinct crew-days -> 59 output rows in January 2026 for the join alone) and shows up even for rows (activities, other legs) that were not themselves drafted.
* **To pairing:** via the ROSTER row, `DUTYDAY, DUTYNO` = `CRROUTE.CDATE, CRROUTE.CROUTE` (all 637 flight draft legs of January 2026 resolve to a CRROUTE row). `ROSTERDT.DUTYDAY/DUTYNO` can be used directly (index `ROSTERDT_INDEX_4`).
* **To flight data:** `ROSTER` leg key -> [LEGMAIN](LEGMAIN.md) / [LEGTIMES](LEGTIMES.md) (all 637 flights found in LEGMAIN; 78 draft flight legs have no LEGTIMES row = not yet flown / not operated).
* **To crew:** `ID` -> `ROSTERID.ID` -> `vvCREWDB.ID`.

## 5. Encoding conventions & gotchas

1. **Day-level vs element-level** is decided by `LEG_FLT = 0`. Do not join day-level rows on the leg key - they never match.
2. **Drafts are many rows per pairing.** A draft is recorded **per leg** (element), not per pairing: January 2026 shows 561 PNT draft legs spread over 320 pairings for 202 crew; a crew may be drafted on some legs of a pairing only. Count pairings with `COUNT(DISTINCT DUTYDAY, DUTYNO)`, not rows.
3. **PNC vs PNT is implicit** in the code: 15/16 = cabin crew (PNC), 19/20 = pilots (PNT). Verified against `ROSTER.POS` (positions 1, 2, 4 = PNT per `position_category`): no crossover in January 2026.
4. **Untimed / non-flight draft rows exist:** 8 of the 645 January leg rows have negative `LEG_FLT` (ground legs / activities), so no LEGMAIN/LEGTIMES row and no departure time. Filter `LEG_FLT > 0` for flights only.
5. **Time of the drafted leg** is not in ROSTERDT: derive `ACTUAL_DEPARTURE` from LEGTIMES/LEGMAIN, priority `OPSATD -> BLOF -> ETD -> STD`, as UTC minutes after midnight of `LEG_DAY` (see [LEGTIMES](LEGTIMES.md)). Planned (future) legs only have `STD`.
6. **Draft is recorded at assignment time**: markers exist for future days (max `LEG_DAY` 17125 = 2026-11-20 for code 20) - they are the planned roster, not proof that the draft was flown.
7. **Large and mixed table:** 26.9M rows, ~50 RECTYPEs; always filter `RECTYPE` first (indexes 2/3 start with it) plus a `LEG_DAY` range.
8. **Collation / types:** `LEG_DEP`/`LEG_LEGCD` are nchar (blank = empty string, not NULL).
9. Zero-valued `VALUE2` is not "missing" for RECTYPE 21; it is the constant 0.

## 6. How the planner-assist procedures use it

**No procedure in `database\dbo` or `database\rpt` reads ROSTERDT.** It is the source of the *recorded* draft status used by the Snowflake mart `PRD_DVL.DMT_CREW.DMT_DRAFTS_PNT_PNC` (referenced in the header of the backlog query). Relation to the procedures:

* `R0_GetDraftList` **predicts / ranks who could be drafted** onto a pairing (PNT draft order of "Procedure Draft PNT", 13 steps, using `ROSTER`, qualifications, `draft_order10_crews`, ...). It does not read what AIMS actually recorded.
* `ROSTERDT` (RECTYPE 21, VALUE1 in 15/16/19/20) **records what has actually been drafted** in AIMS. Use it as ground truth to validate or back-test R0 (e.g. compare R0's candidate order with who was really drafted on that pairing), or to exclude already-drafted legs.
* `R4/R5/R3` do not use it. A drafted leg may show up in their results simply as ordinary ROSTER rows.

## 7. Typical query patterns

Drafted flight legs of a month, with pairing and actual departure (tested; full file: `..\queries\drafted_legs.sql`):

```sql
DECLARE @B INT = DATEDIFF(DAY,'1980-01-01','2026-01-01'), @E INT = DATEDIFF(DAY,'1980-01-01','2026-01-31');
SELECT d.ID, DATEADD(DAY,d.LEG_DAY,'1980-01-01') AS LEG_DATE, r.POS, d.VALUE1 AS DRAFT_CODE,
       cr.DESC_ AS PAIRING_NAME, d.LEG_CARRIER, d.LEG_FLT, d.LEG_DEP, lm.ARR
FROM TSC.dbo.ROSTERDT d
JOIN TSC.dbo.ROSTER r ON r.ID=d.ID AND r.LEG_DAY=d.LEG_DAY AND r.LEG_DEP=d.LEG_DEP AND r.LEG_CARRIER=d.LEG_CARRIER
                     AND r.LEG_FLT=d.LEG_FLT AND r.LEG_LEGCD=d.LEG_LEGCD AND r.DUTYNO=d.DUTYNO AND r.DUTYDAY=d.DUTYDAY AND r.GRDDUTYBEG=d.GRDDUTYBEG
LEFT JOIN TSC.dbo.CRROUTE cr ON cr.CDATE=r.DUTYDAY AND cr.CROUTE=r.DUTYNO
LEFT JOIN TSC.dbo.LEGMAIN lm ON lm.DAY=r.LEG_DAY AND lm.DEP=r.LEG_DEP AND lm.CARRIER=r.LEG_CARRIER AND lm.FLT=r.LEG_FLT AND lm.LEGCD=r.LEG_LEGCD
WHERE d.RECTYPE=21 AND d.VALUE1 IN (15,16,19,20) AND d.LEG_FLT>0 AND d.LEG_DAY BETWEEN @B AND @E;
```

Number of drafts per type per year (cheap, uses index 2):

```sql
SELECT YEAR(DATEADD(DAY,LEG_DAY,'1980-01-01')) AS yr, VALUE1 AS draft_code, COUNT(*) AS rows_, COUNT(DISTINCT ID) AS crews
FROM TSC.dbo.ROSTERDT WHERE RECTYPE=21 AND VALUE1 IN (15,16,19,20) AND LEG_DAY BETWEEN 16802 AND 17166 GROUP BY YEAR(DATEADD(DAY,LEG_DAY,'1980-01-01')), VALUE1;
```

Mandatory filters: `RECTYPE = 21`, `VALUE1 IN (15,16,19,20)`, an integer `LEG_DAY` range, and `LEG_FLT > 0` (or `<> 0`) unless you explicitly want day-level markers (`LEG_FLT = 0`).

## 8. Data profile (measured 2026-11-03)

Draft rows by year (RECTYPE 21, `VALUE1` 15/16/19/20, element + day level, `LEG_DAY` >= 14000):

| Year | 15 PNC base | 16 PNC out of base | 19 PNT | 20 PNT on vacation |
|---|---|---|---|---|
| 2018 | 1,184 | 184 | 726 | - |
| 2019 | 940 | 213 | 2,308 | - |
| 2020 | 880 | 47 | 796 | - |
| 2021 | 396 | 2 | 228 | - |
| 2022 | 1,915 | 282 | 2,376 | 2 |
| 2023 | 719 | 215 | 3,072 | 1 |
| 2024 | 528 | 219 | 4,020 | 4 |
| 2025 | 466 | 153 | 3,719 | 52 |
| 2026 | 445 | 238 | 6,500 | 85 |

January 2026 (days 16802-16832): 645 element-level draft rows (71 / 1 / 561 / 4 element-level rows for 15 / 16 / 19 / 20; 637 flights + 8 ground), 245 crew, 341 distinct pairing names; 37 day-level markers; 78 draft flight legs without LEGTIMES (76 PNT, 1 PNC, 1 vacation draft; not flown / not operated); 0 cancelled drafted flights; 2 PNT draft legs are return legs (`DEP = ARR`). 2026 whole year: 480 day-level markers for 390 crew.
Day-level markers (2026 sample, days 16802-17050) always coincide with ROSTER flight rows of the same crew-day, a few with ground-in-pairing rows.

RECTYPE inventory for 2026 (`LEG_DAY` 16802..17166; **meaning undecoded except 21**):

| RECTYPE | rows 2026 | day-level rows | VALUE1 distinct (min..max) | note |
|---|---|---|---|---|
| 1 | 217,973 | 0 | 2 (0..1) | flag |
| 6 | 4,892 | 0 | 31 (1..148) | |
| 15 / 16 | 22,315 / 22,312 | 0 | 2 (0..1) | co-occur with draft rows (165/163 rows on drafted legs in Jan) |
| **21** | 31,769 | 10,242 | 19 (1..24) | **assignment/draft type** |
| 22 | 6,091 | 0 | 1 (1) | |
| 23, 24 | 5 each | 0 | 1 (0) | |
| 43 | 9,727 | 0 | 3,784 (24,195,420..24,675,540) | packed value |
| 100, 103, 108, 109, 111, 123, 221 | 14 / 6,282 / 53 / 169,253 / 7 / 147,326 / 137 | 0 | small | flags / small codes |
| 106 | 49,778 | 49,744 | 1 (0) | mostly day-level |
| 201, 203, 230, 301-304 | 117 / 636 / 33,580 / 9,456 / 335 / 653 / 7,441 | all day-level | 1..173 | |
| 350, 355 | 3,434 / 4 | 0 | 177 (-60..1430) / 2 | looks like minutes |
| 1106, 1111, 1112, 1113, 1119, 1243, 1244 | 384,656 / 248,897 / 202,944 / 155,616 / 251,384 / 20,955 / 21,855 | all day-level | up to 6,489 distinct | numeric day-level quantities |
| other all-time RECTYPEs | 14, 18, 19, 30, 101, 104, 105, 107, 113, 202, 1009, 1108, 1109, 1125, 1240, 1241, 1248 (none or few rows in 2026) | | | |

Pattern observed (not a rule): RECTYPE >= 201 are day-level in 2026 data (all rows have `LEG_FLT = 0`), RECTYPE < 200 are mostly element-level.

## 9. Open questions / confidence

* **High:** structure, keys, level split (day vs element), RECTYPE 21 + VALUE1 15/16/19/20 = the four draft categories, PNC/PNT split, join to ROSTER/CRROUTE/LEGMAIN/LEGTIMES (profiled).
* **Medium:** that ROSTERDT is an AIMS-maintained EAV extension of ROSTER (trigger present, same key); that day-level markers mean "crew drafted that day" (consistent with the backlog's intent and the observation that the crew-day always has flights, but the exact AIMS behaviour of a day-level draft is not documented).
* **Unknown:** the meaning of the other `VALUE1` codes of RECTYPE 21 (1-14, 17, 18, 21-24, 27) and of **every other RECTYPE**; whether `VALUE2` is ever non-zero for RECTYPE 21 in older years; whether a draft marker is removed when the draft is cancelled (the table shows planned future rows); the meaning of "A LA BASE / HORS BASE" geography (base of the crew vs base of the pairing) - the data do not say.
* **Open for the business:** how the Snowflake column `CREW_CODE` maps to AIMS (probably the crew `ID` or an attribute of `ROSTERID`; not profiled to avoid personal data), and whether `ACTUAL_DEPARTURE_DATE_UTC` there uses the OPSATD -> BLOF -> ETD -> STD priority used by R3/R4.


