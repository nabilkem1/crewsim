# CRCODES  (Table)  - Crew activity / duty / absence code dictionary ("schedule codes")

## 1. Purpose & business meaning

`TSC.dbo.CRCODES` is the AIMS **dictionary of crew schedule codes** (activity codes). One row = one code that can be placed on a crew member's roster day instead of a flight: day off (`CON`), vacation (`VAC`), sick (`MAL`), maternity (`MAT`), reserve / standby (`AM`, `PM`, `LCR`), simulator (`SIM`), classroom training (`FORM`, `ANN`), office work (`BUR`), union duty (`SYN`), "willing to fly" (`WFLY`), unpaid leave (`CSS`), etc. The roster (`ROSTER`) refers to a code by its **negative integer id**: `ROSTER.LEG_FLT = ROSTER.DUTYNO = CRCODES.ID` for a stand-alone roster activity, and `ROSTER.LEG_FLT = CRCODES.ID` for a ground leg inside a pairing (see ROSTER.md).

Everything the procedures know about the *meaning* of a code is **inside the binary column `DATA_BEGIN_END` (386 bytes)**: description text, effectivity dates, flight-time credit, report/debrief offsets and a block of flag bytes (rest, leave, reserve, training, ...). There is no category column. The procedures therefore decode this blob with `SUBSTRING`/`bit_is_set`, and this document records the decoding so that an LLM or analyst can classify codes without re-deriving it.

Grain: one row per schedule code (449 rows: ID -497..0; 427 with a non-blank code, 22 blank/system placeholders). Lifecycle: maintained by AIMS administrators (code catalogue); very stable (68 codes carry an end-effective date, 67 already ended). Readers: R0, R3, R3_Batch, R4, R5, `rpt.CalculateCrewFTC`. Nothing in planner-assist writes it.

Business classes (derived from the flag bytes exactly as the procedures do, see 3.2) with their weight in the 2026 roster (577,065 stand-alone activity rows):

| Class | Rule used by code | Codes | 2026 roster rows |
|---|---|---|---|
| Special pass-through (CON, CONG, WFLY, VACP, FERP, CONR, REAT) | named in R0 `@SpecialSchedCodes` | 7 | 274,088 |
| Leave / absence | byte 97 & 0x30 <> 0 (R0 `Is_Leave`) | 64 (62 here + `VACP`/`FERP` counted as special) | 187,789 |
| Reserve (R0 definition, byte 98 bit 1) | R0 `Is_Reserve` | 26 named (+5 blank) | 31,881 |
| Reserve (R3/R4 definition, byte 101 bit 7) | `CC_IS_Reserve` | 14 | 31,779 |
| Training | byte 99 bit 0 (R0 `Is_Training`) | 213 (145 classroom/other + 68 simulator) | 15,543 |
| Rest flag (day-off equivalent) | byte 97 bit 2 (R3 `CC_IS_Rest`; R3 also forces `WFLY` to rest) | 44 (41 with a code) | 313,358 (incl. CON/CONG/VAC/FER) |
| Other activity | any other flag | 119 | ~67,764 |

## 2. Physical facts

* `TSC.dbo.CRCODES`, user table, **449 rows** (rowcounts.json), 4 columns.
* **Primary key** `PK_CRCODES` (clustered, unique) on `CRCODES_ID` (identity surrogate; no business meaning).
* `CRCODES_INDEX_0` **unique** on `ID` (the business key the roster references; verified: 449 distinct IDs, all <= 0).
* `CRCODES_INDEX_1` non-unique on `CC` (access by code string). Among the 427 non-blank codes `CC` is in fact unique (427 distinct), case-insensitive collation `SQL_Latin1_General_CP1_CI_AS`.
* Tiny table: scanning/decoding it is free; the procedures materialise the decoded flags once (R0 `#SchedCodeCat`).

## 3. Column dictionary

### 3.1 Columns

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| ID | smallint | YES (never NULL, never duplicated) | **Business key of the code, as stored in the roster.** Always <= 0: `0` is the blank default row, all others are negative (`-1` = `CON`, `-411` = `WFLY`). The roster stores exactly this number in `LEG_FLT`/`DUTYNO`. | -497..0; 449 distinct; 448 negative + one 0; gaps exist (-22, -38, -44, ...). Join: `CRCODES.ID = ROSTER.LEG_FLT` (or `ROSTER.DUTYNO` for kind-A rows). | R0 592/675, R3 289, R4 391, R5 456; profiled |
| CC | nchar(8) | YES (never NULL) | **The schedule code the planner types / sees** (up to 4 characters used, space padded): `CON`, `VAC`, `SIM`, `AM`, `LCR`... 22 rows are blank (system reserved / unused slots). Unique among non-blank values. | Trailing spaces (`'MAT '`): comparisons with `=` ignore them, string output needs `RTRIM`. R0 compares `c.CC = 'CPP5'`, `schedule_code in ('CON','CONG',...)`. Some codes contain symbols (`N/D`, `N/DC`, `X.`). | R0 340/592, R4 469, R5 450 `RTRIM(ISNULL(MAX(c.CC), ...))`; profiled |
| DATA_BEGIN_END | binary(386) | YES | **Packed AIMS record of the code** (description, effectivity, credits, offsets, flag bytes). Layout in 3.2. | binary; offsets below are 1-based `SUBSTRING` positions. Smallints are **little-endian**: the procedures read them as `CONVERT(SMALLINT, SUBSTRING(x, n+1, 1) + SUBSTRING(x, n, 1))`. | all procedures; profiled |
| CRCODES_ID | int identity | NO | Surrogate identity / primary key. Unrelated to `ID`. | 1.. | columns.json (idn = true); not used by any procedure |

### 3.2 Decoded layout of `DATA_BEGIN_END` (386 bytes)

All offsets are 1-based (`SUBSTRING(DATA_BEGIN_END, n, len)`). "Code" = confirmed by repository SQL; "Profiled" = decoded from data and consistent, not used by SQL; "Unknown" = non-constant but undecoded.

| Bytes | Size / type | Meaning | Evidence |
|---|---|---|---|
| 1-80 | 40 x UTF-16LE chars | **Code description** (French/English mix, space padded), e.g. `CONGE DE MATERNITE`, `RESERVE AM PNT`, `SIMULATEUR CAE`. Read with `CAST(SUBSTRING(DATA_BEGIN_END,1,80) AS NVARCHAR(40))`. Quote the description exactly as stored when listing. | Profiled (all 449 decode as text) |
| 81-84 | 4 bytes | zero in all rows | Profiled |
| 85-86 | smallint LE | **Effective-from day number** (days since 1980-01-01); 0 = no start (inherits 1980). 284 codes have a value. | Profiled; inference (see 85-88) |
| 87-88 | smallint LE | **Effective-to day number**; 0 = open-ended. 68 codes have an end date, 67 in the past (e.g. the "DISCONTINUED" reserves `XAM`/`XPM` end 2026-01-06; `PVHR` ends 2022-07-01). | Profiled; inference: names "DISCONTINUED" align with the end dates |
| 89-90 | smallint LE | **Flight-time credit (FTC) of the activity, in minutes** (`ACTIVITY_FTC`): credit granted for the day instead of flying (240 = 4 h, 300 = 5 h simulator, 360 = 6 h training day, 0 = none). | **Code**: R3 258, R5 316, `rpt.CalculateCrewFTC` 210: `CONVERT(SMALLINT, SUBSTRING(DATA_BEGIN_END,90,1) + SUBSTRING(DATA_BEGIN_END,89,1))`. Values seen: 0 (177 codes), 60, 120, 130, 180, 200, 240 (68), 270, 275, 285, 300 (65), 312, 360 (81), 600. |
| 91-96 | 6 bytes | zero in all rows | Profiled |
| 97 | flag byte 1 | bit 2 (0x04) = **REST flag** (rest-day equivalent: day off, vacation, statutory holiday, "N/D"...). bits 4-5 (0x30) = **LEAVE flag** (leave / absence). bit 6-7, bits 0-3: other, see table below. | **Code**: R3 `bit_is_set(substring(...,1,1),2)` = `CC_IS_Rest`; R0 `(Byte1 & 48) > 0` = `Is_Leave`; R0 `Is_Activity` tests `Byte1 & 207`. `TSC.dbo.bit_is_set(byte, n)` is verified to test bit n counted from the least significant bit (0-based). |
| 98 | flag byte 2 | bit 1 (0x02) = **reserve-family flag** (R0 `Is_Reserve`). bit 5 (0x20) set on 308 codes (undecoded; set on CON, CONG, IOU and nearly all duty/training codes). bit 0 (0x01) set on 38 long-absence/unpaid/"not qualified" codes (CSS, MAP, MAT, PAT, NQ*, N/D...). | **Code**: R0 `(Byte2 & 2) > 0`; Profiled for the others |
| 99 | flag byte 3 | bit 0 (0x01) = **TRAINING flag** (R0 `Is_Training`). bit 1 (0x02) additionally set on 68 simulator / flight-deck training codes (inference: "simulator or instructor-led flight-deck session"; also `THEI`, `TCMD`, `INT3`, `MPVA`, `MINS`). Only `SHWP` has bit 1 alone. | **Code**: R0 `(Byte3 & 1) = 1`; Profiled |
| 100 | flag byte 4 | non-zero only on `RS` (1). | R0 `Byte4 > 0` feeds `Is_Activity` |
| 101 | flag byte 5 | bit 7 (0x80) = **RESERVE flag used by R3/R4** (`CC_IS_Reserve`): 14 codes. bit 2 (0x04) set on 243 timed ground-activity codes (training, simulator, office, meetings; inference: "activity occupies the duty time window"); bit 3 (0x08) on `JUP1`, `DON`, `MALO`, `CPP4`. | **Code**: R3 299 `bit_is_set(CONVERT(tinyint, substring(Substring(CC.DATA_BEGIN_END,97,6),5,1)),7)`; R4 390. |
| 102 | flag byte 6 | zero in all rows | R0 `Byte6 > 0` |
| 103-251 | 149 bytes | non-constant, undecoded | Unknown - not used by any procedure |
| 252-253 | smallint LE | **Report offset in minutes BEFORE the activity start** (briefing time): `0, 30, 60, 90`. Duty start of an activity = `GRDDUTYBEG - offset`. | **Code**: R3 263 `-1*CONVERT(SMALLINT, SUBSTRING(...,253,1) + SUBSTRING(...,252,1))`, R4 328, R5 450 |
| 254-255 | smallint LE | **Debrief offset in minutes AFTER the activity end**: `0, 15, 30, 60`. Duty end = `GRDDUTYEND + offset`. | **Code**: R3 269, R4 345/357/369, R5 452 |
| 256-386 | 131 bytes | non-constant, undecoded | Unknown - not used by any procedure |

Distinct values of the flag bytes (449 rows): byte 97 = 1, 2 (256 codes), 9, 10, 17, 25, 57, 65, 69, 129, 130 (26), 137 (35), 138, 145, 153 (19), 157, 185, 193, 194, 197 (18), 198, 205 (7), 209, 213, 217, 221 (9), 241, 242, 249 (7). Interpretation by combination (observed, partly inference):

| byte 97 | Observed meaning (examples) |
|---|---|
| 0x02 (2) | plain ground duty with no absence/rest flag: training, simulator, office, meetings, union duty, projects (`SIM`, `FORM`, `BUR`, `REU`, `ANN`...) |
| 0x82 (130), 0xC2 (194) | reserve / standby family (`AM`, `PM`, `LCR`, `RAM`, `RPM`, `REA1`, `RSV`, `CXX`...) |
| 0xC5 (197), 0xCD (205), 0xC6 (198), 0xC1 (193), 0x45 (69) | **rest family**: day off `CON`, `CONG`, `CONR`, `CMF`, `CMG`, `TDO`, `RELV`, `IOU`, `N/D`, `N/DC`, `DSP1-4`, `GATE` |
| 0xDD (221) | **vacation** (`VAC`, `VACA`, `VACM`, `VAMI`, `VNR`, `VNRA`, `IVAC`, `VACP`, `OSTW`) - rest flag AND leave flag |
| 0x9D (157) | **statutory holiday** (`FER`, `FERI`, `FERM`, `FEMI`, `FER2`, `FE2A`, `FERP`) - rest + leave |
| 0xD5 (213) | `PVHR` reduced-hours block - rest + leave |
| 0xF9 (249), 0xF1 (241), 0xF2 (242), 0xD9 (217), 0xB9 (185), 0xD1 (209) | **sickness / medical / injury / personal paid leave**: `MAL`, `MOL`, `MHB`, `MHB1`, `MALO`, `N/DM`, `MFIT`, `FI2`, `INV`, `MAL1`, `FIT3`, `CPP4`, `CPP5`, `PMAL` - leave flag, no rest flag |
| 0x99 (153), 0x91 (145), 0x89 (137), 0x8A (138) | **unpaid / long absence / administrative**: leave without pay `CSS*`, `MAP`, `NSHW`/`NSHP`/`LATE` (no-show), `MILI`, parental `MAT`/`PAT`/`PAR`, suspension `SUSV`/`SUSU`; 137/138: bereavement, resignation, reassignment, donated flights, inactive (`DEUI`, `DEM`, `INAC`, `REAF`, `DON*`, `MNL`...) |
| 0x01, 0x09, 0x0A, 0x41, 0x81 | status codes: `DISP`/`SHW1` (available/showed for flight), `SV` suspension, not-qualified `NQ*`, `WFLY` (0x81) |

