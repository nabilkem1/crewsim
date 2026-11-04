# CrewSim corpus from AIMS (TSC) - D4 absences, D5 reserve call-outs, D6 schedule changes, direct draft export

Scope of this file: `d4_absences` (+ optional `notification_source`), `d5_reserve_callouts`, `d6_schedule_changes`, and the direct draft export Nabil asked for in `backlog\verify\pierre2_export_drafts_aims.md`. Also an evaluation of `Pierre3.md` point 4 (empty `notification_ts`).

Method: read-only SQL against the live TSC database (`10.180.1.10`), bounded by indexed keys / narrow day ranges, aggregates only (no crew ids, names, free text or message content were read or are reproduced). v3 CSV facts come from `C:\dev\crewsim\src\crewsim\data\corpus\real_datav2\v3\*.csv` (aggregate counts only). **Verified** = measured on data; **inference** = reasoned from names/behaviour and must be confirmed by the business. Day numbers = days since 1980-01-01 (2024-04-24 = 16185, 2024-05-14 = 16205, 2026-08-31 = 17044, 2026-10-27 = 17101).

Snapshot caveat: the last journal row in TSC is 2026-10-27 04:14 (local), although the server clock says 2026-11-03: the database is a refreshed copy about one week old. All "history" below stops at 2026-10-27.

---------------------------------------------------------------------------------------------------

## 0. Headline findings

| # | Finding | Evidence |
|---|---|---|
| 1 | AIMS **does** keep an event history. Three layers: (a) `LOG_ROSTER` / `LOG_ROSTERDT` = row-level journal of every insert / update / delete of ROSTER / ROSTERDT, with timestamp, user, program, and old+new value for updated fields (2024-05-14 -> 2026-10-27); (b) `LOG` = business-level roster-change log (old duty -> new duty per crew-day, who, when, **crew-notification stamp**), dense from 2023-11-08, sick/reserve tracking from 2024-03-14; (c) `PROSTER` / `PROSTERDT` = **published roster snapshot** (2022-12-21 -> 2026-12-01). | section 1 |
| 2 | **v3 D5 is exactly "PROSTER pilot reserve rows".** Rows per month in v3 D5 equal the number of PROSTER pilot reserve-code rows (codes XAM, XPM, AM, PM, AM0, PM0 = SC; LCR = LC) within +-2 for every month checked (e.g. 2024-05 = 1,015 both; 2025-03 = 1,194 both; 2026-03 = 452 LC + 234 SC both). So D5's skeleton is FULL from AIMS and PROSTER goes back to 2022-12-21 (covers the 36-month target). | section 5 |
| 3 | **`INTROUVABLE` / `AUCUNE_ROTATION_A_RETIRER` in D4 are source artefacts, not data limits.** 140 of the 174 INTROUVABLE rows are absences starting 2024-04-24..2024-05-31, i.e. before the retention start of the row journal (2024-05-14). `LOG` has the sick-code entry (with timestamp) for 151/151 pilot sick-run starts in that window; the 650 AUCUNE rows are sick codes entered on days with no pairing - the journal still has the sick-code *insert*. | section 4.5 |
| 4 | `ROSTER.NOTDATE/NOTTIME` is a free, permanent fallback timestamp: populated for ~100 % of sick roster rows back to 2022, equals the journal insert stamp for 144/145 sampled sick run starts, and for 87-95 % of drafts / reserve call-outs in 2023 is within 0-3 days before the flight (last-touch semantics). | sections 4.5, 5, 7 |
| 5 | **Prior status of drafted pilots is overwhelmingly `WFLY` ("willing to fly"), not day off.** Jan 2026, 373 PNT draft pairings: 318 (85 %) came from WFLY, 20 from CON/CONG/CONR, 5 from reserve codes, 7 from other activity codes, 23 from another pairing or an empty day. | section 7 |
| 6 | All journal clocks (`ONDAY/ONMIN`, `LOG.ONDATE/ONTIME`, `ROSTER.NOTDATE/NOTTIME`) are **server-local wall-clock (Montreal), not UTC** (inference from working-hour shape, see 1.4). v3 timestamps are documented as UTC: a DST-aware conversion is required. | section 1.4 |
| 7 | IOC (MOVEMENT.EXE) changes are written to `LOG_ROSTER` but almost never to `LOG` (1 of 1,236 pairing-adds in Jan 2026). D6 / drafts initiated by IOC therefore need `LOG_ROSTER` (from 2024-05-14 only). | section 6 |
| 8 | Reserve **decline / no-show are recorded as roster activity codes** (`REFU`, `RFU1`, `NSHW`, `NSHP`, `RAFP`, `LATE`) but are extremely rare for pilots (2 `REFU`, 46 `NSHW`, 15 `NSHP` in 2025-26). "Released" is not a discrete AIMS event. | section 5.3 |
| 9 | Pay multiplier / credit of drafted legs is only visible in `TIMEPNCPNT` for LEG_DAY 2026-05-27 -> 2026-10-07 (T_1_5 on 61 % of drafted pilot legs, T_2 on 1 %). | section 7 |
| 10 | The v3 D6 volume dips (Jun-24, Dec-24, Jun-25, Dec-25, Jul/Aug-26) are **not** present in the AIMS journal (pairing-add rows in `LOG` are 4.8k-8.1k every month). They are extraction artefacts of the v3 files. | section 6.5 |

Verdicts (detail in each section):

| Dataset | Verdict | One line |
|---|---|---|
| D4 `d4_absences` | **MOSTLY** | everything derivable; real timestamp for every absence >= 2024-03-14 (journal), approximation before; `absence_type` taxonomy needs Pierre's code list. |
| D5 `d5_reserve_callouts` | **MOSTLY** | skeleton + call/report times + SC/LC derivable for 36 months; outcomes `declined/no-show/released` only approximable. |
| D6 `d6_schedule_changes` | **PARTIAL** | old/new block, new pairing, timestamp derivable; `reason_code` and `initiator` are heuristics (no reason / user-group field decoded). |
| Draft export (`d12_drafts`) | **MOSTLY** | draft_id/crew/pairing/ts/notified_ts/prior_status/initiator-by-program FULL from 2024-04-24; outcome partial; trigger_reason MISSING; pay only recent. |

---------------------------------------------------------------------------------------------------

## 1. Newly discovered AIMS objects (notes) and cross-cutting decoding

### 1.1 Object notes

