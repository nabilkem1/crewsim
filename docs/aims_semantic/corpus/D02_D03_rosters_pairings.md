# CrewSim corpus from AIMS - D2 `d2_rosters`, D3 `d3_pairings`, D3 `d3_pairing_legs` (+ optional `deadhead`)

Verified read-only against the live TSC database (`10.180.1.10`) on 2026-11-03, and against Pierre's v3 CSVs
(`crewsim\src\crewsim\data\corpus\real_datav2\v3\d2_rosters.csv`, `d3_pairings.csv`, `d3_pairing_legs.csv`).
No personal data is reproduced: crew ids are never printed, only aggregates, codes and operational (flight/pairing) data.
Label convention: **verified** = executed on data; **inference** = reasoned from names/patterns, to be confirmed.

Date arithmetic used throughout: AIMS day number = days since 1980-01-01 (2026-01-01 = 16802, 2026-08-31 = 17044, 2024-04-24 = 16185,
2023-08-01 = 15918, 2026-11-03 = 17108). January 2026 test window = `LEG_DAY / DUTYDAY / CDATE` 16802..16832.

---------------------------------------------------------------------------------------------------

## 0. Verdicts at a glance

| Dataset | Verdict | One-line reason |
|---|---|---|
| D2 `d2_rosters` | **MOSTLY** | Every column is derivable from `ROSTER`+`CRCODES`+`CRROUTE`+`CREWLEG`/`LEGMAIN`+`CREWQUAL`; block-type taxonomy, report/release convention and `fleet_detail` need business rules. Unlike Pierre's file, AIMS can also give the roster **as published before an absence** (`PROSTER`, verified) and **as of any day since 2024-05-14** (`LOG_ROSTER`, verified). |
| D3 `d3_pairings` | **MOSTLY (FULL for 8 of 9 columns)** | One tested SQL reproduces Pierre's header for January 2026: pairing set 1,738 vs 1,737, `position_complement` 100 %, `duty_periods` 100 %, `days` 100 %, `base` 99.94 %. Only `credit_hours` is not a pay credit: Pierre's value is the sum of scheduled block hours (reproduced to 0.02 h on 96.3 %); a true pay credit is not in the tables inspected. |
| D3 `d3_pairing_legs` | **MOSTLY** | All keys and times derivable (`dep_local` identical to Pierre on 96.5 % of aligned legs; 0 stations without a time-zone offset in January; 0 legs without STD/STA, where Pierre has 3.2 % legs without times). `report_local`/`release_local` are a convention (Pierre: dep-60 / arr+30), not stored per leg in AIMS. |
| `deadhead` (optional) | **DIRECT** | `CREWLEG.PAX` (agreement with Pierre 98.8 % on aligned legs). |

Three findings that matter more than the column tables:

1. **Published/historical state exists and works.** `PROSTER` (published roster, 2022-12-21..2026-12-01) holds the pairing that was removed when a pilot went sick: of 10,234 sickness crew-days (2024-04-25..2026-08-31, pilots POS 1/2) the current `ROSTER` still shows a flight on **58 (0.6 %)** while `PROSTER` shows the published flight on **4,198 (41.0 %)** - exactly Pierre's "12 of 4,671" problem, and it is solved inside AIMS (section 2).
2. **D2 `PAIRING` blocks in Pierre's file carry local clock time labelled as UTC** (verified against AIMS true UTC, section 3.4). This is the likely root of the "overlapping blocks" (point 11): the overlap is created by the loader when it re-places pairings with D3 duty periods, not by AIMS.
3. **D3 `UNKNOWN` fleet (6.2 %) is a Pierre artefact**: AIMS resolves the fleet for 99.1 % of pilot pairings (January 2026: 16 of 1,738 unresolved vs Pierre 79 `UNKNOWN`), using `LEGMAIN.AC` of operated legs and `CRLEGGROUND.AC` of simulator legs.

---------------------------------------------------------------------------------------------------

## 1. Method and query budget

Roughly 70 read-only SQL statements (about 25 on the published/historical objects, 20 on D2, 25 on D3), all narrow (`LEG_DAY`/`DUTYDAY`/`CDATE`/`ONDAY` ranges on indexed leading columns; `LOG_*`, `HOTAC`, `ROSTERDT` only through indexed predicates; `MSTLOGCRW`, `CREXPLOG`, `LOG_LEGPAX` not touched). Query results were exported to CSV in the OS temp folder (operational data only) and compared in pandas with Pierre's CSVs. Population used for comparisons: `ROSTER.POS IN (1,2)` (CA/FO). Pierre's population is the D1 pilots (734 distinct crew in January 2026); the AIMS sketch restricted to `CWBASE IN (YUL,YYZ)` and A321/A330 qualifications gives the same block totals as all POS 1/2, so the populations are effectively equal.

---------------------------------------------------------------------------------------------------

## 2. Published and historical roster state (the new objects, critically evaluated)

### 2.1 Object inventory (verified from `sys.columns`, `sys.indexes`, row counts and data profiling; names are not documented by AIMS - interpretation is inference unless stated)

| Object | What it is | Key / grain | Rows | Date range | How it is written (inference) |
|---|---|---|---|---|---|
| **PROSTER** | Clone of `ROSTER` (same 52 columns, same PK `ID, LEG_DAY, LEG_DEP, LEG_CARRIER, LEG_FLT, LEG_LEGCD, DUTYNO, DUTYDAY, GRDDUTYBEG`) = **the roster as published ("P" = published)** | roster element | 3,417,013 | `LEG_DAY`=`DUTYDAY` 15695..17136 = **2022-12-21 .. 2026-12-01** (upper bound = `ROSTERID.PUBLISH` horizon) | filled by the AIMS publish step; see 2.2 for its freeze behaviour |
| **PROSTERDT** | Clone of `ROSTERDT` (EAV attributes, incl. RECTYPE 21 draft markers) for the published roster | `ROSTERDT` key + `RECTYPE` | 5,392,437 | 15695..17136 | same |
| **PROSTERID** | Clone of `ROSTERID` (per-crew header, `PUBLISH`, `SENIOR`) | `ID` | 6,115 | - | `PUBLISH` equals `ROSTERID.PUBLISH` for 6,087 of 6,115 crew (28 lower, 0 higher) |
| **PUBLVER** | Which **published version of which pairing each crew member received**: `ID, SDATE (=CDATE), ROUTE (=CROUTE), PLEGVERSION, PROUTVERSION` | crew x pairing instance | 394,253 | `SDATE` 15694..17136 | joins 100 % (9,082 of 9,082 in 2026-01) to `PUBLCROU` on `VERSION=PROUTVERSION` and to `PUBLLEGS` on `VERSION=PLEGVERSION`; in 2026-01 it holds 16 more crew-pairings than `PROSTER` |
| **PUBLCROU** | Published **versions of the pairing header** (copy of `CRROUTE` columns incl. `CREWNUM`, `RTECAT`; no pairing name `DESC_`) | `SDATE, ROUTE, VERSION` | 288,892 (6,834 pairings) | `SDATE` 15694..17136 | one new version at each publication that changed the pairing; 2026-01 rows by version: v1 2,767, v2 2,256, v3 1,184, ... v9 104, up to v18 (one pairing) |
| **PUBLLEGS** | Published **versions of the legs** (`DAY, CARRIER, FLT, DEP, LEGCD, ARR, AC, STD, STA, PAX, LIMTABLE, HOTEL, REMOVED, REPON/REPOFF ...`) | `SDATE, ROUTE, VERSION, DAY, DEP, CARRIER, FLT, LEGCD` | 543,701 | 15694..17136 | as above |
| **HISTCROU / HISTLEGS** | Same layouts as PUBLCROU/PUBLLEGS = **superseded pairing versions** kept for history | same | 161,246 / 585,740 (11,970 pairings) | `SDATE` 6..17246 | pairing-edit history |
| **HISTVER** | Version-change journal of pairings: `SDATE, ROUTE, LEGVERSION, CROUVERSION, ONDAY, ONTIME, N_SDATE, N_ROUTE, USER_, RECTYPE` (RECTYPE 0: 121,971; 1: 13,026; 2: 82,546, all with a new pairing key `N_SDATE/N_ROUTE` = pairing moved/renumbered; 4: 11) | event | 217,554 | `ONDAY` 16017..17101 = **2023-11-08 .. 2026-10-27** (sparse until 16079 = 2024-01-09) | audit of pairing changes after publication |
| **ORGCROU** | Original (as first built) legs of a pairing: `SDATE, ROUTE, SEQUENCE, DAY, CARRIER, FLT, LEGCD, DEP, ARR, STD, STA, PAX, AC` | pairing x sequence | 1,327,155 (7,916 pairings) | `SDATE` 9162..17136 | snapshot at creation |
| **LOG_ROSTER** | **Field-level audit trail of `ROSTER`**: key columns of the changed row + `ONDAY/ONMIN/ONSEC/ONMSEC` (timestamp), `DBOPERATION`, `AIMSOPERATION`, `AIMSTABLEID`, `AIMSFIELDID`, `DBFIELDNO`, `PRGNO`, `PRGOPTION`, `EXTERNALAPPL`, `NEWVALUE/OLDVALUE` (image). Indexes: key columns (`LOG_ROSTER_INDEX_1`), `ONDAY..` (`_2`). | one row per DB operation (per field for updates) | 12,128,278 | `ONDAY` 16205..17101 = **2024-05-14 .. 2026-10-27** | DB trigger/log writer; `DBOPERATION` **2 = INSERT of a roster row, 4 = DELETE, 3 = UPDATE (one row per changed column; `DBFIELDNO` = ordinal of the ROSTER column, e.g. 28 CHECK_IN, 31-33 NOTDATE/NOTTIME/REPMETHOD)** (verified by sequences on a crew-day) |
| **LOG_ROSTERDT** | Same for `ROSTERDT` | idem + `RECTYPE` | 17,545,053 | 16205..17101 | idem |
| **LOG_CRROUTE / LOG_CREWLEG** | Same journal for pairing header / pairing legs | key + `CDATE,CROUTE` | 201,764 / 455,619 | `ONDAY` 16204..17100 / 16204..17101 | idem |

