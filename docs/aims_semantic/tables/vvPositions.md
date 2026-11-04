# vvPositions  (View)  - Crew position (seat/rank) dictionary: CM, PO, ME, SP, DV, DA, AB, SU

## 1. Purpose & business meaning
`TSC.dbo.vvPositions` is the AIMS dictionary of **crew positions** (the seat or rank a crew member operates in on a flight or duty). One row = one position slot.
AIMS reserves a fixed array of 24 slots; only the first 8 are defined, slots 9-24 are empty placeholders (blank CODE and DESC_).

| ID | CODE | Meaning (from DESC_) | Flight deck / cabin (CK_CB) |
|---|---|---|---|
| 1 | CM | Captain | 0 = flight deck |
| 2 | PO | First officer | 0 |
| 3 | ME | Flight engineer | 0 (but see gotcha: `dbo.position_category` classifies it PNC) |
| 4 | SP | Supervising pilot ("SUP PILOT") | 0 |
| 5 | DV | Flight director (cabin senior) | 1 = cabin |
| 6 | DA | Assistant flight director | 1 |
| 7 | AB | Flight attendant | 1 |
| 8 | SU | Supervisor | 1 |

The position ID is the numeric position key used all over AIMS: `ROSTER.POS`, `CREWQUAL.POS`, the 24 per-position complement counters of a pairing (`CRROUTE.CREWNUM`, byte n = number of crew needed in position n),
and the bit index (ID-1) of the position bitmap in `EXPI.POS`. The view is a read-only projection of an AIMS "system table" (no definition is available to us).
Written by AIMS administrators (static master data, practically never changes); read by the planner-assist procedures to translate position codes (`CM`, `PO`...) typed by the user into numeric IDs and back.

## 2. Physical facts
- Database/schema: `TSC.dbo.vvPositions`, type **VIEW** (definition not retrievable: `view_defs.json` has `def = null`). No row count in rowcounts.json; measured: **24 rows**, `ID` distinct = 24 (unique, 1..24).
- No primary key or index information is available for views. Tiny table: always safe to scan.
- Fixed-width `nchar` columns are blank-padded: always `LTRIM(RTRIM(...))` before comparing (the procedures do this).

## 3. Column dictionary
Character widths below are `len/2` from columns.json (the metadata length is in bytes).

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| ID | smallint | Y | Position number = primary key of the position | 1..24; 1-8 defined (see table above), 9-24 empty slots | profiled; `dbo.position_category.sql` ("Position_Id is TSC.dbo.vvPositions.ID (and ROSTER.POS / CREWQUAL.POS)") |
| CODE | nchar(3) | Y | Two-letter position code used in the UI and in the planner API (`@PositionCodes`) | `CM`,`PO`,`ME`,`SP`,`DV`,`DA`,`AB`,`SU`; blank for slots 9-24. Blank-padded | profiled; `R0_GetDraftList.sql` (lines 110-113), `rpt.list_crew_positions.sql` |
| CODE3 | nchar(1) | Y | Unknown - not used by any procedure. Blank in all 24 rows (probably a legacy 3-letter-code extension) | blank | profiled |
| CODE4 | nchar(1) | Y | Unknown - not used by any procedure. Blank in all 24 rows | blank | profiled |
| DESC_ | nchar(16) | Y | Human description. The 16 characters are **two packed fields**: characters 1-13 = position name (e.g. `CAPTAIN`, `FIRST OFFICER`, `F. ENGINEER`), characters 14-16 = an alternative 3-letter code (`CMD`,`POF`,`MEC`,`SP`,`DIR`,`DVA`,`AB`,`SU`) | Blank-padded; e.g. `CAPTAIN      CMD`, `F. DIRECTOR   DIR`. The alt code is part of the string, there is no separate column for it | profiled (`SUBSTRING(DESC_,1,13)` / `(14,3)`); consumed whole by `rpt.get_crew_certifications.sql`, `R0_GetDraftList.sql` (Position_List) |
| ALTRN | int | Y | Unknown "alternate" attribute; non-zero only for 5 positions. Probably an alternate-position/rank code (inference from name). Not used by any procedure | CM=2, DV=96 (0x60), DA=32 (0x20), AB=48 (0x30), SU=80 (0x50), others 0 | profiled |
| CK_CB | tinyint | Y | Cockpit/Cabin flag: 0 = flight-deck position, 1 = cabin position (inference from name CK_CB = "cockpit / cabin" and from the data) | 0 for IDs 1-4 (CM,PO,ME,SP); 1 for IDs 5-24 | profiled (naming inference for the label) |
| RANK | tinyint | Y | Display/sort order of the position | equals ID in all 24 rows (1..24) | profiled |
| FUTURE | varbinary(96) | Y | Reserved/unused area of the AIMS record | 96 bytes, all zero | profiled; "unknown - not used by any procedure" |