| Object | What it is (inference unless stated) | Key / grain | Rows | Date range | How written / remarks |
|---|---|---|---|---|---|
| **LOG_ROSTER** | Row-level change journal of `ROSTER` (verified: same key columns as ROSTER + audit columns). One row per insert (`DBOPERATION=2`), delete (`4`), or field update (`3`). | `TABLELOGID` (clustered, unique). Index `(ID, LEG_DAY, LEG_DEP, LEG_CARRIER, LEG_FLT, LEG_LEGCD, DUTYNO, DUTYDAY, GRDDUTYBEG, AIMSUSER, AIMSTABLEID, AIMSFIELDID, ONDAY)`; `(ONDAY, ONMIN, ONSEC, ONMSEC)`. | 12,128,278 | ONDAY 16205 = **2024-05-14** -> 17101 = 2026-10-27 (3.06 M rows 2024, 4.92 M 2025, 4.15 M 2026) | Columns: `ONDAY, ONMIN, ONSEC, ONMSEC` (when, local), `AIMSUSER` (who), `PCID`, `AIMSTABLEID` (=19 for ROSTER), `AIMSFIELDID`, `DBOPERATION`, `DBUSER`, `EXTERNALAPPL` (**program name**), `HOST`, `DBFIELDNO` (= ROSTER `column_id`), `PRGNO/PRGOPTION` (AIMS program/option), `AIMSOPERATION`, `NEWVALUE`/`OLDVALUE` (image, **big-endian**, e.g. NOTDATE `{66,4}` = 16900). Insert/delete rows carry only the key (no values). Updates are logged only for ROSTER columns 16 REPORTTIME, 24 CWCATEG, 28 CHECK_IN, 31 NOTDATE, 32 NOTTIME, 33 REPMETHOD (+ a trigger initialising FUT* columns); POS/GRDDUTYBEG... are key or unlogged. |
| **LOG_ROSTERDT** | Same journal for `ROSTERDT`. | `TABLELOGID`; index on the ROSTERDT key + `RECTYPE`. | 17,545,053 | ONDAY 16205 (2024-05-14) -> 17101 | Insert/delete only (value changes appear as DBOPERATION 3 on `VALUE1`, DBFIELDNO 11). **VALUE1 of an inserted/deleted marker is not logged**: for a deleted draft marker the draft code is lost; for a live one read it from `ROSTERDT`. |
| **LOG** | Business-level roster change log ("old duty -> new duty") **with crew-notification fields**. | `LOG_ID`. Indexes `(ID, FORDATE, RECTYPE, FLT, DEP, LEGCD)`, `(ONDATE, ONTIME, ID, USER_)`, `(ID, ONDATE)`. | 3,125,528 | ONDATE 12918 (2015, 13 rows) ... dense from **2023-11-08** (16017); ~45 distinct users/week from 2024-03; **sick-code entries (NEW = MAL) start 2024-03-14**; to 2026-10-27 | `ONDATE/ONTIME` = when the change was made (same minute as the matching `LOG_ROSTER` row: 322/338 identical), `USER_` = who, `FORDATE` = roster day concerned, `RECTYPE` (4 = duty change, see 1.3), `OLD`/`NEW` (bigint: `<0` = `-CRCODES.ID` activity, `>0` = `CRROUTE.CROUTE`, `0` = nothing), `NOTIFIED` (0 = pending, 1 = crew notified, 2 = notification not required), `NOTUSER`, `NOTDATE`, `NOTIME` (**notification stamp**, same clock), `OLDTIME/NEWTIME` (timed activities), `FLT/DEP/LEGCD/CRSDAY` (flight-level rectypes). A replacement is **two rows**: a removal (OLD=x, NEW=0) and an addition (OLD=0, NEW=y) with the same `(ID, FORDATE, ONDATE, ONTIME)`. A multi-day pairing produces one row per roster day (`FORDATE`), `NEW` = `CROUTE` (matches `CRROUTE` with `CDATE = pairing start day`). |
| **PROSTER / PROSTERDT / PROSTERID** | **Published roster**: same layout as ROSTER / ROSTERDT / ROSTERID. Snapshot of the roster as it stood when published (rolling horizon, ROSTERID.PUBLISH = 2026-12-01 for 2,823 crew). Differences with ROSTER grow with the age of the day: share of PROSTER rows missing from ROSTER = 8/846 (day 2026-12-01), 35/2,404 (+22 d), 96/2,445 (today), 378/2,227 (-3 d), 720/2,171 (-68 d). Jan 2026: 20,280 rows only in PROSTER, 22,411 only in ROSTER, of ~76k. (Exact snapshot instant: inference "when first published, ~28 d ahead".) | same key as ROSTER (+RECTYPE for DT) | PROSTER 3,417,013; PROSTERDT 5,392,437; PROSTERID 6,115 | LEG_DAY 15695 = **2022-12-21** -> 17136 (22k rows 2022, 844k 2023, 894k 2024, 873k 2025, 784k 2026) | Written by the publish function; read-only for planners. Gives "roster before the absence / before the draft / before the call-out" for 36+ months. |
| **PUSHNOTIF** | Mobile-app push notifications to crew, linked 1:1 to `LOG.LOG_ID` (40,809/40,809 sampled rows join; `USERID = LOG.ID` for all). | no unique key seen | 296,017 | CDATE 16272 = 2024-07-20 -> 17101 | `CDATE/CTIME` created, `SDATE/STIME` sent (set on 54 %), `STATUS` 1 sent / -1 failed, `ACK` never true (0 acknowledged). 2,532 users, ~15k rows/month. PAYLOAD not read. Optional "push sent" timestamp only. |
| **CRWCHNGS** | Flight-level "crew changed on this flight" event queue (no crew column; 161-byte blob not read). | `CRWCHNGS_ID`; `(DAY, CARRIER, FLT, LEGCD, DEP, EVENTDATE, EVENTTIME...)` | 1,348,593 | EVENTDATE 16082 = 2024-01-12 -> 17101 | ~35-50k events / 30 days on ~5-6k flights. Can count last-minute crew changes per flight, cannot name crew. |
| **MSTLOGCRW** | Master-data (crew master, qualifications, expiry recalcs...) change log, `FORKEYINFO` binary(32) = crew key, `AIMSTABLEID`, `NEWVALUE` only. 260,086,155 rows; first rows 2024-06-01; dominated by AIMSTABLEID 51 (240k rows in 3 days). **Not a roster event source**; touched only with `TABLELOGID` ranges. |
| **MSTLOGLEAVE / MSTLOGMISC / MSTLOGTRN** | Same pattern (leave entitlement balances, misc master data, training); 502k / 119k / 38k rows; 2024-05..2026-10. Leave table 165 = `LEAVE` entitlement (see below). | |
| **LEAVE / LEAVEDESC** | Leave entitlement balances per crew x year x category (annual entitlement, carry-forward, taken, booked); 56,903 rows, years 2009-2027. **No sick bank / absence events.** | | | | |
| **TRIPSWAP / TRIPIDX** | Trip-swap *request board* (crew posts days to give / take; `WITHTYPE_` 6 and 11 = 5.7k + 15k rows per year; `EXACT_TIME_` = ms of day of posting) and match index. Requests, **not executed swaps** (executed swaps are PAIRING -> PAIRING rows in LOG/LOG_ROSTER). 129,402 / 44,596 rows, 2012-2026. | | | | Partial source for a "voluntary swap" flag only. |
| **ALERTCRW / IRREGROSTER / IRREGALERT** | Rule-violation / irregularity alert state: 18 `ALERTTYPE`s, current alerts only (ALERTCRW: ~6.5k rows, FORDAY >= 17073 = 2026-09-29; IRREGALERT 1.12 M rows without timestamps, `EXPCHECKINDATETIME` all 0). **No history, no absence/draft semantics.** | | | | |
| **DutyReq** | Duty-request records (`MODE_` 1, 50, 60, 80; `RECDATE` = days since 0001-01-01, `RECTIME` ms); 166,209 rows 2008-2026 (2025: 11.6k + 3.4k + 73 + 161). `FOR_ID <> ID` for all recent rows. Semantics undecoded (blob 540 bytes not read). **UNKNOWN**; not used. | | | | |
| **Crewmsg / MCREW3 / CREWMSGTYPE** | Crew messages. Crewmsg 7.2 M rows (41,642 with STARTDAY in Jan 2026; `RECDATE/RECTIME` stamp; blob 22 bytes), MCREW3 6.2 M rows (~2 M/yr, only from Q4-2023). **Count-only use**: present on 27 % of drafted crew-days vs 79 % of ordinary flying crew-days (Crewmsg) and 99 % vs 49 % (MCREW3). Not a call log; no content read. `CREWMSGTYPE`: one named type, "open bid / vols hors programme". |
| **CRWCMPL / CNGRSN** | `CRWCMPL` (67 rows) = screen colour/font settings, `CNGRSN` (32 rows) = change-reason table **with empty text**: no change-reason catalogue exists. | | | | |
| **HISTVER / PUBLVER / HISTCROU / PUBLCROU** | Pairing version history (`HISTVER.ONDAY` 2023-11-08 -> 2026-10-27) and published pairing versions (2022-12-20 -> 2026-12-01). Pairing-level, not crew-level; context only. | | | | |
| **TIMEPNCPNT** | Timesheet working table (355,053 rows, LEG_DAY 16948 = 2026-05-27 -> 17081 = 2026-10-07, 18,331 runs): per leg `CHV`, `T_1_5`, `T_2`, `T_1_4`, ... pay buckets. Only the latest pay runs. | | | | See 7. |
| **USER_ / USERGROU** | 1,044 users; `USERGROU` lists 33 named groups (SOCC, Crew scheduler (BADE), Crew planning, Chef de File, DISPATCH, DCC, Network Controller, Pilot Ops, Union, Leave Management...). Group membership is inside `USER_.DATA_BEGIN_END` (not decoded: the table also holds password/name columns; only the lookup `USERGROU` was read). | | | | Needed to map user -> IOC / planner / crew; **open item**. |

### 1.2 `LOG_ROSTER` writers (column `EXTERNALAPPL`, Jan 2026 sample; inference on meaning)

| Program | `PRGNO` | Pairing-add events, ONDAY 2026-01 (all crew; distinct crew x pairing x minute) / of which with a matching `LOG` add-row | Reading |
|---|---|---|---|
| `ScheUpd.EXE` | 1202 | 4,661 / 2,166 | AIMS scheduling update module used by crew schedulers / planners; also writes most sick-code entries (2,664 + 631 + ... of ~4.9k in 60 days) |
| `GRAFSCHE.EXE` | 1210 | 25 / 18 (but 1,255 sick-code entries in 60 days) | graphical scheduler (sick-code entries by schedulers) |
| `MOVEMENT.EXE` | 1300 | 1,236 / **1** | Movement control (IOC / SOCC): last-minute assignments, draft markers, RT109 flags. **Not written to `LOG`.** |
| `OPBIDP.exe` | 180000 | 389 / 383 | open-bid processing (voluntary pick-ups); writes day-level `ROSTERDT RECTYPE 21 VALUE1 = 11` (738 live rows in Jan 2026) |
| `PBSEXPR.exe` | 180000 | ~9,000 crew-pairings (38,747 flight rows in 2 months) | bid-line (PBS) award export: bulk monthly build, not an event |
| `RRMAIN.EXE` | 1304 | 375 / 3 | unknown rostering function (small) |
| `HOTAUTO.EXE`, `HOTACUPD.EXE` | 2302, 120702 | ~820 / ~60 | hotel automation (not crew events) |
| `.Net SqlClient Data Provider` | various / negative | 2,074 / 484 | SQL-level writers (integration, web/app); also writes `ROSTER.REPMETHOD` and ROSTERDT RT 15/16/123 in bulk |

### 1.3 `LOG.RECTYPE` (Jan 2026 sample of 25,714 rows / 15 days; inference)
`4` = roster duty change (89 % of rows; OLD/NEW = activity or pairing; the one used below); `23` = flight-level change (FLT set); `10` = activity code swap with times; `5` = pairing change with flight and times; `2` = pairing assignment with times; `9` = pairing removal with date; `16`, `8`, `6`, `1`, `15`, `7` rare, undecoded. Only RECTYPE 4 is used in this file.

