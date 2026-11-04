# vvAirports  (View)  - Airport / station master (codes, coordinates, time-zone key, country, ops flags) - 124 columns

## 1. Purpose & business meaning
`TSC.dbo.vvAirports` is the AIMS "vv" view of the **airport (station) master**. One row = one station known to AIMS, identified by its 3-letter (rarely 4-character) station code
`AIRPORT` (IATA code or an in-house code, e.g. `YUL`, `CDG`, `PUJ`; also pseudo-stations such as rail stations `FCO1`, `ZLN` "GARE LE MANS (TRAIN)" and `CEP8`). It carries
everything AIMS needs about the station: ICAO code, name, **country (ICAO location prefix)**, **latitude/longitude**, **time-zone key** (`ZONENO` + `ZONEAREA`, resolved
together with `COUNTRY` in `vvZONEIDX`), report/debrief and taxi-time rules, slot (SCR/SMA) addressing, language requirements, customs documents, fuel, diversion airports,
helicopter-deck data and many flags. Grain: one row per station; 779 rows (2026-11-03). Maintained by network/ops control (AIMS Airport table); planner-assist only reads it.

Role in planner-assist: (1) **local-time conversion** - `AIRPORT` -> (`COUNTRY`, `ZONENO`, `ZONEAREA`) -> `vvZONEIDX` -> UTC offset incl. DST (functions `GetEffectiveOffset*`);
(2) **`OVERSEAS` flag** - changes the report-time rule for cabin crew; (3) **latitude/longitude** - input of the civil-twilight function (`GetCivilTwilight`); (4) country lookup for
night-stop country categories; (5) name/coordinate lookup for the MCP (`rpt.lookup_airport`).

## 2. Physical facts
- `TSC.dbo.vvAirports`, view (no definition available). 779 rows at 2026-11-03. No row counts/indexes available for views; `AIRPORT` is unique (779 distinct, no duplicates, none blank,
  all upper case, no leading blanks; 776 codes of length 3, 3 of length 4: `CEP8`, `FCO1`, `FCO2`).
- All columns nullable in metadata, but values are padded blanks / 0 rather than NULL (AIMS fixed-record style). Type lengths below: `nchar` in characters (columns.json gives bytes).
- Cheap view (779 rows); lookups by `AIRPORT` are fine. Functions `GetEffectiveOffset*` read it per row with `WHERE vva.AIRPORT = @Station_Code`.

## 3. Column dictionary

