# LEGTIMES  (Table)  - Actual / estimated movement times of a flown flight leg (1:1 extension of LEGMAIN)

## 1. Purpose & business meaning

**What a row is.** The *actual-operations record* of one flight leg: the times at which the aircraft really left the gate (off-block), took off, landed and arrived at the gate (on-block), plus the latest estimates (ETD / ETA) and a number of movement-message fields (engine start/stop, helicopter rotor / hoist times, fuel specific gravity) that the home airline mostly does not use. It is a **vertical extension of `LEGMAIN`**: same five-column key, at most one row per leg, created only once a leg has operated (or movement data has been received).

**Grain.** One row per `(DAY, DEP, CARRIER, FLT, LEGCD)` - the composite flight key (see LEGMAIN.md section 4). It has no crew or pairing columns: it describes the aircraft movement, independent of who is on board.

**Lifecycle.**
- No row exists while a leg is only scheduled. Cancelled legs never get a row (0 of 845 cancelled home-carrier legs in a 61-day window had one).
- Written by the operations-control / movement-message interface (column names MVT_* show movement-message input; manual entry is also possible) as the flight progresses; it is "post-flight actuals" data.
- At extraction the latest row is for 2026-10-28 (DAY 17102), six days before today, i.e. the interface is not real-time for this copy of the database. Rows go back to 2002-12-02 (DAY 8371).

**Who reads it (planner-assist).** Only as the "actual times" refinement of the scheduled times in LEGMAIN: when computing real duty and block time of historical legs (FDP, block-time limits, flight-time credit, rest) the procedures prefer actuals and fall back to schedule. The *priority order of the fields* is the key piece of business logic (section 6).

**Home carrier dominance.** 429,432 rows; 16 carrier ids; home carrier (`CARRIER = 1`) has 22,686 rows in 2026 and all rows from 2021 on.

## 2. Physical facts

| Item | Value |
|---|---|
| Database / schema | `TSC.dbo.LEGTIMES` |
| Type | Table |
| Rows (extraction) | 429,432 (single partition) |
| Primary key | `LEGTIMES_INDEX_0` UNIQUE `(DAY, DEP, CARRIER, FLT, LEGCD)` |
| Other indexes | none - all access is by the flight key (always join from LEGMAIN, ROSTER or CREWLEG) |
| Collation | `SQL_Latin1_General_CP1_CI_AS` on DEP and LEGCD (identical to LEGMAIN/ROSTER; the `COLLATE` hints in R0 and `rpt.CalculateCrewFTC` are redundant) |
| Width note | `len` in columns.json is bytes: DEP = nchar(4), LEGCD = nchar(1) |

Rows by year (all carriers / carrier 1): 2002 1,060/1,060; 2005 11,897/11,887; 2010 14,460/13,919; 2015 20,825/20,611; 2019 27,535/27,378; 2020 9,551/9,202 (pandemic); 2021 3,343/3,343; 2022 19,620; 2023 26,267; 2024 27,616; 2025 26,617; 2026 (to 10-28) 22,686.

## 3. Column dictionary

All time columns are **minutes after 00:00 UTC of the row's DAY** (the scheduled departure day of the leg), `smallint`, nullable, may be negative (before midnight of DAY: min BLOF = -123) or above 1440 (after midnight: max OPSATA = 3057). Procedure code always converts with `DATEADD(MINUTE, x, DATEADD(DAY, r.LEG_DAY, '1980-01-01'))`, i.e. relative to **LEG_DAY = DAY**, not to the actual calendar day of the event.

### 3.1 Key
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| DAY | smallint | N | Scheduled-departure day (UTC) of the leg; part 1 of the flight key. | days since 1980-01-01 | R3/R4/R5 `lts.DAY = r.LEG_DAY` |
| DEP | nchar(4) | N | Departure airport (IATA) ; part 2. | 3-letter code | R0 `lts.DEP = r.LEG_DEP` |
| CARRIER | smallint | N | Carrier id (`vvCarriers.ID`); part 3. 16 distinct ids; 1 = home carrier. | | R0 `lts.CARRIER = r.LEG_CARRIER` |
| FLT | smallint | N | Flight number; part 4. | | R0 |
| LEGCD | nchar(1) | N | Leg code; part 5 (blank = normal leg, A-D = return legs). | | R0 |

