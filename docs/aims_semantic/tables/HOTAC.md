# HOTAC  (Table)  - Crew hotel accommodation (and related ground-service) bookings per crew member, pairing instance and night

## 1. Purpose & business meaning

`TSC.dbo.HOTAC` is the AIMS **hotel-accommodation (HOTAC) booking table**. A row is one booking line for **one crew member** (or one vacant seat of a pairing) attached to **one pairing instance** (`CDATE` + `CROUTE`), at one supplier at one station, with a check-in and a check-out. It is the layover accommodation that the crew hotel desk (HOTAC module) books and re-books as crew are assigned/bumped; it is also the source for "how far is the hotel" (transit time) in the rest rules and for "was there suitable accommodation during a long gap in an FDP".

`CATEGORY` splits the table into service types:

| CATEGORY | Rows 2026 (by `CHECKINDAY`) | What it is (as far as the data shows) |
|---|---|---|
| **0** | 1,080,072 | **Hotel accommodation**: `SUPPLIER` + `SUPPLIERSTN` identify a `HOTEL` row (100 % join match). The only category the procedures use. |
| 1 | 261,288 | Another service with a supplier that is **not** a hotel (supplier ids up to 484, `SUPPLIERSTN` blank, `FLTNO` and `LEFTSTN` filled): inference = **ground transport / transfer** keyed by flight and station. |
| 4 | 1,258,748 | Same shape as category 1 (suppliers up to 486, `SUPPLIERSTN` blank, `LEFTSTN` filled; 96 % have `FLTNO = 1`): inference = ground transport/transfer (largest volume). |
| 2, 3, 5 | 8,089 / 459 / 14,077 | Small categories with 2, 1 and 1 distinct supplier ids respectively (208..461, 317, 9); nature unknown (other services such as meals / lounge access are possible). |

Planner-assist only needs **category 0** (hotel). The meaning of categories 1-5 is **inferred from column fill patterns, not from code or documentation**.

