# CRLEGGROUND  (Table)  - Ground (non-flying) activity legs inside crew pairings, with station and start/end time

## 1. Purpose & business meaning

**What a row is.** A crew *ground activity* that has been built into a pairing instance: e.g. a simulator session, training/PPC check, meeting, administrative or standby block that sits between or around the flights of a pairing. In AIMS such an activity is modelled as a pseudo-"flight" with a **negative flight number**: `FLT = -n`, where `n` is the activity code `CRCODES.ID` (`CRCODES.CC` holds the short code, e.g. `SIMI`, `APT`, `MAL`, `PPC2`, `REU`, `TAPS`). Because the flight tables (`LEGMAIN`) hold only real flights, the time and place of those ground legs are stored here.

**Grain.** One row per `(DAY, DEP, CARRIER, FLT, LEGCD, CDATE, CROUTE)` - the **composite flight key** (pseudo-flight) plus the **pairing key** (which pairing instance it belongs to). The primary key and index layout are identical to `CREWLEG`; **CRLEGGROUND is the 1:1 time/place extension of the `FLT < 0` rows of `CREWLEG`**: the row count (86,494) equals the number of CREWLEG rows with `FLT < 0` exactly, and 3,039 of 3,039 2026 rows have their CREWLEG twin.

**Lifecycle.** Created when a planner inserts a ground activity into a pairing in the crew-pairing module; edited with the pairing; kept as history (since 2002). Always `CARRIER = 1` (home airline; 1 distinct value in the table).

**Why it matters.** A ground activity is duty for the crew member: it counts towards duty periods, rest and flight-time-credit (FTC) calculations. `ROSTER` rows of such activities also carry `GRDDUTYBEG` / `GRDDUTYEND` per crew; CRLEGGROUND is the *pairing-definition* source of the same times and is the **only** source of times when nobody has been assigned to the pairing (no ROSTER rows yet).

**Who reads it (planner-assist).** R0, R3 (+ Batch), R4, R5 and `rpt.CalculateCrewFTC`, always as a LEFT JOIN with the full 7-column key, to get `STD` / `STA` of a ground leg.

## 2. Physical facts

| Item | Value |
|---|---|
| Database / schema | `TSC.dbo.CRLEGGROUND` |
| Type | Table |
| Rows (extraction) | 86,494 (single partition) |
| Primary key | `CRLEGGROUND_INDEX_0` UNIQUE `(DAY, DEP, CARRIER, FLT, LEGCD, CDATE, CROUTE)` |
| Other index | `CRLEGGROUND_INDEX_1 (CDATE, CROUTE)` - all ground legs of a pairing instance |
| Collation | `SQL_Latin1_General_CP1_CI_AS` on DEP, ARR, LEGCD |
| Width note | DEP/ARR = nchar(4); LEGCD = nchar(1) (`len` in columns.json is bytes) |
| History | CDATE 1980-01-02 (296 test rows) and 2002-2026: 2022 4,993; 2023 6,163; 2024 4,415; 2025 3,885; 2026 3,039 |

