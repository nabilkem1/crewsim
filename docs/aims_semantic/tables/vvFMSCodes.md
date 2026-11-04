# vvFMSCodes  (View)  - Flight-movement ("FMS") code tables: flight service types, leg statuses, regions, aircraft duties (one-row decode of TABLES record FMSCODES)

## 1. Purpose & business meaning
`vvFMSCodes` is a **single-row configuration view**: it unpacks the AIMS setup record `TABLES.RECDESC = 'FMSCODES'` (a 3,915-byte packed `FIELDS` blob, see TABLES.md) into 310 typed columns. It holds the code lists that the AIMS flight-management ("FMS") module uses for flights:

* **flight service types** (26 slots): Charter, Scheduled service, VIP, Ferry, Training, Test flight, ... - the value stored in `LEGMAIN.FLTYPE` is the **1-based slot number** into this list; each type also has a *revenue* flag;
* **leg statuses** (20 slots): Cancelled, Re-schedule, Diverted, Re-routed, Return to ramp, Return from airborne - `LEGMAIN.LEGSTATUS` is the slot number;
* **aircraft duties** (6 slots, `XACDUTY_n`): what an aircraft is used for (only `PS` Passenger is defined here; the 4-entry list actually used by `LEGMAIN.ACDUTY` is the separate `TABLES.FMACDUTY` record, same layout);
* **operating regions** (24 slots): SA, ME, FE, PC, IE, TA, AF, NA;
* ~60 scalar settings of the FMS module (re-route flags, tolerances, shift times, default passenger/baggage weights, colours, reserved bytes) - none is used by planner-assist.

The view is a *lookup*, not a fact table: there is exactly one row and every use is `CROSS APPLY (VALUES ...)` or `SELECT TOP 1 FLTYPE_n_DESC FROM vvFMSCodes`. Maintained by the AIMS administrator in the "FMS codes" setup screen.
Readers in this repo: `rpt.Get_Detailed_Pairing` (CTE `flight_service_type`: turns `LEGMAIN.FLTYPE` into the text `Service_Type`), `rpt.Get_Custom_Rules_CertainFlightsCrew` and `rpt.Get_Custom_Rules_Schedule_WithWithNot` (names the bits of `SPEFRECDATA.FLTTYP` for rule kind 8 "Flights with the following flight types").

## 2. Physical facts
* `TSC.dbo.vvFMSCodes`, **view**, 310 columns. The view definition is not available (encrypted/no permission); structure below is reconstructed (see layout).
* **1 row** at extraction (live `SELECT COUNT(*)`, 2026-11-03). Underlying: `TSC.dbo.TABLES` row `RECDESC = 'FMSCODES'` (unique index `TABLES_INDEX_0`), `FIELDS` = 3,915 bytes. No indexes of its own; no date/validity columns.
* (The metadata extract `columns.json` reports `nchar` lengths in **bytes**; real declared character lengths are half: `RECDESC nchar(10)`, codes `nchar(2)`, descriptions `nchar(20)`, region codes `nchar(3)`, `DRMMESSAGESPATH nchar(30)`. The widths below are the real ones.)
* **Payload layout of `FIELDS` (1-based byte offsets, text = UCS-2 = 2 bytes/char)**, reconstructed from the column order and **proved by the byte sum 6x44 + 26x46 + 20x44 + 24x48 + 423 = 3,915** and spot reads (XACDUTY_1 at byte 1 = "PS"; FLTYPE_1 at 265 = "C"/"CHARTER"/revenue byte 1; STATUS_1 at 1461 = "CA"; REGION_1 at 2341 = "SA"; FLTOLER at 3493 = 32; RRFLAGS at 3494 = 138):
  * `XACDUTY_i` i=1..6: offset 1+(i-1)*44 - code 4 B, description 40 B;
  * `FLTYPE_i` i=1..26: offset 265+(i-1)*46 - code 4 B, description 40 B, REVENUE 1 B, FUT 1 B;
  * `STATUS_i` i=1..20: offset 1461+(i-1)*44 - code 4 B, description 40 B;
  * `REGION_i` i=1..24: offset 2341+(i-1)*48 - code 6 B, description 40 B, REGIONBAG 1 B, NO_DBC 1 B;
  * scalar block from byte 3493 (in column order, offsets listed in the dictionary).

## 3. Column dictionary
All columns are nullable (view over a blob). "Evidence" = where a procedure reads it, otherwise "naming inference" / "profiled".

### 3.0 Key
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| RECDESC | nchar(10) | Y | Name of the underlying TABLES record. | Always `FMSCODES` (the only row). | profiled |

