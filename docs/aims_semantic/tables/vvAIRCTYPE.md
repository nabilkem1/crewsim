# vvAIRCTYPE  (View)  - Aircraft-type master, fully decoded (122 columns)

## 1. Purpose & business meaning
`TSC.dbo.vvAIRCTYPE` is the AIMS "vv" (value-view) of the aircraft-type master: it exposes the table `AIRCTYPE` (35 rows) with its 511-byte record image
(`AIRCTYPE.DATA_BEGIN_END`) decoded into 122 attributes: seat configuration, cargo-hold geometry, performance and fuel-planning data, weights, crew complement /
crew-rest information, weather and runway minima, categories and flags. One row = one aircraft type (fleet type or sub-fleet variant, plus the placeholder `TRN` train).
Grain, lifecycle and ownership are identical to `AIRCTYPE`: static master data maintained by fleet / network planning; planner-assist only reads it.

Planner-assist only needs a handful of columns: the key triple (`ACTYPE`, `IATACODE`, `ACORDER`), `EXCL_FROM_MVT` (is the type used in operations at all) and
`ACORDER` as bit position. The other ~115 columns are fleet-planning / flight-planning data of the AIMS modules (Fleet, Flight planning/ETS, Cargo, Cabin complement,
Weather minima, Helicopter) which no planner-assist procedure touches; they are documented here by name inference and marked as such.

## 2. Physical facts
- `TSC.dbo.vvAIRCTYPE`, view (definition not available - encrypted/no permission). Row count measured 2026-11-03: **35**, identical to `AIRCTYPE`.
- View over `AIRCTYPE`; the key columns `ACTYPE`, `IATACODE`, `ACORDER` are the table's real columns (all unique), everything else is decoded from the binary image.
  Because the view hides the physical table, filters on non-key columns cannot use an index - irrelevant at 35 rows.
- All columns are nullable in the view metadata, but no nulls were observed in profiled columns.
- Type lengths: columns.json reports `nchar` length in bytes; the value below is characters; `varbinary(n)` length is in bytes.

## 3. Column dictionary

### 3.1 Identity and keys
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| ACTYPE | smallint | yes | Numeric aircraft-type id (FK target of `CREWQUAL.AC`, `LEGMAIN.AC`) | 1..35 | `dbo.R0_GetDraftList.sql:484`, `rpt.Get_Detailed_Pairing.sql:310`, `rpt.get_crew_certifications.sql:109` |
| IATACODE | nchar(4) | yes | Fleet-type code shown to users: 332, 333, 320, 321, 32Q, TRN, W7S8... (blank-padded) | trim before comparing | `rpt.Get_Detailed_Pairing.sql:214` (`AC_Type`), `dbo.R0_GetDraftList.sql:356` |
| ACORDER | tinyint | yes | Display order and **bit position (1-based) of the type in `EXPI.MULT_AC` certificate bitmap** | 1..35; 332=1, 333=2, 320=8, 321=17, 32Q=19, TRN=20 | `dbo.R0_GetDraftList.sql:358-360`, `rpt.get_crew_certifications.sql:48-52` |
| DESC_ | nchar(20) | yes | Free-text type description ("Airbus A330-200", "Boeing 737-800 Pax", "Train SNCF") | text | profiled |
| ICAOCODE | nchar(4) | yes | ICAO aircraft designator (A332, A333, A320, A21N, B738...) blank for L15/TRN/some legacy | 4-char ICAO type designator | profiled |
| ACTYPEIATA | nchar(4) | yes | IATA equipment code of the type (332, 333, 320, 321, 32Q, 73H, 7M8, 343...) | IATA 3-char code; blank for some legacy | profiled |
| ACTYPEOWNER | smallint | yes | Operator that owns/operates the type when it is not the home carrier: value equals a `vvCarriers.ID` (46 = WestJet types W7S8/W737/W736/W738/W7M8, 73 = Porter P295, 428/444 = Dash-8 types, 441 = rail operator for TRN); 0 = own fleet | carrier id or 0 | profiled (matches `vvCarriers.ID`/NAME); inference on semantic |
| AC_ADOPT_PBS | nchar(4) | yes | Aircraft code under which the type is "adopted" in the PBS (preferential bidding) system, i.e. fleet grouping: 332 and 333 -> `330`; 320/321/321C/321L/321N/32N/32Q -> `321`; 738 variants -> `738` | code string; blank = not in PBS | profiled; naming inference |
| AC_ADOPT_PAIRING | nchar(5) | yes | Aircraft code under which the type is adopted in the pairing/crew-planning system (`A332`, `A333`, `A32Q`, `A321`, `B738`...) | code string | profiled; naming inference |
| AC_RANK | tinyint | yes | Planner preference rank of the type (333=1, 332=2, 32Q=3, 321=4, 320=5 ...; unused types 6..35) | 1..35, lower = higher rank (inference) | profiled |
| ACGROUP | tinyint | yes | Aircraft group code | 0 for all rows | profiled; not used |
| ACCATEG | tinyint | yes | Aircraft category index (links to GENCAT category type of aircraft) | 0 for all rows | profiled; not used |
| ACCAT_CATEGBYT | varbinary(4) | yes | Aircraft-category bitmap (32 bits) | bitmask | naming inference; not used |