## 3. Column dictionary

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| DAY | smallint | N | UTC calendar day on which the ground activity starts (day number). It can be later than CDATE (for multi-day pairings): in 2026, 2,303 of 3,039 rows have DAY > CDATE (up to 9 days after), the rest DAY = CDATE. Always equals the DAY of the CREWLEG twin. | days since 1980-01-01 | R0 `clg.[DAY] = r.LEG_DAY`; profiled |
| DEP | nchar(4) | N | Station where the activity takes place (IATA code; home base YUL in 66,192 of 86,494 rows, then YYZ, MIA, YMX, LGW, YVR, YQB, CDG ...; 165 distinct stations). A ground activity has no travel, so ARR = DEP on every row. | 3-letter IATA; one row has a 4-char value | profiled; R0 `clg.DEP = r.LEG_DEP` |
| CARRIER | smallint | N | Carrier id of the pseudo-flight - always 1 (home carrier). | 1 | profiled (1 distinct value) |
| FLT | smallint | N | **Negative activity number = CRCODES.ID (CRCODES.ID is itself <= 0; no sign flip)**; never positive in this table (-497 .. -1; 254 distinct codes overall, 115 in 2026). Identifies *what* the activity is, e.g. -428 = code `APT`, -17 = `MAL`, -128 = `SIMI`, -468 = `PPC2`, -475 = `PPC3`, -12 = `REU`, -463 = `SM22`, -385 = `TSM2`, -146 = `SMP2`, -166 = `TAPS`, -104 = `ADMP`. (Descriptions of the codes are documented in CRCODES.md: APT Aircraft Procedures Trainer, SIMI initial simulator, PPC2 / PPC3 proficiency checks (A321 / other type), SM22 / SM21 / SM31 / SM32 simulator phases, TSM2 / TSM3 simulator-session trainer, SMP2 passive simulator 320, TAPS APS-MCC instructor, REU meeting, ADMP chief-pilot office (administrative), MAL sickness code. The overwhelming majority of ground legs in pairings are therefore training / checking events.) | negative smallint; join `CRCODES.ID = CLG.FLT` | R3 `from tsc.dbo.CRCODES crc where crc.ID = r.LEG_FLT` (duty report/debrief minutes and FTC are read from the code record); R5 line 456 `c.ID = r.LEG_FLT` |
| LEGCD | nchar(1) | N | Leg code to disambiguate two identical activities on the same day at the same station within the same key; blank on 85,939 rows, letters 'A'..'B' etc. on 555. | blank / letter | profiled |
| CDATE | smallint | N | Pairing start day (day number) of the pairing instance to which the activity belongs. `CRROUTE.CDATE`. | days since 1980-01-01; range 1..17155 | R0 `clg.CDATE = r.DUTYDAY`; profiled |
| CROUTE | bigint | N | Pairing identifier of that pairing instance (`CRROUTE.CROUTE`, `ROSTER.DUTYNO`). | bigint | R0 `clg.CROUTE = r.DUTYNO` |
| AC | smallint | Y | Aircraft type (`vvAIRCTYPE.ACTYPE`) the activity is tied to - the simulator / equipment type the crew is training on; 0 = no specific type (1,132 of 3,039 2026 rows). 2026: 14 = 1,042; 4 = 668; 6 = 161; 16 = 31; one value 102 (not in `vvAIRCTYPE`, whose ids run 1-35 - stale or special code). One NULL row overall. | ACTYPE id | profiled; naming inference |
| ARR | nchar(4) | Y | Arrival station; always equal to DEP. Not read by any procedure. | | profiled (DEP <> ARR on 0 of 86,494 rows) |
| STD | smallint | Y | Start of the activity, minutes after 00:00 UTC of DAY. Range 0..1440. | UTC minutes since DAY | R3/R4 `DATEADD(MINUTE, clg.STD, DATEADD(DAY, clg.DAY, @BaseDate))` |
| STA | smallint | Y | End of the activity, minutes after 00:00 UTC of DAY (same scale as STD, so it can exceed 1440 if it ends after midnight: 10,823 rows). Range 1..2819; STA > STD on every row; mean duration 263 min in 2026 (min 1, max 1,310). | UTC minutes since DAY | R3/R4 `clg.STA`; profiled |

## 4. Keys & relationships

**Natural key / PK**: composite flight key of the pseudo-flight `(DAY, DEP, CARRIER, FLT, LEGCD)` + pairing key `(CDATE, CROUTE)`. Both keys are needed: the same activity (same negative FLT, day and station) is a different row for every pairing that contains it.