### 1.4 Time zone and resolution
`ONDAY` (day number), `ONMIN` (0..1439), `ONSEC`, `ONMSEC`. Evidence that this is **local wall-clock**: `ScheUpd.EXE` inserts/deletes by hour of `ONMIN` form a working-day shape 07-16 h (peak 09-11) in both January and July (a UTC clock would shift by one hour between EST and EDT and peak 13-21 h); the server runs at UTC-5 (GETDATE 12:14 / GETUTCDATE 17:14). `ROSTER.NOTTIME` = `ONMIN` of the same event (verified on field-1896 updates: `NEWVALUE` equals `ONMIN`). Consequences: (a) convert with a DST-aware Montreal rule; (b) the 01:00-02:00 hour of the fall-back night is ambiguous - use `TABLELOGID` order to disambiguate; (c) Pierre's v3 `notification_ts`/`call_ts`/`change_ts` are described as UTC: verify what he did (his D4 hour-of-day profile peaks 08-10 h, trough 01-04 h).

### 1.5 How things are recorded (decoded facts)
* **Sick call / absence** = activity row in `ROSTER` with `LEG_FLT = DUTYNO = CRCODES.ID` of a sick code (`MAL` -17 = "MALADIE - SICK", `MAL4` -344, `MALO` -300 overtime, `MHB` -147, `MOL` -42, `N/DM` -84 "non disponible maladie", `MARH` -251 "maladie RH", `MAL1` -80, `INV` -117 invalidity, `MFIT` -87 "fit from maladie" = return state, `RETP` -16 preventive withdrawal, `CPP5` -364 personal paid day (PNT)). The planner action is journalled as: **delete** of the previous element(s) of that crew-day (20-day sample of deletes within 2 min of a `MAL` insert: pairing flight rows 384, `N/DM` 204, `REA1` 130, `RAM` 118, `CON` 117, `RPM` 84, `MAL` 76, `CONG` 74, `AM` 8, ...) and **insert** of the sick row, in the same minute (3-day sample: 47 of 218 `MAL` inserts within 2 min of a pairing delete, 116 with no pairing delete near). About 80 % of the sick-code entries are made 0-1 days ahead of the day concerned (`ScheUpd.EXE` 2,664 + `GRAFSCHE.EXE` 1,255 of ~4.9k in 60 days).
* **Reserve** = timed activity row `AM`(-160) / `PM`(-412) / `AM0`,`PM0` (zero credit) / `XAM`(-66) `XPM`(-67) (discontinued 2026-01-06 -> AM/PM) = short call (SC); `LCR`(-194, effective 2026-03-01) = long call (LC); `REA1`(-348) "reaffectation"; cabin `RAM`/`RPM`. **Reserve rows carry the window**: `GRDDUTYBEG/GRDDUTYEND` are set (AM begin 480..1321, PM 1080..1386, LCR 540..1425 UTC minutes of `LEG_DAY`; 100 % timed for pilots).
* **Call-out** = the reserve row is deleted and flight rows of a pairing are inserted for the same crew-day in the same minute (10-day sample, 2026-03: RAM -> flight 282, RPM -> flight 160, LCR -> flight 60, AM -> flight 19, PM -> flight 8; the same reserve codes are also replaced by sick codes, `CON`, `CSS`, ...). `LOG` has the pair with `NOTDATE/NOTIME`.
* **Draft** = pairing assignment + `ROSTERDT RECTYPE 21` marker (VALUE1 15/16/19/20, see `drafts.md`). Marker created by `ScheUpd.EXE` (> 90 %), `MOVEMENT.EXE`, `GRAFSCHE.EXE`, `RRMAIN.EXE`.
* **Crew notified** = `LOG.NOTIFIED = 1` with `NOTDATE/NOTIME` (set on every `NOTIFIED=1` row; `NOTIFIED = 2`, 10,139 of 25.7k rows, = outside the notice window, > 7 days ahead, no stamp), mirrored on the `ROSTER` row (`NOTDATE/NOTTIME`, `USER_`).

---------------------------------------------------------------------------------------------------

## 2. v3 CSV profile (aggregates only)

| File | Rows | Period | Key facts |
|---|---|---|---|
| d4_absences | 5,816 | start 2024-04-24 .. 2026-08-31 | SICK 5,669 / FAMILY 143 / INJURY 4; YUL 3,704 / YYZ 2,112; FO 3,137 / CA 2,679; notification_ts empty 824; `notification_source`: JOURNAL_RETRAIT_ROTATION 4,517 / JOURNAL_RETRAIT_PROCHE 475 / AUCUNE_ROTATION_A_RETIRER 650 / INTROUVABLE 174; `affected_pairing_id` empty 1,145; timestamps `YYYY-MM-DDTHH:MM` (minute resolution); 57 absences > 60 days (max 779). |
| d5_reserve_callouts | 27,348 | reserve_date 2024-04-24 .. 2026-08-31 | outcome `not_called` 23,112 / `assigned` 4,236; SC 24,719, LC 2,629 (**LC only from 2026-03**); extra columns `reserve_date`, `reserve_call_type`, `fleet_detail`; 1 row per (crew, reserve_date); 456 crew; `call_ts/report_ts` only for assigned. |
| d6_schedule_changes | 93,599 | 2024-04-24 .. 2026-08-31 | reasons ROSTER_CHANGE 56,318 / CASCADE_UNCOVERED 18,697 / DRAFT 7,006 / SHORT_NOTICE_COVER 6,985 / RESERVE_CALLOUT 4,593; initiator IOC for 100 %; `new_block_type` PAIRING or OPEN only; old types DAY_OFF 24,236, PAIRING 64,172 (45,475 -> PAIRING + 18,697 -> OPEN), RESERVE 4,689, others < 160; 756 crew; ROSTER_CHANGE `change_ts` clusters at 08:xx (30,871 rows in hour 8). |

---------------------------------------------------------------------------------------------------

## 3. Shared derivations (used by all four deliverables)

| Item | Derivation (verified unless noted) |
|---|---|
| `crew_id` | `ROSTER.ID` (int) -> opaque `P######`. **The pseudonymisation key is outside AIMS**: the v3 mapping cannot be reproduced; one stable salted hash must be applied to all datasets (D1/D2/D4/D5/D6/drafts). |
| Pilot filter / `position` | `ROSTER.POS`: 1 = CM -> `CA`, 2 = PO -> `FO` (4 = SP also PNT). |
| `base` | `CREWQUAL.CWBASE` active on the day (`ACTIVBEG <= day <= ACTIVEND`, TOP 1 ordered by `ACTIVBEG DESC`, because qualifications overlap). Tested on 373/373 Jan-2026 drafts: 100 % resolved. |
| `fleet` | `CREWQUAL.AC` (-> `AIRCTYPE.IATACODE`): 14/16 = A321 family, 4/6 = A330 family (see `ROSTER.md`). For events tied to a flight, `ROSTER.AC` of the leg is more precise. A321neoLR is not distinguishable by AIMS fleet type alone (same issue as v3 point 8). |
| `pairing_id` | `RTRIM(CRROUTE.DESC_) + '_' + yyyymmdd(DATEADD(DAY, CRROUTE.CDATE, '1980-01-01'))` with `CDATE = ROSTER.DUTYDAY`, `CROUTE = ROSTER.DUTYNO` (all 373 drafted pairings of Jan 2026 resolved). |
| local -> UTC | `DATEADD(MINUTE, ONDAY*1440 + ONMIN, '1980-01-01')` is **local** time; convert with `AT TIME ZONE 'Eastern Standard Time'` (DST-aware) to UTC. |
| Absence/reserve classes | `CRCODES.CC`; reserve = codes above; leave/sick/etc. by `CRCODES` flag bytes (see `CRCODES.md`). |

---------------------------------------------------------------------------------------------------

## 4. D4 `d4_absences`

### 4.1 Mapping