### 3.1 Identification and location
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| AIRPORT | nchar(4) | yes | **Station code**: unique key; the same code as `LEGMAIN.DEP/ARR`, `ROSTER.LEG_DEP`, `HOTAC.SUPPLIERSTN`, `CREWQUAL.CWBASE` | 3-letter code (776 rows) or 4-char pseudo-station (3 rows); blank padded | `rpt.lookup_airport.sql`, `dbo.R3_Get_Violations_RestTime.sql:286-287`, `rpt.Get_Detailed_Pairing.sql:306-307` |
| ICAO | nchar(4) | yes | ICAO airport code (CYUL, LFPG...) | 4 letters; blank for 89 stations (pseudo-stations/stations without ICAO); 689 distinct non-blank | profiled |
| COUNTRY | nchar(2) | yes | Country of the airport as the **ICAO location-indicator prefix** (1-2 letters): `CY` Canada, `K` USA, `LF` France, `EG` UK, `LE` Spain, `MM` Mexico, `MD` Dominican Rep., `LP` Portugal, `LK` Czechia, `Y` Australia ... NOT an ISO country code | key part 1 of the time-zone key; joins `vvCountries.COUNTRY` and `COUNTRYCATEG.COUNTRY`; blank for 1 station (`RUN`) | `dbo.GetEffectiveOffset.sql:44-47`, `rpt.Get_Detailed_Pairing.sql:168,289`; profiled |
| TERMINAL | nchar(4) | yes | Terminal / sub-station designator (e.g. `MAIN`, `3C`, `A`) | text; 68 stations non-blank | profiled |
| COTERM | nchar(4) | yes | Co-terminal station: the "city" or metro station this station belongs to (e.g. `SM1`->`YUL`, `YSV`->`YMX`) | station code or blank (16 rows) | profiled |
| MORETER | nchar(4) | yes | Further terminal designator | text; 2 rows | profiled |
| PORTNAM | nchar(40) | yes | Airport name (e.g. "AEROPORT INTL P-E TRUDEAU", "PARIS,CHARLES-DE-GAULE") | free text, upper case; used for name lookup | `rpt.lookup_airport.sql` |
| LONGITUD | nchar(12) | yes | **Longitude** as AIMS text `H DDD MM SS ss` (see Section 5) | `E`/`W` + `DDD` degrees + `MM` minutes + `SSss` seconds in hundredths: `W073442900` = 73 deg 44 min 29.00 s West. 724 rows 10 chars, 21 rows with a dotted variant (`E0001412.00`), 19 blank, 1 `' 000000000'` | `dbo.GetCivilTwilight.sql:44-47`; profiled |
| LATITUDE | nchar(12) | yes | **Latitude** as AIMS text `H DD MM SS ss` | `N`/`S` + `DD` + `MM` + `SSss`: `N45280500` = 45 deg 28 min 05.00 s North. 723 rows 9 chars, 21 dotted (`N142300.00`), 3 short (7 chars), 19 blank, 1 `' 00000000'` (`ZLN`) | `dbo.GetCivilTwilight.sql:38-41`; `rpt.lookup_airport.sql` returns it as `Latitude`; profiled |
| ELEVATION | smallint | yes | Airport elevation | feet (inference), 180 stations non-zero | profiled |
| LONGEST_RWY | smallint | yes | Longest runway length | 1 station non-zero (mostly unpopulated) | profiled |
| STATEPROVINCE | nchar(3) | yes | State / province code | all blank in data | profiled |
| ALTAIRPORTCODE | nchar(4) | yes | Alternate airport code | all blank in data | profiled |
| FIRECAT | tinyint | yes | RFF (fire-fighting) category of the airport | code | naming inference; not used |

### 3.2 Time zone, DST, UTC/local flags (what local-time conversion depends on)
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| ZONENO | tinyint | yes | **Time-zone number inside the country** (key part 2). 0 = not assigned | 0..6 (0: 5 stations - `ECP`, `YTM`, `BYJ`, `TSF`, `CAX`; 1: 569; 2: 76; 3: 66; 4: 27; 5: 18; 6: 18). Canada: 1 Newfoundland, 2 Atlantic, 3 Eastern, 4 Central, 5 Mountain, 6 Pacific | `dbo.GetEffectiveOffset.sql:44-47`; profiled |
| ZONEAREA | nchar(1) | yes | **Sub-area of the zone** (key part 3): blank = main area; `A`/`B` = special sub-area with its own rules (e.g. `CY 4 A` Saskatchewan, `CY 3 A` "Eastern2" no-DST) | blank (762 rows), `A` (16), `B` (1) | same; profiled |
| NEWZONENO | tinyint | yes | **Planned future zone number** (zone change effective at `VALIDUNTIL`/`CHANGETIME`) | 0 for all 779 rows (feature unused) | profiled; naming inference |
| NEWZONEAREA | nchar(1) | yes | Planned future zone area | blank for all rows | profiled |
| VALIDUNTIL | smallint | yes | Day number until which the current zone applies (AIMS day number from 1980-01-01) | 0 for all rows | profiled; naming inference |
| CHANGETIME | smallint | yes | Minute of day at which the zone change takes effect | 0 for all rows | profiled; naming inference |
| DATEFLAG | tinyint | yes | Flag for the date/zone-change mechanism | 0 for all rows | profiled; naming inference |
| UNUSED_TIME_DIF | smallint | yes | Legacy fixed time difference to UTC (no longer used) | 1 non-zero row | profiled; name says "unused" |
| UTCORLOCAL | tinyint | yes | Whether the station's stored times are UTC or local | 0 for all rows | profiled; semantic inferred |
| SCR_UTC_LOCAL | tinyint | yes | Whether slot-coordination (SCR) messages use UTC or local times | 0 (657), 32 (104), 1 (18) | profiled |
| EFFECTIVE_DATE / EFFECTIVE_TYPE | smallint / tinyint | yes | Effective-date pair for a station attribute change (date, kind of change) | 7 rows non-zero date | naming inference; not used |

