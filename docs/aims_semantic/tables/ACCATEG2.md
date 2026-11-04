# ACCATEG2  (Table)  - Aircraft-registration -> "additional" aircraft category membership (currently empty)

## 1. Purpose & business meaning
Second, independent aircraft-category dimension, structurally identical to `ACCATEG` (registration + category index + validity window) but whose category names come from **GENCAT type 18** ("additional aircraft categories")
instead of the 32 `TABLES.AIRCATEGnn` records. It exists so a planner can classify tails along a second axis (e.g. a performance class independent of the first set).
It is consumed by rule kind **SEL 20 "Flight with aircraft of additional category"** (`SPEFRECDATA.CTRCAT` decoded against GENCAT type 18).
**The table has 0 rows and GENCAT has no type 18 rows**: the feature is configured nowhere in this database today. Row grain if populated: one (registration, category, from, to).

## 2. Physical facts
* `TSC.dbo.ACCATEG2`, base table, **0 rows** (2026-11-03).
* PK/unique clustered index `ACCATEG2_INDEX_0` on (ACREG, CATEGIDX, ACTIVEBEG, ACTIVEEND). No other index.
* (The metadata extract `columns.json` reports `nchar` lengths in **bytes**; the real declared lengths in characters are half of that and are used below.)

## 3. Column dictionary
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| ACREG | nchar(12) | N | Aircraft tail registration. | Space-padded registration, same format as `ACCATEG.ACREG` / `LEGMAIN.REG` (e.g. `C-FDAT`). | rpt.Get_Detailed_Pairing.sql:253-255 (`accat.ACREG = REG`) |
| CATEGIDX | smallint | N | Additional aircraft category number; name = `GENCAT` where `GENCATTYPE = 18 AND GENCATINDEX = CATEGIDX`. | 1..32 expected (bit in `SPEFRECDATA.CTRCAT`). | rpt.Get_Detailed_Pairing.sql:253 |
| ACTIVEBEG | smallint | N | First day of membership (AIMS day number = days since 1980-01-01). | 0 = always. | rpt.Get_Detailed_Pairing.sql:254 |
| ACTIVEEND | smallint | N | Last day of membership. | days since 1980-01-01; 32767 (2069-09-17) = open ended. | rpt.Get_Detailed_Pairing.sql:254 (see gotcha: the proc does **not** apply it) |

## 4. Keys & relationships
* Natural key = full PK. `ACREG` -> `LEGMAIN.REG` (N:M); `CATEGIDX` -> `GENCAT (GENCATTYPE = 18, GENCATINDEX)` (N:1), exact predicate `gc.GENCATINDEX = accat.CATEGIDX AND gc.[GENCATTYPE] = 18` (rpt.Get_Detailed_Pairing.sql:253).

## 5. Encoding conventions & gotchas
* Same day-number encoding as ACCATEG. 
* In rpt.Get_Detailed_Pairing the predicate is `accat.ACTIVEBEG < (DAY + (STD/1440)) AND accat.ACTIVEEND > (DAY + (STA/1440))` (strict, integer division) - the same off-by-one as ACCATEG (a membership starting on the flight's day is missed).
* Empty table + empty GENCAT type 18 => `Aircraft_Additional_Categories` is always NULL and every SEL 20 rule is a no-op (never matches).

## 6. How the planner-assist procedures use it
* `rpt.Get_Detailed_Pairing`: column `Aircraft_Additional_Categories` (`'| '`-joined names). Always NULL today.
* R1/R2 evaluate rule kind 20 by intersecting that text with the rule's `Aircraft_Additional_Category` JSON array; with no data this can never produce a violation (for R2 "Do not schedule"), and an "Always schedule/Are to be scheduled only" rule of kind 20 would flag everything.

## 7. Typical query patterns
```sql
-- Is the feature in use at all?
SELECT COUNT(*) AS Rows FROM TSC.dbo.ACCATEG2;
-- If populated: additional categories of a tail valid on a day number @n
DECLARE @n int = DATEDIFF(DAY,'1980-01-01','2026-11-03');
SELECT a.ACREG, a.CATEGIDX, LTRIM(RTRIM(g.DESC_)) AS Category
FROM TSC.dbo.ACCATEG2 a JOIN TSC.dbo.GENCAT g ON g.GENCATTYPE = 18 AND g.GENCATINDEX = a.CATEGIDX
WHERE a.ACTIVEBEG <= @n AND a.ACTIVEEND >= @n;
```

## 8. Data profile (measured 2026-11-03)
0 rows. (GENCAT rows with GENCATTYPE = 18: 0.)

## 9. Open questions / confidence
* Structure inferred from the identical column list to ACCATEG and from the code in rpt.Get_Detailed_Pairing; semantics of "additional" are naming inference (the procedures label the rule kinds "additional category"). Cannot be verified against data because the table is empty.
