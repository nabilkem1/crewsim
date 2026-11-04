# CREWLEG  (Table)  - Pairing-to-leg link: which flight (or ground) legs make up each crew pairing instance

## 1. Purpose & business meaning

**What a row is.** One *leg of a crew pairing*: "pairing instance `(CDATE, CROUTE)` contains flight leg `(DAY, DEP, CARRIER, FLT, LEGCD)` at position `ORDER_`". A *pairing* (also "trip", "crew route", "rotation" - the name field `CRROUTE.DESC_`, e.g. `C0290`) is the unit the crew planners build, publish and bid: a sequence of flight legs (and sometimes ground activities such as simulator, standby or deadhead transport) that one crew member works from report to release. `CREWLEG` is the bridge table between the **pairing header** (`CRROUTE`) and the **flight legs** (`LEGMAIN`).

**Grain.** One row per `(flight key, pairing instance)` - PK `(DAY, DEP, CARRIER, FLT, LEGCD, CDATE, CROUTE)`. A flight leg appears once for **every pairing that carries it** - typically several, because pilots and cabin crew are in separate pairings and one pairing is built for each crew group and deadhead set (in days 17040-17050 about 219 flight legs had 2 pairings, 353 had 3, 182 had 4 and 74 had 5; a few had up to 14). A pairing appears once per leg it contains (2026 pairings: mostly 2 legs, up to 10).

**Ground legs are in here too.** Rows with `FLT < 0` are not flights but crew *ground activities* inside a pairing (the negative number is the `CRCODES.ID` of the activity code, e.g. a simulator or transport code). Each such row has a matching row in `CRLEGGROUND` carrying its station, aircraft type and start/end times (3,039 of 3,039 in 2026; 86,494 of 86,494 overall - the CRLEGGROUND row count equals the number of `FLT < 0` CREWLEG rows).

**Lifecycle.** Created when a pairing instance is built in the AIMS crew-pairing module (inference from naming: the module that builds and publishes trips); edited when the planner re-sequences, removes (`REMOVED = 1`) or re-flags a leg; persists in history (2002-2026) after operation. It is the *planned* structure: who actually flew is in `ROSTER`. Because a pairing without any crew assigned has **no ROSTER rows**, CREWLEG is the only source of its legs - planner-assist falls back to it for "unassigned" pairings.

**Who reads it (planner-assist).**
- Resolving a pairing (name+date) to its legs: `rpt.Get_Detailed_Pairing`, `rpt.usp_GetPairingID`.
- Fallback leg source when nobody is on the pairing (R0, R3, R4, R5: "R3-18", "R4-21", "R5-17", "R0-9").
- Per-leg deadhead flag (`PAX`), pilot complement (`LIMTABLE`) and manual-acclimatisation flag (`LGFLAGS_6`) used by R3/R4/R5/CalculateCrewFTC.

## 2. Physical facts

| Item | Value |
|---|---|
| Database / schema | `TSC.dbo.CREWLEG` |
| Type | Table |
| Rows (extraction) | 1,851,571 (single partition) |
| Primary key | `CREWLEG_INDEX_0` UNIQUE `(DAY, DEP, CARRIER, FLT, LEGCD, CDATE, CROUTE)` - flight key + pairing key |
| Other index | `CREWLEG_INDEX_1 (CDATE, CROUTE)` - "all legs of a pairing instance" (the main access path: pairing -> legs). Reverse path flight -> pairings uses the PK prefix (`DAY, DEP, CARRIER, FLT, LEGCD`). |
| Collation | `SQL_Latin1_General_CP1_CI_AS` on DEP and LEGCD |
| Width note | DEP = nchar(4), LEGCD = nchar(1) (`len` in columns.json is in bytes) |
| History | CDATE 1980-01-02 (532 rows of test data) and 2002-12-01 .. 2026-12-21; ~100k rows per year since 2022 (2024: 109,993; 2025: 104,801; 2026: 99,984) |

## 3. Column dictionary