Grain: one row per (crew or vacancy placeholder, pairing instance, hotel booking line / night). A crew member in a multi-night layover has several rows (one per hotel stay; `CHECKINDAY` differs from `CDATE` when the stay starts after the pairing's first day). **The table is append-heavy and versioned**: the same stay is often inserted several times (different `AUTOINC`, `PROCESSSTATUS` 0 and 1), so duplicates per (`CREWID`, `CDATE`, `CROUTE`, `SUPPLIERSTN`) are normal; the procedures take only `PROCESSSTATUS = 0` rows.

Vacancies: `CREWID < 0` means **no named crew yet**: a vacant seat number of the pairing (`-1`, `-2`, ... `-11`; `-1` alone is 116,983 rows in 2026). `rpt.Get_Detailed_Pairing` links them by `-1 * VacancySeq`; R3 uses `CREWID IN (-1, -2, -3)` to include accommodation reserved for the pairing before crew are assigned.

## 2. Physical facts

* `TSC.dbo.HOTAC`, user table, **8,352,458 rows**, 14 columns; collation `SQL_Latin1_General_CP1_CI_AS` (`SUPPLIERSTN`, `LEFTSTN`).
* **Primary key** `PK_HOTAC` clustered unique on `AUTOINC` (identity); `HOTAC_INDEX_5` is a second unique index on `AUTOINC`.
* Non-unique indexes (every one of them **starts with `PROCESSSTATUS`**, so predicates must include `PROCESSSTATUS = n` to seek):
  * `HOTAC_INDEX_0 (PROCESSSTATUS, CREWID, CHECKINDAY)`: a crew member's bookings by check-in day (R3 uses `CREWID`/`CDATE` filters).
  * `HOTAC_INDEX_1 (PROCESSSTATUS, CATEGORY, SUPPLIERSTN, SUPPLIER, CHECKINDAY)`: bookings of a hotel/supplier at a station per day (hotel desk / supplier reporting).
  * `HOTAC_INDEX_2 (PROCESSSTATUS, REPLACEDWITHID, NAMECHANGESTATUS, CHECKINDAY)`: pending name changes (crew substitutions to communicate to the hotel).
  * `HOTAC_INDEX_3 (PROCESSSTATUS, CHECKINDAY, SUPPLIER, FLTNO, LEFTSTN)`: daily supplier/flight lists (transport orders).
  * `HOTAC_INDEX_4 (PROCESSSTATUS, CROUTE, CDATE)`: bookings of a pairing instance (the path used by `rpt.Get_Detailed_Pairing` and R3 for the drafted pairing).
* History: rows with `CHECKINDAY` from 2018-05-19 (a handful), continuous from 2023 (2023: 578,464; 2024: 2,852,175; 2025: 2,298,452; 2026: 2,622,733) up to 2026-12-24 (future bookings exist); 612 junk rows have `CHECKINDAY` around 1980. 8.4 M rows: **always filter on `PROCESSSTATUS` plus `CREWID`/`CROUTE`+`CDATE`/`CHECKINDAY` range**.

## 3. Column dictionary

Day numbers = days since 1980-01-01 (`DATEADD(DAY, n, '1980-01-01')`).

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| PROCESSSTATUS | tinyint | YES (never NULL) | **Processing status of the booking line.** Every procedure keeps only `PROCESSSTATUS = 0`; R3 describes its filters as "category 0, processed, not cancelled, no airport lounge", so the code authors read `0` as the live/processed state. Data: 0 and 1 only; in 2026 only 339,358 of 2,622,733 rows (13 %) are 0 and 87 % are 1 (older versions of the same stay carry 1). The exact AIMS meaning (live vs superseded/archived) is **not proven**. | 0 / 1 | R3 lines 425 and 461, R3_Batch, `rpt.Get_Detailed_Pairing` line 170; profiled |
| CREWID | int | YES (never NULL) | **Crew member the booking is for** (`ROSTER.ID`), or a **negative vacancy placeholder** when no crew is assigned yet. | `> 0` crew id (2026: 2,476,039 of 2,622,733 rows); `< 0` vacant seat n (2026: 146,694 rows; `-1` 116,983; `-2` 18,506; `-3` 5,146; `-4` 3,535; ... down to `-11`; minimum -23 over the whole table); `0` never. 2,661 distinct real crew in 2026 category 0 live rows. | R3 `h.CREWID = @Crew_ID OR h.CREWID IN (-1, -2, -3)`; `rpt.Get_Detailed_Pairing` `htc.CREWID = COALESCE(pb.ActualCrewId, -1 * pb.VacancySeq)` |
| CHECKINDAY | smallint | YES (never NULL) | **Check-in day of the line** (day number, UTC). Used by `rpt.Get_Detailed_Pairing` as the booking day filter. Equals the check-in day stored in the blob (bytes 1-2) for 80 % of sampled category-0 rows. | Day number. Range 2018-05-19..2026-12-24 (max 17159; minimum day number 6 on 612 junk rows around 1980); `CDATE <> CHECKINDAY` for 1,609,755 of 2,622,733 2026 rows (stays after the first day of the pairing). | `rpt.Get_Detailed_Pairing` `h.CHECKINDAY = @TargetCDate`; profiled |
| CATEGORY | tinyint | YES (never NULL) | **Booking category / service type**: 0 = hotel; 1..5 = other services (see section 1). All procedures filter `CATEGORY = 0`. | 0,1,2,3,4,5. | R3 lines 424 and 460 `h.CATEGORY = 0`; `rpt.Get_Detailed_Pairing` line 170; profiled |
| SUPPLIERSTN | nchar(8) | YES | **Station (airport code) of the hotel supplier** = `HOTEL.AIRPORT` for category 0 (space padded `'LIS     '`). Blank for categories 1-5. In R3 `RTRIM(h.SUPPLIERSTN)` is compared with the station where the FDP gap occurs. | IATA code, collation `SQL_Latin1_General_CP1_CI_AS`. | R3 `ht.AirPort = h.SUPPLIERSTN`; R3 `STN = RTRIM(h.SUPPLIERSTN)` |
| SUPPLIER | smallint | YES (never NULL) | **Supplier number**: for category 0 it is the **hotel number at that station** = `HOTEL.HOTELNO` (1..37 in 2026); for other categories it is a supplier id from a different supplier list (up to 486). | smallint; never 0 in 2026. | R3 `ht.HOTELNO = h.SUPPLIER`; profiled |
| REPLACEDWITHID | int | YES | **Crew id that replaced the original crew member on this booking** (crew substitution); negative = replaced by a vacancy placeholder. Non-zero for 66,186 of 2,622,733 rows in 2026 (replacement by vacancy placeholder -1 / -2 is common). | crew id / negative vacancy / 0 = not replaced | naming inference; index `HOTAC_INDEX_2`; profiled |
| NAMECHANGESTATUS | tinyint | YES | **Name-change workflow status** (crew name on the hotel booking must be changed after a substitution): 0 = none (2,485,775 rows in 2026), 1 (32,324), 2 (104,634); exact meaning of 1 vs 2 (pending vs sent?) unknown. | 0/1/2 | naming inference; index `HOTAC_INDEX_2`; profiled |
| FLTNO | smallint | YES | **Flight number** the line is tied to (for the service categories 1,4: the flight whose arrival/departure triggers the service). Blank/0 for hotel lines (all category 0 rows have `FLTNO = 0`). `FLTNO = 1` on 496,878 category-4 rows (placeholder). | flight number or placeholder 1 | profiled; index `HOTAC_INDEX_3` |
| LEFTSTN | nchar(8) | YES | **Station the crew left/arrive from** for category 1/4 lines (non-blank only for those, e.g. CDG, LGW, FCO, YUL, YYZ, LIS...). Blank for hotels. | IATA code | profiled; index `HOTAC_INDEX_3` |
| CROUTE | bigint | YES | **Pairing instance number** = `CRROUTE.CROUTE` = `ROSTER.DUTYNO` (12-digit key). `> 0` on all but 288 2026 rows (those have `CDATE = 0`). | bigint | R3 `h.CROUTE AS Duty_Number`; join `h.CROUTE = ROSTER.DUTYNO`; `htc.CROUTE = pb.CRoute` |
| CDATE | smallint | YES | **Start day of the pairing instance** = `CRROUTE.CDATE` = `ROSTER.DUTYDAY`. `CDATE < CHECKINDAY` for 1,609,445 of 2,622,733 2026 rows, `CDATE > CHECKINDAY` for 310. | Day number; 0 for 288 rows | R3 `h.CDATE AS DUTYDAY`, `h.CDATE BETWEEN @TargetLegDayFrom AND @TargetLegDayTo` |
| AUTOINC | int identity | NO | Surrogate identity / primary key; 46,638,498..58,995,356 observed (the table is purged: the range is far above the row count). Rows inserted later have higher values; used to see the order of versions of the same stay. | monotonic int | columns.json (idn); profiled |
| DATA_BEGIN_END | binary(1089) | YES | **Packed AIMS record of the booking** (check-in/check-out day + minute, status/flag bytes, text). See 3.1. | binary | R3 / `rpt.Get_Detailed_Pairing` |

### 3.1 Decoded bytes of `DATA_BEGIN_END` (1-based `SUBSTRING` positions)

| Bytes | Meaning | Evidence |
|---|---|---|
| 1-2 | **Check-in day** (smallint little-endian, day number, UTC) | R3 line 453: `CONVERT(SMALLINT, SUBSTRING(h.DATA_BEGIN_END, 2, 1) + SUBSTRING(h.DATA_BEGIN_END, 1, 1))` |
| 3-16 | UTF-16 text of the station (copy of `SUPPLIERSTN`) followed by padding (observed `LIM ` for station LIM) | profiled |
| 17-22 | three consecutive smallints; **21-22 = check-in minute of that day** (minutes since 00:00 UTC of the check-in day; sample: 301, 475, 1380, ...) | R3 line 452 `SUBSTRING(h.DATA_BEGIN_END, 22, 1) + SUBSTRING(h.DATA_BEGIN_END, 21, 1)` |
| 23-24 | **Check-out day** (smallint LE) (`>= CHECKINDAY` for 100 % of sampled category-0 rows) | R3 line 455 |
| 25-42 | station text + padding (as 3-16) and two further smallints (observed equal to the check-out minute) | profiled |
| 43-44 | **Check-out minute** (minutes since 00:00 UTC of the check-out day; **can exceed 1439**: 2,664 of 196,051 sampled category-0 rows) | R3 line 454 |
| 45-46 | byte 45 = 1 and byte 46 in {1,2,5,7} on hotel rows (inference: rooms count and the crew position code - 1 CM, 2 PO, 5 DV, 7 AB - the same values as `ROSTER.POS`) | profiled; unverified |
| 149 | **Exclusion flag byte**: R3 and `rpt.Get_Detailed_Pairing` keep only rows with `CONVERT(TINYINT, SUBSTRING(DATA_BEGIN_END, 149, 1)) = 0`. Values 0 / 1 / 2 (sample, category 0 live rows: 22,696 / 73 / 224). Probably cancelled / no-show / released states (the R3 comment calls it "not cancelled"). | R3 line 426; profiled |
| other | `CAST(DATA_BEGIN_END AS NVARCHAR(300))` is searched for `'AIRPORT LOUNGE'` (see gotcha 4) | R3 line 427 |
| rest of the 1089 bytes | undecoded (padding, remarks) | unknown - not used by any procedure |

## 4. Keys & relationships

* **Primary key**: `AUTOINC`. **Natural key (not unique)**: (`CREWID`, `CDATE`, `CROUTE`, `SUPPLIERSTN`, `SUPPLIER`, check-in day/minute in the blob, `AUTOINC` version).
* **HOTAC -> HOTEL** (N:1, category 0 only): `ht.HOTELNO = h.SUPPLIER AND ht.AIRPORT = h.SUPPLIERSTN` (R3 line 419-421, R3_Batch 382-384, `rpt.Get_Detailed_Pairing` 166: `ht.HOTELNO = h.SUPPLIER AND ht.AirPort = h.SUPPLIERSTN`). Match: 126,067 of 126,067 live category-0 rows in 2026 (100 %); 0 matches for categories 1-5 (their suppliers are not hotels).
* **HOTAC -> ROSTER** (N:1 for real crew): `h.CREWID = r.ID AND h.CDATE = r.DUTYDAY AND h.CROUTE = r.DUTYNO`; 3,000 of 3,000 sampled live category-0 rows with `CREWID > 0` have a roster row. Negative `CREWID` has no roster row.
* **HOTAC -> CRROUTE** (N:1): `c.CDATE = h.CDATE AND c.CROUTE = h.CROUTE`; 2,990 of 3,000 sampled live category-0 rows match (the rest are 0/stale instances).
* **HOTAC -> vvAirports -> COUNTRYCATEG/GENCAT** (country category of the layover station): `a.AIRPORT = h.SUPPLIERSTN`, then `cat.COUNTRY = a.COUNTRY` and `g.GENCATTYPE = 4` (`rpt.Get_Detailed_Pairing` lines 167-169) to label "night stop country".
* **HOTAC -> ROSTERID/CREWID**: `CREWID = ROSTERID.ID` (positive).
* Cardinality: a pairing instance x crew has 0..n hotel rows (one per layover station / night, plus re-inserted versions).

## 5. Encoding conventions & gotchas

1. **Always filter `PROCESSSTATUS = 0 AND CATEGORY = 0`** for current hotel stays, plus flag byte 149 = 0, as the procedures do. Without `PROCESSSTATUS` in the predicate no index can be used (all indexes lead with it) and superseded versions (87 % of 2026 rows) are returned.
2. **Versions/duplicates**: the same stay appears repeatedly (e.g. groups with 1 live + 1 non-live rows are the commonest; some groups have 8-12 non-live rows). Aggregate or use `EXISTS`/`MAX`, never `COUNT(*)` as number of nights.
3. **Times are UTC**: check-in/out = day number + minutes since 00:00 UTC (little-endian smallints inside the blob); the minute can exceed 1439 (check-out after midnight). Compose `DATEADD(MINUTE, minute, DATEADD(DAY, day, '1980-01-01'))`.
4. **Airport-lounge filter does not do what it says**: R3, R3_Batch and `rpt.Get_Detailed_Pairing` test `CHARINDEX('AIRPORT LOUNGE', UPPER(CAST(h.DATA_BEGIN_END AS NVARCHAR(300))))` on the **HOTAC** blob (`h`), and that text never occurs there (0 of 196,051 category-0 rows in a 60-day sample; 0 of 126,067 live 2026 rows). The word 'AIRPORT LOUNGE' lives in the **HOTEL** master name (88 hotels, 1,282 of the 126,067 live 2026 category-0 rows (1.0 %) point to such a hotel). Consequently lounge "stays" are **not** excluded from the rest/accommodation logic. If lounges must be excluded, test `HOTEL.DATA_BEGIN_END` (bytes 1-60).
5. **Negative `CREWID`** = vacancy placeholders; use `IN (-1,-2,-3)` (as R3) only to include pairing-level accommodation; real crew only: `CREWID > 0`.
6. **`CDATE` is the pairing start, not the stay date**; the stay day is `CHECKINDAY` / the blob check-in day. They differ for 62 % of 2026 rows, and `CHECKINDAY` differs from the blob check-in day for 20 % of sampled category-0 rows.
7. `SUPPLIERSTN` and `LEFTSTN` are space padded nchar(8): use `RTRIM`. `HOTEL.AIRPORT` is also nchar(8), so the join is padded-to-padded and safe.
8. Categories 1-5 are other services; do not interpret `SUPPLIER` as a hotel for them.
9. `AUTOINC` is a gapped identity (values ~47-59 M for 8.35 M rows): deletes/purges happen.

## 6. How the planner-assist procedures use it

* **dbo.R3_Get_Violations_RestTime and _Batch**
  * *Phase 3.5 (hotel distance)*: `#R3_HotacData` = per crew/duty the **maximum** hotel `DISTANCE` read from `HOTEL.DATA_BEGIN_END` bytes 539-540 (join `HOTEL ON HOTELNO = SUPPLIER AND AirPort = SUPPLIERSTN`), filters `CATEGORY = 0 AND PROCESSSTATUS = 0 AND byte149 = 0 AND no 'AIRPORT LOUNGE'`, `CDATE` within the crew window, `CREWID = @Crew_ID OR IN ('-1','-2','-3')`. In the rest calculation `Distance_Hotel = 0` when the duty ends at the crew base, otherwise the hotel distance; **minimum rest is reduced by `2 * Distance_Hotel` (`REST_TIME_BEFORE_START_Remove_debrief_and_Transit`)**, i.e. the transit time hotel<->airport is deducted both ways before the rolling rest conditions are tested (R3 lines 821-840: a rest of >= 2160 min (36 h) within the last 7 days and >= 4320 min (72 h) within the last 17 days, measured on this reduced rest).
  * *Phase 3.6 (in-FDP accommodation rest, FD-CAR-2557.2, owner decision 2026-11-02)*: `#R3_HotacStays` decodes check-in/out (UTC) from the blob; an FDP is credited with accommodation rest (`Has_Accom_Rest_3h`) when a gap between two legs of the same duty (debrief end of leg to report of the next) at station `Gap_Station` is >= 180 minutes **and** overlaps a live category-0 stay of the same pairing instance (`hs.CDATE = DUTYDAY AND hs.CROUTE = Duty_Number`), at the same station (`STN = Gap_Station`) for that crew, for a vacancy placeholder (`-1,-2,-3`) or for the drafted pairing (`DUTYDAY = @PairingDutyDay AND Trip_Number = @PAIRING_ID`), by at least 180 minutes. Used for WOCL/FDP extension logic.
* **rpt.Get_Detailed_Pairing**: `Hotac` CTE (`h.CHECKINDAY = @TargetCDate AND h.CROUTE = @TargetCRoute AND h.CATEGORY = 0 AND h.PROCESSSTATUS = 0 AND byte149 = 0`) joined to `HOTEL`, `vvAirports`, `COUNTRYCATEG`, `GENCAT` (type 4 = country category) to output "Night_Stops_Station / Night_Stops_Country" for each crew/vacancy at the arrival station of the leg (`htc.Night_stop_at_station = pb.ARR AND htc.CREWID = COALESCE(pb.ActualCrewId, -1 * pb.VacancySeq)`); R2 notes that a leg with two hotel records can yield duplicate rows.
* R0, R4, R5, `rpt.CalculateCrewFTC`: do not use HOTAC.

## 7. Typical query patterns

```sql
-- 1. Live hotel stays of a crew member in a day range (check-in/out decoded, UTC)
SELECT h.AUTOINC, h.CREWID, h.CDATE, h.CROUTE, RTRIM(h.SUPPLIERSTN) AS station, h.SUPPLIER AS hotel_no,
       DATEADD(MINUTE, CONVERT(int,SUBSTRING(h.DATA_BEGIN_END,21,1)) + 256*CONVERT(int,SUBSTRING(h.DATA_BEGIN_END,22,1)),
               DATEADD(DAY,  CONVERT(int,SUBSTRING(h.DATA_BEGIN_END,1,1))  + 256*CONVERT(int,SUBSTRING(h.DATA_BEGIN_END,2,1)),  '1980-01-01')) AS check_in_utc,
       DATEADD(MINUTE, CONVERT(int,SUBSTRING(h.DATA_BEGIN_END,43,1)) + 256*CONVERT(int,SUBSTRING(h.DATA_BEGIN_END,44,1)),
               DATEADD(DAY,  CONVERT(int,SUBSTRING(h.DATA_BEGIN_END,23,1)) + 256*CONVERT(int,SUBSTRING(h.DATA_BEGIN_END,24,1)), '1980-01-01')) AS check_out_utc
FROM TSC.dbo.HOTAC h
WHERE h.PROCESSSTATUS = 0 AND h.CREWID = @crew_id
  AND h.CHECKINDAY BETWEEN DATEDIFF(DAY,'1980-01-01',@from) AND DATEDIFF(DAY,'1980-01-01',@to)
  AND h.CATEGORY = 0
  AND CONVERT(tinyint, SUBSTRING(h.DATA_BEGIN_END, 149, 1)) = 0;

-- 2. Hotel names/airports/transit distance used by a pairing instance
SELECT RTRIM(h.SUPPLIERSTN) AS station, h.SUPPLIER AS hotel_no, h.CREWID,
       CONVERT(int,SUBSTRING(ht.DATA_BEGIN_END,539,1)) + 256*CONVERT(int,SUBSTRING(ht.DATA_BEGIN_END,540,1)) AS distance_min
FROM TSC.dbo.CRROUTE cro
JOIN TSC.dbo.HOTAC h  ON h.PROCESSSTATUS = 0 AND h.CROUTE = cro.CROUTE AND h.CDATE = cro.CDATE
JOIN TSC.dbo.HOTEL ht ON ht.HOTELNO = h.SUPPLIER AND ht.AIRPORT = h.SUPPLIERSTN
WHERE cro.DESC_ = @pairing_id AND cro.CDATE = DATEDIFF(DAY,'1980-01-01',@pairing_date)
  AND h.CATEGORY = 0 AND CONVERT(tinyint, SUBSTRING(h.DATA_BEGIN_END, 149, 1)) = 0;

-- 3. Vacant-seat accommodation of a pairing (placeholders)
SELECT h.CREWID, RTRIM(h.SUPPLIERSTN) AS station
FROM TSC.dbo.HOTAC h
WHERE h.PROCESSSTATUS = 0 AND h.CATEGORY = 0 AND h.CREWID < 0 AND h.CROUTE = @croute AND h.CDATE = @cdate;
```

## 8. Data profile (measured 2026-11-03)

* 8,352,458 rows; `CHECKINDAY` 2018-05-19 (few) / continuous 2023..2026-12-24; per year 2023 578,464; 2024 2,852,175; 2025 2,298,452; 2026 2,622,733; 612 junk rows ~1980. `AUTOINC` 46,638,498..58,995,356. `CREWID` -23..318,117.
* 2026 by `PROCESSSTATUS` x `CATEGORY` (rows): status 1: cat 4 = 1,078,702; cat 0 = 953,987; cat 1 = 232,697; cat 5 = 10,803; cat 2 = 6,897; cat 3 = 289. Status 0: cat 4 = 180,046; cat 0 = 126,085; cat 1 = 28,591; cat 5 = 3,274; cat 2 = 1,192; cat 3 = 170. Live (status 0) total 339,358 of 2,622,733.
* 2026 live category 0: 125,839 rows with real crew (`CREWID > 0`), 2,661 distinct crew, 90 stations, 37 distinct hotel numbers. Top stations by live rows: CDG 4,938; LGW 3,322; YQB 2,854; YUL 2,801; LIS 2,648; YYZ 2,578; FCO 2,377; LYS 1,950.
* Vacancy placeholders 2026: 146,694 rows with `CREWID < 0` (`-1` 116,983; `-2` 18,506; `-3` 5,146; `-4` 3,535; `-5` 976; `-6` 497; ...).
* `NAMECHANGESTATUS`: 0 -> 2,485,775; 2 -> 104,634; 1 -> 32,324. `REPLACEDWITHID <> 0`: 66,186 rows (2026).
* Flag byte 149 (2026-11 sample, category 0): live rows 22,696 = 0, 224 = 2, 73 = 1; non-live rows 141,182 = 0, 16,159 = 2, 15,717 = 1.
* Check-out minute > 1439: 2,664 of 196,051 sampled category-0 rows.
* `CATEGORY` 1/4: `FLTNO` filled for all and `LEFTSTN` for all; 74 distinct `LEFTSTN` values in 2026.

## 9. Open questions / confidence

* **High (code)**: the filters (`CATEGORY = 0`, `PROCESSSTATUS = 0`, byte 149 = 0), join to `HOTEL`, vacancy placeholders, check-in/out byte positions and UTC encoding, use for hotel distance deduction and in-FDP accommodation rest.
* **Medium**: `CREWID`, `CDATE`/`CROUTE` mapping to `ROSTER`/`CRROUTE` (verified by sampling); `REPLACEDWITHID`/`NAMECHANGESTATUS` = substitution workflow (naming + indexes).
* **Low / unknown**: exact AIMS semantics of `PROCESSSTATUS` 0 vs 1 (only 13 % of rows are 0: "processed" per the R3 comment, but it may also be "active/unprocessed"; the data shows multiple versions of the same stay, with 0 appearing on early and late versions), the values 1 and 2 of flag byte 149, the nature of categories 1-5 (transport and others), bytes 45-46, the rest of the blob, why `CHECKINDAY` differs from the blob check-in day for ~20 % of rows.
* **Likely bug / risk**: the airport-lounge exclusion tests the wrong blob (HOTAC instead of HOTEL), see gotcha 4; lounge bookings (about 1 % of live hotel rows) are therefore counted as accommodation.
* No time-zone information is stored: UTC is assumed from the procedures' usage (they add the values to a `1980-01-01` UTC base and compare with UTC leg times).
