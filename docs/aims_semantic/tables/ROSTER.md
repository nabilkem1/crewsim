# ROSTER  (Table)  - Crew roster: one row per crew member x flight leg / ground activity of the crew's published schedule

## 1. Purpose & business meaning

`TSC.dbo.ROSTER` is the AIMS **crew roster (crew schedule)** table: the assignment of crew members (pilots PNT and cabin crew PNC) to the things they do on each day. It is the table the whole planner-assist MCP is built on: every duty/rest/FDP/flight-time check (R0 draft list, R3 rest, R4 FDP, R5 flight-time credit, `rpt.CalculateCrewFTC`) starts by reading a crew member's `ROSTER` rows around the pairing date.

**Grain: one row per (crew member, leg-or-activity, duty instance).** There are three structurally different kinds of row (derived from profiling 2026 `LEG_DAY` 16802..17166; 819,155 rows):

| Kind | How to recognise it | 2026 rows | What it is |
|---|---|---|---|
| **A. Ground status / activity not attached to a pairing** | `LEG_FLT < 0` **and** `DUTYNO < 0`; always `DUTYNO = LEG_FLT = CRCODES.ID` (577,065 of 577,065); `LEG_CARRIER = 0`, `LEG_DEP` and `LEG_LEGCD` blank, `DUTYDAY = LEG_DAY` | 577,065 (70.4 %) | A rostered **activity code** for that crew on that day: day off (CON, CONG), vacation, sick, leave, reserve (AM/PM/LCR...), simulator, training, office, WFLY, etc. Most are untimed all-day statuses (`GRDDUTYBEG = GRDDUTYEND = 0` for 523,446 rows); 53,004 are timed (`GRDDUTYEND > GRDDUTYBEG`). |
| **B. Ground activity inside a pairing** | `LEG_FLT < 0` **and** `DUTYNO > 0`; `LEG_FLT` = `CRCODES.ID`, `DUTYNO` = `CRROUTE.CROUTE` | 3,452 (0.4 %) | A ground leg (simulator session, APT, SHOW, MAL, REU, ...) that belongs to a pairing / training route (CREWLEG row with `FLT < 0`). Carries `GRDDUTYBEG/END` (all 3,452 have end > begin) and usually `AC`. |
| **C. Flight leg (operated or deadhead)** | `LEG_FLT >= 0`, `DUTYNO > 0` | 238,638 (29.1 %) | The crew member is on flight `LEG_CARRIER`/`LEG_FLT` on `LEG_DAY` from `LEG_DEP`, as part of pairing instance (`DUTYDAY`, `DUTYNO`). `GRDDUTYBEG/END` are always 0. Whether the seat is a deadhead is **not** here: it is `CREWLEG.PAX = 1` (join on CDATE/CROUTE and the leg key). |

Lifecycle: rows are created when planners assign crew to pairings or code activities on the roster (AIMS crew-scheduling / rostering module), and are changed/deleted when crew are bumped, swapped or re-coded. `NOTDATE`/`NOTTIME`/`USER_` carry change-notification metadata. The table holds history back to 1999-01-08 and **forward planning up to 2028-04-30** (2026: all 365 days, 2027: 7,363 rows, 2028: 121 rows), so "future" rows are normal and are the published/planned roster, not actuals.
Writers: AIMS (crew assignment, activity coding, publish); planner-assist only reads it. Readers: all `R*` procedures and `rpt.*` procedures listed in section 6.

Related AIMS concepts (all inferred from code, no declared FKs):
* **Duty / pairing instance** = (`DUTYDAY`, `DUTYNO`) = (`CRROUTE.CDATE`, `CRROUTE.CROUTE`); the human pairing name (e.g. `C0290`) is `CRROUTE.DESC_`.
* **Leg** = (`LEG_DEP`, `LEG_CARRIER`, `LEG_DAY`, `LEG_FLT`, `LEG_LEGCD`) = the `LEGMAIN` / `CREWLEG` / `LEGTIMES` leg key (`DEP, CARRIER, DAY, FLT, LEGCD`).
* **Activity** = `CRCODES` row (see CRCODES.md), referenced by negative `LEG_FLT`/`DUTYNO`.

## 2. Physical facts

* Database/schema/object: `TSC.dbo.ROSTER`, user table, **14,361,823 rows** at extraction (rowcounts.json); 52 columns. Collation `SQL_Latin1_General_CP1_CI_AS` (same as DB). Columns `LEG_DEP`, `LEG_LEGCD`, `FUTCHAR0/1` are the only character columns (nchar).
* **Primary key / clustered index `ROSTER_INDEX_0` (unique)**: `(ID, LEG_DAY, LEG_DEP, LEG_CARRIER, LEG_FLT, LEG_LEGCD, DUTYNO, DUTYDAY, GRDDUTYBEG)`. Consequence: data is physically ordered by crew then leg-day, so `WHERE ID = @crew AND LEG_DAY BETWEEN a AND b` (or `DUTYDAY` range) is a cheap range seek; `GRDDUTYBEG` is in the key so that two instances of the same activity code on the same day (different start times) do not collide.
* Secondary indexes (all non-unique) and the access pattern each implies:
  * `ROSTER_INDEX_1 (LEG_DAY, ID, DUTYNO, GRDDUTYBEG)` and `ROSTER_INDEX_2 (ID, LEG_DAY, DUTYNO, GRDDUTYBEG)`: roster by day / by crew.
  * `ROSTER_INDEX_3 (ID, LEG_FLT, LEG_DAY)`: history of one crew on one flight number / activity code.
  * `ROSTER_INDEX_4 (LEG_DAY, LEG_FLT)`: crew list of a flight or all crew on an activity code on a day (used for "who is on flight X").
  * `ROSTER_INDEX_5 (DUTYNO, DUTYDAY, GRDDUTYBEG)`, `ROSTER_INDEX_6 (DUTYDAY, DUTYNO, POS)`, `ROSTER_INDEX_9 (DUTYDAY, DUTYNO, ID)`: crew complement of one pairing instance (by position / by crew id). This is the access path of `rpt.Get_Detailed_Pairing`, `rpt.usp_GetPairingID` and the "draft" reads.
  * `ROSTER_INDEX_7 (SYLDATE, SYLIDX, SYLDAYNO, SYLDTIDX)` and `ROSTER_INDEX_8 (SYLIDX, LEG_DAY)`: training-syllabus lookups.
  * `ROSTER_INDEX_10 (FACILIDX, LEG_DAY, GRDDUTYBEG)`: occupancy of a training facility (simulator / classroom) per day and start time.
