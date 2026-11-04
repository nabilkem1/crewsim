# LEGMAIN  (Table)  - Flight-leg master: one row per scheduled / operated flight leg (sector)

## 1. Purpose & business meaning

**What a row is.** One *flight leg* (one take-off-to-landing sector) of one flight number on one day, as held by the AIMS flight-management ("FMS") module. It is the schedule backbone of the whole database: the schedule times (STD / STA), the route (DEP -> ARR), the aircraft tail (REG) and type (AC), the leg's cancellation / diversion status, and the link to the aircraft rotation (ADATE + AROUTE). Everything the crew side knows about a flight (the crew pairings that carry it - `CREWLEG`, the crew actually rostered on it - `ROSTER`, the actual times - `LEGTIMES`) hangs off the five-part flight key defined here.

**Grain.** One row per `(DAY, DEP, CARRIER, FLT, LEGCD)`. This is the primary key, and it is the **composite flight key** used by every other table in this family (see section 4). A flight number can have 1-3 legs on the same day (multi-stop flights, or extra legs created after a return to ramp); in a sample of 8,557 distinct 2026 (DAY, CARRIER, FLT) combinations, 8,365 had one leg, 187 two and 5 three.

**Lifecycle.**
- Created by the schedule build / flight-planning side of AIMS up to about 14 months ahead (for the home carrier the latest non-cancelled leg at extraction is about 2027-10-30; two stray home-carrier rows exist in 2030).
- Updated by operations control during the day (re-timing, tail swaps, cancellations, diversions, delays DDLY / ADLY).
- Rows are never deleted by the planner procedures; a leg that is dropped is flagged `CANCELLED <> 0`.
- History goes back to 1980-01-02 (DAY = 1) but real volume starts in 2002 (shared with LEGTIMES, CREWLEG).

**Who reads it (planner-assist).** Read-only. Every crew-compliance procedure joins LEGMAIN to resolve the *scheduled departure / arrival time (UTC)* and the *arrival airport* of a roster leg or a pairing leg: R0 (draft list: pairing start/end, overlap windows), R3 (rest / acclimatisation), R4 (FDP, block-time limits), R5 (flight-time credit), `rpt.CalculateCrewFTC`, and `rpt.Get_Detailed_Pairing` (full leg-by-leg dump of a pairing with airport/aircraft categories, time zones, civil twilight).

**Who owns the other half of the picture.** Crew members attached to the leg: `ROSTER` (documented elsewhere). Pairings that contain the leg: `CREWLEG` / `CRROUTE`. Actual times: `LEGTIMES`.

**Home carrier.** `CARRIER = 1` is the operating airline itself (vvCarriers.CODE = `TSC`). The table also holds legs of 327 other carrier ids (partner airlines such as AC=13, WS=46, AF=3, and surface-transport "carriers" such as OWN=9) because crew can deadhead on them. 820,879 of 1,232,038 rows are carrier 1. `rpt.usp_GetPairingID` hard-codes `CARRIER = 1`.

## 2. Physical facts

| Item | Value |
|---|---|
| Database / schema | `TSC.dbo.LEGMAIN` |
| Type | Table |
| Rows (extraction) | 1,232,038 (single partition) |
| Primary key | `LEGMAIN_INDEX_0` UNIQUE `(DAY, DEP, CARRIER, FLT, LEGCD)` |
| Other indexes | `LEGMAIN_INDEX_1 (ADATE, AROUTE)` - find all legs of an aircraft rotation; `LEGMAIN_INDEX_2 (CANCELLED, REG)` - legs by tail; `LEGMAIN_INDEX_3 (AC)` - by aircraft type; `Idx_LEGMAIN_ADATE_AROUTE_AC (ADATE, AROUTE, AC)`; `Idx_LEGMAIN_DEP_FLT_CANCELLED_FLTYPE (DEP, FLT, CANCELLED, FLTYPE)` - lookup by origin + flight number; four tuning-advisor indexes `_dta_index_LEGMAIN_5_2105058535__*` covering `(DAY, STD, ...)` / `(AROUTE, ADATE, DAY, STD, ...)` - i.e. date-window scans ordered by time and aircraft-rotation scans |
| Collation | `SQL_Latin1_General_CP1_CI_AS` (case-insensitive; same as ROSTER, CREWLEG, LEGTIMES, CRLEGGROUND, so no `COLLATE` hint is needed for the key joins) |
| Width note | `columns.json` `len` is in bytes. Character columns are `nchar(len/2)`: DEP/ARR = nchar(4), LEGCD = nchar(1), REG = nchar(12), ARCID = nchar(10), MISSION = nchar(15), DEPTERM/ARRTERM/ONWARD_LEGCD = nchar(1). Station codes are 3-letter IATA (LEN = 3 on all 2026 rows); `=` comparisons ignore trailing blanks. |

