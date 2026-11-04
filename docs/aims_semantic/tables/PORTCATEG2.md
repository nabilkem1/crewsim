# PORTCATEG2  (Table)  - Airport -> "additional" airport category membership (currently empty)

## 1. Purpose & business meaning
Second, independent airport-category dimension, structurally identical to `PORTCATEG` but named through **GENCAT type 17** ("additional airport categories") instead of type 3.
It lets planners classify airports along a second axis. It feeds rule kind **SEL 21 "Flight via Airport of additional category"** (`SPEFRECDATA.AIRCAT` decoded against GENCAT type 17) and the pairing columns
`Departure_Airport_Additional_Categories` / `Arrival_Airport_Additional_Categories`.
**0 rows, and GENCAT has no type 17 rows**: unused today. Row grain if populated: (station, category, active-from, active-to).

## 2. Physical facts
* `TSC.dbo.PORTCATEG2`, base table, **0 rows** (2026-11-03).
* PK/unique clustered index `PORTCATEG2_INDEX_0` on (STATION, CATEGIDX, ACTIVEBEG, ACTIVEEND).
* (The metadata extract `columns.json` reports `nchar` lengths in **bytes**; the real declared lengths in characters are half of that and are used below.)

## 3. Column dictionary
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| STATION | nchar(4) | N | Airport/station code (IATA 3-letter, declared nchar(4), space padded). | Same domain as `PORTCATEG.STATION` / `vvAirports.AIRPORT`. | rpt.Get_Detailed_Pairing.sql:257-263 (`portcat.STATION = DEP` / `= ARR`) |
| CATEGIDX | smallint | N | Additional airport category number; name = `GENCAT (GENCATTYPE = 17, GENCATINDEX = CATEGIDX)`. | 1..32 expected. | rpt.Get_Detailed_Pairing.sql:257,261 |
| ACTIVEBEG | smallint | N | First day of membership (days since 1980-01-01). | 0 = always. | rpt.Get_Detailed_Pairing.sql:258,262 |
| ACTIVEEND | smallint | N | Last day of membership (days since 1980-01-01; 32767 = 2069-09-17 = open). | **not applied by the consumer** (see gotchas). | structure only |

## 4. Keys & relationships
* Natural key = full PK. `STATION` -> `vvAirports.AIRPORT`, `LEGMAIN.DEP`/`ARR`; `CATEGIDX` -> `GENCAT (GENCATTYPE = 17)`: `gc.GENCATINDEX = portcat.CATEGIDX AND gc.GENCATTYPE = 17` (rpt.Get_Detailed_Pairing.sql:257,261).

## 5. Encoding conventions & gotchas
* The consumer filters **only** `portcat.ACTIVEBEG < (DAY + (STD/1440))` - there is no ACTIVEEND test, so an expired membership would still be returned. (Contrast with PORTCATEG, which tests both ends.)
* Same day-number encoding as the other `*CATEG` tables.
* Empty table + empty GENCAT type 17 => `Departure_Airport_Additional_Categories` / `Arrival_Airport_Additional_Categories` are always NULL, and every SEL 21 rule is a no-op.

## 6. How the planner-assist procedures use it
* `rpt.Get_Detailed_Pairing`: two correlated sub-selects per leg (departure and arrival airport) producing `'| '`-joined names (Departure_Airport_Additional_Categories, Arrival_Airport_Additional_Categories; NVARCHAR(300) in the consumers' temp tables).
* R1/R2 rule kind 21: rule JSON `Airport_Additional_Category` is matched against those two texts (dep OR arr). In R1 the JSON key read is `$.Category` (as emitted by rpt.Get_Custom_Rules_CertainFlightsCrew), in R2 it is `$.Airport` (as emitted by rpt.Get_Custom_Rules_Schedule_WithWithNot): each pair is self-consistent, but the key name differs between the two rule families.

## 7. Typical query patterns
```sql
SELECT COUNT(*) AS Rows FROM TSC.dbo.PORTCATEG2;   -- 0: feature unused
-- If it is ever populated (categories valid on a day number @n):
DECLARE @n int = DATEDIFF(DAY,'1980-01-01','2026-11-03');
SELECT LTRIM(RTRIM(p.STATION)) AS Station, p.CATEGIDX, LTRIM(RTRIM(g.DESC_)) AS Category
FROM TSC.dbo.PORTCATEG2 p JOIN TSC.dbo.GENCAT g ON g.GENCATTYPE = 17 AND g.GENCATINDEX = p.CATEGIDX
WHERE p.ACTIVEBEG <= @n AND p.ACTIVEEND >= @n;
```

## 8. Data profile (measured 2026-11-03)
0 rows. GENCAT rows with `GENCATTYPE = 17`: 0.

## 9. Open questions / confidence
* Structure and semantics are inferred from the identical columns to PORTCATEG and from the consumer code; cannot be validated with data.
