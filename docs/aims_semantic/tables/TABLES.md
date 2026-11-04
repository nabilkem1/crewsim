# TABLES  (Table)  - AIMS generic "named record" registry (key = RECDESC, payload = packed FIELDS blob)

## 1. Purpose & business meaning
`TABLES` is the AIMS **catch-all configuration/lookup store**. Instead of one SQL table per small setup screen, AIMS keeps a record per screen in this table:
`RECDESC` is the name of the record (e.g. `FMSCODES`, `FMACDUTY`, `AIRCATEG03`) and `FIELDS` is an `image` column holding a **fixed-layout binary structure** whose layout is known only to the
AIMS application (and to the views `vv*` that decode them, e.g. `vvFMSCodes`). A row is therefore not a "business entity" but one *setup record*; the record families are visible from the prefix of `RECDESC`.
Writers: AIMS setup/administration screens. Readers here: the planner-assist rules procedures (to get names of aircraft categories and of aircraft versions) and, indirectly, through `vvFMSCodes`, the flight service-type descriptions.

Only three record families are used by planner-assist:

| RECDESC | Rows | What the payload means | Used for |
|---|---|---|---|
| `AIRCATEG01` .. `AIRCATEG32` | 32 (8 populated) | **Aircraft (registration) category names.** Record number nn (01..32) = category index nn = `ACCATEG.CATEGIDX` = bit nn in `SPEFRECDATA.CTRCAT` when `SEL = 18`. Payload 108 bytes: first 80 bytes = UCS-2 (`nchar(40)`) description; remaining 28 bytes not decoded. | `Aircraft_Categories` in rpt.Get_Detailed_Pairing; rule kind 18 |
| `FMACDUTY` | 1 | **Aircraft duty (what the aircraft is used for) list**: 4 slots of (code, description); slot k = value k of `LEGMAIN.ACDUTY` (per the LEGMAIN documentation; same layout as `vvFMSCodes.XACDUTY_n`). Payload 2,822 bytes; slot k (k=1..4) starts at byte offset 1 + (k-1)*64: code = 24 bytes (`nchar(12)`), description = 40 bytes (`nchar(20)`). The rule procedures call the slots "Aircraft_Version"; slot k is bit k-1 of byte 1 of `SPEFRECDATA.FLTTYP` when `SEL = 23`. | rule kind 23 (`Aircraft_Version`) |
| `FMSCODES` | 1 | **Flight-movement system code tables** (flight service types, flight statuses, regions, tolerance flags, ...). Payload 3,915 bytes, decoded by the view `vvFMSCodes` (see vvFMSCodes.md). | `Service_Type` (LEGMAIN.FLTYPE -> description) and rule kind 8 |

All other families are application internals (see profile) and are **not** interpreted by this repo; several of them may contain operational parameters or addresses and were deliberately not decoded or profiled.

## 2. Physical facts
* `TSC.dbo.TABLES`, base table, **2,655 rows** (2026-11-03).
* PK `PK_TABLES` on `TABLES_ID` (identity, int). Second **unique** index `TABLES_INDEX_0` on `RECDESC` (non-PK) => `RECDESC` is the natural key and lookups like `WHERE RECDESC LIKE 'FMACDUTY%'`, `WHERE RECDESC >= 'AIRCATEG01' AND RECDESC <= 'AIRCATEG32'` or `RECDESC = 'FMSCODES'` seek on it.
* `FIELDS` is `image` (legacy LOB); payload length varies per family from 9 bytes to 45,980 bytes (`CUSOPTIONS`). Because it is `image`, comparisons need an explicit `CONVERT(varbinary(max), FIELDS)` (the procedures call `SUBSTRING(fields, ...)` directly, which works on image).
* Never `SELECT FIELDS` for all rows: the table holds many large blobs.
* (The metadata extract columns.json reports 
char lengths in **bytes**; the real declared lengths in characters are half of that and are used below.)