| corpus column | status | AIMS source | transformation | evidence | gap / risk |
|---|---|---|---|---|---|
| `absence_id` | DERIVABLE | none (surrogate) | `A` + sequence, or hash of (crew, start, first sick code) | AIMS has no absence key | must be stable across re-extractions: use hash, not a counter |
| `crew_id` | DERIVABLE | `ROSTER.ID` | pseudonymise (section 3) | 100 % | key outside AIMS |
| `notification_ts` | DERIVABLE (>= 2024-03-14) / PARTIAL (before) | 1st choice `LOG` (RECTYPE 4, `NEW` = sick code, `OLD = 0`): `ONDATE/ONTIME` = entry time, `NOTDATE/NOTIME` = crew-notified stamp. 2nd `LOG_ROSTER` insert of the sick row (`DBOPERATION=2`, `LEG_FLT = -code`): `ONDAY/ONMIN` (2024-05-14 ->). 3rd `ROSTER.NOTDATE/NOTTIME` of the first sick row (permanent, last-touch). | local -> UTC; take the **earliest** insert of the first day of the run | run starts with a LOG row: 151/151 (2024-04-24..05-31), 137/137 (2024-06), 149/149 (2025-03), 145/145 (2026-01); with a `LOG_ROSTER` insert: 70/151, 137/137, 149/149, 145/145; `ROSTER.NOTDATE` set 100 %, equal to the journal stamp 144/145 | semantics = time the **planner recorded** the absence (+ stamp when the crew was flagged notified, within 5 min of entry for 96 %), not the moment the pilot phoned in; before 2024-03-14 only the last-touch approximation. Retro entries exist (2.5 % of sick rows have `NOTDATE > LEG_DAY+1`): not an error. |
| `absence_start` | DERIVABLE | `ROSTER` rows with `LEG_FLT = DUTYNO = -(sick code id)` | first `LEG_DAY` of a run of consecutive days (no row of the same class on `LEG_DAY-1`) -> date | 145-146 MAL run starts for pilots in Jan 2026 (74 CM + 72 FO by `ROSTER.POS`) | run-merge rule across different sick codes (MAL then MFIT/N/DM/INV) must be fixed with Pierre |
| `absence_end` | DERIVABLE | same | last day of the run | | long sick leave is planned far ahead in ROSTER (INV/MARH up to 2028): cap at extraction date |
| `duration_days` | DERIVABLE | | `absence_end - absence_start + 1` | v3 min 1, median 2, max 779 | cap as above |
| `absence_type` | PARTIAL | `CRCODES.CC` of the run | map code -> SICK/FAMILY/INJURY | v3 Jan 2026 (YUL/YYZ, 222 rows): SICK 215 + FAMILY 7; AIMS pilot run starts Jan 2026: `MAL` 146, `CPP5` 44, `INV` 3, `MALO` 1, `NSHW` 6, `PAT/PAT1` 4, `MFIT` 182 (return state) | **Pierre's code list is unknown.** Observed: his SICK (215 in Jan 2026) is of the order of `MAL` (146) + `CPP5` (44) + small codes; FAMILY (4-10 per month) cannot be `CPP5` (44 per month) - candidates such as `JUP1`, `DENP`, `PAT1`, `CPNP` are unverified guesses. The 57 absences > 60 days must be long codes (INV / MARH / ...), not sick calls (inference). Needs the code list. |
| `affected_pairing_id` | DERIVABLE | `PROSTER` (published) element of the crew on the absence days: first pairing of the run; else the journalled removed pairing | `pairing_id` (section 3) | Jan 2026 pilot run starts: published state on first day = pairing 107 / reserve 13 / day off 1 / other 2 / nothing 28 (of 151) ; v3 has a pairing for 80 % | answers Pierre3 "only 12/4,671 pairings found in D2": the final ROSTER no longer has the pairing, `PROSTER` does (2022-12-21 ->). Rule for multi-day absences ("first affected pairing" vs all) to confirm. |
| `base` | DERIVABLE | `CREWQUAL.CWBASE` | section 3 | | |
| `fleet` | DERIVABLE | `CREWQUAL.AC` | section 3 | | neoLR issue |
| `position` | DERIVABLE | `ROSTER.POS` | 1 -> CA, 2 -> FO | | |
| *optional* `notification_source` | DERIVABLE (own vocabulary) | which source supplied `notification_ts` | proposed: `LOG_ENTRY`, `LOG_ROSTER_ENTRY`, `ROSTER_NOTDATE_APPROX`, `NONE` | | Pierre's current values (`JOURNAL_RETRAIT_*`, `AUCUNE_ROTATION_A_RETIRER`, `INTROUVABLE`) describe a *pairing-removal* heuristic that is no longer needed |

### 4.2 Tested SQL (Jan 2026 = LEG_DAY 16802..16832)

```sql
-- pilot MAL (-17) run starts, journal coverage and stamp equality (executed: 145 / 145 / 144 / 145)
WITH s AS (SELECT r.ID, r.LEG_DAY, r.NOTDATE, r.NOTTIME FROM TSC.dbo.ROSTER r
           WHERE r.LEG_DAY BETWEEN 16802 AND 16832 AND r.LEG_FLT=-17 AND r.DUTYNO=-17 AND r.POS IN (1,2)
             AND NOT EXISTS (SELECT 1 FROM TSC.dbo.ROSTER p WHERE p.ID=r.ID AND p.LEG_DAY=r.LEG_DAY-1 AND p.LEG_FLT=-17)),
t AS (SELECT s.*,
        (SELECT COUNT(*) FROM TSC.dbo.LOG_ROSTER l WHERE l.ID=s.ID AND l.LEG_DAY=s.LEG_DAY AND l.LEG_FLT=-17 AND l.DBOPERATION=2) a,
        (SELECT COUNT(*) FROM TSC.dbo.LOG_ROSTER l WHERE l.ID=s.ID AND l.LEG_DAY=s.LEG_DAY AND l.LEG_FLT=-17 AND l.DBOPERATION=2
                 AND l.ONDAY=s.NOTDATE AND l.ONMIN=s.NOTTIME) b FROM s)
SELECT COUNT(*) run_starts, SUM(CASE WHEN a>0 THEN 1 ELSE 0 END) with_insert_log,
       SUM(CASE WHEN b>0 THEN 1 ELSE 0 END) notstamp_equals_log, SUM(CASE WHEN NOTDATE>0 THEN 1 ELSE 0 END) notdate_set FROM t;
```
Business-log variant (covers 2024-03-14 ->; the entry stamp and the crew-notified stamp):
```sql
SELECT l.ID, l.FORDATE, l.ONDATE, l.ONTIME, l.NOTIFIED, l.NOTDATE, l.NOTIME
FROM TSC.dbo.LOG l
WHERE l.RECTYPE=4 AND l.OLD=0 AND l.NEW=-17 AND l.ONDATE BETWEEN 16802 AND 16832;   -- earliest per (ID, run start FORDATE)
```
Pre-journal fallback: `ROSTER.NOTDATE/NOTTIME` of the first sick row (populated on 3,289 / 3,581 / 3,905 / 3,086 of the same number of pilot MAL rows in the four 365-day blocks from LEG_DAY 15700 to 17100; `NOTDATE <= LEG_DAY+1` for 97 %).

### 4.3 History depth
* Sick run reconstruction: `ROSTER` 1999-01-08 -> (final state). Pilot MAL rows exist for every year checked (3.1k-3.9k per 365-day block since 2022-12).
* Timestamp: `LOG` from **2024-03-14** (practically no sick-code row before: 0 in 2024-01-30..02-26, 5 in 02-27..03-13, then 74 on 03-14), `LOG_ROSTER` from **2024-05-14**, `ROSTER.NOTDATE` always (approximate). The 2023-08 -> 2024-03-13 stretch has only the approximate stamp (about 7 months of the 36-month target).
* Published roster before the absence (`affected_pairing_id`): `PROSTER` from 2022-12-21 (covers 2023-08).

### 4.4 Comparison with v3
* v3 monthly counts (144-267 per month) are of the same order as pilot `MAL` run starts (146 in Jan 2026 vs 222 in v3 incl. FAMILY and other codes) - the missing ~75 are other sick-like codes in Pierre's list.
* v3 hour-of-day of `notification_ts` (peak 08-10 h = 1,197 of 4,992 stamps, trough 01-04 h) differs from the AIMS **sick-code entry** hour (pilots, Jan-Mar 2026: peak 18-20 h local = 642 of 1,332 inserts, secondary 07-12 h): v3 `JOURNAL_RETRAIT_ROTATION` (4,517 rows) is, by its name, the time the **pairing was removed** (inference), which in AIMS is only the same minute as the sick-code entry in about 1 case in 5 (47 of 218). So the v3 `notification_ts` is a different event than the entry time. For `JOURNAL_RETRAIT_PROCHE` (475) the lead vs absence start has median +54 h, max +336 h, min -2,545 h: unreliable.
* v3 `INTROUVABLE`: 40 (Apr-24) + 100 (May-24) + 34 later; v3 `AUCUNE`: 650 spread evenly (12-36 per month).

### 4.5 Pierre3 point 4 - evaluation
1. **Why 824 empty (14 %)?** `INTROUVABLE` (174): 140 fall in 2024-04-24..05-31, the weeks before the retention start of the row journal that his procedure evidently reads (`LOG_ROSTER`-type, first row 2024-05-14); only the remaining 34 are unexplained (probably runs that start on a day whose sick code was not the first insert or were entered via another route). `AUCUNE_ROTATION_A_RETIRER` (650): the pilot had no pairing to remove (day off, reserve, empty day), so a "pairing-removal" search finds nothing, but the **sick-code insert** is journalled anyway (145/145).
2. **Can AIMS give a real timestamp for every absence?** Yes **for every absence starting on or after 2024-03-14** (journal `LOG`: 151/151, 137/137, 149/149, 145/145 run starts in the four windows tested; `NOTIFIED=1` with a stamp for 99 % of sick entries, stamp within 5 min of the entry for 96 %; 8,027 sick-code additions 2026-01..03). For 2023-08 -> 2024-03-13 only `ROSTER.NOTDATE/NOTTIME` (last touch). "Real" = moment the absence was *entered in AIMS* (and flagged notified); AIMS cannot know when the pilot actually called.
3. **65 rows with notification after the first day:** consistent with AIMS (2.5 % of sick rows have `NOTDATE > LEG_DAY + 1`; late data entry). Keep, flag `retro`.
4. **Affected pairing missing for 20 %:** `PROSTER` gives the published pairing for 107 of 151 first days (71 %) plus later days of the run; the rest had reserve / day off / nothing published.
5. Recommended: take `notification_ts = min(LOG.ONDATE/ONTIME of the sick insert)`, fall back to `LOG_ROSTER`, then `ROSTER.NOTDATE`; emit `notification_source` accordingly; stop using pairing-removal time.