Writers seen in `LOG_ROSTER.EXTERNALAPPL/PRGNO` on 2026-07-18/19 (aggregates only): `ScheUpd.EXE` (PRGNO 1202, schedule update), `GRAFSCHE.EXE` (graphical scheduler), `OPBIDP.exe`/`PBSEXPR.exe` (PRGNO 180000; bulk insert of the bid-awarded roster ~25 days before the day), `HOTACUPD.EXE`, and the .NET SqlClient (PRGNO -2/-3/-579583128: external/API writers). The columns `AIMSUSER`, `DBUSER`, `HOST` identify planners/workstations: **do not extract them**.

### 2.2 What `PROSTER` really is (verified experiments)

| Test | Result | Reading |
|---|---|---|
| Per-day set difference `ROSTER` vs `PROSTER` on the full 9-column key (LEG_DAY 16000, 16500, 16900, 17050, 17090 = past; 17120 = 12 days ahead) | 20-34 % of rows differ on the five past days (e.g. 17050: 807 only in ROSTER, 814 only in PROSTER, of ~2,380); only 3.6 % on 17120 (94/78) | PROSTER is **not** a mirror of ROSTER; it equals ROSTER for the not-yet-started publication window and **freezes** afterwards |
| Rows with `NOTDATE > LEG_DAY` (retro-active change) | PROSTER: **0** on 16 sampled days (15700..17136); ROSTER: 2-211 on the nine sampled past days, 0 on days after today | nothing entered after the day reaches PROSTER |
| `MAX(NOTDATE)` of PROSTER by `LEG_DAY` (every 4th day 17020..17136) | step function with values **17023, 17045, 17068, 17099/17098** (= 2026-08-10, 09-01, 09-24, 10-25); e.g. days 17076-17104 all stop at 17068 | **periodic (roughly monthly / bid-period) publication snapshots**: each snapshot covers the following ~4 weeks; changes made after the snapshot are not copied. (inference: cadence = publication of the roster period; exact trigger unknown) |
| Rebuild PROSTER for `LEG_DAY` 17050 from `ROSTER` + `LOG_ROSTER` by undoing all inserts/deletes with `ONDAY` > cut | cut 17037: 2,387 rebuilt rows vs 2,384 in PROSTER; 61 only-rebuilt / 58 only-PROSTER (**2.5 % residual**); cut 17035: 548 rows, cut 17040: 2,394 rows with 195/185 residual - the roster for that day was bulk-inserted on ONDAY 17036-17037 | the change log is complete enough to time-travel; and PROSTER corresponds to the state right after the bulk publication (~13 days before the day) |
| Crew-days with a **sickness** code in ROSTER (`MAL, MAL4, N/DM, MFIT, MALO, MHB`), January 2026, POS 1/2 | 2,312 crew-days; ROSTER still has a pairing on the same day for 21 (0.9 %); **PROSTER has a pairing on 931 (40.3 %)**, no PROSTER row at all on 422 (18.3 %), and **0** with a sickness code in PROSTER | PROSTER = roster **before** the absence was coded |
| Same over 2024-04-25..2026-08-31 (codes `MAL, MAL4, MALO, MHB, MARH`, POS 1/2, all bases) | 10,234 crew-days / 697 crew; ROSTER flight kept on **58 (0.6 %)**; PROSTER flight on **4,198 (41.0 %)**; recovered only through PROSTER: **4,158**; no PROSTER row: 2,321 (22.7 %) | Pierre: 12 of 4,671 (0.26 %); the current `ROSTER` behaves like Pierre's D2 |
| Crew-pairings with `DUTYDAY` in January 2026 | POS 1/2: `ROSTER` 2,712 (659 crew), `PROSTER` 2,556 (621), union 3,339. All positions: `ROSTER` 9,251, `PROSTER` 9,066, `PUBLVER` 9,082; 3,063 of the 9,066 published crew-pairings (**34 %**) are no longer in `ROSTER` and 3,248 of the 9,251 current ones (35 %) were added after publication (drafts, swaps, pick-ups) | the two states together describe the change flow |

### 2.3 Can we reconstruct ...?

| Need | Source | Verdict | How / limits |
|---|---|---|---|
| Roster **as published before an absence** (Pierre point 4) | `PROSTER` (+`PUBLVER` at pairing level) | **YES (verified)**, 2022-12-21 onward | Join absence crew-day to `PROSTER` rows (`ID`, `LEG_DAY`). Limits: (a) 18-23 % of sickness crew-days have **no PROSTER row** (sick coded on a blank / unpublished day) so "no pairing" is truthful there; (b) PROSTER is the **last publication snapshot before the day**, not the instant before the absence: an assignment made after the snapshot and removed before the absence is invisible (use LOG_ROSTER for that); (c) `PUBLVER/PUBLCROU` do not carry `DESC_`: 152 of 9,082 (1.7 %) published crew-pairings of 2026-01 have no `CRROUTE` row any more, so their `pairing_id` (name) cannot be rebuilt. |
| Roster **as of any past instant** `t` | `ROSTER` current + reverse `LOG_ROSTER` (ops 2/4 with `(ONDAY,ONMIN,ONSEC,ONMSEC,TABLELOGID)` > t) | **YES since 2024-05-14 (verified, 97.5 % vs PROSTER)** | Insert-log coverage of current ROSTER rows by days: 14 % for `LEG_DAY` 16210 (rows inserted before the log starts), 94 % for 16300, 99.5 % for 16600, 100 % for 16900/17050. Time zone of `ONDAY/ONMIN` (UTC or base-local) is **not established**; updates (op 3) need `OLDVALUE` decoding (`image`) only if column values, not membership, are needed. Before 2024-05-14 only PROSTER snapshots exist. |
| Pairing **as published / before re-timing** | `PUBLCROU`, `PUBLLEGS` (versions), `HISTCROU/HISTLEGS`, `ORGCROU`, `HISTVER` | **YES (since 2022-12-20 for publication versions)** | 2026-01: PUBLLEGS vs current LEGMAIN: `STD` differs on 297 of 14,301 leg-versions (2 %), `STA` 285. Pierre's D3 block hours equal the **current** LEGMAIN times (99.9 %), i.e. his D3 is not "as published". |
| Roster history for 2023-08..2024-04 events (change timestamps) | none | **NO** | LOG starts 2024-05-14; for rows still unchanged `ROSTER.NOTDATE/NOTTIME` gives the last notification only. |
| Drafts as published | `PROSTERDT` RECTYPE 21 | yes (same range as PROSTER) | not re-verified here. |

`ROSTERID.PUBLISH` (2026-12-01 = today + 28 for 2,823 crew) is the publication horizon, `ROSTERID.TRANSCOUNTER` a change counter; `PROSTERID` keeps the published copy.

### 2.4 Tested reconstruction SQL (read-only)