### 3.1 Aircraft-duty codes (6 slots)
| Column(s) | Type | Null | Business meaning | Value (slot content today) | Evidence |
|---|---|---|---|---|---|
| `XACDUTY_1_CODE`, `XACDUTY_1_DESC` | nchar(2), nchar(20) | Y | Aircraft-duty slot 1 (code, description). | `PS` = PASSENGER | bytes 1-44 of FIELDS; naming; LEGMAIN.md (ACDUTY) |
| `XACDUTY_2_CODE`, `XACDUTY_2_DESC` | nchar(2), nchar(20) | Y | Aircraft-duty slot 2 (code, description). | blank (unused slot) | bytes 45-88 of FIELDS; naming; LEGMAIN.md (ACDUTY) |
| `XACDUTY_3_CODE`, `XACDUTY_3_DESC` | nchar(2), nchar(20) | Y | Aircraft-duty slot 3 (code, description). | blank (unused slot) | bytes 89-132 of FIELDS; naming; LEGMAIN.md (ACDUTY) |
| `XACDUTY_4_CODE`, `XACDUTY_4_DESC` | nchar(2), nchar(20) | Y | Aircraft-duty slot 4 (code, description). | blank (unused slot) | bytes 133-176 of FIELDS; naming; LEGMAIN.md (ACDUTY) |
| `XACDUTY_5_CODE`, `XACDUTY_5_DESC` | nchar(2), nchar(20) | Y | Aircraft-duty slot 5 (code, description). | blank (unused slot) | bytes 177-220 of FIELDS; naming; LEGMAIN.md (ACDUTY) |
| `XACDUTY_6_CODE`, `XACDUTY_6_DESC` | nchar(2), nchar(20) | Y | Aircraft-duty slot 6 (code, description). | blank (unused slot) | bytes 221-264 of FIELDS; naming; LEGMAIN.md (ACDUTY) |

