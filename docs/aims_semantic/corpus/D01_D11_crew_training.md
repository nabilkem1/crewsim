# CrewSim corpus from AIMS (TSC) - D1 `d1_crew_master` and D11 `d11_training_sessions` (+ crew attributes needed by the other datasets)

Generated 2026-11-03 (AIMS "today" = day 17108). Read-only SQL on `TSC` (10.180.1.10), aggregates and code/lookup values only: **no crew id, name, date of birth, address, contact or any individual's value is reproduced here**.
Everything labelled *(inference)* was deduced from column names, profiling, or by reproducing Pierre's v3 file in aggregate; it is not documented AIMS semantics.
Pierre v3 files read for aggregate comparison only: `C:\dev\crewsim\src\crewsim\data\corpus\real_datav2\v3\d1_crew_master.csv` and `d11_training_sessions.csv`.

## 0. Executive summary

| Dataset | Verdict | One-line reason |
|---|---|---|
| **D1 crew master** | **MOSTLY** (population, base, position, group, qual dates, seniority-order: FULL; fleet detail, hire/termination dates, employment_status: PARTIAL/proxies) | I rebuilt Pierre's D1 population from `CREWQUAL`/`ROSTERID` and got **exactly 1,500 pilots / 736 ACTIVE / 764 TERMINATED**, 453 YUL + 283 YYZ active, 1 hire date = 1980-01-01 default, 11 hires after 2026-08-31, last termination 2026-08-31: i.e. Pierre's D1 is a **snapshot of AIMS CREWQUAL as of 2026-09-01**. Hire/termination are *not HR dates*: they are first/last qualification boundaries. No hire/termination/status field exists in `vvCREWDB`. |
| **D11 training sessions** | **MOSTLY** (sessions: FULL for 10 of 11 types; deadline: PARTIAL rule; cost: MISSING) | Pierre's sessions = pilot roster activity rows (`ROSTER` x `CRCODES`) mapped by code to 11 `session_type`s, consecutive days merged. My SQL reproduces Jan-2026 exactly (SYSTEMS_EXAM 88/87, CRM 73, RECURRENT_GROUND 57, TYPE_RATING_SIM 52, PPC 47, DG 24, ...) and the full window within 0-2% for every type except `INITIAL_GROUND` (code list not recovered). `reschedule_cost_cad_estimate` is a flat per-type lookup x session days (business assumption, not in AIMS). `requalification_deadline` is `end_date + fixed interval` per type (Pierre's rule), not an AIMS stored value. |
| **History** | Qualification/base/position/category: **full past states available** (rows are ended, never overwritten: `CREWQUAL` since 1987, `CREWCATEG` since 1991, `ROSTER` since 1999). Seniority, employment status, hire/termination, expiry dates: **current state only** (seniority/expiry change *events* exist in `MSTLOGCRW` from 2024-06-01 and `CREXPLOG` from 2024-12-24 but without old values / unusable volume). |

Key blockers (ordered): (1) true HR hire/termination dates and a real employment-status feed are not in TSC; (2) the A321neoLR sub-fleet is **not a crew qualification in AIMS** (all A321 pilots hold 321 + 32Q rows with identical dates; sub-fleet must be derived from flying `ROSTER.AC` / `LEGMAIN.AC`); (3) `session_type` code mapping and the `INITIAL_GROUND` code list need business confirmation; (4) `reschedule_cost_cad_estimate` and per-type requalification intervals need a business table; (5) the `P######` pseudonym key of Pierre is unknown, so ids will not match his files unless he hands over his mapping/algorithm (a reproducible keyed permutation is proposed in section 5).

---

## 1. What I relied on (objects and how they were established)

### 1.1 Already documented objects used
`CREWQUAL` (131,018 rows), `CREWCATEG` (31,563) / `CREWCAT` (240), `ROSTERID` (6,151), `vvCREWDB` (287 cols, personal - only column names inspected), `vvPositions`, `AIRCTYPE`/`vvAIRCTYPE`, `EXPI`, `vvCREXPREC`, `CRCODES`, `ROSTER` (14.4M).

### 1.2 Newly discovered / newly profiled objects (notes)