* Size/performance: 14 M rows, ~0.82 M rows per year since 2019 (see section 8). **Never scan without `ID` and/or a `LEG_DAY`/`DUTYDAY` range.** There is no partitioning evidence.

## 3. Column dictionary

Date encoding everywhere: **"day number" = days since 1980-01-01** (`DATEADD(DAY, n, '1980-01-01')`; `@BaseDate = '1980-01-01'` in every procedure). Today (2026-11-03) = 17108. Time encoding: **minutes since 00:00 UTC of the day number named in the text**, can exceed 1439 (cross midnight), can be negative.

### 3.1 Identity of the row (PK columns)

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| ID | int | NO | Crew member identifier (internal crew id, **not** an employee number). | Joins `ROSTERID.ID`, `vvCREWDB.ID`, `CREWQUAL.ID`; procedures pass it as `@Crew_ID` (NVARCHAR) and compare `r.ID = @Crew_ID`. Range 5..800900 in the table. 2,935 distinct crew in 2026; all have a `ROSTERID` row. | R3/R4/R5 `WHERE r.ID = @Crew_ID`; profiled |
| DUTYNO | bigint | NO | **Duty / pairing-route number** of the duty instance the row belongs to. For a pairing it is `CRROUTE.CROUTE` (12-digit surrogate key, 137,980,564,021..383,765,197,657 in 2026, > int range for 242,090 rows); for a pure ground activity (kind A) it is the **activity code id** (negative, = `CRCODES.ID` = `LEG_FLT`). | `> 0` pairing instance (kinds B, C); `< 0` activity (kind A); never 0 in 2026. | R3 `JOIN CRROUTE cro ON cro.CDATE = r.DUTYDAY AND cro.CROUTE = r.DUTYNO`; R0 `JOIN CRCODES c ON c.ID = r.DUTYNO`; `rpt.usp_GetPairingID` `r.DUTYNO > 0`; profiled (577,065 rows `DUTYNO = LEG_FLT`) |
| DUTYDAY | smallint | NO | **Start day (day number) of the duty / pairing instance** = `CRROUTE.CDATE`. All legs of a multi-day pairing share the same `DUTYDAY`; `LEG_DAY` advances. For kind A `DUTYDAY = LEG_DAY`. | Day number since 1980-01-01. `LEG_DAY - DUTYDAY` is 0..11 (2026): 703,965 rows equal, 115,190 later. Range 6947..17652 (1999-01-08..2028-04-30). | R3/R4 `r.DUTYDAY BETWEEN @TargetLegDayFrom AND ...`; `rpt.Get_Detailed_Pairing` `DUTYDAY = @TargetCDate`; profiled |
| LEG_DAY | smallint | NO | **Day number of the leg / activity** (the UTC date of the scheduled departure for a flight, the roster day for an activity). Anchor for all minute-offsets in the row (`GRDDUTYBEG/END`, `REPORTTIME`, `DEBRIEFTIME`). | Day number since 1980-01-01 (UTC date, same as `LEGMAIN.DAY`). | R0 `r.LEG_DAY BETWEEN @StartDateNum AND @EndDateNum`; R4 `DATEADD(DAY, r.LEG_DAY, @BaseDate)`; joins `lm.[DAY] = r.LEG_DAY` |
| LEG_DEP | nchar(8) | NO | **Departure airport of the leg** (IATA code, e.g. `YUL`), part of the leg key. **Blank (8 spaces) for kind A** (pure activities). Space padded (`'YUL     '`); trailing spaces are ignored by `=` but not by `LEN`/concatenation. | 3-letter IATA station for flights; `''` for activities. Collation `SQL_Latin1_General_CP1_CI_AS` (procedures add `COLLATE SQL_LATIN1_GENERAL_CP1_CI_AS` when joining to temp tables). | R3/R4 `lm.DEP = r.LEG_DEP`; profiled (577,065 blank rows in 2026) |
| LEG_CARRIER | smallint | NO | **Carrier id** of the leg, part of the leg key: `vvCarriers.ID`. `0` for kind A. `1` = the home (own-brand) carrier (`rpt.usp_GetPairingID` hard-codes `CARRIER = 1`; 210,353 of 238,638 flight rows in 2026); other ids (13, 73, 9, 434, 3, 433, ...) are partner/charter carriers (ground-transport carriers have `vvCarriers.CAT = 1`, see R4/R5 deadhead logic). | 107 distinct (carrier, leg code) combinations in 2026. | R3/R4 `crr.ID = r.LEG_CARRIER`; `rpt.usp_GetPairingID`; profiled |
| LEG_FLT | smallint | NO | **Flight number of the leg** (operated or deadhead), or **negative `CRCODES.ID` of the ground activity** when `< 0`. Part of the leg key. | `>= 0` flight number (observed max 9999; flight numbers can repeat on a day on multi-stop flights, hence the leg key includes `LEG_DEP`/`LEG_LEGCD`). `< 0` = `-(activity code)`, joins `CRCODES.ID` (all 255 distinct negative values in 2026 match a `CRCODES` row). Range -497..9999. | R3/R4 `r.LEG_FLT < 0` branches; R5 `CRCODES c ON c.ID = r.LEG_FLT`; profiled |
| LEG_LEGCD | nchar(2) | NO | **Leg code** (disambiguates several legs with the same DEP/CARRIER/DAY/FLT; blank normally, `A`/`B`/`D` on split/extra legs). Part of the leg key. | Blank for 99 % of rows (2026: 1,375 rows `A`, 257 `D`, 66 `B` for carrier 1). | `lm.LEGCD = r.LEG_LEGCD` in all procedures; profiled |
| GRDDUTYBEG | smallint | NO | **Start of a ground activity**, minutes since 00:00 UTC of `LEG_DAY`. `0` for flight legs (always 0 in 2026) and for untimed all-day statuses. In the PK so several timed instances of an activity can coexist. | 0..1436 observed; see gotcha: `GRDDUTYBEG % 1440 = 0 AND GRDDUTYEND % 1440 = 0` is a **placeholder (zero-length / all-day)**, not a duty. | R4 `DATEADD(MINUTE, r.GRDDUTYBEG, DATEADD(DAY, r.LEG_DAY, @BaseDate))`; R5 `NOT (r.GRDDUTYBEG % 1440 = 0 AND r.GRDDUTYEND % 1440 = 0)`; profiled |