| To | Cardinality | Exact join predicate (from code) | Source |
|---|---|---|---|
| CREWLEG | 1 : 1 | `clg.DEP = cl.DEP AND clg.CARRIER = cl.CARRIER AND clg.[DAY] = cl.[DAY] AND clg.FLT = cl.FLT AND clg.LEGCD = cl.LEGCD AND clg.CDATE = cl.CDATE AND clg.CROUTE = cl.CROUTE` (CREWLEG has the matching `FLT < 0` row: 3,039 of 3,039 in 2026) | R0 199-202, R3 179, R4 225 |
| ROSTER (documented elsewhere) | 1 : N (one row per crew member scheduled on the activity) | `clg.DEP = r.LEG_DEP AND clg.CARRIER = r.LEG_CARRIER AND clg.[DAY] = r.LEG_DAY AND clg.FLT = r.LEG_FLT AND clg.LEGCD = r.LEG_LEGCD AND clg.CDATE = r.DUTYDAY AND clg.CROUTE = r.DUTYNO`. Measured: roster rows with `DUTYNO > 0 AND LEG_FLT < 0` matched CRLEGGROUND 44 of 44; flight rows (`LEG_FLT > 0`) never match; stand-alone activities (`DUTYNO <= 0`, e.g. -1, -2, -117; 16,071 sampled rows) never match - they are not part of a pairing. | R0 153-156, R3 284, R4 385, R5 389, CalculateCrewFTC 239 |
| CRROUTE | N : 1 | `clg.CDATE = cro.CDATE AND clg.CROUTE = cro.CROUTE` (not joined directly in code; implied by key identity) | |
| CRCODES | N : 1 | `crc.ID = r.LEG_FLT` (negative; CRCODES.ID holds the negative number) - the code record gives the activity's code `CC`, report/debrief minutes (bytes of `DATA_BEGIN_END`) and flags (rest / reserve) | R3 lines 258, 263, 269, 289; R5 456 |
| LEGMAIN | none | negative FLT never matches `LEGMAIN.FLT` (always > 0) - ground rows must use CRLEGGROUND | profiled |
| LEGTIMES | none | no actual times for ground activities | |

## 5. Encoding conventions & gotchas

- **Negative FLT is the discriminator.** `CREWLEG.FLT < 0` / `ROSTER.LEG_FLT < 0` -> look here. Procedures branch `CASE WHEN LEG_FLT < 0 THEN <ground logic using CRLEGGROUND / GRDDUTY*> ELSE <flight logic using LEGMAIN/LEGTIMES>`. Roster rows of the ground leg of *a pairing* are matched by the full 7-column key (with CDATE/CROUTE); a stand-alone activity in the roster is not in this table.
- **Times are UTC minutes from DAY** (same convention as LEGMAIN). `STA` may exceed 1440. Convert with `DATEADD(MINUTE, STD, DATEADD(DAY, DAY, '1980-01-01'))`. These times are **not local** - the ground activity occurs at `DEP`, so local time needs that airport's UTC offset.
- **DAY is the day the activity starts, not the pairing start**; CDATE is the pairing start (`DAY >= CDATE`). In the R3/R4 fallback the ground leg's DAY is used (`clg.DAY`) rather than CDATE.
- **Two sources of the same times.** `ROSTER.GRDDUTYBEG` / `GRDDUTYEND` (per crew member, can be individually changed) are what R0, R3 and R4 use for the start/end of a ground leg of an assigned crew; CRLEGGROUND `STD` / `STA` are used by those procedures when the draft is built from the pairing definition (the R3/R4 fallback inserts `clg.STD, clg.STA` into the `GRDDUTYBEG, GRDDUTYEND` slots) and in the ETD/ETA/ATD flavours of the leg times; R5 and `rpt.CalculateCrewFTC` read `clg.STD/STA` for every ground leg.
- **Duration not hours-credit.** `STA - STD` is the scheduled length of the activity (R3: `Case When r.LEG_FLT < 0 Then clg.STA - clg.STD`), but flight-time credit for the activity (`ACTIVITY_FTC`) comes from `CRCODES.DATA_BEGIN_END`, not from here.
- **No FK:** orphan checking is manual; in 2026 there are none.
- **Small table:** 3,039 rows for the current year; an unfiltered scan is cheap, but always filter by `CDATE` range for history.