Bit classification caveat: only the bits listed in the "Code" rows are used by repository SQL; the rest is observed correlation.

### 3.3 Complete list of the 449 codes, grouped by meaning

Groups follow the **R0 classification order** (special -> reserve -> training -> leave -> activity -> X) with the R3/R4 strict-reserve flag and the rest flag separated, because the two reserve definitions differ. Columns: `Eff. from/to` = bytes 85-88 converted to dates (`-` = none); `FTC min` = bytes 89-90; `Rep/Deb min` = report/debrief offsets (bytes 252-255); `b97/b98/b99/b101` = flag bytes 1, 2, 3, 5 (decimal); `2026 rows` = number of ROSTER rows with `DUTYNO = ID` and `LEG_DAY` in 2026 (stand-alone activity rows only; ground legs inside pairings are not counted). Descriptions are quoted exactly as stored (French/English, accents preserved).

Group sizes: G0 22 + G1 7 + G2 14 + G3 12 + G4a 145 + G4b 68 + G5 62 + G6a 21 + G6b 98 = 449; no code falls in "X".

Reading guide:
* **G1 special codes**: `CON` day off, `CONG` guaranteed day off, `CONR` reserved day off (congé réservé), `REAT` technical reassignment, `WFLY` "willing to fly" (available, counts as rest for R3), `VACP`/`FERP` pilot vacation / statutory holiday (collective-agreement clause CC26). R0 does not categorise them by bitmap; it passes them through as the schedule code; `CON/CONG/CONR/REAT/BL` are the "off-day" statuses of the PNT draft order (steps 5-8) and `VACP/FERP` the vacation status (step 9).
* **G2 strict reserve**: duty-free standby periods (`AM`/`PM` pilot reserve, `RAM`/`RPM` cabin reserve, `LCR` long-call reserve, `AM0`/`PM0` zero-credit reserve, `REA1` reassignment reserve, discontinued `XAM`/`XPM`/ZIKA reserves). R3/R4 set `CC_IS_Reserve = 1` for them: a reserve duty is counted at **33 %** of its report-to-debrief length in the duty-time totals (R3 `Duty_Duration`; R4 `Duty_Duration`, `Overlap_Mins` and the 7/28/365-day cumulative duty minutes M7/M28/M365), and (R4 FIX 2e) is treated as work time for early/late/night classification even without a flight leg.
* **G3 reserve-family only**: flagged reserve by R0 but not by R3/R4: `RSV` generic reserve, maternity reserves `RAMM`/`RPMM`, `RAMS`/`RPMS` switch reserves, `RAM1`, discontinued `XPM1`, `ERR4` (assignment error), `PMET`/`AMET` (reserve for non-qualified PNT), `RS` (Christmas premium amount), and **`CXX` "CANCELED FLIGHT"** (a cancelled flight kept on the roster). Note `RSVT` "RESERVE PNT" is **not** flagged by either definition (byte 98 = 36) and appears in G6b.
* **G4a / G4b training**: everything flagged training; simulator-type (G4b) vs classroom/online/instructor/meetings (G4a). R0 maps all to `TRAINING`; `EPT`, `GEN`, `DG`, `SY20`, `SY30` (online courses) and `ALPD`/`ALCD` (union release/committee, "MOVE") are **movable** (R0 `@PntMovableCodes`: do not block a PNT draft); `PECA` (promotion candidate evaluation day) is not movable.
* **G5 leave**: vacation (`VAC*`, `FER*`, `IVAC`, `VNR*`), sickness (`MAL*`, `MHB*`, `FIT*`, `INV`), parental (`MAT`, `PAT*`, `PAR`), unpaid/administrative absence (`CSS*`, `MAP*`, `SUS*`, `NSHW`...), personal days (`CPP4`/`CPP5` paid, `CPNP`/`CPNT`/`CPNC` unpaid, `JUP*` urgent personal day), `PVHR` reduced-hours block. R0 `LEAVE` = blocking for a draft; `VACP/FERP` are separately called vacation.
* **G6a** codes carry the rest flag without leave/reserve/training: availability/day-off style (`IOU`, `N/D`, `N/DC`, `CMF`, `CMG`, `TDO`, `RELV`, `CONV`, `BP`, `DSP*`, `GATE`, ...) and the online-training day-off hybrids `CON1`/`CON3`/`CON6` ("ONLINE TRAINING - n CRÉDIT").
* **G6b**: other ground duties/statuses without a class flag: administrative (`ADM`, `BTS`, `ADMP`...), donations/reassignments, not-qualified statuses, memo codes, etc.

#### G0. Blank / system-reserved / unused slots (CC is empty, 22 rows) - 22 codes

| ID | CC | Description (as stored) | Eff. from | Eff. to | FTC min | Rep/Deb min | b97 | b98 | b99 | b101 | 2026 rows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | (blank) |  | 2000-02-01 | - | 0 | 0/0 | 193 | 34 | 0 | 0 | 0 |
| -4 | (blank) | System reserved code | - | - | 0 | 0/0 | 69 | 0 | 0 | 0 | 0 |
| -7 | (blank) | System reserved code | - | - | 0 | 0/0 | 2 | 0 | 0 | 0 | 0 |
| -39 | (blank) | Reserved code for AIms | - | - | 0 | 0/0 | 2 | 10 | 0 | 0 | 0 |
| -61 | (blank) | System reserved code | - | - | 0 | 0/0 | 2 | 0 | 0 | 0 | 0 |
| -70 | (blank) | System reserved code | - | - | 0 | 0/0 | 2 | 0 | 0 | 0 | 0 |
| -101 | (blank) | system reserved code | - | - | 0 | 0/0 | 197 | 0 | 0 | 0 | 0 |
| -102 | (blank) | ''                 '' | - | - | 0 | 0/0 | 197 | 0 | 0 | 0 | 0 |
| -103 | (blank) | ''                  '' | - | - | 0 | 0/0 | 1 | 0 | 0 | 0 | 0 |
| -111 | (blank) | system reserved code | - | - | 0 | 0/0 | 2 | 2 | 0 | 0 | 0 |
| -112 | (blank) | ''               '' | - | - | 0 | 0/0 | 2 | 2 | 0 | 0 | 0 |
| -113 | (blank) | ''              '' | - | - | 0 | 0/0 | 2 | 2 | 0 | 0 | 0 |
| -150 | (blank) |  | - | - | 0 | 0/0 | 1 | 0 | 0 | 0 | 0 |
| -151 | (blank) |  | - | - | 0 | 0/0 | 1 | 0 | 0 | 0 | 0 |
| -152 | (blank) |  | - | - | 0 | 0/0 | 1 | 0 | 0 | 0 | 0 |
| -153 | (blank) |  | - | - | 0 | 0/0 | 1 | 0 | 0 | 0 | 0 |
| -154 | (blank) |  | - | - | 0 | 0/0 | 1 | 0 | 0 | 0 | 0 |
| -155 | (blank) |  | - | - | 0 | 0/0 | 1 | 0 | 0 | 0 | 0 |
| -156 | (blank) |  | - | - | 0 | 0/0 | 1 | 0 | 0 | 0 | 0 |
| -157 | (blank) |  | - | - | 0 | 0/0 | 1 | 0 | 0 | 0 | 0 |
| -158 | (blank) |  | - | - | 0 | 0/0 | 1 | 0 | 0 | 0 | 0 |
| -159 | (blank) |  | - | - | 0 | 0/0 | 1 | 0 | 0 | 0 | 0 |

#### G1. Special pass-through codes (R0 treats these by name, not by bitmap) - 7 codes

| ID | CC | Description (as stored) | Eff. from | Eff. to | FTC min | Rep/Deb min | b97 | b98 | b99 | b101 | 2026 rows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| -1 | CON | DAY OFF | 2000-02-01 | - | 0 | 0/0 | 197 | 32 | 0 | 0 | 154871 |
| -2 | CONG | DAY OFF GUARANTEED | 2000-02-01 | - | 0 | 0/0 | 197 | 32 | 0 | 0 | 68805 |
| -115 | CONR | CONGÉ RÉSERVÉ | 2003-07-01 | - | 0 | 0/0 | 197 | 32 | 0 | 0 | 2156 |
| -208 | REAT | RÉAFFECTATION TECHNIQUE | 2011-03-29 | - | 0 | 0/0 | 137 | 32 | 0 | 0 | 1855 |
| -411 | WFLY | WILLING TO FLY | 2017-01-20 | - | 0 | 0/0 | 129 | 32 | 0 | 0 | 27209 |
| -438 | VACP | VACANCES PILOTES (CC26) | 2026-01-06 | - | 270 | 0/0 | 221 | 32 | 0 | 0 | 12169 |
| -439 | FERP | FÉRIÉ PILOTES (CC26) | 2026-01-06 | - | 270 | 0/0 | 157 | 32 | 0 | 0 | 7023 |

#### G2. Reserve / standby duty - strict (byte 101 bit 7 set = CC_IS_Reserve used by R3/R4; also flagged by R0) - 14 codes

| ID | CC | Description (as stored) | Eff. from | Eff. to | FTC min | Rep/Deb min | b97 | b98 | b99 | b101 | 2026 rows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| -66 | XAM | RESERVE AM PNT - DISCONTINUED | 2003-09-01 | 2026-01-06 | 200 | 0/0 | 130 | 38 | 0 | 132 | 36 |
| -67 | XPM | RESERVE PM PNT - DISCONTINUED | 2003-09-01 | - | 200 | 0/0 | 130 | 38 | 0 | 132 | 38 |
| -76 | RAMZ | RÉSERVE AM - ZIKA | - | - | 0 | 0/0 | 130 | 10 | 0 | 132 | 0 |
| -77 | RPMZ | RÉSERVE PM - ZIKA | - | - | 0 | 0/0 | 130 | 10 | 0 | 132 | 0 |
| -99 | RAM | RESERVE AM PNC | 2003-06-01 | - | 0 | 0/0 | 130 | 10 | 0 | 132 | 14130 |
| -100 | RPM | RESERVE PM PNC | 2003-06-01 | - | 0 | 0/0 | 130 | 38 | 0 | 132 | 11410 |
| -109 | RPM1 | RESERVE PM | - | - | 0 | 0/0 | 130 | 38 | 0 | 132 | 17 |
| -160 | AM | RESERVE AM PNT | 2026-01-06 | - | 240 | 0/0 | 130 | 38 | 0 | 132 | 1229 |
| -194 | LCR | LONG CALL RESERVE | 2026-03-01 | - | 180 | 0/0 | 130 | 38 | 0 | 132 | 2369 |
| -348 | REA1 | REAFFECTATION1 | 2020-12-07 | - | 0 | 0/0 | 194 | 34 | 0 | 132 | 1386 |
| -388 | AM0 | Reserve AM PNT 0 Credits | 2021-01-01 | - | 0 | 0/0 | 130 | 34 | 0 | 132 | 167 |
| -389 | PM0 | Reserve PM PNT 0 Credits | - | - | 0 | 0/0 | 130 | 34 | 0 | 132 | 81 |
| -412 | PM | RESERVE PM PNT | - | - | 240 | 0/0 | 130 | 38 | 0 | 132 | 913 |
| -413 | PM1 | RESERVE PNT | 2026-01-06 | - | 240 | 0/0 | 130 | 38 | 0 | 132 | 3 |

#### G3. Reserve-family flag only (byte 98 bit 1 set, byte 101 bit 7 not set): R0 calls these RESERVE, R3/R4 do not - 12 codes