### 3.2 Position, report/debrief, standby

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| POS | tinyint | NO | **Crew position (seat) on this leg**: `vvPositions.ID`. Pilot (PNT) vs cabin (PNC) is derived through `dbo.position_category`. | 1 CM captain, 2 PO first officer, 3 ME flight engineer (PNC so far), 4 SP supervising pilot, 5 DV flight director, 6 DA assistant flight director, 7 AB flight attendant, 8 SU supervisor. PNT = {1,2,4}; everything else PNC. 2026 rows: pos 1 = 112,708, 2 = 114,625, 5 = 104,786, 7 = 485,986, 8 = 1,050 (3/4/6 unused). Drafted crew are given POS 1 (PNT) or 3 (PNC). | `dbo.position_category.sql`; R3 `@DRAFT_POS_PNT = 1`, `@DRAFT_POS_PNC = 3`; `rpt.usp_GetPairingID` `r.POS IN (1,2)`; profiled |
| REPORTTIME | smallint | YES | **Manual report-time override** for the duty, minutes since 00:00 UTC of `LEG_DAY`. `0` (or NULL) = no override, standard report offset applies (-60 min, -80 overseas PNC, ...). Negative values exist (min -330, 161 flights) but procedures only honour `> 0`. | 2026 flights: `> 0` for 5,364 / 238,638 (2.2 %); ground rows ~always 0. Evidence it is relative to `LEG_DAY` (not `DUTYDAY`): joined to `LEGMAIN.STD`, `STD - REPORTTIME` falls in 30..120 min for 1,810 of 4,072 later-day legs when anchored on `LEG_DAY`, but for 0 when anchored on `DUTYDAY`. **R3/R4 use `LEG_DAY`; R5 and `rpt.CalculateCrewFTC` anchor it on `DUTYDAY`** (inconsistent, see section 9). | R3/R4/R5 `WHEN r.REPORTTIME > 0 THEN DATEADD(MINUTE, r.REPORTTIME, DATEADD(DAY, r.LEG_DAY|DUTYDAY, @BaseDate))`; profiled |
| DEBRIEFTIME | smallint | YES | **Manual debrief (end of duty) override**, same scale and rule as `REPORTTIME`. | `> 0` for 1,102 flight rows in 2026; max 2538. | same as above |
| SBYON | smallint | YES | Standby-on time (naming inference: time the crew goes on standby). **Always 0 in 2026**; not used by any procedure. | unknown - not used by any procedure | profiled (0 in all 2026 rows) |
| GRDDUTYEND | smallint | YES | **End of a ground activity**, minutes since 00:00 UTC of `LEG_DAY`; may exceed 1440 (crosses midnight, max 2159 in 2026). 0 for flights/all-day statuses. | Duty start/end for activities: start `GRDDUTYBEG`, end `GRDDUTYEND`; CRCODES report offset is subtracted from the start and debrief offset added to the end (see CRCODES.md). | R4 `DATEADD(MINUTE, r.GRDDUTYEND, ...)`; R5 `MAX(DATEADD(MINUTE, debrief_offset, DATEADD(MINUTE, r.GRDDUTYEND, ...)))`; profiled |

### 3.3 Aircraft, qualification, category snapshot

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| AC | tinyint | YES | **Aircraft type id of the leg** (`AIRCTYPE.ACTYPE`), set on flight legs (208,723 of 238,638 in 2026) and on 2,090 of the 3,452 in-pairing ground rows; 0 for pure activities. | 4 = A330-200 (IATA 332), 6 = A330-300 (333), 14 = A321 (321), 16 = A321neo-type `32Q`, 18 = 320; 101/102 unknown (25 rows). Counts 2026: 16 -> 80,843; 4 -> 79,777; 14 -> 36,645; 6 -> 13,521. | `AIRCTYPE` lookup by profiling; not used by procedures |
| SUPPORTCREWPOS | tinyint | YES | Support-crew position (naming inference). **0 in every 2026 row**. | unknown - not used by any procedure | profiled |
| TRNEXPIRYDATE | smallint | YES | For **training activity rows**: day number until which the training obtained is valid (inference: ANN, FAID, DV2, EPTP, EPTT, GEN, SY20/SY30 rows carry 16771..17136). 0 for 99.8 % of rows. | Day number; 818,149 of 819,155 rows are 0. | profiled (rows by CRCODES code); not used by procedures |
| QUALCAT | tinyint | YES | Qualification category (naming inference). **0 in every 2026 row**. | unknown - not used by any procedure | profiled |
| CWCATEG_CRCATEGBYT | binary(32) | YES | **Snapshot of the crew member's category bitmap** (32 bytes = 256 category flags, bit n = `CREWCAT.CREWCAT` n+1, same layout as the category bitmaps decoded in R0/`rpt.Get_Custom_Rules_*`) copied onto the roster row at assignment time. Non-zero on 100 % of 2026 rows, 2,070 distinct patterns. Denormalised: the authoritative source is `CREWCATEG`. | Not decoded by any procedure here. | naming inference; profiled (distinct/non-zero only, content not read) |
| CODEIDX | smallint | YES | Code index (naming inference): small set of values {128,129,135,141,143,145} on 94 flight rows in 2026; 0 elsewhere. | unknown - not used by any procedure | profiled |
| LANG | binary(10) | YES | **Snapshot of the crew member's language-skills bitmap** on the row (103 distinct patterns; non-zero for 812,130 rows). Personal-skill data: not profiled further. | bitmap | naming inference |

