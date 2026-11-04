# SPEFRECDATA  (Table)  - Detail/list data of the custom "special rules" (flight-condition parameters of SPEFREC1/2/3 rules)

## 1. Purpose & business meaning
The AIMS special-rules engine stores each rule as a *header* row in a family table (`SPEFREC1`, `SPEFREC2`, `SPEFREC3`, ...) and the **parameters of the rule's flight condition** (`SEL`) in this single shared detail table.
Where the header says "this rule applies to flights *with the following aircraft registrations / via airports of category X / to country categories Y / of carriers Z ...*", the actual registrations, carriers, airports, category bits and aircraft types are here.

Row identity = (RULE_, KIND, PLANDAYTODAY, IDX):
* `RULE_` 0..99 - the rule number;
* **`KIND` - which header table the row belongs to**: **1 = SPEFREC1** (crew-complement rules, "68 crew complement"), **2 = SPEFREC2** (*Schedule with / with-not*), **3 = SPEFREC3** (*Certain flights for certain crews*). (KIND 4/5/6 = SPEFREC4N / SPEFREC5 headers have no rows here.) The pairing (RULE_, KIND, PLANDAYTODAY) is the foreign key to the header.
* `PLANDAYTODAY` - rule set: **1 = Plan, 2 = Day-to-Day** (same meaning as in the headers);
* `IDX` 1..48 - slot number of the repeating group. Each rule can have up to **48 list entries** (48 parallel slots for station / registration / carrier / charterer). The per-rule bit-masks (`CRTECAT`, `AIRCAT`, `CITCAT`, `CTRCAT`, `FLTCATS`, `FLTTYP`, `AIRTYP`, `AIRTYP2`) are **not** per slot: they are stored identically (replicated) on every slot row of the rule (verified on every populated rule).

A rule that was never given list data has exactly **1 row (IDX = 1, all columns empty)**; a rule whose list screen was saved has **48 rows (IDX 1..48)**, regardless of how many slots are filled. Maintained by the AIMS special-rules screens; read only (here) by `rpt.Get_Custom_Rules_Schedule_WithWithNot` and `rpt.Get_Custom_Rules_CertainFlightsCrew`.

## 2. Physical facts
* `TSC.dbo.SPEFRECDATA`, base table, **2,853 rows** (2026-11-03): KIND 1 = 194 (Plan) + 193 (Day-to-Day); KIND 2 = 805 + 804; KIND 3 = 429 + 428.
* PK/unique clustered index `SPEFRECDATA_INDEX_0` on (RULE_, KIND, PLANDAYTODAY, IDX): seeks by (RULE_, KIND, PLANDAYTODAY) then ordered by IDX. Tiny table.
* No identity/audit/soft-delete. No orphans: every KIND 2 / KIND 3 row has a header in `SPEFREC2` / `SPEFREC3` (checked: 0 orphans).
* (The metadata extract `columns.json` reports `nchar` lengths in **bytes**; the real declared lengths are BASE nchar(4), REG nchar(12), CARR nchar(4), CHART nchar(3).)

