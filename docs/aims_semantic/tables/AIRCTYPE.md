# AIRCTYPE  (Table)  - Aircraft-type master (fleet-type definition, raw record image)

## 1. Purpose & business meaning
`TSC.dbo.AIRCTYPE` is the AIMS **aircraft type / fleet sub-type master**. One row = one aircraft type that the operation (or the planning system) knows about: a
real fleet type (A330-200 `332`, A330-300 `333`, A320 `320`, A321 `321`, A321neo `32Q`), a legacy or charter type (B737 variants, L1011, B757, A310, A380...), a
sub-fleet variant (`321C` CEO, `321N` neo, `321L` long-range neo, `332C`/`333C` ...), and the pseudo type `TRN` ("Train SNCF", used to model a train as a deadhead
"flight"). Grain: one row per type; 35 rows; effectively static master data (changed by fleet planners in the AIMS fleet screen, not by operations).

The table is the **physical table behind the view `vvAIRCTYPE`**: it only stores the three key/identity attributes (`ACTYPE`, `IATACODE`, `ACORDER`) as real columns, and
the rest of the record (seats, speeds, weights, crew-rest facilities, weather minima ... = the 118 other attributes exposed by `vvAIRCTYPE`) is stored as one 511-byte binary
image in `DATA_BEGIN_END`. Profiling confirms the layout: for type `332` the image starts `0C00 0000 4001 ...` = SEATS1 = 12, SEATS2 = 0, SEATS3 = 320, exactly the values
`vvAIRCTYPE` returns. **Use `vvAIRCTYPE` for any attribute other than the three keys; never decode `DATA_BEGIN_END` by hand.**

Role in planner-assist: translates the aircraft-type code a user types ("333,332") to the numeric aircraft type id (`ACTYPE`) stored on crew qualifications
(`CREWQUAL.AC`) and on flights (`LEGMAIN.AC`), and gives each type its bit position (`ACORDER`) in certificate/rule bitmaps (`EXPI.MULT_AC`).

## 2. Physical facts
- Database/schema: `TSC.dbo.AIRCTYPE`, user table. Row count at extraction: **35** (confirmed 2026-11-03).
- Primary key: `PK_AIRCTYPE` on `AIRCTYPE_ID` (identity surrogate; NOT equal to `ACTYPE` for all rows, e.g. ACTYPE 27 has AIRCTYPE_ID 12, ACTYPE 12 has 10).
- Unique indexes: `AIRCTYPE_INDEX_0` (`ACTYPE`), `AIRCTYPE_INDEX_1` (`IATACODE`), `AIRCTYPE_INDEX_2` (`ACORDER`) => all three are natural keys; lookups by any of
  them are single-row.
- `ACTYPE` min 1, max 35; 35 distinct `ACORDER` (1..35), 35 distinct `IATACODE`; no leading blanks in `IATACODE`.
- Tiny table: no performance concerns, no partitioning.

## 3. Column dictionary
Type lengths: columns.json reports `nchar` length in bytes; the value below is characters.

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| ACTYPE | smallint | yes (unique) | Numeric aircraft-type id: the foreign key used by crew qualifications and flights | 1..35. `CREWQUAL.AC = ACTYPE`, `LEGMAIN.AC = ACTYPE`. Not the display order | `dbo.R0_GetDraftList.sql:107,426,678`; profiled |
| IATACODE | nchar(4) | yes (unique) | Fleet-type code shown to users and typed in requests ("332", "333", "320", "321", "32Q", "TRN", "W7S8"...). Despite the column name it is the airline's fleet code, not always a true IATA equipment code (`32Q`, `W7S8`, `P295`, `TRN` are in-house) | blank-padded; always `LTRIM/RTRIM` before comparing to parameters | `dbo.R0_GetDraftList.sql:108`, `rpt.list_aircraft_types.sql` |
| ACORDER | tinyint | yes (unique) | Sort order of the type AND its **1-based bit position in aircraft bitmaps** (`EXPI.MULT_AC`: bit `(ACORDER-1)%8` of byte `(ACORDER-1)/8+1`) | 1..35. 332=1, 333=2, 320=8, 321=17, 32Q=19, TRN=20 (the six orders `1,2,8,17,19,20` are hard-coded in R0 / get_crew_certifications) | `dbo.R0_GetDraftList.sql:63-64,356-360`; `rpt.get_crew_certifications.sql:48-52` |
| DATA_BEGIN_END | binary(511) | yes | Raw fixed-length record image of the full aircraft-type record; decoded column by column by `vvAIRCTYPE` (SEATS1.. LVOEXP_5, FUTURE2). Bytes 1-2 = SEATS1, 3-4 = SEATS2, 5-6 = SEATS3 (verified for 332/333) | opaque, always 511 bytes | profiled (hex header of types 332/333); no procedure reads it |
| AIRCTYPE_ID | int identity | no | Surrogate row id, PK | 1..35, identity | `indexes.json` |