### 3.2 Estimated and operational times
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| ETD | smallint | Y | Estimated (revised) time of departure after a re-estimate; populated only when operations revised the departure (1,750 of 7,453 legs in days 17000-17100). Differs from STD in only some cases. | UTC minutes of DAY | R3 `lts.ETD` as 2nd departure fallback; R4 block pair ETD/ETA |
| ETA | smallint | Y | Estimated (revised) time of arrival; 7,410 of 7,453 legs populated. | UTC minutes of DAY (may exceed 1440) | R0 `COALESCE(lts.BLON, lts.ETA, lm.STA)`; R3 |
| OPSATD | smallint | Y | Operational actual time of departure = actual off-block as recorded by the operations record (the number crew-compliance treats as authoritative). Equals BLOF in 7,181 of 7,453 legs; NULL on 576 of 22,686 2026 legs. | UTC minutes of DAY | R3 `Leg_Scheduled_duration` first choice; R4 block times pair (OPSATD, OPSATA) |
| OPSATA | smallint | Y | Operational actual time of arrival = actual on-block. Equals BLON in 7,120 of 7,453 legs. | UTC minutes of DAY | R3 `COALESCE(lts.OPSATA, lts.BLON, ...)` for arrival; R4 |
| OPSTKOFF | smallint | Y | Operational actual take-off time (wheels off). Equals TKOF in 7,233 of 7,453 sampled legs; non-zero on 387,506 rows overall. | UTC minutes of DAY | profiled; unused by procedures |
| OPSTDOWN | smallint | Y | Operational actual touch-down time (wheels on). | UTC minutes of DAY | profiled; unused |

### 3.3 Block / flight times (movement messages)
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| BLOF | smallint | Y | **Block-off**: actual time the aircraft left the gate/stand (actual departure). Equals STD + DDLY of LEGMAIN in 98.9% of sampled legs. Present on all but 48 of 429,432 rows. | UTC minutes of DAY | R3/R4/R5 `lts.BLOF`; R4 block-time pair (BLOF, BLON) |
| BLON | smallint | Y | **Block-on**: actual time the aircraft arrived at the gate (actual arrival). Equals STA + ADLY in 98.1% of sampled legs; > 1440 on 1,291 of 7,453 sampled legs (lands after UTC midnight). | UTC minutes of DAY | R0 `COALESCE(lts.BLON, lts.ETA, lm.STA)`; R3/R4/R5 |
| TKOF | smallint | Y | Actual take-off (wheels off) as flown; always later than BLOF (7,414 of 7,414 sampled non-null). Non-zero on 427,484 rows. | UTC minutes of DAY | profiled |
| TDOWN | smallint | Y | Actual touch-down (wheels on); earlier than BLON. | UTC minutes of DAY | profiled |
| ESTTKOFF | smallint | Y | Estimated take-off time from movement message; **0 on every row (never populated)**. | | profiled (0 non-zero of 429,432) |
| ESTTDOWN | smallint | Y | Estimated touch-down time; **0 on every row**. | | profiled |
| FIRSTATD | smallint | Y | First reported actual time of departure (before later corrections); **0 on every row**. | | profiled |
| FIRSTROUT | smallint | Y | First routing/route-out time; **0 on every row**. | | profiled |

Block time of a leg (minutes) = `OPSATA - OPSATD` or `BLON - BLOF` (see section 6). Air time = `TDOWN - TKOF`.