## 6. How the planner-assist procedures use it

| Procedure | Columns | Filter / reason |
|---|---|---|
| `dbo.R0_GetDraftList` | key + CDATE/CROUTE, STD, STA | LEFT JOIN for roster legs with `LEG_FLT < 0` when computing pairing start/end: `CASE WHEN r.LEG_FLT < 0 THEN DATEADD(MINUTE, clg.STD, DATEADD(DAY, clg.DAY, @BaseDate)) ELSE ... lm.STD`; and end `clg.STA`. Also in the "pairing has no crew" fallback, driven from CREWLEG (`cl.FLT < 0`). |
| `dbo.R3_Get_Violations_RestTime` / `_Batch` | key + pairing key, STD, STA | (a) Fallback draft insert: `clg.STD, clg.STA` as ground start/end; (b) `LEG_START_WITH_REPORT_ETD/ATD` for ground legs = `clg.STD`, `LEG_END_WITH_DEBRIEF_ETA` = `clg.STA`; (c) `Leg_Scheduled_duration` for ground = `clg.STA - clg.STD`; rule family: duty period / rest (FD-PCA-3830, EASA FDP table). |
| `dbo.R4_Get_Violation_FDP` | same | Same logic; ground legs form part of the duty period (FDP / duty limits). |
| `dbo.R5_Get_Violation_FTC` | key + pairing key, STD, STA | Unlike R3/R4, R5 uses CRLEGGROUND for *all* ground legs of the roster and draft: duration `clg.STA - clg.STD` (line 296), leg start `DATEADD(MINUTE, clg.STD, DATEADD(DAY, clg.DAY, @BaseDate))` (line 340) and end `clg.STA` (lines 350, 361, 373); its fallback draft insert (R5-17) carries no GRDDUTYBEG/END at all. Purpose: flight-time credit (FTC) and duty time including ground activities. |
| `rpt.CalculateCrewFTC` | STD, STA | `CASE WHEN LEG_FLT < 0 THEN DATEADD(MINUTE, clg.STD, DATEADD(DAY, clg.DAY, @BaseDate))` start and `clg.STA` end of each ground leg for FTC/duty time. |

## 7. Typical query patterns

```sql
-- 1. Ground activities of a pairing instance, with the activity code
SELECT g.DAY, g.DEP AS station, c.CC AS activity_code, g.AC,
       DATEADD(MINUTE, g.STD, DATEADD(DAY, g.DAY, '1980-01-01')) AS start_utc,
       DATEADD(MINUTE, g.STA, DATEADD(DAY, g.DAY, '1980-01-01')) AS end_utc
FROM TSC.dbo.CRROUTE cr
JOIN TSC.dbo.CRLEGGROUND g ON g.CDATE = cr.CDATE AND g.CROUTE = cr.CROUTE
LEFT JOIN TSC.dbo.CRCODES c ON c.ID = g.FLT
WHERE cr.DESC_ = 'S321I' AND cr.CDATE = DATEDIFF(DAY,'1980-01-01','2026-11-10')
ORDER BY g.DAY, g.STD;

-- 2. Which activity codes are used most in a year (activity code frequency)
SELECT c.CC AS code, COUNT(*) AS n, AVG(g.STA - g.STD) AS avg_minutes
FROM TSC.dbo.CRLEGGROUND g
LEFT JOIN TSC.dbo.CRCODES c ON c.ID = g.FLT
WHERE g.CDATE BETWEEN DATEDIFF(DAY,'1980-01-01','2026-01-01') AND DATEDIFF(DAY,'1980-01-01','2026-12-31')
GROUP BY c.CC ORDER BY n DESC;

-- 3. All legs of a pairing - flights and ground activities together, times in UTC minutes
SELECT cl.ORDER_, cl.FLT, cl.DAY,
       COALESCE(lm.STD, g.STD) AS start_min, COALESCE(lm.STA, g.STA) AS end_min
FROM TSC.dbo.CREWLEG cl
LEFT JOIN TSC.dbo.LEGMAIN lm ON lm.DAY = cl.DAY AND lm.DEP = cl.DEP AND lm.CARRIER = cl.CARRIER
                            AND lm.FLT = cl.FLT AND lm.LEGCD = cl.LEGCD
LEFT JOIN TSC.dbo.CRLEGGROUND g ON g.DAY = cl.DAY AND g.DEP = cl.DEP AND g.CARRIER = cl.CARRIER
                               AND g.FLT = cl.FLT AND g.LEGCD = cl.LEGCD AND g.CDATE = cl.CDATE AND g.CROUTE = cl.CROUTE
WHERE cl.CDATE = DATEDIFF(DAY,'1980-01-01','2026-11-10') AND cl.CROUTE = 288571274809 AND cl.REMOVED = 0
ORDER BY cl.ORDER_;
```