### 3.3 Flags used by crew-rule procedures
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| OVERSEAS | tinyint | yes | **Overseas / long-haul destination flag**. 1 for 149 stations (e.g. most of France `LF` 38 of 61, UK 18 of 40, Germany 8 of 21, Spain 10 of 27, Italy 9, `HNL`), 0 for all 106 Canadian stations, 159 of 163 US stations (the 4 US stations with 1 include `HNL`), and for Mexico, Caribbean, Brazil (`GRU` 0) and Australia (`SYD` 0). Hence it is the airline's **trans-ocean ("overseas") station** flag, not a country test | 0 / 1 | `dbo.R3_Get_Violations_RestTime.sql:264`, `dbo.R4_Get_Violation_FDP.sql:329-330`, `dbo.R5_Get_Violation_FTC.sql:331-332`, `rpt.CalculateCrewFTC.sql:214-215`, `rpt.Get_Detailed_Pairing.sql:231-232` |
| ACHOMEBASE | tinyint | yes | Station is an aircraft/crew home base | 0 (690), 1 (23), 32 (66: probably a bit flag) - `YUL`, `YYZ`, `YQB`, `CDG` = 1 | profiled; semantic inferred; not used |
| USE_REPTYPE | tinyint | yes | Report-time type (index into AIMS report-time table) the station uses | 0 (310), 4, 6, 7, 11, 12, 14 (75), 15 (270), 32 (111), 40; `YUL` = 4, `CDG` = 6, most others 14/15 | profiled; semantic inferred; not used (procedures use fixed offsets) |
| FLAGS | tinyint | yes | Misc. flag byte | unused in data (0) | profiled |

### 3.4 Report / debrief time rules per airport (not used by procedures)
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| AIRP_REP_DEB_1_ACS | varbinary(12) | yes | Aircraft-type bitmap the cockpit report/debrief rule #1 applies to | bitmask of `AIRCTYPE.ACORDER` | naming inference |
| AIRP_REP_DEB_1_REPORT / _DEBRIEF | tinyint | yes | Cockpit report (before dep.) / debrief (after arr.) time rule #1 | minutes; 3 stations non-zero | profiled |
| AIRP_REP_DEB_2_ACS / _REPORT / _DEBRIEF | varbinary(12) / tinyint / tinyint | yes | Rule #2 | as above | naming inference |
| AIRP_PAXAIR_REPORT / _DEBRIEF | tinyint | yes | Report/debrief for crew travelling as passengers on a flight (deadhead by air) | minutes | naming inference |
| AIRP_PAXGRND_REPORT / _DEBRIEF | tinyint | yes | Same for deadheading by ground transport | minutes | naming inference |
| AIRP_CB_REP_DEB_1_ACS / _REPORT / _DEBRIEF, AIRP_CB_REP_DEB_2_ACS / _REPORT / _DEBRIEF | varbinary(12) / tinyint / tinyint | yes | Same rules for **cabin** crew ("CB" = cabin) | minutes | naming inference |
| AIRP_CB_PAXAIR_REPORT / _DEBRIEF, AIRP_CB_PAXGRND_REPORT / _DEBRIEF | tinyint | yes | Cabin crew deadhead report/debrief by air / by ground | minutes | naming inference |
| TAXI_DEP / TAXI_ARR | smallint | yes | Standard taxi-out / taxi-in time at the station | minutes; 66 stations non-zero (e.g. `CDG` 15/10, `YWG` 10/5) | profiled |
| MINPASSENGERTM / MINCARGOTM | smallint | yes | Minimum passenger / cargo ground (transfer) time | minutes | naming inference |
| CK_LNDG / CK_BRIEF | tinyint | yes | Checkbox: landing check / briefing required | 0/1 | naming inference |

> IMPORTANT: planner-assist procedures do **not** read these per-airport report/debrief columns; they use constants (report -60 min, -80 min for overseas PNC, debrief +15 min). See `dbo.R3_Get_Violations_RestTime.sql:61-63`.

