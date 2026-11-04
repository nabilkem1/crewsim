# CREWQUAL  (Table)  - Crew qualifications: crew x home base x aircraft type x position, with active period and instructor/check flags

## 1. Purpose & business meaning
`TSC.dbo.CREWQUAL` is the AIMS **crew qualification table**: it says which crew member is qualified (and based) where, on which aircraft type, in which position, during which period.
One row = one qualification record of one crew member: (`ID` crew, `CWBASE` home base, `AC` aircraft type, `POS` position) valid from `ACTIVBEG` to `ACTIVEND` (inclusive AIMS day numbers).
A flying crew member holds several simultaneously valid rows - one per aircraft type he/she may be rostered on (measured today: 12,246 rows valid for 2,823 crew, about 4.3 rows per crew), so this table is a **crew x aircraft-type** table, not a crew table. History is kept (rows are ended, not deleted: 118,766 of 131,018 rows have a finite end date).
Business use in AIMS: (a) crew pairing/rostering eligibility (the rostering engine only assigns a crew member to a trip with the aircraft/position/base he holds a valid row for); (b) crew home base (needed for local-time, rest and acclimatization computations); (c) seniority list per base/aircraft/position (`SENIOR`); (d) per-row instructor / check-pilot capability flags (`DATA_BEGIN_END`).
Writers: AIMS crew administration (qualification changes: type-rating courses, base transfers, promotions to captain etc.). Readers in this repo: the draft list (`R0`), the rest-time / FDP procedures (`R3`, `R4`) for the crew's home base, and the `rpt.get_crew_*` report procedures.

## 2. Physical facts
- `TSC.dbo.CREWQUAL`, **USER_TABLE**, **131,018 rows** (rowcounts.json; measured identical), 6,151 distinct crew `ID` (= the 6,151 rows of `ROSTERID` / `vvCREWDB`).
- Primary key `PK_CREWQUAL` on `CREWQUAL_ID` (identity surrogate; 131,018 distinct).
- `CREWQUAL_INDEX_0` (non-unique): (`ID`, `ACTIVEND`, `ACTIVBEG`) - the "qualifications of crew X valid in period" path used by every per-crew lookup.
- `CREWQUAL_INDEX_1` (unique): (`CWBASE`, `AC`, `POS`, `QUALCAT`, `ID`, `PRIMARY_`, `ACTIVEND`, `ACTIVBEG`) - the **uniqueness key** of the business record and the "who is qualified on base/type/position" path used by the draft list (`WHERE q.CWBASE = ... AND q.AC IN (...) AND q.POS IN (...) AND q.PRIMARY_ = 0 AND ACTIVEND >= ... AND ACTIVBEG <= ...`).
- `CREWQUAL_INDEX_2` (unique): (`ID`, `IDX`) - per-crew sequence number.
- `CREWQUAL_INDEX_3` (unique): (`CWBASE`, `AC`, `POS`, `QUALCAT`, `SENIOR`, `ID`, `PRIMARY_`, `ACTIVEND`, `ACTIVBEG`) - the **seniority list** path (order crew by seniority within base/type/position).
- Medium table: always filter on `ID` or on (`CWBASE`,`AC`,`POS`) plus a date window; never aggregate the whole history without a date filter.