### 3.4 Syllabus / facility (training scheduling)

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| SYLIDX | smallint | NO | **Training syllabus index** the activity belongs to (naming inference: "SYL" = syllabus). >0 for 8,803 kind-A rows in 2026, all on training/instructor codes (INIT, ANN, EPTT, FAIT, FAID, DV1..DV7, GEN, NEW1, REUI, DSOP, ...) and on `CON` (1,215) when a day off is inside a course. 0 for flights. 49 distinct values (0..168). | index into a syllabus table that is **not** in the extracted schema | profiled by code; indexes `ROSTER_INDEX_7/8` |
| SYLDATE | smallint | NO | Syllabus start date / reference day (inference): day number; > 0 on 8,779 rows, equals `LEG_DAY` on 3,808 of them (the first day of the course). | day number | profiled |
| SYLDAYNO | tinyint | NO | Day number **within the syllabus** (0..6) (inference). | 0..6 | profiled |
| SYLDTIDX | smallint | NO | Syllabus detail/time-slot index (inference), 0..14. | 0..14; `(SYLDAYNO 0, SYLDTIDX 1)` = 2,404 rows, the most common | profiled |
| FACILIDX | smallint | NO | **Training facility index** (simulator bay / classroom) booked for the activity (inference from the index `(FACILIDX, LEG_DAY, GRDDUTYBEG)`). >0 on 7,338 kind-A rows in 2026 (INIT, ANN, EPTT, FAIT, FAID, DV*...), `-1` on 239 rows (facility not assigned), 0 otherwise. 27 distinct values (-1..52). | index into a facility table not in the extract | profiled; `ROSTER_INDEX_10` |

### 3.5 Notification, hotel, check-in, misc flags

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| USER_ | smallint | YES | AIMS **user id that last created/changed the row** (109 distinct in 2026, never 0/NULL). | user index | naming inference; profiled |
| CHECK_IN | smallint | YES | Crew **check-in** time recorded for the flight (naming inference), minutes (range -1432..1394). Non-zero only on flight rows (87,187 of 238,638 in 2026); `STD - CHECK_IN` averages 817 min, i.e. **not** a simple minutes-since-midnight of the leg day, semantic unresolved. | unknown encoding | profiled; not used by procedures |
| CHECK_OUT | smallint | YES | Check-out counterpart. **0 on every 2026 row.** | unknown - not used | profiled |
| AGE | tinyint | YES | Value 0..80. Possibly the crew member's age at the time of the roster row (naming inference). Personal data - **not profiled beyond range**, not used by any procedure. | unknown | naming inference |
| NOTDATE | smallint | YES | **Date (day number) the crew was notified** of / the row was last published or changed (inference). Never NULL/0 in 2026 (16150..17101); greater than `LEG_DAY` for 31,047 rows (retro-active changes after the day). | day number | naming inference; profiled |
| NOTTIME | smallint | YES | Time of that notification, minutes of the day (0..1439). | minutes since 00:00 (local/UTC not determined) | naming inference; profiled |
| REPMETHOD | tinyint | YES | Method by which the crew was notified/reported (inference): values 2 (2,583), 8 (84,630), 10 (6) in 2026; 0 for 731,936 rows. | code, meaning unknown | profiled; not used |
| REPTIME | smallint | YES | Report-time companion field. **0 on every 2026 row.** | unknown - not used | profiled |
| DAYOFFIDX | tinyint | YES | Flag `1` on **day-off rows** (CON 2,192, CONG 1,016, a few N/DC/DON1/VAC/MAL rows) = 3,524 rows in 2026; else 0. Probably "this row is a day-off index/marker". | 0/1 | profiled; not used |
| RECTYPE | smallint | YES | Record type / flag word (inference): 0 for 817,923 rows; bit-style values 16, 64, 128, 4096, 8192 on 1,232 rows (128 on 1,030 of them, mostly kind-A). | bit flags, meaning unknown | profiled; not used |
| HOTELNO | smallint | YES | Hotel number (intended link to `HOTEL.HOTELNO`) - **never populated**: 0 or NULL on every 2026 row (no value > 0). Hotel stays are in `HOTAC`, not here. | unknown - not used | profiled |

### 3.6 Reserved / "future use" columns (all empty in 2026)

| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| FUTURE1 | binary(4) | YES | Reserved for future use. NULL for 176,567 rows, `0x00000000` otherwise; no non-zero value. | unused | profiled |
| FUTFLAG1 | tinyint | YES | Reserved. 0 / NULL only. | unused | profiled |
| FUTFLAGS | binary(2) | YES | Reserved. No non-zero value. | unused | profiled |
| FUTBYTE0..FUTBYTE3 | tinyint x4 | YES | Reserved bytes. 0 / NULL only. | unused | profiled |
| FUTSMALLINT0..FUTSMALLINT4 | smallint x5 | YES | Reserved smallints. 0 / NULL only. | unused | profiled |
| FUTCHAR0, FUTCHAR1 | nchar(2) x2 | YES | Reserved text. Blank in all 2026 rows. | unused | profiled |
| FUTURE | binary(10) | YES | Reserved. No non-zero value. | unused | profiled |

Column coverage check: all 52 columns of `columns.json` are named above (ID, DUTYNO, DUTYDAY, LEG_DAY, LEG_DEP, LEG_CARRIER, LEG_FLT, LEG_LEGCD, GRDDUTYBEG, SYLIDX, SYLDATE, SYLDAYNO, SYLDTIDX, FACILIDX, POS, REPORTTIME, DEBRIEFTIME, SBYON, GRDDUTYEND, AC, SUPPORTCREWPOS, TRNEXPIRYDATE, QUALCAT, CWCATEG_CRCATEGBYT, CODEIDX, LANG, USER_, CHECK_IN, CHECK_OUT, AGE, NOTDATE, NOTTIME, REPMETHOD, REPTIME, FUTURE1, DAYOFFIDX, FUTFLAG1, FUTFLAGS, RECTYPE, HOTELNO, FUTBYTE0-3, FUTSMALLINT0-4, FUTCHAR0-1, FUTURE).