### 3.5 Slot coordination (SCR / SMA) and handling
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| SCR_OR_SMA | tinyint | yes | Station requires SCR (schedule change request) or SMA (slot message) coordination | code | naming inference; not used |
| SCRADDR_1 / SCRADDR_2 | nchar(8) | yes | SITA/AFTN addresses for slot messages | text | naming inference |
| SCR_DATEFROM1 / SCR_DATETO1 ... SCR_DATEFROM4 / SCR_DATETO4 | smallint x8 | yes | Date ranges (day numbers) for which slot coordination is active (up to four seasons) | AIMS day numbers; 34 stations have range 1 | profiled; naming inference |
| HISTORIC_RATE | tinyint | yes | Historic-slot rate | code | naming inference |
| DECLARATION_COPIES / MANIFEST_COPIES | smallint | yes | Number of customs declaration / manifest copies | count | naming inference |
| DOCUMENTS | tinyint | yes | Documents-required code | code | naming inference |
| GROUND_EQUIPMENT | tinyint | yes | Ground-equipment code | code | naming inference |
| NUM_FROM / NUM_TO | smallint | yes | Number range allocated to the station (e.g. flight/message numbering) | unknown - not used | naming inference |
| ALL_CONTACTS | tinyint | yes | Link/flag to the contacts list of the station | unknown - not used | naming inference |
| IVR_NAME / IVR_LETTERCD / IVR_NAME2 / IVR_LETTERCD2 | nchar(40)/nchar(4)/nchar(30)/nchar(4) | yes | Names and letter codes for the IVR (voice response) crew-call system | text; 10 stations | profiled; naming inference |
| HEADINFO | nchar(3) | yes | Header information | blank in data | profiled |
| CATEG_CATEGBYT | varbinary(4) | yes | Station-category bitmap (13 stations non-zero); the authoritative category data is in `PORTCATEG`/`PORTCATEG2` | bitmask | profiled |
| FUTAIRCATEG | tinyint | yes | Reserved airport category | unused | naming inference |
| USER_ | smallint | yes | Id of the AIMS user who last changed the row | user id | naming inference |
| FUTURE | varbinary(47) | yes | Reserved bytes | unused | naming inference |

### 3.6 Diversion airports, fuel, language and misc.
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| FREQ_1 / FREQ_2 | nchar(10) | yes | Radio frequencies | text | naming inference |
| DIVERT_1_AIRPORT / DIVERT_1_DISTANCE ... DIVERT_4_AIRPORT / DIVERT_4_DISTANCE | nchar(4) + smallint, x4 | yes | Up to four diversion (alternate) airports and the distance to each | station code + nm; 5 stations have an alternate | profiled |
| FUEL_CURRENCY / FUEL_UNIT | nchar(2) / smallint | yes | Fuel price currency / unit | code | naming inference |
| TAX_FREE_SAL_1 / _2 / _3 | float x3 | yes | Tax-free salary thresholds for the station | money | naming inference |
| LANGREQ_1_NUM / _LANG / _POS ... LANGREQ_4_NUM / _LANG / _POS | tinyint, tinyint, varbinary(3), x4 | yes | Language requirements at the station: number of crew members of position bitmap `_POS` who must speak language `_LANG` | count / language id / `vvPositions` bitmap | naming inference |
| LANG_1 / LANG_2 | tinyint | yes | Main languages of the station | language id | naming inference |
| EUROC_OK | tinyint | yes | Eurocontrol-compliance OK flag | 0/1 | naming inference |

### 3.7 Helicopter-deck data (CHC)
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| CHC_LOCATION | smallint | yes | Helicopter location code | unknown - not used | naming inference |
| CHC_FUEL_AVL_FROM / CHC_FUEL_AVL_TO | smallint | yes | Period fuel is available | minutes of day | naming inference |
| CHC_DECK_AVL_FROM / CHC_DECK_AVL_TO | smallint | yes | Period the deck is available | minutes of day | naming inference |
| CHC_EDTHELHGHT | smallint | yes | Helideck height | unknown | naming inference |
| CHC_CKIMPEFB | tinyint | yes | Checkbox: impose ... flight bulletin | unknown | naming inference |
| CHC_CKBNOUSEFDIVER | tinyint | yes | Checkbox: do not use as diversion | unknown | naming inference |
| CHC_CKNOTEFB | tinyint | yes | Checkbox: note on flight bulletin | unknown | naming inference |
| CHC_MAXWGHT | smallint | yes | Maximum weight allowed | unknown | naming inference |

