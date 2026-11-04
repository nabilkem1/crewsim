# SPEFREC2  (Table)  - Custom "special rule" family 2: "Schedule WITH / WITH-NOT" crew-pairing rules (header row of each rule)

## 1. Purpose & business meaning
AIMS has a **"special rules" engine** (company/government-specific scheduling restrictions that the standard legality engine does not know). Rules are grouped in families, each stored in its own table: `SPEFREC1` (crew complement min/max), **`SPEFREC2` (this table, KIND = 2)**,
`SPEFREC3` (KIND = 3, "certain flights for certain crews"), `SPEFREC4N`, `SPEFREC5`, `SPEFREC6`. The variable-length list parts of the rules (bases, registrations, carriers, charterers, bit-masks of categories) are in **`SPEFRECDATA`**, keyed by (RULE_, KIND, PLANDAYTODAY).

**SPEFREC2 = "Schedule With / With-Not" (AIMS screen: *Schedule - with & with-not*).** One row is the *header* of one rule that constrains **which two crew members may / must fly together on the same flight leg**:

> *a crew member in position `POS1` who holds one of the crew categories in `CATEG1` ... [must / must not] be scheduled **with** a crew member in position `POS2` who holds one of the categories in `CATEG2` ... on flights matching the condition `SEL` (+ the lists in SPEFRECDATA) ... between `FMDATE` and `TODATE`.*

* `SCHE = 1` -> **"Always Schedule"** (*with*): a first-side crew member must be accompanied by a qualifying second-side crew member (e.g. a junior FO "en LI-RC" must fly with a check pilot).
* `SCHE = 2` -> **"Do not Schedule"** (*with-not*): the two categories must not be on the same leg (e.g. junior captain + junior first officer).
* `AUTOHARD` gives the **authority/severity**: 1 = Company (soft; the planner may override), 2 = Government (hard).

Row grain: one rule slot = (RULE_, PLANDAYTODAY): rule numbers 0..99, each existing twice - **PLANDAYTODAY = 1 for the Planning (bid/roster-building) rule set and 2 for the Day-to-Day (operations) rule set**.
Most slots are empty templates (inactive). Writers: the AIMS "Special rules" setup screen. Readers: `rpt.Get_Custom_Rules_Schedule_WithWithNot` (decodes it), then `dbo.R2_Get_Violations_Schedule_WithWithNot` (evaluates it on a drafted pairing).

## 2. Physical facts
* `TSC.dbo.SPEFREC2`, base table, **199 rows** (2026-11-03): PLANDAYTODAY 1 -> 100 rows (RULE_ 0..99), PLANDAYTODAY 2 -> 99 rows (RULE_ 1..99; no rule 0).
* PK/unique clustered index `SPEFREC2_INDEX_0` on (RULE_, PLANDAYTODAY). No other index (not needed: 199 rows). No identity, no audit, no soft-delete (ACTIVE = 0 is the "off" switch).
* (The metadata extract `columns.json` reports `nchar` lengths in **bytes**; the real declared lengths in characters are half of that and are used below.)
* The first 100 slots of a rule number are pre-allocated by AIMS: 163 of 199 rows are untouched templates (SEL2/BLKHRS NULL).