### 3.2 Operational status flags
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| EXCL_FROM_MVT | tinyint | yes | "Excluded from Movement": 1 = type is not used in flight operations (legacy, placeholder, partner or train); 0 = active type | **0 only for 332, 333, 320, 321, 32Q**; 1 for the other 30 rows (incl. TRN) | `rpt.Get_Detailed_Pairing.sql:310`, `rpt.Get_Custom_Rules_*.sql:229,295` (`a.EXCL_FROM_MVT = 0`); profiled |
| INACTIVEDATE | smallint | yes | Date after which the type is inactive (AIMS day number since 1980-01-01) | 0 = not set for 34 rows; -1 for 763 | profiled |
| IS_SUB_CHARTER | tinyint | yes | Type used for sub-chartered (wet-leased) flying | 0 for all rows | profiled; naming inference |
| ISHELICOPTER | tinyint | yes | Helicopter flag (AIMS also serves helicopter operators) | 0 for all rows | profiled; not used |

### 3.3 Seats and cabin
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| SEATS1 | smallint | yes | Passenger seats in cabin class 1 (premium/"Club") | 332/333 = 12, 32Q = 12, 321/320 = 0 | profiled (matches record-image header 0x0C) |
| SEATS2 | smallint | yes | Passenger seats, class 2 | 0 on all active types | profiled |
| SEATS3 | smallint | yes | Passenger seats, class 3 (economy) | 332 = 320, 333 = 320, 321 = 198, 320 = 180, 32Q = 187 | profiled |
| SEATS4 | smallint | yes | Passenger seats, class 4 | 0 | profiled |
| SEATCATEG_1 .. SEATCATEG_4 | tinyint x4 | yes | Seat-category index of cabin class 1..4 | 0 | naming inference; not used |
| SEAT11, SEAT12, SEAT21, SEAT22, SEAT31, SEAT32, SEAT41, SEAT42 | smallint x8 | yes | Sub-split of the seats of each class (n1/n2 = two seat blocks or min/max per class) | unknown - not used by any procedure | naming inference |
| CABINSEATS | smallint | yes | Cabin-crew jump seats (or total cabin seats) | 0 on active types | naming inference; not used |
| CREW_SEATS | smallint | yes | Flight-crew / crew seats available | 0 on all types | profiled; not used |
| CREW_BUNKS | smallint | yes | Number of crew-rest bunks on board (relevant to augmented-crew FDP extension) | 0 for all types in data | profiled; naming inference |
| RESTFACIL | tinyint | yes | Crew-rest facility class of the type | 332/333/320/32Q = 3, 321 = 4, some legacy 0 | profiled; semantics inferred |
| CABIN_SELECTION | tinyint | yes | Cabin selection mode for cabin-crew complement | unknown - not used | naming inference |