## 8. Data profile

Measured 2026-11-03.

- Rows 86,494; all CARRIER = 1; DAY 2..17159; CDATE 1..17155; FLT -497..-1 (254 distinct codes); STD 0..1440, STA 1..2819; STA > 1440 on 10,823 rows; STA > STD on 86,494 rows; DEP = ARR on 86,494 rows; LEGCD blank on 85,939, non-blank 555 (values up to 'B').
- Rows by CDATE year: 2003 2,351; 2007 2,490; 2011 4,664; 2014 5,673; 2018 7,003; 2019 6,570; 2020 1,774; 2021 892; 2022 4,993; 2023 6,163; 2024 4,415; 2025 3,885; 2026 3,039; 1980 296 and 1981 1 (test data).
- 2026 (CDATE 16802..17166): 3,039 rows, 1,556 pairings with at least one ground leg (935 with several); 115 distinct codes; mean duration 263 min (min 1, max 1,310); DAY = CREWLEG.DAY on all rows; PAX = 0 on all; 376 of the ground legs are the first leg (ORDER_ = 0) of their pairing.
- Top 2026 codes (code, rows, mean minutes): APT 256 / 239; MAL 238 / 105; SIMI 230 / 240; PPC2 225 / 240; PPC3 192 / 240; REU 122 / 357; SM22 107 / 240; TSM2 107 / 236; SM32 89 / 240; TSM3 88 / 235.
- 2026 pairings containing ground legs by pairing-name prefix: S 1,897; J 297; D 289; F 175; T 106; G 79; C 73; V 62; H 34; N 22 (S-prefixed names dominate: S-pairings are the ones used for training/simulator sessions - inference).
- Top stations: YUL 66,192; YYZ 7,245; MIA 4,181; YMX 1,333; LGW 838; YVR 678; YQB 528; CDG 513 (165 stations total).
- AC (2026): 0 = 1,132; 14 = 1,042; 4 = 668; 6 = 161; 16 = 31; 102 = 2; 18 = 2; NULL = 1.

## 9. Open questions / confidence

- **High**: key structure, link to CREWLEG `FLT < 0`, times UTC minutes from DAY, `CRCODES.ID = FLT` join, fallback use in R0/R3/R4/R5.
- **Medium (inference)**: AC = equipment type of a simulator/training session. Activity-code descriptions are taken from CRCODES.md (written separately from the code's text field); `CRCODES` itself holds only the short code and a binary blob, no description column in columns.json.
- **Unknown**: the exact rule for non-blank LEGCD; the one `AC = 102` and one NULL `AC`; whether CRLEGGROUND times can differ from ROSTER.GRDDUTYBEG/END for assigned crews (planner code prefers the ROSTER values).