## 3. Column dictionary
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| RULE_ | smallint | N | Rule number (slot), part of the rule's identity. | 0..99 (the trailing underscore is because RULE is a reserved word). Number is shown to planners as "Rule n". | indexes.json; rpt.Get_Custom_Rules_Schedule_WithWithNot.sql:55 (`Rule_Nbr`) |
| PLANDAYTODAY | tinyint | N | Which rule set the row belongs to. | **1 = Plan** (planning period), **2 = Day-to-Day**. Both R2 and the rpt procedure query 2. 1 is inferred as "Plan" from the `ELSE 'Plan'` branch of the label CASE. | rpt.Get_Custom_Rules_Schedule_WithWithNot.sql:7,56,143; R2 line 66-69 (`@Filter_PlanDayToDay = 2`) |
| KIND | tinyint | Y | Rule family discriminator, = 2 for every row of this table. Mirrors `SPEFRECDATA.KIND` (the join key to the list data). | 2 = "Schedule-With-&-With-Not". (1 = SPEFREC1 crew complement, 3 = SPEFREC3, 4 = SPEFREC4N, 5/6 = SPEFREC5.) | profiled (199/199 = 2); rpt.Get_Custom_Rules_Schedule_WithWithNot.sql:9-10,57 |
| ACTIVE | tinyint | Y | Rule switch. | **0 = inactive; 1 and 2 = active** (the procedures test `ACTIVE <> 0`/`!= 0` and label 'Yes'). Observed: 1 <-> AUTOHARD = 1, 2 <-> AUTOHARD = 2 in every row but one, so 1/2 are probably "active-company / active-government" - this distinction itself is never evaluated. | rpt...WithWithNot.sql:58,144; profiled |
| SCHE | tinyint | Y | The rule's modality. | **1 = Always Schedule (with)**, any other value (observed 2) = **Do not Schedule (with-not)**. | rpt...WithWithNot.sql:59; R2 4.4/4.5; profiled |
| POS1 | tinyint | Y | Crew position of the **first** side of the pair. | `vvPositions.ID`: 1 `CM`, 2 `PO`, 3 `ME`, 4 `SP`, 5 `DV`, 6 `DA`, 7 `AB`, 8 `SU` (ids 9-24 unnamed); **25 = pseudo-position "CM \| PO"** (either pilot), **26 = "DV \| AB"** (hard-coded in the procedures). 0 = none (rule-0 template). Observed: 1, 2, 3, 25. | rpt...WithWithNot.sql:62-65 |
| CATEG1 | binary(32) | Y | Set of **crew categories** the first-side crew must hold (any of them). | 256-bit bitmap: bytes 1-2 = special header bits (byte 1 bit 0/1 = pseudo-categories Male/Female - see R2-10; byte 2 bit 7 set on rules 20,21,22 - meaning unknown, not decoded); **bytes 3..32 = crew category n (n = 1..240) at byte `3 + (n-1)/8`, bit `(n-1)%8` (0 = LSB)**. Name from `CREWCAT(CREWCAT = n).DESC_`. Empty (all 0) = no category. | rpt...WithWithNot.sql:117-141 (`bit_is_set(...SUBSTRING(BinCat,3+((N-1)/8),1),(N-1)%8)`) |
| POS2 | tinyint | Y | Crew position of the **second** side. | Same encoding as POS1 (0 once, template). | rpt...WithWithNot.sql:68-71 |
| CATEG2 | binary(32) | Y | Categories of the second side. | Same layout as CATEG1. On rule 23 byte 1 = `0x03` = Male + Female = "anyone". | R2 lines 645-667 |
| SEL | tinyint | Y | **Flight condition** the rule applies to (the "kind of flights"). | 1 International; 2 Domestic; 3 Any kind of flights; 4 flights with crew-route categories; 5 flights via airports of categories; 6 city pairs of categories; 7 flights to country categories; 8 flights with flight types; 9 flights with AC types; 10 overnight flight; 11 to/from bases; 12 aircraft registrations; 13 carriers; 14 charterers; 15 flight categories; 16 night stops at stations; 17 night stops at countries; 18 aircraft of categories; 19 via airports; 20 aircraft additional category; 21 via airport of additional category; 22 via countries of additional category; 23 AC versions. Anything else -> "Unknown". Observed: 3 (46 rows, incl. all 16 active day-to-day rules), 5 (152 rows, all inactive templates), 0 (1). The parameters of the condition are in `SPEFRECDATA` (KIND=2, same RULE_/PLANDAYTODAY). | rpt...WithWithNot.sql:73-100; profiled |
| NO6065 | tinyint | Y | Naming inference: "age 60-65 exemption" flag. Not read by any procedure. | 0 in all rows. | unknown - not used by any procedure |
| FMDATE | smallint | Y | Rule effective **from** (inclusive), AIMS day number. | Days since 1980-01-01 (`CAST('1980-01-01'+FMDATE AS date)`). 0 = since the beginning. Observed non-zero: 13148 (2015-12-31, rule 15), 16535 (2025-04-09, rule 14), 16526 (2025-03-31, rule 22). | rpt...WithWithNot.sql:102 |
| TODATE | smallint | Y | Rule effective **to** (inclusive). | Days since 1980-01-01; **32767 (= 2069-09-17) = open ended** (198 of 199 rows). | rpt...WithWithNot.sql:103; profiled |
| PENALTY | smallint | Y | Presumably an optimiser penalty weight for violations. | 0 in all rows. Not used. | unknown - not used by any procedure |
| OPENDATES | tinyint | Y | Flag "open dates" (rule has no end date?) - meaning undocumented (R1 comment: "what that flag means is not documented"). | 0 in all rows. | unknown - not used (SPEFREC3 procedure exposes it as OPEN_DATES) |
| OBSRVR | tinyint | Y | 1 = the rule does **not** apply to crew observers. | 0/1 (only rule 3 has 1). The procedure labels it `Rule_Apply_To_Crew_Observers = 'No'` when 1. **R2 does not evaluate it.** | rpt...WithWithNot.sql:105 |
| AUTOHARD | tinyint | Y | Authority / hardness of the rule. | **1 = Company, 2 = Government**, 0/other = '' (blank). Exposed as `Rule_Authority`, then `Rule_Severity` ("Company" = warning, "Government" = blocking per R2 comment). | rpt...WithWithNot.sql:106; R2 line 403,446 |
| MSGCOLR | int | Y | Colour of the violation message in the AIMS UI. | Windows COLORREF-like int (`0x00BBGGRR`, inference: 172, 221 = shades of red). 0 on inactive rules. Not used. | profiled |
| MSG | nchar(60) | Y | **Violation message** shown to the planner (French and/or English, trailing spaces; may contain accented characters). | Free text: e.g. "Junior CM and FO cannot fly together". Returned as `Violation_Message` and `RTRIM`-ed by R2. | rpt...WithWithNot.sql:107; R2 line 767 |
| BLKHRS | int | Y | Unknown (naming: block hours). | NULL on 163 rows, 0 elsewhere. | unknown - not used by any procedure |
| SEL2 | tinyint | Y | Unknown "second selector"; newer column (NULL on untouched legacy rows). | 3 whenever set (36 rows). | unknown - not used by any procedure |