### 3.2 Flight service types (26 slots) - `LEGMAIN.FLTYPE` -> description
Slot number i is the stored value of `LEGMAIN.FLTYPE` (1..26; 0/NULL = none, no match). `Service_Type` in `rpt.Get_Detailed_Pairing` is `FLTYPE_i_DESC`; SEL 8 rules compare this exact description text. `REVENUE` = 1 marks revenue-generating types; `FUT` = reserved (all 0).
| Column(s) | Type | Null | Business meaning | Value (slot content today) | Evidence |
|---|---|---|---|---|---|
| `FLTYPE_1_CODE`, `FLTYPE_1_DESC`, `FLTYPE_1_REVENUE`, `FLTYPE_1_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 1 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | `C` = CHARTER; REVENUE=1; FUT=0 | bytes 265-310; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_2_CODE`, `FLTYPE_2_DESC`, `FLTYPE_2_REVENUE`, `FLTYPE_2_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 2 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | `J` = SCHEDULED SERVICE; REVENUE=1; FUT=0 | bytes 311-356; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_3_CODE`, `FLTYPE_3_DESC`, `FLTYPE_3_REVENUE`, `FLTYPE_3_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 3 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | `E` = VIP FLIGHT; REVENUE=1; FUT=0 | bytes 357-402; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_4_CODE`, `FLTYPE_4_DESC`, `FLTYPE_4_REVENUE`, `FLTYPE_4_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 4 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | `P` = FERRY; REVENUE=0; FUT=0 | bytes 403-448; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_5_CODE`, `FLTYPE_5_DESC`, `FLTYPE_5_REVENUE`, `FLTYPE_5_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 5 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | `K` = TRAINING; REVENUE=0; FUT=0 | bytes 449-494; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_6_CODE`, `FLTYPE_6_DESC`, `FLTYPE_6_REVENUE`, `FLTYPE_6_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 6 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | `T` = TEST FLIGHT; REVENUE=0; FUT=0 | bytes 495-540; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_7_CODE`, `FLTYPE_7_DESC`, `FLTYPE_7_REVENUE`, `FLTYPE_7_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 7 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | `G` = ADDITIONAL FLIGHTS; REVENUE=1; FUT=0 | bytes 541-586; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_8_CODE`, `FLTYPE_8_DESC`, `FLTYPE_8_REVENUE`, `FLTYPE_8_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 8 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | `Z` = OTHER AIRLINES; REVENUE=0; FUT=0 | bytes 587-632; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_9_CODE`, `FLTYPE_9_DESC`, `FLTYPE_9_REVENUE`, `FLTYPE_9_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 9 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | `U` = SURFACE VEHICULE; REVENUE=1; FUT=0 | bytes 633-678; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_10_CODE`, `FLTYPE_10_DESC`, `FLTYPE_10_REVENUE`, `FLTYPE_10_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 10 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | `O` = SPECIAL CHARTER; REVENUE=1; FUT=0 | bytes 679-724; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_11_CODE`, `FLTYPE_11_DESC`, `FLTYPE_11_REVENUE`, `FLTYPE_11_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 11 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | `X` = TECH STOP; REVENUE=0; FUT=0 | bytes 725-770; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_12_CODE`, `FLTYPE_12_DESC`, `FLTYPE_12_REVENUE`, `FLTYPE_12_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 12 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | `H` = CHARTER CARGO; REVENUE=1; FUT=0 | bytes 771-816; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_13_CODE`, `FLTYPE_13_DESC`, `FLTYPE_13_REVENUE`, `FLTYPE_13_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 13 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | `F` = SCHEDULED CARGO; REVENUE=1; FUT=0 | bytes 817-862; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_14_CODE`, `FLTYPE_14_DESC`, `FLTYPE_14_REVENUE`, `FLTYPE_14_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 14 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | blank (unused slot); REVENUE=0; FUT=0 | bytes 863-908; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_15_CODE`, `FLTYPE_15_DESC`, `FLTYPE_15_REVENUE`, `FLTYPE_15_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 15 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | blank (unused slot); REVENUE=0; FUT=0 | bytes 909-954; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_16_CODE`, `FLTYPE_16_DESC`, `FLTYPE_16_REVENUE`, `FLTYPE_16_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 16 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | blank (unused slot); REVENUE=0; FUT=0 | bytes 955-1000; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_17_CODE`, `FLTYPE_17_DESC`, `FLTYPE_17_REVENUE`, `FLTYPE_17_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 17 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | blank (unused slot); REVENUE=0; FUT=0 | bytes 1001-1046; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_18_CODE`, `FLTYPE_18_DESC`, `FLTYPE_18_REVENUE`, `FLTYPE_18_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 18 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | blank (unused slot); REVENUE=0; FUT=0 | bytes 1047-1092; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_19_CODE`, `FLTYPE_19_DESC`, `FLTYPE_19_REVENUE`, `FLTYPE_19_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 19 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | blank (unused slot); REVENUE=0; FUT=0 | bytes 1093-1138; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_20_CODE`, `FLTYPE_20_DESC`, `FLTYPE_20_REVENUE`, `FLTYPE_20_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 20 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | blank (unused slot); REVENUE=0; FUT=0 | bytes 1139-1184; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_21_CODE`, `FLTYPE_21_DESC`, `FLTYPE_21_REVENUE`, `FLTYPE_21_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 21 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | blank (unused slot); REVENUE=0; FUT=0 | bytes 1185-1230; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_22_CODE`, `FLTYPE_22_DESC`, `FLTYPE_22_REVENUE`, `FLTYPE_22_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 22 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | blank (unused slot); REVENUE=0; FUT=0 | bytes 1231-1276; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_23_CODE`, `FLTYPE_23_DESC`, `FLTYPE_23_REVENUE`, `FLTYPE_23_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 23 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | blank (unused slot); REVENUE=0; FUT=0 | bytes 1277-1322; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_24_CODE`, `FLTYPE_24_DESC`, `FLTYPE_24_REVENUE`, `FLTYPE_24_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 24 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | blank (unused slot); REVENUE=0; FUT=0 | bytes 1323-1368; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_25_CODE`, `FLTYPE_25_DESC`, `FLTYPE_25_REVENUE`, `FLTYPE_25_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 25 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | blank (unused slot); REVENUE=0; FUT=0 | bytes 1369-1414; rpt.Get_Detailed_Pairing.sql:135-146 |
| `FLTYPE_26_CODE`, `FLTYPE_26_DESC`, `FLTYPE_26_REVENUE`, `FLTYPE_26_FUT` | nchar(2), nchar(20), tinyint, tinyint | Y | Flight service type = value 26 of `LEGMAIN.FLTYPE` (code, description, revenue flag, reserved). | blank (unused slot); REVENUE=0; FUT=0 | bytes 1415-1460; rpt.Get_Detailed_Pairing.sql:135-146 |

### 3.3 Leg status codes (20 slots) - `LEGMAIN.LEGSTATUS` -> description
| Column(s) | Type | Null | Business meaning | Value (slot content today) | Evidence |
|---|---|---|---|---|---|
| `STATUS_1_CODE`, `STATUS_1_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 1 of `LEGMAIN.LEGSTATUS`. | `CA` = CANCELLED | bytes 1461-1504; LEGMAIN.md |
| `STATUS_2_CODE`, `STATUS_2_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 2 of `LEGMAIN.LEGSTATUS`. | `RS` = RE-SCHEDULE | bytes 1505-1548; LEGMAIN.md |
| `STATUS_3_CODE`, `STATUS_3_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 3 of `LEGMAIN.LEGSTATUS`. | `DV` = DIVERTED | bytes 1549-1592; LEGMAIN.md |
| `STATUS_4_CODE`, `STATUS_4_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 4 of `LEGMAIN.LEGSTATUS`. | `RR` = RE-ROUTED | bytes 1593-1636; LEGMAIN.md |
| `STATUS_5_CODE`, `STATUS_5_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 5 of `LEGMAIN.LEGSTATUS`. | `QG` = Rtn to ramp | bytes 1637-1680; LEGMAIN.md |
| `STATUS_6_CODE`, `STATUS_6_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 6 of `LEGMAIN.LEGSTATUS`. | `QF` = Rtn fm airborn | bytes 1681-1724; LEGMAIN.md |
| `STATUS_7_CODE`, `STATUS_7_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 7 of `LEGMAIN.LEGSTATUS`. | blank (unused slot) | bytes 1725-1768; LEGMAIN.md |
| `STATUS_8_CODE`, `STATUS_8_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 8 of `LEGMAIN.LEGSTATUS`. | blank (unused slot) | bytes 1769-1812; LEGMAIN.md |
| `STATUS_9_CODE`, `STATUS_9_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 9 of `LEGMAIN.LEGSTATUS`. | blank (unused slot) | bytes 1813-1856; LEGMAIN.md |
| `STATUS_10_CODE`, `STATUS_10_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 10 of `LEGMAIN.LEGSTATUS`. | blank (unused slot) | bytes 1857-1900; LEGMAIN.md |
| `STATUS_11_CODE`, `STATUS_11_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 11 of `LEGMAIN.LEGSTATUS`. | blank (unused slot) | bytes 1901-1944; LEGMAIN.md |
| `STATUS_12_CODE`, `STATUS_12_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 12 of `LEGMAIN.LEGSTATUS`. | blank (unused slot) | bytes 1945-1988; LEGMAIN.md |
| `STATUS_13_CODE`, `STATUS_13_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 13 of `LEGMAIN.LEGSTATUS`. | blank (unused slot) | bytes 1989-2032; LEGMAIN.md |
| `STATUS_14_CODE`, `STATUS_14_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 14 of `LEGMAIN.LEGSTATUS`. | blank (unused slot) | bytes 2033-2076; LEGMAIN.md |
| `STATUS_15_CODE`, `STATUS_15_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 15 of `LEGMAIN.LEGSTATUS`. | blank (unused slot) | bytes 2077-2120; LEGMAIN.md |
| `STATUS_16_CODE`, `STATUS_16_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 16 of `LEGMAIN.LEGSTATUS`. | blank (unused slot) | bytes 2121-2164; LEGMAIN.md |
| `STATUS_17_CODE`, `STATUS_17_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 17 of `LEGMAIN.LEGSTATUS`. | blank (unused slot) | bytes 2165-2208; LEGMAIN.md |
| `STATUS_18_CODE`, `STATUS_18_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 18 of `LEGMAIN.LEGSTATUS`. | blank (unused slot) | bytes 2209-2252; LEGMAIN.md |
| `STATUS_19_CODE`, `STATUS_19_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 19 of `LEGMAIN.LEGSTATUS`. | blank (unused slot) | bytes 2253-2296; LEGMAIN.md |
| `STATUS_20_CODE`, `STATUS_20_DESC` | nchar(2), nchar(20) | Y | Special leg status = value 20 of `LEGMAIN.LEGSTATUS`. | blank (unused slot) | bytes 2297-2340; LEGMAIN.md |