### 3.4 Cabin crew complement rules (reduce / increase by passenger load)
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| CK_REDUCECABIN | tinyint | yes | Checkbox: complement may be reduced when passengers are below a threshold | 0/1 | naming inference; not used |
| PASSANGBELOW | smallint | yes | Passenger count below which the cabin complement is reduced | pax count | naming inference; not used |
| COMPLEMENTREDUCE | tinyint | yes | Number of cabin crew removed on reduction | count | naming inference; not used |
| COMPLEMENTPOSIDX | tinyint | yes | Crew position index (see `vvPositions.ID`) that is reduced/increased | position id | naming inference; not used |
| CK_INCREASECABIN | tinyint | yes | Checkbox: complement is increased | 0/1 | naming inference; not used |
| CK_CONCERN_AC | tinyint | yes | Checkbox: rule concerns this aircraft | 0/1 | naming inference; not used |
| INCREASE_COMPL | smallint | yes | Pax count / amount at which the complement increases | unknown - not used | naming inference |
| OTHERCKB | tinyint | yes | Other checkbox | unknown - not used | naming inference |
| DEADHEADCB | tinyint | yes | Checkbox: deadheading crew counted in complement / seats | unknown - not used | naming inference |
| CREWLISTCB | tinyint | yes | Checkbox: crew list required/printed | unknown - not used | naming inference |
| CREWWEIGHT | int | yes | Standard crew weight for weight & balance | 0 | profiled; not used |

### 3.5 Performance, cost, revenue, fuel planning
| Column | Type | Null | Business meaning | Encoding / units | Evidence |
|---|---|---|---|---|---|
| MTOW | int | yes | Maximum take-off weight | kg (332 = 230000, 333 = 215000, 320 = 77000, 321/32Q = 83000) | profiled |
| MAXRANGE | float | yes | Maximum range | nautical miles (332 = 6000, 333 = 5000, 320 = 2500, 321 = 2350) | profiled; unit inferred |
| CRSPEED | float | yes | Cruise speed | knots (332/333 = 469, 320 = 454, 321/32Q = 447) | profiled; unit inferred |
| FIRSTCRSPEED | float | yes | Cruise speed of the first flight-planning leg / first speed profile | speed | naming inference |
| FIRSTFUEL | float | yes | Fuel for the first flight-planning leg / first profile | fuel unit per FIRSTFUELUNT | naming inference |
| FIRSTSPEEDUNT | tinyint | yes | Unit code of FIRSTCRSPEED | code | naming inference |
| FIRSTFUELUNT | tinyint | yes | Unit code of FIRSTFUEL | code | naming inference |
| HOURSSPEED | smallint | yes | Hours basis for the speed profile | unknown - not used | naming inference |
| HOURSFUEL | smallint | yes | Hours basis for the fuel profile | unknown - not used | naming inference |
| FUEL_BURN_RATE | float | yes | Fuel burn per hour | e.g. 332 = 5280, 333 = 5300, 320 = 2600, 321 = 2740 (kg/h inferred) | profiled |
| DISTSPEED | float | yes | Distance-speed parameter of the planning model | unknown - not used | naming inference |
| DISTFUEL | float | yes | Distance-fuel parameter of the planning model | unknown - not used | naming inference |
| RTEALTITUDE | int | yes | Standard route altitude | feet (inference) | naming inference |
| COSMICCLIMBING | smallint | yes | Climb time of the "Cosmic" flight-planning profile | minutes (inference) | naming inference |
| COSMICDESCEND | smallint | yes | Descent time of the "Cosmic" profile | minutes (inference) | naming inference |
| COSMICCLIMBRATE | int | yes | Climb rate of the "Cosmic" profile | ft/min (inference) | naming inference |
| COSMICDESCENDRATE | int | yes | Descent rate of the "Cosmic" profile | ft/min (inference) | naming inference |
| FUELTYPE | tinyint | yes | Fuel type code | 0 | profiled; not used |
| ETSFUELCLCMETHOD | tinyint | yes | Fuel calculation method for emissions-trading (ETS) reporting | code | naming inference |
| OPERATING_COST | float | yes | Operating cost per block hour | money | naming inference |
| DISR_OPERATING_COST | float | yes | Operating cost used in disruption (re-planning) cost evaluation | money | naming inference |
| CHARTREVENUE | float | yes | Charter revenue rate | money | naming inference |
| BLKREVENUE | float | yes | Revenue per block hour | money | naming inference |
| WGH_UNIT | tinyint | yes | Weight unit code of the weight columns (kg/lb) | code | naming inference |
| TURBULENCECATEGORY | nchar(1) | yes | Wake-turbulence category (H/M/L) | blank for all rows in data | profiled |
| FIRECAT | tinyint | yes | Airport rescue and fire-fighting (RFF) category the type requires | 332 = 8, 333 = 9, 320 = 6, 0 = not set | profiled; semantics inferred |
| SMSINITUNTIL | smallint | yes | "SMS initialised until": date until which an SMS/message flag is initialised | unknown - not used | naming inference |