## 4. Keys & relationships
* Natural key: (RULE_, PLANDAYTODAY) (= PK). KIND is constant (2) but is part of the key of the detail table.
* **Detail rows**: `SPEFRECDATA` where `SPEFRECDATA.RULE_ = SPEFREC2.RULE_ AND SPEFRECDATA.PLANDAYTODAY = SPEFREC2.PLANDAYTODAY AND SPEFRECDATA.KIND = 2` (1 : N; N = 1 row for an untouched rule, 48 rows (IDX 1..48) once the rule was saved with list data). No orphans (0 SPEFRECDATA KIND=2 rows without a header). Predicate in code: `[Extent1].[KIND] = @Flag_Kind_Schedule AND [Extent1].RULE_ = TM.Rule_Nbr AND [Extent1].PLANDAYTODAY = @Filter_PlanDayToDay` (rpt.Get_Custom_Rules_Schedule_WithWithNot.sql:399-401).
* `POS1`/`POS2` -> `vvPositions.ID` (N:1): `LEFT JOIN vvPositions P1 ON E.POS1 = P1.ID` (+ the 25/26 pseudo codes).
* `CATEG1`/`CATEG2` bits -> `CREWCAT.CREWCAT` (N:M): `INNER JOIN TSC.dbo.CREWCAT C ON C.CREWCAT = n.N WHERE bit_is_set(...)`. A crew member's categories are in `CREWCATEG` (ID, CREWCATIDX, ACTIVEBEG, ACTIVEEND).
* `AUTOHARD`, `SCHE`, `SEL` are code columns with the decodings above (no lookup table).