## 3. Column dictionary
Character widths = `len/2` of columns.json (metadata is in bytes).

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| ID | int | Y (never null in the data) | Crew member internal AIMS id (the same id as `ROSTER.ID`, `CREWCATEG.ID`, `vvCREWDB.ID`, `ROSTERID.ID`, `vvCREXPREC.CREW_ID`) | integer; measured 0 NULL, 0 rows without `ROSTERID`/`vvCREWDB` match | profiled; `R0_GetDraftList.sql` line 425 (`JOIN ROSTERID rid ON rid.ID = q.ID`) |
| CWBASE | nchar(4) | Y | Crew **home base** (domicile) of this qualification row | IATA airport code, blank-padded. All-time: YYZ 58,007 rows, YUL 44,109, YVR 17,516, YMX 10,709, YYC 518, YHZ 59, YOW 53, YHM 42, PRG 4, YWG 1. **Valid today: only YYZ (4,714 rows) and YUL (7,532 rows)** | profiled; `R0_GetDraftList.sql` line 428 (`q.CWBASE = @CrewMainBase`); `dbo.crew_base_timezone.sql` ("as in CREWQUAL.CWBASE") |
| AC | tinyint | Y | Aircraft type of the qualification = `AIRCTYPE.ACTYPE` (`vvAIRCTYPE.ACTYPE`) | see AC table below; 0 NULL | profiled; `R0_GetDraftList.sql` lines 107, 426, 678 (`ct.ACTYPE = q.AC`) |
| POS | tinyint | Y | Crew position of the qualification = `vvPositions.ID` | 1=CM, 2=PO, 3=ME, 4=SP, 5=DV, 6=DA, 7=AB, 8=SU (see `vvPositions.md`) | profiled; `dbo.position_category.sql` ("Position_Id is TSC.dbo.vvPositions.ID (and ROSTER.POS / CREWQUAL.POS)") |
| QUALCAT | smallint | Y | "Qualification category" - part of the unique business key. **Always 0** in all 131,018 rows (unused) | 0 | profiled; index definitions |
| PRIMARY_ | smallint | Y | Primary-qualification flag. Inference: `0` = the crew member's **primary (main-fleet) qualification**, `1` = additional qualification on another type. Evidence: the draft list selects only `PRIMARY_ = 0` (`@PrimaryFlag = 0`); every crew member with a valid qualification today has at least one valid row with 0 (2,823 of 2,823) and usually exactly one (2,809), plus 1-4 rows with 1 | 0 (34,073 rows), 1 (96,945 rows). Today: 2,839 rows = 0, 9,407 rows = 1 | `R0_GetDraftList.sql` line 100 (`DECLARE @PrimaryFlag INT = 0`), lines 430, 683; profiled |
| IDX | smallint | Y | Per-crew sequence number of the qualification record (1,2,3...). (`ID`,`IDX`) is unique; IDX is contiguous (max IDX = row count) for 6,150 of 6,151 crew | 1..364 | profiled; `CREWQUAL_INDEX_2` |
| ACTIVBEG | smallint | Y | First day (inclusive) of the qualification | AIMS day number = days since **1980-01-01**; `0` = since the beginning (7 rows); otherwise 1987-01-01 .. 2026-11-18 | profiled; `rpt.get_crew_qualifications.sql` line 43 (`CAST(Convert(DATETIME,'1980-01-01') + ACTIVBEG AS DATE)`) |
| ACTIVEND | smallint | Y | Last day (inclusive) of the qualification | same encoding; **`32767` = open-ended sentinel (= 2069-09-17)**, 12,252 rows; finite ends 1980-01-02 .. 2026-11-17; 286 rows are single-day (`ACTIVBEG = ACTIVEND`) | profiled; `rpt.get_crew_qualifications.sql` line 54 (`YEAR(...) = 2069`) |
| SENIOR | smallint | Y | Crew seniority rank **within this base/aircraft/position list** (lower = more senior). Used as the sort key of `CREWQUAL_INDEX_3`. Not identical to `ROSTERID.SENIOR` (equal for only 837 of 2,839 open primary rows) | 0..9998 real ranks (2,236 distinct values); `9999` = no rank/default (1,487 rows), `0` = 505 rows | profiled; `R0_GetDraftList.sql` line 418 uses `rid.SENIOR`, not this column |
| DATA_BEGIN_END | binary(90) | Y | Raw AIMS record block of the qualification (fixed 90 bytes). Decoded layout: **bytes 1-6 = 48 instructor/check-capability bits** (bit n = `vvFMSInfo1.FLTDUT_n`, see below); byte 9 = an unknown 0/1 flag (set on 7,481 rows); bytes 10-33 = a 12-character UTF-16LE text field that is blank for 131,000 rows and holds an airport/base code (YUL, YVR, YMX) on 121 rows (probably an alternate/secondary base - inference, not used by any procedure); the rest is zero | Bit n (1-based): byte `(n-1)/8 + 1`, mask `2^((n-1)%8)`. Bytes 11-90 otherwise 0x00/0x20 | profiled byte by byte; `R0_GetDraftList.sql` lines 277-290, 459-468, 521-526; `rpt.get_crew_qualifications.sql` lines 46-51 |
| CREWQUAL_ID | int | N | Surrogate identity primary key of the row | identity, unique | `PK_CREWQUAL`; used as tie-breaker `ORDER BY q.ACTIVBEG DESC, q.ACTIVEND DESC, q.CREWQUAL_ID DESC` in `R4_Get_Violation_FDP.sql` lines 396, 714 |