### 4.6 Verdict D4: **MOSTLY**
All columns except `absence_type` are derivable from AIMS; the notification timestamp is a real journal timestamp for 100 % of the absences in the v3 window (>= 2024-04-24) and an approximation for 2023-08..2024-03-13. Missing/needed, in order: (1) Pierre's CRCODES list for SICK / FAMILY / INJURY and the run-merge rule; (2) which event he calls "notification" (entry vs pairing removal vs call); (3) the pseudonymisation key; (4) time-zone convention of v3; (5) for 2023-08..2024-03 accept approximate timestamps.

---------------------------------------------------------------------------------------------------

## 5. D5 `d5_reserve_callouts`

### 5.1 Key discovery
v3 D5 = one row per (pilot, reserve day) taken from the **published** roster, plus assignment info. Verified by month: v3 rows == `PROSTER` pilot reserve rows (`POS IN (1,2)`, `LEG_FLT IN (-66,-67,-160,-412,-194,-388,-389)`, i.e. XAM XPM AM PM LCR AM0 PM0; `REA1` excluded):

| month | v3 D5 rows | PROSTER pilot reserve rows | | month | v3 D5 rows | PROSTER |
|---|---|---|---|---|---|---|
| 2024-05 | 1,015 | 1,015 | | 2025-12 | 892 | 892 |
| 2024-06 | 785 | 785 | | 2026-01 | 870 | 870 |
| 2024-11 | 1,494 | 1,494 | | 2026-02 | 529 | 529 |
| 2025-03 | 1,194 | 1,194 | | 2026-03 | 686 (452 LC) | 686 (452 LCR + 234 SC) |
| 2025-09 | 1,209 | 1,209 | | 2026-08 | 750 (531 LC) | 750 (531 LCR + 219 SC) |
(all other months equal within +-2; April 2024: v3 57 = the 7 days from 04-24.) Note: PROSTER has 2023-01 .. 2024-03 rows too (1,000-1,800 per month), so the same file can be produced for 2023-08 onward.
v3 `assigned` share (17-20 %) ~ AIMS "pairing **starts** on the reserve day" (2025-03: 187 of 1,194 = 15.7 % vs v3 197); AIMS "any flight now on that day" = 297 (24.9 %), the extra 110 being days inside a pairing that started earlier.

### 5.2 Mapping

| corpus column | status | AIMS source | transformation | evidence | gap / risk |
|---|---|---|---|---|---|
| `callout_id` | DERIVABLE | none | surrogate (hash of crew + reserve day) | | |
| `crew_id` | DERIVABLE | `PROSTER.ID` | pseudonymise | | |
| `call_ts` | DERIVABLE for `assigned` (2024-03-14 ->), PARTIAL before | `LOG` add row (RECTYPE 4, `OLD = 0`, `NEW = CROUTE`, `FORDATE = pairing start`) paired with the removal row of the reserve code (same ID/FORDATE/ONDATE, \|dONTIME\| <= 2): `ONDATE/ONTIME`; crew-notified stamp `NOTDATE/NOTIME`; alt. `LOG_ROSTER` flight inserts (2024-05-14 ->); pre-journal `ROSTER.NOTDATE/NOTTIME` of the flight row | local -> UTC; NULL for `not_called` (as v3) | 2025-03: 185 of 187 call-outs (98.9 %) have a LOG row and a notification stamp (184 on the same day); 2023-10: 162 call-outs, 141 (87 %) with plausible `NOTDATE` (0-3 days before) | `LOG` rows written by IOC (`MOVEMENT.EXE`) are missing (only `LOG_ROSTER`); notification stamp = recording time (96 % within 5 min), not phone-call time |
| `report_ts` | DERIVABLE | first flight of the pairing for that crew: `LEGMAIN.STD` (UTC minutes of `LEG_DAY`) minus report offset (default 60; `ROSTER.REPORTTIME > 0` override; -80 overseas PNC; rules in `ROSTER.md`/R3) | UTC | tested call-out notice (report approx = STD-60 vs `LOG` entry, EST) Jan-Mar 2026 pilots: `LCR` n=103 notice avg 29.5 h (min 6.1, max 92.1), `AM` n=29 avg 5.3 h (0.1-15.7), `PM` n=7 avg 7.4 h (3.4-22.1), `XAM` n=74/20 avg 5.6 / 3.3 h, `XPM` n=48 avg 11 h, `REA1` n=23-30 avg 18-32 h | v3 has 238 rows with `report_ts < call_ts` and 217 with gap > 72 h: most likely v3 join defects (e.g. a later re-stamp used as call time); with first-insert logic notice is >= -3.9 h (a call after the nominal report time exists for XAM, min -3.9 h) |
| `assigned_pairing_id` | DERIVABLE | pairing of the call-out (`CROUTE`/`CDATE`) | section 3 | v3 empty for 89 of 4,236 assigned | |
| `outcome` | PARTIAL | `PROSTER` reserve row vs **current** `ROSTER` on the same crew-day | see 5.3 | | `declined`/`no-show` rare; `released` is an inference |
| `base`, `fleet` | DERIVABLE | `CREWQUAL` / `ROSTER.AC` | section 3 | v3 base YUL 14,361 / YYZ 12,987 | |
| extra v3 cols `reserve_date`, `reserve_call_type` | DIRECT / DERIVABLE | `PROSTER.LEG_DAY`; SC = XAM XPM AM PM AM0 PM0 (and RAM/RPM for cabin), **LC = `LCR` only (exists from 2026-03-01; before that all reserves are SC, exactly as in v3)** | | v3 LC rows start 2026-03 (452, 411, 382, 412, 441, 531) = PROSTER `LCR` counts (452, 411, 382, 413, 441, 531) | pre-2026-03 "long call" does not exist as a code: CrewSim's LC calibration has only 6 months |

### 5.3 Outcome derivation (2025: ~13.6 k published pilot reserve days (sum of the monthly counts 13,589); current ROSTER state of the same crew-day; shares approximate)

| current ROSTER state | rows | share | proposed outcome |
|---|---|---|---|
| still XAM/XPM (reserve kept) | 7,022 | ~52 % | `not_called` |
| flight(s) | 3,533 | ~26 % | `assigned` (pairing starts that day) / continuation |
| no ROSTER row any more | 975 | ~7 % | `released` (inference) |
| `PM0`/`AM0` (zero-credit reserve) | 455 | ~3 % | `released` / no-credit (inference, code name "0 credits") |
| `CON/CONR/WFLY` day-off conversions | ~430 | ~3 % | `released` (inference) |
| `MAL`, `MFIT`, `INV`, `CPP5`, `FIT1` ... | ~870 | ~6 % | absence (sick / leave) - cross-link with D4 |
| `NSHW` 12, `SHOW` 7, `REFU`/`RFU1`/`NSHP`/`RAFP`/`LATE` (not in the 30 largest states) | ~20 | < 0.3 % | `no-show` / `declined` |

Codes: `REFU` (-89 "REFUS DE VOL") 26 rows 2025 / 37 in 2026 (2 pilots in 2025-26), `RFU1` (-398), `NSHW` (-88) 356 / 217 (46 pilots), `NSHP` (-85 "NO SHOW PILOTE") 15, `RAFP` (-195), `LATE` (-252), `SHOW`/`SHW1`/`SHWP`. So v3's "outcomes only assigned/not_called" is close to the truth for **pilots**; declined/no-show exist but are ~0.4 % of reserve days. "Released" is not an AIMS state: it can only be inferred as row removed/converted. Business must say whether AM0/PM0 means "released" or "used with zero credit".

### 5.4 Tested SQL (2025-03 = LEG_DAY 16496..16526)
```sql
WITH p AS (SELECT ID, LEG_DAY FROM TSC.dbo.PROSTER
           WHERE LEG_DAY BETWEEN 16496 AND 16526 AND LEG_FLT IN (-66,-67,-160,-412,-194,-388,-389) AND POS IN (1,2)),
q AS (SELECT p.*,
        CASE WHEN EXISTS (SELECT 1 FROM TSC.dbo.ROSTER r WHERE r.ID=p.ID AND r.LEG_DAY=p.LEG_DAY AND r.LEG_FLT>=0) THEN 1 ELSE 0 END any_flight,
        CASE WHEN EXISTS (SELECT 1 FROM TSC.dbo.ROSTER r WHERE r.ID=p.ID AND r.LEG_DAY=p.LEG_DAY AND r.DUTYDAY=p.LEG_DAY AND r.LEG_FLT>=0) THEN 1 ELSE 0 END pairing_starts FROM p)
SELECT COUNT(*) reserve_days, SUM(any_flight) any_flight, SUM(pairing_starts) pairing_starts_that_day FROM q;   -- 1194 / 297 / 187
```
Call time (call-out via journal):
```sql
-- reserve code removed + pairing added in the same minute, notice vs first leg (executed, Jan-Mar 2026)
WITH a AS (SELECT l.ID, l.NEW pairing, l.FORDATE, l.ONDATE, l.ONTIME, l.NOTDATE, l.NOTIME,
             (SELECT TOP 1 s.OLD FROM TSC.dbo.LOG s WHERE s.ID=l.ID AND s.RECTYPE=4 AND s.FORDATE=l.FORDATE AND s.ONDATE=l.ONDATE
                AND s.NEW=0 AND s.OLD<0 AND ABS(s.ONTIME-l.ONTIME)<=2 ORDER BY ABS(s.ONTIME-l.ONTIME)) prev
           FROM TSC.dbo.LOG l WHERE l.RECTYPE=4 AND l.ONDATE BETWEEN 16890 AND 16950 AND l.OLD=0 AND l.NEW>0)
SELECT RTRIM(c.CC) reserve_code, COUNT(*) n FROM a JOIN TSC.dbo.CRCODES c ON c.ID=a.prev AND c.CC IN ('AM','PM','AM0','PM0','LCR','XAM','XPM','REA1') GROUP BY RTRIM(c.CC);
```
(Result in 5.2 for notice statistics; join of the first leg `ROSTER -> LEGMAIN.STD` added.)