## 4. Keys & relationships
- Natural key: `AIRPORT` (unique).
- **Time zone**: `vvAirports (COUNTRY, ZONENO, ZONEAREA)` -> `vvZONEIDX (COUNTRY, ZONENO, ZONEAREA)` N:1. Exact predicate (all three `GetEffectiveOffset*` functions):
  `INNER JOIN TSC.dbo.vvZONEIDX vvz ON vvz.COUNTRY = vva.COUNTRY AND vvz.ZONENO = vva.ZONENO AND vvz.ZONEAREA = vva.ZONEAREA WHERE vva.AIRPORT = @Station_Code` (`dbo.GetEffectiveOffset.sql:44-48`).
  Measured: 774 of 779 stations match; the 5 stations with `ZONENO = 0` do not (they return **no row -> NULL offset**).
- **Flight legs**: `LEGMAIN.DEP = vvAirports.AIRPORT` (departure) and `LEGMAIN.ARR = vvAirports.AIRPORT` (arrival); also `ROSTER.LEG_DEP`. Predicates: `LEFT JOIN TSC.dbo.vvAirports AS dep_arp ON dep_arp.AIRPORT = r.LEG_DEP` / `... arr_arp ON arr_arp.AIRPORT = lm.ARR` (`dbo.R4_Get_Violation_FDP.sql:387-388`; R3, R5, `rpt.CalculateCrewFTC` same). All 7,198 legs of 2026-10-01..2026-11-30 (LEGMAIN.DAY 17075-17135) match both ends; none has `ZONENO = 0`.
- **Hotels / night-stop country**: `HOTAC.SUPPLIERSTN = vvAirports.AIRPORT`, then `COUNTRYCATEG.COUNTRY = vvAirports.COUNTRY` (`rpt.Get_Detailed_Pairing.sql:166-169`); `COUNTRYCATEG.Country = (SELECT TOP 1 Country FROM vvAirports WHERE AIRPORT = ARR)` (`:289`).
- **Country**: `vvAirports.COUNTRY = vvCountries.COUNTRY` (N:1; all stations match except `RUN` with blank country).
- **Crew base**: `CREWQUAL.CWBASE` holds a station code and is used as `GetEffectiveOffset*('YUL', ...)` (station code domain of this view).
- `PORTCATEG.STATION` / `PORTCATEG2.STATION` = `AIRPORT` (airport categories), `CITYCATEG.STN1/STN2`.

