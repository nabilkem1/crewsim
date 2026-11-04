# vvCarriers  (View)  - Carrier master (airlines AND ground-transport / rail / car suppliers), 40 columns

## 1. Purpose & business meaning
`TSC.dbo.vvCarriers` is the AIMS "vv" view of the **carrier master**. One row = one carrier code that can appear as the *carrier* of a flight leg or of a crew leg: the home airline
itself (`ID 1`, `CODE = TSC`, name "AirTransat" - the database name TSC is this carrier code), partner/codeshare airlines used for deadheading (BA, AF, AC, WS, PD ...), and - important
for crew rules - **ground-transport suppliers** (taxi, limousine/bus companies, "own transport", car-rental firms, rail operators such as TGV/SNCF/AccesRail) that AIMS models as carriers so a
crew can be moved "on a flight" that is really a taxi, bus or train. The `CAT` and `GROUNDCATEGORY` columns tell airline from ground transport and which kind of ground transport.
Besides the code/classification, the row holds the supplier's contact data, payment/currency settings, SITA addresses and default report/off-duty times (all unused by planner-assist).

Grain: one row per carrier; 346 rows (2026-11-03). Maintained by operations/crew-transport staff; planner-assist reads it only.

## 2. Physical facts
- `TSC.dbo.vvCarriers`, view (no definition available). 346 rows; `ID` 1..490 with gaps, 346 distinct `ID`, 346 distinct `CODE`.
- Type lengths: `nchar` in characters (columns.json reports bytes).
- Cheap (346 rows). In procedures it is joined by `ID` with a LEFT JOIN, once per leg row.

## 3. Column dictionary

### 3.1 Identity and classification
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| ID | smallint | yes | **Carrier id**: the value stored in `LEGMAIN.CARRIER`, `CREWLEG.CARRIER`, `ROSTER.LEG_CARRIER`, `CRLEGGROUND.CARRIER` | 1..490; `1` = home carrier (`TSC`); join key | `dbo.R3_Get_Violations_RestTime.sql:288`, `rpt.Get_Detailed_Pairing.sql:308`; profiled |
| CODE | nchar(4) | yes | Carrier code shown to users: 2-letter IATA airline code or in-house code (`TSC`, `BA`, `AC`, `WS`, `NAT`, `TAX`, `YULO`, `TR`) | unique; `rpt.Get_Detailed_Pairing` outputs it as `Carrier_Code` | `rpt.Get_Detailed_Pairing.sql:211` |
| ALTCODE | nchar(4) | yes | Alternative code (3-letter ICAO or a second code) | blank for most; e.g. `TSC`->`TS`, `GA`->`GIA`, `TR`->`TGV` | profiled |
| CAT | tinyint | yes | **Carrier category: 0 = airline, 1 = ground transport / non-airline supplier** (taxi, bus/limo, own transport, car rental, train booked as ground, `AIR JET SERVICES`) | 0 (187 rows), 1 (159 rows) | `dbo.R4_Get_Violation_FDP.sql:332-346`, `dbo.R5_Get_Violation_FTC.sql:297-299,334-335`, `rpt.CalculateCrewFTC.sql:197-199,217-218`; profiled |
| GROUNDCATEGORY | tinyint | yes | Kind of ground transport (meaningful when `CAT = 1`): `1` taxi, `2` bus / limousine / coach / shuttle (149 rows), `3` own transport / car, `4` train (TGV, rail), `0` = none / other (car-rental firms, air-jet service) | 0..4; (CAT,GROUNDCATEGORY) combos: (0,0) 185, (0,4) 2 [SNCF `2C`, AccesRail `9B` rail operators coded as airlines], (1,0) 4, (1,1) 2, (1,2) 149, (1,3) 2, (1,4) 2 | `dbo.R4_Get_Violation_FDP.sql:332`; profiled; labels inferred from names of members |
| CARRIER_CAT | nchar(2) | yes | Carrier category/class code | blank for all rows in data | profiled; naming inference |
| PRIMARYCARRIER | tinyint | yes | Flag: this is the primary (own) carrier of the airline group | 0 for all 346 rows | profiled; naming inference |
| NAME | nchar(30) | yes | Carrier name (e.g. "AirTransat", "WestJet", "TRAIN-TGV", "Own transport", "LIMOTOUR") | free text, mixed case; some placeholder names equal the code (`W9`, `P5`) | profiled |
| COMPANYCODE | nchar(2) | yes | Company code in the accounting system | blank for all | profiled |
| COMPANYBASE | nchar(4) | yes | Home base of the company | blank for all | profiled |
| COMB_GRND_TRANSP | tinyint | yes | Combined ground transport flag (carrier is combined air + ground) | 0/1 | naming inference; not used |