### 3.6 Cargo and baggage holds
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| CARGO_CAP | int | yes | Total cargo capacity | weight unit per WGH_UNIT; 0 on active types | profiled |
| CARGOINFO_UPPER_LOWER_1_ULD | float | yes | Unit-load-device (ULD) count/type for upper-lower hold 1 | unknown - not used | naming inference |
| CARGOINFO_UPPER_LOWER_1_VOLUME | float | yes | Volume of hold 1 | m3 (inference) | naming inference |
| CARGOINFO_UPPE_LOWE_1_DENSIT | float | yes | Density of hold 1 | unknown | naming inference |
| CARGOINFO_UPPER_LOWER_1_TARE | float | yes | ULD tare weight, hold 1 | weight | naming inference |
| CARGOINFO_UPPE_LOWE_1_USETYP | tinyint | yes | Use type of hold 1 | code | naming inference |
| CARGOINFO_UPPER_LOWER_1_FUTURE | varbinary(21) | yes | Reserved bytes | unused | naming inference |
| CARGOINFO_UPPER_LOWER_2_ULD / _VOLUME / CARGOINFO_UPPE_LOWE_2_DENSIT / CARGOINFO_UPPER_LOWER_2_TARE / CARGOINFO_UPPE_LOWE_2_USETYP / CARGOINFO_UPPER_LOWER_2_FUTURE | float, float, float, float, tinyint, varbinary(21) | yes | Same six attributes for hold 2 | as hold 1 | naming inference |
| CARGOINFO_BULKVOLUME | float | yes | Bulk-hold volume | m3 (inference) | naming inference |
| CARGOINFO_BULKDENSITY | float | yes | Bulk-hold density | unknown | naming inference |
| CARGOINFO_FUTURE | varbinary(20) | yes | Reserved bytes | unused | naming inference |
| AVRGPAXLUGWEIGHT | smallint | yes | Average passenger luggage weight | weight | naming inference |
| AVRGPAXLDFACT | smallint | yes | Average passenger load factor (percent) | percent | naming inference |
| AVRGCARGOLDFACT | smallint | yes | Average cargo load factor (percent) | percent | naming inference |

### 3.7 Weather and airfield minima
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| WEATHER_CEILING_1, WEATHER_CEILING_2 | smallint x2 | yes | Cloud-ceiling minima, two limit profiles (e.g. take-off / landing or limit 1/2) | feet | naming inference; not used |
| WEATHER_RVR_1, WEATHER_RVR_2 | smallint x2 | yes | Runway visual range minima | metres | naming inference; not used |
| WEATHER_VISIBILITY_1, WEATHER_VISIBILITY_2 | smallint x2 | yes | Visibility minima | metres | naming inference; not used |
| WEATHER_CROSSWIND_1, WEATHER_CROSSWIND_2 | smallint x2 | yes | Crosswind limits | knots | naming inference; not used |
| WEATHER_WIND_1, WEATHER_WIND_2 | smallint x2 | yes | Wind limits | knots | naming inference; not used |
| WEATHER_TAKEOFFMIN | smallint | yes | Take-off minima | unknown | naming inference; not used |
| ILS | tinyint | yes | ILS category requirement | code | naming inference; not used |
| MINRWYLEN | smallint | yes | Minimum runway length | metres/feet | naming inference; not used |
| MINRWYWID | tinyint | yes | Minimum runway width | unknown | naming inference; not used |
| LVOEXP_1 .. LVOEXP_5 | smallint x5 | yes | Low-visibility-operations experience requirement thresholds (crew) | unknown | naming inference; not used |