**Access pattern implication.** The PK starts with `DAY`, so any query that restricts a DAY range (or equality) is an index seek. A query by flight number alone (`FLT = ...` without DAY) cannot use the PK and falls back to `Idx_LEGMAIN_DEP_FLT_...` only if DEP is also supplied - always filter on DAY.

## 3. Column dictionary

Day numbers: **DAY / ADATE / ORGDAY / ONDAY / UPDDATE = whole days since 1980-01-01** (`DATEADD(DAY, n, '1980-01-01')`; day 17108 = 2026-11-03). Minute columns (STD, STA, ORGSTD, ORGSTA) = minutes since 00:00 **UTC** of the row's DAY (may exceed 1440 for arrivals after midnight).

### 3.1 Flight key
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| DAY | smallint | N | Day of the *scheduled departure* (UTC) of the leg. First part of the flight key. | Days since 1980-01-01 (UTC date). Range 1..18270 (1980-01-02 .. 2030-01-08). | R0/R3/R4/R5 `DATEADD(DAY, lm.DAY, @BaseDate)`; profiled |
| DEP | nchar(4) | N | Departure airport (station) of the leg. Second part of the key. | 3-letter IATA code, e.g. YUL, YYZ, CDG. Joins `vvAirports.AIRPORT`. | R3 `dep_arp.AIRPORT = r.LEG_DEP`; Get_Detailed_Pairing |
| CARRIER | smallint | N | Operating carrier of the flight. Third part of the key. | `vvCarriers.ID`. 1 = home carrier (code TSC). Other ids = partner airlines (13=AC, 46=WS, 3=AF, 208=NAT ...) and surface carriers (9=OWN, CAT=1). 328 distinct ids. | `usp_GetPairingID` (`CARRIER = 1`); R3 `crr.ID = r.LEG_CARRIER`; profiled |
| FLT | smallint | N | Flight number. Fourth part of the key. Always positive in this table (1..9999). Numbers 6001-6999 were used for FLTYPE 9 surface/train legs. Negative flight numbers exist only in CREWLEG / CRLEGGROUND / ROSTER and denote ground activities (see CRLEGGROUND). | smallint, 1..9999 | profiled (0 negative rows of 1,232,038) |
| LEGCD | nchar(1) | N | Leg code: disambiguates several legs of the same flight number departing the same airport on the same day. Fifth part of the key. Blank (single space) = the original / normal leg (99.3% of 2026 carrier-1 rows). Letters A,B,C,D (rare) = additional legs created when a flight returned: `A`/`B`/`C` coincide with LEGSTATUS 5 (return to ramp) and `D` with LEGSTATUS 6 (return from airborne); in every such row `DEP = ARR`. | ' ' (blank, equals '' in comparisons) / A-D / rare '.', 'W','P', etc. in old data. Case-insensitive collation. | profiled; R3 `lm.LEGCD = r.LEG_LEGCD`; interpretation of A-D is **inference** from LEGSTATUS/DEP=ARR |