## 3. Column dictionary
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| RECDESC | nchar(10) | Y | Name of the setup record = family prefix + serial (e.g. `AIRCATEG03`, `FMACDUTY`, `FMSCODES`). Unique (no duplicates, no NULLs: 2,655 distinct). Space padded; matching is case-insensitive (procedures use lower-case `'aircateg01'` and upper-case `'FMACDUTY%'` alike). | Free 10-character key (the widest values, e.g. `AIRCATEG01`, fill it exactly); many families have a numeric suffix (`...0001`, `...01`), some negative-number suffixes (`FORM9 -1`..`FORM9 -94`). | rpt.Get_Custom_Rules_*.sql:27,44-45; rpt.Get_Detailed_Pairing.sql:69-71,82-88; profiled |
| FIELDS | image | Y | Packed binary payload of the record; layout depends on RECDESC family. NULL only for the record `TABLESINFO` (1 row). | Text sub-fields are **UCS-2** (2 bytes/char) in `AIRCATEG`, `FMACDUTY` and `FMSCODES` (decode with `CONVERT(nchar(n), SUBSTRING(fields, offset, 2*n))`). Numeric/flag sub-fields are single bytes or smallints. | rpt.Get_Detailed_Pairing.sql:65-88; profiled (FMSCODES offset test) |
| TABLES_ID | int | N (identity) | Surrogate id, PK. Range 1..2701 (2,655 rows => ~46 gaps from deletions). | identity | indexes.json; profiled |

## 4. Keys & relationships
* Natural key: `RECDESC` (unique index). Surrogate: `TABLES_ID`.
* No FKs. Logical relationships (all by *text key prefix*, not by id):
  * `AIRCATEGnn` -> `ACCATEG.CATEGIDX = CAST(SUBSTRING(RECDESC, 9, 2) AS INT)` (rpt.Get_Detailed_Pairing.sql:65-71,249-251); also bit `nn` of `SPEFRECDATA.CTRCAT` for rule SEL 18.
  * `FMACDUTY` -> bit k-1 of byte 1 of `SPEFRECDATA.FLTTYP` (rule SEL 23) (rpt.Get_Custom_Rules_*.sql:281-286 / 323-329).
  * `FMSCODES` -> exposed 1:1 by `vvFMSCodes` (one row view).

## 5. Encoding conventions & gotchas
* Decode `AIRCATEG`: `SELECT CAST(SUBSTRING(RECDESC,9,2) AS int) AS CategIdx, LTRIM(RTRIM(CONVERT(nchar(40), SUBSTRING(fields,1,80)))) AS Name FROM TSC.dbo.TABLES WHERE RECDESC >= 'AIRCATEG01' AND RECDESC <= 'AIRCATEG32' AND CONVERT(nchar(40), SUBSTRING(fields,1,80)) <> ''` (this is how the procedures do it). Empty slots exist for 24 of 32 numbers - filter on the blank name.
* `FMACDUTY` is **one row**; the procedures UNION four `SUBSTRING` windows of it to make a 4-row list (index 1..4). The slot names are `PS`=PASSENGER, `FOB`=Fuel on Board, `TRAIN`=TRAIN, `321L`=EUROPE 321L (profiled): i.e. the aircraft-duty codes (passenger, fuel on board, training, a European A321 configuration); the "version" label comes from the rules procedures, the "duty" label from LEGMAIN.ACDUTY.
* The first 4 bytes of the FMSCODES payload are `P\0S\0` (UCS-2 "PS"): text sub-fields are 2 bytes per character, so the 4-byte code field of the view `vvFMSCodes` is `nchar(2)` and its 40-byte description field is `nchar(20)`.
* The RECDESC prefix list shows that many *application-internal* records live here (UI colours, mail/SMS gateway settings, IP white-lists, bid/rule engines, ...). Do not use TABLES as a source of business data except for the three families above.
* Case-insensitive collation is assumed (code mixes cases), not verified against the column collation.

## 6. How the planner-assist procedures use it
* `rpt.Get_Detailed_Pairing` (lines 58-71, 73-88, 249): builds `#AIRCAT_REF(Index_, Desc_)` from `AIRCATEG01..32` and `#FLTTYP_REF(Index_ '1'..'4', Code_, Desc_)` from `FMACDUTY`; `#AIRCAT_REF` is joined to `ACCATEG` to produce `Aircraft_Categories`.
* `rpt.Get_Custom_Rules_CertainFlightsCrew` (lines 18-47) and `rpt.Get_Custom_Rules_Schedule_WithWithNot` (lines 154-188): same two temp tables, used to name the bits of `SPEFRECDATA.CTRCAT` (rule kind 18, `Aircraft_Category`) and `SPEFRECDATA.FLTTYP` byte 1 (rule kind 23, `Aircraft_Version`).
* `vvFMSCodes` (a view over `TABLES.RECDESC = 'FMSCODES'`) is read by both rules procedures and Get_Detailed_Pairing (service-type names).
* R1/R2/R3/R4/R5 never read TABLES directly.