## 5. Encoding conventions & gotchas
* **Dates**: FMDATE/TODATE are day numbers (days since 1980-01-01), `smallint`, inclusive both ends; 32767 = no end. Validity test used by the rules procedure: `FMDATE <= @PairingStart_Offset AND TODATE >= @PairingStart_Offset` where the offset is `DATEDIFF(day,'1980-01-01',@Date_PairingStart)`. A rule is therefore evaluated against the **pairing start date**, not the date of each leg.
* **Active = non-zero** (1 *or* 2). Filtering `ACTIVE = 1` loses half the rules.
* **Label gotcha**: in `rpt.Get_Custom_Rules_Schedule_WithWithNot` the `Rule_Type` is `CASE WHEN E.PlanDayToDay = @Filter_PlanDayToDay THEN 'DayToDay' ELSE 'Plan'` while the WHERE already forces equality, so the output says 'DayToDay' even when the procedure is called with `@Filter_PlanDayToDay = 1`. Likewise `Rule_Kind` is derived from `E.Kind = @Flag_Kind_Schedule`.
* **Category bytes 1-2 are not categories**: the procedure only decodes bytes 3..32 (categories 1..240). Male/Female pseudo-categories (byte 1 bits 0-1) and byte 2 flags are ignored, so a list that contains only those arrives *empty* (R2 handles rule 23 as a special case "second list = anyone").
* The two sides are matched **orientation-free** on position text (`CHARINDEX(crew_position, 'CM | PO')`), so a rule PO(cat A) vs CM(cat B) fires whichever crew member is listed first; but for rules whose two sides hold the **same position and different category lists** the R2 code evaluates a single orientation per unordered pair (X.Crew_ID < Y.Crew_ID as *text*) and may miss the opposite assignment (code analysis, not tested; all currently active same-position rules 3, 11, 12, 18, 22 have identical lists on both sides, so they are unaffected).
* Messages contain non-ASCII characters (accents); `nchar(60)` space padded -> `RTRIM`.
* Position codes are space-padded 2-letter strings in `vvPositions.CODE`; position 25/26 are not in `vvPositions`.
* `OBSRVR`, `NO6065`, `PENALTY`, `OPENDATES`, `BLKHRS`, `SEL2`, `MSGCOLR`, `ACTIVE` (1 vs 2) are not evaluated by R2.

## 6. How the planner-assist procedures use it
* **`rpt.Get_Custom_Rules_Schedule_WithWithNot(@Date_PairingStart, @Filter_PlanDayToDay = 2, @Flag_Kind_Schedule = 2)`** reads `SPEFREC2 E` with `E.PLANDAYTODAY = @Filter_PlanDayToDay AND E.Active != 0 AND E.FMDATE <= offset AND E.TODATE >= offset`, decodes SCHE (text), POS1/POS2 (position names), SEL (condition text), the two CATEG bitmaps (`Category_FirstPosition_List`, `Category_SecondPosition_List` as `'| '`-joined CREWCAT names), FMDATE/TODATE (real dates), OBSRVR, AUTOHARD (Authority) and MSG, then builds `Subconditions_Raw_JSON` from SPEFRECDATA (see SPEFRECDATA.md).
* **`dbo.R2_Get_Violations_Schedule_WithWithNot(@Crew_Position_To_Draft, @Crew_Id_To_Draft, @pPAIRING_ID, @pPAIRING_DATE)`**: loads the rules (INSERT ... EXEC), loads the pairing's legs and crew (`rpt.Get_Detailed_Pairing`, plus related pairings), "drafts" the crew member into the open slot, and builds all **pairs of crew on the same physical leg** (same Day_Offset, Flight_Number, Carrier_Code, Departure_Airport, Arrival_Airport, STD_UTC). For each pair x active rule:
  1. *position match*: X/Y positions are found in `First_Position_Name`/`Second_Position_Name` (either orientation); `Is_X_First_Position` records the orientation;
  2. *category match*: `Condition_1_Category_FirstPosition_List` = the first-position crew holds >= 1 category listed in `Category_FirstPosition_List`; same for the second -> `Is_Category_Intersect_Matched` = both;
  3. *flight condition*: `Is_SubCondition_Matched` evaluates `SEL` against the leg using the JSON from SPEFRECDATA (kind 3 and the unsupported-but-tolerated kinds 14 and 22 are always true; 1/2/10 test the leg's `Is_International` / `Is_Domestic` / `Is_Overnight` flags; kind 23 is never true; all other kinds compare the leg's text attributes with the JSON lists);
  4. **Do not Schedule** rows (SCHE <> 1): violation when positions + both category lists + flight condition match and **either crew is the drafted one** (`X_Is_Draft = 1 OR Y_Is_Draft = 1`), `X <> Y`. Message = `MSG`, severity = AUTOHARD ('Company' soft, 'Government' hard);
  5. **Always Schedule** rows (SCHE = 1): evaluated per *subject* crew member (the one in POS1 holding a CATEG1 category, on a leg where the flight condition holds). A violation is reported when nobody else on the same physical leg (in any loaded pairing) holds position POS2 *and* a category of CATEG2 (rule 23: or, if CATEG2 = "anyone", any non-cadet in POS2), and the drafted crew is the subject or holds POS2. The reported partner is the drafted crew (or lowest id) in POS2 who does not qualify, or NULL when nobody holds POS2.