### 3.4 Operating regions (24 slots)
| Column(s) | Type | Null | Business meaning | Value (slot content today) | Evidence |
|---|---|---|---|---|---|
| `REGION_1_CODE`, `REGION_1_DESC`, `REGION_1_REGIONBAG`, `REGION_1_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 1 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | `SA` = SOUTH AMERICA; REGIONBAG=0; NO_DBC=0 | bytes 2341-2388; naming; not used by any procedure |
| `REGION_2_CODE`, `REGION_2_DESC`, `REGION_2_REGIONBAG`, `REGION_2_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 2 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | `ME` = MIDDLE EAST; REGIONBAG=0; NO_DBC=0 | bytes 2389-2436; naming; not used by any procedure |
| `REGION_3_CODE`, `REGION_3_DESC`, `REGION_3_REGIONBAG`, `REGION_3_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 3 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | `FE` = FAR EAST; REGIONBAG=0; NO_DBC=0 | bytes 2437-2484; naming; not used by any procedure |
| `REGION_4_CODE`, `REGION_4_DESC`, `REGION_4_REGIONBAG`, `REGION_4_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 4 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | `PC` = PACIFIC; REGIONBAG=0; NO_DBC=0 | bytes 2485-2532; naming; not used by any procedure |
| `REGION_5_CODE`, `REGION_5_DESC`, `REGION_5_REGIONBAG`, `REGION_5_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 5 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | `IE` = EUROPE; REGIONBAG=0; NO_DBC=0 | bytes 2533-2580; naming; not used by any procedure |
| `REGION_6_CODE`, `REGION_6_DESC`, `REGION_6_REGIONBAG`, `REGION_6_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 6 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | `TA` = ATLANTIC; REGIONBAG=0; NO_DBC=0 | bytes 2581-2628; naming; not used by any procedure |
| `REGION_7_CODE`, `REGION_7_DESC`, `REGION_7_REGIONBAG`, `REGION_7_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 7 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | `AF` = AFRICA; REGIONBAG=0; NO_DBC=0 | bytes 2629-2676; naming; not used by any procedure |
| `REGION_8_CODE`, `REGION_8_DESC`, `REGION_8_REGIONBAG`, `REGION_8_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 8 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | `NA` = NORTH AMERICA; REGIONBAG=0; NO_DBC=0 | bytes 2677-2724; naming; not used by any procedure |
| `REGION_9_CODE`, `REGION_9_DESC`, `REGION_9_REGIONBAG`, `REGION_9_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 9 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | blank (unused slot); flags 0 | bytes 2725-2772; naming; not used by any procedure |
| `REGION_10_CODE`, `REGION_10_DESC`, `REGION_10_REGIONBAG`, `REGION_10_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 10 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | blank (unused slot); flags 0 | bytes 2773-2820; naming; not used by any procedure |
| `REGION_11_CODE`, `REGION_11_DESC`, `REGION_11_REGIONBAG`, `REGION_11_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 11 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | blank (unused slot); flags 0 | bytes 2821-2868; naming; not used by any procedure |
| `REGION_12_CODE`, `REGION_12_DESC`, `REGION_12_REGIONBAG`, `REGION_12_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 12 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | blank (unused slot); flags 0 | bytes 2869-2916; naming; not used by any procedure |
| `REGION_13_CODE`, `REGION_13_DESC`, `REGION_13_REGIONBAG`, `REGION_13_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 13 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | blank (unused slot); flags 0 | bytes 2917-2964; naming; not used by any procedure |
| `REGION_14_CODE`, `REGION_14_DESC`, `REGION_14_REGIONBAG`, `REGION_14_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 14 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | blank (unused slot); flags 0 | bytes 2965-3012; naming; not used by any procedure |
| `REGION_15_CODE`, `REGION_15_DESC`, `REGION_15_REGIONBAG`, `REGION_15_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 15 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | blank (unused slot); flags 0 | bytes 3013-3060; naming; not used by any procedure |
| `REGION_16_CODE`, `REGION_16_DESC`, `REGION_16_REGIONBAG`, `REGION_16_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 16 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | blank (unused slot); flags 0 | bytes 3061-3108; naming; not used by any procedure |
| `REGION_17_CODE`, `REGION_17_DESC`, `REGION_17_REGIONBAG`, `REGION_17_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 17 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | blank (unused slot); flags 0 | bytes 3109-3156; naming; not used by any procedure |
| `REGION_18_CODE`, `REGION_18_DESC`, `REGION_18_REGIONBAG`, `REGION_18_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 18 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | blank (unused slot); flags 0 | bytes 3157-3204; naming; not used by any procedure |
| `REGION_19_CODE`, `REGION_19_DESC`, `REGION_19_REGIONBAG`, `REGION_19_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 19 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | blank (unused slot); flags 0 | bytes 3205-3252; naming; not used by any procedure |
| `REGION_20_CODE`, `REGION_20_DESC`, `REGION_20_REGIONBAG`, `REGION_20_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 20 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | blank (unused slot); flags 0 | bytes 3253-3300; naming; not used by any procedure |
| `REGION_21_CODE`, `REGION_21_DESC`, `REGION_21_REGIONBAG`, `REGION_21_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 21 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | blank (unused slot); flags 0 | bytes 3301-3348; naming; not used by any procedure |
| `REGION_22_CODE`, `REGION_22_DESC`, `REGION_22_REGIONBAG`, `REGION_22_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 22 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | blank (unused slot); flags 0 | bytes 3349-3396; naming; not used by any procedure |
| `REGION_23_CODE`, `REGION_23_DESC`, `REGION_23_REGIONBAG`, `REGION_23_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 23 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | blank (unused slot); flags 0 | bytes 3397-3444; naming; not used by any procedure |
| `REGION_24_CODE`, `REGION_24_DESC`, `REGION_24_REGIONBAG`, `REGION_24_NO_DBC` | nchar(3), nchar(20), tinyint, tinyint | Y | Operating region slot 24 (code, description, 'region bag' flag, 'no DBC' flag - flags unexplained). | blank (unused slot); flags 0 | bytes 3445-3492; naming; not used by any procedure |

### 3.5 Scalar settings (byte offsets from 3493; values measured 2026-11-03)
None of these is read by any planner-assist procedure ("unknown - not used by any procedure"); the guessed meaning is from the column name only.
| Column | Type | Null | Business meaning (naming inference) | Value today | Offset (bytes) |
|---|---|---|---|---|---|
| FLTOLER | tinyint | Y | Flight-time/schedule tolerance setting. | 32 | 3493 |
| RRFLAGS | tinyint | Y | Bit flags of re-route / re-schedule handling. | 138 | 3494 |
| AVERAGEWEIGHTOLD | tinyint | Y | Legacy 1-byte default passenger weight. | 0 | 3495 |
| AVERAGEBAGGAGEOLD | tinyint | Y | Legacy 1-byte default baggage weight. | 0 | 3496 |
| RRFLAGS2 | smallint | Y | Second flag word for re-routing. | 0 | 3497-3498 |
| RESCHE_STATUS | tinyint | Y | Status code applied on re-scheduling. | 0 | 3499 |
| FUTBYTE | tinyint | Y | Reserved ("future") byte. | 0 | 3500 |
| USER_ | smallint | Y | Id of the AIMS user who last saved the record (an internal numeric id; not a name). | numeric | 3501-3502 |
| LSTUPDDT | smallint | Y | Last-update date (AIMS day number). | 0 | 3503-3504 |
| LSTUPDTM | smallint | Y | Last-update time (minutes). | 0 | 3505-3506 |
| USEDELAYREMARKS | tinyint | Y | Flag: use delay remarks. | 1 | 3507 |
| DLYREMARKCATEG | smallint | Y | Category number used for delay remarks. | 19 | 3508-3509 |
| DO_NOT_OVERRIDE_CCCODES | tinyint | Y | Flag: do not override change/cancel codes. | 0 | 3510 |
| OLDCCODESLLIST | varbinary(38) | Y | Legacy list of change codes (binary). | all zero | 3511-3548 |
| ISSUE_CHARTERER_WARN | tinyint | Y | Flag: warn about charterer. | 0 | 3549 |
| FORCE_CHARTERER_UPD | tinyint | Y | Flag: force charterer update. | 0 | 3550 |
| CHANGE_REASON_CONVERT | tinyint | Y | Flag: convert change reason. | 0 | 3551 |
| IGNORE_OFFERED_SEATS | tinyint | Y | Flag: ignore offered seats. | 0 | 3552 |
| FLDIDX | smallint | Y | Field index setting. | -1 | 3553-3554 |
| PRTY_CLRS_1, PRTY_CLRS_2, PRTY_CLRS_3, PRTY_CLRS_4, PRTY_CLRS_5, PRTY_CLRS_6 | tinyint x6 | Y | Priority colours (6 levels). | 0,0,0,0,0,0 | 3555-3560 |
| CCODESLLIST | varbinary(80) | Y | List of change/cancel codes (binary). | all zero | 3561-3640 |
| ACTIVE_NO_MORE | tinyint | Y | Unknown flag ("no more" family). | 0 | 3641 |
| NO_MORE | tinyint | Y | Unknown flag. | 0 | 3642 |
| SHIFTS_1_BEGTIME, SHIFTS_1_ENDTIME, SHIFTS_2_BEGTIME, SHIFTS_2_ENDTIME, SHIFTS_3_BEGTIME, SHIFTS_3_ENDTIME, SHIFTS_4_BEGTIME, SHIFTS_4_ENDTIME | smallint x8 | Y | Begin/end of up to four duty shifts (minutes since midnight, inference). | all 0 | 3643-3658 |
| EXCLUDE_ADHOC | tinyint | Y | Flag: exclude ad-hoc flights. | 0 | 3659 |
| AVERAGEWEIGHT | int | Y | Default average passenger weight. | 0 | 3660-3663 |
| AVERAGEBAGGAGE | int | Y | Default average baggage weight. | 0 | 3664-3667 |
| DRMMESSAGESPATH | nchar(30) | Y | File-system path for DRM message files (value not reproduced; a configuration path). | non-blank (30 chars) | 3668-3727 |
| NO_MORE2, NO_MORE3, NO_MORE4 | tinyint x3 | Y | Unknown flags. | 0,0,0 | 3728-3730 |
| MTCE_CAT1, MTCE_CAT2, MTCE_CAT3, MTCE_CAT4 | tinyint x4 | Y | Maintenance category flags/ids (4). | 0,0,0,0 | 3731-3734 |
| ACTIVE_NO_MORE2, ACTIVE_NO_MORE3, ACTIVE_NO_MORE4 | tinyint x3 | Y | Unknown flags. | 0,0,0 | 3735-3737 |
| CREWSEATSRULE | tinyint | Y | Crew-seat rule selector. | 0 | 3738 |
| SERVICETYPESINBITS_1, SERVICETYPESINBITS_2, SERVICETYPESINBITS_3, SERVICETYPESINBITS_4 | tinyint x4 | Y | 32-bit set of service types (bit mask over the 26 flight types), 4 bytes. | 0,0,0,0 | 3739-3742 |
| FLTSTATUSONATD | tinyint | Y | Flag: set flight status on actual-time-of-departure. | 1 | 3743 |
| FUTURE | varbinary(172) | Y | Reserved bytes ("future use"). | 172 bytes, not all zero | 3744-3915 |

Counting check: the 310 columns = RECDESC 1 + XACDUTY 12 + FLTYPE 104 + STATUS 40 + REGION 96 + scalar block 57.

## 4. Keys & relationships
* No key: one row. Logical (positional) joins - *slot index = stored code value*:
  * `LEGMAIN.FLTYPE` -> `FLTYPE_<FLTYPE>_CODE/DESC`: `LEFT JOIN flight_service_type fst ON fst.FLTYPE_INDEX = FinalBase.FLTYPE` (rpt.Get_Detailed_Pairing.sql:135-146,309), where the CTE unpivots the 26 slots with `vvFMSCodes CROSS APPLY (VALUES (1, FLTYPE_1_CODE, FLTYPE_1_DESC), ..., (26, ...))`;
  * `LEGMAIN.LEGSTATUS` -> `STATUS_<n>_CODE/DESC` (documented in LEGMAIN.md; not used by the procedures here);
  * `SPEFRECDATA.FLTTYP` bit n -> `FLTYPE_<n>_DESC` (rule kind 8): `CASE Indexes.IDX WHEN 1 THEN (SELECT top 1 FLTYPE_1_DESC FROM vvFMSCodes) ... END` (rpt.Get_Custom_Rules_*.sql:254-278);
  * `LEGMAIN.ACDUTY` -> `TABLES.FMACDUTY` slot (same layout as `XACDUTY_n`).

## 5. Encoding conventions & gotchas
* **Positional codes**: the code stored on a leg (`LEGMAIN.FLTYPE`, `LEGSTATUS`) is a *slot number*, not the letter code; the letter (`C`, `J`, ...) is `FLTYPE_n_CODE`. `FLTYPE = 0` / NULL matches nothing (about 4,900 of 13,650 legs in DAY 17000-17100 have FLTYPE 0, so `Service_Type` is NULL for them).
* **Unused slots are blank strings, not NULL** (codes/descriptions are space-padded `nchar`; flags 0). The `WHERE V.FLTYPE_CODE IS NOT NULL` in the pairing CTE therefore does not remove the 13 blank flight-type slots; they are harmless because no leg references them. The rule procedures filter them with `LTRIM(RTRIM(FLTTYP_DESC)) <> ''`.
* Declared `nchar(n)` is in characters: codes are only 2 characters (3 for regions) and descriptions 20 characters; longer text would be truncated by the editor.
* SEL 8 rules match on the **description text** (`Service_Type = FLTYPE_n_DESC`), so a changed description in the setup screen silently changes the rule's meaning; typo "SURFACE VEHICULE" is the stored spelling.
* One row only: always read with `TOP 1` / no join key; a join to it without a predicate is a cross join with 1 row (fine), but never expect more rows.
* The view decodes a blob: it cannot be indexed and each reference re-parses the payload; the procedures call `SELECT top 1 ... FROM vvFMSCodes` 26 times per rule row - negligible at this size.
* `FUTURE`, `OLDCCODESLLIST`, `CCODESLLIST` are `varbinary` (reserved/legacy).

## 6. How the planner-assist procedures use it
* `rpt.Get_Detailed_Pairing`: CTE `flight_service_type` (unpivot of `FLTYPE_1..26_CODE/DESC`) -> `Service_Type` per leg (`LEGMAIN.FLTYPE`). Service type is one of the leg attributes that R1/R2 compare against rule conditions.
* `rpt.Get_Custom_Rules_CertainFlightsCrew` / `rpt.Get_Custom_Rules_Schedule_WithWithNot`: translate `SPEFRECDATA.FLTTYP` bits 1..26 into the list of `Flight_Type` descriptions (JSON `Flight_Type`); `dbo.R1_Get_Violations_CertainFlightsCrew` / `dbo.R2_Get_Violations_Schedule_WithWithNot` match them with the leg's `Service_Type` (rule kind 8).
* No other procedure (R3-R5) reads it. No procedure reads XACDUTY, STATUS, REGION or the scalar block.

## 7. Typical query patterns
```sql
-- 1. The flight service types (slot number = LEGMAIN.FLTYPE), with revenue flag
SELECT v.Slot, RTRIM(v.Code) AS Code, RTRIM(v.Descr) AS Description, v.Revenue
FROM TSC.dbo.vvFMSCodes
CROSS APPLY (VALUES
  (1,FLTYPE_1_CODE,FLTYPE_1_DESC,FLTYPE_1_REVENUE),(2,FLTYPE_2_CODE,FLTYPE_2_DESC,FLTYPE_2_REVENUE),(3,FLTYPE_3_CODE,FLTYPE_3_DESC,FLTYPE_3_REVENUE),
  (4,FLTYPE_4_CODE,FLTYPE_4_DESC,FLTYPE_4_REVENUE),(5,FLTYPE_5_CODE,FLTYPE_5_DESC,FLTYPE_5_REVENUE),(6,FLTYPE_6_CODE,FLTYPE_6_DESC,FLTYPE_6_REVENUE),
  (7,FLTYPE_7_CODE,FLTYPE_7_DESC,FLTYPE_7_REVENUE),(8,FLTYPE_8_CODE,FLTYPE_8_DESC,FLTYPE_8_REVENUE),(9,FLTYPE_9_CODE,FLTYPE_9_DESC,FLTYPE_9_REVENUE),
  (10,FLTYPE_10_CODE,FLTYPE_10_DESC,FLTYPE_10_REVENUE),(11,FLTYPE_11_CODE,FLTYPE_11_DESC,FLTYPE_11_REVENUE),(12,FLTYPE_12_CODE,FLTYPE_12_DESC,FLTYPE_12_REVENUE),
  (13,FLTYPE_13_CODE,FLTYPE_13_DESC,FLTYPE_13_REVENUE)) v(Slot,Code,Descr,Revenue)