## 7. Typical query patterns
```sql
-- 1. Names of the aircraft categories (index = ACCATEG.CATEGIDX)
SELECT CAST(SUBSTRING(RECDESC,9,2) AS int) AS CategIdx,
       LTRIM(RTRIM(CONVERT(nchar(40), SUBSTRING(CONVERT(varbinary(max),FIELDS),1,80)))) AS Name
FROM TSC.dbo.TABLES
WHERE RECDESC >= 'AIRCATEG01' AND RECDESC <= 'AIRCATEG32'
  AND CONVERT(nchar(40), SUBSTRING(CONVERT(varbinary(max),FIELDS),1,80)) <> ''
ORDER BY 1;

-- 2. The four aircraft-version slots
SELECT s.Slot, LTRIM(RTRIM(CONVERT(nchar(12), SUBSTRING(CONVERT(varbinary(max),t.FIELDS),(s.Slot-1)*64+1,24)))) AS Code,
              LTRIM(RTRIM(CONVERT(nchar(20), SUBSTRING(CONVERT(varbinary(max),t.FIELDS),(s.Slot-1)*64+25,40)))) AS Descr
FROM TSC.dbo.TABLES t CROSS JOIN (VALUES (1),(2),(3),(4)) s(Slot)
WHERE t.RECDESC = 'FMACDUTY';

-- 3. Which record families exist (counts only; no payload)
SELECT LEFT(RTRIM(RECDESC),5) AS Prefix, COUNT(*) AS Records FROM TSC.dbo.TABLES GROUP BY LEFT(RTRIM(RECDESC),5) ORDER BY Records DESC;
```

## 8. Data profile (measured 2026-11-03)
* 2,655 rows, 2,655 distinct `RECDESC`, 0 NULL `RECDESC`, 1 NULL `FIELDS` (`TABLESINFO`); `TABLES_ID` 1..2701.
* 188 distinct 5-character prefixes. Largest families (rows, payload bytes): `ASTUAP0001..9999` 872 (40 B), `SLWCOL0001..9999` 729 (40 B), `CHK_CU0001..1505` 167 (337 B), `MapPrf0004..1518` 162 (596 B), `FORM9 -n` 100 (32 B),
  `TSCCRTCD01..99` 99 (124 B), `TSCCTRY001..040` 40 (140 B), `OCNGRS0001..32` 32, `AIRCATEG01..32` 32 (108 B), `TSCINOUT01..32` 32, `TSCRSTCT01..26` 26. ~130 singleton records (`FMSCODES`, `FMACDUTY`, `CUSOPTIONS`, `LANGUAGE`, `TIMEZONES`, `SSIM_NEW1`, ...).
* `AIRCATEG`: 8 populated: 01 "HD High Density aircraft / 375 seats", 02 "Vacuum aircraft", 03 "A310 A4 type engines", 04 "A310 A2 type engines", 05 "ACFT WITH ONLY ONE A.D.F", 06 "A310 - 308", 07 "ACT equiped aircraft", 08 "LD Low Density aircraft / 332 seats"; 24 blank. `ACCATEG` actually uses indices 5, 7, 8 only.
* `FMACDUTY`: 1 row, 2,822 bytes; `FMSCODES`: 1 row, 3,915 bytes.

## 9. Open questions / confidence
* High confidence: layout of AIRCATEG (80-byte name), FMACDUTY (4 x 64-byte slots) and FMSCODES (verified by byte-sum 3,915 and spot reads, see vvFMSCodes.md).
* Unknown: remaining 28 bytes of each AIRCATEG record (probably flags/colour), remaining bytes of FMACDUTY (2,822 - 256), meaning of the 4 "version" slots beyond their text, and all other record families. Not needed by any current procedure.
* The `FIELDS` blobs of other families were not decoded (privacy/safety: possible credentials, addresses, IP lists).