### 3.8 Helicopter / other (inherited from the generic AIMS fleet record)
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| CHC_DESC | nchar(6) | yes | Helicopter-operator (CHC) description | text | naming inference; not used |
| DEFEON | tinyint | yes | "Default ... on" setting | unknown - not used by any procedure | naming inference |
| DEFEOFF | tinyint | yes | "Default ... off" setting | unknown - not used by any procedure | naming inference |
| DEFEGAP | smallint | yes | Gap between DEFEON/DEFEOFF | unknown - not used by any procedure | naming inference |
| ROTORSON | smallint | yes | Rotors-on time (helicopter) | minutes | naming inference; not used |
| ROTORSOFF | smallint | yes | Rotors-off time (helicopter) | minutes | naming inference; not used |
| DVALUE | smallint | yes | D-value (aircraft size / helideck) | unknown - not used | naming inference |
| FUTURE2 | varbinary(37) | yes | Reserved bytes | unused | naming inference |

## 4. Keys & relationships
- Primary natural key: `ACTYPE` (also unique: `IATACODE`, `ACORDER`).
- `vvAIRCTYPE.ACTYPE = CREWQUAL.AC` (1:N): `LEFT JOIN TSC.dbo.vvAIRCTYPE a ON a.ACTYPE = cp.AC` (`dbo.R0_GetDraftList.sql:484`); `inner join TSC.dbo.vvAIRCTYPE act on act.ACTYPE = cq.AC` (`rpt.get_crew_certifications.sql:109`).
- `vvAIRCTYPE.ACTYPE = LEGMAIN.AC` (1:N): `ac.ACTYPE = CONVERT(TINYINT, FinalBase.Ac) AND ac.EXCL_FROM_MVT = 0` (`rpt.Get_Detailed_Pairing.sql:310`).
- `vvAIRCTYPE.ACTYPE` = each byte of `SPEFREC3.AIRTYP` / `AIRTYP2` (aircraft slots of a custom rule): `ACTYPE = CONVERT(tinyint, substring(AIRTYP, idx, 1))` (`rpt.Get_Custom_Rules_CertainFlightsCrew.sql:228-232`).
- `vvAIRCTYPE.ACORDER` = bit index in `EXPI.MULT_AC` (certificate applies to aircraft): `CONVERT(tinyint, SUBSTRING(CONVERT(binary(12), E.MULT_AC), (A.ACORDER - 1)/8 + 1, 1)) & POWER(2,(A.ACORDER - 1)%8) > 0` (`dbo.R0_GetDraftList.sql:357-361`).
- `vvAIRCTYPE.ACTYPEOWNER = vvCarriers.ID` (operator owning a partner-fleet type) - inferred from values.

## 5. Encoding conventions & gotchas
- **Three ids**: `ACTYPE` (data FK), `ACORDER` (bitmap bit position, 1-based), `IATACODE` (user text). `ACORDER <> ACTYPE` (332: ACTYPE 4, ACORDER 1).
- `EXCL_FROM_MVT = 0` identifies the five types actually flown (332, 333, 320, 321, 32Q); rpt.Get_Detailed_Pairing and the custom-rule reports return a NULL/blank aircraft type for any other type because of this filter. `32Q` (A321neo) and `321` share the PBS adopt code `321` (`AC_ADOPT_PBS`).
- Certificate-expiry logic in R0 only covers ACORDER {1,2,8,17,19,20} = 332, 333, 320, 321, 32Q, TRN; a candidate on any other type triggers `EXPIRY_CHECK_NOT_CONFIGURED`.
- Date columns in the view (`INACTIVEDATE`) follow the AIMS day-number convention (days since 1980-01-01); `-1`/`0` mean "not set".
- `nchar` columns are blank padded; trim before comparing.
- The view carries many reserved `FUTURE*` byte columns: ignore.
- `SEATS1..4` are per-class seat counts: sum is not stored. For the active types total = SEATS1 + SEATS3 (e.g. A330-300 = 12 + 320).

