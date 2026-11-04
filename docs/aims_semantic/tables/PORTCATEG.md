# PORTCATEG  (Table)  - Airport -> airport category membership (with validity period)

## 1. Purpose & business meaning
Tags **airports (stations)** with planner-defined **airport categories** - operational restrictions or special characteristics of an aerodrome (low-visibility airfield, "category C" airfield, cash payment for fuel,
only A310-and-smaller aircraft, short-runway restriction, vacuum toilets not allowed, 2 x A.D.F. requirement, avoid a given aircraft due to EGPWS). Row grain: one (station, category, active-from, active-to).
Category names are in `GENCAT` with `GENCATTYPE = 3`. Maintained by AIMS administrators (airport category setup); read by planner-assist to resolve rules of kind **SEL 5 "Flights via airport of following categories"** in R1 (certain flights for certain crews) and R2 (schedule with / with-not).
Sibling `PORTCATEG2` is the identical structure for the "additional" airport categories (GENCAT type 17; empty).

## 2. Physical facts
* `TSC.dbo.PORTCATEG`, base table, **18 rows** (2026-11-03).
* PK/unique clustered index `PORTCATEG_INDEX_0` on (STATION, CATEGIDX, ACTIVEBEG, ACTIVEEND): lookups are by station. No other index, no identity, no audit columns.
* (The metadata extract `columns.json` reports `nchar` lengths in **bytes**; the real declared lengths in characters are half of that and are used below.)

## 3. Column dictionary
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| STATION | nchar(4) | N | Airport/station code. | 3-letter IATA codes in the data (`CDG`, `MCI`, `LIS`, ...), declared nchar(4), space padded; equals `vvAirports.AIRPORT` and the leg's `LEGMAIN.DEP` / `ARR` (all 13 distinct stations exist in vvAirports). | rpt.Get_Detailed_Pairing.sql:267-273 (`pc.STATION = DEP` / `= ARR`); profiled |
| CATEGIDX | smallint | N | Airport category number; name = `GENCAT` row (`GENCATTYPE = 3`, `GENCATINDEX = CATEGIDX`). Also bit CATEGIDX of `SPEFRECDATA.AIRCAT` when `SEL = 5`. | Observed 1,2,3,4,5,7,8,18,20 (18 and 20 have **no** GENCAT type-3 name: GENCAT type 3 only defines 1..8, so they are invisible to the procedures). | rpt.Get_Detailed_Pairing.sql:267; profiled |
| ACTIVEBEG | smallint | N | First day of membership (AIMS day number, days since 1980-01-01). | 0 = since always (all rows). | rpt.Get_Detailed_Pairing.sql:268 |
| ACTIVEEND | smallint | N | Last day of membership. | days since 1980-01-01; 32767 = 2069-09-17 = open ended (all rows). | rpt.Get_Detailed_Pairing.sql:268 |