### 3.2 Contact, payment, accounting (personal/company data; not used by planner-assist; values not profiled beyond fill rates)
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| CONTACT_NAME | nchar(30) | yes | Name of the supplier's contact person (personal data - do not output) | 196 rows filled | profiled (fill rate only) |
| POSITION | nchar(30) | yes | Job title of the contact | text | naming inference |
| TEL_1, TEL_2, TEL_3 | nchar(20) | yes | Telephone numbers (134 rows have TEL_1) | text | profiled (fill rate) |
| TELTYPE_1, TELTYPE_2, TELTYPE_3 | tinyint | yes | Type of each phone number (voice, fax, mobile...) | code | naming inference |
| E_MAIL, E_MAIL2 | nchar(70) | yes | E-mail addresses (116 rows have E_MAIL) | text | profiled (fill rate) |
| WEBSITE | nchar(40) | yes | Web site | blank for all | profiled |
| SITA1, SITA2 | nchar(8) | yes | SITA addresses (2 rows filled) | text | profiled |
| CURRENCY_ | smallint | yes | Currency id of the supplier's tariff (302 rows set) | currency index (see `vvCountries.CURRCY`) | naming inference |
| RATE | real | yes | Rate / tariff | 0 for all rows | profiled |
| PAYMETHOD | tinyint | yes | Payment method | 0 for 342 rows, 1 for 2, 2 for 2 | profiled |
| ACCOUNT_REF | nchar(15) | yes | Accounting account reference | blank | naming inference |
| VENDOR_NO | nchar(7) | yes | Vendor number in the finance system | blank | naming inference |
| ID50STATUS | tinyint | yes | ID50 (staff travel discount ticket) eligibility status | 1 for 274, 0 for 72 | profiled; naming inference |
| ALLOWNAMECHANGE | tinyint | yes | Name changes allowed on bookings with this carrier | 0/1 (83 rows = 1) | profiled; naming inference |
| TRANSREQ | tinyint | yes | Transport requested/required flag | 0 | naming inference |
| AUTOADJUSTTMS | tinyint | yes | Auto-adjust times flag | 0 | naming inference |
| PASSENGERCAPACITY | tinyint | yes | Passenger capacity of the ground vehicle (bus/taxi) | 0 | naming inference |
| FUTURE | varbinary(239) | yes | Reserved bytes | unused | naming inference |

### 3.3 Default crew report / off-duty times for ground transport
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| CK_REPTIME | smallint | yes | Cockpit report time offset when travelling with this carrier | minutes; 0 for all rows | profiled |
| CK_OFFTIME | smallint | yes | Cockpit off-duty (debrief) time offset | minutes; 0 for all | profiled |
| CB_REPTIME | smallint | yes | Cabin crew report time offset | minutes; 0 for all | profiled |
| CB_OFFTIME | smallint | yes | Cabin crew off-duty time offset | minutes; 0 for all | profiled |
| GRND_TIME | smallint | yes | Ground-transport time | minutes; 1 row non-zero | profiled |

> Planner-assist does NOT use these columns; it hard-codes the report/debrief offsets and uses `CAT` / `GROUNDCATEGORY` only.

## 4. Keys & relationships
- Natural key: `ID` (and `CODE`, both unique).
- `vvCarriers.ID` = `LEGMAIN.CARRIER` (1:N; every one of the 13,656 legs of LEGMAIN.DAY 17000-17100 matches) and = `CREWLEG.CARRIER`, `ROSTER.LEG_CARRIER`.
  Predicate: `LEFT JOIN TSC.DBO.vvCarriers crr on crr.ID = r.LEG_CARRIER` (`dbo.R3_Get_Violations_RestTime.sql:288`, `R4:389`, `R5:393`, `rpt.CalculateCrewFTC.sql:243`); `crr.ID = CARRIER` (`rpt.Get_Detailed_Pairing.sql:308`).
- `vvAIRCTYPE.ACTYPEOWNER` = `vvCarriers.ID` (inference from values).

## 5. Encoding conventions & gotchas
- **Rule flag**: `CAT = 1` means "this leg is ground transport (taxi/bus/train/own)", not a flight. In the duty/FTC computations:
  - cabin crew deadheading (`PAX = 1`) on `CAT = 1` with scheduled time >= 60 min credit **half** the scheduled time (`(STA-STD)*0.5`), under 60 min credit 0 (R5 / FTC);
  - report offset of the leg (R4 / R5 / FTC): after the cabin-crew overseas/deadhead cases (-80 / -30), a pilot on `CAT = 1 and GROUNDCATEGORY = 4` (train) reports 60 min before (-60); any other leg of a `CAT = 1` carrier gets 0 min before departure; every flight leg (`CAT = 0`) gets -60;\n  - debrief offset after arrival (R4): a deadheading crew member (`PAX = 1`) on a `CAT = 1` carrier gets 0 min, everyone else +15.
