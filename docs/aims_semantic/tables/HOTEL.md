# HOTEL  (Table)  - Crew hotel master: hotels (and airport lounges) available at each station, with address block and hotel<->airport transit distance

## 1. Purpose & business meaning

`TSC.dbo.HOTEL` is the AIMS **hotel master / supplier directory for crew accommodation**. One row = one hotel (or hotel-like facility such as an "AIRPORT LOUNGE") that the company can book for crew **at one airport/station**. Hotels are numbered **per airport** (`HOTELNO` 1..40 within an `AIRPORT`), so the business key is (`AIRPORT`, `HOTELNO`) - e.g. "hotel 26 at YUL".

All descriptive content is packed in `DATA_BEGIN_END` (846 bytes): the hotel name (which often carries a contract/rate tag such as a "-20H" rate or PNT/PNC crew-group suffix), a street/city/postal-code/phone block, and **the transit distance/time between airport and hotel** that planner-assist's rest-time rules subtract from the rest period.

Grain: one row per hotel per station (1,199 rows, 294 stations). Lifecycle: maintained by the AIMS hotel-desk / crew-accommodation administrators; very small and stable. Read by planner-assist R3 (rest rules) and `rpt.Get_Detailed_Pairing` (night-stop country); referenced by `HOTAC` bookings (category 0).

## 2. Physical facts

* `TSC.dbo.HOTEL`, user table, **1,199 rows**, 4 columns; collation `SQL_Latin1_General_CP1_CI_AS` for `AIRPORT`.
* **Primary key** `PK_HOTEL` clustered unique on `HOTEL_ID` (identity surrogate; values 1..1236, gaps from deleted hotels).
* **Unique** `HOTEL_INDEX_0` on `(AIRPORT, HOTELNO)`: the real lookup path used by every join (`ht.HOTELNO = h.SUPPLIER AND ht.AIRPORT = h.SUPPLIERSTN`).
* Tiny table, no performance concerns.

## 3. Column dictionary

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| AIRPORT | nchar(8) | YES (never NULL) | **Station (airport code)** where the hotel is located; first part of the business key. Space padded (`'YUL     '`). 294 distinct codes; one code (1 hotel) is not present in `vvAirports`. | IATA 3-letter code; join `HOTAC.SUPPLIERSTN = HOTEL.AIRPORT` (also nchar(8), so padded-to-padded). Largest stations by hotel count: CDG 31, YUL 26, CUN 22, YYZ 20, DUB 18, LIS 17, PUJ 17, FCO 17, GLA 16, BCN 16, YVR 16, MRS 15. | R3 `ht.AirPort = h.SUPPLIERSTN`; `rpt.Get_Detailed_Pairing` line 166; profiled |
| HOTELNO | smallint | YES (never NULL) | **Hotel number within the airport** (1..40); second part of the business key and the value stored in `HOTAC.SUPPLIER` for hotel bookings. Not globally unique, not contiguous per airport (70 airports have gaps, e.g. deleted hotels). | 1..40, 40 distinct | R3 `ht.HOTELNO = h.SUPPLIER`; profiled |
| DATA_BEGIN_END | binary(846) | YES | **Packed AIMS record of the hotel** (name, flags, address block, transit distance, other floats). Layout in 3.1. | binary, UTF-16LE text, little-endian numbers | R3 lines 414-417, `rpt.Get_Detailed_Pairing`; profiled |
| HOTEL_ID | int identity | NO | Surrogate identity / primary key. No business meaning. | 1..1236 | columns.json (idn = true); profiled |

### 3.1 Decoded layout of `DATA_BEGIN_END` (1-based byte positions)