### 5.5 History depth
* Skeleton (`reserve_date`, crew, SC/LC, current state): `PROSTER` 2022-12-21 -> 2026-12-01 (1,000-1,800 reserve days per month for pilots) = covers 2023-08 -> 2026-08.
* `call_ts`: `LOG` 2024-03-14 ->; `LOG_ROSTER` 2024-05-14 ->; before, `ROSTER.NOTDATE/NOTTIME` of the call-out flight row (2023-10 test: 141 / 162 plausible).
* Past states of a **roster** are not stored except through PROSTER (publication-time snapshot) and by replaying `LOG_ROSTER` backwards (2024-05-14 ->).

### 5.6 Verdict D5: **MOSTLY**
Skeleton, SC/LC, pairing, call time and report time are derivable for 36 months (call time exact from 2024-03-14, approximate before). The outcome set is only partially recoverable (declined/no-show codes exist but are rare; "released" is inference); no notice-hour rule exists in AIMS (the SC/LC "notice hours" are a collective-agreement convention, not data). Needed: (1) Pierre's exact assigned definition (pairing starts on reserve day?); (2) meaning of `AM0/PM0` and removed reserve rows; (3) IOC call-outs are missing in `LOG` -> use `LOG_ROSTER` (>= 2024-05-14); (4) time-zone convention; (5) `REA1` handling (excluded by v3).

---------------------------------------------------------------------------------------------------

## 6. D6 `d6_schedule_changes`

### 6.1 Mapping

| corpus column | status | AIMS source | transformation | evidence | gap / risk |
|---|---|---|---|---|---|
| `change_id` | DERIVABLE | `LOG.LOG_ID` / `LOG_ROSTER.TABLELOGID` | surrogate | | |
| `crew_id` | DERIVABLE | `LOG.ID` / `LOG_ROSTER.ID` | pseudonymise | | |
| `change_ts` | DERIVABLE (2024-03-14 ->, dense; `LOG_ROSTER` 2024-05-14 ->) | `LOG.ONDATE/ONTIME` or `LOG_ROSTER.ONDAY/ONMIN(+ONSEC)` | local -> UTC | same-minute equality with `LOG_ROSTER` 322/338 | before 2024-03-14 no timestamp for changes except `ROSTER.NOTDATE` (last touch); `LOG` is **incomplete for IOC (MOVEMENT.EXE) and bulk (PBS/OPBIDP partly)** -> use `LOG_ROSTER` |
| `old_block_type` | DERIVABLE | `LOG.OLD` (or `LOG_ROSTER` delete row key): `>0` PAIRING; `<0` activity -> class from `CRCODES` | classes: DAY_OFF (CON, CONG, CONR, **and WFLY** - v3 places WFLY drafts under DAY_OFF), RESERVE (reserve flag / list in 1.5), VACATION (VAC*, FER*), ABSENCE (sick set), TRAINING, SIMULATOR, OFFICE, OTHER; `0` = empty day | `OLD`->class distribution in 15 days of 2026: `zero->PAIRING` 1,884, `VAC->zero` 1,690, `PAIRING->zero` 1,351, `RAM->zero` 843, `CON->WFLY` 650 ... | classification of ~250 `CRCODES` into v3's 9 classes is a mapping table to agree |
| `new_block_type` | DERIVABLE | `LOG.NEW` | `PAIRING` (`NEW>0`), `OPEN` (= pairing removed from the crew: `OLD>0, NEW=0`) in v3; other new classes exist in AIMS (v3 keeps only pairing-related) | | |
| `new_pairing_id` | DERIVABLE | `LOG.NEW = CRROUTE.CROUTE`, `CDATE` from `CRROUTE` join (`CDATE BETWEEN FORDATE-14 AND FORDATE`) | section 3 | 453 rows `FORDATE = CDATE`, 317 `+1`, 143 `+2` ... : one LOG row per pairing day; take the row where `FORDATE = CDATE` (or earliest) to get one event per pairing | for `CASCADE_UNCOVERED` v3 leaves it empty |
| `reason_code` | PARTIAL | **no reason field exists** (`CNGRSN` is empty). Rules that can be implemented: `DRAFT` = pairing added with `ROSTERDT RT21 VALUE1 IN (15,16,19,20)`; `RESERVE_CALLOUT` = previous element is a reserve code; `CASCADE_UNCOVERED` = pairing removed (`OLD>0, NEW=0`) in the same minute as a sick code entered (525 of 744 sick-code additions in a 10-day sample have a removal row in the same minute; the share that removes a pairing was not separated); `SHORT_NOTICE_COVER` = assignment from DAY_OFF/WFLY with lead <= 1 day without draft marker (heuristic); `ROSTER_CHANGE` = rest | counts: v3 DRAFT per month vs AIMS PNT draft pairings (all bases) - 2024-07: 329 vs 338; 2024-08: 422 vs 416; 2025-03: 146 vs 167; 2025-12: 280 vs 342; 2026-01: 400 vs 373; 2026-06: 506 vs 539 | The v3 `SHORT_NOTICE_COVER` vs `DRAFT` distinction (Pierre3 point 6) is **not an AIMS concept**: all four marker codes 15/16/19/20 are drafts; the other `RECTYPE 21` codes are undecoded assignment types. `VOLUNTARY_SWAP` (in the brief, absent from v3) would need `OPBIDP.exe`/TRIPSWAP evidence: 444 of ~5.4k LOG pairing adds in Jan 2026 come from `OPBIDP.exe` (bid pick-ups), 3,379 from `ScheUpd.EXE`, 724 from the `.Net` writer, 852 have no matching `LOG_ROSTER` row |
| `initiator` | PARTIAL | `LOG.USER_` / `LOG_ROSTER.AIMSUSER` + `EXTERNALAPPL`: `MOVEMENT.EXE` = Movement/IOC (inference), `ScheUpd.EXE`/`GRAFSCHE.EXE` = crew scheduling, `OPBIDP.exe` = crew open-bid, `.Net SqlClient` = system | user -> group needs `USER_.DATA_BEGIN_END` (groups SOCC, Crew scheduler (BADE), Crew planning, Chef de File, ...; not decoded) | | v3 has IOC for 100 % of rows: v3 cannot separate IOC from planners or crew; AIMS can, once user->group is supplied |

### 6.2 What D6 rows are in AIMS (Jan 2026, `LOG` RECTYPE 4, pairing adds, pilots)
790 pilot pairing-add events with a crew position known (578 from an activity code, 158 from an empty day, 54 from another pairing) + ~640 more whose pairing no longer sits on the crew's roster (later removed) = ~1.1-1.4 k; `LOG_ROSTER` pairing-add events for pilots in Jan 2026 (excluding `PBSEXPR`, which adds 1,795 pilot crew-pairings in bulk) ~1,780, ~1,570 without hotel automation (ScheUpd 1,093, MOVEMENT 235, HOTAUTO 209, .Net 134, RRMAIN 78, GRAFSCHE 17, HOTACUPD 14). v3 D6 has **5,053 rows in Jan 2026** (ROSTER_CHANGE ~60 %, with a lead of 22 days and a 08:xx timestamp peak - not an operational-change profile). The v3 definition of `ROSTER_CHANGE` (what produced 56,318 rows) cannot be matched to an AIMS event and must be explained by Pierre.

### 6.3 Tested SQL (counts)
```sql
-- pairing additions per month, business log (executed for 2024-05..2026-08, all crew)
SELECT CONVERT(char(7),DATEADD(DAY,ONDATE,'1980-01-01'),120) m,
       SUM(CASE WHEN NEW>0 AND OLD=0 THEN 1 ELSE 0 END) pairing_add_rows,
       SUM(CASE WHEN OLD>0 AND NEW=0 THEN 1 ELSE 0 END) pairing_removal_rows
FROM TSC.dbo.LOG WHERE RECTYPE=4 AND ONDATE BETWEEN 16192 AND 17044 GROUP BY CONVERT(char(7),DATEADD(DAY,ONDATE,'1980-01-01'),120);
```
Result: 2024-06 7,966 / 6,447; 2024-12 6,106 / 5,104; 2025-06 5,781 / 5,191; 2025-12 4,849 / 4,468; 2026-07 5,264 / 4,531; 2026-08 5,965 / 4,591 (adds / removals).
```sql
-- replacement pairs: removal + addition in the same minute for one crew-day
SELECT COUNT(*) FROM TSC.dbo.LOG a JOIN TSC.dbo.LOG r ON r.ID=a.ID AND r.FORDATE=a.FORDATE AND r.ONDATE=a.ONDATE
 AND r.RECTYPE=4 AND r.NEW=0 AND r.OLD<>0 AND ABS(r.ONTIME-a.ONTIME)<=2
WHERE a.RECTYPE=4 AND a.OLD=0 AND a.NEW>0 AND a.ONDATE BETWEEN 16930 AND 16939;
```