WHERE LTRIM(RTRIM(v.Code)) <> '';

-- 2. Service-type description of legs (narrow LEGMAIN.DAY window; CARRIER = 1 = own flights)
SELECT TOP 20 l.DAY, l.FLT, l.FLTYPE, RTRIM(t.Descr) AS ServiceType
FROM TSC.dbo.LEGMAIN l
LEFT JOIN (SELECT v.Slot, v.Descr FROM TSC.dbo.vvFMSCodes CROSS APPLY (VALUES (1,FLTYPE_1_DESC),(2,FLTYPE_2_DESC),(3,FLTYPE_3_DESC),(4,FLTYPE_4_DESC),(5,FLTYPE_5_DESC),(6,FLTYPE_6_DESC),(7,FLTYPE_7_DESC),(8,FLTYPE_8_DESC),(9,FLTYPE_9_DESC),(10,FLTYPE_10_DESC),(11,FLTYPE_11_DESC),(12,FLTYPE_12_DESC),(13,FLTYPE_13_DESC)) v(Slot,Descr)) t ON t.Slot = l.FLTYPE
WHERE l.DAY BETWEEN 17100 AND 17101 AND l.CARRIER = 1;

-- 3. Leg status codes
SELECT v.Slot, RTRIM(v.Code) AS Code, RTRIM(v.Descr) AS Description
FROM TSC.dbo.vvFMSCodes
CROSS APPLY (VALUES (1,STATUS_1_CODE,STATUS_1_DESC),(2,STATUS_2_CODE,STATUS_2_DESC),(3,STATUS_3_CODE,STATUS_3_DESC),(4,STATUS_4_CODE,STATUS_4_DESC),(5,STATUS_5_CODE,STATUS_5_DESC),(6,STATUS_6_CODE,STATUS_6_DESC)) v(Slot,Code,Descr);
```

## 8. Data profile (measured 2026-11-03)
* 1 row (`RECDESC = 'FMSCODES'`, payload 3,915 bytes). Populated slots: XACDUTY 1 of 6 (`PS`), FLTYPE 13 of 26, STATUS 6 of 20, REGION 8 of 24.
* Flight types (slot: code - description, revenue): 1 C CHARTER 1; 2 J SCHEDULED SERVICE 1; 3 E VIP FLIGHT 1; 4 P FERRY 0; 5 K TRAINING 0; 6 T TEST FLIGHT 0; 7 G ADDITIONAL FLIGHTS 1; 8 Z OTHER AIRLINES 0; 9 U SURFACE VEHICULE 1; 10 O SPECIAL CHARTER 1; 11 X TECH STOP 0; 12 H CHARTER CARGO 1; 13 F SCHEDULED CARGO 1.
* Statuses: 1 CA CANCELLED; 2 RS RE-SCHEDULE; 3 DV DIVERTED; 4 RR RE-ROUTED; 5 QG Rtn to ramp; 6 QF Rtn fm airborn. Regions: 1 SA SOUTH AMERICA; 2 ME MIDDLE EAST; 3 FE FAR EAST; 4 PC PACIFIC; 5 IE EUROPE; 6 TA ATLANTIC; 7 AF AFRICA; 8 NA NORTH AMERICA (REGIONBAG = NO_DBC = 0 on all).
* Usage in the data (DAY 17000-17100, all carriers): `LEGMAIN.FLTYPE` = 2 (scheduled) on 8,610 legs, 0 on 4,898, 4 (ferry) on 133, 7 on 6, 5 on 5, NULL on 4.

## 9. Open questions / confidence
* High confidence: the FLTYPE/STATUS/REGION/XACDUTY layout and meaning (byte-sum proof, spot reads, code, and LEGMAIN usage); the positional join `LEGMAIN.FLTYPE -> slot`.
* Low confidence / unknown: every scalar setting in 3.5 (names only; unused by procedures); `FLTYPE_n_FUT`, `REGION_n_REGIONBAG`, `REGION_n_NO_DBC` semantics; what the six `XACDUTY_n` slots are for given `FMACDUTY` is the list LEGMAIN actually uses.
* The view definition is unavailable, so the claim that it is `SELECT ... FROM TABLES WHERE RECDESC = 'FMSCODES'` is an inference (consistent with the blob size and offsets).