## 3. Column dictionary
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| RULE_ | smallint | N | Rule number = `SPEFREC<k>.RULE_`. | 0..99. | indexes.json; rpt.Get_Custom_Rules_*.sql |
| KIND | tinyint | N | Header family. | 1 = SPEFREC1, 2 = SPEFREC2 (with / with-not), 3 = SPEFREC3 (certain flights for certain crews). The rules procedures filter `KIND = 2` / `KIND = 3`. | profiled; rpt...WithWithNot.sql:399; ...CertainFlightsCrew.sql:8 (`@Filter_Kind = 3`) |
| PLANDAYTODAY | tinyint | N | Rule set. | 1 = Plan, 2 = Day-to-Day. | same |
| IDX | smallint | N | Slot number inside the rule's repeating list. | 1..48. `ORDER BY IDX` + `TOP 1` picks slot 1 for the scalar masks; all rows are aggregated for the lists. | rpt...WithWithNot.sql:194,402; ...CertainFlightsCrew.sql:155,349; profiled |
| CRTECAT | binary(6) | Y | Bit-mask of **route (crew pairing) categories** = GENCAT type 1 (SEL 4). | Bit N (1..48) = GENCATINDEX N: byte `CEILING(N/8)` (1-based, forward byte order), bit `(N-1)%8` (0 = LSB). e.g. KIND 1 rule 1 = `0x010000000000` = index 1 "Augmented". Procedures convert it to `binary(32)` (right zero-padded) before decoding; the pairing side (CRROUTE.RTECAT) is decoded with *reversed* byte order (see gotchas). | rpt...WithWithNot.sql:200-207; profiled |
| AIRCAT | binary(4) | Y | Bit-mask of **airport categories** (SEL 5: GENCAT type 3 / PORTCATEG) **or** of *additional* airport categories (SEL 21: GENCAT type 17 / PORTCATEG2). Same column, interpreted by SEL. | 32 bits, same bit layout. **Empty in all rows today.** | rpt...WithWithNot.sql:209-229 (`TM.Flight_Kind_Id = 5` / `= 21`) |
| AIRTYP2 | binary(12) | Y | Second aircraft-type selection (up to 96 types). | **Layout not certain.** The procedures read it byte-wise (11 one-byte ACTYPE ids -> `Aircraft_Types2`, only shown in the raw JSON, **never evaluated**). The live values (`0x682000400000...`, `0xFF3F020C...`, `0xFFFF1F0C...`) are sparse bit patterns, and bytes such as 0x68=104 are not valid `ACTYPE` ids (1..35), so it looks like a **bit-mask: bit k of AIRTYP2 = AIRCTYPE.ACTYPE k** (inference). Non-empty only on KIND 1 rule 1 and KIND 3 rules 2 and 3 (all 48 rows). | rpt...CertainFlightsCrew.sql:242-252; profiled |
| FLTTYP | binary(8) | Y | Bit-mask of **flight (service) types** (SEL 8) or of **A/C versions** (SEL 23). | SEL 8: bit N (1..26) = `vvFMSCodes.FLTYPE_N_*` = value of `LEGMAIN.FLTYPE`. SEL 23: bits 0-3 of **byte 1** = slot 1..4 of the `TABLES.FMACDUTY` version list. **Empty in all rows today.** | rpt...CertainFlightsCrew.sql:254-286 |
| FLTCATS | binary(6) | Y | Bit-mask of **flight categories** (SEL 15) = GENCAT type 6 (bit N up to 48; compares with `LEGMAIN.FLTCAT`). | 48 bits, forward order. Empty today. | rpt...WithWithNot.sql:303-310 |
| BASE | nchar(4) | Y | List entry (slot IDX): an **airport/base code** (3-letter IATA). One column feeds three SEL meanings: SEL 11 bases (to/from), SEL 16 night-stop stations, SEL 19 airports (via). | Space padded; unused slots blank (the procedures strip `CHAR(0)`). **No row has a BASE today.** | rpt...: `Lists.Base`, `Lists.Station`, `Lists.Airport` |
| REG | nchar(12) | Y | List entry: **aircraft registration** (SEL 12). | e.g. `F-GZHA`, `C-GEXI`; blank when unused. 15 populated slots (rules of KIND 3: 5 + 9 + 1). | rpt...: `Lists.Registration`; profiled |
| CARR | nchar(4) | Y | List entry: **carrier (airline) code** (SEL 13). | 1 populated slot (KIND 2 rule 17: the airline's own code). | `Lists.Carrier`; profiled |
| CHART | nchar(3) | Y | List entry: **charterer code** (SEL 14, "flights on behalf of the following charterers"). | 3 populated slots (KIND 1 rule 7: `ADV`, `ET6`, `SSV`). **SEL 14 is not evaluated** by R1/R2 (treated as always true). | `Lists.Charter`; profiled |
| CITCAT | binary(4) | Y | Bit-mask of **city-pair categories** (SEL 6) = GENCAT type 2 / CITYCATEG. | 32 bits. Empty today. | rpt...WithWithNot.sql:231-239 |
| CTRCAT | binary(4) | Y | Bit-mask whose **meaning depends on the header's SEL**: SEL 7 / 17 -> country categories (GENCAT type 4 / COUNTRYCATEG); SEL 18 -> aircraft categories (TABLES `AIRCATEGnn` / ACCATEG); SEL 20 -> additional aircraft categories (GENCAT 18 / ACCATEG2); SEL 22 -> "via country" additional categories (GENCAT 19). | 32 bits. Populated on KIND 3 rule 3 (`0x04000000` = bit 3 = "MEC OVER AGE 60 - CANNOT OPERATE") and one further row in the KIND 3 Plan set (not examined); empty elsewhere. | rpt...WithWithNot.sql:241-260,313-338 |
| AIRTYP | binary(96) | Y | **List of aircraft types** (SEL 9): up to 96 one-byte `AIRCTYPE.ACTYPE` ids; the procedures read the first 8 bytes only. | Byte value 0 = unused slot; resolved through `vvAIRCTYPE` (`EXCL_FROM_MVT = 0`) to `IATACODE`. **All zero in every row today.** | rpt...CertainFlightsCrew.sql:223-234 |

## 4. Keys & relationships
* Natural key: (RULE_, KIND, PLANDAYTODAY, IDX) (= PK).
* **To the header** (1 header : 1 or 48 rows), exact predicates used:
  * with / with-not: `SPEFRECDATA.KIND = 2 AND SPEFRECDATA.RULE_ = SPEFREC2.RULE_ AND SPEFRECDATA.PLANDAYTODAY = SPEFREC2.PLANDAYTODAY` (rpt.Get_Custom_Rules_Schedule_WithWithNot.sql:399-401);
  * certain flights / crews: `SPEFRECDATA.KIND = 3 AND SPEFRECDATA.RULE_ = SPEFREC3.RULE_ AND SPEFRECDATA.PLANDAYTODAY = SPEFREC3.PLANDAYTODAY` (rpt.Get_Custom_Rules_CertainFlightsCrew.sql:346-348).
* Bits -> names: `CRTECAT`->`GENCAT(1)`, `AIRCAT`->`GENCAT(3)`/`(17)`, `CITCAT`->`GENCAT(2)`, `CTRCAT`->`GENCAT(4)`/`(18)`/`(19)`/`TABLES.AIRCATEGnn`, `FLTCATS`->`GENCAT(6)`, `FLTTYP`->`vvFMSCodes.FLTYPE_n_DESC` or `TABLES.FMACDUTY`, `AIRTYP`->`vvAIRCTYPE.ACTYPE` (-> `IATACODE`).
* List values -> the pairing: `REG` = `LEGMAIN.REG` (`AC_Registration`), `CARR` = carrier code of the leg (`vvCarriers.code`), `BASE` = `LEGMAIN.DEP`/`ARR` (or the night-stop station, `HOTAC.SUPPLIERSTN`).

## 5. Encoding conventions & gotchas
* **Decode formula for any GENCAT-based mask M and category N**: `byte = SUBSTRING(CONVERT(binary(32), M), CEILING(N/8.0), 1)`; set iff `(CONVERT(tinyint, byte) / POWER(2,(N-1)%8)) % 2 = 1` (the procedures call the scalar UDF `TSC.dbo.bit_is_set(byte, bitpos)`).
  Crew-category masks in the headers (`CATEG`, `CATEG1`, `CATEG2`) differ: **2 header bytes first, then categories from byte 3** (see SPEFREC2.md). Do not mix the two layouts.
* **The interpretation of `CTRCAT`, `AIRCAT` and `FLTTYP` depends on the header's SEL** (the same 32 bits mean country categories, aircraft categories, additional aircraft categories... depending on the rule). A mask can therefore only be decoded together with its header.
* **The masks are repeated on all 48 slot rows**; read them from one row (`TOP 1 ... ORDER BY IDX`, as the procedures do) or `DISTINCT`, never count rows to count categories. Counting `COUNT(*)` of a rule gives 1 or 48, not the number of list items; count only slots with non-empty values.
* Empty text slots can contain NUL (`CHAR(0)`) or blanks: use `LEN(REPLACE(col, CHAR(0), '')) > 0` (as the procedures do) to detect a filled slot.
* The three BASE-based lists (SEL 11, 16, 19) share the same column: in `rpt.Get_Custom_Rules_CertainFlightsCrew` the three JSON keys `Lists.Base`, `Lists.Station`, `Lists.Airport` are all filled from the same BASE values whatever the rule's SEL (the consumer then reads the key matching SEL); `Lists.Registration`, `Lists.Carrier` and `Lists.Charter` likewise. In `rpt.Get_Custom_Rules_Schedule_WithWithNot` the Base/Station/Airport keys are filtered by SEL.
* The lists are published as **one comma-separated string** under `$.Lists.<Base|Station|Airport|Registration|Carrier|Charter>`; R1/R2 `STRING_SPLIT` it (R1-2/R2-2 fix).
* `AIRTYP` (SEL 9) is decoded from the first 8 bytes only (max 8 types); `AIRTYP2` is not evaluated at all.
* Route-category bit order differs between the two sides: `SPEFRECDATA.CRTECAT` is forward (bit 1-8 in byte 1) but `rpt.Get_Detailed_Pairing` reads `CRROUTE.RTECAT` as `CONVERT(BINARY(4), rtecat)` with bits 1-8 in **byte 4**, 9-16 in byte 3, ... - the two use different byte orders for the same GENCAT type-1 numbering (comparison is by name, so a wrong order silently gives wrong results).
* SEL 14 (charterers) and SEL 22 (via-country additional categories) are accepted by R1/R2 as "always true" ("Not used options"); SEL 23 (AC version): R1 flags it as unsupported (warning), R2 evaluates it as never matched.
* Row inflation: a rule header joined to its data rows multiplies by 48; aggregate or `TOP 1` before joining.

## 6. How the planner-assist procedures use it
Both rules procedures build, per active header rule, one **JSON document** ("Subconditions_Raw_JSON") from this table:
`SELECT TOP 1 RULE_, KIND, PLANDAYTODAY, <decoded masks>, <aggregated lists> FROM SPEFRECDATA WHERE KIND=<k> AND RULE_=<rule> AND PLANDAYTODAY=<set> ORDER BY IDX FOR JSON PATH, WITHOUT_ARRAY_WRAPPER` with the keys
`Route_Categories` (CRTECAT, GENCAT 1), `Airport_Category` (AIRCAT, GENCAT 3), `Airport_Additional_Category` (AIRCAT, GENCAT 17), `City_Pairs_Category` (CITCAT, GENCAT 2), `Country_Category` (CTRCAT, GENCAT 4), `Aircraft_Additional_Category` (CTRCAT, GENCAT 18),
`Cat_G19_CountryVia` (CTRCAT, GENCAT 19; with/with-not proc only), `Flight_Categories` (FLTCATS, GENCAT 6), `Flight_Type` (FLTTYP -> vvFMSCodes), `Aircraft_Types` (AIRTYP -> vvAIRCTYPE), `Aircraft_Types2` (AIRTYP2, byte-wise, unused), `Aircraft_Version` (FLTTYP byte 1 -> TABLES FMACDUTY),
`Aircraft_Category` (CTRCAT -> TABLES AIRCATEGnn) and `Lists.{Base,Registration,Carrier,Charter,Station,Airport}` (comma-separated). A `Subconditions` column then extracts the part relevant to the rule's SEL via `JSON_QUERY`.

**What SEL means and how R1/R2 evaluate it against a pairing leg** (the leg attributes come from `rpt.Get_Detailed_Pairing`):

| SEL | Flight condition (as shown to planners) | Parameter source in SPEFRECDATA | Leg attribute tested (match = 1) |
|---|---|---|---|
| 1 | International flights | none | `Is_International = 'Yes'` (dep or arr airport `OVERSEAS = 1`) |
| 2 | Domestic flights | none | `Is_Domestic = 'Yes'` (both airports `OVERSEAS = 0`) |
| 3 | Any kind of flights | none | always true |
| 4 | Flights with crew route categories | `CRTECAT` -> GENCAT 1 | `Crew_Route_Categories` (CRROUTE.RTECAT) shares a name with the JSON `Route_Categories` |
| 5 | Flights via airports of categories | `AIRCAT` -> GENCAT 3 | `Dep_Airport_Categories` OR `Arr_Airport_Categories` (PORTCATEG) share a name |
| 6 | City pairs of categories | `CITCAT` -> GENCAT 2 | `City_Pair_Categories` (CITYCATEG, either direction) |
| 7 | Flights to country categories | `CTRCAT` -> GENCAT 4 | `Country_Categories` (COUNTRYCATEG of the **arrival** airport's country) |
| 8 | Flights with flight (service) types | `FLTTYP` bits -> `vvFMSCodes.FLTYPE_n_DESC` | `Service_Type` (LEGMAIN.FLTYPE description) equals one type |
| 9 | Flights with AC types | `AIRTYP` bytes -> `vvAIRCTYPE.IATACODE` | `AC_Type` equals one type |
| 10 | Overnight flight | none | `Is_Overnight = 'Yes'` (local departure after civil twilight end and no night-stop at arrival) |
| 11 | Flights to/from bases | `BASE` list | Departure OR Arrival airport in list |
| 12 | Aircraft registrations | `REG` list | `AC_Registration` in list |
| 13 | Carriers | `CARR` list | `Carrier_Code` in list |
| 14 | On behalf of charterers | `CHART` list | **not evaluated (always true)** |
| 15 | Flight categories | `FLTCATS` -> GENCAT 6 | `Flight_Categories` (LEGMAIN.FLTCAT) share a name |
| 16 | Night stops at stations | `BASE` list | `Night_Stop_Station` (HOTAC.SUPPLIERSTN of the crew's hotel night at the arrival) in list |
| 17 | Night stops at countries | `CTRCAT` -> GENCAT 4 | `Night_Stop_Country` (name of the country category of the hotel airport) in list |
| 18 | Aircraft of categories | `CTRCAT` -> TABLES `AIRCATEGnn` | `Aircraft_Categories` (ACCATEG of the leg's tail) share a name |
| 19 | Flights via airports | `BASE` list | Departure OR Arrival airport in list |
| 20 | Aircraft of additional category | `CTRCAT` -> GENCAT 18 | `Aircraft_Additional_Categories` (ACCATEG2) - no data |
| 21 | Via airport of additional category | `AIRCAT` -> GENCAT 17 | `Departure/Arrival_Airport_Additional_Categories` (PORTCATEG2) - no data |
| 22 | Via countries of additional category | `CTRCAT` -> GENCAT 19 | not evaluated (always true) |
| 23 | AC versions | `FLTTYP` byte 1 -> TABLES FMACDUTY | R2: never true; R1: unsupported (warning) |

### Worked example - how a "with / with-not" rule is defined and fires
Rule 16 of SPEFREC2 (Day-to-Day set): `PLANDAYTODAY = 2, ACTIVE = 1, SCHE = 1 (Always Schedule), POS1 = 2 (PO), CATEG1 = {FO en LI - RC}, POS2 = 1 (CM), CATEG2 = {A CHECK A330, B CHECK A330, CD Line check de droite A330, A CHECK A321, B CHECK A321, CD Line check de droite A321}, SEL = 3, AUTOHARD = 1 (Company), MSG = "DOIT VOLER AVEC PILOTE VERIFICATEUR"`.
Its SPEFRECDATA rows (`KIND = 2`, `RULE_ = 16`, `PLANDAYTODAY = 2`) hold 48 empty slots (SEL 3 needs no parameters). Meaning: *a first officer holding category "FO en LI - RC" must, on every leg, be scheduled with a captain who holds one of the check-pilot categories; if none of the crew of that physical leg qualifies, R2 reports 'ALWAYS SCHEDULE VIOLATION' (severity Company, message above)*.
Contrast rule 1 (`SCHE = 2`): PO [JUNIOR FO] with CM [JUNIOR CPT] on the same leg -> 'DO NOT SCHEDULE VIOLATION' (severity Government, "Junior CM and FO cannot fly together").

### Worked example - a data-bearing rule (certain flights / crews)
SPEFREC3 rule 1 (inactive, "Can't Operate on this AC TAIL", `SEL = 12`, POS 25 = CM|PO, SCHE 2): SPEFRECDATA `KIND = 3, RULE_ = 1` slots IDX 1..5 carry five aircraft registrations in `REG`; the procedure aggregates them to `Lists.Registration = 'F-GZHA, F-GZHB, F-GZHD, F-GZHI, F-GZHJ'`, and R1 flags a drafted CM/PO flying a leg whose `AC_Registration` is in that list.

## 7. Typical query patterns
```sql
-- 1. The list entries (registrations) of a rule - the Day-to-Day set, certain-flights family
SELECT d.IDX, LTRIM(RTRIM(REPLACE(d.REG, CHAR(0), ''))) AS Registration
FROM TSC.dbo.SPEFRECDATA d
WHERE d.KIND = 3 AND d.PLANDAYTODAY = 2 AND d.RULE_ = 1 AND LEN(REPLACE(d.REG, CHAR(0), '')) > 0
ORDER BY d.IDX;

-- 2. Header + condition parameters for every active with/with-not rule that has any list value (one row per rule, no x48 inflation)
SELECT e.RULE_, e.SEL,
       (SELECT STRING_AGG(LTRIM(RTRIM(REPLACE(d.REG, CHAR(0), ''))), ', ') FROM TSC.dbo.SPEFRECDATA d
         WHERE d.KIND = 2 AND d.RULE_ = e.RULE_ AND d.PLANDAYTODAY = e.PLANDAYTODAY AND LEN(REPLACE(d.REG, CHAR(0), '')) > 0) AS Registrations,
       (SELECT STRING_AGG(LTRIM(RTRIM(REPLACE(d.BASE, CHAR(0), ''))), ', ') FROM TSC.dbo.SPEFRECDATA d
         WHERE d.KIND = 2 AND d.RULE_ = e.RULE_ AND d.PLANDAYTODAY = e.PLANDAYTODAY AND LEN(REPLACE(d.BASE, CHAR(0), '')) > 0) AS Bases
FROM TSC.dbo.SPEFREC2 e WHERE e.PLANDAYTODAY = 2 AND e.ACTIVE <> 0;

-- 3. Route-category names set on a rule's CRTECAT mask (slot 1 carries the mask), e.g. SPEFREC1 rule 1 (KIND = 1)
SELECT g.GENCATINDEX, LTRIM(RTRIM(g.DESC_)) AS RouteCategory
FROM TSC.dbo.SPEFRECDATA d JOIN TSC.dbo.GENCAT g ON g.GENCATTYPE = 1 AND g.GENCATINDEX > 0
WHERE d.KIND = 1 AND d.RULE_ = 1 AND d.PLANDAYTODAY = 2 AND d.IDX = 1
  AND (CONVERT(tinyint, SUBSTRING(CONVERT(binary(32), d.CRTECAT), CEILING(g.GENCATINDEX/8.0), 1)) / POWER(2,(g.GENCATINDEX-1)%8)) % 2 = 1;

-- 4. Slot-count sanity check: how many rows per rule (1 = never saved, 48 = saved)
SELECT KIND, PLANDAYTODAY, COUNT(*) AS DataRows, COUNT(DISTINCT RULE_) AS Rules FROM TSC.dbo.SPEFRECDATA GROUP BY KIND, PLANDAYTODAY ORDER BY 1,2;
```

## 8. Data profile (measured 2026-11-03)
* 2,853 rows: KIND 1 = 387 (Plan 194, DTD 193; 100 / 99 rules), KIND 2 = 1,609 (805 / 804), KIND 3 = 857 (429 / 428). IDX 1..48. Rules with 1 row vs 48 rows: KIND 1: 98/2 (Plan), 97/2 (DTD); KIND 2: 85/15, 84/15; KIND 3: 93/7, 92/7. No other row counts per rule exist.
* 48-row rules: KIND 1 -> rules 1, 7; KIND 2 -> rules 2, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19 (identical in both sets); KIND 3 -> rules 1, 2, 3, 5, 6, 7, 9.
* Content: **every `AIRCAT`, `FLTTYP`, `CITCAT`, `AIRTYP`, `FLTCATS` and `BASE` value is empty/zero in all 2,853 rows.** Populated: `CRTECAT` (KIND 1, 48 rows per set: rule 1 = route category 1 "Augmented"), `AIRTYP2` (KIND 1 rule 1; KIND 3 rules 2 and 3 - 48 rows each), `CHART` (KIND 1 rule 7: 3 charterer codes), `CARR` (KIND 2 rule 17: 1 carrier code),
  `REG` (KIND 3: rule 1 = 5 registrations, rule 7 = 9, rule 9 = 1), `CTRCAT` (KIND 3 rule 3 = category bit 3 "MEC OVER AGE 60 - CANNOT OPERATE"; one extra row in the KIND 3 Plan set).
* Consequence: the live **active** rules (all `SEL = 3` any-flight in KIND 2 and 3) do not depend on this table at all; the table content matters only for inactive/historic rules (aircraft restrictions, over-60 country restrictions, jumpseat equipment).

## 9. Open questions / confidence
* High confidence: key semantics (KIND = header table, PLANDAYTODAY, IDX = slot), forward bit layout of the GENCAT-based masks (confirmed by decoded names that match the rule messages, e.g. CTRCAT bit 3 = "MEC OVER AGE 60" on the "MECH OVER 60 YEARS OLD" rule; CRTECAT bit 1 = Augmented), list columns, and the SEL -> source/evaluation mapping (code).
* Medium/uncertain: `AIRTYP2` layout (bit-mask vs byte list - inferred bit-mask; never evaluated); meaning of the SPEFREC1 (KIND 1) rows (SPEFREC1 not documented here); `FLTTYP`/`AIRCAT`/`CITCAT`/`FLTCATS` decoding is code-derived but untestable (no data).
* Why a rule has 48 slot rows even with SEL 3 is unknown (AIMS pre-creates all 48 slots when the list screen is saved - inference).