### 3.2 Status
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| CANCELLED | tinyint | N | Cancellation flag of the leg. `0` = leg is live (operating or planned). Non-zero = cancelled. Planner code only distinguishes 0 / <>0. | 0 = live; 1 = cancelled (carries CNXREASON / ONDAY / ONTIME in 2026, AROUTE = 0); 2 = cancelled/removed with LEGSTATUS 1 ("CA") in 4,397 of 5,550 cases and no cancel reason - exact difference between 1 and 2 is **not documented** (see section 9). 2026 carrier-1: 26,377 / 160 / 5,550. | R4 `lm.CANCELLED <> 0`; Get_Detailed_Pairing `CANCELLED = 0`; profiled |
| LEGSTATUS | tinyint | Y | Special status of the leg = 1-based index into the FMS "STATUS" list of `vvFMSCodes` (`STATUS_n_CODE/DESC`). 0 = none. | 1 CA cancelled, 2 RS re-schedule, 3 DV diverted, 4 RR re-routed, 5 QG return to ramp, 6 QF return from airborne. 2026 carrier-1 counts: 0 = 26,146 (live) + others. | vvFMSCodes (read live); profiled; no procedure reads it |
| FLTYPE | tinyint | Y | Service type of the flight = 1-based index into `vvFMSCodes.FLTYPE_n_CODE/DESC`. | 1 C Charter, 2 J Scheduled service, 3 E VIP, 4 P Ferry, 5 K Training, 6 T Test flight, 7 G Additional flight, 8 Z Other airlines, 9 U Surface vehicle (train), 10 O Special charter, 11 X Tech stop, 12 H Charter cargo; 0 = undefined (402,356 rows, mostly non-home carriers). 2026 carrier-1 legs flown up to day 17100 (live, with LEGTIMES): 2 = 22,260; 4 = 374; 7 = 40. | Get_Detailed_Pairing `flight_service_type fst ON fst.FLTYPE_INDEX = FinalBase.FLTYPE`; profiled |
| ACDUTY | tinyint | Y | Aircraft duty (what the aircraft is used for) = 1-based index into `TABLES` record `FMACDUTY` (code 24 chars + description 40 chars per entry, same layout as `vvFMSCodes.XACDUTY_n`). | 1 PS passenger, 2 FOB fuel on board, 3 TRAIN, 4 "321L" (Europe 321L configuration; used for AC=16 in 2026). FLTYPE 9 rows are always ACDUTY 3 and AC 17 (TRN). | Get_Detailed_Pairing builds `#FLTTYP_REF` from FMACDUTY% (but never uses it); profiled. Meaning of value 4 is **inference** from the table label. |
| ORDER_ | tinyint | Y | 0-based sequence of the leg inside its aircraft rotation (ADATE, AROUTE). 0 = first leg of the rotation. | 0..5 in 2026 | profiled (rotation sample: out-and-back = 0 then 1) |
| SEQUENCE | tinyint | Y | Unknown - not used by any procedure (all 0 / NULL in 2026). | | profiled |
| SCHEDULEDOPS | tinyint | Y | Unknown - not used by any procedure (all 0). | | profiled |
| LEGMAINFLAGS | tinyint | Y | Unknown flag byte, not used (2026: 0 for 32,074 rows, 2 and 4 on 5 rows). | bit flags | profiled |
| FLAGS | tinyint | Y | Unknown flag byte, not used. 2026 carrier-1 values 0, 8, 16, 24 -> bits 3 and 4 used (probably per-leg operational flags). | bit flags | profiled |
| VP_FLAGS, VP_FLAGS2 | tinyint | Y | Unknown flag bytes ("VP" = possibly vacation-planning / variation); VP_FLAGS2 = 64 on 378 of 2026 carrier-1 rows. Not used. | bit flags | profiled |
| AAREPFLAG | tinyint | Y | Unknown flag (0 or 2 in 2026), not used. | | profiled |
| DO_NOT_CHANGE | tinyint | Y | "Do not change" lock flag on the leg (naming inference); 0 everywhere. | | naming inference |
| EASAPR10, EASAPR2, EASAERR10, EASAERR2 | tinyint | Y | EASA-related (PR / ERR) flags, 10 / 2 probably refer to day-night counts; all zero in the whole table. Unknown - not used. | | naming inference; profiled (all 0) |
| TRAFFICLIM | tinyint | Y | Traffic limitation (naming inference); all 0. | | profiled |
| SCOMPLIX | tinyint | Y | Unknown (seat complexity?); all 0. | | profiled |
| SEATFLAGS | tinyint | Y | Unknown; all 0. | | profiled |
| LEASEIND | tinyint | Y | Lease indicator (naming inference). 2026 carrier-1: 32 on 28,387 rows, 0 on 3,692 - possibly "wet-lease / own-metal" bits. Not used. | | profiled |

### 3.3 Scheduled times and route
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| ARR | nchar(4) | Y | Arrival airport of the leg. NULL-able but never NULL in 2026. For return-to-ramp legs (LEGCD A-D) equals DEP. | 3-letter IATA | R0/R3/R4/R5 `lm.ARR`; Get_Detailed_Pairing |
| STD | smallint | Y | Scheduled time of departure, minutes after 00:00 UTC of DAY. 0..1440. | UTC minutes. Local time = + station UTC offset (computed by `CrewSchedAI.dbo.GetEffectiveOffset*` from DEP and the instant). | R0 `DATEADD(MINUTE, lm.STD, DATEADD(DAY, lm.DAY, @BaseDate))` "UTC, like STD / STA"; Get_Detailed_Pairing `STD_UTC` |
| STA | smallint | Y | Scheduled time of arrival, minutes after 00:00 UTC of **DAY (the departure day)**; values above 1440 mean the landing is on a later UTC day. 1..2874; 1,475 of 8,754 legs in a 100-day 2026 sample exceed 1440. | UTC minutes since DAY midnight. Arrival date = DAY + STA/1440. | R0 `lm.STA`, R4 `DATEADD(MINUTE, lm.STA, DATEADD(DAY, r.LEG_DAY, @BaseDate))`; profiled |
| ORGDAY | smallint | Y | Original (first published) DAY if the leg was re-dated after publication; 0 = never re-dated. | day number | profiled (8,727 of 8,754 zero) |
| ORGSTD | smallint | Y | Original scheduled departure minute before the last schedule change; 0 = unchanged. | UTC minutes | profiled |
| ORGSTA | smallint | Y | Original scheduled arrival minute; 0 = unchanged. | UTC minutes | profiled |
| DDLY | smallint | Y | Departure delay in minutes (negative = early). Equals BLOF - STD in 7,372 of 7,453 legs of a 2026 sample. | minutes | profiled vs LEGTIMES |
| ADLY | smallint | Y | Arrival delay in minutes. Equals BLON - STA in 7,310 of 7,453 sampled legs. | minutes | profiled vs LEGTIMES |
| DEPTERM | nchar(1) | Y | Departure terminal; blank everywhere. | | profiled |
| ARRTERM | nchar(1) | Y | Arrival terminal; blank everywhere. | | profiled |