| Object | What it is | Key / grain | Rows | Date range | How written (inference) |
|---|---|---|---|---|---|
| **`FIELDSINFO`** | AIMS data dictionary: `FIELDID`, `TABLEID`, `FIELDNAME`, type, size (no table name column). Lets the numeric ids of the audit log be decoded: TABLEID **28 = CREWQUAL** (ID, CWBASE, AC, POS, QUALCAT, PRIMARY, IDX, ACTIVBEG, ACTIVEND, SENIOR...), **30 = CREWDB** (333 crew-master fields), **51 = CREXPREC** (CHKLAST, EXPIDATE, MAN_EXPIDATE...), **215 = CREWCATEG** (CREWCATIDX, ACTIVBEG/ACTIVEND...), **262 = ROSTERID** (ACTUALROSTERSTARTDAY, SENIOR, PRINTUNTIL...) | field | 24,594 | - | static, AIMS installer. Table ids were matched by field names and by "key = crew id" tests (first 4 bytes little-endian of `FORKEYINFO` = a crew id for tables 30, 51, 215, 262; not for 28, whose key starts with the base). |
| **`MSTLOGCRW`** (260M rows) | Field-level **audit log** of crew-master tables. Columns: `TABLELOGID` (PK), `FORKEYINFO` binary(32) (record key), `AIMSTABLEID`, `AIMSFIELDID`, `DBOPERATION` (2 = insert row, 3 = update field, 4 = delete row, inference), `ONDAY/ONMIN/ONSEC/ONMSEC` (when), `AIMSUSER`, `PCID`, `NEWVALUE` varbinary(1001) (**new value only, no old value**). Indexed by `(AIMSTABLEID, ONDAY, ONMIN...)` - safe with `AIMSTABLEID = n AND ONDAY BETWEEN a AND b`. | one row per changed field/row | 260M | **2024-06-01 .. 2026-10-27** for tables 28/30/51/215/262 (min ONDAY 16223..16225) | written by AIMS on every edit. CREWQUAL (28): ~45k row inserts + ~45k deletes per quarter and ~214k `SENIOR` updates in the first quarter, i.e. rows are rewritten routinely (bulk re-seniority, qualification updates). Useful to detect retro-active edits and to date seniority changes; cannot rebuild old values. |
| **`MSTLOGLEAVE`, `MSTLOGTRN`, `MSTLOGMISC`** | same structure as `MSTLOGCRW`, for leave bank (`LEAVE`), training module (`TRN*`) and misc tables. `MSTLOGTRN` 37,539 rows. | same | 502k / 37.5k / ? | not profiled beyond structure | same. |
| **`CREXPREC`** (base table of `vvCREXPREC`, 145,012 rows) | per crew x expiry type: `CHKLAST`, `EXPIDATE`, `GRACEDATE`, packed `DATA_BEGIN_END` (101 B; holds `MAN_EXPIDATE`). **Current state only** (one row per crew x type). | (CREW_ID, EXPIIDX) | 145,012 | CHKLAST 1987.. | AIMS recomputes after each renewing activity. |
| **`CREXPLOG`** (1.8 billion rows) | Audit/recalculation log of expiry records: `ADAY/AMIN/ASEC/AMSEC` (log time), `AIMSUSER`, `CREW_ID`, `EXPIIDX`, `DATA_BEGIN_END` binary(88) (before/after image, undecoded). Indexes `(ADAY,AMIN,EXPIIDX)`, `(EXPIIDX,ADAY,AMIN,CREW_ID)`, `(CREW_ID,ADAY,AMIN,AIMSUSER)`. | one row per recomputation | 1.8e9 | **ADAY min 16429 (2024-12-24) .. max 17101 (2026-10-27)** (TOP 1 on the ADAY index) | **~52,900 log rows for ONE pilot in 27 days (23 types)**, i.e. a nightly recalculation, not one row per training. A `COUNT(*)` for a single day timed out (60 s) - never aggregate it. Not usable as session history. |
| **`CREWBASES`** | base dictionary: `BASEIDX`, `CWBASE`, `COTERM` (co-terminal base). 21 rows: YMX(coterm YUL), YYZ, YVR, YEG, YQB, YHZ, YYC, YUL(coterm YMX), YWG, YXE, YYT, YQM, YQR, YOW, YHM, YUY, YQT, YXU, YQG, PRG, FRA | BASEIDX | 21 | - | static. YUL and YMX are declared co-terminal. |
| **`CREWPOS`** | physical table behind `vvPositions` (24 rows; `DATA_BEGIN_END` 144 B: CODE + description). | ID | 24 | - | static. |
| **`CREWDB`** | physical table behind `vvCREWDB`: `ID`, `NAME`, `SHORTNAME`, `SWIPECARD`, `DATA_BEGIN_END` binary(3811), `CREWDB_ID`. No hidden extra columns: everything is decoded by the 287 columns of the view (none is a hire date, termination date or employment status; see 4.1). | ID | 6,151 | - | AIMS crew admin / HR interface. |
| **`CREWDATES`** | 1 row, sentinel values (`-32768`), unused. | - | 1 | - | - |
| **`LEAVE` / `LEAVEDESC`** | annual leave bank per crew and year: `LEAVE(ID, CAT, LVEYEAR, DATA_BEGIN_END binary(992))`, `LEAVEDESC` 144 rows (3 categories x 48 entries, descriptions blank). 56,903 rows, 2009..2027 (about 2.4k..3.7k crews/year). **Balances, not absence history** - not usable for employment status. Absence periods are roster codes (see 4.1). | (ID, LVEYEAR) | 56,903 | 2009..2027 | - |
| **`TRNMEMBS2`** (3,617), **`TRNSESS2`** (4), **`TRNBOOKING`** (887), **`TRNPATTERN`** (1,170), **`TRNDATECOURSE`** (639), **`TRNFAILURE`** (6,393), **`TRNCOURSE`/`TRNCOURSE2`/`TRNCOURSEDT*`** (37/115 syllabi), **`TRNFACIL`** (35 facilities), `TRN3RD`, `TRNSIMUS` | AIMS **training module**: syllabus catalogue (`SYLIDX` -> `SYLCODE`: "PPC 321 PH1..PH6", "PPC 330 PH1..6", "SYS 321/330", "DG", "EPTT/EPTP FR/EN", "REUI", "Generic Training", "EET", "PRLI", "SOP + PERF", "Onboarding Pilot", "IE - INITIAL", ...), facilities (A330 FFS, A320 FFS, CAE, classrooms), course dates, enrolled members (`TRNMEMBS2`: SYLDATE, SYLIDX, SYLDAYNO, ID), bookings and failures. `ROSTER.SYLIDX/SYLDATE/SYLDAYNO/SYLDTIDX/FACILIDX` link the roster activity to these. | various | see left | **`TRNMEMBS2` SYLDATE 2026-01-12 .. 2026-12-17; `TRNBOOKING` 885 of 887 rows in 2026; `TRNFAILURE` OPERDATE 2025..2026 (14 rows with 1980 sentinel); `TRNSESS2` 4 rows (2006)** | written by the training scheduler; **old sessions are purged**, so the module is *not* a history source (only the current year). Pilot content in 2026: ~1,170 `TRNMEMBS2` rows (EPTT FR/EN, Generic Training, REUI, EPTP, SOP+PERF, SYS 321/330, DG, EET, PRLI, Onboarding Pilot, IE-INITIAL, Jet SOP, REUS, CCMD); 2,298 distinct crew overall (mostly cabin). `TRNFAILURE`: 3,309 rows 2025, 3,070 rows 2026, 452 crews, dominated by cabin `ANN`/`FAID`/`DV1`; pilot-relevant codes SY20 (403), GEN (202), EPTP (124), EPTT (35), SY30 (22), DG (2); `REASON` is free text (non-blank on every row - not read). |
| `HISTHRS` (3,024) | per crew: `AC`, `POS`, packed hours (232 B) - prior-experience hours, not training. Not used. | ID | 3,024 | - | - |

`vvCREWDB` day-number columns profiled for non-zero counts (names only): `TRAINBEG` (3 rows, 2000-ish), `TRAINEND`, `REENTRY`, `SBYBEG`, `COMP_START`, `CONTRACT`, `UPUNTILDATE`, `PERMANENTFO`, `IOE_COMPL`, `LD_UPGRD`, `IOE_REL`, `ACTIVECMDAYS`, `ACTIVEFADAYS`, `SICK_BALANCE`, `VACATION_BALANCE`, `TRAINING_MMG` are **all 0 / blank on every row** (or 3 rows). `UPDDATE` (audit stamp, 5,987 non-zero) and `TSCREASON` (free text, 3,763 non-blank - content not read) exist but are not dates of hire/termination. `ROSTERID.ACTDATA` is *not* a hire date either (347 of 1,510 pilots non-zero, 338 later than the first qualification, max 2009-05-02). Conclusion: **no hire date, termination date or employment status column exists in TSC**.

---

## 2. D1 - `d1_crew_master`

### 2.1 What the real v3 file contains (aggregates)
Header: `crew_id, base, crew_group, position, fleet, fleet_family, fleet_detail, qual_valid_from, qual_valid_to, seniority_number, employment_status, hire_date, termination_date` (`fleet_detail` is an extra column not in `DATASET_SCHEMAS`; CrewSim ignores it).
1,500 rows, 1,500 distinct `crew_id` (`P` + 6 digits, uniformly spread 500..999365), `crew_group` = PILOT only (no CABIN), position CA 609 / FO 891, employment_status ACTIVE 736 / TERMINATED 764, base YUL 732 / YYZ 562 / YMX 73 / YHZ 55 / YHM 36 / YOW 33 / YVR 8 / PRG 1 (active: YUL 453, YYZ 283), fleet A321 630 / A330 520 / B737 192 / A310 104 / W7S8 36 / B757 14 / L15 4 (fleet_family empty on 40 rows = W7S8 + L15, all terminated), `qual_valid_to` empty for the 736 ACTIVE, `termination_date` = `qual_valid_to` for 743 of 764 terminated, `hire_date` 1980-01-01 once, 11 hires dated after 2026-08-31, `seniority_number` 1..1571 (unique, max > row count; ACTIVE 39..1571).

### 2.2 Column mapping

Convention for the AIMS side: `d` = as-of day number (`DATEDIFF(DAY,'1980-01-01', @asof)`); "valid on d" = `ACTIVBEG <= d AND ACTIVEND >= d` (inclusive both ends; `ACTIVEND = 32767` = open-ended; `ACTIVBEG = 0` = since the beginning). Pilot rows = `CREWQUAL.POS IN (1,2)` (CM, PO); `PRIMARY_ = 0` = primary qualification.