## 6. How the planner-assist procedures use it
- `dbo.R0_GetDraftList` (`:356-363`, `:484-487`): builds the aircraft list per certificate (`#CertRules.Aircraft_List`) by decoding `EXPI.MULT_AC` with `ACORDER`; and verifies that every aircraft type present in the candidate pool is one of the six certificate-checked orders, otherwise raises `EXPIRY_CHECK_NOT_CONFIGURED` (R0-1).
- `rpt.get_crew_certifications`: same decode of `EXPI.MULT_AC` limited to `ACORDER IN (1,2,8,17,19,20)` to list the aircraft each certificate applies to (`:44-55`) and joins `act.ACTYPE = cq.AC` for the crew's qualification (`:109`).
- `rpt.Get_Custom_Rules_CertainFlightsCrew` / `_Schedule_WithWithNot`: translate the `AIRTYP`/`AIRTYP2` slots of a custom rule to `IATACODE` for display (`EXCL_FROM_MVT = 0` on the first slot list).
- `rpt.Get_Detailed_Pairing`: `AC_Type` = `vvAIRCTYPE.IATACODE` of the leg's aircraft (`LEGMAIN.AC`), only for types with `EXCL_FROM_MVT = 0`.
- No rule/regulation check uses the numeric attributes (seats, MTOW, etc.).

## 7. Typical query patterns
```sql
-- active fleet types and their bitmap position
SELECT ACTYPE, LTRIM(RTRIM(IATACODE)) AS Type_Code, LTRIM(RTRIM(DESC_)) AS Description, ACORDER
FROM TSC.dbo.vvAIRCTYPE
WHERE EXCL_FROM_MVT = 0
ORDER BY ACORDER;

-- aircraft type of the legs of one day (day number = days since 1980-01-01)
SELECT lm.DEP, lm.ARR, lm.FLT, LTRIM(RTRIM(a.IATACODE)) AS Aircraft
FROM TSC.dbo.LEGMAIN lm
LEFT JOIN TSC.dbo.vvAIRCTYPE a ON a.ACTYPE = lm.AC
WHERE lm.DAY = DATEDIFF(DAY,'1980-01-01','2026-11-05') AND lm.CANCELLED = 0;

-- seat configuration of the active types
SELECT LTRIM(RTRIM(IATACODE)) AS Type_Code, SEATS1 AS Seats_Class1, SEATS3 AS Seats_Class3, MTOW
FROM TSC.dbo.vvAIRCTYPE WHERE EXCL_FROM_MVT = 0;
```

## 8. Data profile (measured 2026-11-03)
- 35 rows; `EXCL_FROM_MVT = 0` for 5 (332, 333, 320, 321, 32Q), `= 1` for 30.
- Seats (class1/class3): 332 12/320; 333 12/320; 320 0/180; 321 0/198; 32Q 12/187. MTOW 230000 / 215000 / 77000 / 83000 / 83000.
- `ACTYPEOWNER` non-zero on W7S8, W737, W736, W738, W7M8 (46), TRN (441), WDH4 (428), PDH4 (444), P295 (73).
- `CREW_SEATS`, `CREW_BUNKS`, `ACGROUP`, `ACCATEG`, `ISHELICOPTER`, `IS_SUB_CHARTER`, `FUELTYPE` are 0 for every row; `INACTIVEDATE = -1` only for `763`.

## 9. Open questions / confidence
- High confidence: key columns, `EXCL_FROM_MVT` semantics, `ACORDER` bit position, seat counts, `ACTYPEOWNER` = carrier id.
- Everything in sections 3.4-3.8 is name inference and none of it is used by any planner-assist procedure; units (nm, kt, kg/h) inferred from magnitudes.
- Meaning of `AC_RANK`, `RESTFACIL` (class 3 vs 4), `DEFEON/DEFEOFF/DEFEGAP`, `SMSINITUNTIL`, `DVALUE` unverified.
- The view definition is unavailable; the decode is assumed to be the AIMS record layout (verified only for the first three smallint attributes).