### 3.4 Aircraft and aircraft-rotation
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| REG | nchar(12) | N | Registration (tail number) of the aircraft assigned to the leg, e.g. `C-GOIR`. Blank when no tail is assigned (1 of 8,754 sampled legs). | Canadian-style registration; joins `ACCATEG.ACREG` | Get_Detailed_Pairing `acc.ACREG = REG` |
| AC | smallint | Y | Aircraft type = `vvAIRCTYPE.ACTYPE` (key; IATACODE gives the type code). 2026 carrier-1: 16 (32Q) 14,438; 4 (332) 8,679; 14 (321) 7,675; 6 (333) 1,295. | ACTYPE id | Get_Detailed_Pairing `ac.ACTYPE = CONVERT(TINYINT, FinalBase.Ac)`; R0 `AIRCTYPE.ACTYPE` |
| ORGREG | nchar(12) | Y | Originally planned registration before a tail swap; blank on most rows (1,645 non-blank in the whole table). | | profiled |
| ADATE | smallint | N | Date on which the aircraft rotation (AROUTE) starts / is defined. Equals DAY for 6,595 of 8,754 sampled legs; differs when a rotation spans midnight; 0 for legs without an aircraft route. | day number | profiled; index `(ADATE, AROUTE)` |
| AROUTE | bigint | N | Aircraft-route (rotation) identifier: the chain of legs flown by one tail in sequence. Together with ADATE it identifies the rotation; all legs of one (ADATE, AROUTE) have the same REG (879 of 879 rotations sampled, up to 4 legs). **0 for every cancelled leg of 2026 carrier 1 (5,710 of 5,710)** and for legs not assigned to a rotation. | large id (e.g. 137979048240) | profiled (no procedure reads it) |
| ARCID | nchar(10) | Y | Aircraft ID text; blank everywhere. | | profiled |
| PIC | int | Y | Pilot-in-command of the leg as a crew-member id (join to the crew master). Non-zero only on a minority of legs (about 2.5% of 2026 carrier-1 rows; 278 distinct ids among legs of days 16802-17100). Not used by planner-assist; values not profiled (personal data). | crew id | naming inference; privacy rule |
| MISSION | nchar(15) | Y | Free-text mission; blank everywhere. | | profiled |