| ID | CC | Description (as stored) | Eff. from | Eff. to | FTC min | Rep/Deb min | b97 | b98 | b99 | b101 | 2026 rows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| -35 | RSV | RESERVE | 2000-02-01 | 2003-09-30 | 0 | 0/0 | 130 | 130 | 0 | 0 | 0 |
| -36 | RAMM | RÉSERVE AM MATERNITE | 2005-09-30 | - | 0 | 0/0 | 130 | 42 | 0 | 0 | 39 |
| -37 | RPMM | RÉSERVE PM MATERNITE | 2005-09-30 | - | 0 | 0/0 | 130 | 42 | 0 | 0 | 1 |
| -47 | CXX | CANCELED FLIGHT | 2000-02-01 | - | 0 | 0/0 | 130 | 2 | 0 | 0 | 0 |
| -78 | RAMS | RESERVE SWITCH AM | 2003-06-01 | - | 0 | 0/0 | 130 | 10 | 0 | 4 | 0 |
| -79 | RPMS | RESERVE SWITCH PM | 2003-06-01 | - | 0 | 0/0 | 130 | 10 | 0 | 4 | 0 |
| -116 | RAM1 | RESERVE AM | - | - | 0 | 0/0 | 130 | 2 | 0 | 4 | 0 |
| -180 | XPM1 | RESERVE PNT - DISCONTINUED | 2007-09-01 | 2026-01-06 | 200 | 0/0 | 130 | 42 | 0 | 0 | 0 |
| -230 | ERR4 | ERREUR D'ASSIGNATION DE RÉSERVE | - | - | 240 | 0/0 | 130 | 42 | 0 | 0 | 55 |
| -260 | PMET | Reserve PNT non qualifie | 2015-06-01 | - | 200 | 0/0 | 130 | 38 | 0 | 4 | 0 |
| -261 | AMET | Reserve PNT non qualifie | 2015-06-01 | - | 200 | 0/0 | 130 | 38 | 0 | 4 | 0 |
| -427 | RS | prime noel montant réserve | - | - | 0 | 0/0 | 130 | 14 | 0 | 4 | 7 |

#### G4a. Training - classroom / online / instructor / meetings (byte 99 bit 0 set, bit 1 clear) - 145 codes

| ID | CC | Description (as stored) | Eff. from | Eff. to | FTC min | Rep/Deb min | b97 | b98 | b99 | b101 | 2026 rows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| -9 | FORM | FORMATION - TRAINING | 2000-02-01 | - | 360 | 60/0 | 2 | 32 | 1 | 4 | 0 |
| -51 | REQ | REQUAL PRIOR TO ANNUAL | 2000-02-01 | - | 240 | 60/0 | 2 | 32 | 1 | 4 | 93 |
| -52 | THE | THÉORIE COURS | 2000-02-01 | 2024-01-01 | 360 | 0/0 | 2 | 32 | 1 | 4 | 0 |
| -54 | ENT | ENTRAINEMENT | - | - | 0 | 0/0 | 2 | 32 | 1 | 4 | 0 |
| -58 | MTCE | MEC MTCE | 2005-03-01 | - | 240 | 0/0 | 2 | 32 | 1 | 4 | 0 |
| -71 | CBT | COMPUTER BASE TRAINING | - | - | 360 | 0/0 | 2 | 0 | 1 | 4 | 0 |
| -73 | TRN3 | FORMATION - TRAINING 3 CRÉDITS | - | - | 180 | 0/0 | 2 | 0 | 1 | 4 | 5 |
| -74 | EPT | CRM-A-En ligne/Online | - | - | 360 | 0/0 | 2 | 0 | 1 | 4 | 292 |
| -75 | PERF | PERFORMANCE GROUND COURSE | 2003-01-01 | - | 360 | 0/0 | 2 | 0 | 1 | 4 | 40 |
| -120 | EPTP | CRM-B- En classe/In class- Fire/Ditch | - | - | 360 | 30/0 | 2 | 32 | 1 | 4 | 330 |
| -121 | WALK | ETOPS WALKAROUND | - | - | 180 | 0/0 | 2 | 0 | 1 | 4 | 0 |
| -122 | PVTA | CHECK PILOT TRAINING | - | - | 360 | 0/0 | 2 | 0 | 1 | 4 | 51 |
| -125 | REC3 | RECCURENT GS COURSE 330 | - | 2024-01-01 | 360 | 0/0 | 2 | 0 | 1 | 4 | 0 |
| -126 | REC4 | RECCURENT GS COURSE 310 | - | 2024-01-01 | 360 | 0/0 | 2 | 0 | 1 | 4 | 0 |
| -132 | ANN | ANNUAL TRAINING | 2023-09-01 | - | 240 | 60/0 | 2 | 32 | 1 | 4 | 1727 |
| -133 | FAID | FIRST AID - PREMIERS SOINS | 2004-09-01 | - | 240 | 60/0 | 2 | 32 | 1 | 4 | 427 |
| -134 | DITC | FIRE/DITCH | 2003-09-01 | - | 240 | 30/0 | 2 | 32 | 1 | 4 | 0 |
| -138 | CPRA | RÉANIMATION CARDIO-RESPIRATOIRE - DEFIB | 2004-09-01 | - | 240 | 60/0 | 2 | 32 | 1 | 4 | 0 |
| -140 | PECA | CANDIDAT PROMOTION - PROMOTION CANDIDATE | - | - | 270 | 30/0 | 2 | 0 | 1 | 4 | 23 |
| -141 | SIM1 | ANNUAL DRILL SIMULATOR | 2005-06-01 | 2024-01-01 | 0 | 0/0 | 2 | 32 | 1 | 4 | 0 |
| -143 | CBTI | Computer Based Training  INITIAL | 2005-11-01 | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 24 |
| -144 | FMGS | ENTRAINEMENT INITIAL 330 | 2005-11-01 | 2024-01-01 | 180 | 0/0 | 2 | 0 | 1 | 4 | 0 |
| -161 | IANN | ANNUAL TRAINING INSTRUCTOR | 2005-07-01 | 2011-10-31 | 240 | 60/15 | 2 | 32 | 1 | 4 | 0 |
| -162 | IFAI | FIRST AID TRAINING INSTRUCTOR | 2005-07-01 | 2011-10-31 | 240 | 60/15 | 2 | 32 | 1 | 4 | 0 |
| -163 | ICPR | CPR-AED INSTRUCTOR | 2005-07-01 | 2011-10-31 | 240 | 60/15 | 2 | 32 | 1 | 4 | 0 |
| -164 | IDIT | DITCHING INSTRUCTOR | 2005-07-01 | 2011-10-31 | 240 | 60/15 | 2 | 32 | 1 | 4 | 0 |
| -167 | IREQ | REQUALIFICATION TRAINING INSTRUCTOR | 2005-07-01 | 2011-10-31 | 240 | 60/15 | 2 | 32 | 1 | 4 | 0 |
| -169 | CPRI | QUALIFICATION INSTRUCTEUR CPRA | 2005-12-01 | 2024-01-01 | 240 | 60/15 | 2 | 32 | 1 | 4 | 0 |
| -170 | FAII | QUALIFICATION INSTRUCTEUR FIRST AID | 2005-12-01 | - | 240 | 60/15 | 2 | 32 | 1 | 4 | 4 |
| -173 | TH3C | THÉORIE 3 CHV | 2006-11-06 | 2024-01-01 | 180 | 0/0 | 2 | 32 | 1 | 4 | 0 |
| -174 | EPTT | CRM-C- En classe/In class | 2007-01-31 | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 360 |
| -177 | JCRM | JET TRANSITION CRM INITIAL B | - | - | 360 | 0/0 | 2 | 0 | 1 | 0 | 32 |
| -178 | TCRM | JET TRANSITION CRM INITIAL B INSTRUCTOR | - | - | 0 | 0/0 | 2 | 0 | 1 | 0 | 4 |
| -197 | FDIT | DITCHING INSTRUCTOR | 2012-12-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 0 |
| -201 | TFMG | INSTRUCTEUR FMGS | - | - | 300 | 0/0 | 2 | 0 | 1 | 4 | 0 |
| -202 | TEPP | IINSTRUCTEUR EPT 3 ANS | - | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 131 |
| -203 | TETT | INSTRUCTEUR EPT 1 AN | - | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 120 |
| -204 | TTH6 | INSTRUCTEUR THEORIE 6 CREDITS | - | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 10 |
| -205 | TTH3 | INSTRUCTEUR THEORIE 3 CREDITS | - | - | 180 | 0/0 | 2 | 32 | 1 | 4 | 1 |
| -207 | REU6 | RÉUNION ANNUELLE PNT 330/320 | 2011-09-01 | 2065-01-01 | 360 | 0/0 | 2 | 0 | 1 | 4 | 134 |
| -213 | WEB1 | FORMATION WEB | - | 2024-01-01 | 60 | 0/0 | 2 | 32 | 1 | 4 | 0 |
| -215 | FANN | INSTRUCTEUR ANNUELLE PNC 6 CRÉDITS | 2011-11-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 388 |
| -216 | FFAI | INSTRUCTEUR FIRST AID PNC 6 CRÉDITS | 2011-11-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 143 |
| -217 | FCPR | INSTRUCTEUR CPRA PNC 6 CRÉDITS | 2011-11-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 0 |
| -218 | FREQ | INSTRUCTEUR REQUAL PNC 6 CRÉDITS | 2011-11-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 38 |
| -219 | FFOR | INSTRUCTEUR FORMATION DIVERS PNC 6 CR. | 2011-11-01 | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 120 |
| -222 | B737 | FORMATION 737 | 2013-09-16 | 2024-01-01 | 240 | 0/0 | 2 | 32 | 1 | 4 | 0 |
| -223 | F737 | INSTRUCTEUR 737 | 2013-09-16 | 2024-01-01 | 360 | 60/15 | 2 | 32 | 1 | 4 | 0 |
| -224 | FINT | INSTRUCTEUR INITIALE PNC 6 CRÉDITS | 2018-04-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 351 |
| -225 | CBEX | CBTI + EXAMEN SYSTÈME | 2014-01-01 | 2024-01-01 | 360 | 0/0 | 2 | 0 | 1 | 4 | 0 |
| -226 | CBX3 | CBTI + EXAMEN SYSTÈME | 2016-11-01 | 2024-01-01 | 180 | 0/0 | 2 | 0 | 1 | 4 | 0 |
| -227 | RQ33 | RECCURENT GS COURSE 330 | 2016-10-01 | 2024-01-01 | 180 | 0/0 | 2 | 0 | 1 | 4 | 0 |
| -228 | RQ44 | RECCURENT GS COURSE 310 | 2016-10-01 | 2024-01-01 | 180 | 0/0 | 2 | 0 | 1 | 4 | 0 |
| -229 | RQ88 | RECCURENT GS COURSE 738 | 2016-10-01 | 2024-01-01 | 180 | 0/0 | 2 | 0 | 1 | 4 | 0 |
| -232 | INIR | Initial retour DV ou AB - en classe | 2018-06-01 | - | 240 | 60/0 | 2 | 32 | 1 | 4 | 289 |
| -234 | INIT | Initial nouveau AB - en classse | 2018-06-01 | - | 0 | 60/0 | 2 | 32 | 1 | 4 | 2879 |
| -235 | REC8 | RECCURENT GS COURSE 738 | 2014-01-01 | 2024-01-01 | 360 | 0/0 | 2 | 0 | 1 | 4 | 0 |
| -236 | GEN | COURS GÉNÉRIQUES | 2014-01-01 | - | 360 | 0/0 | 2 | 0 | 1 | 4 | 393 |
| -237 | SY30 | EXAMEN SYSTÈME 330 - ONLINE | 2014-01-01 | - | 180 | 0/0 | 2 | 32 | 1 | 4 | 172 |
| -238 | SY10 | Examen Systeme 313 | 2014-01-01 | 2024-01-01 | 180 | 0/0 | 2 | 0 | 1 | 4 | 0 |
| -239 | SY38 | Examen Systeme 738 | 2014-01-01 | 2024-01-01 | 180 | 0/0 | 2 | 0 | 1 | 4 | 0 |
| -240 | SY20 | EXAMEN SYSTÈME 320 - ONLINE | 2017-11-01 | - | 180 | 0/0 | 2 | 32 | 1 | 4 | 238 |
| -241 | ANNR | Annuel non reussi | 2017-01-01 | - | 240 | 60/0 | 2 | 32 | 1 | 4 | 42 |
| -242 | FAIT | FAID initial AB | 2018-06-01 | - | 240 | 60/0 | 2 | 32 | 1 | 4 | 414 |
| -243 | WEB | Online Training - Formation en ligne PNC | 2018-06-01 | - | 240 | 0/0 | 2 | 32 | 1 | 4 | 121 |
| -246 | REQR | REQUAL - NO ANNUAL NECESSARY | 2018-10-26 | - | 240 | 60/0 | 2 | 32 | 1 | 4 | 1 |
| -247 | A320 | Formation A320 | 2023-12-01 | - | 240 | 30/0 | 2 | 32 | 1 | 4 | 0 |
| -248 | F320 | Formateur A320 | - | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 0 |
| -249 | ANNQ | Non Qualifié - Évaluation Compétence | 2019-01-01 | - | 240 | 60/0 | 2 | 32 | 1 | 4 | 1 |
| -254 | PRLI | PRÉPARATION AU L.I.- en classe | - | - | 360 | 0/0 | 2 | 0 | 1 | 4 | 55 |
| -263 | DG | Cours Dangerous Goods- Online | 2021-02-01 | - | 60 | 0/0 | 2 | 0 | 1 | 4 | 106 |
| -264 | FDV | FD Meeting - part of training | - | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 56 |
| -265 | RQAN | REQ + ANN | 2020-07-22 | - | 240 | 60/0 | 2 | 32 | 1 | 4 | 0 |
| -267 | DVC | formation coach DV | - | - | 360 | 60/0 | 2 | 32 | 1 | 4 | 159 |
| -268 | ONE | day in a life of... | 2012-02-01 | - | 240 | 0/0 | 2 | 32 | 1 | 4 | 0 |
| -269 | DV0 | Formation initiale DV | - | - | 240 | 0/0 | 2 | 32 | 1 | 4 | 24 |
| -270 | DV1 | Mon rôle de leader/ My role as a Leader | 2012-01-01 | - | 240 | 0/0 | 2 | 32 | 1 | 4 | 169 |
| -271 | DV2 | Leader en action / Leader in action | 2012-01-01 | - | 240 | 0/0 | 2 | 32 | 1 | 4 | 266 |
| -272 | DV3 | Leader d'impact / Leader of Impact | 2012-01-01 | - | 240 | 0/0 | 2 | 32 | 1 | 4 | 0 |
| -273 | DV4 | Leader Proactif / Proactive Leader | 2012-01-01 | - | 240 | 0/0 | 2 | 32 | 1 | 4 | 0 |
| -274 | DV5 | Formation initiale DV | 2012-01-01 | - | 240 | 0/0 | 2 | 32 | 1 | 4 | 0 |
| -275 | DV6 | Formation initiale DV | 2012-01-01 | - | 240 | 0/0 | 2 | 32 | 1 | 4 | 0 |
| -276 | DV7 | Formation Intiale DV | 2012-01-01 | - | 240 | 0/0 | 2 | 32 | 1 | 4 | 0 |
| -278 | FDTR | FLIGHT DIRECTOR ANNUAL TRAINING | 2014-09-01 | 2024-01-01 | 240 | 60/15 | 2 | 32 | 1 | 4 | 0 |
| -279 | FQAN | REQUAL +ANN  PNC formateur 6 crédits | 2020-07-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 0 |
| -280 | TVCO | Travel Service Conversion Training | 2015-11-20 | 2024-01-01 | 270 | 60/0 | 2 | 32 | 1 | 4 | 0 |
| -281 | TCXO | Condor / Thomas Cook training | 2018-10-01 | 2024-01-01 | 270 | 0/0 | 2 | 32 | 1 | 4 | 0 |
| -292 | TV35 | Conversion Training 4hrs 35 | - | 2024-01-01 | 275 | 60/0 | 2 | 32 | 1 | 4 | 0 |
| -293 | TV45 | Conversion Training 4hrs 45 | - | 2024-01-01 | 285 | 60/0 | 2 | 32 | 1 | 4 | 0 |
| -294 | TV5 | Conversion Training 5hrs | - | 2024-01-01 | 300 | 60/0 | 2 | 32 | 1 | 4 | 0 |
| -296 | ANNX | Annuel training | 2021-07-01 | - | 240 | 60/0 | 2 | 32 | 1 | 4 | 0 |
| -297 | XFRM | PNC en extra sur la formation | 2022-03-01 | - | 240 | 60/0 | 2 | 32 | 1 | 4 | 11 |
| -299 | TRNG | TRAINING | 2007-05-01 | - | 240 | 60/0 | 2 | 32 | 1 | 0 | 0 |
| -303 | INNA | Intial Annual Tranining | 2023-09-01 | - | 240 | 60/15 | 2 | 32 | 1 | 4 | 34 |
| -312 | FINU | Instructeur sous contrat Air Inuit | - | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 5 |
| -313 | FSUB | INSTRUCT. SOUS‑CONTRAT ‑ SUBCONTRACTED | - | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 7 |
| -314 | FWRT | ECRITURE/ Writing | - | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 503 |
| -315 | FGAT | BARRIERES/Gates | - | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 148 |
| -316 | FEET | EET Instructor | - | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 6 |
| -317 | FDND | Sous Contrat DND | - | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 6 |
| -318 | FBUR | Travail de Bureau/Office Work | - | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 45 |
| -319 | TTT | Train the trainer | 2025-04-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 22 |
| -321 | INT6 | JOURNÉE INTRO | 2017-01-01 | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 43 |
| -322 | EET | EET – EMERGENCY EQUIPMENT TRAINING - FCM | 2018-01-01 | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 22 |
| -323 | SOP | THÉORIE INITIALE- en classe | 2018-01-01 | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 87 |
| -324 | CCMD | Cours de commandant-en classe | 2018-01-01 | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 26 |
| -325 | INSI | Instructeurs PNT - initial | 2018-09-01 | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 54 |
| -327 | NEW1 | jour 1 formation Initial | - | - | 0 | 0/0 | 2 | 32 | 1 | 4 | 129 |
| -328 | FSOP | instructeurs FD TRAINING | - | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 73 |
| -329 | DSOP | PARTICIPANTS FD TRAINING | - | - | 240 | 60/15 | 2 | 32 | 1 | 4 | 233 |
| -330 | REUI | Réunion instructeurs | 2017-09-01 | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 188 |
| -331 | REU7 | Réunion annuelle PNT 737 | 2017-09-01 | 2024-01-01 | 360 | 0/0 | 2 | 0 | 1 | 4 | 0 |
| -332 | REU2 | A320 WINDOW 2023 | 2023-12-01 | - | 180 | 30/30 | 2 | 0 | 1 | 4 | 0 |
| -333 | REU3 | Réunion annuelle PNT 310 | 2017-09-01 | 2024-01-01 | 360 | 0/0 | 2 | 0 | 1 | 4 | 0 |
| -334 | FCAN | Instructeur sous contrat Canadian North | 2023-09-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 0 |
| -336 | FCHK | Inspection d’avion - Aircraft inspection | - | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 0 |
| -337 | IIT | Formation Initiale Instructeur PNC | - | - | 0 | 60/15 | 2 | 32 | 1 | 4 | 25 |
| -339 | FCTA | Co-Teach Annuel PNC Training | - | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 0 |
| -345 | FCTR | Co-Teach Requal PNC Training | - | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 1 |
| -352 | PEL1 | Formation pelesys attribuée | 2021-07-01 | - | 60 | 0/0 | 2 | 32 | 1 | 4 | 5 |
| -353 | PEL3 | Formation pelesys attribuée | 2021-07-01 | - | 180 | 0/0 | 2 | 32 | 1 | 4 | 80 |
| -354 | PEL6 | Formation pelesys attribuée | 2021-07-01 | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 3 |
| -355 | MISS | Formation Pelesys Mission + | 2022-10-01 | 2024-01-01 | 60 | 0/0 | 2 | 32 | 1 | 4 | 0 |
| -357 | FDVC | Formateur des DV coach | 2022-10-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 8 |
| -359 | TRLI | Instructeur ground PRLI | 2024-01-01 | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 10 |
| -366 | TPER | Instructeur Cours Performance | 2025-04-01 | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 5 |
| -372 | TGEN | Instructeur de la formation GEN | 2021-02-01 | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 21 |
| -373 | TSOP | Instructeur de la formation SOP | 2021-02-01 | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 11 |
| -391 | LYXT | SmartLynx Training | 2023-03-13 | 2024-01-01 | 270 | 0/0 | 2 | 32 | 1 | 4 | 0 |
| -392 | FIRE | Fire /Ditch In person | 2024-07-01 | - | 180 | 0/0 | 2 | 32 | 1 | 4 | 0 |
| -396 | REUS | RÉUNION PILOTE STANDARDISATEUR | - | - | 360 | 0/0 | 2 | 0 | 1 | 4 | 10 |
| -399 | FSAN | SHADOW Annuel PNC formateur 6 crédits | 2023-09-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 12 |
| -400 | FSRQ | SHADOW Requal PNC 6 credits | 2023-09-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 3 |
| -401 | FSIN | SHADOW Initial PNC formateur 6 credits | 2023-09-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 2 |
| -402 | FSET | SHADOW EET Instructor | 2023-09-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 0 |
| -403 | FSFD | SHADOW Instructor FD Training | 2023-09-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 0 |
| -404 | FSGT | SHADOW Barriere | 2023-09-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 2 |
| -405 | FSFA | SHADOW First Aid PNC formateur 6 credits | 2023-09-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 7 |
| -406 | FSCK | SHADOW Post c Check | 2023-09-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 0 |
| -407 | FS3P | SHADOW instructeur sous contrat | 2023-09-01 | - | 360 | 60/15 | 2 | 32 | 1 | 4 | 0 |
| -410 | IGEN | Cours Générique Initial | - | - | 360 | 0/0 | 2 | 0 | 1 | 4 | 0 |
| -417 | JSOP | JET TRANSITION INITIAL B | - | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 21 |
| -418 | TJET | INSTRUC. JET TRANSITION INTIAL B | - | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 10 |
| -428 | APT | Aircraft Procedures Trainer | - | - | 300 | 0/0 | 2 | 0 | 1 | 4 | 2 |
| -437 | INTR | SUPERVISEUR - RÉUNION D'INSTRUCTEURS | - | - | 360 | 0/0 | 2 | 32 | 1 | 4 | 17 |