## 4. Keys & relationships

* **Natural/primary key**: `(ID, LEG_DAY, LEG_DEP, LEG_CARRIER, LEG_FLT, LEG_LEGCD, DUTYNO, DUTYDAY, GRDDUTYBEG)`.
* **ROSTER -> ROSTERID** (N:1, header of the crew): `r.ID = rid.ID` (R0 lines 425/677). Every `ROSTER.ID` in 2026 (2,935 crew) has a header.
* **ROSTER -> CRROUTE** (N:1, pairing instance and its name): `cro.CDATE = r.DUTYDAY AND cro.CROUTE = r.DUTYNO` (R0 line 680, R3 line 149, R4 line 193, R5 line 455). Matches for 100 % of `DUTYNO > 0` rows (8,491 rows on days 17000-17010, 0 unmatched). `CRROUTE.DESC_` is the pairing id the planners type (`C0290`, `YYZ2`).
* **ROSTER -> CRCODES** (N:1, activity dictionary): `c.ID = r.LEG_FLT` for any row with `LEG_FLT < 0` (the complete form: covers kinds A and B; R5 line 456, R4 line 328). The procedures R0 (592, 675), R3 (289, 299) and R4 (391) join `c.ID = r.DUTYNO` instead, which only matches kind A (kind B/C have `DUTYNO > 0`, so `schedule_code`/reserve/rest flags are NULL for in-pairing ground legs). 100 % of negative values match (577,065 / 577,065 and 3,452 / 3,452).
* **ROSTER -> LEGMAIN** (N:1 for flights): `lm.DEP = r.LEG_DEP AND lm.CARRIER = r.LEG_CARRIER AND lm.[DAY] = r.LEG_DAY AND lm.FLT = r.LEG_FLT AND lm.LEGCD = r.LEG_LEGCD` (all R*). 5,000/5,000 sampled flight rows matched.
* **ROSTER -> CREWLEG** (crew-leg definition within the pairing, gives deadhead `PAX`, `LIMTABLE` pilot count, `LGFLAGS_6`): same five leg columns **plus** `cl.CDATE = r.DUTYDAY AND cl.CROUTE = r.DUTYNO` (R3 line 283, R4 line 384).
* **ROSTER -> CRLEGGROUND** (times of a ground leg): leg key + `clg.CDATE = r.DUTYDAY AND clg.CROUTE = r.DUTYNO` (R4 385).
* **ROSTER -> LEGTIMES** (actual/estimated times `ETD/ETA/BLOF/BLON/OPSATD/OPSATA`): `lts.DAY = r.LEG_DAY AND lts.DEP = r.LEG_DEP AND lts.CARRIER = r.LEG_CARRIER AND lts.FLT = r.LEG_FLT AND lts.LEGCD = r.LEG_LEGCD` (add `COLLATE SQL_LATIN1_GENERAL_CP1_CI_AS` against temp tables).
* **ROSTER -> CREWQUAL** (crew base on that day): `q.id = r.ID AND r.LEG_DAY BETWEEN q.ACTIVBEG AND q.ACTIVEND` (R0 674; R3/R4 use `OUTER APPLY TOP 1 ... ORDER BY ACTIVBEG DESC` because ranges overlap). Also `q.POS`/`q.AC` align with `r.POS`/`r.AC`.
* **ROSTER -> vvPositions / position_category**: `POS = vvPositions.ID = position_category.Position_Id`.
* **ROSTER -> vvCarriers**: `crr.ID = r.LEG_CARRIER` (CAT, GROUNDCATEGORY used for report/debrief offsets).
* **ROSTER -> vvAirports**: `LEG_DEP = vvAirports.AIRPORT` (OVERSEAS flag drives the -80 min overseas PNC report offset).
* **ROSTER -> HOTAC** (hotel stay of the same crew and duty instance): `h.CREWID = r.ID AND h.CDATE = r.DUTYDAY AND h.CROUTE = r.DUTYNO`; 3,000 / 3,000 sampled active category-0 HOTAC rows with `CREWID > 0` have a matching ROSTER row. `HOTAC.CREWID < 0` rows are vacancy placeholders and have no ROSTER row. See HOTAC.md.
* **Cardinalities**: crew x day is 1:N (2026, days 17000-17030: 63,428 crew-days with 1 row, 2,694 with 2, 154 with 3, 11 with 4; days without any row exist). A pairing instance (`DUTYDAY`,`DUTYNO`) is 1:N crew (typically 4-10 crew x legs). The same flight leg is shared by all crew of that pairing.

* **`ROSTERDT` (roster detail, EAV side table; added 2026-11-03)** - `TSC.dbo.ROSTERDT` has the same key as ROSTER plus `RECTYPE` (`ID, LEG_DAY, LEG_DEP, LEG_CARRIER, LEG_FLT, LEG_LEGCD, DUTYNO, DUTYDAY, GRDDUTYBEG, RECTYPE`) and holds typed attributes (`VALUE1`, `VALUE2`) of a roster element. N:1 to ROSTER on the full key (rows with `LEG_FLT = 0` are day-level and join on `ID + LEG_DAY` only). `RECTYPE = 21` with `VALUE1` in 15/16/19/20 marks the element as **drafted** (15/16 cabin crew, 19/20 pilots). See [ROSTERDT.md](ROSTERDT.md) and [../drafts.md](../drafts.md).

## 5. Encoding conventions & gotchas