### 3.1 AC (aircraft type) values present (join `TSC.dbo.AIRCTYPE.ACTYPE` / `vvAIRCTYPE`)
AC -> IATA code (`vvAIRCTYPE.ACORDER`): 1=380 (9), 2=738 (10), 3=763 (11), 4=332 (1), 5=738C (12), 6=333 (2), 7=313 (5), 8=737E (13), 9=738T (14), 10=737 (7), 11=733 (15), 12=752 (4), 13=734 (16), 14=321 (17), 15=320T (18), 16=32Q (19), 17=TRN (20), 18=320 (8), 19=321L (21), 20=321C (22), 21=321N (23), 22=WDH4 (24), 23=W737 (25), 24=W736 (26), 25=W738 (27), 26=W7M8 (28), 27=L15 (3), 28=W7S8 (6), 29=32N (29), 30=PDH4 (30), 31=7M8 (31), 32=333C (32), 33=P295 (33), 34=332C (34), 35=343C (35).
Rows per AC in `CREWQUAL` (all time / valid today): 2=7,621/0; 4=26,231/2,381; 5=1/0; 6=26,236/2,382; 7=19,819/0; 9=661/0; 10=8,543/0; 12=4,056/0; 14=9,837/2,518; 15=68/0; 16=8,837/2,518; 18=8,513/2,447; 20=20/0; 27=4,999/0; 28=5,014/0; 31=302/0; 32=205/0; 34=26/0; 35=29/0.
Today the fleet is therefore A330 (4=332, 6=333), A321 (14=321, 16=32Q) and A320 (18=320).

### 3.2 DATA_BEGIN_END bits 1-48 (instructor / check-pilot capabilities; labels = `vvFMSInfo1.FLTDUT_n` where `RECDESC = 'CREWCODES2'`)
Rows having the bit set (all periods / valid today):
1 A CHECK PILOT 694/71; 2 B CHECK PILOT 395/35; 3 LINE CHECK DROIT 800/73; 4 LINE CHECK GAUCH 286/0; 5 MECANICIEN VERIF 34/0; 6 RC ETOPS CHECK 5/0; 7 ENTRAINEUR PRLI 12/12; 8 ENTRAINEUR SOP 25/22; 9 ENTRAINEUR SIMULATEUR 176/157; 10 ENTRAINEUR PERFORMANCE 5/5; 11 ENTRAINEUR EPT 42/31; 12 ENTRAINEUR PNT FORMATION SOL 30/27; 13 CRM JET TRANSITION INITIAL B 5/5; 14 PILOTE STANDARDISATEUR 39/33; 15 TRAINING DEVELOPPER 45/40; 16 REQUALIFICATION 183/128; 17 EET 178/123; 18 LINE INSPECTION 178/123; 19 AIRCRAFT INSPECTION 173/118; 20 ENTRAINEUR INITIAL 183/128; 21 ENTRAINEUR FIRST AID 152/107; 22 ENTRAINEUR ANNUELLE 183/128; 23 ENTRAINEUR DV 70/40; 24 LINE COACH PNC 225/140; 25 INITIAL-B APS-MCC INSTRUCTEUR 26/20; 26 JET TRANSITION INITIAL B 8/8; 27 FD MEETING Leadership 30/25; 28 Formation Commandant 2/2; bits 29-48 have no label and are never set.
(Bits 1-3 and 7-15 are pilot roles, 16-24 mostly cabin-crew instructor roles - inference from the labels.) Only 2,712 of 131,018 rows have any of bits 1-48 set.