### 3.1 Flight key (which leg)
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| DAY | smallint | N | UTC scheduled-departure day of the leg. Equal to or after CDATE (0..11 days after the pairing start in 2026). | days since 1980-01-01 | profiled; R3 `cl.[DAY] = r.LEG_DAY` |
| DEP | nchar(4) | N | Departure airport of the leg (IATA). For a ground activity: the station where it takes place. | 3-letter code | R3 `cl.DEP = r.LEG_DEP` |
| CARRIER | smallint | N | Carrier of the flight = `vvCarriers.ID`; 1 = home carrier. 311 distinct ids (deadheads on partner airlines / surface transport are legs too). | | R3 |
| FLT | smallint | N | Flight number; **negative = ground activity** (= `CRCODES.ID` of the activity); range -497 .. 9999. 86,494 rows have FLT < 0. | | profiled; R3 comments "it also holds the ground legs, FLT < 0" |
| LEGCD | nchar(1) | N | Leg code of the flight; blank for normal legs. | blank / A-D | R3 |

### 3.2 Pairing key (which pairing)
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| CDATE | smallint | N | **Pairing start date**: the day-number on which the pairing instance begins (day of its first leg's departure, UTC) - this is `ROSTER.DUTYDAY`. For all 4,961 pairings of days 17040-17080, CDATE = MIN(DAY) of its legs. | days since 1980-01-01; range 1..17155 (1980-01-02 .. 2026-12-21) | `rpt.usp_GetPairingID` `cl.CDATE = cr.CDATE`; roster join `cl.CDATE = r.DUTYDAY`; profiled |
| CROUTE | bigint | N | **Pairing (crew route) identifier**: a large numeric id of the pairing pattern; with CDATE it names one dated pairing instance. Same CROUTE recurs on many CDATEs (the same named trip operating on many days; 4,453 of 6,962 CROUTE values in 2026 appear on several dates). Never 0 in this table; `usp_GetPairingID` still filters `CROUTE <> 0`. 1:1 with `CRROUTE.DESC_` (the pairing name) across the whole history. | bigint (e.g. 288571274809) = `ROSTER.DUTYNO` for a pairing duty | `cl.CROUTE = r.DUTYNO`; profiled |

### 3.3 Position and attributes of the leg within the pairing
| Column | Type | Null | Business meaning | Encoding / allowed values | Evidence |
|---|---|---|---|---|---|
| ORDER_ | tinyint | Y | 0-based position of the leg inside the pairing instance, ordered by time. Exactly one leg with ORDER_ = 0 per pairing and the sequence is contiguous (1,401 of 1,401 pairings checked). | 0..12 | profiled |
| PAX | tinyint | Y | **Deadhead flag** - crew travels on the leg as a passenger (positioning) instead of operating it. 0 = operating crew; 1 = deadhead ("PAX"). 2026: 22,821 deadhead legs (all flights), 74,124 operating; ground legs always 0. | 0 / 1 | R3 `cl.PAX != 1` operated, `Leg_CLASS` 0.01 when PAX = 1; Get_Detailed_Pairing `Deadhead = PAX`, `@Include_Deadhead` filter `PAX = 0` / `PAX <= 1` |
| LIMTABLE | tinyint | Y | **Flight-time-limit table / crew complement index** (augmentation level): 0 = 2 pilots (standard crew), 1 = 3 pilots, 2 = 4 pilots (double crew). Cabin pairings carry 0. R3 converts `LIMTABLE` 0/1/2 to the pilot count 2/3/4 to select the EASA-style max-FDP row. 2026 flights: 0 = 87,906 (incl. 22,798 deadhead legs), 1 = 8,511, 2 = 528; values 1/2 occur only on flight-deck pairings (names beginning C / G). | 0 / 1 / 2 | R3 `PNT_Count` CASE (`WHEN cl.LIMTABLE = 0 THEN 2 WHEN 1 THEN 3 WHEN 2 THEN 4`); profiled |
| HOTEL | tinyint | Y | Layover/hotel code attached to the leg (non-zero on about 4.8% of 2026 rows, 37 distinct values 1-37). Not the layover length and not station-specific (the same code occurs at different arrival stations). Probably a reference to a layover/hotel booking class or slot for the overnight following the leg. Not used by planner-assist (hotel data is read from `HOTAC` by `CDATE`/`CROUTE`). | 0 = none | profiled (checked against gap-to-next-leg and ARR); **unknown meaning** |
| REMOVED | tinyint | Y | **Soft-delete flag**: 1 = the leg was removed from the pairing instance (the planner took the leg out); 0 = active. 187 rows overall (CDATE 2002-2023), 0 in 2024-2026. The fallback leg readers filter `cl.REMOVED = 0`. | 0 / 1 | R0 line 208, R3 line 37/182, R4, R5 |
| REPON | smallint | Y | **Report-on lead time in minutes** before the departure of the first leg of a duty: 60 (19,416 flight legs in 2026), 80 (10,756), 30 (1,569, mostly deadhead legs), 95/110 (rare); 0 on all non-first legs and ground legs. Matches the report offset hard-coded in R3/R4/R5 (60, 80 for overseas cabin crew, 30 for deadhead). Value profile is consistent with this reading; marked **inference**; R3 lists it as "not used". | minutes | profiled; R3 comment "CREWLEG.REPON / REPOFF (not used)"; R3 constants `@REPORT_OFFSET_MIN = -60`, `-80`, `-30` |
| REPOFF | smallint | Y | Debrief (report-off) lead time after the last leg of a duty in minutes. 0 on all 2026 rows (debrief offset 15 min is hard-coded in the procedures instead). | minutes | profiled; naming inference |
| CLEGMISC | smallint | Y | Miscellaneous per-leg code; non-zero on 2.7% of 2026 flight legs (153 distinct values up to 335) and 3 ground legs. Meaning not determinable from code or data. | | profiled; **unknown - not used by any procedure** |
| EXTRAPOSCODE | tinyint | Y | Extra-position code (e.g. supernumerary/observer position code on the leg). 0 on all 2026 rows. | | naming inference; profiled |
| INFLTREST | smallint | Y | In-flight rest facility class (relevant for augmented crew rest). 0 on every 2026 flight leg; R3 documents "CREWLEG.INFLTREST would be the data source but it is 0 on every 2026 flight leg", therefore the procedure assumes class 3. | | R3 line 102; profiled |

### 3.4 Flag bytes
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| LGFLAGS | tinyint | Y | Leg flag byte 1 - unknown, not used. Only 1 non-zero row (16) in 2026. | bit flags | profiled |
| LGFLAGS_2 | tinyint | Y | Leg flag byte 2 - unknown, not used (all 0/NULL). | bit flags | profiled |
| LGFLAGS_3 | tinyint | Y | Leg flag byte 3 - unknown, not used; 128 on 40 rows, 32 / 192 on a few. | bit flags | profiled |
| LGFLAGS_4 | tinyint | Y | Leg flag byte 4 - all 0. | bit flags | profiled |
| LGFLAGS_5 | tinyint | Y | Leg flag byte 5 - all 0. | bit flags | profiled |
| LGFLAGS_6 | tinyint | Y | Leg flag byte 6. **Value 64 (bit 7) = "manual acclimatisation" flag**: the planner manually marked the leg as starting/ending a change of acclimatisation state for the crew (used for the EASA acclimatisation chain). R3 `Case When cl.LGFLAGS_6 = 64 Then 1 else 0 end As Manual_Acclim_Flag`. 924 of 99,984 2026 rows. | bit flags; = 64 | R3, R3 Batch, R4 |
| LGFLAGS_7 | tinyint | Y | Leg flag byte 7 - all 0. | bit flags | profiled |
| LGFLAGS_8 | tinyint | Y | Leg flag byte 8 - all 0. | bit flags | profiled |

## 4. Keys & relationships

**Two keys meet here.**

1. **Composite flight key** `(DAY, DEP, CARRIER, FLT, LEGCD)` - identifies the flight leg; identical to `LEGMAIN`'s PK and to `ROSTER.(LEG_DAY, LEG_DEP, LEG_CARRIER, LEG_FLT, LEG_LEGCD)`.
2. **Pairing key** `(CDATE, CROUTE)` - identifies the pairing instance; identical to `CRROUTE`'s PK and to `ROSTER.(DUTYDAY, DUTYNO)`.

The full PK is flight key + pairing key (7 columns) because one flight leg is shared by several pairings.

| To | Cardinality | Exact join predicate (from code) | Source |
|---|---|---|---|
| CRROUTE (pairing header) | N : 1 | `cl.CDATE = cro.CDATE AND cl.CROUTE = cro.CROUTE` (in `usp_GetPairingID`: `INNER JOIN TSC.dbo.CRROUTE cr ON cl.CDATE = cr.CDATE AND cl.CROUTE = cr.CROUTE`). Measured: all 556,776 distinct (CDATE, CROUTE) of CREWLEG exist in CRROUTE and all 11,876 CRROUTE rows of days 17000-17100 have at least one CREWLEG row. | R0 195, R3 36, R3 178, R4 224, R5 244, usp_GetPairingID |
| LEGMAIN (flight leg) | N : 1 (for FLT > 0) | `legs.[DAY] = lm.[DAY] AND legs.[CARRIER] = lm.[CARRIER] AND legs.[FLT] = lm.[FLT] AND legs.[DEP] = lm.[DEP] AND legs.[LEGCD] = lm.[LEGCD]`. 96,945 of 96,945 2026 flight rows match. | rpt.Get_Detailed_Pairing line 185; R0 196-198 (`lm.DEP = cl.DEP AND lm.CARRIER = cl.CARRIER AND lm.[DAY] = cl.[DAY] AND lm.FLT = cl.FLT AND lm.LEGCD = cl.LEGCD`) |
| CRLEGGROUND (ground leg) | 1 : 0..1 (only when FLT < 0) | `clg.DEP = cl.DEP AND clg.CARRIER = cl.CARRIER AND clg.[DAY] = cl.[DAY] AND clg.FLT = cl.FLT AND clg.LEGCD = cl.LEGCD AND clg.CDATE = cl.CDATE AND clg.CROUTE = cl.CROUTE` (full 7-column key) | R0 199-202, R3 179, R4 225 |
| LEGTIMES | N : 0..1 | `lts.[DAY] = cl.[DAY] AND lts.DEP = cl.DEP AND lts.CARRIER = cl.CARRIER AND lts.FLT = cl.FLT AND lts.LEGCD = cl.LEGCD` (flight key only; pairing columns not used) | R0 203-205 |
| ROSTER (documented by someone else) | 1 : N (one row per crew member on the leg of the pairing) | Predicate as used in code: `cl.DEP = r.LEG_DEP AND cl.CARRIER = r.LEG_CARRIER AND cl.[DAY] = r.LEG_DAY AND cl.FLT = r.LEG_FLT AND cl.LEGCD = r.LEG_LEGCD AND cl.CDATE = r.DUTYDAY AND cl.CROUTE = r.DUTYNO`. Also written `r.DUTYDAY = cro.CDATE AND r.DUTYNO = cro.CROUTE` to reach the pairing header. In a 8,454-row roster sample all flight rows with `DUTYNO > 0` matched CREWLEG. | R3 283, R4 384 and 1187, R5 388, rpt.CalculateCrewFTC 238 |
| HOTAC | 1 : N | `htc.CDATE = pb.CDate AND htc.CROUTE = pb.CRoute` (hotel nights of the pairing; HOTAC has own CHECKINDAY / CROUTE columns) | rpt.Get_Detailed_Pairing |
| vvPositions (via CRROUTE.CREWNUM) | | required complement per position id comes from the header, not from CREWLEG | rpt.Get_Detailed_Pairing `complement` CTE |

**Why both keys appear in the roster predicate.** A roster row says *"crew member X works leg F as part of pairing P"*. Because the same leg belongs to several pairings, matching `ROSTER` to `CREWLEG` on the flight key alone would multiply rows; the predicate therefore adds the pairing key `cl.CDATE = r.DUTYDAY AND cl.CROUTE = r.DUTYNO`. `ROSTER.DUTYNO <= 0` is not a pairing: it is a stand-alone activity (negative `CRCODES.ID` such as -1, -2, -117 ...), which has no CRROUTE/CREWLEG rows.

**Cardinalities.** pairing instance (CRROUTE) 1 : N legs (CREWLEG); flight leg (LEGMAIN) 1 : N pairing instances (CREWLEG); so LEGMAIN : CRROUTE is N : M through CREWLEG.

## 5. Encoding conventions & gotchas

- **`FLT < 0` rows are ground activities**, not flights. They never match LEGMAIN; their times are in `CRLEGGROUND.STD/STA` (minutes UTC from `DAY`). Any "count the flights of the pairing" query must add `FLT > 0` (or inner-join LEGMAIN).
- **Filter `REMOVED = 0`.** The fallback readers use it; removed legs are history (none after 2023).
- **Deadhead (`PAX = 1`) legs are in the pairing** and count as duty but not as operated flight time; Get_Detailed_Pairing exposes `@Include_Deadhead` (0: only `PAX = 0`, otherwise `PAX <= 1`).
- **Same leg in many pairings.** Counting rows by flight key is not counting flights. Use `COUNT(DISTINCT ...)` or filter to one pairing.
- **`CROUTE = 0`** is filtered in `usp_GetPairingID` (`cl.CROUTE <> 0`), but no CREWLEG row has CROUTE = 0 (0 of 1,851,571) - a defensive filter.
- **CDATE vs DAY.** CDATE is the pairing's start date (UTC day number of the first leg); legs of a multi-day pairing have DAY > CDATE. `ROSTER.DUTYDAY` also equals CDATE for every leg of the pairing, not the leg's own day.
- **Pairing name is not unique per date across time but is unique per CROUTE**: `CRROUTE.DESC_` ↔ `CROUTE` is 1:1 over the whole history (44,201 pairings); `(CDATE, DESC_)` is unique, so `PAIRING_ID + date` safely resolves to one (CDATE, CROUTE). The R3 comment "4,417 of 6,877 CRROUTE names in 2026 are reused on several dates" means the same pairing pattern operates on many dates - partition by pairing instance `(ID, DUTYDAY, Duty_Number)`, not by name.
- **Day numbers are UTC.** A leg's `DAY` is the UTC date of departure, which is not necessarily the local date at the departure station.
- **Time-window access:** `CREWLEG_INDEX_1 (CDATE, CROUTE)` is the supporting index for pairing -> legs; to find pairings flying a given flight leg filter on the full flight key (PK prefix). Do **not** scan by `FLT` alone.

## 6. How the planner-assist procedures use it

| Procedure | Columns | Filter / purpose |
|---|---|---|
| `rpt.usp_GetPairingID` | DAY, FLT, CARRIER, LEGCD, CDATE, CROUTE | Given a *flight* (`@PAIRING_DATE` as DAY, `@PAIRING_FLT`, `CARRIER = 1`, `LEGCD = ' '`) finds the distinct pairings that carry it (`CROUTE <> 0`), joins `CRROUTE` for the pairing name (`DESC_`), then `ROSTER` (`fr.CDATE = r.DUTYDAY AND fr.CROUTE = r.DUTYNO AND r.LEG_FLT = @PAIRING_FLT AND r.DUTYNO > 0`) to list *other* pairings (name differs from the input) whose crew sits on the same flight in the requested position group (`POS IN (1, 2)` for CM/PO, else `POS > 2`). Business use (inference): "which other trips fly this flight, so a drafted crew member could be swapped". |
| `rpt.Get_Detailed_Pairing` | DAY, DEP, CARRIER, FLT, LEGCD, CDATE, CROUTE, PAX | `legs` CTE: `SELECT DISTINCT ... WHERE CDATE = @TargetCDate AND CROUTE = @TargetCRoute`; PAX becomes the output column `Deadhead`; deadhead filter `@Include_Deadhead = 0 AND PAX = 0` or `<> 0 AND PAX <= 1`. Joined to LEGMAIN, then to ROSTER and a vacancy sequence (positions required by `CRROUTE.CREWNUM` minus rostered crew), HOTAC night-stops, categories. |
| `dbo.R0_GetDraftList` | CDATE, CROUTE, key, REMOVED, FLT | Fallback: pairing start/end when the pairing has no ROSTER rows (`cl.REMOVED = 0`, `cl.FLT < 0` -> use CRLEGGROUND times, else LEGMAIN/LEGTIMES). |
| `dbo.R3_Get_Violations_RestTime` (+ `_Batch`) | key, CDATE, CROUTE, REMOVED, PAX, LIMTABLE, LGFLAGS_6 | (1) Existence check of the pairing's legs (`EXISTS ... cl.REMOVED = 0`); (2) fallback insert of the DRAFTED legs from the pairing definition; (3) per leg: `PNT_Count` from LIMTABLE (2/3/4 pilots; NULL for ground legs), `Manual_Acclim_Flag = LGFLAGS_6 = 64`, `PAX` for deadhead logic (operated = `LEG_FLT >= 0 AND ISNULL(PAX,0) <> 1`; `LEG_CLASS` 0.01 deadhead / 1.0 ground / 100.0 flight). Rules: EASA FDP table / FD-PCA-3830 rest and acclimatisation. |
| `dbo.R4_Get_Violation_FDP` | key, CDATE, CROUTE, REMOVED, PAX, LGFLAGS_6 | Same fallback and PAX / acclimatisation logic; FDP limit and block-time (FD-CAR-3300 / CAR 700.103) evaluation; deadhead legs are listed with `ISNULL(cl.PAX, 0)`. |
| `dbo.R5_Get_Violation_FTC` / `rpt.CalculateCrewFTC` | key, CDATE, CROUTE, REMOVED, PAX | Flight-time credit: deadhead (PAX = 1) pilots credited full leg duration, cabin crew half (or 0 for surface transport shorter than 60 min); fallback legs from pairing definition (`R5-17`). |
| R1, R2 | indirect | Call `rpt.Get_Detailed_Pairing`. |

## 7. Typical query patterns

```sql
-- 1. Legs of a pairing (name + start date) with deadhead flag, flights only
DECLARE @cdate int = DATEDIFF(DAY,'1980-01-01','2026-11-10');
SELECT cl.ORDER_, cl.DAY, cl.DEP, lm.ARR, cl.CARRIER, cl.FLT, cl.LEGCD, cl.PAX, cl.LIMTABLE
FROM TSC.dbo.CRROUTE cr
JOIN TSC.dbo.CREWLEG cl ON cl.CDATE = cr.CDATE AND cl.CROUTE = cr.CROUTE
JOIN TSC.dbo.LEGMAIN lm ON lm.DAY = cl.DAY AND lm.DEP = cl.DEP AND lm.CARRIER = cl.CARRIER
                       AND lm.FLT = cl.FLT AND lm.LEGCD = cl.LEGCD
WHERE cr.DESC_ = 'C0290' AND cr.CDATE = @cdate
  AND cl.REMOVED = 0 AND cl.FLT > 0
ORDER BY cl.ORDER_;

-- 2. Which pairings carry a given flight (flight key -> pairings)
SELECT cr.DESC_ AS pairing, cr.CDATE, cl.PAX, cl.LIMTABLE
FROM TSC.dbo.CREWLEG cl
JOIN TSC.dbo.CRROUTE cr ON cr.CDATE = cl.CDATE AND cr.CROUTE = cl.CROUTE
WHERE cl.DAY = DATEDIFF(DAY,'1980-01-01','2026-11-10')
  AND cl.CARRIER = 1 AND cl.FLT = 326 AND cl.LEGCD = ' ' AND cl.REMOVED = 0;

-- 3. Ground activities inside pairings of one start date, with activity code and times
SELECT cr.DESC_, c.CC AS activity_code, g.DEP AS station, g.STD, g.STA
FROM TSC.dbo.CREWLEG cl
JOIN TSC.dbo.CRLEGGROUND g ON g.DAY = cl.DAY AND g.DEP = cl.DEP AND g.CARRIER = cl.CARRIER
                          AND g.FLT = cl.FLT AND g.LEGCD = cl.LEGCD AND g.CDATE = cl.CDATE AND g.CROUTE = cl.CROUTE
JOIN TSC.dbo.CRROUTE cr ON cr.CDATE = cl.CDATE AND cr.CROUTE = cl.CROUTE
LEFT JOIN TSC.dbo.CRCODES c ON c.ID = cl.FLT
WHERE cl.CDATE = DATEDIFF(DAY,'1980-01-01','2026-11-10') AND cl.FLT < 0;

-- 4. Number of operating (non-deadhead) flight legs per pairing starting in a window
SELECT cr.DESC_, cr.CDATE, COUNT(*) AS operated_legs
FROM TSC.dbo.CREWLEG cl
JOIN TSC.dbo.CRROUTE cr ON cr.CDATE = cl.CDATE AND cr.CROUTE = cl.CROUTE
WHERE cl.CDATE BETWEEN 17108 AND 17115 AND cl.FLT > 0 AND cl.REMOVED = 0 AND cl.PAX = 0
GROUP BY cr.DESC_, cr.CDATE;
```

## 8. Data profile

Measured 2026-11-03.

- Rows 1,851,571; DAY 1..17159; CDATE 1..17155 (max = 2026-12-21); distinct CARRIER 311, carrier 1 = 1,422,329 rows (76.8%).
- Rows by CDATE year: 2002 5,897; 2005 50,541; 2010 65,479; 2015 88,492; 2019 112,015; 2020 38,905; 2021 11,203; 2022 78,942; 2023 95,208; 2024 109,993; 2025 104,801; 2026 99,984 (of which 3,039 ground and 96,945 flight legs). 1980: 532 rows (test data).
- FLT: min -497, max 9999; 86,494 negative rows (distinct codes 254 in CRLEGGROUND).
- CROUTE = 0: 0 rows; CDATE = 0: 0 rows.
- DAY - CDATE (2026 flight rows): 0..11 (52,811 of 99,984 pairings rows are on a later day than the pairing start, including ground rows).
- 2026: PAX = 1 on 22,821 rows (22.8%); LIMTABLE 0/1/2 = 90,945 / 8,511 / 528; REMOVED = 0 on all; HOTEL non-zero 4,912 rows (37 distinct values, most frequent 11 = 1,045, 21 = 914, 30 = 772, 26 = 202, 8 = 175, 31 = 168, 3 = 151); REPON 0 = 65,198, 60 = 19,416, 80 = 10,756, 30 = 1,569, 95 = 4, 110 = 2 (flight legs); REPOFF = 0 on all; INFLTREST = 0 on all; EXTRAPOSCODE = 0 on all; LGFLAGS_6 = 64 on 924; CLEGMISC non-zero on 2,591.
- Legs per pairing (days 17000-17100, flight legs, REMOVED = 0): 1 leg 166; 2 legs 7,866; 3 legs 2,073; 4 legs 1,294; 5 legs 288; 6 legs 85; 7 legs 14; 8 legs 6; 9 legs 3; 10 legs 4.
- Pairings per flight leg (home carrier, days 17040-17050): 1 -> 3 legs; 2 -> 219; 3 -> 353; 4 -> 182; 5 -> 74; 6 -> 46; 7 -> 14; 8 -> 4; 9 -> 3; 11 -> 1; 14 -> 1.
- Referential integrity (2026): flight rows with a LEGMAIN row: 96,945 of 96,945; with a CRROUTE row: 96,945 of 96,945; ground rows with CRLEGGROUND: 3,039 of 3,039; distinct (CDATE, CROUTE) pairs of CREWLEG in CRROUTE: 556,776 of 556,776.

## 9. Open questions / confidence

- **High**: PK/keys, FLT < 0 = ground activity linked to CRLEGGROUND, REMOVED soft delete, PAX = deadhead, LIMTABLE -> pilot count 2/3/4, LGFLAGS_6 = 64 manual acclimatisation, CDATE = pairing start date = ROSTER.DUTYDAY, CROUTE = ROSTER.DUTYNO.
- **Medium (inference)**: REPON as report lead time and REPOFF as debrief lead time (value distribution 60/80/30 matches the offsets the procedures hard-code; R3 itself lists them as "open decision, not used").
- **Unknown**: HOTEL value domain (1-37, code not station-specific, not layover hours); CLEGMISC (153 distinct codes); LGFLAGS, LGFLAGS_2, LGFLAGS_3 bit meanings; INFLTREST and EXTRAPOSCODE are empty so cannot be interpreted from data.
- Which of the several pairings carrying a leg is "the" pilot or cabin pairing is only visible through `CRROUTE.CREWNUM` (required complement) and the name prefix (see CRROUTE.md), not in CREWLEG.