1. **All dates are day numbers since 1980-01-01** (`smallint`; valid until 2069). Convert with `DATEADD(DAY, LEG_DAY, '1980-01-01')`; to filter by calendar date use `LEG_DAY BETWEEN DATEDIFF(DAY,'1980-01-01',@from) AND DATEDIFF(DAY,'1980-01-01',@to)`.
2. **Times are UTC minutes from 00:00 UTC of `LEG_DAY`** (`GRDDUTYBEG`, `GRDDUTYEND`, `REPORTTIME`, `DEBRIEFTIME`, and `LEGMAIN.STD/STA`). They are **not local time**; local base time is obtained with `dbo.GetEffectiveOffset(Utc)` / `AT TIME ZONE`. End values can exceed 1440 (`GRDDUTYEND` up to 2159); divide by 1440 for day carry (`DEP_DATE = DATEADD(DAY, GRDDUTYBEG/1440, ...)`).
3. **Sentinels**: `0` in `REPORTTIME/DEBRIEFTIME` = no override (code tests `> 0`); `GRDDUTYBEG = GRDDUTYEND = 0` (or both multiples of 1440) = untimed / zero-length placeholder (day off, vacation...) and **is not a duty**: R3/R4 explicitly exclude `Trip_Number IS NULL AND DEP_TIME = '00:00:00' AND ARR_TIME = '00:00:00'`; R5 excludes `GRDDUTYBEG % 1440 = 0 AND GRDDUTYEND % 1440 = 0`. `LEG_DEP` blank, `LEG_CARRIER = 0`, `LEG_LEGCD` blank on activities; `FACILIDX = -1` = facility not assigned; `HOTELNO`, `SBYON`, `CHECK_OUT`, `REPTIME`, `SUPPORTCREWPOS`, `QUALCAT` are always 0/NULL.
4. **Kind discrimination**: `LEG_FLT >= 0` = flight; `LEG_FLT < 0` = ground code. Inside the ground codes, `DUTYNO < 0` = stand-alone roster status, `DUTYNO > 0` = ground leg inside a pairing/route. A planner-assist query that wants "flights only" must use `LEG_FLT >= 0`; "activities only" `DUTYNO < 0`; "everything the crew does" both.
5. **A reserve / training / leave / rest classification is not stored on ROSTER**; it comes from decoding `CRCODES.DATA_BEGIN_END` flags (see CRCODES.md). Join on `c.ID = r.LEG_FLT` (or `DUTYNO` for kind A).
6. **Deadhead (PAX) is not a ROSTER column**: take it from `CREWLEG.PAX` (join with CDATE/CROUTE). A passenger/deadhead leg changes the report offset (-30 PNC, 0 for ground-transport carriers) and the flight-time credit (50 % for PNC, 100 % PNT).
7. **`LEG_DAY` vs `DUTYDAY`**: for filters on "roster of the crew between two dates" the procedures use `DUTYDAY` (R3/R4: `r.DUTYDAY BETWEEN @TargetLegDayFrom AND @TargetLegDayTo`) so a multi-day pairing is returned whole; R0 uses `LEG_DAY`. `LEG_DAY - DUTYDAY` is 0..11.
8. **Overrides inherited by a draft are cleared**: R5-7 sets `REPORTTIME/DEBRIEFTIME` to NULL for a drafted copy of another crew's legs, so a draft is evaluated with standard offsets.
9. **Same pairing leg appears once per crew**: to get "the legs of a pairing" take any one crew (procedures use `ROW_NUMBER() OVER (PARTITION BY DUTYDAY, DUTYNO, LEG_DAY, LEG_FLT, LEG_DEP, LEG_CARRIER, LEG_LEGCD ORDER BY ID) = 1`); a pairing with nobody assigned has **no ROSTER rows** (fallback to `CREWLEG`/`CRLEGGROUND`).
10. **Future rows**: data exists beyond today (2027-2028). A "history" check must therefore bound `LEG_DAY` itself; there is no `PUBLISHED` column (publishing horizon is `ROSTERID.PUBLISH`, 2026-12-01 at extraction, i.e. 28 days ahead).
11. **Collation**: `LEG_DEP`/`LEG_LEGCD` are `SQL_Latin1_General_CP1_CI_AS`. Procedures declare temp-table text columns with the same collation to avoid "collation conflict".
12. **Performance traps**: no leading column on `DUTYNO` alone except `INDEX_5` (`DUTYNO,DUTYDAY,GRDDUTYBEG`); `LEG_FLT` alone is not indexable (`INDEX_4` needs `LEG_DAY` first). `r.ID = @Crew_ID` with an NVARCHAR parameter is an implicit conversion of the parameter (cheap), but `TRY_CAST` first when the id comes from user text.

## 6. How the planner-assist procedures use it

