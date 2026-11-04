# vvCREXPREC  (View)  - Crew expiry records: per crew member and expiry type, last check date and computed expiry date

## 1. Purpose & business meaning
`TSC.dbo.vvCREXPREC` is the AIMS view over the **crew expiry record** table: for each crew member it holds one row per expiry type (`EXPI`) the crew member has a record for, with the **date of the last check/completion** (`CHKLAST`) and the **date on which the certificate expires** (`EXPIDATE`).
It is the "when does crew member X's medical / PPC / route check / dangerous-goods / passport / landing currency expire?" table. The *definition* of each expiry type (name, applicable positions/aircraft/categories, validity length) is in `EXPI`.
Grain: (crew member, expiry type); measured unique (0 duplicate pairs). A crew member has between 1 and 129 records (average 26.3); 5,511 of the 6,151 crew in `vvCREWDB` have at least one.
Lifecycle: records are created/updated by AIMS when a renewing activity (training/check roster code, see `EXPI.CREWCODE1..20`) is completed or by manual entry by crew-training administrators (`MAN_EXPIDATE`), and by interfaces (e.g. passport / ETA dates). Old expiry types keep their records (89,782 of the 145,012 records belong to ended `EXPI` definitions) and records of crew who left remain.
Used by planner-assist to flag candidates whose certificate would be expired at the end of a pairing (`R0_GetDraftList`) and to list a crew member's certificates (`rpt.get_crew_certifications`).