| corpus column | status | AIMS source | transformation | evidence | gap / risk |
|---|---|---|---|---|---|
| `crew_id` | DERIVABLE | `CREWQUAL.ID` (= `ROSTERID.ID` = `vvCREWDB.ID`) | pseudonymise **outside SQL** (section 5). AIMS ids are **not** pseudonyms. | Pierre's 1,500 numbers do not coincide with AIMS ids (3 chance matches of 1,500; expected ~2). AIMS pilot ids fall in clusters: below 10,000 (356), 10,000-300,000 (26), 300,000-320,000 (961), 320,000-800,000 (1) and >= 800,000 (166 pilots whose qualifications all ended by 2022-03 and who never flew in the window): employee-number-like *(inference; Pierre's first extract used matricules like these)*. | Raw `ID` is likely an employee number -> must never be exported as `crew_id` (Law 25). Pierre's own pseudonym key is unknown: pseudonyms will differ from his files unless he shares the mapping or algorithm. |
| `base` | DERIVABLE | `RTRIM(CREWQUAL.CWBASE)` of the row valid on `d` (primary row first); for terminated: base of the last-ending row | `TOP 1 ... ORDER BY PRIMARY_, ACTIVBEG DESC` (a crew has exactly 1 base on any day: checked 2025-06-15 and 2026-11-03) | Active snapshot 2026-09-01: **YUL 453 / YYZ 283 = Pierre's 453/283** | Pierre gives **one base per pilot** (current/last); AIMS gives the base **per date** (807 of 1,510 pilots held >1 base ever, 29 changed base inside 2024-04-24..2026-08-31). YMX is declared co-terminal of YUL in `CREWBASES`. Terminated pilots' base: last row only (approximation of what Pierre did). |
| `crew_group` | DERIVABLE | `CREWQUAL.POS`: 1,2,3,4 = PILOT; 5..8 = CABIN (`vvPositions.CK_CB`; planner table `position_category`: ME(3) is classed PNC there but AIMS marks it cockpit) | `CASE` | all-time: pilot 1,581 crews (1,510 with CM/PO), cabin 4,579, 9 crews in both groups | Pierre delivered PILOT only; CABIN is available in the same way (valid 2026-09-01: AB 1,691 [YUL 1,029, YYZ 662], DV 360, SU 30). ME (78 crews, ended long ago) and SP (4) are not CA/FO. |
| `position` | DERIVABLE | `CREWQUAL.POS` 1 = CM -> `CA`, 2 = PO -> `FO` | `CASE` | rebuilt: CA 612 / FO 888 vs Pierre 609 / 891 (3 pilots differ: mid-upgrade, tie in the choice of row) | 455 pilots hold both CA and FO rows in history (upgrade history is recoverable, Pierre's file keeps only the latest). |
| `fleet` | PARTIAL | `CREWQUAL.AC` (primary row) -> `AIRCTYPE.IATACODE` -> family: 332,333 -> A330; 321,32Q,320 -> A321; 738,738T,737,... -> B737; 313 -> A310; 752 -> B757; 27/28 (`L15`,`W7S8`) legacy | mapping table; `vvAIRCTYPE.AC_ADOPT_PBS` already groups 320/321/321C/321L/321N/32N/32Q -> `321` and 332/333 -> `330` | Active 2026-09-01 rebuilt: A321 **441** vs 436, A330 **295** vs 300; terminated: A330 203 vs 220, A321 202 vs 194, B737 201 vs 192, A310 114 vs 104, B757 14 = 14, `W7S8` 38 vs 36, `L15` 2 vs 4 | Differences come from **which row is "the" qualification** when a pilot holds several (see 2.5). Terminated pilots' fleet is ambiguous. |
| `fleet_family` | DERIVABLE | same mapping | Pierre has it empty for W7S8/L15 (40 rows); AIMS gives AC 27/28 but no family | - | `L15` (L-1011 *(inference)*) and `W7S8` (Boeing 737-800 wet-lease *(inference)*) need a business label or removal (Pierre was asked in his notes). |
| `qual_valid_from` | DERIVABLE (definition to fix) | `MAX(CREWQUAL.ACTIVBEG)` over the rows valid on `d` (ACTIVE) / `ACTIVBEG` of the last-ending row (TERMINATED) | `DATEADD(DAY, n, '1980-01-01')` | Year histogram of AIMS (2010:1, 2011:1, 2015:4, 2017:1, 2018:2, 2019:20, 2020:6, 2021:10, 2022:64, 2023:97, **2024:328**, 2025:87) matches Pierre's ACTIVE (1,1,4,1,2,20,6,11,65,102,**345**,102); 13 active rows start after 2026-08-31 (Pierre 19; he apparently also uses rows starting after the snapshot day, max in his file 2026-09-23) | It is "start of the **latest** qualification row" (a 320 differences row, a promotion...), **not** "start of the type rating". Semantics differ from the data dictionary ("start of the current type-rating qualification period"). One pilot has only `ACTIVBEG = 0` -> NULL (Pierre also has 1 NULL). |
| `qual_valid_to` | DERIVABLE | `MAX(ACTIVEND)` of the pilot (`32767` -> NULL) for TERMINATED; NULL for ACTIVE | - | rebuilt: 736 NULL (= ACTIVE) and 764 non-NULL; `termination_date = qual_valid_to` for **764/764** (Pierre 743/764; the 21 differences are his) | Same as Pierre: it is a qualification boundary, not a contract date. |
| `seniority_number` | PARTIAL | ACTIVE: `ROSTERID.SENIOR` (1..9998 real; 9999 = unset, 0 also unset). Also `CREWQUAL.SENIOR` (rank inside base/type/position list - not the company list) | take `ROSTERID.SENIOR BETWEEN 1 AND 9998` | For the 736 valid pilots all have a real value, 736 distinct, range **2..747**. Spearman(SENIOR, first-qualification start) = **0.998**; in Pierre's file Spearman(seniority, hire_date) = 0.99995 (active) / 0.9974 (terminated) *(inference: same ordering)*. | Absolute numbers differ (Pierre 39..1571, unique over 1,500 rows incl. terminated; AIMS 2..747). CrewSim only needs **order among ACTIVE**, which AIMS gives (DIRECT for that use). For the 774 non-active pilots `SENIOR` is stale and duplicated (1,270 real values, 770 distinct over all 1,510) -> NULL them or rank by hire proxy. **No history**: `CREWQUAL.SENIOR` has a single value per pilot in rows since 2024-04 (292 pilots, 1 distinct value each); only `MSTLOGCRW` (tables 262/28, field 19853/3036, since 2024-06-01) records *when* it changed, without values. Pierre's exact method is unknown. |
| `employment_status` | PARTIAL | qualification validity (ACTIVE = valid on `d`, else TERMINATED) + optional: `CREWCATEG`/`CREWCAT` (36 `PNT ACTIF`, 96 `PNT NON QUALIFIE`, 86 `CADET UNDER TRAINING`, 72 `BLOC INACTIF`, 222 `No longer with Air Transat`, 162 `PNT RAPPELE`, 169/165 `REFUS RAPPEL*`) + leave-flag roster codes (`INV`, `MAL`, `MAT`, `PAT`, `CSRH`, `CPP5`, `PTP`...) | see SQL 2.3 | v3 rebuilt: 736 / 764 (= Pierre's). Categories at 2026-09-01 over the 736 valid pilots: `PNT ACTIF` 683, `PNT NON QUALIFIE` 41, `CADET UNDER TRAINING` 7, `Pilote Instructeur` 116, `FO en LI - RC` 46 ... Jan-2026 roster: `INV` 52 pilots (1,476 pilot-days), `MAL` 135, `MFIT` 156, `PAT` 12, `CPP5` 44, `MARH` 3, `MAT` 1. Cat 222 ("No longer with Air Transat"): held by 197 pilots (196 with an ended qualification), begins within +-3 d of the last qualification end for 152 of them | The target domain (`ACTIVE, INACTIVE, TERMINATED, LONG_TERM_ABSENCE, MANAGEMENT_OR_INSTRUCTOR, INITIAL_TRAINING, FLEET_TRANSITION`) needs **business rules** on categories and absence codes. Category `PNT ACTIF` covers only 809 of 1,510 pilots (not a complete status) and 222 only 26% of the ended pilots. 86 pilots have a *gap* in qualification validity (120 gaps: 26 <= 31 d, 73 of 32..365 d, 21 > 365 d; none starts inside or after the 2024-04-24 window) = re-hires/long absences. CrewSim v3 only has ACTIVE/TERMINATED. |
| `hire_date` | PARTIAL (proxy) | `MIN(NULLIF(CREWQUAL.ACTIVBEG,0))` over the pilot's rows | `DATEADD` | Year histogram of AIMS first-qualification start (1987:13, 1996:46, 1997:37, 1998:56, 2000:69, 2011:93, 2019:179, 2023:149, 2024:95 ...) matches Pierre's hire years (1987:13, 1996:47, 1997:38, 1998:56, 2000:69, 2011:93, 2019:178, 2023:148, 2024:93); **the one hire date = 1980-01-01 is exactly the pilot whose only start is `ACTIVBEG = 0`** (my query reproduces 1) | **Not a real hire date**: it is the first qualification start (a pilot qualified before 1987 or hired earlier than the first logged row is mis-dated). 11 rows start after 2026-08-31 (reproduced). Real HR hire date: **MISSING** in TSC. |
| `termination_date` | PARTIAL (proxy) | `MAX(CREWQUAL.ACTIVEND)` when no row is open-ended | - | AIMS "last qualification end" by year equals Pierre's termination years almost exactly (2000:33, 2001:15, 2002:15, 2003:18, 2004:24, ..., 2020:**176**, 2022:84/83, 2023:68/69, 2024:45, 2025:43, 2026:28/25) and **max = 2026-08-31 in both** | Not an HR termination date; a pilot on long leave whose qualification lapsed would look terminated; re-hired pilots (86 with gaps) look ACTIVE with a re-hire. Category 222 gives a corroborating date for only 26% of them. |

### 2.3 Tested SQL (read-only) - D1 snapshot at 2026-09-01 (day 17045)
Run unchanged (wrapped in aggregates) on TSC. Output: **1,500 rows, 736 ACTIVE, 764 TERMINATED, 764 NULL seniority (non-active), 1 hire_date = 1980-01-01, 11 hire_date > 2026-08-31, max termination 2026-08-31, CA 612 / FO 888, 764/764 `qual_valid_to = termination_date`**.
The WHERE clause `first_beg <= 17045` removes the **10 pilots whose first qualification starts after 2026-09-01**: 1,510 - 10 = 1,500 (this is what makes the population identical to Pierre's file).

```sql
WITH q AS (SELECT ID, RTRIM(CWBASE) AS base, AC, POS, PRIMARY_, ACTIVBEG, ACTIVEND
           FROM TSC.dbo.CREWQUAL WHERE POS IN (1,2)),                       -- pilots; use POS IN (5,6,7,8) for CABIN
life AS (SELECT ID, MIN(NULLIF(ACTIVBEG,0)) AS first_beg,
                MAX(CASE WHEN ACTIVEND=32767 THEN 99999 ELSE ACTIVEND END) AS last_end
         FROM q GROUP BY ID),
cur AS (SELECT q.*, ROW_NUMBER() OVER (PARTITION BY ID ORDER BY PRIMARY_, ACTIVBEG DESC, AC) AS rn,
               MAX(ACTIVBEG) OVER (PARTITION BY ID) AS max_beg_valid
        FROM q WHERE ACTIVBEG <= 17045 AND ACTIVEND >= 17045),              -- 17045 = DATEDIFF(DAY,'1980-01-01','2026-09-01')
lastrow AS (SELECT q.*, ROW_NUMBER() OVER (PARTITION BY ID ORDER BY ACTIVEND DESC, PRIMARY_, ACTIVBEG DESC) AS rn FROM q),
d1 AS (
  SELECT l.ID AS crew_id_raw,                                               -- pseudonymise outside SQL
         COALESCE(c.base, lr.base)                                  AS base,
         'PILOT'                                                    AS crew_group,
         CASE COALESCE(c.POS, lr.POS) WHEN 1 THEN 'CA' WHEN 2 THEN 'FO' END AS position,
         COALESCE(c.AC, lr.AC)                                      AS ac,   -- map to fleet / fleet_family with AIRCTYPE
         CAST(DATEADD(DAY, COALESCE(c.max_beg_valid, lr.ACTIVBEG), '1980-01-01') AS date) AS qual_valid_from,
         CASE WHEN c.ID IS NULL THEN CAST(DATEADD(DAY, l.last_end, '1980-01-01') AS date) END AS qual_valid_to,
         CASE WHEN c.ID IS NOT NULL AND r.SENIOR BETWEEN 1 AND 9998 THEN r.SENIOR END AS seniority_number,
         CASE WHEN c.ID IS NOT NULL THEN 'ACTIVE' ELSE 'TERMINATED' END AS employment_status,
         CAST(DATEADD(DAY, COALESCE(l.first_beg,0), '1980-01-01') AS date) AS hire_date,
         CASE WHEN c.ID IS NULL THEN CAST(DATEADD(DAY, l.last_end, '1980-01-01') AS date) END AS termination_date
  FROM life l
  LEFT JOIN cur c      ON c.ID = l.ID AND c.rn = 1
  JOIN lastrow lr      ON lr.ID = l.ID AND lr.rn = 1
  JOIN TSC.dbo.ROSTERID r ON r.ID = l.ID
  WHERE COALESCE(l.first_beg,0) <= 17045)
SELECT * FROM d1;     -- (tested only as COUNT/SUM aggregates)
```

Other tested sketches (results in the text above):
* Snapshot split (base / position / fleet family / status): ACTIVE A321-family 441 (CA 207 / FO 234; YUL 287 / YYZ 154), ACTIVE A330 295 (142 / 153; 166 / 129), TERMINATED A330 203, A321 202, B737 201, A310 114, W7S8 38, B757 14, L15 2.
* Month-start pilot headcount (below, 2.4) = `JOIN CREWQUAL q ON q.POS IN (1,2) AND q.ACTIVBEG <= d AND q.ACTIVEND >= d` for each month start `d`.
* Reproducibility of the crew-level history (effective-dated D1): same query with `d` replaced by each date; one row per (crew, period).

### 2.4 History depth and past-state availability (the explicit question)

| Object | What is stored | Range | Past states? |
|---|---|---|---|
| `CREWQUAL` | rows (crew, base, AC, position, PRIMARY_, validity, SENIOR), **ended not deleted** (118,766 of 131,018 rows have a finite end) | `ACTIVBEG` 1987-01-01 .. (7 rows = 0 "since always"); pilot rows from 1987 | **YES**: base, position (CA/FO), fleet/AC, qualification start/end for any past date. 455 pilots have CA+FO history, 807 more than one base, 846 more than one primary fleet family, 86 have validity gaps. Pilot headcount by month-start below. Consistency with the roster: Jan 2026, of 7,490 pilot flight rows, **1** has no qualification of the same position valid that day, and 150 of the 6,020 rows that carry an AC (2.5%) use an AC that is not among the pilot's valid ACs. |
| `CREWCATEG` | crew x category x validity, rows ended not deleted (17,650 of 31,563 ended) | `ACTIVEBEG` 1991 .. 2027; `0` = since always (8,355 rows) | YES for categories (PNT ACTIF from 2010, 809 pilots; PNT NON QUALIFIE 2018+, 1,001 pilots; "No longer with Air Transat" from 2008, 197 pilots). Incomplete as a status feed. |
| `ROSTERID`, `vvCREWDB`/`CREWDB` | **current state only** (seniority, schedulable window, crew master) | - | NO (only change events in `MSTLOGCRW`, from 2024-06-01, new value only) |
| `ROSTER` | one row per crew x element, with `POS` and `AC` per row | **1999-01-08 .. 2028-04-30** (training activities from 2000; pilot training rows ~4-9k/year) | YES: position and aircraft **as rostered per duty** (pilot flight rows 2023..2026: AC = 0 on 16-21%, 32Q 34-37%, 321 18-19%, A330 26-28%) = real fleet history. |
| `vvCREXPREC`/`CREXPREC` | current expiry per crew x type | - | NO. History only in `CREXPLOG` (from 2024-12-24, 1.8e9 rows, unusable) |
| `TRN*` | training module | 2026 only | NO |
| `MSTLOGCRW` | field-level change log (new values) | 2024-06-01 .. 2026-10-27 | partial: event times only |

Pilot headcount valid at month start (CREWQUAL, POS 1,2) - covers the whole 36-month ask (2023-08..): 684 (2023-08), 693 (2023-12), 720 (2024-04; YUL 494/YYZ 226), 746 (2024-12), 748 (2025-03), 743 (2025-08), 734 (2025-12), 726 (2026-03), 711 (2026-08), **736 (2026-09-01; YUL 453 / YYZ 283)**, 743 (2026-11-03). Base moves are visible (month-start 2023-09 -> 2023-10: YUL 371 -> 428, YYZ 306 -> 253; 2024-03 -> 2024-04: YUL 427 -> 494, YYZ 281 -> 226). Every valid pilot is based at YUL or YYZ at every month start since 2023-08 (no other base has a valid pilot row).
Since Pierre's file is a single snapshot, an AIMS-based D1 can be **effective-dated** (one row per crew x qualification period), which resolves his open point 8 ("historique de qualification par sous-flotte") for base/position/AC (not for the neoLR distinction, see 2.5).

### 2.5 A321 sub-fleets (320 / 321 / neoLR) - what AIMS really says
* `AIRCTYPE`: 320 = A320 (ACTYPE 18), 321 = A321 (14), **32Q = A321neo (16)** (12 premium + 187 economy seats; `AC_ADOPT_PBS` for 320, 321, 32Q = `321`, i.e. AIMS bids them as one fleet). Types `321C`, `321L`, `321N`, `32N` (CEO/neo/long-range variants) exist in the master but **no pilot CREWQUAL row exists for 321L/321N/32N** (and `321C` only for cabin 2022-12..2023-05).
* **Every pilot qualification on 321 has an overlapping 32Q row; since 2018, 1,979 of 2,125 32Q pilot rows have the identical (crew, position, start, end) 321 row, all 2,125 overlap.** Counts of valid pilots by type at 2019-07 / 2021-01 / 2023-07 / 2025-01 / 2025-08: 321 = 32Q = 117 / 389 / 422 / 462 / 407. The 320 row appears from **2023-12** (103 pilots) and grows to 444 by 2025-01 (an **A320 differences qualification roll-out**, not a fleet transfer).
* Combination of valid rows on 2026-11-03 (743 pilots): `320,321*,32Q` 423; `321*,32Q` 14; `332*,333` 287; others <= 6 (`*` = PRIMARY_ = 0).
* **Consequence for Pierre's `fleet_detail`**: for pilots with 320+321+32Q rows valid, 241 pilots have the 320 row starting *later* than the 321/32Q rows (which are equal), 185 have all three identical, 6 have a later 32Q row (4 of them also a later 320), 13 have no 320 row. Pierre's ACTIVE `A320-200` 250 / `A321-200` 181 / `A321neoLR` 5 mirror these groups: **`fleet_detail` = the type of the most recently started valid row** *(inference)*. It is an artefact (the 320 differences roll-out), which is why D1 and D2 disagree (his point 8) and why only 1-5 pilots are "neoLR". There is **no AIMS data saying which pilots are "A321neoLR pilots"**: all A321 pilots hold 32Q.
* What AIMS can say instead: **what they fly**. `ROSTER.AC` (14 = 321, 16 = 32Q) on flight rows, Jan 2026: 154 pilots flew only 32Q, 15 only 321, 280 both, 205 only A330, 4 none; `LEGMAIN.AC` for own-carrier non-cancelled legs 2024-04-24..2026-08-31: 32Q 27,082, 332 18,329, 321 14,223, 333 3,197, 320 332. So an "A321neoLR scope" must be defined by **aircraft flown** (or by an operational agreement), not by qualification. Business must say whether the simulation scope "A321neoLR/YUL/FO" means "A321-qualified YUL FOs" - which AIMS supports - or "pilots that actually fly 32Q" (434 pilots flew 32Q in Jan 2026, 154 of them only 32Q).

### 2.6 Comparison with Pierre v3 D1 (summary)
| Item | Pierre v3 | AIMS rebuild (day 17045) |
|---|---|---|
| rows / ACTIVE / TERMINATED | 1,500 / 736 / 764 | **1,500 / 736 / 764** |
| active base | YUL 453, YYZ 283 | **453, 283** |
| CA / FO | 609 / 891 | 612 / 888 |
| hire_date = 1980-01-01 | 1 | **1** (ACTIVBEG = 0 sentinel) |
| hires after 2026-08-31 | 11 | **11** |
| max termination_date | 2026-08-31 | **2026-08-31** |
| qual_valid_to NULL | 736 | **736** |
| active fleet A321 / A330 | 436 / 300 | 441 / 295 |
| seniority | unique 1..1571 (incl. terminated) | ACTIVE 2..747 distinct; terminated not usable |
| extra column | `fleet_detail` | derivable only as "latest started row" |
| crew_group | PILOT only | CABIN also derivable |
Fields Pierre computed outside AIMS (inference): the status label (qualification validity), the pseudonym, the seniority renumbering, `fleet_detail`.

### 2.7 Verdict D1: MOSTLY
Population, base, position, group, qualification dates, ACTIVE/TERMINATED status and the ordering of seniority are produced by SQL from `CREWQUAL`/`ROSTERID` and match Pierre's file to the row count; base/position/fleet can be given **per date** instead of one value per pilot. What is not in AIMS: real hire/termination dates, a real employment-status feed, a unique company-wide seniority number for historical pilots, and any "A321neoLR qualified" flag.
Missing / business inputs (ordered): (1) HR hire and termination dates (or acceptance of the qualification proxies and a rename such as `first_qual_date`); (2) status rules (mapping of categories 36/72/86/96/162/222 and absence codes INV/MAL/MAT/CSRH to `INACTIVE`, `LONG_TERM_ABSENCE`, `INITIAL_TRAINING`, `FLEET_TRANSITION`, `MANAGEMENT_OR_INSTRUCTOR`); (3) definition of "fleet" for the A321 family and the neoLR scope (qualified vs flown); (4) labels for `L15` and `W7S8`; (5) seniority policy for non-active crew; (6) the pseudonym algorithm/mapping (section 5).

---

## 3. D11 - `d11_training_sessions`

### 3.1 What the real v3 file contains (aggregates)
13,177 rows, 773 pilots (696 ACTIVE + 77 TERMINATED in D1; all `crew_id` exist in D1), `start_date` 2024-04-24 .. 2026-08-31 (same window as the other files), 0 duplicate rows, max 2 sessions per crew-day. Eleven `session_type` values (not the schema's `SIM`/`GROUND`): `TYPE_RATING_SIM` 2,257, `CBT` 2,201, `PPC` 2,104, `RECURRENT_GROUND` 1,821, `CRM` 1,779, `INITIAL_GROUND` 1,100, `SYSTEMS_EXAM` 1,030, `DANGEROUS_GOODS` 561, `SIM_OTHER` 230, `RECENCY_3_LANDINGS` 63, `PASSIVE_SIM` 31. 11,128 sessions are single-day, 2,049 multi-day (span up to 28 days). Per month 141..1,106 sessions (peak 2025-11: 1,106). `requalification_deadline` non-null on 7,358 rows (null on 5,819 = exactly the 5 types TYPE_RATING_SIM + CBT + INITIAL_GROUND + SIM_OTHER + PASSIVE_SIM); `reschedule_cost_cad_estimate` filled on every row (480..41,760, 29 distinct values).

### 3.2 How the real file was built (reverse-engineered from aggregates; inference, strongly supported)
**Source = pilot roster training activity rows**: `ROSTER` rows with `LEG_FLT < 0 AND DUTYNO < 0` (stand-alone activity, `LEG_FLT = CRCODES.ID`, both <= 0) whose code is a training code (CRCODES training flag byte 99 bit 0/1), `POS IN (1,2)`, mapped by code to `session_type`, **consecutive days of the same type merged into one session** (`start_date` = first day, `end_date` = last day). Learner codes only: the trainer/instructor codes (`TPP2/TPP3`, `TSM2/TSM3`, `TEPP`, `TETT`, `TSOP`, `TGEN`, `TRLI`...), `REU6` (annual meeting, 500 rows), `REUI`, `SHWP`, `MINS`, `PVTA` and the discontinued `SIMP` are not in the file.
Proof: the AIMS counts below (same window, `POS IN (1,2)`) reproduce Pierre's totals and *crew counts*:

| Pierre `session_type` | Candidate CRCODES codes (description) | AIMS sessions / crews (window) | Pierre sessions / crews | Match |
|---|---|---|---|---|
| PPC | `PPC2` (PPC A321), `PPC3` (PPC A330) | 2,105 / 496 | 2,104 / 496 | exact |
| SYSTEMS_EXAM | `SY20`, `SY30` (system exam 320/330 online) | 1,032 / 633 | 1,030 / 633 | exact |
| DANGEROUS_GOODS | `DG` | 562 / 544 | 561 / 544 | exact |
| TYPE_RATING_SIM | `SM21..SM26` (SIM A321 phases 1-6), `SM31..SM36` (A330), `SIMI` (initial sim) | 2,254 / 493 | 2,257 / 493 | exact (+-3) |
| CBT | `PEL1`, `PEL3`, `PEL6` (Pelesys), `CBT`, `CBTI` | 2,213 / 737 | 2,201 / 737 | +-12 |
| CRM | `EPT` (CRM-A online), `EPTP` (CRM-B class/Fire-Ditch), `EPTT` (CRM-C) | 1,761 / 733 | 1,779 / 741 | +-18 |
| RECURRENT_GROUND | `GEN` (cours generiques) | 1,835 / 745 | 1,821 / 749 | +-14 |
| SIM_OTHER | `SIM`, `SIMU` (simulator, CAE) | 238 / 145 | 230 / 143 | +-8 |
| RECENCY_3_LANDINGS | `LSI2`, `LSI3` (simulator 3 landings A321/A330) | 71 / 33 | 63 / 29 | +-8 |
| PASSIVE_SIM | `SMP2`, `SMP3` (passive sim 320/330) | 33 / 30 | 31 / 28 | +-2 |
| INITIAL_GROUND | **not recovered**: best candidate set (`SOP, PRLI, INSI, INT6, JSOP, JCRM, PERF, CCMD, EET, FIRE, FORM, PECA, REU2`) gives 728 sessions / 386 crews | 728 / 386 (candidate A) | 1,100 / 273 | **NO** - code list unknown (activity concentrated 2024-04..2025-05, 2024 new-hire classes) |

Month check: sessions *starting in January 2026*: AIMS SYSTEMS_EXAM 88, CRM 73, RECURRENT_GROUND 57, TYPE_RATING_SIM 52, PPC 47, DG 24, SIM_OTHER 4, CBT 4, RECENCY 4 vs Pierre 87, 73, 57, 52, 47, 24, 5, 4, 4 (CRM crews 64 = 64; SYSTEMS crews 87 = 87).
Per-day costs in his file: `reschedule_cost_cad_estimate` = (end_date - start_date + 1) x a **constant per type** (SYSTEMS_EXAM and RECENCY 480; DG and CBT 720; PPC, TYPE_RATING_SIM, SIM_OTHER, PASSIVE_SIM 960; CRM, RECURRENT_GROUND, INITIAL_GROUND 1,440; verified for spans 1..3 days). 480 = 2 h x $240/h (the single-time hourly rate quoted in PierreEmail.md) *(inference)*: 2 h / 3 h / 4 h / 6 h of pay per day. It does **not** follow the AIMS flight-time credit of the codes (CRCODES bytes 89-90: PPC 300 min, SY 180, DG 60, GEN/EPT 360).
`requalification_deadline` = `end_date` + {PPC 365, SYSTEMS_EXAM 365, CRM 365, RECURRENT_GROUND 365, DANGEROUS_GOODS 730, RECENCY_3_LANDINGS 90} days, always exactly (min = max per type), NULL for the other 5 types.

### 3.3 Column mapping

| corpus column | status | AIMS source | transformation | evidence | gap / risk |
|---|---|---|---|---|---|
| `crew_id` | DERIVABLE | `ROSTER.ID` | pseudonymise as D1 | AIMS keeps the training rows of crew who left (77 terminated crews in Pierre's file) | same pseudonym issue |
| `session_type` | DERIVABLE (mapping needs sign-off) / PARTIAL for INITIAL_GROUND | `ROSTER.LEG_FLT` -> `CRCODES.CC` | `JOIN CRCODES c ON c.ID = r.LEG_FLT`, map `RTRIM(c.CC)` to the 11 types (table 3.2); islands of consecutive `LEG_DAY` per (crew, type) = one session | Jan-2026 exact; window 0-2% per type | 11 values vs the schema's two (`SIM`, `GROUND`): CrewSim only consumes start/end; the types are informational. The code vocabulary **changes over time** (retired `SM2Q/SM3Q` (166+75 rows 2023-08..2024-04) replaced by `SM21..SM26/SM31..SM36`; PPC codes `PPC2/PPC3` from 2019, `DG` from 2021, `SY20/SY30` from 2014) - the mapping must be versioned. Non-recommendation codes `PC2U`, `PC3U`, `SM2U`, `SM3U` (11+3+6+3 rows in window = failed/not-recommended PPC/SIM) are not in Pierre's file. |
| `start_date` | DERIVABLE | first `ROSTER.LEG_DAY` of the island | `DATEADD(DAY, n, '1980-01-01')` | - | `LEG_DAY` is the **UTC** day of the activity; activity times are UTC minutes (`GRDDUTYBEG/END`). Sim sessions 11:00-27:00 UTC (4 of 35 PPC2 rows and 4 of 37 SM21 rows in Jan 2026 cross UTC midnight, `GRDDUTYEND` up to 1,620). A base-local date (YUL/YYZ) would differ for late sessions; CrewSim's rule is "UTC otherwise". |
| `end_date` | DERIVABLE | last `LEG_DAY` of the island (+1 when `GRDDUTYEND > 1440` if sessions crossing UTC midnight should count) | - | 2,049 multi-day sessions in Pierre | Pierre's PPC "sessions" span 2,209 calendar days for 2,105 rows, so his merge allows gaps (<= 3 d, e.g. PPC phases split) *(inference)*; my merge uses strictly consecutive days. |
| `requalification_deadline` | PARTIAL | not stored per session. Rule per type (Pierre) **or** AIMS `vvCREXPREC.EXPIDATE` (current expiry per crew x type, `EXPI.MAXDUE/DAYTYP`): DG 24 months (730 = Pierre), SYS320/SYS332 12 months (365 = Pierre), EPT 12, GEN 12, REUP 12 (365), LAND2/LAND3 90 days (90 = Pierre), **A321 / A330 "Qual/PPC" (PPC) 6 months (182..373 d observed; Pierre 365)** | `end_date + interval` or join `vvCREXPREC` on the current record | measured on valid pilots (records with `CHKLAST >= 2024-04-24`): EPT expiry-last check 366..452 d (683 of 683 manual), GEN 366..1,122 (650/661 manual), SYS 365..454 (~93% manual), DG 730..761 (691/702 manual), A321 PPC 6 months | AIMS expiry dates are **current state only**, frequently **manually overwritten** (`MAN_EXPIDATE`), and a pilot's deadline at the time of an old session is lost (CREXPLOG since 2024-12-24, nightly recalculation, 52,900 rows/pilot/27 days: not usable). `ROSTER.TRNEXPIRYDATE` is set on only 239 of 402,501 pilot activity rows in the window (EPTP 95, GEN 46, SY20 39, SY30 28, DG 19, REUI 12; value = 11..91 days *after* the session: looks like a "complete-by" date for assigned online courses, not a requalification deadline). PPC interval (365 in Pierre vs 6 months in AIMS) must be confirmed with Training. |
| `reschedule_cost_cad_estimate` | MISSING (business table) | none in AIMS (no cost of rescheduling; the CRCODES FTC minutes do not reproduce it) | lookup table `session_type -> CAD/day` x (end - start + 1) | verified from Pierre's file (constant per type and span) | Business assumption (hours x $240?). The dictionary says this column may be left empty if not in "your systems" (`pierre_analyse_donnees_reelles.md`): it is not used by the code (`used_in_code = No`). |

There are no `OPTIONAL_COLUMNS` for D1 or D11 in `loaders.py`; D1 of v3 carries one undeclared extra (`fleet_detail`).

### 3.4 Tested SQL - sessions (window 2024-04-24 .. 2026-08-31 = days 16185..17044)
Run unchanged on TSC. Output (session_type, sessions, session_days, crews): TYPE_RATING_SIM 2,254 / 2,701 / 493; CBT 2,213 / 2,661 / 737; PPC 2,105 / 2,105 / 496; RECURRENT_GROUND 1,835 / 1,894 / 745; CRM 1,761 / 2,323 / 733; SYSTEMS_EXAM 1,032 / 1,032 / 633; DANGEROUS_GOODS 562 / 562 / 544; SIM_OTHER 238 / 538 / 145; RECENCY_3_LANDINGS 71 / 72 / 33; PASSIVE_SIM 33 / 55 / 30 (total 12,104 vs Pierre's 12,077 for the same ten types). Query time < 2 s (index `ROSTER_INDEX_4 (LEG_DAY, LEG_FLT)`).

```sql
WITH map AS (SELECT v.cc, v.st FROM (VALUES
   ('PPC2','PPC'),('PPC3','PPC'),('SY20','SYSTEMS_EXAM'),('SY30','SYSTEMS_EXAM'),('DG','DANGEROUS_GOODS'),
   ('EPT','CRM'),('EPTP','CRM'),('EPTT','CRM'),('GEN','RECURRENT_GROUND'),
   ('PEL1','CBT'),('PEL3','CBT'),('PEL6','CBT'),('CBT','CBT'),('CBTI','CBT'),
   ('SM21','TYPE_RATING_SIM'),('SM22','TYPE_RATING_SIM'),('SM23','TYPE_RATING_SIM'),('SM24','TYPE_RATING_SIM'),
   ('SM25','TYPE_RATING_SIM'),('SM26','TYPE_RATING_SIM'),('SM31','TYPE_RATING_SIM'),('SM32','TYPE_RATING_SIM'),
   ('SM33','TYPE_RATING_SIM'),('SM34','TYPE_RATING_SIM'),('SM35','TYPE_RATING_SIM'),('SM36','TYPE_RATING_SIM'),
   ('SIMI','TYPE_RATING_SIM'),('SIM','SIM_OTHER'),('SIMU','SIM_OTHER'),
   ('SMP2','PASSIVE_SIM'),('SMP3','PASSIVE_SIM'),('LSI2','RECENCY_3_LANDINGS'),('LSI3','RECENCY_3_LANDINGS')) v(cc, st)),
d AS (SELECT DISTINCT r.ID, r.LEG_DAY, m.st
      FROM TSC.dbo.ROSTER r
      JOIN TSC.dbo.CRCODES c ON c.ID = r.LEG_FLT
      JOIN map m ON m.cc = RTRIM(c.CC)
      WHERE r.LEG_DAY BETWEEN 16185 AND 17044          -- narrow LEG_DAY range is mandatory (14M-row table)
        AND r.LEG_FLT < 0 AND r.DUTYNO < 0            -- stand-alone activity rows
        AND r.POS IN (1,2)),                          -- pilots (CM, PO)
g AS (SELECT ID, st, LEG_DAY, LEG_DAY - ROW_NUMBER() OVER (PARTITION BY ID, st ORDER BY LEG_DAY) AS grp FROM d),
s AS (SELECT ID, st, MIN(LEG_DAY) AS sd, MAX(LEG_DAY) AS ed FROM g GROUP BY ID, st, grp)
SELECT ID AS crew_id_raw, st AS session_type,
       CAST(DATEADD(DAY, sd, '1980-01-01') AS date) AS start_date,
       CAST(DATEADD(DAY, ed, '1980-01-01') AS date) AS end_date
FROM s;      -- tested as GROUP BY st aggregates (counts above)
```
The training-code inventory used to build the map (pilot rows, window; sessions are rows) came from: `SELECT RTRIM(c.CC), description = CAST(SUBSTRING(c.DATA_BEGIN_END,1,80) AS NVARCHAR(40)), COUNT(*), COUNT(DISTINCT r.ID) FROM ROSTER r JOIN CRCODES c ON c.ID = r.LEG_FLT WHERE r.LEG_DAY BETWEEN 16185 AND 17044 AND r.LEG_FLT < 0 AND r.DUTYNO < 0 AND r.POS IN (1,2,4) AND (CONVERT(tinyint, SUBSTRING(c.DATA_BEGIN_END,99,1)) & 3) > 0 GROUP BY ...` (84 training codes were active in the window; top: GEN 1,894, EPT 1,502, PPC2 1,330, PEL3 1,120, TPP2 907 [trainer], PEL1 784, PPC3 775, EPTP 681, REUI 661, CBTI 651, TPP3 629, SIMI 622, DG 562, SY20 560 ...).

### 3.5 History depth
`ROSTER` keeps pilot training activity rows from **2000-ish (2001: 291 pilots, 2,914 rows) to 2026**, 4,000-9,000 rows per year; therefore 2023-08..2026-08 (and the full 36 months) is covered. The **code vocabulary** is the limit: `PPC2/PPC3` exist from 2019 (257 rows in 2019, 923 in 2024), `DG` from 2021 (348), `SY20/SY30` from 2014, CRM codes throughout (EPT 2001+), and `SM2Q/SM3Q` (166 + 75 rows between 2023-08-01 and 2024-04-23) have to be added to `TYPE_RATING_SIM` for the first window (they were retired in 2024-04: 1-2 rows after). Unlike absences, training rows are *planned* activity rows (no completed/failed marker): non-recommendation codes `PC2U/PC3U/SM2U/SM3U` and `TRNFAILURE` (2025+) record failures only partly. `TRN*` tables are not usable for history (2026 only); `ROSTER.SYLIDX/SYLDATE/FACILIDX` (set on 8,803 activity rows in 2026; `FACILIDX` > 0 on 603 pilot rows in the window, 10 facilities) can enrich sessions with the syllabus (`TRNCOURSE2.SYLCODE`, e.g. "PPC 321 PH3") and the facility (A330 FFS, A320 FFS, CAE) for 2026 only.
Because the ROSTER is a live plan, a session shown in the window may have been moved/cancelled later; for the **published-then-changed** view, `LOG_ROSTER` / `PROSTER` (not profiled here, see the D2/D6 group) would be needed.

### 3.6 Comparison with Pierre v3 D11
Pierre's file ~= the SQL above (+ INITIAL_GROUND codes I could not recover) + per-type constants (cost, interval). Differences worth flagging: (a) v3 `session_type` has 11 values vs `SIM|GROUND` in the schema/dictionary; (b) `reschedule_cost` is not an AIMS fact; (c) `requalification_deadline` is rule-based (PPC 365 d vs 6 months in `EXPI`); (d) 773 pilots only, drafts-relevant roles only (no instructor/trainer sessions); (e) Pierre's email says "1 020 sessions pour 419 pilotes" for v2 and the v3 has 13,177 / 773 - v2 and v3 are different extraction logics; v3 is the one reproduced here.

### 3.7 Verdict D11: MOSTLY
Sessions (crew, type, start, end) can be generated directly and reproduce the v3 numbers within 0-2% for 10 of 11 types, with 2000+ history. Missing / business inputs (ordered): (1) agreed `CRCODES` -> `session_type` mapping, including the `INITIAL_GROUND` code list and treatment of trainer codes, `REU6/REUI`, `FIRE`, `EET`, `PERF`, `SIMP`, non-recommendation codes; (2) `reschedule_cost_cad_estimate` table (CAD per day by type) or leave empty; (3) requalification intervals per type (PPC 6 vs 12 months) or read `vvCREXPREC.EXPIDATE` for the **current** deadline only; (4) local vs UTC date rule for sessions crossing midnight; (5) whether failed/moved sessions must be reconstructed (needs `LOG_ROSTER`/`PROSTER`).

---

## 4. Crew attributes needed by the other datasets (D2/D4/D5/D6/D7/D10 `base`, `fleet`, `position`)

| Need | AIMS answer | Notes |
|---|---|---|
| `base` of a crew on a day (D2 block base, D4/D5 base, scope filters) | `CREWQUAL.CWBASE` valid on the day (`TOP 1 ... ORDER BY ACTIVBEG DESC, ACTIVEND DESC`; R3/R4 already do this) | exact, history from 1987; one base/day/crew. D2 `*_local` uses the base timezone (`crew_base_timezone`, `GetEffectiveOffset*`). |
| `position` CA/FO | `CREWQUAL.POS` valid on the day, or `ROSTER.POS` of the element (`ROSTER.POS` = position flown; drafted crew are given POS 1 for pilots - R3 constants) | for drafted elements `ROSTER.POS` can be the *draft slot* rather than the qualification (see `drafts.md`): use `CREWQUAL` for the crew's real position. |
| `fleet` | primary `CREWQUAL.AC` on the day, or `ROSTER.AC` (what was flown; AC = 0 on ~19% of pilot flight rows: deadheads/no-type -> complete with `LEGMAIN.AC`) | the A321 family is one pilot pool (320+321+32Q); see 2.5. |
| `crew_group` PILOT/CABIN | `POS` 1-4 / 5-8 (`vvPositions.CK_CB`, `position_category`) | ME (3) classification differs between AIMS and the planner table (no live crew). |
| `seniority_number` | `ROSTERID.SENIOR` (current), no history | for historical draft order reconstruct from first qualification start (Spearman 0.998 with SENIOR). |
| `employment_status`, `hire`, `termination` | qualification validity; categories 36/72/86/96/222; roster leave codes | proxies only, see 2.2. |
| qualification validity history incl. A321neoLR | `CREWQUAL` (full), neoLR: **not separable** | see 2.5. |

Reference sketch (tested): month-start pilot headcount by base/position (`CREWQUAL` x month starts) returned the series in 2.4; `ROSTER` vs `CREWQUAL` consistency for Jan 2026 returned 7,490 pilot flight rows / 658 crews / 1 without same-position qualification / 150 with an AC not qualified.

## 5. `crew_id` pseudonymisation (reproducible, `P######`)

* AIMS ids range 5..999999 (`ROSTERID.ID` max 999999, pilots up to 888888): they fit a 6-digit domain **exactly** (10^6 values) and look like employee numbers *(inference)*, so `P` + `ID` is forbidden.
* Pierre's `crew_id` are uniformly spread over 0..999999 with no correlation to seniority/hire order (rank correlation -0.008), 1,500 distinct values, min gap 1: consistent with a **keyed hash / random permutation of the id**, but his key cannot be recovered and his mapping "stays with him" (`pierre_analyse_donnees_reelles.md` rule 4) - so reproducing **his** pseudonyms requires him to provide the mapping table or the algorithm and key.
* Proposed reproducible scheme (stateless, collision-free, same pseudonym in every file and every extraction): **keyed Feistel permutation of the 6-digit id** with an HMAC-SHA-256 round function; the key is stored in a secret store, never in the repo or the corpus.
  ```python
  import hmac, hashlib
  def make_pseudonymiser(key: bytes, rounds: int = 4):
      f = [[int.from_bytes(hmac.new(key, f"{i}:{r}".encode(), hashlib.sha256).digest()[:8], "big") % 1000
            for r in range(1000)] for i in range(rounds)]
      def pseudo(crew_id: int) -> str:          # 0 <= crew_id <= 999_999
          l, r = divmod(crew_id, 1000)
          for i in range(rounds):
              l, r = r, (l + f[i][r]) % 1000     # balanced Feistel over Z1000 x Z1000 => bijection
          return f"P{l*1000 + r:06d}"
      return pseudo
  ```
  Tested (with a dummy key): the 4-round network maps 0..999,999 onto **1,000,000 distinct outputs** (bijection, no collisions) in 1.2 s and is invertible (round-trip checked). A salted hash `mod 10^6` would collide (about 19 expected collisions over 6,151 crews) and then needs a persisted mapping; the permutation avoids that. Compute it in the extraction job (Python/CrewSchedAI), not in SQL, and keep `crew_id_raw` out of every file. Law 25: pseudonymisation with a secret key is reversible by the key holder - treat the key like the mapping table.

## 6. Sources, objects and query log (short)
Files read: `docs\aims_semantic\README.md` and `tables\{vvCREWDB,ROSTERID,CREWQUAL,CREWCATEG,CREWCAT,AIRCTYPE,vvAIRCTYPE,vvPositions,position_category,EXPI,vvCREXPREC,CRCODES,ROSTER}.md`, `_raw\{q.ps1,columns.json,indexes.json,all_tables.txt}`; CrewSim `loaders.py` (lines 33-215), `data_dictionary.md` (D1, D11), `Pierre3.md`, `pierre2.md`, `PierreEmail.md`, `backlog\verify\pierre_analyse_donnees_reelles.md`, `finding_after_pierre_dtata.md`. ~60 read-only queries (about 30 per dataset), all through a SELECT-only wrapper equivalent to `q.ps1` (copy kept in `%TEMP%`, nothing written to the repo apart from this file). Big tables were only hit with indexed narrow predicates (`ROSTER` by `LEG_DAY` range/`ID`; `MSTLOGCRW` by `AIMSTABLEID` + `ONDAY`; `CREXPLOG` by `TOP 1` on the `ADAY` index and by one `CREW_ID` for 27 days - one single-day `COUNT(*)` timed out and was not repeated).

## 7. Open questions for the business (ordered)
1. HR source for hire date, termination date, employment status (Pierre's Snowflake mart? HRIS?), or accept qualification-boundary proxies and rename the columns.
2. Define the A321 "fleet": pilot pool (320+321+32Q, AIMS PBS code `321`) vs aircraft flown (32Q = neo/LR). Needed before any "A321neoLR/YUL/FO" scope; the 5 "neoLR" rows of Pierre are an artefact.
3. Training: sign-off on the code -> `session_type` map, the INITIAL_GROUND codes, trainer codes, and the cost / interval tables; decide UTC vs local session dates.
4. Seniority: confirm that CrewSim needs only the order among ACTIVE pilots (AIMS `ROSTERID.SENIOR`), and how to rank historical pilots (first qualification start).
5. Provide Pierre's pseudonym algorithm or accept the keyed permutation of section 5 (ids will then differ from his files).