* **dbo.R0_GetDraftList** (draft candidates for a pairing): (a) pairing start/end: `CRROUTE cro JOIN ROSTER r ON r.DUTYDAY = cro.CDATE AND r.DUTYNO = cro.CROUTE` with `REPORTTIME > 0` / `DEBRIEFTIME > 0` overrides, else first STD-60 / last STA+15; (b) `CPP5_Crew`: crew with a roster row whose CRCODES code is `CPP5` in the pairing window (`c.ID = r.DUTYNO`) -> excluded; (c) `RosterDays`: counts of rows per crew/day to find blank days (`OffDays` => schedule code `BLANCHE`); (d) `OnLegs`: crew's roster rows `LEG_DAY BETWEEN @StartDateNum AND @EndDateNum AND BETWEEN q.ACTIVBEG AND q.ACTIVEND`, decodes activity via CRCODES, adds `Act_Start_UTC/Act_End_UTC` from `GRDDUTYBEG/END` for ground codes (period used for the "touches another activity" overlap test) and builds categories FLIGHT / RESERVE / TRAINING / LEAVE / ACTIVITY / special codes (WFLY, CON, CONG, CONR, REAT, VACP, FERP). `POS` -> PNT/PNC through `position_category`. Output feeds the PNT draft order (clause 14.15 / 14.5.3).
* **dbo.R3_Get_Violations_RestTime / _Batch** (rest, duty split, FDP table, acclimatisation FD-PCA-3830, 700.40.1 rest at home base): reads the crew's roster `DUTYDAY` from pairing date -367 to +14 days (`@HISTORY_DAYS = 367`, `@FORWARD_DAYS = 14`); `POS` gives PNT/PNC (duty-split gap 11 h PNT / 12 h PNC); `REPORTTIME/DEBRIEFTIME` overrides; `GRDDUTYBEG/END` for activities; the drafted pairing is read from the roster of any crew on it (`cro.DESC_ = @PAIRING_ID AND r.DUTYDAY = @PairingDutyDay`), `LEG_FLT < 0` -> `ACTIVITY_LEG`. CRCODES flags give `REST_DAY` (rest flag or WFLY) and `CC_IS_Reserve`.
* **dbo.R4_Get_Violation_FDP** (flight duty period limits; also run in impact mode by R4_Get_Future_Impact for `@HorizonDays` ahead): same reads; `Pos_Category` from the **latest** roster row of the crew (`TOP 1 ... ORDER BY DUTYDAY DESC`); draft/overlap pruning (`OVERLAP_PREVIOUS_PAIRING / _ACTIVITY`).
* **dbo.R5_Get_Violation_FTC** and **rpt.CalculateCrewFTC** (flight-time credit, monthly/rolling limits): `ACTIVITY_FTC` of CRCODES (bytes 89-90) for ground rows, `LEG_FLT < 0` rows with no pairing (`cro.DESC_ IS NULL`) as previous-duty candidates; deadhead credit rules by `POS` class.
* **dbo.R4_Get_Future_Impact**: checks whether the crew is already on the pairing (`EXISTS ROSTER ... cro.DESC_ = @PAIRING_ID`).
* **rpt.Get_Detailed_Pairing**: `rosters` CTE `WHERE DUTYNO = @TargetCRoute AND DUTYDAY = @TargetCDate`, numbering crew per leg/position (`CODE_SEQ`) to match the crew complement (`CRROUTE.CREWNUM` positions) and to fill vacancies (`-VacancySeq`) -> joins `HOTAC` on `CREWID`.
* **rpt.usp_GetPairingID**: finds the other pairings (`PAIRING_ID != @PAIRING_ID`) that contain the same flight number on a date: `r.DUTYDAY = cr.CDATE AND r.DUTYNO = cr.CROUTE AND r.LEG_FLT = @PAIRING_FLT AND r.DUTYNO > 0 AND ((@pos IN ('CM','PO') AND r.POS IN (1,2)) OR (... r.POS > 2))`.
* **dbo.position_category** comment lists R0, R3, R3_Batch, R4, R5 and `rpt.CalculateCrewFTC` as readers of `ROSTER.POS`.

## 7. Typical query patterns

(All use mandatory filters: crew id and/or a `LEG_DAY`/`DUTYDAY` range, expressed as day numbers.)

```sql
-- 1. A crew member's roster for a calendar window (flights AND activities), with pairing name and activity code
SELECT r.LEG_DAY, DATEADD(DAY, r.LEG_DAY, '1980-01-01') AS leg_date,
       r.DUTYDAY, RTRIM(cro.DESC_) AS pairing_id, r.LEG_FLT, RTRIM(r.LEG_DEP) AS dep,
       RTRIM(c.CC) AS activity_code, r.POS, r.GRDDUTYBEG, r.GRDDUTYEND
FROM TSC.dbo.ROSTER r
LEFT JOIN TSC.dbo.CRROUTE cro ON cro.CDATE = r.DUTYDAY AND cro.CROUTE = r.DUTYNO
LEFT JOIN TSC.dbo.CRCODES c   ON c.ID = r.LEG_FLT AND r.LEG_FLT < 0
WHERE r.ID = @crew_id
  AND r.LEG_DAY BETWEEN DATEDIFF(DAY,'1980-01-01',@from) AND DATEDIFF(DAY,'1980-01-01',@to)
ORDER BY r.LEG_DAY, r.GRDDUTYBEG, r.LEG_FLT;

-- 2. Crew complement of one pairing instance (use CRROUTE.DESC_ + CDATE)
SELECT r.ID, r.POS, r.LEG_DAY, r.LEG_FLT, RTRIM(r.LEG_DEP) AS dep
FROM TSC.dbo.CRROUTE cro
JOIN TSC.dbo.ROSTER r ON r.DUTYDAY = cro.CDATE AND r.DUTYNO = cro.CROUTE
WHERE cro.DESC_ = @pairing_id AND cro.CDATE = DATEDIFF(DAY,'1980-01-01',@pairing_date)
ORDER BY r.LEG_DAY, r.LEG_FLT, r.POS;

-- 3. Who is on a given day in a reserve (strict reserve flag = CRCODES byte 101 bit 7)
SELECT r.ID, RTRIM(c.CC) AS code
FROM TSC.dbo.ROSTER r
JOIN TSC.dbo.CRCODES c ON c.ID = r.LEG_FLT
WHERE r.LEG_DAY = DATEDIFF(DAY,'1980-01-01',@day)
  AND r.LEG_FLT < 0
  AND TSC.dbo.bit_is_set(CONVERT(tinyint, SUBSTRING(c.DATA_BEGIN_END, 101, 1)), 7) = 1;

-- 4. Number of flight legs per crew position in a month (flights only)
SELECT r.POS, COUNT(*) AS legs
FROM TSC.dbo.ROSTER r
WHERE r.LEG_DAY BETWEEN DATEDIFF(DAY,'1980-01-01','2026-10-01') AND DATEDIFF(DAY,'1980-01-01','2026-10-31')
  AND r.LEG_FLT >= 0
GROUP BY r.POS;
```

## 8. Data profile (measured 2026-11-03; 2026 = `LEG_DAY` 16802..17166 unless stated)