## 4. Keys & relationships
- Natural key: `ID` (1:1 with `CODE` for the 8 defined rows).
- `ROSTER.POS` = `vvPositions.ID` (N:1). Used in `R0_GetDraftList.sql` line 679 `INNER JOIN TSC.dbo.vvPositions AS vp ON vp.ID = q.POS`.
- `CREWQUAL.POS` = `vvPositions.ID` (N:1). Same join (R0 line 427, `rpt.get_crew_qualifications.sql` line 126: `inner join TSC.dbo.vvPositions p on p.id = Cq.POS`, `rpt.get_crew_certifications.sql` line 108). Measured: 0 `CREWQUAL` rows without a matching position.
- `dbo.position_category.Position_Id` = `vvPositions.ID` (planner-owned table classifying each position PNT/PNC).
- `CRROUTE.CREWNUM` byte n = number of crew of position n required by a pairing (`rpt.Get_Detailed_Pairing.sql` ~line 105-123: unpivots 24 bytes into `(POS_ID, POS_QTY)` and joins `vvPositions p ON p.ID = v.POS_ID`).
- `EXPI.POS` (binary(3)) is a bitmap: bit (ID-1) set = the expiry applies to that position. Decoded by `(CONVERT(tinyint, SUBSTRING(CONVERT(binary(32), E.POS), (P.ID - 1) / 8 + 1, 1)) & POWER(2, (P.ID - 1) % 8)) > 0` (`R0_GetDraftList.sql` lines 364-372).
- `SPEFREC3.POS` (rule "certain flights for certain crews") and `SPEFREC2.POS1`/`POS2` (rule "schedule with / with not") reference `vvPositions.ID` (`rpt.Get_Custom_Rules_Schedule_WithWithNot.sql` lines 115-116: `left JOIN vvPositions P1 ON E.POS1 = P1.ID`). The SPEFREC3 rule table additionally uses two pseudo-values **25 = 'CM | PO'** and **26 = 'DV | AB'** that do NOT exist in this view (`rpt.Get_Custom_Rules_CertainFlightsCrew.sql` lines 66-68).

## 5. Encoding conventions & gotchas
- Blank padding on `CODE` and `DESC_` (compare with `LTRIM(RTRIM())`); `rpt.list_crew_positions` filters `Code != ''` to hide empty slots 9-24.
- **Position category (PNT/PNC) is NOT derived from this view by the planner.** It uses `dbo.position_category`: IDs 1,2,4 = PNT (pilots), everything else PNC. AIMS itself flags ID 3 (ME, flight engineer) as cockpit (`CK_CB = 0`) whereas `position_category.sql` has it as PNC "to be confirmed by the business". No crew is currently qualified on ME in an active period (0 active rows).
- **`DESC_` carries the alternative code at its end** (see column dictionary). `R0_GetDraftList` builds `#CertRules.Position_List` from `RTRIM(LTRIM(P.DESC_))` and later tests `CHARINDEX(RTRIM(LTRIM(cp.Crew_Position_Code)), RTRIM(LTRIM(cr.Position_List))) > 0` with `Crew_Position_Code = vvPositions.CODE`. Measured `CHARINDEX(CODE, DESC_)` is > 0 for CM, PO, ME, SP, AB, SU (the `CODE` is found inside the alt code, e.g. `CM` inside `CMD`) but **= 0 for DV and DA** (`F. DIRECTOR   DIR` does not contain `DV`; `AF. DIRECTOR  DVA` does not contain `DA`). So the R0 expired-certificate check can never match DV/DA crew. This is currently harmless because R0 is used for pilots, but it is a latent defect (inference from measured CHARINDEX values).
- Position bitmaps in `EXPI.POS` are read only for IDs 1..10 by the planner (`P.ID BETWEEN 1 AND 10`).
- Positions 9-24 exist only as placeholders; never join expecting meaning for them.

