# CITYCATEG  (Table)  - City-pair (sector) -> sector category membership (with validity period)

## 1. Purpose & business meaning
Classifies **city pairs / sectors** (origin-destination station pair, direction-independent) with planner-defined **city-pair categories** from `GENCAT` type 2:
"REQUIRES DOUBLE CREW", "REQUIRES AT LEAST 1 SENIOR PILOT", "NO TRAFFIC RIGHTS SECTOR", "REGULAR", "SUB SERVICE ROUTE", "TRAINING". Row grain: one (STN1, STN2, category, from, to).
It is the data behind rule kind **SEL 6 "City pairs of following category"** in R1/R2: e.g. "this crew type may only operate sectors of category X".
Maintained by AIMS administrators (city-pair category setup). Note the AIMS "city pair" is the *sector* (a leg between two airports), not a metropolitan area.

## 2. Physical facts
* `TSC.dbo.CITYCATEG`, base table, **1,480 rows** (2026-11-03).
* PK/unique clustered index `CITYCATEG_INDEX_0` on (STN1, STN2, CATEGIDX, ACTIVEBEG, ACTIVEEND): seeks by (STN1, STN2) pair. (The metadata extract `columns.json` reports `nchar` lengths in **bytes**; the real declared lengths in characters are half of that and are used below.) The reverse direction needs a second seek (the procedures OR both directions, which costs a scan-like plan on correlated sub-selects; table is tiny).

## 3. Column dictionary
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| STN1 | nchar(4) | N | First station of the pair. | Airport code (3 letters, declared nchar(4), space padded). Stored in **alphabetical order**: 1,467 rows STN1 < STN2, 13 rows STN1 = STN2, none STN1 > STN2. Also contains non-IATA internal codes such as `SM1`, `TS0` (simulator pseudo-stations in category 15). All 353 distinct stations of the table exist in `vvAirports`. | rpt.Get_Detailed_Pairing.sql:284-286; profiled |
| STN2 | nchar(4) | N | Second station of the pair. | same domain. | same |
| CATEGIDX | smallint | N | City-pair category number; name = `GENCAT (GENCATTYPE = 2, GENCATINDEX = CATEGIDX)`; also bit CATEGIDX of `SPEFRECDATA.CITCAT` when `SEL = 6`. | Observed 1, 3, 4, 15. | rpt.Get_Detailed_Pairing.sql:284; profiled |
| ACTIVEBEG | smallint | N | First day of membership (days since 1980-01-01). | 0 in all rows. | rpt.Get_Detailed_Pairing.sql:285 |
| ACTIVEEND | smallint | N | Last day of membership. | 32767 (= 2069-09-17) in all rows = open ended. | rpt.Get_Detailed_Pairing.sql:285 |

## 4. Keys & relationships
* Natural key = full PK; effectively (STN1, STN2, CATEGIDX) because all validity windows are open (1,480 distinct pairs for 1,480 rows).
* To a leg: **either direction** - predicate `((pc2.STN1 = DEP AND pc2.STN2 = ARR) OR (pc2.STN1 = ARR AND pc2.STN2 = DEP)) AND pc2.ACTIVEBEG < (DAY + (STD/1440.0)) AND pc2.ACTIVEEND > (DAY + (STA/1440.0))` against `LEGMAIN` (DEP, ARR) (rpt.Get_Detailed_Pairing.sql:284-286). Cardinality leg N : M pair-category rows.
* `CATEGIDX` -> `GENCAT` with `gc.GENCATINDEX = pc2.CATEGIDX AND gc.GENCATTYPE = 2` (N:1).
* `STN1`,`STN2` -> `vvAirports.AIRPORT` (N:1 each; 100 % matched).

## 5. Encoding conventions & gotchas
* **Direction-independent**: one row per unordered pair, stored with STN1 < STN2; always match both orders (or normalise the pair with `CASE WHEN a<b ...`) - matching `STN1 = DEP AND STN2 = ARR` alone misses half the legs. Self pairs (STN1 = STN2, 13 rows) exist (training/sim stations).
* Day-number validity; the consumer uses the strict decimal-day tests (`ACTIVEBEG < DAY + STD/1440.0`, `ACTIVEEND > DAY + STA/1440.0`): a membership whose last day equals the flight day is never matched.
* Space padding of `nchar(4)` stations.
* One pair can belong to several categories (rows differ by CATEGIDX).

## 6. How the planner-assist procedures use it
* `rpt.Get_Detailed_Pairing`: `City_Pair_Categories` per leg (`' | '`-joined names, nvarchar(300)).
* R1/R2 rule kind 6: `$.City_Pairs_Category` JSON (from `SPEFRECDATA.CITCAT` via GENCAT type 2) intersected with the leg's `City_Pair_Categories`.
* The pairing procedure also uses these categories indirectly to tell whether a sector "requires double crew" etc. only through such rules; no procedure reads the meaning directly.

## 7. Typical query patterns
```sql
-- 1. Category of a sector in either direction, valid on a day number
DECLARE @n int = DATEDIFF(DAY,'1980-01-01','2026-11-03');
SELECT c.CATEGIDX, LTRIM(RTRIM(g.DESC_)) AS Category
FROM TSC.dbo.CITYCATEG c
JOIN TSC.dbo.GENCAT g ON g.GENCATTYPE = 2 AND g.GENCATINDEX = c.CATEGIDX
WHERE ((c.STN1 = 'YUL' AND c.STN2 = 'CUN') OR (c.STN1 = 'CUN' AND c.STN2 = 'YUL'))
  AND c.ACTIVEBEG <= @n AND c.ACTIVEEND >= @n;

-- 2. Sectors of a given category (e.g. 3 = NO TRAFFIC RIGHTS SECTOR)
SELECT LTRIM(RTRIM(STN1)) AS Stn1, LTRIM(RTRIM(STN2)) AS Stn2 FROM TSC.dbo.CITYCATEG WHERE CATEGIDX = 3 ORDER BY 1,2;

-- 3. Category counts
SELECT g.GENCATINDEX, LTRIM(RTRIM(g.DESC_)) AS Category, COUNT(c.STN1) AS Sectors
FROM TSC.dbo.GENCAT g LEFT JOIN TSC.dbo.CITYCATEG c ON c.CATEGIDX = g.GENCATINDEX
WHERE g.GENCATTYPE = 2 GROUP BY g.GENCATINDEX, g.DESC_ ORDER BY 1;
```

## 8. Data profile (measured 2026-11-03)
1,480 rows / 1,480 distinct (STN1,STN2) / 353 distinct stations. Rows per category: 4 "REGULAR" = 1,472 (311 distinct STN1, 231 distinct STN2); 3 "NO TRAFFIC RIGHTS SECTOR" = 5 (e.g. AMS-ATH, AMS-LGW, ATH-BOD, ATH-GLA, ATH-MRS); 1 "REQUIRES DOUBLE CREW" = 1 (AVI-FPO); 15 "TRAINING" = 2 (SM1-YUL, TS0-YUL). Index 2 and 5 are named but have no member.
All rows: `ACTIVEBEG = 0`, `ACTIVEEND = 32767`.

## 9. Open questions / confidence
* High confidence on structure, direction handling and joins (code + data).
* "REGULAR" (category 4) appears to be the default tag for the airline's operated sectors (1,472 of 1,480 rows); the rule engine can use it to detect non-regular sectors (inference).
* Meaning of the pseudo stations `SM1`, `TS0` (simulator/training) inferred from the category name "TRAINING".