| Bytes | Meaning | Evidence |
|---|---|---|
| 1-60 | **Hotel name**, 30 UTF-16LE characters, space padded. Names begin with the brand (e.g. a hotel brand + category), often suffixed by a rate/contract tag: `-20H` appears in 94 names, `PNT` in 8, `PNC` in 10 (e.g. a pilot/cabin-crew-specific contract). **88 rows start with `AIRPORT LOUNGE`** (lounge facilities, 89 contain "LOUNGE"). Never blank. | profiled |
| 61-62 | two flag/type bytes: byte 61 is 0 or 1 (1 on 1,060 rows), byte 62 is 0..6 (most frequent combos: `1,0` 458 rows; `1,4` 349; `0,0` 95; `1,1` 93; `1,2` 54; `1,5` 41; `1,6` 37; `1,3` 28). Meaning unknown (inference: record-in-use flag + contract/room type code). | profiled; unknown - not used by any procedure |
| 63-64 | zero | profiled |
| 65-524 | **Address block**, 230 UTF-16LE characters, space padded: street address, city, postal code and a telephone number, as one free-text field (blank for 432 hotels). Business-location text, not decoded or reproduced here. | profiled |
| 525-538 | numeric fields (little-endian IEEE floats observed, e.g. 59.0, 64.0, 72.0; zero on many rows); meaning unknown (inference: geographic distance or coordinates) | profiled; unknown - not used by any procedure |
| **539-540** | **Transit distance airport <-> hotel, smallint little-endian**, read by R3 as `CONVERT(SMALLINT, SUBSTRING(ht.DATA_BEGIN_END, 540, 1) + SUBSTRING(ht.DATA_BEGIN_END, 539, 1))` and exposed as `DISTANCE`/`Distance_Hotel`. R3 **subtracts `2 * DISTANCE` from the rest period** (`REST_TIME_BEFORE_START_Remove_debrief_and_Transit`), so the unit is **minutes of one-way transit time** (values are multiples of 15: 15, 30, 40, 60, 120, 135, 150, 165, 180). | **Code**: R3 lines 414-417 and 808-810; profiled |
| 541-846 | undecoded | unknown - not used by any procedure |

Distribution of the distance field (all 1,199 hotels): 0 -> 528; **120 -> 605 (50 %)**; 135 -> 36; 150 -> 17; 40 -> 5; 165 -> 3; 60 -> 2; 15 -> 1; 30 -> 1; 180 -> 1. Hotels with a distance > 0: 671. The dominant value 120 looks like a default/placeholder rather than a measured transit time (inference; verify with the business), and 528 hotels have 0 (no deduction).

## 4. Keys & relationships

* **Business key**: (`AIRPORT`, `HOTELNO`) unique (`HOTEL_INDEX_0`). `HOTEL_ID` is a surrogate only.
* **HOTAC -> HOTEL** (N:1, for `HOTAC.CATEGORY = 0`): `ht.HOTELNO = h.SUPPLIER AND ht.AIRPORT = h.SUPPLIERSTN` (R3 419-421, R3_Batch 382-384, `rpt.Get_Detailed_Pairing` 166). 100 % match for live 2026 hotel bookings (126,067 / 126,067); 270 distinct (station, hotel) combinations used in 2026 out of 1,199 hotels.
* **HOTEL -> vvAirports** (N:1): `AIRPORT = vvAirports.AIRPORT` (1,198 of 1,199 match) - gives country/airport attributes (used in `rpt.Get_Detailed_Pairing` through `HOTAC.SUPPLIERSTN`).
* **ROSTER.HOTELNO** has the same name but is never populated (0/NULL); there is no relationship ROSTER -> HOTEL in practice.
* No relation from HOTEL to crew tables.

## 5. Encoding conventions & gotchas

1. **Composite key**: never join on `HOTELNO` alone (it repeats per airport). Always pair with `AIRPORT`.
2. **Padding**: `AIRPORT` is nchar(8); equality is fine, but use `RTRIM(AIRPORT)` for output and string concatenation.
3. **Text is UTF-16 inside the blob**: `CAST(SUBSTRING(DATA_BEGIN_END, 1, 60) AS NVARCHAR(30))` returns the name. Do not try `LIKE` on the raw binary.
4. **Lounges are rows in this table** (88 of 1,199 start with `AIRPORT LOUNGE`); the repository's airport-lounge exclusion tests the HOTAC blob, not HOTEL (see HOTAC.md gotcha 4), so lounges are not excluded in practice. To exclude them: `CHARINDEX('AIRPORT LOUNGE', UPPER(CAST(SUBSTRING(ht.DATA_BEGIN_END, 1, 60) AS NVARCHAR(30)))) = 0`.
5. **Distance 0 is "no transit deduction"**, and R3 ignores the distance when the duty ends at the crew base (`duty_end_station = Crew_Base` -> 0).
6. **Distance units** (minutes) are deduced from the way R3 subtracts it from a rest expressed in minutes; the field itself has no unit label.
7. Hotel names/addresses are business data; the text-to-SQL agent may display them, but should expect French/English mixed names and trailing padding.

## 6. How the planner-assist procedures use it