#### G4b. Training - simulator and flight-deck training (byte 99 bits 0 and 1 set) - 68 codes

| ID | CC | Description (as stored) | Eff. from | Eff. to | FTC min | Rep/Deb min | b97 | b98 | b99 | b101 | 2026 rows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| -6 | SIMU | SIMULATEUR CAE | 2000-02-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 0 |
| -10 | SIM | SIMULATEUR | 2000-02-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 134 |
| -13 | TSIM | TRAINER SIMULATOR | 2000-02-01 | 2024-01-01 | 300 | 90/30 | 2 | 32 | 3 | 4 | 0 |
| -30 | TSMU | TRAINER SIMULATOR | - | 2024-01-01 | 300 | 90/30 | 2 | 32 | 3 | 4 | 0 |
| -60 | SIML | SIMULATEUR LOFT | 2008-01-01 | 2024-01-01 | 300 | 90/30 | 2 | 32 | 3 | 4 | 0 |
| -65 | SIMP | SIMULATOR-PASSIF - DISCONTINUED | - | 2026-03-01 | 300 | 90/30 | 2 | 32 | 3 | 0 | 13 |
| -114 | PEEV | ÉVALUATEUR PROMOTION-PROMOTION EVALUATOR | - | - | 300 | 0/0 | 2 | 0 | 3 | 0 | 18 |
| -128 | SIMI | SIMULATEUR INITIAL | 2003-12-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 73 |
| -129 | THEI | THÉORIE INITIAL | 2003-12-01 | - | 360 | 0/0 | 2 | 32 | 3 | 4 | 0 |
| -142 | SMP3 | SIMULATEUR PASSIF 330 - PASSIVE SIM 330 | - | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 54 |
| -146 | SMP2 | SIMULATEUR PASSIF 320 - PASSIVE SIM 320 | - | - | 300 | 90/30 | 2 | 32 | 3 | 0 | 32 |
| -165 | APSM | APS - MCC INITIAL B | - | - | 300 | 90/30 | 2 | 0 | 3 | 4 | 0 |
| -166 | TAPS | APS - MCC INSTRUCTEUR | - | - | 300 | 90/30 | 2 | 0 | 3 | 4 | 22 |
| -199 | TSIL | TRAINER SIM AND LANDING | 2016-04-01 | 2024-01-01 | 300 | 90/30 | 2 | 32 | 3 | 4 | 0 |
| -231 | LSIM | SIMULATEUR 3 LANDING | 2014-09-01 | 2024-01-01 | 180 | 90/30 | 2 | 32 | 3 | 4 | 0 |
| -289 | TCMD | Ground Instructor Captains course | 2023-11-01 | - | 360 | 0/0 | 2 | 32 | 3 | 4 | 0 |
| -295 | MPVA | Moniteur TC du PVA | 2019-03-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 0 |
| -301 | MINS | Moniteur de l'Instructeur | 2022-03-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 47 |
| -320 | INT3 | JOURNÉE INTRO | 2017-01-01 | - | 180 | 0/0 | 2 | 32 | 3 | 4 | 0 |
| -368 | LSI2 | SIMULATEUR 3 LANDINGS A321 | 2020-12-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 13 |
| -369 | LSI3 | SIMULATEUR 3 LANDINGS A330 | 2020-12-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 15 |
| -370 | TSL2 | Trainer SIM | 2020-12-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 4 |
| -371 | TSL3 | Trainer SIM | 2020-12-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 0 |
| -374 | LSM2 | Training + LANDING 321 | 2024-10-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 0 |
| -375 | LSM3 | Training  + LANDING 330 | 2024-10-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 1 |
| -376 | SLC3 | Simulateur Line Check A330 | 2021-07-01 | 2024-01-01 | 300 | 90/30 | 2 | 32 | 3 | 4 | 0 |
| -378 | TLC3 | Entraineur simulateur Line Check A330 | 2022-02-07 | 2024-01-01 | 300 | 60/30 | 2 | 32 | 3 | 4 | 0 |
| -382 | TPP3 | Entraineur session simulateur PPC A330 | 2021-10-01 | - | 300 | 60/30 | 2 | 32 | 3 | 4 | 231 |
| -383 | TPP2 | Entraineur session simulateur PPC A321 | 2021-10-01 | - | 300 | 60/30 | 2 | 32 | 3 | 4 | 354 |
| -384 | TSM3 | Entraineur session simulateur A330 | 2021-10-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 248 |
| -385 | TSM2 | Entraineur session simulateur A321 | 2021-10-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 391 |
| -386 | SPP3 | Shadow sur session A330 | 2022-02-07 | - | 300 | 60/30 | 2 | 32 | 3 | 4 | 7 |
| -387 | SPP2 | Shadow sur session A321 | 2022-02-07 | - | 300 | 60/30 | 2 | 32 | 3 | 4 | 0 |
| -409 | ZFTT | Zero Flight Time Training | 2025-01-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 0 |
| -453 | SM3Q | SIM-A330-PH2 EQRH | 2023-06-01 | - | 360 | 90/30 | 2 | 32 | 3 | 4 | 0 |
| -454 | SM2Q | SIM-A321-PH2 EQRH | 2023-06-01 | - | 360 | 90/30 | 2 | 32 | 3 | 4 | 0 |
| -455 | SM11 | SIM A310 - phase 1 | 2019-04-01 | 2024-01-01 | 300 | 90/60 | 2 | 32 | 3 | 4 | 0 |
| -456 | SM12 | SIM A310 - phase 2 | 2019-04-01 | 2024-01-01 | 300 | 90/60 | 2 | 32 | 3 | 4 | 0 |
| -461 | PPC1 | PPC - A310 | 2019-04-01 | 2024-01-01 | 300 | 90/60 | 2 | 32 | 3 | 4 | 0 |
| -462 | SM21 | SIM A321 - phase 1 | 2019-04-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 250 |
| -463 | SM22 | SIM A321 - phase 2 | 2019-04-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 268 |
| -464 | SM23 | SIM A321 - phase 3 | 2019-04-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 43 |
| -465 | SM24 | SIM A321 - phase 4 | 2019-04-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 4 |
| -466 | SM25 | SIM A321 - phase 5 | 2019-04-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 7 |
| -467 | SM26 | SIM A321 - phase 6 | 2019-04-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 12 |
| -468 | PPC2 | PPC - A321 | 2019-04-01 | - | 300 | 60/30 | 2 | 32 | 3 | 4 | 566 |
| -469 | SM31 | SIM A330 - phase 1 | 2019-04-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 128 |
| -470 | SM32 | SIM A330 - phase 2 | 2019-04-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 140 |
| -471 | SM33 | SIM A330 - phase 3 | 2019-04-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 22 |
| -472 | SM34 | SIM A330 - phase 4 | 2019-04-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 0 |
| -473 | SM35 | SIM A330 - phase 5 | 2019-04-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 1 |
| -474 | SM36 | SIM A330 - phase 6 | 2019-04-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 8 |
| -475 | PPC3 | PPC - A330 | 2019-04-01 | - | 300 | 60/30 | 2 | 32 | 3 | 4 | 299 |
| -476 | SM71 | SIM B737 - phase 1 | 2019-04-01 | 2024-01-01 | 300 | 90/60 | 2 | 32 | 3 | 4 | 0 |
| -477 | SM72 | SIM B737 - phase 2 | 2019-04-01 | 2024-01-01 | 300 | 90/60 | 2 | 32 | 3 | 4 | 0 |
| -478 | SM73 | SIM B737 - phase 3 | 2019-04-01 | 2024-01-01 | 300 | 90/60 | 2 | 32 | 3 | 4 | 0 |
| -479 | SM74 | SIM B737 - phase 4 | 2019-04-01 | - | 300 | 90/60 | 2 | 32 | 3 | 4 | 0 |
| -480 | SM75 | SIM B737 - phase 5 | 2019-04-01 | 2024-01-01 | 300 | 90/60 | 2 | 32 | 3 | 4 | 0 |
| -481 | SM76 | SIM B737 - phase 6 | 2019-04-01 | 2024-01-01 | 300 | 90/60 | 2 | 32 | 3 | 4 | 0 |
| -482 | PPC7 | PPC - B737 | 2019-04-01 | 2024-01-01 | 300 | 90/60 | 2 | 32 | 3 | 4 | 0 |
| -483 | AL33 | ALOFT - Amoc-Loft A330 (30jrs) | 2021-02-01 | 2024-01-01 | 300 | 60/30 | 2 | 32 | 3 | 4 | 0 |
| -484 | ALO3 | ALOFT - Amoc-Loft A330 (60 jrs) | 2020-11-01 | 2024-01-01 | 300 | 60/30 | 2 | 32 | 3 | 4 | 0 |
| -485 | ALO2 | ALOFT - Amoc-Loft A321 (60jrs) | 2021-02-01 | 2024-01-01 | 300 | 60/30 | 2 | 32 | 3 | 4 | 0 |
| -486 | AL22 | ALOFT - Amoc-Loft A321 (30jrs) | 2021-02-01 | 2024-01-01 | 300 | 60/30 | 2 | 32 | 3 | 4 | 0 |
| -487 | SM2U | Non-recommandation A321 | 2021-02-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 0 |
| -488 | SM3U | Non-recommandation A330 | 2021-02-01 | - | 300 | 90/30 | 2 | 32 | 3 | 4 | 3 |
| -490 | PC2U | Non-recommandation A321 | 2021-02-01 | - | 300 | 60/30 | 2 | 32 | 3 | 4 | 3 |
| -491 | PC3U | Non-recommandation A330 | 2021-02-01 | - | 300 | 60/30 | 2 | 32 | 3 | 4 | 2 |