### 3.5 Capacity, commercial, other
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| FLTCAT | binary(6) | Y | Flight-category bit mask (48 bits). Bit N (1..48, byte `(N-1)/8 + 1`, bit `(N-1)%8`) set = category N of `GENCAT` type 6 applies to the flight (e.g. long-haul / overseas / ...). Non-zero on about 28% of 2026 carrier-1 legs. | bitmask decoded with `TSC.dbo.bit_is_set` | Get_Detailed_Pairing `Flight_Categories` (decodes `CONVERT(BINARY(32), FLTCAT)`) |
| SEATS | binary(8) | Y | Seat counts by cabin packed in 8 bytes (not decoded); non-zero on 14,222 of 32,087 2026 carrier-1 rows. Unknown layout - not used. | binary | profiled |
| ACCONFIG | binary(8) | Y | Aircraft cabin configuration code(s); non-zero on 14,767 rows. Unknown layout - not used. | binary | profiled |
| BC | smallint | Y | Unknown (business-class count?). 0 everywhere in 2026. | | profiled |
| ACO | smallint | Y | Unknown flag 0/1 (746 of 32,087 rows = 1, all on AC 4/6/14/16). Not used. | | profiled |
| FDO, CCO, ODD, RTL | smallint | Y | Unknown, 0 everywhere in 2026 (FDO/CCO probably flight-deck / cabin-crew observers; naming inference only). Not used. | | profiled |
| QUOTNO | int | Y | Unknown (quotation / contract number?). 26 non-zero rows in the whole table. | | profiled |
| AWARDNO | int | Y | Unknown (award number). 0 in the whole table. | | profiled |
| COSMICRADIATION | real | Y | Cosmic-radiation dose of the leg (naming). 0 in the whole table - not populated. | | profiled |
| CHANGE_REASON, PLAN_CHANGE_REASON, CREW_REL_CHANGE_REASON | binary(4) | Y | Bit masks of the reason(s) for operational change / planning change / crew-release change. All zero in 2026. | | naming inference; profiled |
| UPDDATE | smallint | Y | Date of last update (day number). 0 in the whole table (not maintained). | | profiled |
| UPDTIME | smallint | Y | Time of last update; 0 (not maintained). | | profiled |
| ORGCARRIER | smallint | Y | Original carrier id before a codeshare/carrier change; 0 everywhere. | | profiled |
| CNXREASON | int | Y | Cancellation reason code (index). Non-zero on 1,062 legs of 2026 carrier 1, all of them cancelled. | 1..n | profiled |
| ONDAY | smallint | Y | Day on which the leg was cancelled / the decision was taken (day number); non-zero 1,061 rows, always accompanied by CNXREASON. Can be earlier than DAY. | day number | profiled |
| ONTIME | int | Y | Time-of-day of that decision in seconds since midnight (values 42129, 49618, 59813, 69450 ...; exceeds the 1440-minute range so it cannot be minutes). | seconds (inference) | profiled |
| ONWARD_CARRIER | smallint | Y | Carrier of the "onward" (continuation) flight. Non-zero on 30,456 of 32,087 2026 carrier-1 rows. | carrier id | profiled |
| ONWARD_FLT | smallint | Y | Flight number of the onward flight. In a sample it points to the next flight in the same aircraft rotation pattern (e.g. leg 110 -> 111, 111 -> 110 the same DAY), i.e. not necessarily later in time. | flight number | profiled |
| ONWARD_LEGCD | nchar(1) | Y | Leg code of the onward flight. | blank | profiled |
| ONWARD_LAYOVER | tinyint | Y | Layover count/length class before the onward flight (0 for 96.9% of rows, 1-6 otherwise). Exact unit unknown. | | profiled |

## 4. Keys & relationships

**Natural key = composite flight key**: `(DAY, DEP, CARRIER, FLT, LEGCD)` (PK, unique, no NULLs). Read it as: *the leg of flight `CARRIER FLT` departing airport `DEP` on UTC date `DAY`, qualified by leg code `LEGCD`*. The same five columns (prefixed `LEG_` in ROSTER) appear in LEGTIMES, CREWLEG, CRLEGGROUND and ROSTER; there are **no declared foreign keys**.

| To | Cardinality | Join predicate (exact, from code) | Source |
|---|---|---|---|
| LEGTIMES | 1 : 0..1 | `lts.[DAY] = lm.DAY AND lts.DEP = lm.DEP AND lts.CARRIER = lm.CARRIER AND lts.FLT = lm.FLT AND lts.LEGCD = lm.LEGCD` (written from the roster side as `lts.DAY=r.LEG_DAY AND lts.DEP=r.LEG_DEP AND lts.CARRIER=r.LEG_CARRIER AND lts.FLT=r.LEG_FLT AND lts.LEGCD=r.LEG_LEGCD`) | R3, R4, R5 |
| CREWLEG | 1 : N (one row per pairing that carries the leg) | `cl.DAY = lm.DAY AND cl.DEP = lm.DEP AND cl.CARRIER = lm.CARRIER AND cl.FLT = lm.FLT AND cl.LEGCD = lm.LEGCD` ; Get_Detailed_Pairing: `legs.[DAY] = lm.[DAY] AND legs.[CARRIER] = lm.[CARRIER] AND legs.[FLT] = lm.[FLT] AND legs.[DEP] = lm.[DEP] AND legs.[LEGCD] = lm.[LEGCD]` | rpt.Get_Detailed_Pairing |
| ROSTER (documented elsewhere) | 1 : N (one row per crew member on the leg) | `lm.DEP = r.LEG_DEP AND lm.CARRIER = r.LEG_CARRIER AND lm.[DAY] = r.LEG_DAY AND lm.FLT = r.LEG_FLT AND lm.LEGCD = r.LEG_LEGCD` | R0 line 676, R3 line 282, R4 line 383, R5 line 387, CalculateCrewFTC line 236 |
| CRLEGGROUND | none (ground activities have negative FLT; LEGMAIN.FLT is always > 0). Roster rows with `LEG_FLT < 0` therefore match CRLEGGROUND, not LEGMAIN. | | R0/R3 LEFT JOINs with `lm` and `clg` both |
| vvAirports | N : 1 | `dep_arp.AIRPORT = lm.DEP`, `arr_arp.AIRPORT = lm.ARR` | R3, Get_Detailed_Pairing |
| vvCarriers | N : 1 | `crr.ID = lm.CARRIER` | R3, Get_Detailed_Pairing |
| vvAIRCTYPE | N : 1 | `ac.ACTYPE = lm.AC` (cast to tinyint in code) | Get_Detailed_Pairing |
| vvFMSCodes | N : 1 (positional) | FLTYPE / LEGSTATUS / ACDUTY are positional indexes into the `*_n_CODE` columns | Get_Detailed_Pairing |
| ACCATEG / ACCATEG2 | 1 : N | `acc.ACREG = REG AND acc.ACTIVEBEG < (DAY + STD/1440) AND acc.ACTIVEEND > (DAY + STA/1440)` (aircraft category validity in day numbers) | Get_Detailed_Pairing |