### 3.4 Engine / rotor / hoist / fuel fields (movement-message side, mostly unused by this airline)
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| ENGON | smallint | Y | Engine-start time (engine on) recorded manually. Non-zero on 8,104 rows overall (older years); NULL/0 in 2026. | UTC minutes | profiled |
| ENGOFF | smallint | Y | Engine-shutdown time. Non-zero 8,105 rows overall. | UTC minutes | profiled |
| MVT_ENGINEON | smallint | Y | Engine-on time from an automatic movement (MVT) message; 0 on every row. | | profiled |
| MVT_ENGINEOFF | smallint | Y | Engine-off time from an MVT message; 0 on every row. | | profiled |
| ROTORSSIGNON | smallint | Y | Helicopter rotors-turning start; 0 on every row (helicopter feature of the product). | | naming inference; profiled |
| ROTORSSIGNOFF | smallint | Y | Helicopter rotors stop; 0 on every row. | | naming inference; profiled |
| MVT_ROTORSSIGNON | smallint | Y | Rotors start from an MVT message; 0 on every row. | | profiled |
| MVT_ROTORSSIGNOFF | smallint | Y | Rotors stop from an MVT message; 0 on every row. | | profiled |
| MVT_SPEC_GR | real | Y | Fuel specific gravity from an MVT message; non-zero on 804 rows only. | | naming inference; profiled |
| SPEC_GR | real | Y | Fuel specific gravity (density) used for the leg; non-zero on 57,476 rows. | | naming inference; profiled |
| HOISTTIME | smallint | Y | Helicopter hoist time (minutes of hoist operation); 0 on every row. | | naming inference; profiled |
| MVTHOISTTIME | smallint | Y | Hoist time from an MVT message; non-zero on 1,293 rows. | | naming inference; profiled |

None of the columns in 3.4 is read by any planner-assist procedure.

## 4. Keys & relationships

**Natural key / PK**: composite flight key `(DAY, DEP, CARRIER, FLT, LEGCD)`.

| To | Cardinality | Exact join predicate used in code | Source |
|---|---|---|---|
| LEGMAIN | 1 : 1 (LEGTIMES row optional; every LEGTIMES row has a LEGMAIN row: 22,686 of 22,686 in 2026) | `lts.DAY = lm.DAY AND lts.DEP = lm.DEP AND lts.CARRIER = lm.CARRIER AND lts.FLT = lm.FLT AND lts.LEGCD = lm.LEGCD` | implied; LEGMAIN joined separately on the same ROSTER columns in R3/R4/R5 |
| ROSTER (documented elsewhere) | 1 : N (the actual times apply to every crew member rostered on the leg) | `lts.DAY=r.LEG_DAY AND lts.DEP=r.LEG_DEP AND lts.CARRIER=r.LEG_CARRIER AND lts.FLT=r.LEG_FLT AND lts.LEGCD=r.LEG_LEGCD` (R3 line 285, R4 lines 386 and 1188, R5 line 390). R0 line 157-159 and `rpt.CalculateCrewFTC` line 240 write the same with `COLLATE SQL_LATIN1_GENERAL_CP1_CI_AS` on `DEP` and `LEGCD`. | R0/R3/R4/R5, CalculateCrewFTC |
| CREWLEG (pairing definition) | 1 : N (a leg appears in several pairings) | `lts.[DAY] = cl.[DAY] AND lts.DEP = cl.DEP AND lts.CARRIER = cl.CARRIER AND lts.FLT = cl.FLT AND lts.LEGCD = cl.LEGCD` | R0 lines 203-205 (fallback for unassigned pairings) |

The join from ROSTER/CREWLEG must **always be a LEFT JOIN**: scheduled-only legs, cancelled legs and legs in the last days before the extraction have no LEGTIMES row.

LEGTIMES has no link of its own to a pairing (CDATE/CROUTE) - to reach CRROUTE go via CREWLEG or ROSTER.

## 5. Encoding conventions & gotchas