```sql
-- (a) roster of one day as published (use the published copy directly)
SELECT ID, DUTYDAY, DUTYNO, LEG_FLT, LEG_DEP, POS FROM TSC.dbo.PROSTER WHERE LEG_DAY = @leg_day;

-- (b) roster of one LEG_DAY as it was at day @cut (tested: @leg_day=17050, @cut=17037 -> 2,387 rows, 97.5 % identical to PROSTER)
WITH ev AS (SELECT ID,LEG_DAY,LEG_DEP,LEG_CARRIER,LEG_FLT,LEG_LEGCD,DUTYNO,DUTYDAY,GRDDUTYBEG, DBOPERATION op,
            ROW_NUMBER() OVER (PARTITION BY ID,LEG_DAY,LEG_DEP,LEG_CARRIER,LEG_FLT,LEG_LEGCD,DUTYNO,DUTYDAY,GRDDUTYBEG
                               ORDER BY ONDAY,ONMIN,ONSEC,ONMSEC,TABLELOGID) rn
            FROM TSC.dbo.LOG_ROSTER
            WHERE ONDAY BETWEEN @cut+1 AND @today AND LEG_DAY = @leg_day AND DBOPERATION IN (2,4)),   -- ONDAY index first
first_after AS (SELECT * FROM ev WHERE rn = 1),                  -- earliest event after the cut decides the state at the cut
cur AS (SELECT ID,LEG_DAY,LEG_DEP,LEG_CARRIER,LEG_FLT,LEG_LEGCD,DUTYNO,DUTYDAY,GRDDUTYBEG FROM TSC.dbo.ROSTER WHERE LEG_DAY=@leg_day)
SELECT c.* FROM cur c WHERE NOT EXISTS (SELECT 1 FROM first_after f WHERE f.op=2 AND f.ID=c.ID AND f.LEG_DEP=c.LEG_DEP AND f.LEG_CARRIER=c.LEG_CARRIER
       AND f.LEG_FLT=c.LEG_FLT AND f.LEG_LEGCD=c.LEG_LEGCD AND f.DUTYNO=c.DUTYNO AND f.DUTYDAY=c.DUTYDAY AND f.GRDDUTYBEG=c.GRDDUTYBEG)   -- inserted after the cut -> absent
UNION
SELECT ID,LEG_DAY,LEG_DEP,LEG_CARRIER,LEG_FLT,LEG_LEGCD,DUTYNO,DUTYDAY,GRDDUTYBEG FROM first_after WHERE op=4;                     -- deleted after the cut -> present

-- (c) crew-days with a sickness code today whose published roster had a flight (tested: 4,198 of 10,234 for 16186..17044)
SELECT COUNT(*) FROM (SELECT DISTINCT r.ID, r.LEG_DAY FROM TSC.dbo.ROSTER r
  WHERE r.LEG_DAY BETWEEN 16186 AND 17044 AND r.POS IN (1,2) AND r.DUTYNO<0 AND r.LEG_FLT IN (-17,-344,-300,-147,-251)) ab    -- 2024-04-25..2026-08-31; MAL, MAL4, MALO, MHB, MARH
WHERE EXISTS (SELECT 1 FROM TSC.dbo.PROSTER p WHERE p.ID=ab.ID AND p.LEG_DAY=ab.LEG_DAY AND p.DUTYNO>0 AND p.LEG_FLT>=0);
```
(The tested version of (c) wraps the counts with ROSTER/PROSTER `EXISTS` flags; run time ~2 s. Use `LEG_FLT` codes from `CRCODES` of your D4 rules.)

---------------------------------------------------------------------------------------------------

## 3. D2 `d2_rosters`

### 3.1 What Pierre's file is (v3, aggregate counts only)

493,216 rows, 827 crew, `start_utc` 2024-04-24 04:00 .. 2026-09-01, per-month 16.4-18.4 k blocks (2024-04 and 2026-09 partial). `base` YUL 305,365 / YYZ 187,851; `fleet` A321 322,040 / A330 171,176 (extra column `fleet_detail`: A321-200 312,066, A330-200 163,034, A321neoLR 9,790, A330-300 8,142, A320-200 184 - **not** in the DATASET_SCHEMAS); `position` CA 247,789 / FO 245,427. Block types: DAY_OFF 242,606; PAIRING 89,490; ABSENCE 56,150; VACATION 44,994; RESERVE 15,699 (SC 14,415, LC 1,284); OTHER 13,210; TRAINING 12,004; OFFICE 10,976; SIMULATOR 8,087 (no `REST`). 3,426 PAIRING blocks (3.8 %) have an empty `pairing_id`; 9,447 PAIRING blocks repeat an existing (crew, pairing_id) (same pairing split into 2-3 blocks 9.5-130 h apart). Zero overlapping blocks (0 by running maximum of `end_utc`), zero zero-length blocks. All non-PAIRING blocks are calendar-day blocks (start_local 00:00 for 388,243 of the 403,726 non-PAIRING blocks), 24 h: SIMULATOR, TRAINING, VACATION, DAY_OFF, ABSENCE, OFFICE, OTHER; RESERVE are 12 h windows (SC `12:00-00:00` 8,291 and `04:00-16:01` 6,058) or 24 h (LC `00:00-00:00` 1,271). UTC offsets `start_local - start_utc` are -5/-4 h only (EST/EDT) for both bases.

### 3.2 Column mapping (one row per corpus column)

| corpus column | status | AIMS source | transformation | evidence | gap / risk |
|---|---|---|---|---|---|
| `crew_id` | DERIVABLE | `ROSTER.ID` (internal crew id; not an employee number) | map to an opaque surrogate `P######` with a persistent key table kept by Air Transat; same map for D1/D4..D11 | `ROSTER.ID` 5..800900; every crew has a `ROSTERID` row | Pierre's surrogate mapping is unknown: v3 ids cannot be joined to a new extract unless he provides the key table. Do not use `SWIPECARD/NAME`. |
| `base` | DERIVABLE | `CREWQUAL.CWBASE` valid on the roster day: `LEG_DAY BETWEEN ACTIVBEG AND ACTIVEND`, `POS IN (1,2)`, `TOP 1 ORDER BY ACTIVBEG DESC, ACTIVEND DESC, CREWQUAL_ID DESC` | RTRIM | Valid on 2026-01-16: every POS 1/2 crew has exactly **1 base and 1 position** (417 crew `AC` {14,16,18}, 295 `{4,6}`, 16 `{14,16}`, 2 mixed); only YUL/YYZ appear in the sketch; 139 of 19,763 January blocks have no qualification row (base NULL) | qualification ranges overlap -> TOP 1 rule is mandatory; crew without a qualification on the day (e.g. new hires, leave) get NULL |
| `fleet` | DERIVABLE (family) | same row: `CREWQUAL.AC` -> A321 family `{14 (321), 16 (32Q), 18 (320)}`, A330 `{4 (332), 6 (333)}` (`vvAIRCTYPE.IATACODE`) | CASE | all A32x pilots hold **all three** AC values (14,16,18) simultaneously | Pierre's `fleet_detail` (A321neoLR vs A321-200, A330-200 vs -300) is **not** derivable from qualifications for non-flying days; only from the AC flown (`ROSTER.AC`, 16 = 32Q = A321neo) -> PARTIAL for `fleet_detail` (not a schema column). Pierre's `A320-200` (184 rows) cannot be reproduced from CREWQUAL either (A320 is in the A321 family set). |
| `position` | DIRECT | `ROSTER.POS` (NOT NULL on every row incl. activities): 1 -> CA, 2 -> FO | CASE | `ROSTER.POS` is NOT NULL (also on activity rows, see `ROSTER.md`); Jan 2026 filter `POS IN (1,2)` returns 19,763 crew-days incl. activity-only days | POS 4 (SP, supervising pilot) is not in Pierre's file; drafted crew carry `POS` 1 (note R3 `@DRAFT_POS_PNT = 1`) |
| `block_type` | DERIVABLE (taxonomy needs sign-off) | `ROSTER` + `CRCODES` (flags) - mapping in 3.3 | see 3.3 | Jan 2026 (POS 1/2): VACATION 1,432/248 crew vs Pierre 1,434/248; SIMULATOR 178 vs 177; ABSENCE 2,399 vs 2,107; DAY_OFF 8,430 vs 8,721; RESERVE 714 vs 557; TRAINING 449 (+173 ground legs in pairings) vs 298; OTHER 697 vs OFFICE 533 + OTHER 495 | Pierre's rules for OFFICE/OTHER/ABSENCE/TRAINING/RESERVE boundaries are not documented; see 3.3. `REST` (engine block) is not stored in AIMS (CRCODES "rest flag" = day-off-like codes), it is computed by the engine. |
| `start_utc`, `end_utc` | DERIVABLE (PAIRING, timed activities) / PARTIAL (day blocks) | PAIRING: `MIN(DAY*1440+STD)` .. `MAX(DAY*1440+STA)` of the pairing's legs (`LEGMAIN` / `CRLEGGROUND`, via `ROSTER` rows of the crew) minus report offset (60; `ROSTER.REPORTTIME` overrides, 2.2 % of flight rows) and plus debrief (15-30; `DEBRIEFTIME` overrides 0.5 %) ; timed activity: `DATEADD(MINUTE, GRDDUTYBEG, DATEADD(DAY,LEG_DAY,'1980-01-01'))` .. `GRDDUTYEND` (UTC minutes of `LEG_DAY`, `GRDDUTYEND` may exceed 1440) minus/plus `CRCODES` offsets (bytes 252-255); untimed status (`GRDDUTYBEG%1440=0 AND GRDDUTYEND%1440=0`): whole roster day | UTC min arithmetic; for untimed rows the day is the **roster (local) day**: `LEG_DAY` of timed rows is the UTC day of the start (max `GRDDUTYBEG` 1436), for untimed rows no time exists | 2026: 523,419 of 577,065 stand-alone activity rows (90.7 %) are untimed placeholders; Jan 2026 POS 1/2: untimed-status-only crew-days 12,528, timed activity only 1,564 | day blocks need a decision (local midnight to midnight, as Pierre); time-of-day of simulator/training is available in AIMS but Pierre's file flattens it to 24 h blocks |
| `start_local`, `end_local` | DERIVABLE | UTC -> **base** local: `AT TIME ZONE 'UTC' AT TIME ZONE <zone>` using `CrewSchedAI.dbo.crew_base_timezone` (YUL, YYZ = `Eastern Standard Time`, DST aware) or `GetEffectiveOffsetUtc(base,...)` | Pierre's offsets are -5/-4 only | `crew_base_timezone` has 10 bases; YWG inconsistency irrelevant | none for YUL/YYZ |
| `pairing_id` | DERIVABLE | `RTRIM(CRROUTE.DESC_)+'_'+CONVERT(char(8),DATEADD(DAY,CRROUTE.CDATE,'19800101'),112)` joined on `(CDATE,CROUTE) = (ROSTER.DUTYDAY, ROSTER.DUTYNO)` | none | 100 % of `DUTYNO>0` roster rows join `CRROUTE`; `(CDATE, DESC_)` unique | only for rows from current `ROSTER`; rows rebuilt from `PROSTER`/`PUBLVER` can lose the name if the pairing was deleted from `CRROUTE` (1.7 % in 2026-01) |
| `reserve_call_type` | DERIVABLE | `CRCODES`: **LC = `LCR`** (ID -194, `LONG CALL RESERVE`, effective 2026-03-01); **SC = `AM`, `PM`** (effective 2026-01-06) and, before that, `XAM`, `XPM` (discontinued 2026-01-06) (+ `AM0`, `PM0`, `PM1`: zero-credit/other variants) ; `REA1` (REAFFECTATION1) is a reserve-flagged reassignment code | CASE on `CRCODES.CC` | **Verified against Pierre**: LC by month 2026-03..08 = 317, 299, 190, 146, 149, 183 vs `LCR` rows in AIMS (POS 1/2, all bases) 309, 289, 183, 131, 144, 168; Pierre has **no LC before 2026-03**, matching the code's effective date; SC of the same order before 2026 (2024Q2: Pierre 1,157 vs AIMS `XAM+XPM` 1,062, with `AM0/PM0` 1,268; counts from 2024-04-25) | which of `AM0/PM0/REA1/PM1` Pierre counts as RESERVE is unknown (AIMS strict reserve 714 rows vs Pierre 557 in Jan 2026; without REA1 606; AM+PM+XAM+XPM only 531) |