## 4. Keys & relationships
- Business key: (`CWBASE`,`AC`,`POS`,`QUALCAT`,`ID`,`PRIMARY_`,`ACTIVEND`,`ACTIVBEG`) (unique index 1). Surrogate: `CREWQUAL_ID`. Per-crew order: (`ID`,`IDX`).
- `CREWQUAL.ID` -> `ROSTERID.ID` (N:1; `R0_GetDraftList.sql` line 425), -> `vvCREWDB.ID`, `ROSTER.ID`, `CREWCATEG.ID`, `vvCREXPREC.CREW_ID` (all N:1 on crew id; 0 orphans measured against `ROSTERID` and `vvCREWDB`).
- `CREWQUAL.AC` -> `AIRCTYPE.ACTYPE` (N:1; `JOIN TSC.dbo.AIRCTYPE AS ct ON ct.ACTYPE = q.AC`, R0 line 426; `vvAIRCTYPE.ACTYPE = cq.AC` in `rpt.get_crew_certifications.sql` line 109). 0 orphans measured.
- `CREWQUAL.POS` -> `vvPositions.ID` (N:1; R0 lines 427, 679; `rpt.get_crew_qualifications.sql` line 126). 0 orphans.
- `CREWQUAL.CWBASE` -> `dbo.crew_base_timezone.Base` (planner table; same text) and, informally, IATA airport code.
- To `ROSTER` (the actual duties): the duty is attributed to the qualification valid on the duty day: `r.ID = q.ID AND r.LEG_DAY BETWEEN q.ACTIVBEG AND q.ACTIVEND` (R0 lines 672-674). This is **1 duty -> many qualification rows** (one per aircraft type valid that day), so it multiplies rows unless `POS`/`AC`/`PRIMARY_` are also fixed (R0 constrains `q.AC IN (...)`, `q.POS IN (...)`, `q.PRIMARY_ = 0`, `q.CWBASE = @CrewMainBase`).
- 1:N to `vvCREXPREC` indirectly: the certificate-expiry logic joins `CREWQUAL` (via the pool) to `vvCREXPREC` on crew id.

## 5. Encoding conventions & gotchas
- **Day numbers:** `ACTIVBEG`/`ACTIVEND` are days since 1980-01-01. `ACTIVEND = 32767` = open-ended (2069-09-17). `ACTIVBEG = 0` = since the beginning. Convert only for display.
- **Both ends inclusive:** next period of the same crew starts at `ACTIVEND + 1` (gap = 1 is the most common gap, 25,909 occurrences). All procedures that join duties use `BETWEEN ACTIVBEG AND ACTIVEND` or `<=`/`>=`.
- **Valid-today predicate:** `ACTIVBEG <= D AND ACTIVEND >= D` with `D = DATEDIFF(DAY,'1980-01-01',GETDATE())`. `rpt.get_crew_certifications` compares `CAST(1980-01-01 + ACTIVEND AS DATE) > GETDATE()` (effectively `ACTIVEND > today`, no begin test, and it also keeps qualifications that start in the future).
- **`rpt.get_crew_qualifications` returns only open-ended rows** (`YEAR(1980-01-01 + ACTIVEND) = 2069`), i.e. it hides ended and finite-end qualifications by design.
- **Overlapping ranges / row multiplication:** a crew member has several rows valid on the same day (one per aircraft type, and `PRIMARY_` 0/1). To obtain "the crew's base" on a day, R3 and R4 take `TOP 1 ... ORDER BY q.ACTIVBEG DESC, q.ACTIVEND DESC, q.CWBASE` (R3) or `... q.CREWQUAL_ID DESC` (R4). In practice a crew member has a single base and a single position on any given day (checked: on 2026-11-03 2,823 crew -> exactly 1 distinct base and 1 distinct position each; on 2025-06-15 2,803 crew -> 1 base, 1 position each), but several aircraft types. Joining `CREWQUAL` to duties without `TOP 1`/`DISTINCT` multiplies the duties by the number of types.
- **`PRIMARY_` polarity is counter-intuitive** (`0` = primary). Do not filter `PRIMARY_ = 1` to get the main fleet.
- **Crew base list is narrow today:** only YYZ and YUL have valid rows; other bases (YVR, YMX, YYC, YHZ, YOW, YHM, PRG, YWG) are history only. `dbo.crew_base_timezone` carries 10 bases for that reason.
- `CWBASE` is blank-padded `nchar`; compare with `LTRIM(RTRIM())` or a trimmed parameter (R0 compares `q.CWBASE = @CrewMainBase` directly, which works because SQL Server ignores trailing blanks in `=` comparison).
- `SENIOR = 9999` is "unranked"; do not sort by it as if it were a real rank without excluding it.
- Instructor bits: the decode only works with the labels from `vvFMSInfo1` (`RECDESC = 'CREWCODES2'`); labels are blank-padded, French-English mix; planner filters compare `LTRIM(RTRIM(label))` to the requested names (R0 lines 298-300, 459-468).
- Personal data: the table itself holds no personal attributes; `ID` is still a person identifier - aggregate, do not list individuals.