## 6. How the planner-assist procedures use it
- `dbo.R0_GetDraftList`: (a) resolves `@PositionCodes` (comma list, e.g. `'CM,PO'`) to IDs: `SELECT ID FROM TSC.dbo.vvPositions WHERE LTRIM(RTRIM(CODE)) IN (...)`; (b) joins `CREWQUAL.POS` to get `Crew_Position_Code` (`vp.CODE`) for each candidate; (c) builds `Position_List` of each certificate rule from the `EXPI.POS` bitmap (IDs 1-10, `DESC_`), then matches the candidate's `CODE` against it (see gotcha above).
- `rpt.list_crew_positions`: `SELECT DISTINCT LTRIM(RTRIM(CODE)) FROM vvPositions WHERE Code != ''` - the list of valid position codes offered to the LLM/MCP client.
- `rpt.get_crew_qualifications`: `p.DESC_ AS Position` (the packed 16-char description is returned as is).
- `rpt.get_crew_certifications`: builds the position list of each certificate from the `EXPI.POS` bitmap using `P.DESC_`, and matches `CHARINDEX(RTRIM(LTRIM(p.DESC_)), temp.Position_List)` - here both sides come from `DESC_`, so DV/DA do match.
- `rpt.Get_Detailed_Pairing`: expands `CRROUTE.CREWNUM` into one row per required crew member and labels it with `vvPositions`.
- `rpt.Get_Custom_Rules_*`: translate `SPEFREC2.POS1/POS2` and `SPEFREC3.POS` ids into `CODE`.
- R3/R4/R5/CalculateCrewFTC do not read the view directly; they classify `ROSTER.POS` via `dbo.position_category`.

## 7. Typical query patterns
```sql
-- valid position codes
SELECT ID, LTRIM(RTRIM(CODE)) AS Code, LTRIM(RTRIM(DESC_)) AS Description, CK_CB
FROM TSC.dbo.vvPositions
WHERE LTRIM(RTRIM(CODE)) <> N''
ORDER BY RANK;

-- decode the position of a qualification row
SELECT q.ID, LTRIM(RTRIM(p.CODE)) AS Position_Code
FROM TSC.dbo.CREWQUAL AS q
JOIN TSC.dbo.vvPositions AS p ON p.ID = q.POS
WHERE q.ID = @crew_id
  AND DATEDIFF(DAY, '1980-01-01', GETDATE()) BETWEEN q.ACTIVBEG AND q.ACTIVEND;

-- position code -> id
SELECT ID FROM TSC.dbo.vvPositions WHERE LTRIM(RTRIM(CODE)) = N'CM';
```

## 8. Data profile (measured 2026-11-03)
- 24 rows, IDs 1..24 unique; 8 populated (CM, PO, ME, SP, DV, DA, AB, SU), 16 blank.
- `CK_CB`: 0 for IDs 1-4, 1 for IDs 5-24. `RANK` = `ID`. `CODE3`, `CODE4` blank everywhere; `FUTURE` all zero bytes.
- Usage in `CREWQUAL` (all periods, 131,018 rows): POS 1 = 7,900; 2 = 8,773; 3 = 212; 4 = 6; 5 = 28,599; 6 = 13,561; 7 = 71,595; 8 = 372. Active today: 1 = 904; 2 = 1,021; 5 = 1,709; 7 = 8,452; 8 = 160; 3, 4, 6 = 0.
- Number of `EXPI` expiry types that include the position in their `POS` bitmap: CM 159, PO 152, ME 44, SP 36, DV 31, DA 18, AB 31, SU 25 (IDs 9, 10: 4 each).

## 9. Open questions / confidence
- High confidence: ID/CODE/DESC_ semantics, `RANK` = order, `CK_CB` as cockpit/cabin (values consistent; the name expansion is an inference).
- Medium: the 13+3 packing of `DESC_` is observed in all 8 rows; the reason for the alt code is unknown (probably AIMS legacy display field).
- Unknown: meaning of `ALTRN` values (2, 96, 32, 48, 80) and of `CODE3`/`CODE4`.
- Business question already raised in the repo: whether ME (flight engineer) should be PNT; AIMS marks it cockpit.