### 6.4 History depth
`LOG`: sparse 2015-2023-10, **dense 2023-11-08 -> 2026-10-27** (1.5k-28k RECTYPE-4 rows/week Nov 2023 - Feb 2024 with 4-29 users/week, 9k-24k/week from 2024-03-12 with 33-48 users); sick/reserve codes complete from 2024-03-14. `LOG_ROSTER`: 2024-05-14 -> 2026-10-27. Earlier changes only as net differences `PROSTER` vs `ROSTER` (2022-12-21 ->) without timestamps (except last-touch `NOTDATE/NOTTIME`). 36 months from 2023-08 are therefore **not** recoverable with true timestamps for 2023-08..2024-03-13.

### 6.5 Pierre's irregular volumes (Pierre3 point 6)
v3 has 992-1,665 rows in Jun-24 (1,418), Dec-24 (1,431), Jun-25 (992), Dec-25 (1,521), Jul-26 (1,489), Aug-26 (1,665) against 2,600-5,000 elsewhere. The AIMS business log shows **no such dips** (pairing adds 4,849-8,142 every month, all crew). So those months are extraction gaps in the v3 files, not real. Re-extracting from AIMS removes them.

### 6.6 Verdict D6: **PARTIAL**
Derivable and journal-backed: who (crew), when (`change_ts`), old/new block, new pairing, number of changes per month, from 2024-03-14 (LOG) / 2024-05-14 (LOG_ROSTER). Heuristic only: `reason_code` (DRAFT via RT21 and RESERVE_CALLOUT via previous code are good; SHORT_NOTICE_COVER and ROSTER_CHANGE are definitions to agree), `initiator` (program/user based, needs the user->group list). Not recoverable: change timestamps for 2023-08..2024-03-13, any reason text. Needed: (1) definition of ROSTER_CHANGE and SHORT_NOTICE_COVER used by Pierre; (2) user -> group list (SOCC vs crew schedulers vs crew); (3) class table CRCODES -> 9 block types; (4) decision whether bulk PBS publish is excluded; (5) time zone.

---------------------------------------------------------------------------------------------------

## 7. Direct draft export (`pierre2_export_drafts_aims.md`, proposed `d12_drafts.csv`)

### 7.1 Mapping

| requested field | status | AIMS source | transformation | evidence | gap / risk |
|---|---|---|---|---|---|
| `draft_id` | DERIVABLE | `LOG_ROSTERDT.TABLELOGID` of the RT21 insert (2024-05-14 ->), else hash(crew, `DUTYNO`, `DUTYDAY`) | | | one draft = one (crew, pairing instance), not one leg (561 PNT draft legs = 373 crew-pairings in Jan 2026) |
| `crew_id` | DERIVABLE | `ROSTERDT.ID` | pseudonymise | 202 crews Jan 2026 | |
| `assigned_pairing_id` | DERIVABLE | `ROSTERDT.DUTYNO/DUTYDAY` -> `CRROUTE` | section 3 | 373/373 resolved | day-level markers (`LEG_FLT=0`) have no pairing: take the pairing of the same crew-day |
| `draft_ts` | DERIVABLE (2024-03-14 ->), PARTIAL before | `LOG` add row of the pairing (`OLD=0, NEW=DUTYNO, FORDATE=DUTYDAY`): `ONDATE/ONTIME`; alt. `LOG_ROSTERDT` insert of the RT21 marker (2024-05-14 ->; 100 % in 2025-03 and 2026-06, 77/182 in 2024-05, 0 before 05-14); pre-journal `ROSTER.NOTDATE/NOTTIME` of the drafted leg | local -> UTC | Jan 2026: 370 / 373 with a LOG add-row; windows: 2024-04-24..30 56/56, 2024-05 177/182, 2025-03 166/167, 2026-06 429/450 | the 3-5 % without a LOG row are `MOVEMENT.EXE`/other writers: add the `LOG_ROSTER` path; pre-journal: 2023-10 150/158 and 2022-10 120/133 draft legs have `NOTDATE` 0-2 days before the flight |
| `notified_ts` | DERIVABLE (2024-03-14 ->) | `LOG.NOTDATE/NOTIME` of the same row; optional `PUSHNOTIF.SDATE/STIME` (2024-07-20 ->, subset) | local -> UTC | Jan 2026: 369 / 373 with a notification stamp, all within 5 min of the entry (of 414 PNT+PNC draft pairings: PNT lead from entry to pairing start = same day 140, +1 day 224, +2-3 days 4, retro 1, > 7 days 1; PNC same day 38, +1 day 2) | = time the planner flagged the pilot as notified (not acknowledged: `PUSHNOTIF.ACK` is never true) |
| `prior_status` | DERIVABLE | sibling removal row in `LOG` (same crew/day/minute, `NEW=0`) -> `CRCODES.CC`; or `PROSTER` | classes: `WFLY`, `DAY_OFF` (CON, CONG, CONR), `RESERVE_SC` (XAM XPM AM PM AM0 PM0 REA1), `RESERVE_LC` (LCR), `OTHER_PAIRING`, `EMPTY`, `OTHER:<code>` | Jan 2026, 373 PNT draft pairings (aggregate query 7.2): **WFLY 318, DAY_OFF 20, RESERVE_SC 5, other activity codes 7, other pairing / empty 23**. Same month incl. PNC (414 crew-pairings; ordering of prior element): WFLY 318, CON 34, other pairing 23, empty 16, CONG 4, XPM 3, GEN 2, REA1 2, REU6 2, VAC 2, RAM 2, FER 1, DON1 1, XAM 1, RPM 1; 4 without an add row | brief's list (DAY_OFF, RESERVE_SC, RESERVE_LC) misses the dominant `WFLY` (85 %): v3 maps it to DAY_OFF (6,135 of 7,006 DRAFT rows) |
| `initiator` | PARTIAL | `LOG_ROSTERDT` RT21 insert: `EXTERNALAPPL`, `AIMSUSER` | program/user | Jan 2026 live RT21 markers 15/16/19/20 (element + day level, 682 with a journal row): `ScheUpd.EXE` 615 (90 %), `MOVEMENT.EXE` 24, `RRMAIN.EXE` 20, `GRAFSCHE.EXE` 17, `.Net` 6 | user -> group list needed for IOC / Crew control |
| `outcome` | PARTIAL | `ROSTER` today + `LOG` later rows + codes | `accepted` = pairing still on the crew (407 / 410), `cancelled` = removal row after the add (3 / 410), `refused` = `REFU`/`RFU1`/`NSHW`/`NSHP`/`RAFP`/`LATE` code within 3 days (0 / 410) | Jan 2026, 414 PNT+PNC crew-pairings of which 410 have an add row | AIMS has no explicit "accepted"; refusal is a roster code and was 0 here |
| `trigger_reason` | MISSING | no cause field (`CNGRSN` empty); only indirect link: same-day sick codes / cancelled flights (`LEGMAIN`, D8) | | | not recoverable from AIMS |
| `base` | DERIVABLE | `CREWQUAL.CWBASE` | | 373/373 | |
| `fleet` | DERIVABLE | `ROSTER.AC` of the drafted leg (or `CREWQUAL.AC`) | | | fleet flown vs fleet qualified may differ |
| `position` | DERIVABLE | `ROSTER.POS` (19/20 -> CA 1 / FO 2) | | | |
| `credit_hours` / `pay_multiplier` | PARTIAL (recent only) | `TIMEPNCPNT` on the drafted leg key: `T_1_5`, `T_2`, `T_1_4`, `CHV`, `BLOCK_PR` | | drafted pilot legs LEG_DAY 16960..17075: 5,189 / 5,196 have a timesheet row; `T_1_5 > 0` 3,178, `T_2 > 0` 51, `T_1_4 > 0` 232, `CHV > 0` 2,228 | table only holds LEG_DAY 2026-05-27 -> 2026-10-07; mapping T_1_5 = DRAFT_THX (150 %) / T_2 = DRAFT_T2 (200 %) is inference; no history -> D7 still needed for backtest |