## 2. Physical facts
- `TSC.dbo.vvCREXPREC`, **VIEW** (definition not retrievable - `view_defs.json` has `def = null`; no row count or index metadata). Measured: **145,012 rows**, 5,511 distinct `CREW_ID`, 178 distinct `EXPIIDX`.
- Candidate key (`CREW_ID`, `EXPIIDX`) is unique in the data (0 duplicates), but nothing guarantees it (no constraint on a view; the underlying table's key is unknown).
- No index information: always filter by `CREW_ID` (the planner does `WHERE A.CREW_ID = @crew_id` or joins on the candidate pool) and by `EXPIIDX`; a full scan of 145k rows is acceptable but avoid joining it unfiltered to big tables.
- `FUTURE` is a 100-byte reserved area (all zero).

## 3. Column dictionary
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| CREW_ID | int | Y (never null in the data) | Crew member internal AIMS id (same id as `vvCREWDB.ID`, `ROSTER.ID`, `CREWQUAL.ID`, `CREWCATEG.ID`) | integer; 0 NULL, 0 orphans vs `vvCREWDB` | profiled; `R0_GetDraftList.sql` line 569 (`A.CREW_ID = cp.ID`); `rpt.get_crew_certifications.sql` line 99 |
| EXPIIDX | smallint | Y (never null) | Expiry type number = `EXPI.EXPI` | 178 distinct values; 0 orphans vs `EXPI` | profiled; `R0_GetDraftList.sql` line 571 (`cr.EXPI = A.EXPIIDX`) |
| CHKLAST | smallint | Y | Date of the **last check / completion** of the item (the date from which the validity period runs). For document-type expiries without a validity length (`EXPI.MAXDUE = 0`, e.g. passport `PASS`, `MOT`, `BKLT`) it is usually 0 and the expiry date is entered directly; for the UK ETA (`UKETA`) it appears to hold the authorisation end date itself (inference: it equals `EXPIDATE` in 2,424 of 2,904 records) | AIMS day number = days since **1980-01-01**; `0` = never checked / not set (12,862 records). Range 1987-01-01 .. 2036-10-14 (2,416 records are dated in the future: 2,413 `UKETA`, 2 `MOT`, 1 `FAIDI`) | profiled; `rpt.get_crew_certifications.sql` lines 96, 175 (commented use) |
| EXPIDATE | smallint | Y | **Expiry date**: last day on which the certificate is still valid (inclusive: R0 treats `EXPIDATE < pairing end day` as expired, so an item expiring on the last day of the pairing is not flagged) | same day number encoding. `0` = no expiry date set (5,626 records); `32767` = never expires (2,682 records, = 2069-09-17 sentinel); finite values 1987-01-01 .. 2050-12-31 | profiled; `R0_GetDraftList.sql` lines 564, 569; `rpt.get_crew_certifications.sql` line 97 |
| GRACEDATE | smallint | Y | Grace/extension date. Sparse: non-zero in only 161 records (86 MED, 21 BKLT, 11 MOT, 11 RC332, ...), and in 142 of them it is *earlier* than `EXPIDATE`, so it is not a simple "extended deadline" - meaning unclear. Not used by any procedure | day number; 0 = none (144,851 records); max day 25932 = 2050-12-31 | profiled; unknown semantics |
| MAN_EXPIDATE | tinyint | Y | Origin/override flag of `EXPIDATE`: `0` = computed automatically from `CHKLAST` + the rule of `EXPI` (127,755 records), `1` = expiry date set manually (13,783), `10` = another manual/special origin (3,474; exact meaning unknown) | 0, 1, 10 | profiled (manual flag is concentrated on `PASS`, `MED`, `BKLT`); not used by any procedure |
| FUTURE | varbinary(100) | Y | Reserved area of the AIMS record | 100 bytes, always 0 | profiled; unknown - not used by any procedure |

## 4. Keys & relationships
- Candidate key: (`CREW_ID`, `EXPIIDX`).
- `vvCREXPREC.EXPIIDX` -> `EXPI.EXPI` (N:1). Predicate in code: `INNER JOIN #CertRules cr ON cr.EXPI = A.EXPIIDX` (`R0_GetDraftList.sql` lines 570-571, #CertRules is a filtered copy of `EXPI`); `LEFT OUTER JOIN TSC.dbo.EXPI C ON A.EXPIIDX = C.EXPI` (`rpt.get_crew_certifications.sql` line 100).
- `vvCREXPREC.CREW_ID` -> `vvCREWDB.ID` (N:1): `LEFT OUTER JOIN TSC.dbo.VVCREWDB B ON B.ID = A.CREW_ID` (`rpt.get_crew_certifications.sql` line 99); also = `CREWQUAL.ID`, `CREWCATEG.ID`, `ROSTER.ID`, `ROSTERID.ID`.
- To `CREWQUAL`: the planner does not join on a column; it combines the crew member's qualification (position, aircraft, via the candidate pool) with the type's position/aircraft bitmaps (`R0_GetDraftList.sql` lines 568-587) or, in `rpt.get_crew_certifications`, `INNER JOIN (SELECT DISTINCT POS, AC, ID, CWBASE FROM CREWQUAL WHERE <not ended>) cq ON cq.ID = A.CREW_ID`.
- Cardinalities: crew 1:N records; expiry type 1:N records.

## 5. Encoding conventions & gotchas
- **Day numbers since 1980-01-01** (not yyyymmdd). Display with `CAST(DATEADD(DAY, n, '1980-01-01') AS DATE)`; compare with today via `DATEDIFF(DAY, '1980-01-01', GETDATE())`.
- **Sentinels in `EXPIDATE`:** `0` = no expiry date (not set / not applicable) and `32767` = never expires (2069-09-17). **Always exclude both when you want "expired" or "expiring" certificates**, otherwise `EXPIDATE = 0` rows appear as "expired in 1980".
  The current R0 code does not exclude 0: its `A.EXPIDATE < @PairingEndNum` test also matches `EXPIDATE = 0` records of live types (measured: 1,065 of 54,052 records on live, non-excluded types for all crew; 1,283 records of live types for crew with a valid qualification today), which would print "(1980-01-01)" in `Expired_Cert_List`. This is a latent false-positive path in the existing procedure (observation, not a change).
- **`CHKLAST = 0`** means "no check recorded" (12,862 records) - not 1980-01-01. For `UKETA`/document types `CHKLAST` can be in the future.
- **Ended types:** 89,782 of the 145,012 records belong to expiry types that are no longer live (`EXPI.EFFECTIVE_END <> 0`); the planner restricts to `EXPI.EFFECTIVE_END = 0` and a non-blank `SHORTDESC`, and (R0) to `SHORTDESC NOT IN ('WB','IFRLIC','SIMDUT')`.
- **Applicability is not in this view.** A record exists for a crew member even if the type no longer applies to his position/aircraft/category (e.g. after promotion). Check applicability with the `EXPI` bitmaps as R0 does, otherwise you will list irrelevant "expired" items (for live types and crew with a valid qualification today: 9,035 records of 39,918 are past due, 2,722 crew; many are non-applicable or historical items).
- **Crew who left** keep their records (category 222 "No longer with Air Transat" has 325 assignments); restrict to crew with a valid `CREWQUAL` row to talk about the active workforce.
- **View, no statistics:** filter by `CREW_ID` first.
- Personal data caution: the view contains per-person medical/passport dates; report aggregates (counts per certificate type), never individual rows, in free text.

## 6. How the planner-assist procedures use it
- `dbo.R0_GetDraftList` (CTE `CrewExpirations`): for every candidate in `#CrewPool`, aggregates (`STRING_AGG`) `Certificate_Code + ' (' + expiry date + ')'` over the records with `A.EXPIDATE < @PairingEndNum` (expired by the end of the pairing), restricted to live `EXPI` types whose position list contains the candidate's position code, whose aircraft list contains the candidate's aircraft code, that are not excluded by an `EXCLUDECAT` category the candidate holds, and that either have no include categories or one the candidate holds. The text appears as `'Expired Certs: ...'` in the candidate's warnings (`Expiry_Warnings`) - the qualification-currency check of a draft.
- `rpt.get_crew_certifications`: lists a crew member's certificates (`Certificate_code`, `Certificate_Description`, `EXPIDATE`) for each live type that applies to his qualification rows (position, aircraft) and categories; `CHKLAST` is selected only in commented-out code.
- Other procedures (R1-R5, `CalculateCrewFTC`, custom rules) do not read this view.

## 7. Typical query patterns
```sql
-- certificates of one crew member, with real dates; skip not-set / never-expiring sentinels in the date column
SELECT LTRIM(RTRIM(e.SHORTDESC)) AS Certificate_Code, LTRIM(RTRIM(e.DESC_)) AS Certificate_Description,
       CASE WHEN r.CHKLAST = 0 THEN NULL ELSE CAST(DATEADD(DAY, r.CHKLAST, '1980-01-01') AS DATE) END AS Last_Check,
       CASE WHEN r.EXPIDATE IN (0, 32767) THEN NULL ELSE CAST(DATEADD(DAY, r.EXPIDATE, '1980-01-01') AS DATE) END AS Expiry_Date
FROM TSC.dbo.vvCREXPREC AS r
JOIN TSC.dbo.EXPI       AS e ON e.EXPI = r.EXPIIDX
WHERE r.CREW_ID = @crew_id
  AND e.EFFECTIVE_END = 0
  AND LTRIM(RTRIM(ISNULL(e.SHORTDESC, N''))) <> N''
ORDER BY e.SHORTDESC;

-- expired at a given date (e.g. end of a pairing) for one crew member: exclude the 0 / 32767 sentinels
DECLARE @end INT = DATEDIFF(DAY, '1980-01-01', @pairing_end_date);
SELECT LTRIM(RTRIM(e.SHORTDESC)) AS Certificate_Code,
       CAST(DATEADD(DAY, r.EXPIDATE, '1980-01-01') AS DATE) AS Expiry_Date
FROM TSC.dbo.vvCREXPREC AS r
JOIN TSC.dbo.EXPI       AS e ON e.EXPI = r.EXPIIDX
WHERE r.CREW_ID = @crew_id
  AND r.EXPIDATE BETWEEN 1 AND @end - 1          -- expiry strictly before the pairing end day, as R0 does
  AND e.EFFECTIVE_END = 0 AND LTRIM(RTRIM(ISNULL(e.SHORTDESC, N''))) <> N''
  AND e.SHORTDESC NOT IN (N'WB', N'IFRLIC', N'SIMDUT');

-- aggregate: certificates that expire in the next 30 days, per type (live types only)
SELECT LTRIM(RTRIM(e.SHORTDESC)) AS Certificate_Code, COUNT(*) AS Records_Expiring
FROM TSC.dbo.vvCREXPREC AS r
JOIN TSC.dbo.EXPI       AS e ON e.EXPI = r.EXPIIDX
WHERE e.EFFECTIVE_END = 0
  AND r.EXPIDATE BETWEEN DATEDIFF(DAY, '1980-01-01', GETDATE()) AND DATEDIFF(DAY, '1980-01-01', GETDATE()) + 30
GROUP BY e.SHORTDESC
ORDER BY Records_Expiring DESC;
```

## 8. Data profile (measured 2026-11-03)
- 145,012 records; 5,511 crew (of 6,151 in `vvCREWDB`); 178 expiry types; per crew 1..129 records, average 26.3; 0 duplicate (`CREW_ID`,`EXPIIDX`); 0 orphans on either side.
- `CHKLAST`: 12,862 records = 0; non-zero range 1987-01-01 .. 2036-10-14; 2,416 dated after today.
- `EXPIDATE`: 5,626 = 0; 2,682 = 32767; other values 1987-01-01 .. 2050-12-31. Cross-tab: `CHKLAST > 0` with finite `EXPIDATE` = 125,859 records; `CHKLAST > 0` and `EXPIDATE = 0` = 3,609; `CHKLAST = 0` and `EXPIDATE > 0` = 10,845 (typically documents whose date is typed in); both 0 = 2,017.
- `EXPIDATE` already in the past (1..today-1): 103,519 records overall; among live named types and crew with a valid qualification today: 9,035 of 39,918 records (2,722 crew).
- `GRACEDATE` non-zero: 161 records (max day 25932 = 2050-12-31). `MAN_EXPIDATE`: 0 = 127,755; 1 = 13,783; 10 = 3,474 (by type: manual flag common on PASS 1,264, MED 477, BKLT 612).
- Most populated live types (records): PASS 5,412, MOT 4,223, FAIDP 3,124, FIREP 3,123, ANNP 3,123, DGPNC 3,122, UKETA 2,904, A320DT 2,872, A320D 2,388, NEW 1,463 (full list with all live types in `EXPI.md` section 8).

## 9. Open questions / confidence
- High: columns `CREW_ID`, `EXPIIDX`, `EXPIDATE`, join keys, day-number encoding, sentinels `0`/`32767` (measured), use in R0.
- Medium: `CHKLAST` = "last check date" (consistent with `EXPIDATE - CHKLAST` equalling the `EXPI` validity length for automatic records); for document types it is used differently (observed).
- Low / unknown: `GRACEDATE` (sparse, often earlier than `EXPIDATE`), `MAN_EXPIDATE` value 10, `FUTURE`.
- The view definition is unavailable; whether the underlying table stores more per-record fields (e.g. next planned check date, remarks) is unknown.