- `GROUNDCATEGORY` is only meaningful with `CAT = 1`; two rail operators (`2C` SNCF, `9B` AccesRail) are `CAT = 0` with `GROUNDCATEGORY = 4` and are NOT treated as ground transport by those `CAT = 1` tests (inference: possibly a data-entry inconsistency).
- The home carrier is `ID = 1`/`CODE = 'TSC'` (8,754 of 13,656 legs in LEGMAIN.DAY 17000-17100 = 2026-07-18..2026-10-26; next: `OWN` own transport, `AC`, `NAT`, `AF`). Flights flown by the home airline are those with `ID = 1`.
- Placeholder rows exist with `NAME` = `CODE` (`W9`, `P5`...) or `NAME` blank (`AGP` train-station carrier): treat as unmaintained.
- `CODE` is blank padded `nchar(4)` ('AC  '): trim before comparing/displaying.
- Contact columns contain personal contact data: do not expose them in text-to-SQL answers.

## 6. How the planner-assist procedures use it
- `dbo.R3_Get_Violations_RestTime` / `_Batch` (`:243/:252`, `:272/:288`): `crr.CAT = 1` in the cabin-crew deadhead-credit rule (`(lm.STA - lm.STD) * 0.5` for ground legs of >= 60 min).
- `dbo.R4_Get_Violation_FDP` (`:332-333, :346, :358, :370`): report offset by carrier category (see above) and "deadhead on ground transport" exceptions in the FDP/duty-time computation.
- `dbo.R5_Get_Violation_FTC` and `rpt.CalculateCrewFTC` (`R5:297-299,334-335`; `CalculateCrewFTC:197-199,217-218`): FTC credit of a deadheading cabin crew member (half of scheduled time on ground transport; block time on a non-ground carrier) and report offset.
- `rpt.Get_Detailed_Pairing:211,308`: outputs `crr.code` as `Carrier_Code` of each leg.

## 7. Typical query patterns
```sql
-- carriers that are ground transport, by kind
SELECT ID, LTRIM(RTRIM(CODE)) AS Code, LTRIM(RTRIM(NAME)) AS Name, GROUNDCATEGORY
FROM TSC.dbo.vvCarriers
WHERE CAT = 1
ORDER BY GROUNDCATEGORY, NAME;

-- carrier code of the legs of a pairing day (day number = days since 1980-01-01)
SELECT lm.FLT, lm.DEP, lm.ARR, LTRIM(RTRIM(c.CODE)) AS Carrier, c.CAT
FROM TSC.dbo.LEGMAIN lm
LEFT JOIN TSC.dbo.vvCarriers c ON c.ID = lm.CARRIER
WHERE lm.DAY = DATEDIFF(DAY,'1980-01-01','2026-11-05') AND lm.CANCELLED = 0;
```
(Do not select contact columns.)

## 8. Data profile (measured 2026-11-03)
- 346 carriers; `CAT = 0`: 187 (incl. 2 rail operators with GROUNDCATEGORY 4), `CAT = 1`: 159.
- Legs per carrier, LEGMAIN.DAY 17000-17100 = 2026-07-18..2026-10-26 (13,656 legs, every leg has a matching carrier row): `TSC` (ID 1) 8,754; `OWN` (9) 802; `AC` (13) 720; `NAT` (208) 573; `AF` (3) 329; `PD` (73) 291; `YULO` (433) 231; ID 138: 206; ID 486: 162; ID 434: 132.
- Crew legs (CREWLEG.CARRIER) 17000-17100 by (CAT,GROUNDCATEGORY): (0,0) 28,757; (1,3) 818; (1,2) 740; (1,0) 298; (1,1) 69; (1,4) 48.
- All time-offset columns `CK_*`/`CB_*` = 0 for every row.

## 9. Open questions / confidence
- High: `ID` <-> leg carrier join, `CAT = 1` = ground transport (used as such in code comments `/* GROUND TRANSPORT*/`).
- Medium: label mapping of `GROUNDCATEGORY` 1/2/3/4 to taxi / bus-limo / own-or-car / train (derived from the names of the members of each value, not from documentation).
- Unknown: `CARRIER_CAT`, `PRIMARYCARRIER`, `TRANSREQ`, `AUTOADJUSTTMS`, `COMB_GRND_TRANSP`, `ID50STATUS` precise semantics (naming only, not used).
