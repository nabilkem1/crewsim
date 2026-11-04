# COUNTRYCATEG  (Table)  - Country (ICAO prefix) -> country category membership (with validity period)

## 1. Purpose & business meaning
Groups **countries / regions** into planner-defined **country categories** (GENCAT type 4): age-60 operating restrictions per position, airport/aircraft restrictions, Canada, "H out of Canada", "SA south" (sun destinations: US, Caribbean, Central/South America),
"EU Europe", "UK & IE", "Moyen Orient", "Nordique". Row grain: one (country, category, from, to). Used for rule kind **SEL 7 "Flights to the following country categories"** (destination country) and SEL 17 (night-stop countries) in R1/R2,
and to name the country of a hotel night stop in `rpt.Get_Detailed_Pairing`.
Maintained by AIMS administrators. Unlike the other `*CATEG` tables, memberships here really are **time-dependent**: the table contains real validity windows (see profile).

## 2. Physical facts
* `TSC.dbo.COUNTRYCATEG`, base table, **79 rows** (2026-11-03).
* PK/unique clustered index `COUNTRYCATEG_INDEX_0` on (COUNTRY, CATEGIDX, ACTIVEBEG, ACTIVEEND).
* (The metadata extract `columns.json` reports `nchar` lengths in **bytes**; the real declared lengths in characters are half of that and are used below.)

## 3. Column dictionary
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| COUNTRY | nchar(2) | N | Country identifier = the **ICAO location-indicator prefix** of airports (not ISO-3166): `K` (USA), `CY` (Canada), `LF` (France), `EG` (UK), `EI` (Ireland), `MM` (Mexico)... 1-2 characters (declared nchar(2), space padded). Matches `vvAirports.COUNTRY` (72/72 distinct values matched). | e.g. `YUL -> CY`, `MCI -> K`, `CDG -> LF`, `LIS -> LP`, `CUN -> MM` (vvAirports, profiled). | rpt.Get_Detailed_Pairing.sql:168,288-291; profiled |
| CATEGIDX | smallint | N | Country category number; name = `GENCAT (GENCATTYPE = 4, GENCATINDEX = CATEGIDX)`; also bit CATEGIDX of `SPEFRECDATA.CTRCAT` when `SEL = 7/17`. | Observed 1,2,5,7,8,9,10,11 (see profile). | rpt.Get_Detailed_Pairing.sql:169,288 |
| ACTIVEBEG | smallint | N | First day of membership (days since 1980-01-01). | 0 = always; other values seen: 15706 (2023-01-01), 16184 (2024-04-23), 16983 (2026-07-01). | profiled |
| ACTIVEEND | smallint | N | Last day of membership. | 32767 (2069-09-17) = open ended; 16982 (2026-06-30) on 5 rows. | profiled |

## 4. Keys & relationships
* Natural key = full PK. A country can have several categories at once (6 countries do) and one category spans many countries.
* To airports: `COUNTRYCATEG.COUNTRY = vvAirports.COUNTRY` (N airports per country row). Pairing arrival country: `pc.Country = (SELECT TOP 1 Country FROM vvAirports WHERE AIRPORT = ARR)` with `pc.ACTIVEBEG < (DAY + (STD/1440)) AND pc.ACTIVEEND > (DAY + (STA/1440))` (rpt.Get_Detailed_Pairing.sql:288-291).
* To night-stops: `HOTAC.SUPPLIERSTN -> vvAirports.AIRPORT`, then `COUNTRYCATEG.COUNTRY = vvAirports.COUNTRY`, then `GENCAT(type 4)` by `Categidx` (rpt.Get_Detailed_Pairing.sql:162-173) - **note: no validity filter and no category filter**, so a night-stop country with *several* categories yields one HOTAC row per category (inference: this would duplicate the leg rows downstream; the `Hotac` CTE does not de-duplicate).
* `CATEGIDX` -> GENCAT type 4, N:1.

## 5. Encoding conventions & gotchas
* `COUNTRY` is an **ICAO prefix, not a 2-letter ISO code**: `K` is a single letter (padded). The nationality codes stored in `SPEFREC3.NATIONALITIES` are 2-letter codes from `vvCountries.Country` (see R1 comments), a *different* code list - do not join them.
* The pairing procedure matches only the **arrival** airport's country (`ARR`) for `Country_Categories`; departure country is not categorised. Rule kind 7 ("flights to the following country categories") is thus destination-based.
* Time windows are real: on **2026-07-01** the Nordic countries (`BI` Iceland, `EF` Finland, `EK` Denmark, `EN` Norway, `ES` Sweden) leave category 8 "EU Europe" (ACTIVEEND = 16982 = 2026-06-30) and enter category 11 "Nordique" (ACTIVEBEG = 16983 = 2026-07-01). Today (2026-11-03) they are only in 11. Always filter by the validity window when answering "which category is country X in on date D".
* Strict inequality / integer-division in the consumer (`ACTIVEBEG < DAY + STD/1440`) - a membership that begins on the flight's own day is not matched, and one that ends on the flight's own day is not matched; for the 2026-06-30/07-01 switch this means flights whose STD/STA fall **on 2026-07-01 get neither** category (inconsistent with the "inclusive" convention used in R2 for crew categories).
* `nchar(2)` space padded (`'K '`).