* Whole table: 14,361,823 rows; `LEG_DAY`/`DUTYDAY` 6947..17652 = 1999-01-08..2028-04-30; `ID` 5..800900.
* Rows per calendar year (by `LEG_DAY`): 2009 485,556; 2010 565,452; 2011 616,779; 2012 697,786; 2013 706,399; 2014 710,448; 2015 736,130; 2016 759,019; 2017 765,991; 2018 806,934; 2019 863,358; 2020 934,719; 2021 941,066; 2022 824,342; 2023 883,049; 2024 918,348; 2025 891,711; **2026 819,155 (2,935 crew)**; 2027 7,363 (157 crew); 2028 121 (1 crew). 1999-2008: 23k-64k rows/year.
* 2026 kind split: A pure activity 577,065; B ground-in-pairing 3,452; C flight 238,638. `DUTYNO < 0` 577,065; `DUTYNO > 0` 242,090; `DUTYNO = 0` none. 6,968 distinct `DUTYNO` values, 36,360 distinct (`DUTYDAY`,`DUTYNO`) instances over the year.
* 2026 `LEG_CARRIER` x `LEG_LEGCD`: carrier 0 (activities) 577,065; carrier 1 blank legcd 210,353; carrier 13: 3,983; 73: 3,631; 9: 3,158; 434: 2,671; 3: 2,195; 433: 1,661; carrier 1 + `A` 1,375; 138: 1,351 (107 combinations).
* 2026 busiest departure airports (flight legs): YUL 65,151; YYZ 44,455; PUJ 12,228; CUN 11,817; CDG 10,979; YQB 10,121; LGW 5,842; LIS 5,344; FCO 3,929; POP 3,841.
* 2026 `POS`: 1 -> 112,708 (367 crew); 2 -> 114,625 (413); 5 -> 104,786 (550); 7 -> 485,986 (1,879); 8 -> 1,050 (34).
* 2026 activity-code usage (`DUTYNO < 0`), top: `CON` (-1) 154,871 rows / 2,718 crew; `CONG` (-2) 68,805; `INV` (-117) 51,064; `VAC` (-25) 29,672; `WFLY` (-411) 27,209; `MAP` (-20) 17,236; `FER` (-26) 15,024; `MAT` (-27) 14,568; `DON1` (-135) 14,208; `RAM` (-99) 14,130; `MAL` (-17) 14,015; `CSSM` (-255) 12,882; `VACP` (-438) 12,169; `RPM` (-100) 11,410; `CSS` (-19) 9,886. 251 distinct activity codes used as `DUTYNO` in 2026 (255 as `LEG_FLT`).
* 2026 activity classes with the R0 bitmap logic (rows / crew): leave 187,789 / 2,760; CON 154,871; CONG 68,805; other activity 67,764; reserve 31,881; WFLY 27,209; training 15,543; VACP 12,169; FERP 7,023; CONR 2,156; REAT 1,855. Rest-flag (CRCODES byte 97 bit 2) rows 313,358; strict reserve (byte 101 bit 7) 31,779.
* Timing columns, 2026: kind A `GRDDUTYBEG = 0` for 523,446, `GRDDUTYEND = 0` for 523,465, zero-length placeholders 523,419, `GRDDUTYEND >= 1440` for 15,105, `GRDDUTYEND < GRDDUTYBEG` 46 (data quirks); kind B all timed, 431 cross midnight; kind C all 0. `REPORTTIME > 0`: 5,364 flight rows; `DEBRIEFTIME > 0`: 1,102 flight rows (+2 / +11 on kind B).
* 2026 aircraft: `AC` 16 -> 80,843; 4 -> 79,777; 14 -> 36,645; 6 -> 13,521; 101 -> 13; 102 -> 12; 18 -> 2.
* 2026 reserved/unused columns: `SBYON`, `CHECK_OUT`, `REPTIME`, `SUPPORTCREWPOS`, `QUALCAT` always 0; `HOTELNO` never > 0 (NULL for ~176k rows); `FUT*` all zero.
* 2026 syllabus/facility: `SYLIDX > 0` 8,803 rows (49 distinct values), `FACILIDX > 0` 7,338, `FACILIDX = -1` 239, `TRNEXPIRYDATE > 0` 1,006.
* Rows per crew-day (days 17000-17030): 1 row 63,428; 2 rows 2,694; 3 rows 154; 4 rows 11.

## 9. Open questions / confidence

* **High confidence** (code + data): PK/grain, three row kinds, `DUTYNO`/`DUTYDAY` = `CRROUTE.CROUTE`/`CDATE`, `LEG_*` = leg key to `LEGMAIN`, `LEG_FLT < 0` = `CRCODES.ID`, day-number and UTC-minute encodings, `POS` mapping, `REPORTTIME`/`DEBRIEFTIME` override semantics, `GRDDUTYBEG/END` for activities, placeholder rule.
* **Medium**: `AC` = `AIRCTYPE.ACTYPE` (derived by value matching of 5 IDs only; 101/102 unknown), `SYLIDX/SYLDATE/SYLDAYNO/SYLDTIDX` = training-syllabus coordinates and `FACILIDX` = training facility (inferred from index names, columns being populated only for training codes and from the facility index shape; the syllabus/facility dictionaries are not in the extract), `NOTDATE/NOTTIME/USER_` = change/notification metadata, `TRNEXPIRYDATE` = validity of the training course taken.
* **Low / unknown**: `CODEIDX`, `RECTYPE` (bit values 16/64/128/4096/8192), `REPMETHOD` (2/8/10), `CHECK_IN` encoding, `AGE`, `DAYOFFIDX` exact meaning, `SBYON`, `CHECK_OUT`, `REPTIME`, `SUPPORTCREWPOS`, `QUALCAT`, `HOTELNO` (all unused / always 0), `CWCATEG_CRCATEGBYT` and `LANG` bit layouts (copied bitmaps, not decoded here).
* **Inconsistency in the repository SQL**: `REPORTTIME/DEBRIEFTIME` are anchored on `LEG_DAY` in R3/R4 but on `DUTYDAY` in R5 and `rpt.CalculateCrewFTC`. Profiling supports the `LEG_DAY` anchor (see `REPORTTIME` row); for multi-day pairings with an override on a later day the R5/FTC variant would shift the override by `(LEG_DAY - DUTYDAY)` days (override rows are rare: 2.2 % of flight rows).
* **Join gap in the repository SQL**: R0/R3/R4 join `CRCODES` on `r.DUTYNO`, so ground legs inside pairings (kind B, 3,452 rows in 2026) get no `CRCODES` row (NULL schedule code, `CC_IS_Reserve = 0`, `CC_IS_Rest = 0`); R5 joins on `r.LEG_FLT` (correct for all ground codes).
* Whether `ROSTER` contains **only published** assignments or also unpublished working drafts is unknown (no publish flag; the publish horizon is a per-crew date in `ROSTERID.PUBLISH`).

