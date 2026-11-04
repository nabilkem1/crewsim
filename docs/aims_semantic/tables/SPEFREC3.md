# SPEFREC3  (Table)  - Custom "special rule" family 3: "Certain flights for certain crews" (header row of each rule)

## 1. Purpose & business meaning
`SPEFREC3` (KIND = 3) is the second special-rule screen used by planner-assist ("**Certain flights for certain crews**"; see SPEFREC2.md for the family overview). A row is the header of one rule that restricts **individual crew members (not pairs)** to or from a class of flights:

> *crew members in position `POS` who hold one of the categories in `CATEG` (or whose nationality is in `NATIONALITIES` when `NAT_CATEG = 1`) **are not to be scheduled** (`SCHE = 2`) / **are to be scheduled only** (`SCHE = 1`) on flights that satisfy the condition `SEL` (+ list data in SPEFRECDATA KIND = 3), valid `FMDATE`..`TODATE`; severity `AUTOHARD`; message `MSG`.*

Typical uses (from the live data): unqualified cabin/flight crew ("PNC NON QUALIFIE", "PNT NON QUALIFIE") may not fly at all (`SEL = 3` any flight); crew over 60 may not operate flights to certain countries (`SEL = 7`);
"cannot operate on this AC tail" (`SEL = 12`, list of registrations); "JUMPSEAT NOT EQUIPED"; "Must be ambassador".
Row grain: one rule slot (RULE_, PLANDAYTODAY): rule numbers 0..99 for **PLANDAYTODAY = 1 (Plan)** and **2 (Day-to-Day)**. Most slots are empty templates. Writer: AIMS special-rules screen; readers: `rpt.Get_Custom_Rules_CertainFlightsCrew` -> `dbo.R1_Get_Violations_CertainFlightsCrew`.

## 2. Physical facts
* `TSC.dbo.SPEFREC3`, base table, **199 rows** (2026-11-03): PLANDAYTODAY 1 -> 100 rows (RULE_ 0..99), PLANDAYTODAY 2 -> 99 rows (RULE_ 1..99).
* PK/unique clustered index `SPEFREC3_INDEX_0` on (RULE_, PLANDAYTODAY). No other indexes. No identity/audit/soft delete (ACTIVE = 0 is "off").
* (The metadata extract `columns.json` reports `nchar` lengths in **bytes**; the real declared lengths in characters are half of that and are used below.)
* 184 of 199 rows are untouched templates (SEL = 4, SCHE = 1, POS = 1, NULL SEL2/BLKTIME/INCEXCL/NAT_CATEG/DOMINTCHK); 15 rows were edited by an administrator.

