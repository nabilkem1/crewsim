# GENCAT  (Table)  - Generic category registry (name of every bit/index of the "category" bitmasks used across AIMS)

## 1. Purpose & business meaning
GENCAT is the **dictionary of named categories** that AIMS lets a planner define for things that are not crew: routes (crew pairings), city pairs, airports,
countries, flights, simulators, training locations, delay reasons, ... Each row says: "in category-family `GENCATTYPE`, category number `GENCATINDEX` is called `DESC_`".

* A *category family* (GENCATTYPE) corresponds to one "kind of object" that can be categorised (airport, country, city pair, flight, ...).
* A *category index* (GENCATINDEX, 1..n) is the position of the category inside that family. The index is used in two ways:
  1. as the **bit position** in the packed bitmask columns of other tables (`SPEFRECDATA.CRTECAT / AIRCAT / CITCAT / CTRCAT / FLTCATS`, `CRROUTE.RTECAT`, `LEGMAIN.FLTCAT`):
     bit number N (1-based) is stored in byte `CEILING(N/8)` (1-based), bit `(N-1)%8` (0 = least significant);
  2. as a **foreign key value** (`CATEGIDX`) in the "membership" tables `PORTCATEG`, `CITYCATEG`, `COUNTRYCATEG` (and the empty `PORTCATEG2` / `ACCATEG2`), each of which
     says "this airport / city pair / country belongs to category N during [ACTIVEBEG, ACTIVEEND]".