* **dbo.R3_Get_Violations_RestTime** and **dbo.R3_Get_Violations_RestTime_Batch** (Phase 3.5): `#R3_HotacData` = `MAX(DISTANCE)` over the crew's live hotel bookings of each duty (`HOTAC h INNER JOIN HOTEL ht ON ht.HOTELNO = h.SUPPLIER AND ht.AirPort = h.SUPPLIERSTN`), where `DISTANCE` = bytes 539-540 of `HOTEL.DATA_BEGIN_END`. In the rest evaluation, `Distance_Hotel = 0` if the duty ends at the crew base, else the hotel distance; the rest available before the next duty is reduced by `2 * Distance_Hotel` before the rolling 36 h / 72 h rest tests. (If a duty has several hotel rows the largest distance is used.)
* **rpt.Get_Detailed_Pairing**: joins HOTEL only as an existence check on the `Hotac` CTE (`INNER JOIN HOTEL ... ON ht.HOTELNO = h.SUPPLIER AND ht.AirPort = h.SUPPLIERSTN`), so a hotel booking whose HOTEL row is missing would drop out of the "night stop" columns.
* **dbo.R2_Get_Violations_Schedule_WithWithNot**: only a comment mentions duplicate rows when a leg has two hotel records (via `rpt.Get_Detailed_Pairing`); it does not read HOTEL.

## 7. Typical query patterns

```sql
-- 1. Hotels at a station with name and transit minutes
SELECT RTRIM(ht.AIRPORT) AS station, ht.HOTELNO,
       RTRIM(CAST(SUBSTRING(ht.DATA_BEGIN_END, 1, 60) AS NVARCHAR(30))) AS hotel_name,
       CONVERT(int, SUBSTRING(ht.DATA_BEGIN_END, 539, 1)) + 256 * CONVERT(int, SUBSTRING(ht.DATA_BEGIN_END, 540, 1)) AS transit_minutes
FROM TSC.dbo.HOTEL ht
WHERE ht.AIRPORT = 'LIS'
ORDER BY ht.HOTELNO;

-- 2. Hotel used by a live booking (always join on BOTH key columns)
SELECT h.CREWID, h.CDATE, h.CROUTE, RTRIM(h.SUPPLIERSTN) AS station, h.SUPPLIER AS hotel_no,
       RTRIM(CAST(SUBSTRING(ht.DATA_BEGIN_END, 1, 60) AS NVARCHAR(30))) AS hotel_name
FROM TSC.dbo.HOTAC h
JOIN TSC.dbo.HOTEL ht ON ht.HOTELNO = h.SUPPLIER AND ht.AIRPORT = h.SUPPLIERSTN
WHERE h.PROCESSSTATUS = 0 AND h.CATEGORY = 0 AND h.CREWID = @crew_id
  AND h.CHECKINDAY BETWEEN DATEDIFF(DAY,'1980-01-01',@from) AND DATEDIFF(DAY,'1980-01-01',@to);

-- 3. Number of hotels per station, excluding lounges
SELECT RTRIM(ht.AIRPORT) AS station, COUNT(*) AS hotels
FROM TSC.dbo.HOTEL ht
WHERE CHARINDEX('AIRPORT LOUNGE', UPPER(CAST(SUBSTRING(ht.DATA_BEGIN_END, 1, 60) AS NVARCHAR(30)))) = 0
GROUP BY RTRIM(ht.AIRPORT)
ORDER BY hotels DESC;
```

## 8. Data profile (measured 2026-11-03)

* 1,199 rows; `HOTEL_ID` 1..1236; 294 distinct `AIRPORT`; `HOTELNO` 1..40 (40 distinct); no NULL in `AIRPORT`/`HOTELNO`.
* Hotels per station (top): CDG 31, YUL 26, CUN 22, YYZ 20, DUB 18, LIS 17, PUJ 17, FCO 17, GLA 16, BCN 16, YVR 16, MRS 15. 70 stations have non-contiguous hotel numbers.
* Name tags: `-20H` in 94 names; `PNT` in 8; `PNC` in 10; 88 names start with `AIRPORT LOUNGE`; no blank names; address block blank for 432 rows.
* Transit-distance field: 671 hotels > 0, 528 = 0; value histogram in section 3.1; 3 lounge rows have a non-zero distance.
* 270 (station, hotel) combinations appear in live 2026 category-0 bookings (`HOTAC`); 1,282 live 2026 booking rows (1.0 %) point to a lounge row.

## 9. Open questions / confidence

* **High**: key, join to HOTAC, byte positions of name (1-60), address block (65-524) and distance (539-540); distance is subtracted twice from rest in R3.
* **Medium**: unit of the distance = minutes (deduced from its arithmetic use in R3, not documented); name tags (`-20H`, `PNT`, `PNC`) are rate/crew-group tags - the interpretation is a guess.
* **Low / unknown**: bytes 61-62 (type/flag), 525-538 (floats), 541-846; whether the 120-minute default for half of the hotels is real or a placeholder; the effective date or active flag of a hotel (none found in the decoded bytes - there is no `ACTIVEBEG/ACTIVEEND`, so inactive hotels cannot be distinguished except by absence of bookings).