* `SPEFREC2` is not read by R1, R3, R4, R5.

## 7. Typical query patterns
```sql
-- 1. All active Day-to-Day with / with-not rules that are valid on a date, decoded (no crew data involved)
DECLARE @n int = DATEDIFF(DAY,'1980-01-01','2026-11-03');
SELECT e.RULE_,
       CASE WHEN e.SCHE = 1 THEN 'Always Schedule' ELSE 'Do not Schedule' END AS Modality,
       CASE e.POS1 WHEN 25 THEN 'CM | PO' WHEN 26 THEN 'DV | AB' ELSE p1.CODE END AS FirstPosition,
       CASE e.POS2 WHEN 25 THEN 'CM | PO' WHEN 26 THEN 'DV | AB' ELSE p2.CODE END AS SecondPosition,
       CASE e.AUTOHARD WHEN 1 THEN 'Company' WHEN 2 THEN 'Government' ELSE '' END AS Authority,
       e.SEL AS FlightConditionId, RTRIM(e.MSG) AS Message
FROM TSC.dbo.SPEFREC2 e
LEFT JOIN TSC.dbo.vvPositions p1 ON p1.ID = e.POS1
LEFT JOIN TSC.dbo.vvPositions p2 ON p2.ID = e.POS2
WHERE e.PLANDAYTODAY = 2 AND e.ACTIVE <> 0 AND e.FMDATE <= @n AND e.TODATE >= @n
ORDER BY e.RULE_;

-- 2. Crew categories named in the first / second list of one rule (bit n -> byte 3+(n-1)/8, bit (n-1)%8)
SELECT 'first' AS Side, c.CREWCAT, RTRIM(c.DESC_) AS Category
FROM TSC.dbo.SPEFREC2 e JOIN TSC.dbo.CREWCAT c ON c.CREWCAT BETWEEN 1 AND 240
WHERE e.RULE_ = 16 AND e.PLANDAYTODAY = 2
  AND (CONVERT(tinyint, SUBSTRING(CONVERT(binary(32), e.CATEG1), 3 + (c.CREWCAT-1)/8, 1)) / POWER(2,(c.CREWCAT-1)%8)) % 2 = 1
UNION ALL
SELECT 'second', c.CREWCAT, RTRIM(c.DESC_)
FROM TSC.dbo.SPEFREC2 e JOIN TSC.dbo.CREWCAT c ON c.CREWCAT BETWEEN 1 AND 240
WHERE e.RULE_ = 16 AND e.PLANDAYTODAY = 2
  AND (CONVERT(tinyint, SUBSTRING(CONVERT(binary(32), e.CATEG2), 3 + (c.CREWCAT-1)/8, 1)) / POWER(2,(c.CREWCAT-1)%8)) % 2 = 1
ORDER BY 1, 2;

-- 3. Header-level statistics
SELECT PLANDAYTODAY, ACTIVE, AUTOHARD, SCHE, COUNT(*) AS Rules FROM TSC.dbo.SPEFREC2 GROUP BY PLANDAYTODAY, ACTIVE, AUTOHARD, SCHE ORDER BY 1,2,3,4;
```

## 8. Data profile (measured 2026-11-03; day number of today = 17108)
* 199 rows: Plan (1) = 100 rows (83 inactive, 7 ACTIVE=1, 10 ACTIVE=2); Day-to-Day (2) = 99 rows (83 inactive, 7 ACTIVE=1, 9 ACTIVE=2). KIND = 2 everywhere. SEL: 3 = 46, 5 = 152 (templates), 0 = 1. SCHE: 1 = 15, 2 = 184. AUTOHARD: 0 = 159, 1 = 19, 2 = 21.
  POS1: 1 = 14, 2 = 177, 3 = 4, 25 = 4; POS2: 0 = 1, 1 = 176, 2 = 16, 3 = 4, 25 = 2. OBSRVR = 1 on 2 rows (rule 3); NO6065 / PENALTY / OPENDATES = 0 on all rows. TODATE = 32767 on 198 rows.
* **The 16 active Day-to-Day rules** (rule: modality; POS1 [categories] vs POS2 [categories]; authority; message). Check-pilot set = {A CHECK A330, B CHECK A330, CD Line check de droite A330, A CHECK A321, B CHECK A321, CD Line check de droite A321}; all have SEL = 3 (any flight):