## 4. Keys & relationships
* Natural key = the whole PK.
* `PORTCATEG.STATION` -> `vvAirports.AIRPORT` (N:1) and to `LEGMAIN.DEP` / `LEGMAIN.ARR` (the leg's departure and arrival airport). Predicate: `pc.STATION = DEP` (departure categories) and `pc.STATION = ARR` (arrival categories), with `pc.ACTIVEBEG < (DAY + (STD/1440.0)) AND pc.ACTIVEEND > (DAY + (STA/1440.0))` (rpt.Get_Detailed_Pairing.sql:267-273).
* `PORTCATEG.CATEGIDX` -> `GENCAT (GENCATTYPE = 3, GENCATINDEX)` N:1: `gc.GENCATINDEX = pc.[CATEGIDX] AND gc.[GENCATTYPE] = 3`.

## 5. Encoding conventions & gotchas
* Day numbers; `smallint` open end = 32767.
* `PORTCATEG` and `CITYCATEG` are the `*CATEG` tables for which Get_Detailed_Pairing divides by `1440.0` (decimal): `ACTIVEBEG < DAY + STD/1440.0` includes a membership starting on the flight's own day when STD > 0 (but not when STD = 0), and `ACTIVEEND > DAY + STA/1440.0` **never** matches a membership whose last day is the flight's own day (DAY > DAY + fraction is always false).
  `PORTCATEG2`, `ACCATEG`, `ACCATEG2` and `COUNTRYCATEG` use integer division (`STD/1440`), i.e. a strict comparison at whole-day granularity. The boundary-day treatment is therefore inconsistent between tables (latent today: all PORTCATEG rows are 0..32767).
* Categories 18 and 20 attached to `MCI` have no name in GENCAT type 3 -> dropped by the inner join, they never reach a rule.
* The category applies to the **airport as an endpoint (departure or arrival)**, not to overflight. Rule kind 5 treats "via airport" as "departure OR arrival airport has the category".
* Station codes are space padded (`nchar(4)`); trim when comparing to text.

## 6. How the planner-assist procedures use it
* `rpt.Get_Detailed_Pairing`: `Dep_Airport_Categories` / `Arr_Airport_Categories` (`'| '`-joined GENCAT type-3 names) per flight leg (varchar(300) cut).
* R1/R2 rule kind 5: `OPENJSON(Subconditions_Raw_JSON,'$.Airport_Category')` categories (from `SPEFRECDATA.AIRCAT` bits via GENCAT type 3) are matched against the dep OR arr airport category text.
* Not used by R3-R5.

## 7. Typical query patterns
```sql
-- 1. Airport categories valid on a given day, with names
DECLARE @n int = DATEDIFF(DAY,'1980-01-01','2026-11-03');
SELECT LTRIM(RTRIM(p.STATION)) AS Station, p.CATEGIDX, LTRIM(RTRIM(g.DESC_)) AS Category
FROM TSC.dbo.PORTCATEG p
LEFT JOIN TSC.dbo.GENCAT g ON g.GENCATTYPE = 3 AND g.GENCATINDEX = p.CATEGIDX
WHERE p.ACTIVEBEG <= @n AND p.ACTIVEEND >= @n
ORDER BY p.STATION, p.CATEGIDX;

-- 2. Categories of the departure airport of recent legs (narrow LEGMAIN window)
SELECT TOP 50 l.DAY, LTRIM(RTRIM(l.DEP)) AS Dep, p.CATEGIDX
FROM TSC.dbo.LEGMAIN l JOIN TSC.dbo.PORTCATEG p ON p.STATION = l.DEP
WHERE l.DAY BETWEEN 17100 AND 17110;
```

## 8. Data profile (measured 2026-11-03)
18 rows, 13 distinct stations. All `ACTIVEBEG = 0`, `ACTIVEEND = 32767`. By category: 8 (AVOID ACFT C-FDAT - EGPWS) on CDG, EXL, GLA, LGW, LIS, OPO; 5 (RWY 7200FT OR LESS RESTRICTION L10&L15) on EXT, OGG, SXM, ZLO; 4 (ONLY A310 AND SMALLER AIRCRAFT OPERATION) on CFG and MCI; 7 (2x A.D.F REQUIREMENT) on SNU;
MCI also carries 1 (LOW VISIBILITY AIRFIELD), 2 (CATEGORY C AIRFIELD), 3 (REQUIRES CASH PAYMENT FOR FUEL), 18 and 20 (unnamed). Index 6 (vac toilet not allowed) has no member.

## 9. Open questions / confidence
* High confidence on structure/joins. The *rule content* that references these categories (SEL 5) is currently dormant (no active SPEFREC2/3 rule uses SEL 5; 152 inactive SPEFREC2 template rows have SEL 5).
* Category 8's meaning is in the English text only ("AVOID ACFT C-FDAT - EGPWS": an aircraft restriction at these airports); how AIMS enforces it is not visible here.
* MCI index 18/20: probably categories defined once and since removed from GENCAT (inference).
