# Can CrewSim's corpus (D1-D12) be read directly from AIMS (TSC)?

Analysis date 2026-11-03. Evidence: the semantic layer built for `planner-assist-mcp`, live **read-only** profiling of `TSC` (production AIMS) and a column-by-column comparison with the real extract delivered by Pierre (`real_datav2\v3`). Detailed per-dataset mappings with tested SQL sketches, counts and caveats are in this folder:
[D01_D11_crew_training.md](D01_D11_crew_training.md), [D02_D03_rosters_pairings.md](D02_D03_rosters_pairings.md), [D04_D05_D06_events_drafts.md](D04_D05_D06_events_drafts.md), [D07_D08_D10_D12_pay_ops.md](D07_D08_D10_D12_pay_ops.md).

## 1. Bottom line

**Yes for the operational core, no for money and for some HR/business facts.** 8 of the 13 dataset files (D1, D2, D3 pairings, D3 legs, D4, D5, D8, D11) can be produced from AIMS with SQL, with a handful of business conventions to sign off. D6 (schedule changes) and the draft export are derivable but `reason_code`/`initiator` are heuristics. **D7 (pay in dollars), D10 (invoice amounts) and most of D12 (agreement rules) are not in AIMS**; D9 is computed by CrewSim anyway.

Three things AIMS can do **better than the Pierre extract**, because AIMS keeps history that v3 lost:
1. **The roster as published before an absence** (`PROSTER`, 2022-12-21 ->; and any past state via `LOG_ROSTER`, 2024-05-14 ->). This is the root cause of CrewSim's failing check V3 ("only 12 of 4,671 absences find their pairing in the pilot's D2"): over 10,234 sick crew-days the *current* roster still shows a flight on 0.6 % of them, the *published* roster on 41 %.
2. **A real `notification_ts`** for absences, call-outs and drafts from the AIMS change journals (`LOG` from 2024-03-14, `LOG_ROSTER`/`LOG_ROSTERDT` from 2024-05-14): 100 % of sick-run starts in the tested windows, instead of Pierre's 14 % blanks.
3. **Draft identification** without the fragile D6 x D7 join: `ROSTERDT` (`RECTYPE 21`, `VALUE1` 15/16/19/20) plus its journal gives who, which pairing, when and the status before the draft.

## 2. Dataset-level answer

Legend: **FULL** = every column derivable and tested; **MOSTLY** = all columns derivable, some conventions/mappings need sign-off; **PARTIAL** = key columns missing or heuristic; **NOT POSSIBLE** = not in AIMS.