### 7.2 Tested SQL (Jan 2026; PNT only; executed: 373 drafts, 202 crews, 373 with pairing name, 370 with draft ts, 369 with notified ts, 373 with base; prior: WFLY 318, DAY_OFF 20, RESERVE_SC 5, other activity codes 7, other pairing / empty 23)
```sql
WITH d AS (SELECT ID, DUTYNO, DUTYDAY, MAX(VALUE1) code FROM TSC.dbo.ROSTERDT
           WHERE RECTYPE=21 AND VALUE1 IN (19,20) AND LEG_FLT>0 AND LEG_DAY BETWEEN 16802 AND 16832 GROUP BY ID, DUTYNO, DUTYDAY),
a AS (SELECT d.*, l.ONDATE, l.ONTIME, l.NOTDATE, l.NOTIME, l.NOTIFIED
      FROM d OUTER APPLY (SELECT TOP 1 * FROM TSC.dbo.LOG l WHERE l.ID=d.ID AND l.RECTYPE=4 AND l.NEW=d.DUTYNO AND l.OLD=0
                           AND l.FORDATE=d.DUTYDAY ORDER BY l.ONDATE DESC, l.ONTIME DESC) l),
p AS (SELECT a.*, (SELECT TOP 1 s.OLD FROM TSC.dbo.LOG s WHERE s.ID=a.ID AND s.RECTYPE=4 AND s.FORDATE=a.DUTYDAY AND s.ONDATE=a.ONDATE
                    AND s.NEW=0 AND s.OLD<>0 AND ABS(s.ONTIME-a.ONTIME)<=2 ORDER BY ABS(s.ONTIME-a.ONTIME)) prev FROM a)
SELECT p.ID, RTRIM(cr.DESC_) pairing, p.ONDATE draft_day, p.ONTIME draft_min, p.NOTDATE, p.NOTIME,
       CASE WHEN p.prev IS NULL THEN 'EMPTY_OR_UNKNOWN' WHEN p.prev>0 THEN 'OTHER_PAIRING' WHEN c.CC IN ('CON','CONG','CONR') THEN 'DAY_OFF'
            WHEN c.CC='WFLY' THEN 'WFLY' WHEN c.CC IN ('XAM','XPM','AM','PM','AM0','PM0','RAM','RPM','REA1') THEN 'RESERVE_SC'
            WHEN c.CC='LCR' THEN 'RESERVE_LC' ELSE 'OTHER:'+RTRIM(c.CC) END prior_status,
       (SELECT TOP 1 cq.CWBASE FROM TSC.dbo.CREWQUAL cq WHERE cq.ID=p.ID AND cq.POS IN (1,2) AND p.DUTYDAY BETWEEN cq.ACTIVBEG AND cq.ACTIVEND ORDER BY cq.ACTIVBEG DESC) base
FROM p LEFT JOIN TSC.dbo.CRROUTE cr ON cr.CDATE=p.DUTYDAY AND cr.CROUTE=p.DUTYNO LEFT JOIN TSC.dbo.CRCODES c ON c.ID=p.prev AND p.prev<0;
```
(counts executed as an aggregate version of this query; row values were not read.)

### 7.3 Volumes and history
* Marker history `ROSTERDT RT21` exists since 2018 (`drafts.md`); PNT pairing-level drafts by month of pairing start (all bases): 2024-05 182, 06 273, 07 338, 08 416, 09 341, 10 129, 11 82, 12 157, 2025-01 148, 02 199, 03 167, 04 186, 05 100, 06 191, 07 304, 08 298, 09 163, 10 115, 11 186, 12 342, 2026-01 373, 02 476, 03 480, 04 422, 05 353, 06 539, 07 462, 08 475. The v3 `DRAFT` rows per month are within about -22 % / +7 % of these (2024-07 329 vs 338, 2024-08 422 vs 416, 2025-03 146 vs 167, 2025-12 280 vs 342, 2026-01 400 vs 373, 2026-03 379 vs 480); v3 is keyed by change month and YUL/YYZ, AIMS by pairing-start month and all pilot bases, so exact agreement is not expected. The large gap in 2024-05 (35 vs 182) and 2024-06 (212 vs 273) is consistent with the v3 source journal starting mid-May 2024 (inference).
* Timestamps: `LOG` from 2024-03-14 (draft pairings Apr-24..30: 56/56), `LOG_ROSTERDT` from 2024-05-14, before that last-touch `ROSTER.NOTDATE/NOTTIME` (94-95 % plausible).
* Marker deleted later: its `VALUE1` is lost (only insert/delete journalled) -> a cancelled draft cannot be classified 15/16/19/20 retroactively.

### 7.4 Answer to Nabil's question
"Can AIMS list the assignments made by operations control on a pilot not scheduled that day?" **Yes, as a SQL extraction, without D7**: draft = `ROSTERDT RECTYPE 21 VALUE1 IN (15,16,19,20)` (the same logic as the Snowflake `DMT_DRAFTS_PNT_PNC`), enriched with `LOG`/`LOG_ROSTERDT` (timestamps, user, program, prior state) and `PROSTER`. It identifies drafts by marker, not by pay, and removes the D6 x D7 join. It cannot supply the trigger reason and gives pay data only for 2026-05-27 -> 2026-10-07 (`TIMEPNCPNT`); a minimal D7 stays useful for the V6 back-test.

### 7.5 Verdict (drafts): **MOSTLY**
FULL: crew, pairing, draft_ts (>= 2024-03-14), notified_ts, prior_status, base, position, marker type. PARTIAL: initiator (program only), outcome (accepted/cancelled by inference), pay (2026-05-27 -> 2026-10-07 only). MISSING: `trigger_reason`. Needed: user -> group, the meaning of "accepted/refused" for pilots (REFU practice), the exact notion of "draft" for the other RT21 codes (1-14, 17, 18, 21-24, 27: undecoded), the WFLY policy (is a WFLY pilot "not scheduled"?).

---------------------------------------------------------------------------------------------------

## 8. `ROSTERDT` / `ROSTER` RECTYPE decoding attempts (evidence, not conclusions)

| Object / RECTYPE | Observed | Best reading (inference) |
|---|---|---|
| `ROSTERDT 21` VALUE1 15/16/19/20 | drafts (confirmed in `drafts.md`); created by ScheUpd / MOVEMENT / GRAFSCHE / RRMAIN | draft markers |
| `ROSTERDT 21` VALUE1 **11** | 738 live **day-level** rows (Jan 2026) inserted by `OPBIDP.exe` (+ 79 flight rows by `ScheUpd.EXE`) | day-level "assigned by open-bid" |
| `ROSTERDT 21` VALUE1 **8** | 467 flight rows (Jan 2026), journalled as written by `.Net SqlClient` (automation) | system/automatic assignment |
| `ROSTERDT 21` VALUE1 **1, 2, 5** | 586 / 93 / 121 flight rows, journalled as written by `ScheUpd.EXE` (only groups >= 60 rows listed) | manual planner assignment types (1 = default) |
| `ROSTERDT 15 / 16` | PNT flights only (positions 1 and 2 equally); VALUE1 0/1; inserted in pairs by one `.Net SqlClient` user (607 + 607 inserts in 10 days) and by schedulers (33 + 31); (v15, v16) on the same element: (0,0) 1,789, (1,0) 169, (0,1) 196, (1,1) 206; 165 of 2,456 RT15 elements coincide with a PNT draft | no clear link to drafts (a bulk automatic writer creates most rows); per-leg pilot flag pair (takeoff / landing role?) - undecoded |
| `ROSTERDT 22` | PNT flights, VALUE1 = 1 (226 in Jan 2026) | per-leg pilot flag, undecoded |
| `ROSTERDT 109` | flights (PNC 12.5k, PNT 4.9k) and activities, VALUE1 0/1; **written by `MOVEMENT.EXE` (11,803 inserts / 8,615 deletes in 10 days)** | IOC per-leg crew flag (operational/notified mark), undecoded |
| `ROSTERDT 123` | flights only, VALUE1 0; 3,784 inserts + 500 updates by one `.Net` user, plus ScheUpd/MOVEMENT | automatic per-leg flag, undecoded |
| `ROSTERDT 1`, `6` | 1: activities (PNC 16.5k, PNT 3k) VALUE1 0, by ScheUpd; 6: PNT flights VALUE1 1/2/128/129 | flags, undecoded |
| `ROSTER.RECTYPE` | 128 on training/online-course codes (ANN, FAID, EPTP, DV2, EPTT, GEN, SY20, SY30, DG = R0's "movable" training codes); 4096 on `RAM` (128 rows); 16 on `TETT` | 128 = movable training; others undecoded |
| `ROSTER.REPMETHOD` | 8 on ~40 % of flight rows, 2 on 163; set by the `.Net` writer | notification channel code (8 = app/system?) undecoded |

---------------------------------------------------------------------------------------------------

## 9. Open items for the business / Pierre (ordered)

1. Code lists: which `CRCODES` make `SICK`, `FAMILY`, `INJURY` (D4); which reserve codes make SC / LC (confirm `AM0/PM0`, `REA1`); which codes count as "released".
2. Meaning of v3 `notification_ts` (entry vs pairing removal vs call) and **time zone** of all v3 timestamps.
3. Definitions of `ROSTER_CHANGE` (56k rows) and `SHORT_NOTICE_COVER` vs `DRAFT` in v3 D6; whether bulk publishing (`PBSEXPR`) must be excluded.
4. `USER_` id -> group (SOCC / Crew scheduler / Crew planning / ...) to set `initiator` (IOC vs planners vs crew).
5. Pseudonymisation key for `crew_id`.
6. Whether a WFLY pilot is "not scheduled" for the draft definition; the other `RECTYPE 21` values (1-14, 17, 18, 21-24, 27).
7. Retention: ask the DBA whether `LOG_ROSTER` (starts 2024-05-14) / `LOG` (dense 2023-11-08) were purged or simply started then; 36 months (2023-08) of timestamped events is only possible if older journals exist elsewhere (archive/backup).

## 10. Operational notes (production safety)
All queries above are bounded: key-prefix seeks (`ID, LEG_DAY` on ROSTER/LOG_ROSTER indexes), `ONDATE/ONDAY` ranges on `LOG`/`LOG_ROSTER`, `RECTYPE + LEG_DAY` on `ROSTERDT`, `LEG_DAY` on `PROSTER`. `MSTLOGCRW` (260 M rows) was only touched with three clustered-key queries (`TOP 1` by `TABLELOGID` ascending and descending, plus one `TABLELOGID` range of ~250k rows); `CREXPLOG` was not touched. Messages (`Crewmsg`, `MCREW3`, `PUSHNOTIF.PAYLOAD`) were counted only. The `LOG` approach (OUTER APPLY per draft) is fine for a month at a time; for the full 28-month window run month by month. `LOG` has no index on `(ID, NEW)`: always give `ID` and `FORDATE`.