#### G5. Leave / absence (byte 97 & 0x30 <> 0) - 62 codes

| ID | CC | Description (as stored) | Eff. from | Eff. to | FTC min | Rep/Deb min | b97 | b98 | b99 | b101 | 2026 rows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| -11 | JUP1 | JOURNÉE URGENCE PERS. RÉMUNÉRÉE | 2005-03-01 | - | 0 | 0/0 | 57 | 32 | 0 | 8 | 0 |
| -16 | RETP | RETRAIT PRÉVENTIF | 2000-02-01 | - | 0 | 0/0 | 17 | 0 | 0 | 0 | 3237 |
| -17 | MAL | MALADIE - SICK | 2000-02-01 | - | 0 | 0/0 | 249 | 32 | 0 | 0 | 14015 |
| -18 | JUP | JOURNÉE URGENCE PERSONNELLE | 2000-02-01 | 2024-07-01 | 0 | 0/0 | 25 | 32 | 0 | 0 | 0 |
| -19 | CSS | CONGÉ SANS SOLDE | 2000-02-01 | - | 0 | 0/0 | 153 | 1 | 0 | 0 | 9886 |
| -21 | PMAL | CSS Paternité - Crédit Banque de Maladie | 2026-01-06 | - | 0 | 0/0 | 241 | 32 | 0 | 0 | 0 |
| -24 | VACA | VACATION - VACANCES/PAS DE CONGÉS COLLÉS | 2000-02-01 | - | 240 | 0/0 | 221 | 32 | 0 | 0 | 3273 |
| -25 | VAC | VACATION - VACANCES | 2000-02-01 | - | 240 | 0/0 | 221 | 32 | 0 | 0 | 29672 |
| -26 | FER | FÉRIÉ - STATUTORY HOLIDAY | 2000-02-01 | - | 240 | 0/0 | 157 | 32 | 0 | 0 | 15024 |
| -27 | MAT | CONGÉ DE MATERNITÉ | 2000-02-01 | - | 0 | 0/0 | 145 | 1 | 0 | 0 | 14568 |
| -28 | PAT | CONGÉ DE PATERNITÉ | 2000-02-01 | - | 0 | 0/0 | 145 | 1 | 0 | 0 | 1579 |
| -42 | MOL | MALADIE HORS-BASE DANS CREW ROUTE =0 | - | - | 0 | 0/0 | 249 | 32 | 0 | 0 | 0 |
| -45 | PAT1 | PATERNITE PAYÉE | 2005-03-01 | - | 0 | 0/0 | 145 | 1 | 0 | 0 | 30 |
| -80 | MAL1 | MALADIE 1 INJUSTIFIÉE | - | - | 0 | 0/0 | 217 | 32 | 0 | 0 | 0 |
| -83 | N/DJ | NON DISPONIBLE J.U.P. 1 | 2005-11-01 | - | 0 | 0/0 | 57 | 32 | 0 | 0 | 0 |
| -84 | N/DM | NON DISPONIBLE MALADIE | 2005-11-01 | - | 0 | 0/0 | 249 | 1 | 0 | 0 | 906 |
| -85 | NSHP | NO SHOW PILOTE | - | - | 0 | 0/0 | 153 | 0 | 0 | 0 | 15 |
| -87 | MFIT | FIT FROM MALADIE | - | - | 0 | 0/0 | 185 | 32 | 0 | 0 | 5981 |
| -88 | NSHW | NO SHOW | - | - | 0 | 0/0 | 153 | 0 | 0 | 0 | 217 |
| -92 | FERI | FÉRIÉ - STATUTORY HOL/PAS CONGÉ COLLÉ | - | - | 240 | 0/0 | 157 | 32 | 0 | 0 | 1137 |
| -93 | FERM | FÉRIÉ - STATUTORY HOL 3/Mini-bloc | - | - | 180 | 0/0 | 157 | 32 | 0 | 0 | 870 |
| -94 | FEMI | FÉRIÉ - STATUTORY HOL 3/Pas congés collé | - | - | 180 | 0/0 | 157 | 32 | 0 | 0 | 45 |
| -95 | VACM | VACATION - VACANCES/Mini-bloc | - | - | 120 | 0/0 | 221 | 32 | 0 | 0 | 2857 |
| -96 | VAMI | VACATION - VACANCES/Pas de congés collés | - | - | 120 | 0/0 | 221 | 32 | 0 | 0 | 162 |
| -117 | INV | INVALIDITÉ | 2004-01-01 | - | 0 | 0/0 | 209 | 32 | 0 | 0 | 51064 |
| -119 | FIT3 | RETOUR DE MALADIE INJUSTIFIÉE | - | - | 0 | 0/0 | 217 | 32 | 0 | 0 | 0 |
| -130 | VNR | VACANCES NON RÉMUNÉRÉE | - | - | 0 | 0/0 | 221 | 0 | 0 | 0 | 1669 |
| -131 | VNRA | VACANCES NON RÉMUNÉRÉE-PAS CONGÉS COLLÉS | - | - | 0 | 0/0 | 221 | 0 | 0 | 0 | 7 |
| -147 | MHB | MALADIE HORS-BASE POUR PAYER CRDTS | 2006-01-31 | - | 0 | 0/0 | 249 | 32 | 0 | 0 | 58 |
| -181 | PAR | CONGE PARENTAL | - | - | 0 | 0/0 | 145 | 1 | 0 | 0 | 0 |
| -182 | MHB1 | MAL HORS BASE HEURE | - | - | 0 | 0/0 | 242 | 32 | 0 | 0 | 0 |
| -190 | IVAC | VACANCES CARANCES | 2005-11-01 | - | 240 | 0/0 | 221 | 32 | 0 | 0 | 0 |
| -210 | 737B | CHANGEMENT D'APPAREIL | 2013-11-01 | 2025-01-01 | 0 | 0/0 | 25 | 0 | 0 | 0 | 0 |
| -220 | RPP | RÉDUCTION PETIT PORTEUR | 2012-06-01 | - | 0 | 0/0 | 153 | 0 | 0 | 0 | 0 |
| -250 | CSRH | Congé sans solde RH | 2015-01-01 | - | 0 | 0/0 | 153 | 1 | 0 | 0 | 738 |
| -251 | MARH | Maladie Ressource Humaines | 2015-05-01 | - | 0 | 0/0 | 153 | 1 | 0 | 0 | 7588 |
| -252 | LATE | LATE - MÊME APPLICATION QUE NO SHOW | 2016-10-01 | - | 0 | 0/0 | 153 | 0 | 0 | 0 | 22 |
| -255 | CSSM | CSSM mitigation | - | - | 0 | 0/0 | 153 | 1 | 0 | 0 | 12882 |
| -259 | NDF | Non dispo formation Pelesys | 2020-02-01 | - | 0 | 0/0 | 153 | 0 | 0 | 0 | 19 |
| -262 | CSSD | Congé sans solde deuil | 2019-10-01 | - | 0 | 0/0 | 153 | 1 | 0 | 0 | 12 |
| -290 | CSSP | CONGE SANS SOLDE PARENTAL | 2016-02-01 | - | 0 | 0/0 | 153 | 1 | 0 | 0 | 3135 |
| -291 | CSF | Congé Spécial Fédéral | - | - | 0 | 0/0 | 153 | 1 | 0 | 0 | 0 |
| -298 | PVHR | bloc heure réduite | 2009-11-12 | 2022-07-01 | 0 | 0/0 | 213 | 1 | 0 | 0 | 0 |
| -300 | MALO | MALADIE OVERTIME | - | - | 0 | 0/0 | 249 | 32 | 0 | 8 | 1296 |
| -309 | OSTP | Outside the Scope of the coll agreement | 2016-07-01 | - | 0 | 0/0 | 153 | 1 | 0 | 0 | 1371 |
| -310 | OSTW | Outside the Scope of the coll agreement | 2016-07-01 | - | 0 | 0/0 | 221 | 33 | 0 | 0 | 0 |
| -311 | OSPR | Outside the Scope of the coll agreement | 2016-07-01 | - | 0 | 0/0 | 153 | 1 | 0 | 0 | 0 |
| -344 | MAL4 | MALADIE - SICK | 2023-06-01 | - | 0 | 0/0 | 249 | 32 | 0 | 0 | 43 |
| -346 | FER2 | FERIE - STATUTORY HOL 2 mini bloc | - | - | 120 | 0/0 | 157 | 32 | 0 | 0 | 0 |
| -347 | FE2A | FERIE - STATUTORY HOL 2/Pas conges colle | - | - | 120 | 0/0 | 157 | 32 | 0 | 0 | 0 |
| -360 | CPP | Journée personnelle payée (payé de la ba | - | 2024-10-23 | 0 | 0/0 | 249 | 32 | 0 | 0 | 1 |
| -361 | DENP | Deuil PAS payé | - | - | 0 | 0/0 | 153 | 1 | 0 | 0 | 186 |
| -363 | CPNP | Journée Personnelle NON payé | - | - | 0 | 0/0 | 25 | 32 | 0 | 0 | 15 |
| -364 | CPP5 | Conge Personnel Paye (PNT) | - | - | 312 | 0/0 | 217 | 32 | 0 | 0 | 572 |
| -365 | CPNT | Conge Personnel Non Paye (PNT) | - | - | 0 | 0/0 | 25 | 32 | 0 | 0 | 43 |
| -380 | SUSV | Suspension Administrative Vaccin | 2021-01-01 | - | 0 | 0/0 | 153 | 1 | 0 | 0 | 0 |
| -381 | SUSU | Suspension non-payée / Unpaid Suspension | 2021-01-01 | - | 0 | 0/0 | 153 | 1 | 0 | 0 | 0 |
| -394 | CPP4 | Conge Personnel Paye (PNC) | - | - | 240 | 0/0 | 217 | 32 | 0 | 8 | 2886 |
| -395 | CPNC | Conge Personnel Non Paye (PNC) | - | - | 0 | 0/0 | 25 | 32 | 0 | 0 | 102 |
| -408 | MILI | CON - Membre de la réserve Armée Can. | 2000-02-01 | - | 0 | 0/0 | 153 | 1 | 0 | 0 | 0 |
| -425 | FI2 | RETOUR MAL REDUIT MINIMUM | - | - | 0 | 0/0 | 185 | 32 | 0 | 0 | 0 |
| -426 | PTP | Programme de temps partagé PNT | - | - | 0 | 0/0 | 153 | 1 | 0 | 0 | 606 |

#### G6a. Other codes carrying the REST flag (byte 97 bit 2) but no leave / reserve / training flag - 21 codes

| ID | CC | Description (as stored) | Eff. from | Eff. to | FTC min | Rep/Deb min | b97 | b98 | b99 | b101 | 2026 rows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| -3 | IOU | DAY OFF OWED TO PN | 2000-02-01 | - | 0 | 0/0 | 205 | 32 | 0 | 0 | 230 |
| -5 | X. |  | 2010-01-01 | 2010-01-31 | 0 | 0/0 | 197 | 32 | 0 | 0 | 0 |
| -15 | AIMS | System reserved do not t | - | - | 0 | 0/0 | 197 | 32 | 0 | 0 | 0 |
| -29 | N/D | NON DISPONIBLE | 2000-02-01 | - | 0 | 0/0 | 205 | 1 | 0 | 0 | 388 |
| -105 | CMF | CONGÉ MENSUEL FLOTTANT | - | - | 0 | 0/0 | 197 | 32 | 0 | 0 | 0 |
| -106 | CMG | CONGÉ MENSUEL GARANTI | - | - | 0 | 0/0 | 197 | 32 | 0 | 0 | 0 |
| -168 | RELV | RELEVÉ | 2005-10-01 | - | 0 | 0/0 | 197 | 32 | 0 | 0 | 7307 |
| -171 | N/DC | NON DISPONIBLE COUPURE CRÉDIT (DMG) | - | - | 0 | 0/0 | 205 | 1 | 0 | 0 | 1908 |
| -172 | CONV | CONGÉ REMIS SUR VOL | - | - | 0 | 0/0 | 205 | 32 | 0 | 0 | 118 |
| -193 | TDO | TRAINING DAY OFF | - | - | 0 | 0/0 | 197 | 32 | 0 | 0 | 74 |
| -209 | BP | NON-DISPONIBLE BLOC PARTAGÉ | 2011-12-01 | - | 0 | 0/0 | 205 | 1 | 0 | 0 | 59 |
| -212 | FCON | CONGÉ POUR FORMATEURS PNC | 2011-11-01 | - | 0 | 0/0 | 197 | 32 | 0 | 0 | 2374 |
| -214 | FCOG | CONGÉ POUR FORMATEURS PNC | - | - | 0 | 0/0 | 197 | 32 | 0 | 0 | 0 |
| -257 | GATE | GATE SUPERVISION | - | - | 0 | 0/0 | 198 | 32 | 0 | 0 | 0 |
| -302 | TVS | N/D TVS | 2017-10-10 | - | 0 | 0/0 | 205 | 1 | 0 | 0 | 0 |
| -305 | INSF | relève instructeur | 2016-10-01 | - | 0 | 0/0 | 197 | 32 | 0 | 0 | 0 |
| -308 | CUPE | relève syndicale | - | - | 0 | 0/0 | 197 | 32 | 0 | 0 | 0 |
| -390 | LYX | N/D Smartlynx | 2023-04-01 | - | 0 | 0/0 | 205 | 1 | 0 | 0 | 0 |
| -414 | CON1 | ONLINE TRAINING - 1 CRÉDIT | - | - | 60 | 0/0 | 197 | 32 | 0 | 0 | 48 |
| -415 | CON3 | ONLINE TRAINING - 3 CRÉDITS | - | - | 180 | 0/0 | 197 | 32 | 0 | 0 | 209 |
| -416 | CON6 | ONLINE TRAINING - 6 CRÉDITS | - | - | 360 | 0/0 | 197 | 32 | 0 | 0 | 903 |

#### G6b. Other ground activities / administrative duties (some flag set, none of the above) - 98 codes

| ID | CC | Description (as stored) | Eff. from | Eff. to | FTC min | Rep/Deb min | b97 | b98 | b99 | b101 | 2026 rows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| -8 | BUR | BUREAU - OFFICE | 2000-02-01 | - | 240 | 0/0 | 2 | 32 | 0 | 4 | 131 |
| -12 | REU | RÉUNION - MEETING | 2000-02-01 | - | 240 | 0/0 | 2 | 32 | 0 | 4 | 448 |
| -14 | NQ3 | NOT QUALIFIED | 2000-12-12 | - | 0 | 0/0 | 9 | 1 | 0 | 0 | 0 |
| -20 | MAP | MISE À PIED - LAID OFF | 2000-02-01 | - | 0 | 0/0 | 137 | 1 | 0 | 0 | 17236 |
| -23 | DEUI | DEUIL - FUNERAL | 2000-02-01 | - | 0 | 0/0 | 137 | 32 | 0 | 0 | 615 |
| -31 | INAC | INACTIF | 2000-02-01 | - | 0 | 0/0 | 137 | 0 | 0 | 0 | 0 |
| -32 | DEM | DÉMISSION | 2000-02-01 | - | 0 | 0/0 | 137 | 0 | 0 | 0 | 3049 |
| -33 | REAF | RÉAFFECTATION | 2000-02-01 | - | 0 | 0/0 | 137 | 32 | 0 | 0 | 1338 |
| -34 | BLNK | BLANK  DAY | - | - | 0 | 0/0 | 137 | 32 | 0 | 0 | 0 |
| -40 | DON | DONATION | 2005-12-01 | - | 0 | 0/0 | 137 | 0 | 0 | 8 | 10 |
| -41 | SEV1 | PROJET SPÉCIAUX PAYÉ À TEMPS SIMPLE | 2005-03-01 | - | 0 | 0/0 | 2 | 32 | 0 | 4 | 64 |
| -43 | NQ1 | NOT QUALIFIED PAS PAYÉ | 2005-03-01 | - | 0 | 0/0 | 9 | 1 | 0 | 0 | 316 |
| -48 | JURY | JURY DUTY | 2000-02-01 | - | 0 | 0/0 | 2 | 32 | 0 | 4 | 25 |
| -50 | TRAN | TRANSFERT | 2000-02-01 | - | 240 | 0/0 | 137 | 1 | 0 | 0 | 0 |
| -55 | SEV | SERVICE EN VOL | 2000-02-01 | - | 0 | 0/0 | 2 | 32 | 0 | 4 | 1744 |
| -56 | SV | SUSPENSION | 2000-02-01 | - | 0 | 0/0 | 1 | 0 | 0 | 0 | 326 |
| -57 | SYN | UNION MEETING - SYNDICAT | 2000-02-01 | - | 240 | 0/0 | 2 | 32 | 0 | 4 | 213 |
| -62 | CSST | CSST QUEBEC | - | - | 0 | 0/0 | 137 | 1 | 0 | 0 | 2303 |
| -63 | WCB | WCB (REST OF CANADA) | - | - | 0 | 0/0 | 137 | 0 | 0 | 0 | 525 |
| -68 | SYNR | SYNDICAT NON PLANIFIÉ | - | - | 0 | 0/0 | 2 | 32 | 0 | 4 | 0 |
| -81 | FIT1 | MALADIE À 0 CRÉDIT | - | - | 0 | 0/0 | 138 | 0 | 0 | 0 | 912 |
| -82 | FIT2 | RETOUR MAL RÉDUIT MINIMUM | - | - | 0 | 0/0 | 138 | 0 | 0 | 0 | 34 |
| -86 | CHKF | CHECK FIT | - | - | 0 | 0/0 | 137 | 0 | 0 | 0 | 2 |
| -89 | REFU | REFUS DE VOL | - | - | 0 | 0/0 | 9 | 0 | 0 | 0 | 35 |
| -90 | SHOW | SHOWED UP FOR FLT 4 HRS MIN | - | - | 240 | 0/0 | 2 | 32 | 0 | 4 | 104 |
| -91 | DISP | DISPONIBLE POUR VOL | - | 2022-10-01 | 0 | 0/0 | 1 | 0 | 0 | 0 | 11 |
| -97 | RSVT | RESERVE PNT | 2005-03-01 | - | 0 | 0/0 | 130 | 36 | 0 | 0 | 0 |
| -98 | REAM | RÉAFFECTATION MATERNITÉ | 2003-06-01 | - | 0 | 0/0 | 137 | 0 | 0 | 0 | 0 |
| -104 | ADMP | BUREAU CHEF PILOTE PAYÉ | 2026-01-06 | - | 270 | 0/0 | 2 | 32 | 0 | 4 | 574 |
| -107 | CGPN | COMITÉ GESTION PN | - | - | 240 | 0/0 | 2 | 32 | 0 | 4 | 2 |
| -108 | REAS | RÉAFFECTATION SÉNIOR | - | - | 0 | 0/0 | 137 | 0 | 0 | 0 | 8 |
| -110 | REAP | RÉAFFECTATION PRIORITAIRE | 2006-08-22 | - | 0 | 0/0 | 137 | 0 | 0 | 0 | 3 |
| -118 | NQ | NOT QUALIFIED | - | - | 0 | 0/0 | 9 | 0 | 0 | 0 | 1106 |
| -123 | ADM | BUREAU CHEF PILOTE | 2005-11-01 | - | 240 | 0/0 | 2 | 32 | 0 | 4 | 860 |
| -124 | BTS | BUREAU TIMESHEET | 2005-11-01 | - | 0 | 0/0 | 1 | 32 | 0 | 4 | 3503 |
| -127 | SST | SANTÉ SÉCURITÉ AU TRAVAIL | 2003-07-01 | - | 240 | 0/0 | 2 | 32 | 0 | 4 | 117 |
| -135 | DON1 | DON DE VOL / DONATED FLIGHT SWITCH | 2004-08-20 | - | 0 | 0/0 | 137 | 0 | 0 | 0 | 14208 |
| -136 | DON2 | DON DE VOL / DONATED FLIGHT SWITCH | 2004-08-20 | - | 0 | 0/0 | 137 | 0 | 0 | 0 | 5 |
| -137 | DON3 | DON DE VOL / DONATED FLIGHT SWITCH | 2004-08-20 | - | 0 | 0/0 | 137 | 0 | 0 | 0 | 0 |
| -139 | SSTT | SANTÉ SÉCURITÉ AU TRAVAIL | 2005-01-21 | - | 600 | 0/0 | 2 | 32 | 0 | 4 | 0 |
| -145 | SHW1 | SHOW FOR FLIGHT | 2005-10-01 | - | 0 | 0/0 | 1 | 32 | 0 | 0 | 58 |
| -148 | RET | RETRAITE | 2005-06-30 | - | 0 | 0/0 | 137 | 1 | 0 | 0 | 884 |
| -149 | TEMP | Sr code index 149>>>159 | - | - | 0 | 0/0 | 65 | 1 | 0 | 0 | 0 |
| -175 | BCK | Transfert/back to base | - | - | 0 | 0/0 | 137 | 1 | 0 | 0 | 71 |
| -176 | SEV2 | PROJET SPÉCIAUX | 2019-07-01 | - | 0 | 0/0 | 2 | 32 | 0 | 4 | 123 |
| -179 | DEUP | DEUIL PILOTE – AVANT PUBLICATION | 2026-01-06 | - | 270 | 0/0 | 137 | 32 | 0 | 0 | 12 |
| -183 | AJU | AJUSTEMENT CREDITS INCLUS CODE 40 | 2007-01-01 | - | 0 | 0/0 | 137 | 32 | 0 | 0 | 104 |
| -184 | PBS | VERIFICATION DE CEDULES | 2007-06-01 | - | 240 | 0/0 | 2 | 32 | 0 | 0 | 36 |
| -185 | SHWP | SHOW - PILOT | 2026-01-05 | - | 270 | 0/0 | 2 | 32 | 2 | 0 | 33 |
| -186 | GREF | AJUSTEMENT DE GRIEFF | - | - | 0 | 0/0 | 137 | 32 | 0 | 0 | 0 |
| -187 | HAJJ | hajj | 2010-09-01 | - | 0 | 0/0 | 137 | 32 | 0 | 0 | 0 |
| -188 | BUR6 | BUREAU 6 HEURES | - | - | 360 | 0/0 | 2 | 32 | 0 | 4 | 26 |
| -189 | MAP1 | MISE À PIED QUI NE COUPE PAS | 2010-12-01 | - | 0 | 0/0 | 137 | 1 | 0 | 0 | 0 |
| -191 | ALCD | COMITÉ SYNDICAT - UNION COMMITTEE - MOVE | 2026-03-01 | - | 270 | 0/0 | 2 | 32 | 0 | 0 | 64 |
| -192 | ALPD | RELÈVE SYNDICALE - UNION RELEASE - MOVE | 2026-03-01 | - | 270 | 0/0 | 2 | 32 | 0 | 0 | 95 |
| -195 | RAFP | RÉAFFECTATION NO-SHOW | 2012-04-01 | - | 0 | 0/0 | 137 | 0 | 0 | 0 | 0 |
| -196 | CGP1 | COMITÉ GESTION PN CUMULABLE | - | - | 240 | 0/0 | 2 | 32 | 0 | 4 | 40 |
| -198 | DMG | DIMINUTION MINIMUM GARANTI (SW) | 2026-01-06 | - | 0 | 0/0 | 137 | 0 | 0 | 0 | 8 |
| -200 | PROG | RETOUR PROGRESSIF | 2009-09-30 | - | 0 | 0/0 | 1 | 0 | 0 | 0 | 0 |
| -206 | ADMZ | BUREAU CHEF PILOTE PAYÉ - DISCONTINUED | - | 2026-01-05 | 240 | 0/0 | 2 | 32 | 0 | 4 | 3 |
| -211 | SSTS | SANTÉ SÉCURITÉ AU TRAVAIL | 2016-09-01 | - | 360 | 0/0 | 2 | 32 | 0 | 4 | 96 |
| -233 | SUBC | sous contrat | 2015-09-01 | - | 0 | 0/0 | 137 | 32 | 0 | 0 | 0 |
| -244 | PER | Performance | 2012-10-01 | - | 240 | 0/0 | 2 | 32 | 0 | 4 | 0 |
| -245 | REL | union duty paid by company. | 2017-03-02 | - | 240 | 0/0 | 2 | 32 | 0 | 4 | 221 |
| -256 | DONP | DON PILOTE | 2016-06-01 | - | 0 | 0/0 | 137 | 0 | 0 | 0 | 101 |
| -258 | MAPS | mise à pied spéciale | 2017-01-31 | - | 0 | 0/0 | 137 | 1 | 0 | 0 | 0 |
| -277 | NQR | Non qualifie | - | - | 130 | 0/0 | 1 | 1 | 0 | 0 | 0 |
| -282 | TCX | Condor Thomas Cook | - | 2024-01-01 | 0 | 0/0 | 1 | 0 | 0 | 0 | 0 |
| -283 | ML1 | Memo lu avec coupure de crédits | - | - | 0 | 0/0 | 9 | 32 | 0 | 0 | 0 |
| -284 | MNLA | Memo non lu | 2018-02-01 | 2018-06-26 | 0 | 0/0 | 138 | 0 | 0 | 0 | 0 |
| -285 | MNL1 | Memo non lu avec coupure de crédits | 2018-02-01 | - | 0 | 0/0 | 9 | 32 | 0 | 0 | 0 |
| -286 | ML | Memo lu | - | - | 0 | 0/0 | 138 | 0 | 0 | 0 | 0 |
| -287 | REUP | RÉUNION PILOTE - PILOT MEETING | - | - | 270 | 0/0 | 2 | 32 | 0 | 4 | 5 |
| -288 | MNL | Memo non lu | 2018-06-27 | - | 0 | 0/0 | 137 | 0 | 0 | 0 | 0 |
| -304 | SCAE | Instructeur chez CAE | - | - | 0 | 0/0 | 2 | 0 | 0 | 0 | 0 |
| -335 | N/DG | Non disponible garanti | 2021-12-01 | - | 0 | 0/0 | 137 | 32 | 0 | 0 | 37 |
| -338 | LINC | PNC Licenciés | 2021-10-01 | - | 0 | 0/0 | 137 | 1 | 0 | 0 | 0 |
| -340 | DSP1 | DISPONIBLE POUR VOLER | - | - | 0 | 0/0 | 193 | 32 | 0 | 0 | 53 |
| -341 | DSP2 | DISPONIBLE POUR VOLER | - | - | 0 | 0/0 | 193 | 32 | 0 | 0 | 2 |
| -342 | DSP3 | DISPONIBLE POUR VOLER | - | - | 0 | 0/0 | 193 | 32 | 0 | 0 | 1 |
| -343 | DSP4 | DISPONIBLE POUR VOLER | - | - | 0 | 0/0 | 193 | 32 | 0 | 0 | 0 |
| -350 | CCQ | FORMATION CCQ | - | - | 240 | 0/0 | 1 | 32 | 0 | 0 | 0 |
| -351 | DQ | FORMATION DQ | - | - | 240 | 0/0 | 1 | 0 | 0 | 0 | 0 |
| -362 | DEU4 | Deuil payé 4hres | - | - | 240 | 0/0 | 2 | 32 | 0 | 4 | 0 |
| -367 | ROPS | Réunion des opérations | 2021-02-01 | 2024-01-01 | 360 | 0/0 | 2 | 32 | 0 | 4 | 0 |
| -393 | DEUA | DEUIL - AVANT PUBLICATION | - | - | 240 | 0/0 | 137 | 32 | 0 | 0 | 3 |
| -398 | RFU1 | Refus de vol dans crew route | 2014-12-01 | - | 0 | 0/0 | 10 | 0 | 0 | 0 | 0 |
| -424 | FI1 | MALADIE A 0 CREDIT | - | - | 0 | 0/0 | 137 | 0 | 0 | 0 | 4 |
| -435 | NQP | Non qualifié payé | - | - | 130 | 0/0 | 1 | 0 | 0 | 0 | 500 |
| -436 | NQF | Non Qualifié Formation | - | - | 0 | 0/0 | 9 | 0 | 0 | 0 | 224 |
| -440 | ALPA | RELÈVE SYNDICALE - UNION RELEASE | 2026-01-06 | - | 270 | 0/0 | 2 | 32 | 0 | 0 | 663 |
| -441 | ALPC | COMITÉ SYNDICAT - UNION COMMITTEE | 2026-01-06 | - | 270 | 0/0 | 2 | 32 | 0 | 0 | 529 |
| -492 | PINT | Pilot Interview | - | - | 240 | 0/0 | 2 | 32 | 0 | 4 | 58 |
| -493 | PROZ | SPECIAL PROJECTS - DISCONTINUED | - | - | 240 | 0/0 | 2 | 32 | 0 | 4 | 2 |
| -494 | PROX | TRAINING PROJECTS - DISCONTINUED | - | - | 240 | 0/0 | 2 | 32 | 0 | 4 | 0 |
| -495 | SYNC | syndicat commite | - | - | 240 | 0/0 | 2 | 32 | 0 | 4 | 4 |
| -496 | PROS | SPECIAL PROJECTS | - | - | 270 | 0/0 | 2 | 32 | 0 | 4 | 199 |
| -497 | PROT | TRAINING PROJECTS | - | - | 270 | 0/0 | 2 | 32 | 0 | 4 | 60 |

## 4. Keys & relationships

* **Business key**: `ID` (unique index `CRCODES_INDEX_0`). `CC` (unique among non-blank values) is the human key. `CRCODES_ID` is only the surrogate PK.
* **ROSTER -> CRCODES** (N:1): `CRCODES.ID = ROSTER.LEG_FLT` for every row with `LEG_FLT < 0` (complete form, R5 456 and R5 522: `LEFT JOIN TSC.dbo.CRCODES c ON c.ID = r.LEG_FLT`); `CRCODES.ID = ROSTER.DUTYNO` for stand-alone activity rows (R0 `LEFT JOIN CRCODES c ON c.ID = r.DUTYNO` lines 592/675, R3 `c.ID = r.DUTYNO` 289/299, R4 391). For stand-alone activities `DUTYNO = LEG_FLT` always (577,065 / 577,065 in 2026), so both are equivalent there; for ground legs inside a pairing (`DUTYNO > 0`) only the `LEG_FLT` form works. All 255 distinct negative `LEG_FLT` values used in 2026 exist in CRCODES (0 orphans).
* No other table in the extract references CRCODES. Pairing/route tables (`CRROUTE`, `CREWLEG`, `CRLEGGROUND`) store the same negative ids in `CREWLEG.FLT`/`CRLEGGROUND.FLT` for ground legs of pairings (inferred from the fallback reads in R3/R4/R5: `cl.FLT < 0`), which is why ground legs inside pairings carry a `CRCODES` id.
* `vvCREWDB` carries per-crew block dates `TSC_BLOCKDATES_1_BEGD1/ENDD1, _BEGD2/ENDD2, _3_...` that R0 uses for the "PVHR" flag (`pvhr_list`); this is **not** a join to CRCODES. The code `PVHR` (ID -298, "bloc heure réduite" = reduced-hours block) also exists in CRCODES (effective 2009-11-12 .. 2022-07-01, byte 97 = 213 = rest + leave).

## 5. Encoding conventions & gotchas

1. **Negative ids, 0 = blank**: `ID <= 0`; the roster stores the same negative number. Do not look codes up by absolute value.
2. **`CC` is padded** (`nchar(8)`): use `RTRIM(CC)` for output; equality with literals is fine. 22 rows have a blank `CC` (system reserved, e.g. -4, -7, -39, -61, -70, -101..-103, -111..-113, -150..-159, 0): they are not usable codes (descriptions such as "System reserved code" / blank), so `WHERE LEN(CC) > 0` as R0 does.
3. **Meaning is in `DATA_BEGIN_END`, not in columns.** Classify with the bytes in 3.2. Use `TSC.dbo.bit_is_set(CONVERT(tinyint, SUBSTRING(DATA_BEGIN_END, n, 1)), bit)` where `bit` is 0-based from the least significant bit. Smallints are little-endian (`SUBSTRING(x,n+1,1) + SUBSTRING(x,n,1)` as the procedures do, or `CONVERT(int,SUBSTRING(x,n,1)) + 256*CONVERT(int,SUBSTRING(x,n+1,1))`).
4. **Two different "reserve" definitions in the repository**: R0 = byte 98 bit 1 (26 named codes: includes `RSV`, `CXX`, `RAMM`, `RS`, `ERR4`...), R3/R4 = byte 101 bit 7 (14 codes: only `AM`, `PM`, `LCR`, `RAM`, `RPM`, `REA1`, ...). `RSVT` ("RESERVE PNT") is flagged by neither. A text-to-SQL agent asked for "reserve" should name which definition it uses.
5. **Rest vs leave vs duty**: rest (byte 97 bit 2) covers days off, vacation and statutory holidays (+ `WFLY` by name in R3) but **not** sickness, parental or unpaid leave; leave (byte 97 & 0x30) covers vacation/holiday, sickness, parental, unpaid, personal days. Vacation/holiday codes carry **both** flags.
6. **R0 categorisation order matters**: `schedule_code` NULL and `Flight_Number` not NULL => `FLIGHT` (this also labels in-pairing ground legs, because R0 joins CRCODES on `DUTYNO`); no roster row that day => `BLANCHE`; special code or `RESERVE` => as is; then Is_Reserve > Is_Training > Is_Leave > Is_Activity > `X`.
7. **Effectivity dates are not enforced by procedures** (no procedure filters on bytes 85-88). Discontinued codes (e.g. `XAM`, `XPM`, `XPM1`, `PVHR`, `ADMZ`, `SIMP`, `TSIM`) can still appear on historical roster rows.
8. **Offsets only apply to ground rows**: report/debrief offsets of bytes 252-255 are read only when `ROSTER.LEG_FLT < 0`; flights use fixed offsets (-60 / -80 / -30 report, +15 debrief) plus the `REPORTTIME/DEBRIEFTIME` overrides.
9. **Placeholders**: untimed statuses (CON, VAC, MAL...) have `GRDDUTYBEG = GRDDUTYEND = 0` on the roster, so their "duty" is zero-length and ignored by overlap logic (they are calendar statuses, not periods).
10. Character set: descriptions contain accented French characters (UTF-16). Some tools/ODBC paths return them as `?`/replacement characters; the underlying data is correct.

## 6. How the planner-assist procedures use it

* **dbo.R0_GetDraftList**: builds `#SchedCodeCat` once from `CRCODES` (`CC NOT IN @SpecialSchedCodes AND LEN(CC) > 0`; bytes 97-102 -> `Is_Training` (b3 & 1), `Is_Leave` (b1 & 48), `Is_Reserve` (b2 & 2), `Is_Activity` (b1 & 207, b2 & 253, b3 & 254, b4, b5, b6)); `schedule_code = c.CC` per roster row; special lists: `@SpecialSchedCodes` = CON, CONG, WFLY, VACP, FERP, CONR, REAT; `@AltCodes` = BLANCHE, CON, CONG, RESERVE, CONR, REAT; `@PntAltCodes` = BLANCHE, CON, CONG, CONR, REAT (off-day statuses, steps 5-8; RESERVE is **not** an off day for PNT); `@VacationCodes` = VACP, FERP; `@PntMovableCodes` = GEN, DG, EPT, SY20, SY30, ALPD, ALCD (not activities for a regular pilot); `@PecaCode` = PECA (captain candidate evaluation day: candidate not called); `@CppExclusionCode` = CPP5 (crew with CPP5 in the pairing window are excluded: "Excluded: CPP5 activity overlap."); `@WflyCode` = WFLY ("wait to fly": top of the draft order, steps 1-4 and 11); `@ExcludedCertCodes` are certificate codes, unrelated. Draft ordering rule: PNT draft procedure clause 14.15 / article 14.5.3.
* **dbo.R3_Get_Violations_RestTime / _Batch** (rest rules, FD-PCA-3830, 700.40.1, 13.4.4): `Schedule_Code = c.CC`; `REST_DAY = CC_IS_Rest OR CC = 'WFLY'`; `CC_IS_Reserve` (byte 101 bit 7) -> reserve duty counts 33 % in `Duty_Duration`; `ACTIVITY_FTC` (bytes 89-90) for ground legs; report offset `-1 * bytes 252-253` and debrief offset `bytes 254-255` for `LEG_FLT < 0`.
* **dbo.R4_Get_Violation_FDP**: same offsets/flags for ground activities (`LEG_START_WITH_REPORT_STD`, `LEG_END_WITH_DEBRIEF_*`), `CC_IS_Reserve` (33 % in duty totals M7/M28/M365, overlap minutes, early/late/night classification FIX 2e), label of a previous/next activity in the overlap messages (`RTRIM(CC)` of the activity that overlaps the draft: `OVERLAP_PREVIOUS_ACTIVITY`, `OVERLAP_NEXT_ACTIVITY`).
* **dbo.R4_Get_Future_Impact** (via R4): same.
* **dbo.R5_Get_Violation_FTC** and **rpt.CalculateCrewFTC**: `ACTIVITY_FTC` per ground row (flight-time credit of the activity), activity period `GRDDUTYBEG - report offset .. GRDDUTYEND + debrief offset`, label (`CC`) of bumped untimed activities ("activity on a day the draft covers").
* Not used anywhere: effectivity dates (85-88), description text (1-80) except for documentation, bytes 103-251 and 256-386.

## 7. Typical query patterns

```sql
-- 1. Decode a code (flags, FTC, offsets, description) by its schedule code
SELECT c.ID, RTRIM(c.CC) AS code,
       CAST(SUBSTRING(c.DATA_BEGIN_END, 1, 80) AS NVARCHAR(40)) AS description,
       CONVERT(int, SUBSTRING(c.DATA_BEGIN_END, 89, 1)) + 256 * CONVERT(int, SUBSTRING(c.DATA_BEGIN_END, 90, 1))   AS ftc_minutes,
       CONVERT(int, SUBSTRING(c.DATA_BEGIN_END, 252, 1)) + 256 * CONVERT(int, SUBSTRING(c.DATA_BEGIN_END, 253, 1)) AS report_offset_min,
       CONVERT(int, SUBSTRING(c.DATA_BEGIN_END, 254, 1)) + 256 * CONVERT(int, SUBSTRING(c.DATA_BEGIN_END, 255, 1)) AS debrief_offset_min,
       TSC.dbo.bit_is_set(CONVERT(tinyint, SUBSTRING(c.DATA_BEGIN_END, 97, 1)), 2) AS is_rest,
       CASE WHEN (CONVERT(tinyint, SUBSTRING(c.DATA_BEGIN_END, 97, 1)) & 48) > 0 THEN 1 ELSE 0 END AS is_leave,
       CASE WHEN (CONVERT(tinyint, SUBSTRING(c.DATA_BEGIN_END, 99, 1)) & 1) = 1 THEN 1 ELSE 0 END AS is_training,
       TSC.dbo.bit_is_set(CONVERT(tinyint, SUBSTRING(c.DATA_BEGIN_END, 101, 1)), 7) AS is_reserve_r3r4,
       CASE WHEN (CONVERT(tinyint, SUBSTRING(c.DATA_BEGIN_END, 98, 1)) & 2) > 0 THEN 1 ELSE 0 END AS is_reserve_r0
FROM TSC.dbo.CRCODES c
WHERE LEN(c.CC) > 0 AND c.CC = 'LCR';

-- 2. All codes of a class, e.g. every training code (R0 definition)
SELECT c.ID, RTRIM(c.CC) AS code, CAST(SUBSTRING(c.DATA_BEGIN_END, 1, 80) AS NVARCHAR(40)) AS description
FROM TSC.dbo.CRCODES c
WHERE LEN(c.CC) > 0 AND (CONVERT(tinyint, SUBSTRING(c.DATA_BEGIN_END, 99, 1)) & 1) = 1
ORDER BY c.CC;

-- 3. Roster rows of one crew member with the code decoded to a business class (stand-alone activities only)
SELECT r.LEG_DAY, DATEADD(DAY, r.LEG_DAY, '1980-01-01') AS d, RTRIM(c.CC) AS code,
       CASE WHEN RTRIM(c.CC) IN ('CON','CONG','WFLY','VACP','FERP','CONR','REAT') THEN RTRIM(c.CC)
            WHEN (CONVERT(tinyint, SUBSTRING(c.DATA_BEGIN_END, 98, 1)) & 2) > 0 THEN 'RESERVE'
            WHEN (CONVERT(tinyint, SUBSTRING(c.DATA_BEGIN_END, 99, 1)) & 1) = 1 THEN 'TRAINING'
            WHEN (CONVERT(tinyint, SUBSTRING(c.DATA_BEGIN_END, 97, 1)) & 48) > 0 THEN 'LEAVE'
            ELSE 'ACTIVITY' END AS business_class
FROM TSC.dbo.ROSTER r
JOIN TSC.dbo.CRCODES c ON c.ID = r.LEG_FLT
WHERE r.ID = @crew_id AND r.LEG_FLT < 0
  AND r.LEG_DAY BETWEEN DATEDIFF(DAY,'1980-01-01',@from) AND DATEDIFF(DAY,'1980-01-01',@to);
```

## 8. Data profile (measured 2026-11-03)

* 449 rows; `ID` -497..0, 448 negative + `0`; 449 distinct `ID`; 427 non-blank `CC`, all distinct; 22 blank `CC`.
* Effectivity: 284 codes have a start date, 68 an end date (67 in the past, 1 in the future/open).
* Flight-time credit (bytes 89-90) values (codes): 0 -> 177; 60 -> 5; 120 -> 4; 130 -> 2; 180 -> 22; 200 -> 5; 240 -> 68; 270 -> 16; 275 -> 1; 285 -> 1; 300 -> 65; 312 -> 1; 360 -> 81; 600 -> 1.
* Report offsets (bytes 252-253) 0 -> 321, 30 -> 5, 60 -> 72, 90 -> 51 codes; debrief offsets 0 -> 345, 15 -> 39, 30 -> 55, 60 -> 10 codes.
* Class counts: blank 22; special 7; strict reserve 14; reserve-flag-only 12; training classroom/other 145; training simulator 68; leave 62; rest-flag-only 21; other activity 98 (sum 449). Flag-byte combos in 3.2.
* 2026 usage in ROSTER (stand-alone activity rows `DUTYNO = ID`): 251 distinct codes used (of 427). Rows by class: special 274,088 (`CON` 154,871; `CONG` 68,805; `WFLY` 27,209; `VACP` 12,169; `FERP` 7,023; `CONR` 2,156; `REAT` 1,855), leave 187,789 (`INV` 51,064; `VAC` 29,672; `FER` 15,024; `MAT` 14,568; `MAL` 14,015; `CSSM` 12,882), strict reserve 31,779 (`RAM` 14,130; `RPM` 11,410; `LCR` 2,369; `REA1` 1,386; `AM` 1,229; `PM` 913), reserve-flag-only 102, training 15,543 (classroom 12,130 across 80 codes, simulator 3,413 across 33 codes), other activity (G6b) 54,146 (e.g. `MAP` 17,236; `DON1` 14,208; `BTS` 3,503) and rest-flag-only (G6a) 13,618 (e.g. `RELV` 7,307); together 67,764 = the R0 `ACTIVITY` class.
  Note: the per-code table in 3.3 lists 2026 rows for all 449 codes (0 = not used in 2026).
* Ground legs inside pairings (`LEG_FLT < 0`, `DUTYNO > 0`) in 2026: 3,452 rows over 115 distinct codes (top: `PPC2` 266, `APT` 254, `SIMI` 250, `MAL` 246, `PPC3` 232, `SHOW` 167).

## 9. Open questions / confidence

* **Confirmed by code**: `ID`/`CC` semantics and joins; flag byte positions used by procedures (97 bit 2 rest, 97 & 0x30 leave, 98 bit 1 reserve-R0, 99 bit 0 training, 101 bit 7 reserve-R3/R4); FTC at 89-90; report/debrief offsets at 252-255; little-endian smallints; `bit_is_set` is 0-based.
* **Decoded from data (high confidence)**: description text at bytes 1-80 (UTF-16LE).
* **Inference (medium)**: bytes 85-88 = effective-from/to day numbers (supported by "DISCONTINUED" codes ending 2026-01-06 and `PVHR` ending 2022-07-01, not used by any procedure); byte 99 bit 1 = simulator/flight-deck training; byte 101 bit 2 = timed duty activity; byte 98 bit 0 = long absence / unpaid.
* **Unknown**: byte 98 bit 5 (0x20, set on 308 codes), byte 97 bits 0, 1, 3, 6, 7 individually, byte 100, bytes 103-251 and 256-386 (non-constant; possibly rates, pay factors or per-position rules).
* The leave/rest/reserve assignment of an individual code is therefore **as the repository code classifies it**, not necessarily what the collective agreement says (e.g. `CXX` "CANCELED FLIGHT" is a reserve for R0; `RSVT` "RESERVE PNT" is no reserve for either; `VACP`/`FERP` are only recognised by name).
* Business meaning of French abbreviations in descriptions is quoted as stored; translations given in section 3.3 are glosses, not data.
* `PVHR` handling: R0 uses crew block dates from `vvCREWDB`, not the CRCODES row; whether roster rows with code `PVHR` (-298) still exist is not checked in 2026 (code ended 2022-07-01).