| Dataset | Verdict | AIMS sources | History available in AIMS | What is missing / needs a decision |
|---|---|---|---|---|
| **D1** crew master | **MOSTLY** | `CREWQUAL` (base, aircraft, position, validity), `ROSTERID.SENIOR`, `CREWCATEG`, `vvPositions` | qualification/base/position/category history back to ~2000; seniority and status current-state only | no HR fields (hire/termination date, employment status) - only proxies from qualification validity; seniority numbers differ from Pierre's (order among active crew is right); `A321neoLR` is **not a qualification** in AIMS (every 321 pilot also has 32Q) -> neoLR scope must be defined by aircraft flown; crew pseudonym key |
| **D2** rosters | **MOSTLY** | `ROSTER` + `CRCODES` + `CRROUTE` + `CREWQUAL`; time zones `vvAirports`/`vvZONEIDX` | current roster ~2000 ->; published snapshots `PROSTER` 2022-12-21 ->; any past state `LOG_ROSTER` 2024-05-14 -> | code -> block_type table (PAIRING/DAY_OFF/VACATION/RESERVE/...; `REST` block is not stored in AIMS); report/debrief/reserve-window conventions; choose which roster state D2 means (published / current / as-of); pseudonym key |
| **D3** pairings | **MOSTLY** (8 of 9 columns exact) | `CRROUTE`, `CREWLEG`, `LEGMAIN` | full | `credit_hours` = Pierre's sum of scheduled block hours, **not** a pay credit (no pay-credit table found); `fleet_detail` tie rule for 118 pairings mixing A321/A321neo |
| **D3** pairing legs (+`deadhead`) | **MOSTLY** | `CREWLEG`, `CRLEGGROUND`, `LEGMAIN`, `vvCarriers`; `deadhead` = `CREWLEG.PAX` (98.8 % agreement) | full | `report_local`/`release_local` are **conventions** (60 min before / 30 min after in v3; 15 min debrief in planner code), not stored per leg; ground-leg `block_hours` not reproducible |
| **D4** absences | **MOSTLY** | `ROSTER` sick codes via `CRCODES`; `LOG` (notification); `PROSTER` (affected pairing) | `notification_ts` real from 2024-03-14; before that only approximate `ROSTER.NOTDATE/NOTIME` | Pierre's code lists for SICK / FAMILY / INJURY and the run-merge rule; which event his `notification_ts` meant; long absences planned to 2028 must be capped |
| **D5** reserve call-outs | **MOSTLY** | `PROSTER`/`ROSTER` reserve codes (`AM`,`PM`,`LCR`...), `LOG` (call time), first leg `LEGMAIN.STD` (report) | `call_ts` from 2024-03-14 | `declined`/`no-show` exist as roster codes but are almost absent; `released` can only be inferred; v3's inconsistent `report_ts < call_ts` rows look like join defects |
| **D6** schedule changes | **PARTIAL** | `LOG` and `LOG_ROSTER` (time, user, program, old/new), `ROSTERDT` | `LOG` dense from 2023-11-08 (sick entries 2024-03-14); `LOG_ROSTER` 2024-05-14 -> | **no reason field exists** in AIMS: `reason_code` (DRAFT vs SHORT_NOTICE_COVER vs CASCADE...) is a heuristic; `initiator` only by program/user (needs a user -> group list); `LOG` misses IOC changes (written by `MOVEMENT.EXE`) so IOC history exists only from 2024-05-14; v3's monthly volume dips are not in AIMS (extraction artefacts) |
| **D7** pay register | **PARTIAL (hours only)** | `TIMEPNCPNT` (AIMS side of Snowflake `TIMESHEET_PNC_PNT`), `CRCODES` credit minutes | **only 4 pay months** (2026-06 to 2026-09, two snapshots per crew-month) | **no dollars in TSC** (`EZYPAYROL` empty): `rate_cad`, `amount_cad`, `premium_cad` are business constants x hours (240 $/h; 1.5x -> 2x from 2026-02-01); DRAFT vs OVERTIME and DRAFT_T2 vs HOLIDAY_T2 split, AJU/DMG not reproducible; V6 backtest "against real pay" impossible; hours match Pierre within ~0.2 % |
| **D8** flight movements | **MOSTLY** | `LEGMAIN`, `LEGTIMES`, `LEGDELAYS`, `DLYCD` | continuous 2023-08 -> 2026-10 | `cancelled` in v3 is not `LEGMAIN.CANCELLED` (v3 flags "no actual times"); true cancellation cause is **not stored** as coded data; Pierre's selection rule for the single IATA code per leg is unknown (AIMS codes 100 % of delayed legs, v3 ~49 %) |
| **D9** station days | **N/A** | computed by CrewSim from D8/D4/D2 (HMM) | - | nothing to extract |
| **D10** positioning invoices | **PARTIAL events / NOT POSSIBLE amounts** | `HOTAC` (hotel and transport events), `CREWLEG.PAX=1` (deadheads) | hotel nights from 2023-09 | **no invoice amount or credit in TSC**; invoice date/lines (incl. credits, group bills) not rebuildable; categories 2, 3, 5 of HOTAC unknown |
| **D11** training sessions | **MOSTLY** | `ROSTER` training/sim activities via `CRCODES` (11 session types, consecutive days merged) | ~2000 -> but the code vocabulary changes over time | `INITIAL_GROUND` code list not recovered (728 vs 1,100); `requalification_deadline` is a per-type rule (AIMS expiries are current-state and manually overwritten); `reschedule_cost_cad_estimate` is a business table; code -> session_type map needs sign-off |
| **D12** agreement rules | **PARTIAL** | `CRCODES` credit minutes (reserve guarantee: AM/PM 4.00 h from 2026-01-06, LCR 3.00 h from 2026-03-01, legacy XAM/XPM 3.33 h = 799.20 $ at 240 $/h) | codes only | notice hours (SC/LC), caps, protected blocks, cabin agreement, `premium_pct`, term dates are **not in AIMS** (`SPEFREC*`, `RULESTBL`, `RULESETS`, `ENTRULREC*` are scheduling/leave rules, not these); the mock's 250/180 $ guarantee is wrong versus AIMS-derived hours |
| **Draft export** (Nabil's request) | **MOSTLY** | `ROSTERDT` RT21 + `LOG`/`LOG_ROSTERDT` + `PROSTER` | 2024-04-24 -> (`draft_ts` 2024-03-14 -> via `LOG`) | `trigger_reason` MISSING; `outcome` partial (no "accepted" concept); `initiator` by program only; prior status is `WFLY` (85 % in Jan 2026), not "day off" - the brief's list omits it |

## 3. Column-level view

DIRECT = 1:1 column; DERIVABLE = verified join/decode; PARTIAL = approximate or only for part of period/population; MISSING = not in TSC.

| Dataset | DIRECT / DERIVABLE (verified) | PARTIAL | MISSING |
|---|---|---|---|
| D1 | `crew_id` (needs pseudonym), `base`, `crew_group`, `position`, `fleet_family`, `qual_valid_from/to` (semantics differ) | `fleet` (which row is "the" qualification), `seniority_number`, `employment_status`, `hire_date`, `termination_date` (proxies from qualification validity) | real HR dates and status |
| D2 | `crew_id`, `base`, `fleet` (family), `position`, `block_type`, `start/end_utc`, `start/end_local`, `pairing_id`, `reserve_call_type` (LC = `LCR` from 2026-03-01; SC = AM/PM...) | `fleet_detail` (not a crew attribute) | `REST` engine block |
| D3 pairings | `pairing_id`, `base`, `fleet`, `position_complement`, `duty_periods`, `layover_stations`, `start_date`, `days` | `credit_hours` (block-hour proxy) | pay credit |
| D3 legs | `pairing_id`, `duty_period`, `leg_seq`, `origin`, `destination`, `dep_local`, `arr_local`, `block_hours` (flights), `deadhead` | `flight_no` (carrier lost), `report_local`, `release_local` (conventions) | per-leg report/release; ground-leg block hours |
| D4 | `absence_id` (hash), `crew_id`, `notification_ts` (>= 2024-03-14), `absence_start/end`, `duration_days`, `affected_pairing_id` (via `PROSTER`), `base`, `fleet`, `position` | `absence_type` (needs code list), `notification_ts` before 2024-03-14 | - |
| D5 | `callout_id`, `crew_id`, `call_ts` (>= 2024-03-14), `report_ts`, `assigned_pairing_id`, `base`, `fleet` | `outcome` (declined/no-show rare, released inferred), `call_ts` before 2024-03-14 | explicit released/declined events |
| D6 | `change_id`, `crew_id`, `change_ts`, `old/new_block_type`, `new_pairing_id` | `reason_code`, `initiator` | the real reason of a change |
| D7 | `crew_id`, `base`, `fleet`, `pay_period`, `hours`, `duty_date`, `linked_pairing_id` | `pay_code` | `rate_cad`, `amount_cad`, `premium_cad`; history before 2026-06 |
| D8 | `flight_no`, `date`, `origin`, `destination`, `fleet`, sched/actual times, `delay_minutes`, `iata_delay_code`, `delay_subcode/description` | `cancelled` (definition), `cancel_reason` (CNXREASON 1-7 undecoded) | coded true cancellation cause |
| D10 | `station`, `cost_type`, `crew_id`, `pairing_id` | `date` | `amount_cad` |
| D11 | `crew_id`, `session_type`, `start_date`, `end_date` | `requalification_deadline` | `reschedule_cost_cad_estimate` |

## 4. What is missing, in priority order (and who can provide it)

1. **Pay in dollars (D7) and invoice amounts (D10)** - not in TSC; need payroll/finance (Snowflake or the payroll system). Without D7 the V6 backtest can only compare against `hours x assumed rate`.
2. **Agreement rules (D12)** - notice hours, caps, protected blocks, premium percentage, term; business/legal source (CC document).
3. **HR facts** - hire/termination date, employment status, absolute seniority; HR system.
4. **Mapping tables to agree with the business** (can then be coded as versioned reference tables): `CRCODES` -> `block_type` / `absence_type` (SICK, FAMILY, INJURY) / `session_type` (incl. `INITIAL_GROUND`) / reserve SC-LC / "released"; user -> group (IOC, planners, crew) for `initiator`; the definition of `cancelled`; A321 vs A321neoLR scope rule.
5. **Conventions** - report/debrief minutes (60/30 vs 15), which roster state D2 represents, run-merge rule for absences, `fleet_detail` tie rule.
6. **Pseudonymisation key** - AIMS `ID` behaves like an employee number and must not be exported; a keyed, reproducible mapping must be produced outside SQL. Pierre's `P######` cannot be reproduced without his key table.
7. **Pre-2024 events** - change timestamps before 2024-03-14 (`LOG`) / 2024-05-14 (`LOG_ROSTER`) are not available; CrewSim wants history from 2023-08. Ask AIMS admins whether archived journals exist (`LOG_*` archives, backups).
8. **Cancellation cause, trigger reason of drafts** - not recorded in AIMS as data.

## 5. Constraints to respect

* **History windows:** roster/pairing/flight facts go back years; *event* history (notification, change, draft timestamps) only from 2024-03-14 / 2024-05-14; published rosters from 2022-12-21; pay only 2026-06..09. The real window (2024-04-24 .. 2026-08-31) is covered, the wished 2023-08 start is covered for D2/D3/D8/D11 but not for event timestamps or pay.
* **Time:** AIMS minutes are UTC minutes after the row's day; **journal clocks (`LOG*`, `NOTDATE`) are server-local Montreal time** (inferred from working-hour shape) -> DST-aware conversion before comparing with UTC.
* **Production database:** `MSTLOGCRW` (260M), `CREXPLOG` (1.8 billion), `LOG_LEGPAX`, `MSGQ`, `WEBLOGNG` must not be scanned; the extraction should run against a replica / off-peak with narrow date predicates.
* **Privacy (Law 25):** `crew_id` pseudonymised, no names/passenger names (`PXNAMES2`, `LEGPAX`), no free-text memos or messages; CrewSim's loader refuses banned columns.
* **Authority of definitions:** several v3 quirks are conventions of whoever built the extract (e.g. `cancelled` = "no actual times", `credit_hours` = block-hour sum, SICK code set, `start_utc` in D2). Replicating Pierre's logic is possible only where the rule is known; otherwise define it explicitly and re-run CrewSim's quality gates.

## 6. Findings about the v3 extract (to verify with Pierre; from this analysis)

* D2 pairing blocks in v3 carry the **local** report time labelled as UTC (`start_utc` 6 h off true UTC on 55 % of January 2026 pairings, correct on 1.2 %); CrewSim's loader then rebuilds from D3 duty periods and creates the overlaps (367 shortened / 1,599 dropped) - AIMS itself has no overlaps.
* v3 D2 has about 10 % more distinct crew-pairings in January 2026 than either the current or the published AIMS roster; unexplained.
* v3 `cancelled` = no actual times (explains 79 % cancelled in 23-30 April 2024); origin = destination rows are return legs (`LEGCD` A-D); TRN = SNCF train legs (`AC = 17`); P295/PDH4/7M8/... = non-own-metal wet-lease aircraft types.
* v3 D6 monthly dips (Jun-24, Dec-24, Jun-25, Dec-25, Jul/Aug-26) are **not** present in the AIMS journal -> extraction artefacts.
* v3 D1/D2/D4 disagreements on sub-fleet come from "latest-starting qualification row"; AIMS has no neoLR qualification.
* v3 D7 hours equal AIMS `TIMEPNCPNT` hours to ~0.2 % (RESERVE_CREDIT and BME exact for July 2026) - Pierre's pay data is AIMS timesheet hours x rate.

## 7. Recommended way forward

1. Build a **read-only extraction layer** (views/procs in `CrewSchedAI`, like the existing `rpt.*` procedures) per dataset, using the tested SQL sketches in the four detail files, emitting the exact CrewSim schemas; run it on a replica.
2. Keep **reference tables** (versioned) for the mappings of section 4.4 and the pseudonym key (outside SQL).
3. For D7/D10/D12, accept a **hybrid**: AIMS for hours, credits and events, business constants for rates/premiums/rules (`configs/real.yaml` already isolates them), and keep a minimal payroll feed for the V6 backtest if real dollars are required.
4. Use the published/as-of roster to rebuild D2/D4/D5 so CrewSim's V3 (eligible reserve fraction) can finally run, and replace D6 x D7 draft reconstruction by the `ROSTERDT`-based draft export.
5. Validate by reproducing January 2026 and monthly counts against v3 (already done for D1, D2, D3, D5, D8, D11 with the tolerances reported in the detail files) and run CrewSim's quality gates (`crewsim data readiness`).

## 8. Confidence

* Verified directly by me against the live database: `PROSTER` range (2022-12-21 -> 2026-12-01, 3.4M rows), `LOG_ROSTER` start 2024-05-14 with `OLDVALUE/NEWVALUE`, `AIMSUSER`, `EXTERNALAPPL` columns, `TIMEPNCPNT` = 4 pay months (06-2026..09-2026); `ROSTER` and `CREWLEG` reach back to ~2000 (`ROSTER` first day 6947 = 1999; note `LEGMAIN` has odd early rows with `DAY = 1`, so always bound dates).
* Everything else comes from parallel read-only investigations (each documents its queries and counts in its detail file); percentages quoted come from those files. Statements about *meaning* (e.g. server-local journal clock, `RECTYPE 21 VALUE1 = 11` = open-bid marker written by `OPBIDP.exe`, the 4-hour AM/PM guarantee) are inferences unless a file says "verified".
* Not done: no export was produced, no row-level comparison with Pierre beyond aggregates, no check of other AIMS databases or Snowflake, and nothing was written to AIMS.