## 4. Keys & relationships
- Natural keys: `ACTYPE`, `IATACODE`, `ACORDER` (each unique).
- `AIRCTYPE.ACTYPE` = `CREWQUAL.AC` (N:1: many qualification rows per type). Predicate in code: `JOIN TSC.dbo.AIRCTYPE ct ON ct.ACTYPE = q.AC` (`dbo.R0_GetDraftList.sql:426, 678`).
- `AIRCTYPE.ACTYPE` = `LEGMAIN.AC` (flight leg's aircraft type): `vvAIRCTYPE ac ON ac.ACTYPE = CONVERT(TINYINT, FinalBase.Ac) AND ac.EXCL_FROM_MVT = 0` (`rpt.Get_Detailed_Pairing.sql:310`).
- `AIRCTYPE.ACTYPE` = `AIRTYP` / `AIRTYP2` byte slots of rule tables (`SPEFREC*`): `ACTYPE = CONVERT(tinyint, substring(AIRTYP, idx, 1))` (`rpt.Get_Custom_Rules_*.sql`).
- `AIRCTYPE.ACORDER` <-> bit position in `EXPI.MULT_AC` (certificate applicability by aircraft): see `ACORDER` above. Position in `vvPositions.ID` is the analogous bit position for positions.
- `AIRCTYPE.IATACODE` is how users name a type: `STRING_SPLIT(@AircraftIataCodes, ',')` -> `ACTYPE`.

## 5. Encoding conventions & gotchas
- Three different numbers identify a type: `ACTYPE` (FK used in data), `ACORDER` (bitmap position), `AIRCTYPE_ID` (surrogate). Do **not** mix them. Join to crew/flight data only through `ACTYPE`.
- `LEGMAIN.AC` is converted with `CONVERT(TINYINT, ...)` in rpt.Get_Detailed_Pairing (ids all < 256) while `AIRCTYPE.ACTYPE` is smallint.
- `IATACODE` is blank-padded `nchar`; comparisons with `=` ignore trailing blanks but `LTRIM/RTRIM` is used in the code defensively; always trim before `STRING_SPLIT` matching.
- Only 5 types are in active use in the planner (see vvAIRCTYPE `EXCL_FROM_MVT = 0`): 332, 333, 320, 321, 32Q. All other rows are legacy/sub-fleet/placeholder definitions.
- `TRN` (ACTYPE 17 / ACORDER 20) is a train, not an aircraft; it only appears as a deadhead vehicle and is excluded from movement (`EXCL_FROM_MVT = 1`).
- No soft delete, no active period columns; obsolescence is expressed by `vvAIRCTYPE.INACTIVEDATE` / `EXCL_FROM_MVT`.

## 6. How the planner-assist procedures use it
- `dbo.R0_GetDraftList`: (a) `@AircraftTypes` = `ACTYPE` of the types whose `IATACODE` is in the request list (`:105-108`); (b) the candidate pool joins `CREWQUAL.AC` -> `AIRCTYPE.ACTYPE`
  (`:426`) and the roster query does the same (`:678`) to restrict crew to the requested aircraft type(s) and base. (The expiry check then uses `vvAIRCTYPE.ACORDER`, see that file.)
- `rpt.list_aircraft_types`: `SELECT DISTINCT LTRIM(RTRIM(IATACODE)) FROM TSC.dbo.AIRCTYPE` - the list of valid aircraft codes offered to the MCP client (returns all 35 including legacy ones).
- Other procedures use the decoded view `vvAIRCTYPE`, not this table.

## 7. Typical query patterns
```sql
-- resolve user-supplied type codes to ids
SELECT ACTYPE, LTRIM(RTRIM(IATACODE)) AS IATACODE, ACORDER
FROM TSC.dbo.AIRCTYPE
WHERE LTRIM(RTRIM(IATACODE)) IN ('332','333');

-- crew qualified (currently) on a type: always filter the active period of CREWQUAL
SELECT q.ID, q.CWBASE, q.POS
FROM TSC.dbo.CREWQUAL q
JOIN TSC.dbo.AIRCTYPE ct ON ct.ACTYPE = q.AC
WHERE LTRIM(RTRIM(ct.IATACODE)) = '333'
  AND q.ACTIVBEG <= DATEDIFF(DAY,'1980-01-01',GETDATE()) AND q.ACTIVEND >= DATEDIFF(DAY,'1980-01-01',GETDATE());
```

## 8. Data profile (measured 2026-11-03)
- 35 rows. ACTYPE -> IATACODE (ACORDER): 4->332 (1), 6->333 (2), 27->L15 (3), 12->752 (4), 7->313 (5), 28->W7S8 (6), 10->737 (7), 18->320 (8), 1->380 (9), 2->738 (10), 3->763 (11),
  5->738C (12), 8->737E (13), 9->738T (14), 11->733 (15), 13->734 (16), 14->321 (17), 15->320T (18), 16->32Q (19), 17->TRN (20), 19->321L (21), 20->321C (22), 21->321N (23),
  22->WDH4 (24), 23->W737 (25), 24->W736 (26), 25->W738 (27), 26->W7M8 (28), 29->32N (29), 30->PDH4 (30), 31->7M8 (31), 32->333C (32), 33->P295 (33), 34->332C (34), 35->343C (35).
- Active qualifications on 2026-11-03 (CREWQUAL rows whose period contains today) exist only for 32Q (2,518), 321 (2,518), 320 (2,447), 333 (2,382), 332 (2,381).
- Legs scheduled 2026-10-... (LEGMAIN.DAY 17075-17105, not cancelled) by type: 32Q 904, 332 439, 321 380, 333 38 (no 320 legs in that window).

## 9. Open questions / confidence
- High confidence: key roles of ACTYPE / ACORDER / IATACODE and the DATA_BEGIN_END -> vvAIRCTYPE relationship (verified by hex header).
- `DATA_BEGIN_END` layout beyond the first 6 bytes is inferred only from the view's column order; not verified byte-by-byte.
- Whether `ACORDER` was designed as sort order first and bitmap position second (it is used as bitmap position by every procedure that decodes `EXPI.MULT_AC`): inference from code.