- **UTC, anchored on DAY.** All minute columns are offsets from 00:00 UTC of the *scheduled departure day*. An actual on-block after midnight has a value above 1440 (BLON up to 3564, OPSATA up to 3057 in the table) and an actual departure before midnight a negative value (BLOF min -123; OPSATD min -1420 and OPSATA min -1275 are almost a full day early, probably data-entry or re-planned-day artefacts). Always add them to the DAY date, never to the actual calendar day.
- **NULL vs 0.** Missing = NULL for the main fields (BLOF NULL on 48 rows; OPSATD NULL on 40,716 rows - the field was introduced later; ETD NULL on 355,431 rows). The movement-message fields (ESTTKOFF, ESTTDOWN, FIRSTATD, FIRSTROUT, MVT_*) are stored as **0 when absent**, never NULL: do not interpret 0 as midnight. For BLOF/ETD a real 0 occurs (BLOF = 0 on 42 rows, ETD = 0 on 3 rows).
- **Priority of fields** (taken from the procedures): *departure*: OPSATD, then BLOF, then ETD, then LEGMAIN.STD; *arrival*: OPSATA, then BLON, then ETA, then LEGMAIN.STA. R4 additionally requires the pair (both OPSATD and OPSATA, or both BLOF and BLON, or both ETD and ETA) to be non-NULL before using that pair ("times in pairs": ETA alone gave NULL - 3300 design Q5).
- **ETD is rarely populated** (only 1,750 of 7,453 legs; 355,431 NULL overall) - an ETD without an ETA, or vice versa, must be ignored.
- **No row = not flown (yet).** Legs after 2026-10-28 and all cancelled legs have no row. 56 live past-dated home-carrier legs in 2026 (50 FLTYPE 2 scheduled, 6 FLTYPE 4 ferry) also lack one - so a missing row on a past, live leg is possible (reason not determined; inference: no movement data was recorded).
- **No FLT < 0.** Ground activities (negative FLT) have no LEGTIMES row (their times live in CRLEGGROUND / ROSTER.GRDDUTYBEG/END).
- **Performance:** only the PK exists; never scan by a time column - join from LEGMAIN/ROSTER by key with a DAY range.

## 6. How the planner-assist procedures use it

| Procedure | Columns | Use |
|---|---|---|
| `dbo.R0_GetDraftList` | BLON, ETA (+ key) | Pairing end = `COALESCE(lts.BLON, lts.ETA, lm.STA)` + debrief offset (UTC), converted to local time zone; used to size the date window of the draft analysis and the overlap test. |
| `dbo.R3_Get_Violations_RestTime` / `_Batch` | ETD, ETA, BLOF, BLON, OPSATD, OPSATA | Per-leg: (a) end of leg for rest: `COALESCE(lts.OPSATA, lts.BLON, lts.ETA, lm.STA, r.DEBRIEFTIME, 540)`; (b) departure fallback `ISNULL(lm.STD, ISNULL(lts.ETD, ...))`; (c) `Leg_Scheduled_duration`: block time = OPSATA-OPSATD, else BLON-BLOF, else ETA-ETD, else STA-STD (deadhead legs count 0 as "dry flight" - duration is only for operated legs); (d) end-of-duty with debrief in 4 flavours: override (ROSTER.DEBRIEFTIME), ATA (OPSATA/BLON), ETA, STA - chosen in that priority. |
| `dbo.R4_Get_Violation_FDP` | ETD, ETA, BLOF, BLON, OPSATD, OPSATA | Same four time flavours; FDP and rest are evaluated on actual end of duty; Phase 9B block-time limits (FD-CAR-3300A/B/C, CAR 700.103 / AC 5.11, 28/90/365-day block): off/on = OPSATD/OPSATA else BLOF/BLON else ETD/ETA else STD/STA. |
| `dbo.R5_Get_Violation_FTC` | BLOF, BLON, ETD, ETA | Flight-time credit (FTC) per leg: duration = `BLON - BLOF` when BLOF is not NULL, else `ETA - ETD`, else `STA - STD` (LEGMAIN). Deadheading cabin crew on a non-surface carrier get 50% of that duration, deadheading pilots 100%; end-of-duty uses `lts.BLON` + 15 min debrief (`lts.ETA` in the ETA flavour). |
| `rpt.CalculateCrewFTC` | BLOF, BLON, ETD, ETA | Same duration cascade and deadhead weighting as R5 for the roster extract. |
| `rpt.Get_Detailed_Pairing` | none | Pairing description is schedule-only; LEGTIMES is not joined. |

## 7. Typical query patterns