## 5. Encoding conventions & gotchas
- **Station codes are blank-padded `nchar(4)`**: `=` comparisons ignore trailing blanks; never pass a 4-char ICAO code (`CYUL`) - `AIRPORT` is IATA (`YUL`). The offset functions even declare `@Station_Code NVARCHAR(3)`, so the 3 four-character pseudo-stations (`CEP8`, `FCO1`, `FCO2`) can never be resolved.
- **COUNTRY is the ICAO prefix, not ISO**: `CY` (Canada), `K` (USA), `Y` (Australia), `LF`, `EG`... Join to `vvCountries.COUNTRY` (ICAO prefix); the ISO alpha-3 / alpha-2 are `vvCountries.UNCODE` / `IATACODE`. The prefix can be a single character (`K` USA, `Y` Australia, `Z` China, `V` India, `W` Indonesia, `R` Japan, `U` Russia).
- **Time-zone resolution is 3-part**: country + `ZONENO` + `ZONEAREA`. `ZONEAREA` is a 1-char `nchar` (blank = main). A blank country (`RUN`, St-Denis Reunion) joins the blank-country row of `vvZONEIDX` (UTC+2): a data issue (Reunion is UTC+4). `YWG` (Winnipeg) is mapped to `CY / 3 / A` = "Eastern2" (UTC-5, no DST) so the functions return -5 all year although Winnipeg is on Central time (observed: -5.00 on 2026-01-01 and 2026-07-01; `crew_base_timezone` says CST/CDT -360). Reported as observation of master data, to be confirmed.
- **UTC offsets are not stored here**: the numeric offset (`TIMEDIFF`, `DSTDIFF` in **minutes**) and the DST rule are in `vvZONEIDX`. Always compute it with `CrewSchedAI.dbo.GetEffectiveOffset*` (hours, decimal, e.g. +5.5 for BOM, -3.5 for YYT winter) and add `offset*60` minutes to a UTC instant to get local time.
- **Coordinates** are text with a hemisphere letter and no separators: latitude `H DD MM SSss`, longitude `H DDD MM SSss` (the last two digits of the seconds = hundredths). Decimal degrees = `DD + MM/60 + (SSss/100)/3600`, sign negative for `S`/`W` (as in `GetCivilTwilight`). Irregular rows: 21 stations use a dotted variant (e.g. `N240500.00`, `S101400.0`) where the function mis-scales the seconds (error at most 1 minute of arc, harmless); 19 stations have blank coordinates and 1 (`ZLN`) has `' 00000000'`: the twilight function then computes for latitude 0 / longitude 0 **and returns status `Normal`** (no error).
- **OVERSEAS is not a country test**: use it only as the airline's rule flag (cabin-crew report time -80 min on a leg with an overseas end if not deadheading, -30 min if deadheading), not to decide "international". Note `rpt.Get_Detailed_Pairing` nevertheless labels `Is_International = 'Yes'` when either end has `OVERSEAS = 1`, which marks Mexico/Caribbean/Brazil/US flights as `No` (inference: output field name overstates the meaning).
- Unused future-change fields (`NEWZONENO`, `NEWZONEAREA`, `VALIDUNTIL`, `CHANGETIME`, `DATEFLAG`) are 0 for every row: the station master can express a future zone change but none is configured, and the offset functions do not evaluate them in any case.
- Columns are fixed-width AIMS fields: empty text is blanks (never NULL), empty numbers are 0. Test with `RTRIM(col) = ''`.
- Do not `SELECT *` on this view in an agent: 124 columns of which ~100 are unused technical data.

## 6. How the planner-assist procedures use it
| Procedure | Columns | Why |
|---|---|---|
| `dbo.GetEffectiveOffset`, `_v1`, `GetEffectiveOffsetUtc` (CrewSchedAI) | `AIRPORT`, `COUNTRY`, `ZONENO`, `ZONEAREA` | station -> time-zone key -> UTC offset incl. DST |
| `dbo.R3_Get_Violations_RestTime(_Batch)` | `AIRPORT` (join on `LEG_DEP`, `ARR`), `OVERSEAS` | cabin-crew report offset (-80 overseas, non-deadhead) in the rest-time (duty-start) computation; UTC offsets of dep/arr stations via `GetEffectiveOffsetUtc` (R3-15 item 8) for acclimatisation (bio-clock) and local-night rest (LNR) / WOCL |
| `dbo.R4_Get_Violation_FDP` | `OVERSEAS` | report offset -80 (PNC, overseas, non-deadhead) / -30 (PNC overseas deadhead); station offsets via `GetEffectiveOffset` for the acclimatisation (bio-clock) logic of the FDP check |
| `dbo.R5_Get_Violation_FTC`, `rpt.CalculateCrewFTC` | `OVERSEAS` | report/debrief adjustment of the duty for FTC (-80 / -30 minutes for cabin crew) |
| `rpt.Get_Detailed_Pairing` | `OVERSEAS`, `LATITUDE`, `LONGITUD`, `COUNTRY`, `AIRPORT` | `Is_International`/`Is_Domestic`, civil twilight at the departure airport (`GetCivilTwilight(dep_arp.LATITUDE, dep_arp.LONGITUD, ...)`), night-stop country (`COUNTRYCATEG` via `COUNTRY`) |
| `rpt.lookup_airport` | `AIRPORT`, `PORTNAM`, `LONGITUD`, `LATITUDE` | MCP tool that looks up a station by code or exact name and returns the coordinates as raw AIMS text |
| `dbo.R0_GetDraftList` | none directly (uses `crew_base_timezone` for the base) | - |