| Rule | ACTIVE | SCHE | POS1 [CATEG1] | POS2 [CATEG2] | AUTOHARD | Valid from | MSG |
|---|---|---|---|---|---|---|---|
| 1 | 2 | Do not | PO [JUNIOR FO] | CM [JUNIOR CPT] | Government | always | Junior CM and FO cannot fly together |
| 2 | 1 | Do not | CM [CPT en LI - RC] | PO [CPT en RC, JUNIOR FO, FO en LI - RC] | Company | always | VALIDER AVEC QUI IL VOLE |
| 3 | 2 | Do not | CM\|PO [JUNIOR CPT, JUNIOR FO] | CM\|PO [JUNIOR CPT, JUNIOR FO] | Government (OBSRVR=1) | always | CANNOT HAVE MORE THAN 1 JUNIOR PER FLIGHT |
| 10 | 2 | Do not | PO [Medical Restraint] | CM [Medical Restraint] | Government | always | MEDICAL - Categorie 35 - Les 2 PNT ne peuvent voler ensemble |
| 11 | 2 | Do not | PO [Medical Restraint] | PO [Medical Restraint] | Government | always | (same as 10) |
| 12 | 2 | Do not | CM [Medical Restraint] | CM [Medical Restraint] | Government | always | (same as 10) |
| 14 | 2 | Always | CM [CPT en LI - RC] | CM [check-pilot set] | Government | 2025-04-09 | Ne peut pas voler FO et doit voler avec pilote verificateur |
| 15 | 2 | Do not | CM [JUNIOR CPT] | PO [JUNIOR FO] | Government | 2015-12-31 | Junior CM and FO cannot fly together |
| 16 | 1 | Always | PO [FO en LI - RC] | CM [check-pilot set] | Company | always | DOIT VOLER AVEC PILOTE VERIFICATEUR |
| 17 | 1 | Always | CM\|PO [CPT en LI - RC, FO en CMD LI - (NE PEUT PAS VOLER POF)] | CM [check-pilot set] | Company | always | DOIT VOLER AVEC PILOTE VERIFICATEUR |
| 18 | 1 | Do not | PO [JUNIOR FO] | PO [JUNIOR FO] | Company | always | Junior FO en augmented ne peuvent pas voler ensemble |
| 19 | 1 | Always | PO [FO en CMD LI - (NE PEUT PAS VOLER POF)] | CM [check-pilot set] | Company | always | FO EN LI -RC (NE PEUT PAS VOLER POF) |
| 20 | 1 | Always | PO [CADET UNDER TRAINING] | CM [check-pilot set] | Company | always | CADET UNDER TRAINING - Verification necessaire |
| 21 | 1 | Always | PO [CADET with Safety pilot and trainer] | CM [check-pilot set] | Company | always | CADET - Instructeur manquant |
| 22 | 2 | Do not | PO [LICENCE CPL] | PO [LICENCE CPL] | Government | 2025-03-31 | Licence CPL - Maximum 1 PO avec licence CPL sur le vol |
| 23 | 2 | Always | PO [CADET with Safety pilot and trainer] | PO [anyone: Male+Female bits] | Government | always | CADET - Safety Pilot manquant |

  Plan set (PLANDAYTODAY = 1) is nearly identical (17 active rules; it additionally holds rule 7 "deux + de 60 ans" (active), and rule 0 is an inactive template). `ACTIVE` mirrors AUTOHARD (1 <-> Company, 2 <-> Government) in 32 of the 33 active rows.

## 9. Open questions / confidence
* High confidence: the with / with-not semantic (SCHE), position and category decoding, validity dates, severity, join to SPEFRECDATA - all confirmed by code (R2, rpt procedure) **and** by the live rules and their French/English messages.
* Medium: PLANDAYTODAY 1 = Plan (only the `Plan` label branch says so). ACTIVE 1 vs 2 (correlates with AUTOHARD; never evaluated).
* Unknown: byte-2 bit 7 of CATEG1 on rules 20/21/22 (header flag), the bytes 1-2 header in general, NO6065, PENALTY, OPENDATES, BLKHRS, SEL2.
* "PNT" = flight crew, "PNC" = cabin crew (French *personnel navigant technique/commercial*), "LI-RC" etc. are airline qualification jargon; categories are named exactly as in `CREWCAT.DESC_`.