## 3. Column dictionary
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| RULE_ | smallint | N | Rule number. | 0..99. | rpt.Get_Custom_Rules_CertainFlightsCrew.sql:59 |
| PLANDAYTODAY | tinyint | N | Rule set. | 1 = Plan, 2 = Day-to-Day. The rules procedure hard-codes `@Filter_PlanDayToDay = 2` and labels `Rule_Type` from it. | ...CertainFlightsCrew.sql:7,60,141 |
| KIND | tinyint | Y | Family discriminator; always 3 here; joins `SPEFRECDATA.KIND = 3`. | 3 = Certain-Flights-For-Certain-Crews. (The label CASE `E.Kind = 2 -> 'Schedule-With-&-With-Not' ELSE 'Certain-Flights...'` therefore always yields the latter.) | profiled (199/199); ...CertainFlightsCrew.sql:62,@Filter_Kind=3 |
| ACTIVE | tinyint | Y | Rule switch. | 0 = off; **1 = on** (the procedure filter is `ACTIVE IN (1,2)`; only value 1 occurs among active rows: 3 per set). | ...CertainFlightsCrew.sql:63,144; profiled |
| SEL | tinyint | Y | **Flight condition** of the rule (kind of flights). | Same code list as SPEFREC2.SEL: 1 International; 2 Domestic; 3 Any kind of flights; 4 flights with crew-route categories; 5 via airports of categories; 6 city pairs of categories; 7 flights to country categories; 8 flight types; 9 AC types; 10 overnight; 11 to/from bases; 12 aircraft registrations; 13 carriers; 14 charterers; 15 flight categories; 16 night stops at stations; 17 night stops at countries; 18 aircraft categories; 19 via airports; 20 aircraft additional category; 21 via airport additional category; 22 via countries additional category; 23 AC versions. Observed: 4 (180 template rows), 3 (10), 7 (3), 12 (6). | ...CertainFlightsCrew.sql:71-97; profiled |
| SCHE | tinyint | Y | Rule modality. | **1 = "Are to be scheduled only"** (crew may fly *only* flights matching SEL), **other (2) = "Are not to be scheduled"** (crew must not fly flights matching SEL). Observed 1 = 186 (mostly templates), 2 = 13. | ...CertainFlightsCrew.sql:64; R1 5.1/5.2 |
| POS | tinyint | Y | Crew position the rule applies to (single position). | `vvPositions.ID`: 1 CM, 2 PO, 3 ME, ...; **25 = "CM \| PO"**, **26 = "DV \| AB"** (pseudo positions hard-coded). Observed 1 (183), 2 (6), 3 (2), 25 (2), 26 (6). | ...CertainFlightsCrew.sql:66-69 |
| CATEG | binary(32) | Y | Crew categories the rule targets (any of them), when `NAT_CATEG <> 1`. | 256-bit bitmap, same layout as SPEFREC2.CATEG1: bytes 1-2 header, **bytes 3..32 = crew category n (1..240) at byte `3+(n-1)/8`, bit `(n-1)%8`**; names from `CREWCAT`. Active rules: cat 95 "PNC NON QUALIFIE" (rule 2), cat 96 "PNT NON QUALIFIE" (rules 5, 6). | ...CertainFlightsCrew.sql:127-139; profiled |
| VICEVER | tinyint | Y | "Vice-Versa" flag. | 1 -> printed 'Vice-Versa' (196 rows), 0/2 -> '.'. Meaning undocumented; **not evaluated by R1** (R1 comment: all active rules carry it). | ...CertainFlightsCrew.sql:110; R1 line 507-510 |
| AUTOHARD | tinyint | Y | Authority/severity. | **1 = Company, 2 = Government**, 0/other = blank. Exposed as `Rule_Severity`. Active rules: all three (2, 5, 6) are Company in the Day-to-Day set; in the Plan set rule 5 has 0 (blank). | ...CertainFlightsCrew.sql:122 |
| FMDATE | smallint | Y | Valid from (inclusive), AIMS day number (days since 1980-01-01). | 0 = from the beginning; non-zero: 8347 (2002-11-08), 9497 (2006-01-01), 13148 (2015-12-31), 13634 (2017-04-30), 16162 (2024-04-01). | ...CertainFlightsCrew.sql:119 |
| TODATE | smallint | Y | Valid to (inclusive). | 32767 (= 2069-09-17) = open ended (198 rows); 0 on one template. | ...CertainFlightsCrew.sql:120 |
| PENALTY | smallint | Y | Presumably an optimiser penalty. | 0 everywhere. | unknown - not used |
| DEPARR | tinyint | Y | Naming inference: departure/arrival selector for the BETWEEN time window. | 0 everywhere. | unknown - not used by any procedure |
| BETWEENFROM | smallint | Y | Naming inference: start of a time-of-day window in which the rule applies. | 0 everywhere. | unknown - not used |
| BETWEENTO | smallint | Y | Naming inference: end of that window. | 0 everywhere. | unknown - not used |
| OPENDATES | tinyint | Y | "Open dates" flag (undocumented). R1 skips the validity test when it is 'Yes'. | 0 everywhere. | R1 line 323-327; ...CertainFlightsCrew.sql:117 |
| CHECKPAX | tinyint | Y | "Validate deadheading sectors": also apply the rule to crew travelling as passengers. | 0/1 (1 only on inactive rule 7 of the plan set). Printed 'Yes'/'No'; **R1 warns that it does not evaluate it**. R1 loads schedules with `@Include_Deadhead = 0`. | ...CertainFlightsCrew.sql:112; R1 line 517-519 |
| CARRPAXCHECK | tinyint | Y | Which carriers the deadhead check covers. | 0 ALL, 1 Other Carrier, 2 Own Carrier, 3 All Flight, 4 Other Airline, else Ground Transportation. 0 everywhere. Not evaluated. | ...CertainFlightsCrew.sql:113 |
| MSGCOLR | int | Y | UI colour of the message (Windows COLORREF-like). | 0 or e.g. 221, 656847, 2031792, 2490549, 11011456, 14028559. | profiled; not used |
| MSG | nchar(60) | Y | Violation message (French/English, space padded, accents). | e.g. "Illégal, non qualifié - NE PEUT PAS VOLER". Returned as `Violation_Message` (R1 temp table declares NVARCHAR(300)). | ...CertainFlightsCrew.sql:123; R1 line 79,342 |
| OBSRVR | tinyint | Y | 1 = rule does not apply to crew observers. | 0/1 (1 on rules 7, 9 inactive). Label `Does_Not_Apply_To_Crew_Observers`. **Not evaluated** by R1 (warning if Yes). | ...CertainFlightsCrew.sql:111; R1 517 |
| INOUTPAXCHK | tinyint | Y | Deadhead check direction. | 0 ALL, 1 Inbound, else Outbound. Not evaluated. | ...CertainFlightsCrew.sql:116 |
| LAYTRANSPAXCHK | tinyint | Y | Deadhead check: layover vs turnaround. | 0 ALL, 1 Layover, else Turnaround. Not evaluated. | ...CertainFlightsCrew.sql:115 |
| NAT_CATEG | tinyint | Y | Crew filter selector. | **1 = filter by nationality** (`NATIONALITIES`), otherwise by crew category (`CATEG`). Printed as `Crew_Filters`. 0 on all edited rows (NULL on templates). | ...CertainFlightsCrew.sql:99; R1 368-375 |
| NATIONALITIES | nchar(50) | Y | List of nationality codes for nationality rules. | Concatenated **2-character codes** (25 max in nchar(50)), decoded as `SUBSTRING(NATIONALITIES, n, 2)` for odd n (the procedure joins them with `'|'`). The codes are `vvCountries.Country` (compared with the drafted crew's nationality in R1). Blank in all rows today. | ...CertainFlightsCrew.sql:101-108; R1 190-203 |
| INCEXCL | tinyint | Y | Naming inference: include/exclude for the nationality/category list. | 0 on edited rows. Not used. | unknown - not used |
| CATEG2 | smallint | Y | Unknown. | 0 on edited rows. | unknown - not used |
| DOMINTCHK | smallint | Y | Deadhead check: domestic/international. | 0 ALL, 1 Domestic, else International. Printed as `Flights`. 0 on edited rows. Not evaluated. | ...CertainFlightsCrew.sql:114 |
| BLKTIME | smallint | Y | Unknown (naming: block time). | 0 on edited rows. | unknown - not used |
| SEL2 | tinyint | Y | Unknown second selector; newer column. | 3 on the 15 edited rows, NULL on templates. | unknown - not used |

## 4. Keys & relationships
* Natural key = (RULE_, PLANDAYTODAY) (PK).
* **Detail rows** in `SPEFRECDATA` with `KIND = 3`: `SPEFRECDATA.RULE_ = SPEFREC3.RULE_ AND SPEFRECDATA.PLANDAYTODAY = SPEFREC3.PLANDAYTODAY AND SPEFRECDATA.KIND = 3` (1:N, 1 or 48 rows; 0 orphans). In code: `sub.[KIND] = @Filter_Kind AND sub.RULE_ = TM.Rule_Nbr AND sub.PLANDAYTODAY = @Filter_PlanDayToDay` (rpt.Get_Custom_Rules_CertainFlightsCrew.sql:155-349).
* `POS` -> `vvPositions.ID` (with 25/26 pseudo codes, `(SELECT [CODE] FROM vvPositions WHERE ID = E.POS)`).
* `CATEG` bits -> `CREWCAT.CREWCAT` (`INNER JOIN TSC.dbo.CREWCAT C ON C.CREWCAT = n.N`); crew member categories come from `CREWCATEG (ID, CREWCATIDX, ACTIVEBEG, ACTIVEEND)`.
* `NATIONALITIES` codes -> `vvCountries.Country` (2 letters); drafted crew nationality = `vvCountries.Country` for `vvCREWDB.NATCOD = vvCountries.UNCODE` (R1 lines 196-203).

## 5. Encoding conventions & gotchas
* Day numbers for FMDATE/TODATE (days since 1980-01-01, inclusive). **The rules procedure does not filter by date**; R1 applies `Rule_Effective_From <= @pPAIRING_DATE <= Rule_Effective_To` itself (R1-4), unless `OPEN_DATES = 'Yes'`. Note `TODATE = 0` on a template row would read as "ended 1980-01-01" - such rows are inactive.
* **ACTIVE filter is `IN (1,2)`** in the rules procedure and `Active = 'Yes'` in R1; today only value 1 occurs for the live rules.
* **Labels used as logic**: R1 relies on the text labels produced by the rules procedure (`'Yes'`, `'Are not to be scheduled'`, `'Are to be scheduled only'`); changing a label silently disables rules (R1-10 adds a warning).
* **Position matching** is by `CHARINDEX(crew_position, rule.Position) > 0`, so pseudo-position 25 matches both CM and PO crews, 26 matches DV/AB.
* **Same bitmap layout as SPEFREC2**: category numbers start at byte 3. Reading from byte 1 is wrong.
* Not evaluated by R1 (R1 only warns): `OBSRVR`, `CHECKPAX`, `OPEN_DATES`, `CARRPAXCHECK`, `DOMINTCHK` (Flights), `LAYTRANSPAXCHK`, `INOUTPAXCHK`; `VICEVER` silently ignored. Unsupported flight kinds (> 22, i.e. 23) produce an "unsupported rule kind" warning.
* `Rule_Severity`: blank when AUTOHARD = 0 (e.g. plan rule 5).
* Messages are accent-bearing `nchar(60)`; `RTRIM` before display.
* For "are to be scheduled only" rules (SCHE = 1) R1 reports a violation when the crew matches the category/nationality filter **and the flight condition is NOT met** (the 'ALWAYS SCHEDULE VIOLATION' branch).

## 6. How the planner-assist procedures use it
* **`rpt.Get_Custom_Rules_CertainFlightsCrew`** (no parameters; hard-coded `PLANDAYTODAY = 2`, `ACTIVE IN (1,2)`): decodes each rule to text columns (Position, Rule_Condition from SEL, Crew_Filters, Crew_Categories_List, NATIONALITIES, Rule_Action, Rule_Severity, Rule_Effective_From/To, deadhead-check options, Violation_Message) and attaches `Subconditions_Raw_JSON` from SPEFRECDATA (kind 3).
* **`dbo.R1_Get_Violations_CertainFlightsCrew(@Crew_Position_To_Draft, @Crew_Id_To_Draft, @pPAIRING_ID, @pPAIRING_DATE)`**: drafts the crew member into the open slot of the pairing, then for each *drafted* crew row x active rule where `CHARINDEX(crew position, rule.Position) > 0` and the rule is valid at the pairing date:
  * *crew match* (`Is_Category_Matched`): by nationality (`Crew_Filters = 'Nationality'`: crew's 2-letter nationality is in `NATIONALITIES`) or by intersection of the crew's profile categories (active today - `CREWCATEG.ACTIVEEND > today`) with `Crew_Categories_List`;
  * *flight match* (`Is_SubCondition_Matched`): evaluates `Kind_Id` (SEL) against each leg using the JSON from SPEFRECDATA;
  * **'DO NOT SCHEDULE VIOLATION'** when `Rule_Action = 'Are not to be scheduled'` AND crew matched AND flight matched; **'ALWAYS SCHEDULE VIOLATION'** when `Rule_Action = 'Are to be scheduled only'` AND crew matched AND flight NOT matched. Severity = AUTOHARD (Company/Government), text = MSG.
* Not used by R2 (family 2), R3-R5.

## 7. Typical query patterns
```sql
-- 1. All active Day-to-Day "certain flights for certain crews" rules, decoded
SELECT e.RULE_, CASE WHEN e.SCHE = 1 THEN 'Are to be scheduled only' ELSE 'Are not to be scheduled' END AS Action,
       CASE e.POS WHEN 25 THEN 'CM | PO' WHEN 26 THEN 'DV | AB' ELSE p.CODE END AS Position,
       e.SEL AS FlightConditionId, CASE e.NAT_CATEG WHEN 1 THEN 'Nationality' ELSE 'Category' END AS CrewFilter,
       CASE e.AUTOHARD WHEN 1 THEN 'Company' WHEN 2 THEN 'Government' ELSE '' END AS Authority,
       DATEADD(DAY, e.FMDATE, '1980-01-01') AS ValidFrom, DATEADD(DAY, e.TODATE, '1980-01-01') AS ValidTo, RTRIM(e.MSG) AS Message
FROM TSC.dbo.SPEFREC3 e LEFT JOIN TSC.dbo.vvPositions p ON p.ID = e.POS
WHERE e.PLANDAYTODAY = 2 AND e.ACTIVE IN (1,2) ORDER BY e.RULE_;

-- 2. Crew categories targeted by rule 5 (bytes 3..32 of CATEG)
SELECT c.CREWCAT, RTRIM(c.DESC_) AS Category
FROM TSC.dbo.SPEFREC3 e JOIN TSC.dbo.CREWCAT c ON c.CREWCAT BETWEEN 1 AND 240
WHERE e.RULE_ = 5 AND e.PLANDAYTODAY = 2
  AND (CONVERT(tinyint, SUBSTRING(CONVERT(binary(32), e.CATEG), 3 + (c.CREWCAT-1)/8, 1)) / POWER(2,(c.CREWCAT-1)%8)) % 2 = 1;

-- 3. Edited (non-template) rules of both sets
SELECT PLANDAYTODAY, RULE_, ACTIVE, SEL, SCHE, POS, AUTOHARD, RTRIM(MSG) AS Msg FROM TSC.dbo.SPEFREC3 WHERE SEL2 IS NOT NULL ORDER BY PLANDAYTODAY, RULE_;
```

## 8. Data profile (measured 2026-11-03)
* 199 rows (Plan 100 / Day-to-Day 99). KIND = 3 on all. ACTIVE: Plan -> 97 off / 3 on; Day-to-Day -> 96 off / 3 on. **Active rules (same in both sets): rules 2, 5, 6.**
* Active rules: **2** - POS 26 ("DV \| AB" cabin positions), SEL 3 (any flight), SCHE 2 (not to be scheduled), CATEG = "PNC NON QUALIFIE", valid from 2017-04-30, Company, "ILLÉGAL / NON QUALIFIÉ - NE PEUT PAS VOLER";
  **5** - POS 1 (CM), SEL 3, SCHE 2, CATEG = "PNT NON QUALIFIE", authority Company (Day-to-Day) / blank (Plan), "Illégal, non qualifié - NE PEUT PAS VOLER"; **6** - POS 2 (PO), SEL 3, SCHE 2, CATEG = "PNT NON QUALIFIE", Company, "... - Sauf CADET j/s" (except cadets on jump-seat).
  All three: nationality filter off (NAT_CATEG 0), VICEVER 1, OBSRVR 0.
* Inactive but edited rules (both sets): 1 SEL 12 POS 25 "Can't Operate on this AC TAIL" (5 registrations in SPEFRECDATA), 3 SEL 7 POS 3 "VIOLATION!!!! MECH OVER 60 YEARS OLD (IGNORE IF DH)" (from 2002-11-08, country category 3 of GENCAT type 4), 4 (plan only) SEL 7 POS 1 "CMD et POF OVER 60 YEARS OLD" (from 2006-01-01), 7 SEL 12 POS 26 "JUMPSEAT NOT EQUIPED" (from 2024-04-01, OBSRVR 1, 9 registrations),
  9 SEL 12 POS 26 SCHE 1 "Must be ambassador" (VICEVER 2), 10 / 11 SEL 3 POS 2 SCHE 1 "CADETS UNDER TRAINING - verification necessaire" / "CADETS - Doit voler avec instructeur ET safety pilot".
* SEL on all rows: 4 = 180 (templates), 3 = 10, 7 = 3, 12 = 6. SCHE 1 = 186, 2 = 13. POS 1 = 183, 2 = 6, 3 = 2, 25 = 2, 26 = 6. PENALTY/OPENDATES/DEPARR/BETWEENFROM/BETWEENTO/CARRPAXCHECK = 0; NATIONALITIES blank on all rows.
* Practical consequence: today the only live rules of this family say "crew flagged *NON QUALIFIE* cannot fly anything"; they depend on the crew-category assignment (`CREWCATEG`), not on flight attributes.

## 9. Open questions / confidence
* High confidence on structure, SEL/SCHE/AUTOHARD/POS decoding, bitmap layout and R1 evaluation semantics (code + data).
* Unknown/unused: VICEVER semantics, INCEXCL, CATEG2, BLKTIME, SEL2, DEPARR, BETWEENFROM/TO, PENALTY, `ACTIVE = 2` (never present). BETWEEN* / DEPARR are only guessed from names.
* DV / AB are probably cabin positions (flight-attendant roles: the matching live rule targets "PNC", cabin crew, and R1 text says 'DV | AB'); the code never defines them (inference).
* The Plan (1) vs Day-to-Day (2) mapping is inferred from labels; R1 only evaluates set 2.