## 6. How the planner-assist procedures use it
* `rpt.Get_Detailed_Pairing`: (a) `Country_Categories` of the leg's arrival airport (` | `-joined type-4 names); (b) in the HOTAC CTE, to name the country of the hotel station for `Night_Stop_Country`.
* R1/R2 rule kind 7 (arrival country categories) and kind 17 (night-stop country): rule JSON `$.Country_Category` (from `SPEFRECDATA.CTRCAT` via GENCAT type 4) is compared to `Country_Categories` / `Night_Stop_Country`.
* Not used by R3-R5.

## 7. Typical query patterns
```sql
-- 1. Country categories of an airport on a date
DECLARE @n int = DATEDIFF(DAY,'1980-01-01','2026-11-03');
SELECT LTRIM(RTRIM(g.DESC_)) AS Category
FROM TSC.dbo.vvAirports a
JOIN TSC.dbo.COUNTRYCATEG c ON c.COUNTRY = a.COUNTRY AND c.ACTIVEBEG <= @n AND c.ACTIVEEND >= @n
JOIN TSC.dbo.GENCAT g ON g.GENCATTYPE = 4 AND g.GENCATINDEX = c.CATEGIDX
WHERE a.AIRPORT = 'ARN';

-- 2. Members of each category today
SELECT c.CATEGIDX, LTRIM(RTRIM(g.DESC_)) AS Category, COUNT(*) AS Countries
FROM TSC.dbo.COUNTRYCATEG c JOIN TSC.dbo.GENCAT g ON g.GENCATTYPE = 4 AND g.GENCATINDEX = c.CATEGIDX
WHERE c.ACTIVEBEG <= @n AND c.ACTIVEEND >= @n GROUP BY c.CATEGIDX, g.DESC_ ORDER BY 1;

-- 3. Memberships that change over time
SELECT LTRIM(RTRIM(COUNTRY)) AS Country, CATEGIDX, DATEADD(DAY,ACTIVEBEG,'1980-01-01') AS FromDate, DATEADD(DAY,ACTIVEEND,'1980-01-01') AS ToDate
FROM TSC.dbo.COUNTRYCATEG WHERE ACTIVEBEG > 0 OR ACTIVEEND < 32767 ORDER BY CATEGIDX, COUNTRY;
```
(`@n` must be declared in each batch.)

## 8. Data profile (measured 2026-11-03)
79 rows, 72 distinct country prefixes (6 countries in more than one category). Rows per category: 1 "CMDT OVER AGE 60 - CANNOT OPERATE" = 1 (`K`); 2 "PO OVER AGE 60 - CANNOT OPERATE" = 1 (`K`); 5 "CANADA" = 1 (`CY`); 7 "SA south" = 38 (`AW,K,MB,MD,MG,MH,MK,MM,MN,MP,MQ,MR,MS,MT,MU,MW,MY,MZ,SA,SB,SC,SK,SL,SP,SU,SV,SY,TA,TB,TD,TF,TI,TJ,TK,TL,TN,TT,TX`; one of them, `SP`, from 2023-01-01);
8 "EU Europe" = 29 (23 open-ended since 1980, 5 ended 2026-06-30, 1 `GM` from 2024-04-23); 9 "UK & IE" = 2 (`EG,EI`); 10 "Moyen Orient" = 2 (`LL,OL`); 11 "Nordique" = 5 (`BI,EF,EK,EN,ES` from 2026-07-01). Categories 3, 4, 6 have no member.
Validity: 72 rows ACTIVEBEG = 0 (7 rows start later: 1 in 2023, 1 in 2024, 5 on 2026-07-01); ACTIVEEND = 32767 except 5 rows (2026-06-30).

## 9. Open questions / confidence
* High confidence on encoding (ICAO prefix) and joins (every value matches vvAirports.COUNTRY).
* Category 1/2/3 ("OVER AGE 60 - CANNOT OPERATE") attached to `K` (USA) means: crew over 60 (commander / PO / mechanic) may not operate to the USA (US age-60 rule); category 3 (MEC) has no member. This reading is inferred from the names; it is realised through SPEFREC3 rules 3/4 (kind 7), which are inactive.
* `COUNTRYCATEG.COUNTRY` contains 'EK','EN' etc. as in ICAO; the Icelandic prefix `BI` is real ICAO. Not verified that all 72 prefixes denote countries rather than regions (e.g. `K`, `C`-prefixes cover several states).