## 6. How the planner-assist procedures use it
- `dbo.R0_GetDraftList` (candidate crew for a pairing): `#CrewPool` = `CREWQUAL` rows with `CWBASE = @CrewMainBase`, `AC` in the requested aircraft, `POS` in the requested positions, `PRIMARY_ = 0`, active period overlapping the search window (`ACTIVEND >= @StartDateNum AND ACTIVBEG <= @EndDateNum`); optional instructor-qualification filter (`@InstructorQualList`) tests bits of `DATA_BEGIN_END` via the `vvFMSInfo1` labels, with a `DATALENGTH(q.DATA_BEGIN_END) >= QM.ByteIdx` guard; the same bits are rendered as the `Instructor_Qualifications` display string. The off-day expansion uses `cp.ACTIVBEG`/`ACTIVEND` as the span during which the crew member counts as available (`DATEDIFF(DAY,@BaseDate,ds.CalendarDate) BETWEEN cp.ACTIVBEG AND cp.ACTIVEND`), and the on-leg branch joins `ROSTER` on `LEG_DAY BETWEEN q.ACTIVBEG AND q.ACTIVEND`.
- `dbo.R3_Get_Violations_RestTime` and `_Batch`: home base of the crew on the duty day (`OUTER APPLY (SELECT TOP 1 q.cwbase ... WHERE q.id = r.ID AND r.LEG_DAY <= q.ACTIVEND AND r.LEG_DAY >= q.ACTIVBEG ORDER BY q.ACTIVBEG DESC, q.ACTIVEND DESC, q.cwbase)`), then `dbo.GetEffectiveOffsetUtc(cq.cwbase, ...)` gives the home-base UTC offset used by the acclimatization / rest rules (R3 implements an EASA FDP table, line 78, with a biological acclimatization chain in phases 4-5: the crew's acclimatized state starts at the home-base offset). Same pattern in the acclimatization phase (lines ~548-555, batch ~496-500).
- `dbo.R4_Get_Violation_FDP`: same TOP 1 base lookup (`ORDER BY ... CREWQUAL_ID DESC`) for the home-base offset used to compute the maximum flight duty period (FDP) in local base time (lines 394-396, 711-714).
- `rpt.get_crew_qualifications`: lists a crew member's **open-ended** qualifications with position description, aircraft code, base, valid-from/to dates and the decoded `Instructor_Qualifications` string.
- `rpt.get_crew_certifications`: distinct (`POS`,`AC`,`ID`,`CWBASE`) of qualifications with `ACTIVEND > now` to decide for which aircraft type and position each expiry type applies, then to show `CWBASE` next to each certificate.

## 7. Typical query patterns
```sql
-- current qualifications of one crew member (inclusive validity), decoded
DECLARE @d INT = DATEDIFF(DAY, '1980-01-01', GETDATE());
SELECT q.ID, LTRIM(RTRIM(q.CWBASE)) AS Crew_Base, LTRIM(RTRIM(a.IATACODE)) AS Aircraft,
       LTRIM(RTRIM(p.CODE)) AS Position_Code, q.PRIMARY_,
       CAST(DATEADD(DAY, q.ACTIVBEG, '1980-01-01') AS DATE) AS Valid_From,
       CASE WHEN q.ACTIVEND = 32767 THEN NULL ELSE CAST(DATEADD(DAY, q.ACTIVEND, '1980-01-01') AS DATE) END AS Valid_To
FROM TSC.dbo.CREWQUAL AS q
JOIN TSC.dbo.AIRCTYPE  AS a ON a.ACTYPE = q.AC
JOIN TSC.dbo.vvPositions AS p ON p.ID = q.POS
WHERE q.ID = @crew_id AND q.ACTIVBEG <= @d AND q.ACTIVEND >= @d
ORDER BY q.PRIMARY_, a.IATACODE;

-- how many crew are qualified today per base / aircraft / position (aggregate only, primary row to avoid multiple counting of the same crew on several types)
DECLARE @d2 INT = DATEDIFF(DAY, '1980-01-01', GETDATE());
SELECT LTRIM(RTRIM(q.CWBASE)) AS Crew_Base, LTRIM(RTRIM(a.IATACODE)) AS Aircraft,
       LTRIM(RTRIM(p.CODE)) AS Position_Code, COUNT(DISTINCT q.ID) AS Crew_Count
FROM TSC.dbo.CREWQUAL AS q
JOIN TSC.dbo.AIRCTYPE  AS a ON a.ACTYPE = q.AC
JOIN TSC.dbo.vvPositions AS p ON p.ID = q.POS
WHERE q.ACTIVBEG <= @d2 AND q.ACTIVEND >= @d2 AND q.PRIMARY_ = 0
GROUP BY q.CWBASE, a.IATACODE, p.CODE
ORDER BY Crew_Base, Aircraft, Position_Code;

-- home base of a crew member on a given duty day (one row, as R3/R4 do)
SELECT TOP (1) LTRIM(RTRIM(q.CWBASE)) AS Crew_Base
FROM TSC.dbo.CREWQUAL AS q
WHERE q.ID = @crew_id
  AND DATEDIFF(DAY, '1980-01-01', @duty_date) BETWEEN q.ACTIVBEG AND q.ACTIVEND
ORDER BY q.ACTIVBEG DESC, q.ACTIVEND DESC, q.CREWQUAL_ID DESC;

-- does a qualification row carry instructor bit 1 ("A CHECK PILOT")?  (byte 1, mask 1)
SELECT COUNT(*) FROM TSC.dbo.CREWQUAL AS q
WHERE (CONVERT(tinyint, SUBSTRING(q.DATA_BEGIN_END, 1, 1)) & 1) > 0
  AND DATEDIFF(DAY, '1980-01-01', GETDATE()) BETWEEN q.ACTIVBEG AND q.ACTIVEND;
```

## 8. Data profile (measured 2026-11-03)
- 131,018 rows; 6,151 distinct crew; `ID`, all other key columns non-null; `QUALCAT` = 0 in every row; no row with `ACTIVEND < ACTIVBEG`; 286 single-day rows.
- `ACTIVBEG`: 7 rows = 0, otherwise 1987-01-01 .. 2026-11-18. `ACTIVEND`: 12,252 rows = 32767 (open), finite range 1980-01-02 .. 2026-11-17.
- Valid today (`ACTIVBEG <= today <= ACTIVEND`): 12,246 rows, 2,823 crew; `PRIMARY_` 0 = 2,839 rows (2,823 crew), 1 = 9,407 rows (2,816 crew); rows with `PRIMARY_` = 0 per crew: 1 for 2,809 crew, 2 for 12, 3 for 2.
- Valid today by position: CM 904, PO 1,021, DV 1,709, AB 8,452, SU 160 (ME, SP, DA none). By aircraft: 332 2,381; 333 2,382; 321 2,518; 32Q 2,518; 320 2,447. By base: YUL 7,532, YYZ 4,714, all others 0.
- Primary rows today by position/type: pilots (CM/PO) are primary on 332 (143/152 rows), 333 (6/5), 321 (205/237), the other types being additional rows; cabin positions are primary on 333 (DV 345, AB 1,702).
- Crew with a different base/position on the same day: none (checked 2026-11-03 and 2025-06-15).
- `DATA_BEGIN_END` bit statistics: see 3.2.
- Consecutive qualification periods of the same crew: next `ACTIVBEG` = previous `ACTIVEND` + 1 (25,909 cases); overlapping ranges are common (negative gaps, e.g. -29/-30 days: 10,577 / 9,316 cases).

## 9. Open questions / confidence
- High: structure, keys, join predicates, inclusive day-number encoding, 32767/0 sentinels, per-row multiplication, instructor bit layout (bits 1-48 map exactly to the 48 `FLTDUT_n` labels used by R0 and `rpt.get_crew_qualifications`).
- Medium (inference): `PRIMARY_ = 0` meaning "primary qualification" (consistent with data and with R0's constant 0, but no AIMS documentation is available); `SENIOR` as seniority-in-list (index design + values); `IDX` as per-crew sequence.
- Low / unknown: byte 9 flag (7,481 rows) and the 12-char text field at bytes 10-33 of `DATA_BEGIN_END` (looks like an alternate base code on 121 rows); `QUALCAT` (constant 0).
- Open: whether the planner should restrict R0's pool to the crew's primary qualification only (`PRIMARY_ = 0`): the code does, which excludes crew whose only qualification for the requested type is an additional (`PRIMARY_ = 1`) row (e.g. most A321 qualifications held by A330-primary crew).