## 7. Typical query patterns
```sql
-- station lookup (code OR name); coordinates are AIMS text, not decimal degrees
SELECT LTRIM(RTRIM(AIRPORT)) AS Station_Code, LTRIM(RTRIM(ICAO)) AS ICAO, LTRIM(RTRIM(COUNTRY)) AS ICAO_Country_Prefix,
       LTRIM(RTRIM(PORTNAM)) AS Airport_Name, LATITUDE, LONGITUD, ZONENO, ZONEAREA, OVERSEAS
FROM TSC.dbo.vvAirports
WHERE AIRPORT = 'YUL';

-- local time of a UTC instant at a station (hours offset from the CrewSchedAI function)
SELECT DATEADD(MINUTE, CAST(ROUND(o.Effective_UTC_Offset * 60, 0) AS INT), CAST('2026-11-05T14:30:00' AS DATETIME)) AS Local_Time
FROM CrewSchedAI.dbo.GetEffectiveOffsetUtc(N'CDG', CAST('2026-11-05T14:30:00' AS DATETIME)) AS o;

-- stations without a usable time zone (offset would be NULL)
SELECT a.AIRPORT, a.COUNTRY, a.ZONENO, a.ZONEAREA
FROM TSC.dbo.vvAirports a
LEFT JOIN TSC.dbo.vvZONEIDX z ON z.COUNTRY = a.COUNTRY AND z.ZONENO = a.ZONENO AND z.ZONEAREA = a.ZONEAREA
WHERE z.COUNTRY IS NULL;

-- airports of a country with their country name
SELECT a.AIRPORT, LTRIM(RTRIM(a.PORTNAM)) AS Name, LTRIM(RTRIM(c.NAME)) AS Country
FROM TSC.dbo.vvAirports a JOIN TSC.dbo.vvCountries c ON c.COUNTRY = a.COUNTRY
WHERE c.UNCODE = 'CAN';
```

## 8. Data profile (measured 2026-11-03)
- 779 stations, 779 distinct `AIRPORT`, 689 distinct non-blank `ICAO` (89 blank), 129 distinct `COUNTRY`, 1 blank country (`RUN`).
- Largest countries by station count: `K` 163, `CY` 106, `LF` 61, `EG` 40, `LE` 27, `MM` 25, `LI` 23, `R` 23, `ED` 21, `W` 13.
- `ZONENO`: 0 -> 5, 1 -> 569, 2 -> 76, 3 -> 66, 4 -> 27, 5 -> 18, 6 -> 18. `ZONEAREA`: blank 762, `A` 16, `B` 1.
- `OVERSEAS`: 0 = 630, 1 = 149. `UTCORLOCAL` = 0 for all; `NEWZONENO`/`VALIDUNTIL`/`CHANGETIME`/`DATEFLAG` = 0 for all.
- Coordinates: 19 blank, 1 zeros, 24 dotted/short variants, 735 regular. 158 distinct departure stations in LEGMAIN.DAY 16800-17135 (2025-12-30..2026-11-30); busiest departures 2026-10-01..11-30: `YUL`, `YYZ`, `YQB`, `CDG`, `PUJ`, `CUN`, `LIS`, `LGW`, `YOW`.
- Sample offsets from `GetEffectiveOffset` (hours): YUL -5 (Jan) / -4 (Jul); YVR -7 (Jul); CDG +2 (Jul); BOM +5.5; YYT -3.5 (Jan) / -2.5 (Jul); CUN -5 all year; RUN +2 (data issue); YWG -5 all year (data issue).

## 9. Open questions / confidence
- High confidence: `AIRPORT`, `COUNTRY` (ICAO prefix), `ZONENO`/`ZONEAREA` as time-zone key, coordinate format (verified by running `GetCivilTwilight`), `OVERSEAS` use in code.
- Medium: exact business meaning of `OVERSEAS` (airline-defined; derived from data pattern - includes Europe and `HNL`, excludes Mexico/Caribbean/Brazil/Australia).
- Low/unknown: `ACHOMEBASE` (values 0/1/32), `USE_REPTYPE`, `UTCORLOCAL`, all slot/IVR/CHC/LANGREQ columns - inferred from names only and unused by any procedure.
- Master-data suspicions to confirm with the business: `YWG` zone (CY/3/A, no DST), `RUN` blank country/UTC+2, `ZONENO = 0` stations, 19 stations without coordinates.