Not in the schema but present in AIMS and useful: `ROSTER.NOTDATE/NOTTIME` (last notification), `ROSTERDT` RECTYPE 21 (draft marker), `ROSTER.REPORTTIME/DEBRIEFTIME` overrides.

### 3.3 `block_type` mapping (proposed; decoded flags are in `tables\CRCODES.md`)

Flags used: `b97 = byte 97` (rest bit 0x04, leave bits 0x30), `b98` (reserve-family 0x02), `b99` (training 0x01, simulator 0x02), `b101` (strict reserve 0x80). `CRCODES.ID = ROSTER.LEG_FLT` (negative) for activities.

| block_type | AIMS rule (priority order top to bottom) | Codes (examples) | Jan 2026 AIMS rows / crew (POS 1/2) | Pierre Jan 2026 |
|---|---|---|---|---|
| PAIRING | `ROSTER.DUTYNO > 0` (flight rows `LEG_FLT>=0` and ground legs inside pairings), one block per `(ID, DUTYDAY, DUTYNO)` | all pairing instances | 2,712 crew-pairings / 659 (7,490 flight rows + 173 ground-leg rows) | 3,537 blocks = 3,034 distinct (crew, pairing_id) + 96 empty id + 407 repeats; 645 crew |
| VACATION | codes with rest+leave flags `b97` 221/157: `VAC, VACA, VACM, VAMI, VNR, VNRA, IVAC, VACP, FER, FERI, FERM, FEMI, FER2, FE2A, FERP, OSTW` | VACP 773, FERP 470, VAC 172 ... | 1,432 / 248 | 1,434 / 248 |
| RESERVE | strict reserve flag `b101 & 0x80` (14 codes) | AM 223, PM 233, REA1 108, AM0 51, XPM 38, XAM 36, PM0 24, PM1 1 | 714 / 126 | 557 / 74 |
| SIMULATOR | `b99 & 3 = 3` | SIMI, SM2x/SM3x, PPC2/PPC3, TPP*, TSM* | 178 / 93 | 177 / 88 |
| TRAINING | `b99 & 1` | EPT, EPTP, GEN, SY20/SY30, REU6, DSOP, ANN... | 449 / 274 | 298 / 180 |
| ABSENCE | leave flag `b97 & 0x30`, not vacation: sickness (MAL, MAL4, MALO, MHB, MARH, MFIT, INV), parental (MAT, PAT, PAR), unpaid (CSS*, MAP), CPP4/CPP5, RETP ... | INV 1,476*, MAL 312, MFIT 182, PAT 208 | 2,399 / 285 | 2,107 / 248 |
| DAY_OFF | `CON, CONG, CONR, REAT, WFLY` + other rest-flag codes (`IOU, N/D, RELV, FCON, CON1/3/6, TDO...`) | CON 154,871 rows in 2026; WFLY 27,209 | 8,430 (CON/CONG/CONR/REAT 5,645 / 611 crew + WFLY 2,751 / 393 + other rest-flag 34) | 8,721 / 678 |
| OFFICE / OTHER | everything else: `BUR, REU, ADM, ADMP, ALPA, ALPC, BTS, DEM, WCB, N/D, SV, SEV, SHOW...` | BTS 111, ADMP 81, DEM 79, ADM 68 | 697 / 133 | OFFICE 533 + OTHER 495 |

\* `INV` (invalidity) is long-term: 52 crew carry 1,476 of the 2,399 rows in January.
Totals: AIMS ABSENCE+OTHER+TRAINING 3,545 vs Pierre ABSENCE+OFFICE+OTHER+TRAINING 3,433 (3 %): the taxonomy is consistent, the boundaries differ. **Business input needed**: Air Transat/Pierre's code-to-block mapping (which `CC` -> OFFICE/OTHER/ABSENCE/TRAINING; where `WFLY`, `REA1`, `AM0/PM0`, `RETP`, `INV` go).

Reserve windows: AIMS `AM/XAM` rows are `GRDDUTYBEG..END` 540..1259 (09:00-20:59 UTC = 04:00-15:59 EST) or 780..1499 (08:00-19:59 local); `PM/XPM` 1140..1859 (14:00-01:59 local) or 1260..1979 (16:00-03:59); `LCR` 1020..1739 / 1080..1799 (12:00-23:59 / 13:00-00:59 local, 12 h); some rows are very short (1-6 min; inference: reserve cut short after a call-out). Pierre normalises to `04:00-16:01`, `12:00-00:00` (SC) and `00:00-00:00` (LC). The times are therefore **real per-row data in AIMS** but not the same convention; D12 `reserve.*` and the engine must say which one is right.

### 3.4 Overlapping blocks and untimed placeholders (Pierre point 11)