**Aircraft rotation**: legs with the same `(ADATE, AROUTE)` form one aircraft rotation ordered by `ORDER_` (self-grouping, no separate table in scope).

**Referential-integrity facts measured (2026):** every CREWLEG flight row (FLT > 0) has a LEGMAIN row (96,945 of 96,945); every non-cancelled home-carrier leg in a 61-day window has CREWLEG and LEGTIMES rows (4,949 of 4,949); cancelled legs have neither; every LEGTIMES row has a LEGMAIN row (22,686 of 22,686).

## 5. Encoding conventions & gotchas

- **DAY is not a calendar date**: `smallint` days since 1980-01-01. Use `DATEDIFF(DAY, '1980-01-01', @date)` to convert in, `DATEADD(DAY, DAY, '1980-01-01')` out. 17108 = 2026-11-03; 2026 = 16802..17166.
- **STD and STA are UTC minutes after midnight of DAY.** Planner code adds them to `DATEADD(DAY, DAY, '1980-01-01')`; local time is then derived with the airport's UTC offset (`CrewSchedAI.dbo.GetEffectiveOffset`, later `dbo.GetEffectiveOffsetUtc`, evaluated at the UTC instant - R3-15 item 8 documents that using midnight of the day gave the wrong offset on 174 of 40,378 departures on DST-change days).
- **STA may be > 1440** (arrival on the next UTC day) and STD can equal 1440. Never compare STA to a time-of-day without adding the day: arrival date = `DAY + STA/1440` (integer division); this is exactly how `rpt.Get_Detailed_Pairing` windows the aircraft/airport category validity ranges.
- **Cancelled legs stay in the table** (`CANCELLED` 1 or 2). 17.8% of 2026 carrier-1 legs (5,710 of 32,087) are cancelled. They have no crew-leg, no actual-times row and `AROUTE = 0`. Always add `CANCELLED = 0` for "flights that will/did operate" (Get_Detailed_Pairing does). R4 phase 9B treats `CANCELLED <> 0` without actual block times as not flown.
- **Return legs share the key**: a leg code other than blank (A-D) is a *second leg of the same flight number* with `DEP = ARR`; it carries the same STD/STA as the original. Joins that omit LEGCD double-count.
- **Flight numbers are not unique per day**: key must include DEP (and LEGCD); R4 notes "a flight number can appear twice on the same day (multi-stop flights)".
- **CARRIER is part of the key**: partner-airline legs (deadheads) and surface transport (FLTYPE 9, flight numbers 6001-6999, AC 17 = TRN, last used 2024-04) live here too; filter `CARRIER = 1` for own flights.
- **Zero as sentinel**: ORGDAY/ORGSTD/ORGSTA = 0 mean "unchanged"; AROUTE/ADATE = 0 mean "no aircraft route"; ONDAY/CNXREASON/ONTIME = 0 mean "not cancelled"; most flag/option columns are 0 everywhere.
- **Nullable columns are mostly "all populated"** (NULLs appear on about 8-89 of 32,087 2026 carrier-1 rows, e.g. FLTYPE NULL on 89 rows). Use `ISNULL` when joining codes.
- **Case-insensitive collation**: 'a' = 'A' for LEGCD. R0 and `rpt.CalculateCrewFTC` add `COLLATE SQL_LATIN1_GENERAL_CP1_CI_AS` on LEGTIMES.DEP/LEGCD; this is the same collation as the column, so it is redundant unless the code runs under a database with another default collation (CrewSchedAI).
- **Time horizon**: LEGMAIN contains scheduled legs far into the future, unlike LEGTIMES (actuals up to 2026-10-28). Do not assume a LEGTIMES row exists for a future or recent leg.