```sql
-- 1. Actual block times of home-carrier legs on one UTC day
SELECT lm.DEP, lm.ARR, lm.FLT, lm.LEGCD,
       DATEADD(MINUTE, lt.OPSATD, DATEADD(DAY, lm.DAY, '1980-01-01')) AS OffBlock_UTC,
       DATEADD(MINUTE, lt.OPSATA, DATEADD(DAY, lm.DAY, '1980-01-01')) AS OnBlock_UTC,
       lt.OPSATA - lt.OPSATD AS BlockMinutes
FROM TSC.dbo.LEGMAIN lm
JOIN TSC.dbo.LEGTIMES lt
  ON lt.DAY = lm.DAY AND lt.DEP = lm.DEP AND lt.CARRIER = lm.CARRIER AND lt.FLT = lm.FLT AND lt.LEGCD = lm.LEGCD
WHERE lm.DAY = DATEDIFF(DAY, '1980-01-01', '2026-10-20') AND lm.CARRIER = 1 AND lm.CANCELLED = 0;

-- 2. Best-available departure / arrival minute with schedule fallback (same priority as R3/R4)
SELECT lm.DAY, lm.FLT,
       COALESCE(lt.OPSATD, lt.BLOF, lt.ETD, lm.STD) AS Dep_Min,
       COALESCE(lt.OPSATA, lt.BLON, lt.ETA, lm.STA) AS Arr_Min
FROM TSC.dbo.LEGMAIN lm
LEFT JOIN TSC.dbo.LEGTIMES lt
  ON lt.DAY = lm.DAY AND lt.DEP = lm.DEP AND lt.CARRIER = lm.CARRIER AND lt.FLT = lm.FLT AND lt.LEGCD = lm.LEGCD
WHERE lm.DAY BETWEEN 17090 AND 17110 AND lm.CARRIER = 1 AND lm.CANCELLED = 0;

-- 3. Delay statistics (departure delay vs schedule) for a month
SELECT AVG(lt.BLOF - lm.STD) AS avg_dep_delay_min, COUNT(*) AS legs
FROM TSC.dbo.LEGMAIN lm
JOIN TSC.dbo.LEGTIMES lt
  ON lt.DAY = lm.DAY AND lt.DEP = lm.DEP AND lt.CARRIER = lm.CARRIER AND lt.FLT = lm.FLT AND lt.LEGCD = lm.LEGCD
WHERE lm.DAY BETWEEN 17042 AND 17071 AND lm.CARRIER = 1 AND lt.BLOF IS NOT NULL;
```

## 8. Data profile

Measured 2026-11-03.

- Rows 429,432; DAY 8371 .. 17102 (2002-12-02 .. 2026-10-28); 16 carriers.
- Days 17000-17100, carrier 1 (7,453 legs): ETD populated 1,750; ETA 7,410; BLOF 7,453; BLON 7,453; TKOF 7,414; TDOWN 7,414; OPSTKOFF 7,256; OPSTDOWN 7,256; OPSATD 7,261; OPSATA 7,261 (the 192 missing OPS pairs are legs where only BLOF/BLON were recorded).
- In the same sample: DDLY = BLOF - STD on 7,372 legs; ADLY = BLON - STA on 7,310; OPSATD = BLOF on 7,181; OPSATA = BLON on 7,120; BLON > 1440 on 1,291; TKOF > BLOF on all 7,414 non-null; ETD = STD on 796.
- Zero-everywhere: ESTTKOFF, ESTTDOWN, FIRSTATD, FIRSTROUT, MVT_ENGINEON/OFF, ROTORSSIGN*, MVT_ROTORSSIGN*, HOISTTIME.
- Home-carrier 2026 coverage: of 22,742 live legs with DAY <= 17102, 22,686 have a LEGTIMES row (the 56 missing are 50 scheduled-service and 6 ferry legs with no movement record - reason not determined); 160 cancelled and 4,492 removed legs before that date have none; 3,635 live legs after 17102 have none.
- Extremes: BLOF -123..2876; BLON max 3564; ETD -120..2520; OPSATD -1420..2517; OPSATA -1275..3057.

## 9. Open questions / confidence

- **High**: key, 1:1 with LEGMAIN, time anchoring on DAY in UTC, block-off/on = BLOF/BLON, take-off/touch-down = TKOF/TDOWN, field priority used by the procedures, "row exists only for flown legs".
- **Medium**: the distinction between OPSATD/OPSATA ("operational") and BLOF/BLON; they agree for about 96% of legs, so OPS* looks like the operations-controller-confirmed copy of the movement message; the other 4% need a business confirmation of which is the legally authoritative actual.
- **Unknown**: whether OPSATD values far from BLOF (e.g. -1420) are errors; ENGON/ENGOFF use in the past (older data only); whether ETD is a revised or an original estimate.
- Rotor / hoist columns are named after helicopter operations; they are 0 for this fixed-wing airline.