* In **AIMS** January 2026 (POS 1/2), 19,763 crew-days with at least one row: untimed status only 12,528; flights only 5,321; timed activity only 1,564; ground leg in pairing only 100; **flights together with an untimed status the same day 97** (WFLY 52, CON 30, sickness family 13, REAT 2); flights + timed activity 66; untimed + timed activity 15; two untimed statuses 2. So ~0.5 % of crew-days carry a full-day placeholder (`CON/WFLY/...`) on a day with a pairing; the placeholder must yield to the pairing (the loader's `trimmable_block_types` rule is the right model). `ROSTER` has **no row for the days between two legs of a multi-day pairing** and a "blank day" (`BLANCHE`) has no row at all: gaps must be filled by the extractor (Pierre fills them with DAY_OFF blocks).
* In **Pierre's file** there is no overlap (0 of 493,216). The 367 trimmed / 1,599 dropped blocks of the template window are created in `roster_loader._load_pairing_duty_periods` + `load_rosters`: PAIRING blocks are replaced by D3 duty periods (true local + offset `start_utc - start_local`) and then collide with neighbouring D2 blocks. Verified cause: **D2 PAIRING times are not UTC** - for the 1,475 January-2026 pairings present in both AIMS and D2, `D2.start_utc - AIMS true first departure UTC` equals **-360 min in 806 (55 %)** and `D2.end_utc - AIMS last arrival UTC` equals **-270 min** in 339 pairings; `-60` (report = dep-60 in true UTC) occurs for 17 (1.2 %). -360 = base offset (-5 h) + 60 min report: the D2 `_utc` of pairing blocks is the **local report time labelled UTC**; D2 `start_local` is then 4-5 h too early. Over all 86,064 D2 pairing blocks, `start_local` of D2 vs first `report_local` of D3 differs by -240 min (16,725) or -300 min (8,794) and equals only 0.3 % (time-of-day, mod 1440: -240/-300 in 49.9 %). Non-pairing blocks (day off, vacation...) are true UTC (local midnight = 04:00/05:00 UTC), hence the clash. An AIMS-direct extract does not have this defect (inference on the producer side: the Snowflake mart conversion; not verified).
* Other contradictions: D2 has 2,972 distinct crew-pairings with January 2026 pairing-id dates against 2,712 in current `ROSTER` and 2,556 in `PROSTER`; the crew count per pairing equals ROSTER in 51 % and PROSTER in 45 % of 1,736 pairings -> Pierre's roster is a state that is neither (or includes other positions). Not resolved.

### 3.5 Tested SQL sketch - D2 blocks for January 2026 (counts only)

```sql
WITH q AS (SELECT r.ID, r.LEG_DAY, qq.base, qq.fleet
  FROM (SELECT DISTINCT ID, LEG_DAY FROM TSC.dbo.ROSTER WHERE LEG_DAY BETWEEN 16802 AND 16832 AND POS IN (1,2)) r
  CROSS APPLY (SELECT TOP 1 RTRIM(CWBASE) base, CASE WHEN AC IN (14,16,18) THEN 'A321' WHEN AC IN (4,6) THEN 'A330' END fleet
               FROM TSC.dbo.CREWQUAL c WHERE c.ID=r.ID AND r.LEG_DAY BETWEEN c.ACTIVBEG AND c.ACTIVEND AND c.POS IN (1,2)
               ORDER BY c.ACTIVBEG DESC, c.ACTIVEND DESC, c.CREWQUAL_ID DESC) qq),
act AS (SELECT r.ID, r.LEG_DAY, RTRIM(c.CC) cc, r.GRDDUTYBEG, r.GRDDUTYEND,
          CASE WHEN r.GRDDUTYBEG%1440=0 AND r.GRDDUTYEND%1440=0 THEN 1 ELSE 0 END untimed,
          CONVERT(int,SUBSTRING(c.DATA_BEGIN_END,97,1)) b97, CONVERT(int,SUBSTRING(c.DATA_BEGIN_END,98,1)) b98,
          CONVERT(int,SUBSTRING(c.DATA_BEGIN_END,99,1)) b99, CONVERT(int,SUBSTRING(c.DATA_BEGIN_END,101,1)) b101
        FROM TSC.dbo.ROSTER r JOIN TSC.dbo.CRCODES c ON c.ID=r.LEG_FLT
        WHERE r.LEG_DAY BETWEEN 16802 AND 16832 AND r.POS IN (1,2) AND r.DUTYNO<0),
blk AS (SELECT ID, LEG_DAY, CASE
   WHEN cc IN ('VAC','VACA','VACM','VAMI','VNR','VNRA','IVAC','VACP','FER','FERI','FERM','FEMI','FER2','FE2A','FERP','OSTW') THEN 'VACATION'
   WHEN (b101&128)=128 THEN 'RESERVE' WHEN (b99&3)=3 THEN 'SIMULATOR' WHEN (b99&1)=1 THEN 'TRAINING'
   WHEN (b97&48)<>0 THEN 'ABSENCE' WHEN cc IN ('CON','CONG','CONR','REAT','WFLY') OR (b97&4)=4 THEN 'DAY_OFF' ELSE 'OTHER' END block_type, untimed FROM act
 UNION ALL
 SELECT ID, DUTYDAY, 'PAIRING', 0 FROM (SELECT DISTINCT ID, DUTYDAY, DUTYNO FROM TSC.dbo.ROSTER
        WHERE DUTYDAY BETWEEN 16802 AND 16832 AND POS IN (1,2) AND DUTYNO>0) p)
SELECT b.block_type, q.base, q.fleet, COUNT(*) blocks, COUNT(DISTINCT b.ID) crews, SUM(b.untimed) untimed_blocks
FROM blk b LEFT JOIN q ON q.ID=b.ID AND q.LEG_DAY=b.LEG_DAY GROUP BY b.block_type, q.base, q.fleet;
```
Result (verified): 31 groups; PAIRING 2,712 (YUL A321 1,191; YUL A330 561; YYZ A321 509; YYZ A330 451), DAY_OFF 8,430, ABSENCE 2,399, VACATION 1,432, RESERVE 714, TRAINING 449, SIMULATOR 178, OTHER 697 (139 with no qualification row). Full block times additionally need the pairing duty span (section 4 query) and the timed-activity arithmetic above.

### 3.6 History depth

| Table | Range | Note |
|---|---|---|
| `ROSTER`, `ROSTERDT` | `LEG_DAY` 6947..17652 (1999-01-08 .. 2028-04-30); rows/year 2023 883,049; 2024 918,348; 2025 891,711; 2026 819,155 | the current state (retro changes included) of **all** needed months 2023-08..2026-08 |
| `PROSTER`, `PROSTERDT`, `PUBL*` | 2022-12-21 .. 2026-12-01 | covers the 36-month wish (2023-08) |
| `LOG_ROSTER`, `LOG_ROSTERDT` | 2024-05-14 .. 2026-10-27 | event-time reconstruction only from 2024-05-14 (Pierre's file starts 2024-04-24) |
| `CRROUTE/CREWLEG/CRLEGGROUND/LEGMAIN` | 2002 .. 2026-12 (pairings to 2026-12-21) | complete |

### 3.7 Comparison summary D2 (AIMS January 2026 vs Pierre v3)

VACATION and SIMULATOR match within 0.2-0.6 %; reserve LC matches the monthly counts; ABSENCE/OTHER/OFFICE/TRAINING/DAY_OFF totals agree within 3 % overall but the boundaries differ; PAIRING differs (+9.6 % distinct crew-pairings in Pierre vs current ROSTER; 407 repeated blocks; 3.8 % without pairing id); Pierre has 24 h blocks for timed simulator/training and normalised reserve windows; Pierre PAIRING `_utc` mislabelled (3.5). `fleet_detail` and the `crew_id` surrogate are the only items that cannot be rebuilt without Pierre's key/mapping.

### 3.8 Verdict D2: **MOSTLY**

All 11 columns can be produced from AIMS tables with SQL, with measurable fidelity: base/fleet/position from `CREWQUAL`+`ROSTER.POS`, `pairing_id` from `CRROUTE`, `reserve_call_type` from `CRCODES` (LC/SC confirmed by Pierre's counts), `block_type` from `CRCODES` flags, times from `GRDDUTY*`/`LEGMAIN`. Not FULL because (i) the taxonomy and day-block/reserve-window conventions are business decisions (Pierre's differ from AIMS), (ii) `fleet_detail` is not a crew attribute, (iii) the surrogate key map is external, (iv) which roster state (current vs published vs as-of) is "D2" must be decided - AIMS can provide all three.
Missing / needed, in order: (1) agreed `CRCODES.CC` -> `block_type` table (incl. `WFLY`, `REA1`, `AM0/PM0`, office codes); (2) definition of the D2 state (published `PROSTER` vs current `ROSTER` vs as-of `LOG_ROSTER`); (3) crew surrogate key table; (4) report/debrief and reserve-window conventions; (5) rule for blank days and days inside multi-day pairings; (6) decision on `fleet_detail`.

---------------------------------------------------------------------------------------------------

## 4. D3 `d3_pairings`

### 4.1 Pierre's file
45,651 pairings (unique ids), start dates 2024-04-14 .. 2026-08-31 (ids carry the date: `start_date == id date` 100 %); `base` YUL 29,740 / YYZ 15,889 / 22 others (YQB 4, CUN 3, YOW 3...); `fleet` A321 28,198, A330 14,611, **UNKNOWN 2,842 (6.2 %)** (fleet_detail A321neoLR 18,723, A330-200 13,210, A321-200 9,287, A330-300 1,401, A320-200 188); complements `CA:1,FO:1` 22,986, `FO:1` 12,429, `CA:1` 8,232, `CA:2` 1,041 ...; `duty_periods` 1..7 (+ outliers 8, 10, 11, 17); `days` 1..11 (+18); `credit_hours` mean 11.5, 1,032 zeros (mostly prefixes S 566, H 264, T 39..., Y 35 of 35); layover count = `duty_periods - 1` in 100 %.
Monthly count comparison with `CRROUTE` pilot pairings (bytes CM/PO/SP > 0), Pierre / AIMS: 2024-05 1,303/1,305; 2024-12 2,504/2,505; 2025-06 1,369/1,369; 2026-01 1,737/1,738; 2026-08 1,701/1,702; **ratio 0.996-1.000 in every month from 2024-05 to 2026-08** (2024-04: partial month, Pierre starts 2024-04-14). AIMS has the same family for 2023-06 .. 2026-12.

### 4.2 Column mapping

| corpus column | status | AIMS source | transformation | evidence | gap / risk |
|---|---|---|---|---|---|
| `pairing_id` | DERIVABLE | `CRROUTE.DESC_` + `CRROUTE.CDATE` | `RTRIM(DESC_)+'_'+yyyymmdd(DATEADD(DAY,CDATE,'1980-01-01'))` (UTC date of first departure) | 1,737 of 1,738 January pairings identical; 0 Pierre-only ids; `(CDATE,DESC_)` unique | pairing set = `CRROUTE` rows whose `CREWNUM` has CM, PO or SP > 0 (pilot pairings); cabin pairings (`D*`, `F*`) are excluded by the same test |
| `base` | DERIVABLE | departure station of the first leg: `CREWLEG.DEP` at min `DAY*1440+STD` | RTRIM | = first leg origin in 100 % of Pierre rows; vs AIMS 99.94 % (1,736 of 1,737) | AIMS has no pairing-base column (`CRROUTE` has none; `UNCREWED_ROUTES.BASE` exists only for 9,091 transient future pairings); ground-first pairings (S*, T*) take the station of the ground leg |
| `fleet` | DERIVABLE | operated legs (`CREWLEG.PAX=0`, `FLT>0`) -> `LEGMAIN.AC` -> A321 `{14,16,18}` / A330 `{4,6}`; fallback `CRLEGGROUND.AC` of ground legs | CASE | Jan 2026: A32x 1,099 + A330 542 by operated legs, +54 +27 by ground-leg AC, 14 deadhead-only, 2 no legs -> **1,722 of 1,738 (99.1 %) resolved**; tested header agrees with Pierre on 95.5 % (Pierre UNKNOWN 79 -> AIMS resolves 67 of them; 4 + 4 A321<->A330 disagreements) | 118 January pairings mix AC 14 and 16 (A321 / A321neo): `fleet_detail` needs a tie rule (first operated leg?). Deadhead-only pairings stay UNKNOWN |
| `position_complement` | DERIVABLE | `CRROUTE.CREWNUM` byte 1 = CM -> `CA:n`, byte 2 = PO -> `FO:n` (byte 4 SP, ignore) | concatenation `CA:1,FO:1` | Jan 2026: `CA:1,FO:1` 882, `FO:1` 447, `CA:1` 337 (336), `CA:2` 28, `FO:2` 21, `CA:1,FO:2` 16, `CA:2,FO:1` 5, `CA:3,FO:1` 1 - identical to Pierre; tested header **100 %** | none |
| `duty_periods` | DERIVABLE | `COUNT(DISTINCT CREWLEG.DAY)` over the legs (flights + ground, `REMOVED=0`) | UTC departure day | tested header **100 %** vs Pierre | it is the number of distinct **UTC departure days**, not duty periods in the legality sense (a duty crossing UTC midnight or two duties in one UTC day are mis-counted). A rest-gap based count (e.g. >= 8 h between legs) agrees with distinct days in only 80 %; `CREWLEG.REPON` is non-zero only on the first leg of the pairing (76 % of pairings), so it cannot mark later duty starts |
| `credit_hours` | PARTIAL | `SUM((LEGMAIN.STA-LEGMAIN.STD)/60.0)` over operated legs (`PAX=0`) | = Pierre's definition | Pierre `credit_hours == Σ block_hours` in 100 % of 45,651 rows; tested header within 0.02 h on 96.3 % | **not a pay credit**: no table inspected holds pairing credit (`UNCREWED_ROUTES.COCKPITCREDIT/CABINCREDIT` exist but are 0 on all 9,091 rows; `vvALLWRDC`/`ALLWCREDITSTNG` are allowance credits per crew-day; `TIMEPNCPNT.CHV` is timesheet). Minimum-guarantee/duty-rig credit would need the agreement rules (D12). 1,032 zeros are pairings without operated legs (training/ground/deadhead) |
| `layover_stations` | DERIVABLE | arrival station of the last leg of each UTC day index except the last (`LEGMAIN.ARR`), joined with the pipe character in time order | string aggregation | Pierre's list equals this rule in 100 % of rows (45,651); AIMS `HOTAC` (category 0, `PROCESSSTATUS=0`) agrees on the number of stays in 1,420 of 1,738 (81.7 %), HOTAC has more stays in 315 (this comparison used a >= 8 h gap rule between consecutive flights as the derived count) | HOTAC is versioned and includes non-layover hotels; derive from legs, use HOTAC only as corroboration. Local-date vs UTC-day indexing must be fixed (Pierre uses UTC day index) |
| `start_date` | DIRECT | `DATEADD(DAY, CRROUTE.CDATE, '1980-01-01')` | none | = id date 100 % | it is the **UTC** date of the first departure: differs from the local date of the first report on 31 % of Pierre pairings |
| `days` | DERIVABLE | `MAX(CREWLEG.DAY) - CDATE + 1` | UTC departure-day span | tested header **100 %**; `ENDDATE - CDATE + 1` would **differ** on 380 of 1,738 (22 %, last leg lands after UTC midnight) | do not use `CRROUTE.ENDDATE` |

### 4.3 Tested SQL sketch (January 2026; ran in ~1 s, 1,738 rows)

```sql
WITH pp AS (SELECT CDATE, CROUTE, RTRIM(DESC_) desc_, CREWNUM FROM TSC.dbo.CRROUTE
            WHERE CDATE BETWEEN 16802 AND 16832
              AND CONVERT(int,SUBSTRING(CREWNUM,1,1))+CONVERT(int,SUBSTRING(CREWNUM,2,1))+CONVERT(int,SUBSTRING(CREWNUM,4,1))>0),
lg AS (SELECT pp.CDATE, pp.CROUTE, cl.DAY, cl.DEP, cl.FLT, cl.PAX, lm.AC flt_ac, lm.STD flt_std, lm.STA flt_sta, g.AC g_ac,
              COALESCE(lm.STD, g.STD) std_u
       FROM pp JOIN TSC.dbo.CREWLEG cl ON cl.CDATE=pp.CDATE AND cl.CROUTE=pp.CROUTE AND cl.REMOVED=0
       LEFT JOIN TSC.dbo.LEGMAIN lm ON cl.FLT>0 AND lm.DAY=cl.DAY AND lm.DEP=cl.DEP AND lm.CARRIER=cl.CARRIER AND lm.FLT=cl.FLT AND lm.LEGCD=cl.LEGCD
       LEFT JOIN TSC.dbo.CRLEGGROUND g ON cl.FLT<0 AND g.DAY=cl.DAY AND g.DEP=cl.DEP AND g.CARRIER=cl.CARRIER AND g.FLT=cl.FLT
                                      AND g.LEGCD=cl.LEGCD AND g.CDATE=cl.CDATE AND g.CROUTE=cl.CROUTE),
ord AS (SELECT lg.*, ROW_NUMBER() OVER (PARTITION BY CDATE,CROUTE ORDER BY DAY*1440+std_u) rn_first FROM lg),
agg AS (SELECT CDATE, CROUTE, MAX(CASE WHEN rn_first=1 THEN RTRIM(DEP) END) base,
          COUNT(DISTINCT DAY) duty_periods, MAX(DAY)-CDATE+1 days,
          CAST(SUM(CASE WHEN FLT>0 AND PAX=0 THEN (flt_sta-flt_std)/60.0 ELSE 0 END) AS decimal(9,2)) credit_hours_as_block_sum,
          SUM(CASE WHEN FLT>0 AND PAX=0 AND flt_ac IN (14,16,18) THEN 1 ELSE 0 END) op_a32,
          SUM(CASE WHEN FLT>0 AND PAX=0 AND flt_ac IN (4,6) THEN 1 ELSE 0 END) op_a33,
          SUM(CASE WHEN FLT<0 AND g_ac IN (14,16,18) THEN 1 ELSE 0 END) g_a32, SUM(CASE WHEN FLT<0 AND g_ac IN (4,6) THEN 1 ELSE 0 END) g_a33
        FROM ord GROUP BY CDATE, CROUTE)
SELECT pp.desc_+'_'+CONVERT(char(8),DATEADD(DAY,pp.CDATE,'19800101'),112) pairing_id, a.base,
       CASE WHEN a.op_a32>0 AND a.op_a33=0 THEN 'A321' WHEN a.op_a33>0 AND a.op_a32=0 THEN 'A330'
            WHEN a.op_a32=0 AND a.op_a33=0 AND a.g_a32>0 AND a.g_a33=0 THEN 'A321' WHEN a.op_a32=0 AND a.op_a33=0 AND a.g_a33>0 AND a.g_a32=0 THEN 'A330'
            WHEN a.op_a32>0 AND a.op_a33>0 THEN 'MIXED' ELSE 'UNKNOWN' END fleet,
       (CASE WHEN CONVERT(int,SUBSTRING(pp.CREWNUM,1,1))>0 THEN 'CA:'+CAST(CONVERT(int,SUBSTRING(pp.CREWNUM,1,1)) AS varchar(2)) ELSE '' END
        +CASE WHEN CONVERT(int,SUBSTRING(pp.CREWNUM,1,1))>0 AND CONVERT(int,SUBSTRING(pp.CREWNUM,2,1))>0 THEN ',' ELSE '' END
        +CASE WHEN CONVERT(int,SUBSTRING(pp.CREWNUM,2,1))>0 THEN 'FO:'+CAST(CONVERT(int,SUBSTRING(pp.CREWNUM,2,1)) AS varchar(2)) ELSE '' END) position_complement,
       a.duty_periods, a.days, a.credit_hours_as_block_sum, DATEADD(DAY,pp.CDATE,'19800101') start_date
FROM pp JOIN agg a ON a.CDATE=pp.CDATE AND a.CROUTE=pp.CROUTE;
```
Result (verified): 1,738 pairings (A321 1,153, A330 569, UNKNOWN 16; YUL 1,124, YYZ 614); vs Pierre (1,737 common): base 99.94 %, complement 100 %, duty_periods 100 %, days 100 %, credit 96.3 %, fleet 95.5 %. `layover_stations` is built from the legs query of section 5 (last leg of each day index).

### 4.4 History depth
`CRROUTE` rows from 2002; pilot pairings by start month are continuous from 2023-06 (355 in the partial month) to 2026-12 (e.g. 2023-08 1,544, 2024-01 1,436, 2025-01 1,768). Pairings are created ~7 weeks ahead (CDATE up to 2026-12-21). **Past states**: `CRROUTE/CREWLEG/LEGMAIN` hold the *current* definition; published versions in `PUBLCROU/PUBLLEGS` (2022-12-20 onward, STD differs on ~2 % of legs in 2026-01); original legs in `ORGCROU`; pairing edit log `LOG_CRROUTE/LOG_CREWLEG` from 2024-05-13.

### 4.5 Verdict D3 pairings: **MOSTLY (FULL on 8/9 columns)**
Pairing set, base, complement, duty_periods, days, layover, start_date are exact; fleet is better than Pierre's; `credit_hours` is reproducible only as scheduled block sum, which is not the credit Pierre's data dictionary promises. Missing/needed, in order: (1) definition of `credit_hours` (block sum vs pay credit, and if pay credit, the agreement credit rules); (2) tie rule for pairings mixing 321 and 32Q (`fleet_detail`), and whether `A320` joins `A321`; (3) confirmation that `duty_periods`/`days` stay UTC-day based (Pierre's convention) or move to true duty periods / local dates; (4) treatment of pairings with no operated legs (S/T/H prefixes: simulator, ground, deadhead) - include or exclude.

---------------------------------------------------------------------------------------------------

## 5. D3 `d3_pairing_legs` (+ optional `deadhead`)

### 5.1 Pierre's file
129,038 legs for the 45,651 pairings (no orphan either way); flight numbers all `TS` + number (103,746 `TSnnn`, 6,723 `TSn`, 5,783 `TSnnnn`, 3,606 `TSnn`) and **9,180 ground legs** written `TS-<code>` (7.1 %, origin = destination, from `CREWLEG.FLT<0`; 5,069 with times, **4,111 without** = the "3.2 % legs without times"); `deadhead = 1` on 31,363 legs (24.3 %; `block_hours = 0` on exactly those); origin = destination on 12,903 legs (the 9,180 ground legs + 3,723 flight-numbered legs, unexplained: possible return/round-trip legs, not checked). Rules recovered from the data: `report_local = dep_local - 60 min` on the **first leg of each `duty_period` group** (96,600 legs, always exactly 60), `release_local = arr_local + 30 min` on the **last leg of each group**, otherwise report = dep and release = arr (0 offset); `duty_period` = UTC departure day index (`DAY - CDATE + 1`, equals AIMS on 99.94 % of aligned flight legs); `block_hours` = scheduled `(STA-STD)` rounded to 2 decimals on operated legs (99.9 %), 0 on deadhead (99.7 %), and for ground legs 4.92 (4,427 legs) or blank (4,163; the value does **not** equal the CRLEGGROUND duration, 2.3 % equal).

### 5.2 Column mapping

| corpus column | status | AIMS source | transformation | evidence | gap / risk |
|---|---|---|---|---|---|
| `pairing_id` | DERIVABLE | see section 4 | | all 129,038 legs match a header | |
| `duty_period` | DERIVABLE | `CREWLEG.DAY - CREWLEG.CDATE + 1` | UTC departure day index | 99.94 % of 5,023 aligned flight legs equal Pierre; local-date variants only 76-81 % | see 4.2 (`duty_periods`) |
| `leg_seq` | DERIVABLE | `ROW_NUMBER() OVER (PARTITION BY pairing, duty_period ORDER BY DAY*1440+STD)`; `CREWLEG.ORDER_` gives the pairing order (0-based, contiguous) | | aligned by `ORDER_` the origin/destination equal Pierre on 97.6 % of 5,303 legs (rest: ground-leg ordering, multi-day pairs) | ground legs have `STD/STA` from `CRLEGGROUND`; ties need `ORDER_` |
| `flight_no` | PARTIAL | `vvCarriers.CODE` (carrier of `CREWLEG.CARRIER`) + `FLT`; ground: `FLT < 0` = `CRCODES.ID` (both <= 0) | Pierre writes `TS` + FLT for **every** carrier | `TS`+FLT equals AIMS `FLT` on 98.2 % of aligned legs; 1,220 of 5,305 January legs are other carriers (`CARRIER` 9 surface transport 355, 13 AC 182, 73: 150, 434: 140 ...) | Pierre loses the operating carrier (a deadhead on a partner is labelled TS); ground legs are encoded as negative numbers - the code (`CRCODES.CC`) is richer |
| `origin` | DIRECT | `CREWLEG.DEP` (RTRIM) | | | |
| `destination` | DIRECT | `LEGMAIN.ARR` (flights); `CRLEGGROUND.ARR` (= DEP) for ground legs | RTRIM | | |
| `dep_local`, `arr_local` | DERIVABLE | `DATEADD(MINUTE, STD (or STA), DATEADD(DAY, DAY, '1980-01-01'))` (UTC) + `CrewSchedAI.dbo.GetEffectiveOffsetUtc(station, utc_instant)` at the **departure station for dep** and **arrival station for arr** (ground legs: `CRLEGGROUND.STD/STA`) | `+ ROUND(offset*60)` minutes | January 2026: 5,305 legs, **0 NULL offsets**; vs Pierre `dep_local` equal on **96.5 %** (5,107 aligned flight/ground legs; `arr_local` 95.6 %); the remaining 3.5 % are mostly a +1 day shift (79) and ground-leg ordering (87 ground legs) - cause not determined | `LEGMAIN.STD/STA` hold the **current** schedule (not as published); the zone table has 5 stations with `ZONENO=0` (ECP, YTM, BYJ, TSF, CAX) but only **2 legs** (BYJ) in 2024-04-25..2026-08-31 use one; YWG zone issue noted in `vvAirports`; function does not evaluate `DATE_EXCEPT` (known data issues: PAP, SJD, YXY, CMN/RAK). Pierre has 4,111 legs without times; AIMS has STD/STA for 100 % of the 5,305 January legs (0 flights without time, 0 ground legs without time) |
| `report_local` | PARTIAL | not stored per leg. Ingredients: `CREWLEG.REPON` (60 / 80 / 30 on the **first leg of the pairing only**: Jan 2026 flights REPON 60 on 1,351, 0 on 3,790), `ROSTER.REPORTTIME` override (2.2 % of flight rows), standard offsets hard-coded in R3/R4 (60; 80 overseas PNC; 30 deadhead), `CRCODES` bytes 252-253 for ground codes (0/30/60/90) | convention: Pierre = `dep_local - 60` on the first leg of each UTC-day group | 100 % of Pierre's first legs are exactly -60; `ROSTER` overrides exist | business input: confirm 60 min for pilots; later duty days use the same constant (AIMS has no value); drafted overrides are cleared in R5 |
| `release_local` | PARTIAL | not stored. R3/R4 use 15 min debrief; `CREWLEG.REPOFF = 0` on every row; `ROSTER.DEBRIEFTIME` override (0.5 %); `CRCODES` bytes 254-255 for ground (0/15/30/60) | Pierre = `arr_local + 30` on the last leg of each UTC-day group | 95,040 legs +30 min in the file | Pierre's 30 differs from the 15 min in the planner code: confirm |
| `block_hours` | DERIVABLE (flight legs) / UNKNOWN (ground legs) | `(LEGMAIN.STA - LEGMAIN.STD)/60.0` (scheduled, UTC minutes), 0 when `CREWLEG.PAX = 1` | round 2 dp | operated legs **99.9 %** (3,656 of 3,659 equal), deadhead 0 in 99.7 % | actual block (`LEGTIMES.BLON-BLOF`, `OPSATA-OPSATD`) exists for flown legs (LEGTIMES 429,432 rows, latest 2026-10-28; none for cancelled/not yet flown) but Pierre uses schedule; ground-leg `block_hours` 4.92 / blank in Pierre cannot be matched to `CRLEGGROUND.STA-STD` (2.3 %): **UNKNOWN** semantics |
| `deadhead` (optional) | DIRECT | `CREWLEG.PAX` (0/1) | | aligned legs agree 98.8 %; AIMS 1,413 PAX legs vs Pierre 1,412 in January | PAX is per pairing-leg; cabin/pilot split is by pairing |

### 5.3 Tested SQL sketch (January 2026; exported to CSV and compared; 5,305 rows)

```sql
WITH pp AS (SELECT CDATE,CROUTE,DESC_ FROM TSC.dbo.CRROUTE WHERE CDATE BETWEEN 16802 AND 16832
            AND CONVERT(int,SUBSTRING(CREWNUM,1,1))+CONVERT(int,SUBSTRING(CREWNUM,2,1))+CONVERT(int,SUBSTRING(CREWNUM,4,1))>0),
lg AS (SELECT pp.CDATE, pp.CROUTE, RTRIM(pp.DESC_)+'_'+CONVERT(char(8),DATEADD(DAY,pp.CDATE,'19800101'),112) pairing_id,
              cl.ORDER_, cl.FLT, cl.CARRIER, cl.PAX, cl.REPON, RTRIM(cl.DEP) origin, RTRIM(lm.ARR) destination, cl.DAY, lm.STD std_u, lm.STA sta_u, lm.AC
       FROM pp JOIN TSC.dbo.CREWLEG cl ON cl.CDATE=pp.CDATE AND cl.CROUTE=pp.CROUTE AND cl.REMOVED=0 AND cl.FLT>0
       JOIN TSC.dbo.LEGMAIN lm ON lm.DAY=cl.DAY AND lm.DEP=cl.DEP AND lm.CARRIER=cl.CARRIER AND lm.FLT=cl.FLT AND lm.LEGCD=cl.LEGCD
       UNION ALL
       SELECT pp.CDATE, pp.CROUTE, RTRIM(pp.DESC_)+'_'+CONVERT(char(8),DATEADD(DAY,pp.CDATE,'19800101'),112), cl.ORDER_, cl.FLT, cl.CARRIER, 0, cl.REPON,
              RTRIM(cl.DEP), RTRIM(g.ARR), cl.DAY, g.STD, g.STA, g.AC
       FROM pp JOIN TSC.dbo.CREWLEG cl ON cl.CDATE=pp.CDATE AND cl.CROUTE=pp.CROUTE AND cl.REMOVED=0 AND cl.FLT<0
       JOIN TSC.dbo.CRLEGGROUND g ON g.DAY=cl.DAY AND g.DEP=cl.DEP AND g.CARRIER=cl.CARRIER AND g.FLT=cl.FLT AND g.LEGCD=cl.LEGCD
                                 AND g.CDATE=cl.CDATE AND g.CROUTE=cl.CROUTE)
SELECT lg.pairing_id, lg.ORDER_, lg.FLT, lg.CARRIER, lg.PAX, lg.origin, lg.destination, lg.AC,
       DATEADD(MINUTE, lg.std_u, DATEADD(DAY, lg.DAY, '19800101')) dep_utc, DATEADD(MINUTE, lg.sta_u, DATEADD(DAY, lg.DAY, '19800101')) arr_utc,
       o1.Effective_UTC_Offset dep_off, o2.Effective_UTC_Offset arr_off
FROM lg
OUTER APPLY CrewSchedAI.dbo.GetEffectiveOffsetUtc(lg.origin, DATEADD(MINUTE, lg.std_u, DATEADD(DAY, lg.DAY, '19800101'))) o1
OUTER APPLY CrewSchedAI.dbo.GetEffectiveOffsetUtc(lg.destination, DATEADD(MINUTE, lg.sta_u, DATEADD(DAY, lg.DAY, '19800101'))) o2;
-- dep_local = DATEADD(MINUTE, ROUND(dep_off*60,0), dep_utc); arr_local likewise; run in database CrewSchedAI (3-part names)
```
Result: 5,305 legs / 1,738 pairings (5,141 flight legs + 164 ground legs; 1,413 PAX = 1; 4,085 carrier-1 legs, 1,220 other carriers); 0 NULL offsets. Pierre has 5,333 legs for the same pairings (28 more).

### 5.4 History depth and fidelity
`CREWLEG` (2002-12 .. 2026-12-21; `REMOVED=1` only 187 rows, none after 2023), `LEGMAIN` (2002 .. 2026), `CRLEGGROUND` (2002 .. 2026), `LEGTIMES` (2002-12 .. 2026-10-28). All present for 2023-08..2026-08. Schedule times are the **latest** values (retimed legs overwrite `STD/STA`; `LEGMAIN.ORGSTD/ORGSTA/ORGDAY` keep the pre-change values on retimed legs; published versions in `PUBLLEGS`). Pierre's block hours equal the current LEGMAIN schedule, so his D3 is also "current".

### 5.5 Verdict D3 legs: **MOSTLY**
All structural columns and both local times are derivable and verified (96.5 % identical; Pierre's mismatches are +1-day shifts and ground-leg order; his missing times and `UNKNOWN` fleets do not exist in AIMS). Not FULL because report/release are conventions, flight_no loses carrier in Pierre's format, and ground-leg `block_hours` semantic is unknown. Missing/needed, in order: (1) report/release offsets (Pierre 60/30 vs code 60 (80 overseas)/15; apply overrides?); (2) flight_no format (carrier prefix; ground-leg code); (3) ground-leg `block_hours` rule (Pierre 4.92 / blank); (4) scheduled vs actual block (LEGTIMES) vs as-published (PUBLLEGS); (5) whether other-carrier deadhead legs are kept.

---------------------------------------------------------------------------------------------------

## 6. Notes on the newly discovered objects relied on

* **PROSTER / PROSTERDT / PROSTERID** - published copy of ROSTER/ROSTERDT/ROSTERID, 3.4 M / 5.4 M / 6,115 rows, 2022-12-21..2026-12-01. Frozen per publication snapshot (cut-offs seen 2026-08-10, 09-01, 09-24, 10-25); never contains a change dated after its day. Use for "as published". Not documented by AIMS; behaviour inferred from 6 day-level diffs, `NOTDATE` profiles and a reconstruction test.
* **PUBLVER / PUBLCROU / PUBLLEGS** - per-crew version pointers and the published pairing versions (2022-12-20..2026-12-01; max 18 versions per pairing in 2026-01). No pairing name. Join `PUBLVER(ID,SDATE,ROUTE)` -> `PUBLCROU(SDATE,ROUTE,VERSION=PROUTVERSION)` / `PUBLLEGS(...,VERSION=PLEGVERSION)`.
* **HISTCROU / HISTLEGS / HISTVER / ORGCROU** - superseded versions, version-change journal (2023-11-08..2026-10-27) and original pairing legs. Useful for re-timing analysis; not needed for D2/D3.
* **LOG_ROSTER / LOG_ROSTERDT / LOG_CRROUTE / LOG_CREWLEG** - complete-enough audit trail (97.5 % reconstruction), 12.1 M / 17.5 M / 0.2 M / 0.46 M rows, from 2024-05-13/14 to 2026-10-27. Never scan without `ONDAY` (index `_2`) or the key prefix (index `_1`).
* `ROSTER.NOTDATE/NOTTIME` - last notification of the row (not a history); 31,047 retro-active rows in 2026.
* `UNCREWED_ROUTES` (9,091 transient rows, `DUTYDAY` 16888..17138, credits all 0): not a source for credit.

---------------------------------------------------------------------------------------------------

## 7. Consolidated list: what is missing and what business input is needed (priority order)

1. **Which roster state is D2** (published `PROSTER` snapshot, current `ROSTER`, or as-of `LOG_ROSTER`); AIMS can deliver all, the engine needs the published-before-absence state to test eligibility (Pierre's V3 check).
2. **Code -> block_type table** (and which reserve codes count; `WFLY`, `REA1`, `AM0/PM0` decisions) - section 3.3.
3. **Conventions**: report 60 min (80?), release 15 vs 30 min, reserve window times, day blocks local midnight, `duty_periods`/`days` UTC vs local; one place (D12 or config) must state them.
4. **`credit_hours` definition** (block sum vs pay credit) and the credit rules if pay credit is wanted.
5. **Crew surrogate key map** and keeping it stable across D1..D11.
6. **Fleet rule**: `fleet_detail` (321 vs 32Q) tie rule for mixed pairings; treatment of deadhead-only/ground pairings.
7. **History**: ROSTER/PROSTER/CRROUTE cover 2023-08..2026-08; event times from `LOG_ROSTER` only from 2024-05-14.
8. Optional clean-up on Pierre's side if his files are still used: D2 PAIRING `_utc` mislabelled as UTC (-4/-5 h); 3.8 % pairing blocks without id; 407 repeated blocks in January 2026; D3 ground legs without times, `TS` prefix for every carrier, `UNKNOWN` fleet (all avoidable by the AIMS-direct extraction).