## 6. How the planner-assist procedures use it

| Procedure | Columns | Filter / reason |
|---|---|---|
| `dbo.R0_GetDraftList` | DAY, DEP, CARRIER, FLT, LEGCD (join), STD, STA, ARR | LEFT JOIN from ROSTER (and from CREWLEG for unassigned pairings). Computes pairing start = MIN(report time or STD - report offset) and end = MAX(debrief time or (BLON/ETA/STA) + debrief offset), converts UTC -> local zone with `AT TIME ZONE`. Also gives each roster leg its DEP/ARR date-time and `Act_Start_UTC` / `Act_End_UTC` for the overlap test against the pairing being drafted. |
| `dbo.R3_Get_Violations_RestTime` / `_Batch` | key, STD, STA, ARR | Scheduled start/end of every roster and drafted leg; `ISNULL(lm.ARR, r.LEG_DEP)` as arrival station; `ISNULL(lm.STD, ISNULL(lts.ETD, ISNULL(r.REPORTTIME, 480)))` fallback order for departure; builds duty periods, rest and acclimatisation (EASA FDP table in the procedure; FD-PCA-3830 rest rule). |
| `dbo.R4_Get_Violation_FDP` | key, STD, STA, ARR, CANCELLED | FDP and block-time (FD-CAR-3300A/B/C, CAR 700.103 / AC 5.11) calculations; scheduled leg times; `lm.CANCELLED <> 0` leg dropped unless it has actual block times. |
| `dbo.R5_Get_Violation_FTC` | key, STD, STA, ARR | Flight-time-credit calculation: leg duration `lm.STA - lm.STD` as last fallback after actual block times. |
| `rpt.CalculateCrewFTC` | key, STD, STA, ARR | Same as R5 for a crew roster extract. |
| `rpt.Get_Detailed_Pairing` | key, CANCELLED, DEP, ARR, STD, STA, REG, AC, FLTYPE, FLTCAT, CARRIER (everything via `lm.*`) | Lists the legs of one pairing (`@PAIRING_ID`, `@PAIRING_DATE`); filter `CANCELLED = 0`; computes `STD_UTC = DATEADD(MINUTE, STD, DATEADD(DAY, DAY, '1980-01-01'))`, local STD, twilight, international/domestic (via airport OVERSEAS flag), service type, flight/aircraft/airport/country categories. |
| R1, R2 | none directly | They call `rpt.Get_Detailed_Pairing`. |

## 7. Typical query patterns

Always restrict `DAY` and normally `CARRIER = 1` and `CANCELLED = 0`.

```sql
-- 1. Scheduled legs of the home carrier on one date (UTC date)
SELECT DEP, ARR, CARRIER, FLT, LEGCD, REG, AC,
       DATEADD(MINUTE, STD, DATEADD(DAY, DAY, '1980-01-01')) AS STD_UTC,
       DATEADD(MINUTE, STA, DATEADD(DAY, DAY, '1980-01-01')) AS STA_UTC
FROM TSC.dbo.LEGMAIN
WHERE DAY = DATEDIFF(DAY, '1980-01-01', '2026-11-10')
  AND CARRIER = 1 AND CANCELLED = 0
ORDER BY STD;

-- 2. One flight number over a date range (DAY range is mandatory)
SELECT DAY, DEP, ARR, LEGCD, STD, STA, CANCELLED
FROM TSC.dbo.LEGMAIN
WHERE CARRIER = 1 AND FLT = 110
  AND DAY BETWEEN DATEDIFF(DAY,'1980-01-01','2026-11-01') AND DATEDIFF(DAY,'1980-01-01','2026-11-30')
ORDER BY DAY, STD;

-- 3. Scheduled leg joined to its actual times (only flown legs have a LEGTIMES row)
SELECT lm.DAY, lm.DEP, lm.ARR, lm.FLT, lm.STD, lt.BLOF, lt.BLON, lm.DDLY, lm.ADLY
FROM TSC.dbo.LEGMAIN lm
LEFT JOIN TSC.dbo.LEGTIMES lt
       ON lt.DAY = lm.DAY AND lt.DEP = lm.DEP AND lt.CARRIER = lm.CARRIER
      AND lt.FLT = lm.FLT AND lt.LEGCD = lm.LEGCD
WHERE lm.DAY BETWEEN 17090 AND 17100 AND lm.CARRIER = 1 AND lm.CANCELLED = 0;

-- 4. Legs with their pairings (CREWLEG -> CRROUTE)
SELECT lm.DAY, lm.FLT, lm.DEP, lm.ARR, cr.DESC_ AS PAIRING
FROM TSC.dbo.LEGMAIN lm
JOIN TSC.dbo.CREWLEG cl ON cl.DAY = lm.DAY AND cl.DEP = lm.DEP AND cl.CARRIER = lm.CARRIER
                       AND cl.FLT = lm.FLT AND cl.LEGCD = lm.LEGCD AND cl.REMOVED = 0
JOIN TSC.dbo.CRROUTE cr ON cr.CDATE = cl.CDATE AND cr.CROUTE = cl.CROUTE
WHERE lm.DAY = DATEDIFF(DAY,'1980-01-01','2026-11-10') AND lm.CARRIER = 1 AND lm.CANCELLED = 0;
```