* Rows are **master data** typed in by the AIMS administrator (AIMS "Categories" setup screens). Row grain: one (family, index). Almost static (88 rows).
* Readers in this repo: `rpt.Get_Detailed_Pairing` (turns the memberships into the text lists `Dep_Airport_Categories`, `City_Pair_Categories`, `Country_Categories`, `Flight_Categories`, `Crew_Route_Categories`)
  and `rpt.Get_Custom_Rules_CertainFlightsCrew` / `rpt.Get_Custom_Rules_Schedule_WithWithNot` (turn the bitmasks of the special rules into the category names listed in the rule's sub-conditions JSON).
  The names are what the R1/R2 violation procedures finally compare as text (`'|'` separated lists).

## 2. Physical facts
* Database/schema: `TSC.dbo.GENCAT`, base table. **88 rows** at extraction (2026-11-03).
* Primary key / unique clustered index `GENCAT_INDEX_0` on **(GENCATINDEX, GENCATTYPE)** (note: the leading column is the index, not the type). A filter by `GENCATTYPE` alone cannot seek; at 88 rows this is irrelevant.
* No other indexes, no identity column, no timestamps, no soft delete. No foreign keys.
* Not partitioned; negligible size.
* (The metadata extract columns.json reports 
char lengths in **bytes**; the real declared lengths in characters are half of that and are used below.)

## 3. Column dictionary
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| GENCATINDEX | int | N | Number of the category inside its family. Doubles as bit position (1-based) in bitmasks and as `CATEGIDX` in the `*CATEG` tables. | 0..48 observed. Index 0 exists only as a family title/placeholder in types 1 ("Route Categories") and 15 ("UNDEFINED"); every decoding code uses `GENCATINDEX > 0`. Gaps are normal (not every number is named). | rpt.Get_Detailed_Pairing.sql:127-129,238,280-291; rpt.Get_Custom_Rules_*.sql (`T2.GENCATINDEX > 0`); profiled |
| GENCATTYPE | smallint | N | Category family (what kind of object is categorised). | See the decoded list below (types 1,2,3,4,6,7,8,10,15,16 have rows; 17,18,19 are referenced by code but have **no rows**). | rpt.Get_Detailed_Pairing.sql:128; Get_Custom_Rules_*.sql; profiled |
| DESC_ | nchar(40) | Y | Human name of the category (English/French mix, space padded: always `LTRIM(RTRIM())`). This text is the join key used by R1/R2 text comparisons. | Free text. Blank for unused slots (type 8 index 9,10,12; type 15 index 11-16). | all consumers use `LTRIM(RTRIM(T2.DESC_))`; profiled |
| CODE | nchar(2) | Y | Short code of the category where the family has codes. | Blank for types 1,2,3,4,16. Used: type 6 (`HD`,`HS`,`HV`,`LD`,`DI`,`II`,`ID`,`DD`), type 7 (`FF`,`FB`), type 8 (`CL`,`CC`,`CT`,`FI`,`TR`,`HQ`,`AP`,`AI`), type 10 (`Z`,`A`..`F`), type 15 (`01`..`16`). | profiled; not read by any planner-assist procedure |
| COMNY_RES | tinyint | Y | "Company responsible" flag (naming inference: COMpaNY RESponsible). Only meaningful for type 10 (delay/cancel reason groups). | 1 = company-responsible reason, 0 = not. Value 1 on type 10 index 1,2,3 only. | profiled; naming inference; not used by any procedure |

### Decoded GENCATTYPE values (profiled 2026-11-03)
| GENCATTYPE | Rows | Family meaning | Indices -> DESC_ (CODE) | Where it is consumed |
|---|---|---|---|---|
| 1 | 14 (13 + title row 0) | **Route (pairing) categories** - flags on a crew pairing/route; the bitmask is `CRROUTE.RTECAT` / `SPEFRECDATA.CRTECAT` | 0 "Route Categories" (title); 1 Augmented; 2 VIP flight; 3 Union Special agreement to exceed FDP; 4 Trainning flight PNC; 5 Extra PO; 6 Extra CM; 7 Formation; 8 SOUS-CONTRAT; 9 AUTRES; 10 FORM INITIAL; 12 NO PAYMENT; 13 NO OPEN BIDS; 32 HRS & CREDITS ONLY | Get_Detailed_Pairing `Crew_Route_Categories`; rule SEL 4 `Route_Categories` |
| 2 | 6 | **City-pair categories** (membership in `CITYCATEG`; bitmask `SPEFRECDATA.CITCAT`) | 1 REQUIRES DOUBLE CREW; 2 REQUIRES AT LEAST 1 SENIOR PILOT; 3 NO TRAFFIC RIGHTS SECTOR; 4 REGULAR; 5 SUB SERVICE ROUTE; 15 TRAINING | `City_Pair_Categories`; rule SEL 6 |
| 3 | 8 | **Airport categories** (membership in `PORTCATEG`; bitmask `SPEFRECDATA.AIRCAT`) | 1 LOW VISIBILITY AIRFIELD; 2 CATEGORY C AIRFIELD; 3 REQUIRES CASH PAYMENT FOR FUEL; 4 ONLY A310 AND SMALLER AIRCRAFT OPERATION; 5 RWY 7200FT OR LESS RESTRICTION L10&L15; 6 vac toilet not allowed; 7 2x A.D.F REQUIREMENT; 8 AVOID ACFT C-FDAT - EGPWS | `Dep_Airport_Categories`/`Arr_Airport_Categories`; rule SEL 5 |
| 4 | 11 | **Country categories** (membership in `COUNTRYCATEG`; bitmask `SPEFRECDATA.CTRCAT` when SEL=7/17) | 1 CMDT OVER AGE 60 - CANNOT OPERATE; 2 PO OVER AGE 60 - CANNOT OPERATE; 3 MEC OVER AGE 60 - CANNOT OPERATE; 4 AIRPORT/AIRCRAFT RESTRICTION; 5 CANADA; 6 H out of Canada; 7 SA south; 8 EU Europe; 9 UK & IE; 10 Moyen Orient; 11 Nordique | `Country_Categories`; rule SEL 7 / 17 |
| 6 | 8 | **Flight categories** (flag bits of `LEGMAIN.FLTCAT`; bitmask `SPEFRECDATA.FLTCATS`, 48 bits) | 1 HIGH DENSITY FLIGHT / 375 SEATS REQUIRED (HD); 2 HIGH SEATING CAPACITY 321 (HS); 3 HEAVY FLIGHT (HV); 4 LOW DENSITY FLIGHT / 332 SEATS REQUIRED (LD); 45 DOM INT (DI); 46 INT INT (II); 47 INT DOM (ID); 48 DOM DOM (DD) | `Flight_Categories`; rule SEL 15 |
| 7 | 3 | Simulator/trainer type (inference from names) | 1 Full flight (FF); 2 Fixed base (FB); 3 "-" | not used by planner-assist |
| 8 | 11 (8 named) | Training location / training-room type (inference from names) | 1 PLAIN CLASSROOM (CL); 2 COMPUTER BASED (CC); 3 CABIN TRAINER (CT); 4 FIRE DRILL (FI); 5 TRAINING ROOM (TR); 6 HEADQUARTER (HQ); 7 APT (AP); 8 AIRPORT (AI); 9,10,12 blank | not used |
| 10 | 7 | Flight cancellation / delay reason group (inference from names; the `A`-`F` codes look like IATA-style groupings) | 1 Canceled > 14 days prior departure (Z, company-resp.); 2 Within Carrier Control (A, company-resp.); 3 Within Carrier Control - For Safety (B, company-resp.); 4 Weather (C); 5 Air Traffic Control/Nat Aviation System (D); 6 Security (E); 7 Outside Carrier Control - Others (F) | not used |
| 15 | 17 (11 named) | Interface / data-transfer message category (inference from names) | 0 UNDEFINED; 1 Engineering systems related (01); 2 Flight schedule transfer related (02); 3 Reservation systems related (03); 4 Crew Schedule Transfer (04); 5 Personal Crew Info (05); 6 Payroll transfer (06); 7 Crew training/expiries related (07); 8 Crew pairing transfer (08); 9 Emergency Backup Related (09); 10 User defined (10); 11-16 blank | not used |
| 16 | 3 | Crew-activity grouping (unclear; inference) | 1 TRAINING ACTIVITIES (JOB #24); 2 Maladie OPEN; 6 RESERVE AVAILABILITY PERIOD | not used |
| 17 | **0 rows** | "Additional" **airport** categories (`PORTCATEG2`; rule SEL 21; `SPEFRECDATA.AIRCAT`) | referenced in code, no category named | Get_Detailed_Pairing `Departure/Arrival_Airport_Additional_Categories` (always NULL) |
| 18 | **0 rows** | "Additional" **aircraft** categories (`ACCATEG2`; rule SEL 20; `SPEFRECDATA.CTRCAT` bits) | referenced in code, no category named | `Aircraft_Additional_Categories` (always NULL) |
| 19 | **0 rows** | "via country" additional categories (`Cat_G19_CountryVia` in Get_Custom_Rules_Schedule_WithWithNot; rule SEL 22) | referenced in code, no category named | not evaluated |

Types 5, 9, 11-14 do not exist. Aircraft *registration* categories (`ACCATEG`) are **not** in GENCAT: they are named in `TABLES` rows `AIRCATEG01..32` (see TABLES.md).

## 4. Keys & relationships
* Natural key: (GENCATTYPE, GENCATINDEX) (unique).
* `PORTCATEG.CATEGIDX` -> `GENCAT` where `GENCATTYPE = 3`; `PORTCATEG2.CATEGIDX` -> `GENCATTYPE = 17`; `CITYCATEG.CATEGIDX` -> `GENCATTYPE = 2`; `COUNTRYCATEG.CATEGIDX` -> `GENCATTYPE = 4`;
  `ACCATEG2.CATEGIDX` -> `GENCATTYPE = 18`; (`ACCATEG.CATEGIDX` -> `TABLES.AIRCATEGnn`, not GENCAT). Predicate in code: `gc.GENCATINDEX = pc.CATEGIDX AND gc.GENCATTYPE = <t>` (rpt.Get_Detailed_Pairing.sql:253-291). All 1:N (one category, many members).
* Bitmask decoding: `SPEFRECDATA.CRTECAT`->type 1, `AIRCAT`->3 (SEL 5) or 17 (SEL 21), `CITCAT`->2, `CTRCAT`->4 (SEL 7/17), 18 (SEL 20), 19 (SEL 22) or TABLES `AIRCATEGnn` (SEL 18), `FLTCATS`->6.
  Predicate: `bit_is_set(CONVERT(tinyint, SUBSTRING(CONVERT(binary(32), <mask>), CEILING(GENCATINDEX/8.0), 1)), (GENCATINDEX-1)%8) = 1` (rpt.Get_Custom_Rules_CertainFlightsCrew.sql:162-221).
* Crew categories are **not** here: they live in `CREWCAT` (own table, 240 slots) / `CREWCATEG`.

## 5. Encoding conventions & gotchas
* `DESC_` and `CODE` are `nchar` and space padded - always `LTRIM(RTRIM())` before comparing (the procedures do).
* **The category *name* is the join key of the R1/R2 engine**: the pairing side produces `'| '`-joined names from GENCAT, the rule side produces JSON arrays of the same names, and the comparison is a string equality. Renaming a GENCAT row therefore silently changes behaviour; two rows of the same type with the same text would be indistinguishable.
* Type 1 index 0 and type 15 index 0 are title/placeholder rows (not real categories).
* Types 17/18/19 have no rows: rules of SEL 20, 21, 22 can never resolve a category name today.
* `GENCATINDEX` is a bit position, so it is limited by the width of the mask that stores it: `SPEFRECDATA.AIRCAT/CITCAT/CTRCAT` are binary(4) = 32 bits, `CRTECAT` and `FLTCATS` are binary(6) = 48 bits (the CertainFlights rules procedure additionally caps types 1,2,3,4,17,18 at `GENCATINDEX <= 32`; type 6 is uncapped, and index 45-48 of type 6 are indeed used).
* Get_Detailed_Pairing decodes `CRROUTE.RTECAT` with the bytes in **reverse** order (`CONVERT(BINARY(4), rtecat)`, bit 1-8 in byte 4) whereas SPEFRECDATA masks are decoded **forward** (bit 1-8 in byte 1): the two bit orders are not interchangeable.

## 6. How the planner-assist procedures use it
* `rpt.Get_Detailed_Pairing`: loads `CachedGenCat = SELECT GENCATTYPE, GENCATINDEX, DESC_ FROM GENCAT WHERE GENCATTYPE IN (1,2,3,4,6,17,18)` and uses it to name (a) route categories from `RTECAT` (type 1), (b) flight categories from `FLTCAT` (type 6), (c) airport categories (3, 17), city-pair categories (2), country categories (4), aircraft additional categories (18). Also used for the night-stop country name in the HOTAC CTE (`g.GENCATTYPE = 4`).
* `rpt.Get_Custom_Rules_CertainFlightsCrew` and `rpt.Get_Custom_Rules_Schedule_WithWithNot`: for each rule's `SPEFRECDATA` row decode every mask into JSON arrays of category names (Route_Categories, Airport_Category, Airport_Additional_Category, City_Pairs_Category, Country_Category, Aircraft_Additional_Category, Flight_Categories, Cat_G19_CountryVia) using GENCAT.
* `dbo.R1_Get_Violations_CertainFlightsCrew`, `dbo.R2_Get_Violations_Schedule_WithWithNot`: consume only the *text* produced above; they do not read GENCAT directly.

## 7. Typical query patterns
```sql
-- 1. Name of every airport category (the text that appears in rule sub-conditions)
SELECT GENCATINDEX, LTRIM(RTRIM(DESC_)) AS Name
FROM TSC.dbo.GENCAT WHERE GENCATTYPE = 3 AND GENCATINDEX > 0 ORDER BY GENCATINDEX;

-- 2. Categories of the airports in the MCI/CDG sample (membership active today)
SELECT p.STATION, g.GENCATINDEX, LTRIM(RTRIM(g.DESC_)) AS Category
FROM TSC.dbo.PORTCATEG p
JOIN TSC.dbo.GENCAT g ON g.GENCATINDEX = p.CATEGIDX AND g.GENCATTYPE = 3
WHERE p.ACTIVEBEG <= DATEDIFF(DAY,'1980-01-01',CAST(GETDATE() AS date))
  AND p.ACTIVEEND >= DATEDIFF(DAY,'1980-01-01',CAST(GETDATE() AS date))
ORDER BY p.STATION, g.GENCATINDEX;

-- 3. Decode the flight-category bits of a SPEFRECDATA row (FLTCATS, 48 bits) into names
SELECT LTRIM(RTRIM(g.DESC_)) AS FlightCategory
FROM TSC.dbo.SPEFRECDATA d
JOIN TSC.dbo.GENCAT g ON g.GENCATTYPE = 6 AND g.GENCATINDEX > 0
WHERE d.RULE_ = 1 AND d.KIND = 2 AND d.PLANDAYTODAY = 2 AND d.IDX = 1
  AND (CONVERT(tinyint, SUBSTRING(CONVERT(binary(32), d.FLTCATS), CEILING(g.GENCATINDEX/8.0), 1)) / POWER(2,(g.GENCATINDEX-1)%8)) % 2 = 1;
```

## 8. Data profile (measured 2026-11-03)
88 rows. Rows per GENCATTYPE: 1=14, 2=6, 3=8, 4=11, 6=8, 7=3, 8=11, 10=7, 15=17, 16=3. Named (non-blank DESC_) rows: 14,6,8,11,8,3,8,7,11,3 = 79. Index range 0..48.
`COMNY_RES=1` on 3 rows (type 10 index 1-3), 0 elsewhere. Cross-checks that confirm the bit decoding: `LEGMAIN.FLTCAT` first byte `0x08` (=index 4, LOW DENSITY) on 1,944 legs and `0x01` (=index 1, HIGH DENSITY) on 513 legs in DAY 17000-17100; `PORTCATEG` index 8 sits on airports where the aircraft in the text must be avoided.

## 9. Open questions / confidence
* High confidence: types 1,2,3,4,6 (code + data cross-checked). Medium (names only): 7, 8, 10, 15, 16 - never referenced by any procedure here.
* Types 17/18/19 are empty: either the "additional categories" feature is unused at this airline or the names live elsewhere. The empty `PORTCATEG2`/`ACCATEG2` support the former.
* Whether GENCATINDEX 0 is a deliberate title row is inferred from the text "Route Categories"/"UNDEFINED".
* GENCAT.CODE is blank for the families that matter to the planner; no evidence of use.