## 8. Data profile

Measured 2026-11-03 (read-only).

- Rows 1,232,038; DAY 1 .. 18270 (1980-01-02 .. 2030-01-08); 328 distinct CARRIER ids; carrier 1 = 820,879 rows.
- Rows by calendar year (from 2025 on; earlier years not broken out): 2025: 47,824 (carrier 1: 31,502), 2026: 50,277 (carrier 1: 32,087), 2027: 23,510 (all carrier 1), 2030: 2 (carrier 1).
- CANCELLED (all rows): 0 = 1,025,502; 2 = 188,559; 1 = 17,977. 2026 carrier-1: 0 = 26,377, 1 = 160, 2 = 5,550.
- LEGCD (all): blank 1,226,967; A 3,281; D 541; '.' 483; W 244; B 214; P 153; others fewer than 20 each.
- LEGSTATUS (all): 0 = 1,221,000; 1 = 7,319; 5 = 1,915; 3 = 910; 4 = 493; 2 = 216; 6 = 173; NULL = 12.
- FLTYPE (all): 2 = 587,472; 0 = 402,356; 9 = 169,419 (train/surface legs, 2019-05..2024-04); 1 = 30,314; 4 = 24,728; 3 = 8,609; 5 = 7,365; 7 = 1,441; 6 = 137; 12 = 11; 10 = 4; 8 = 3; 11 = 2; NULL = 177.
- ACDUTY (all): 1 = 556,090; 0 = 405,828; 3 = 169,419; 4 = 100,682; NULL = 19.
- 2026 carrier-1 aircraft types: AC 16 = 14,438; 4 = 8,679; 14 = 7,675; 6 = 1,295.
- STD range 0..1440; STA 1..2874; 1,475 of 8,754 legs in days 17000-17100 (carrier 1) have STA > 1440.
- In days 17000-17100 (carrier 1): 8,754 legs, 8,753 with STA > STD; AROUTE non-zero on 7,453 (= live legs), 189 distinct values; ADATE = DAY on 6,595.
- Aircraft rotations in days 17040-17060: 879, one REG each, average 1.85 legs, max 4.
- Rotation order ORDER_ (2026 carrier 1): 0 = 16,773; 1 = 14,429; 2 = 545; 3 = 273; 4 = 62; 5 = 5.
- Zero-everywhere (2026 carrier 1): SEQUENCE, SCHEDULEDOPS, TRAFFICLIM, DO_NOT_CHANGE, SCOMPLIX, SEATFLAGS, EASA* , BC, FDO, CCO, ODD, RTL, QUOTNO, AWARDNO, COSMICRADIATION, UPDDATE, UPDTIME, ORGCARRIER, DEPTERM, ARRTERM, ARCID, MISSION, CHANGE_REASON, PLAN_CHANGE_REASON, CREW_REL_CHANGE_REASON.

## 9. Open questions / confidence

- **High confidence**: key semantics, DAY/STD/STA encodings and UTC, CANCELLED 0 vs non-zero, join predicates, FLTYPE / LEGSTATUS / ACDUTY decoding labels (read from the system's own code tables), the fact that LEGCD A-D are return legs (DEP = ARR, LEGSTATUS 5/6).
- **Medium**: ADATE/AROUTE/ORDER_ as aircraft rotation (consistent with data, no procedure uses them); DDLY/ADLY as delay minutes (matches BLOF-STD to the minute in 98.9% of sampled legs); ONTIME in seconds.
- **Unresolved**: difference between CANCELLED = 1 and CANCELLED = 2 (2 = 4,397 of 5,550 with LEGSTATUS 1 and no cancel reason, 1 always has a reason; possibly "cancelled in operations" vs "removed from the schedule"); meaning of ACDUTY = 4; ONWARD_* semantics; FLAGS / VP_FLAGS* bit meanings; SEATS / ACCONFIG layouts; PIC is a crew id (not profiled).
- The 2030 rows (2 carrier-1 rows) look like data-entry outliers.
