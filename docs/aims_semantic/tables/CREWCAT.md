# CREWCAT  (Table)  - Crew category dictionary (240 fixed slots: qualifications, groups, languages, status flags)

## 1. Purpose & business meaning
`TSC.dbo.CREWCAT` is the AIMS **dictionary of crew categories** ("crew categories" / "crew groups" in the AIMS crew-data screens). A category is a free-form label that the airline attaches to crew members for a period of time
(see `CREWCATEG` for the per-crew assignment). At this airline (Air Transat, per the category text "No longer with Air Transat") the 161 named categories (plus 5 "Empty Slot" labels) mix several kinds of information:

- fleet checks and instructor roles ("A CHECK A330", "B CHECK A321", "SIM INSTRUCTOR A330", "Entraineur EPT", "Pilote Instructeur", "INSTRUCTEUR FIRST AID PNC");
- seat / experience status ("JUNIOR FO", "JUNIOR CPT", "CPT en LI - RC", "FO en LI - RC", "RIGHT SEAT QUALIFIED", "POF permanent", "Pilot over 60 years old", "CADET UNDER TRAINING");
- cabin crew groups ("NEW PNC", "DV initiaux", "DETENTEUR POSITION DV", "GROUPE 1 - DV", "PNC - B", "PNC - G", month-of-training groups "FEVRIER FORMATION PNC" ... "JANVIER FORMATION PNC");
- union / work-schedule regimes ("BLOC INACTIF", "BLOC PNT REG", "REGULIER", "SYNDICAT 95 HRS 18/10/24"), recall status ("PNT RAPPELE", "PNC RAPPELE", "REFUS RAPPEL");
- language ("FRANÇAIS", "ANGLAIS"), security/regulatory ("TSA - FINGER PRINTS.", "PNC non vaccines", "eCrew Access") and employment status ("PNT NON QUALIFIE", "PNC NON QUALIFIE", "No longer with Air Transat").

One row = one category definition; the row **index (`CREWCAT`) is the category number** (1..240) and is also the **bit position** used by many AIMS bitmaps (`EXPI.CREWCAT`, `EXPI.EXCLUDECAT`, `SPEFREC2.CATEG1/CATEG2`, `SPEFREC3`, ...).
Maintained by AIMS crew administrators (static master data, edited from time to time); read by planner-assist to translate category numbers to names, to filter drafts by category and to evaluate rule/certificate applicability.

## 2. Physical facts
- `TSC.dbo.CREWCAT`, **USER_TABLE**, **240 rows** (rowcounts.json = measured 240). Exactly one row per number 1..240 (the table is a fixed-size array; 74 rows have a blank `DESC_`, 5 rows carry the label "-------- Empty  Slot ---------", 161 rows have a real name).
- Primary key: `CREWCAT_INDEX_0` (unique) on `CREWCAT`. No other index (not needed: 240 rows).
- Tiny table: scanning is free; the procedures cross-join it with `BETWEEN 1 AND 240`.
- Database collation `SQL_Latin1_General_CP1_CI_AS` (case-insensitive, **accent-sensitive**): `DESC_` stores accented characters (É, Ç, é...); a filter typed without the accent will not match.

## 3. Column dictionary
Character widths = `len/2` of columns.json (metadata gives bytes).

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| CREWCAT | smallint | N | Category number = primary key of the category; also the bit index (CREWCAT-1) of every category bitmap in AIMS | 1..240, contiguous | profiled; `R0_GetDraftList.sql` lines 385-390; `rpt.get_crew_certifications.sql` lines 21-25 |
| DESC_ | nchar(40) | Y | Category name as shown to schedulers and as matched by the planner (filter lists `@CategoryIncludeList` / `@CategoryExcludeList` and rule category lists are compared with the trimmed text, **not** the number) | Blank-padded free text, mixed French/English, mixed case. Blank for unused slots. **Not unique**: "BLOC RÉGULIER PNT (CC26)" is stored under both 10 and 11 and "-------- Empty  Slot ---------" 5 times (IDs 26-30) | profiled; `R0_GetDraftList.sql` lines 436-457 (`LTRIM(RTRIM(catDef.DESC_)) = filter.CatName`), `rpt.list_crew_categories.sql` |
| QUAL | tinyint | Y | Probably a flag "this category represents a qualification" (inference from name). Unused: 0 in all 240 rows | 0 | profiled; naming inference; not used by any procedure (only selected by `rpt.get_crew_categories`) |
| ISFORECREW | tinyint | Y | Probably "category applies to fore (= flight-deck) crew" flag (inference from name). Unused: 0 in all 240 rows | 0 | profiled; naming inference; selected by `rpt.get_crew_categories` only |

## 4. Keys & relationships
- Natural/primary key: `CREWCAT`. Business-wise `LTRIM(RTRIM(DESC_))` is used as the name key by the planner (with the duplicate-name caveat above).
- `CREWCATEG.CREWCATIDX = CREWCAT.CREWCAT` (1:N; one category has many crew assignments). Join used everywhere, e.g. `INNER JOIN TSC.dbo.CREWCAT AS cc ON cc.CREWCAT = Main.CREWCATIDX` (`rpt.get_crew_categories.sql` line 19-20), `INNER JOIN TSC.dbo.CREWCAT AS catDef ON catDef.CREWCAT = ccSub.CREWCATIDX` (`R0_GetDraftList.sql` line 440). Measured: 0 `CREWCATEG` rows without a matching `CREWCAT` row.
- Bitmap decode (N:M "expiry type applies to categories"): bit `(CREWCAT-1)%8` of byte `(CREWCAT-1)/8 + 1` of `EXPI.CREWCAT` (include list, binary(30), converted to binary(32)) and `EXPI.EXCLUDECAT` (exclude list). Code: `JOIN TSC.dbo.CREWCAT C ON C.CREWCAT BETWEEN 1 AND 240 WHERE (CONVERT(tinyint, SUBSTRING(CONVERT(binary(32), E.CrewCat), (C.CREWCAT - 1) / 8 + 1, 1)) & POWER(2, (C.CREWCAT - 1) % 8)) > 0` (`R0_GetDraftList.sql` lines 382-403).
- Custom rules `SPEFREC2.CATEG1/CATEG2` are decoded against `CREWCAT` as well, but with a different byte offset: **byte `3 + (N-1)/8`, bit `(N-1)%8`** (the first 2 bytes of those 32-byte fields are skipped) - `rpt.Get_Custom_Rules_Schedule_WithWithNot.sql` lines 117-139. Do not reuse the EXPI offset for SPEFREC.

## 5. Encoding conventions & gotchas
- Always `LTRIM(RTRIM(DESC_))`: fixed-width `nchar(40)`.
- The category **name** is the matching key in planner-assist, not the number: names with a trailing space or a different accent will not match. Duplicate names (IDs 10 and 11) collapse into one name in `#CrewCatMap` (it is built `SELECT DISTINCT ... LTRIM(RTRIM(cat.DESC_))`).
- Slots 26-30 are explicitly "Empty Slot"; the 74 blank rows (IDs such as 88, 89, 93, 97, 109, 119, 128, 129, 139, ... up to 238) are unnamed spare slots. `rpt.list_crew_categories` returns `SELECT DISTINCT LTRIM(RTRIM(DESC_))` and therefore also returns one blank and one "-------- Empty  Slot ---------" entry; filter them out in clients.
- Name suffixes sometimes embed a date or a rule reference ("(CC26)", "SYNDICAT 88 HRS 01/08/2009", "SYNDICAT 95 HRS 18/10/24", "ENTRAINEMENT MFF - start 2023"): these are labels only.
- Category 239 "Discontinued Expiry" and 240 "Not to fly on certain  AC TAIL" are used as markers (239 is in the include bitmap of one expiry type; 240 has no assignment).
- The category dictionary is not a hierarchy; a crew member normally holds many categories at the same time (see `CREWCATEG`).

## 6. How the planner-assist procedures use it
- `dbo.R0_GetDraftList` (candidate crew for a pairing):
  - candidate pool filter `@CategoryIncludeList` / `@CategoryExcludeList` (comma lists of names): joins `CREWCATEG` -> `CREWCAT` and compares `LTRIM(RTRIM(DESC_))` to the filter names, with validity overlap `ACTIVEBEG <= @EndDateNum AND ACTIVEEND >= @StartDateNum` (lines 435-458).
  - `#CrewCatMap` (crew, category-name) and the display string `Crew_Categories` (`STRING_AGG ... ' | '`) (lines 500-527).
  - `#CertCatInc` / `#CertCatExc`: decodes the include/exclude category bitmaps of each certificate rule in `EXPI` into category names; a certificate applies to a crew member only if he holds no excluded category and (no include list or at least one included category) (lines 380-403, 574-586).
- `dbo.R1_Get_Violations_CertainFlightsCrew`, `dbo.R2_Get_Violations_Schedule_WithWithNot`: build `Crew_Profile_Categories` (`' | '`-joined names) of the drafted crew member, then match against the rule's category list by `STRING_SPLIT(...,'|')` on trimmed names; R2 treats names starting with `CADET` specially for "anyone but cadets" rules (R2-10). R2 evaluates validity on the pairing date (inclusive on both ends); R1 and `rpt.get_crew_certifications` use `ACTIVEEND > today` only.
- `rpt.get_crew_categories`: returns the categories currently valid for one crew member (with `QUAL`, `ISFORECREW`).
- `rpt.list_crew_categories`: distinct category names for the client UI.
- `rpt.get_crew_certifications`: decodes `EXPI.CREWCAT` / `EXCLUDECAT` into `Crew_Categories_To_Include` / `_To_Exclude` text.
- `rpt.Get_Custom_Rules_Schedule_WithWithNot`: decodes `SPEFREC2.CATEG1/2` (offset 3) into category lists.

## 7. Typical query patterns
```sql
-- named categories only (skip blanks and empty slots)
SELECT CREWCAT, LTRIM(RTRIM(DESC_)) AS Category_Name
FROM TSC.dbo.CREWCAT
WHERE LTRIM(RTRIM(DESC_)) <> N'' AND DESC_ NOT LIKE N'%Empty  Slot%'
ORDER BY CREWCAT;

-- categories of one crew member that are valid today (ACTIVEBEG/ACTIVEEND = inclusive day numbers since 1980-01-01)
SELECT cc.CREWCATIDX, LTRIM(RTRIM(c.DESC_)) AS Category_Name
FROM TSC.dbo.CREWCATEG AS cc
JOIN TSC.dbo.CREWCAT   AS c ON c.CREWCAT = cc.CREWCATIDX
WHERE cc.ID = @crew_id
  AND cc.ACTIVEBEG <= DATEDIFF(DAY, '1980-01-01', GETDATE())
  AND cc.ACTIVEEND >= DATEDIFF(DAY, '1980-01-01', GETDATE())
ORDER BY c.CREWCAT;

-- crew holding a given category today (count only; do not output names)
SELECT COUNT(DISTINCT cc.ID) AS Crew_Count
FROM TSC.dbo.CREWCATEG AS cc
JOIN TSC.dbo.CREWCAT   AS c ON c.CREWCAT = cc.CREWCATIDX
WHERE LTRIM(RTRIM(c.DESC_)) = N'JUNIOR FO'
  AND DATEDIFF(DAY, '1980-01-01', GETDATE()) BETWEEN cc.ACTIVEBEG AND cc.ACTIVEEND;
```

## 8. Data profile (measured 2026-11-03)
- 240 rows; `QUAL` = 0 and `ISFORECREW` = 0 in all rows; 161 rows have a real name, 5 are "Empty Slot" labels, 74 are blank.
- Duplicate names: "BLOC RÉGULIER PNT (CC26)" (IDs 10, 11) and the empty-slot label (IDs 26-30).
- Assignments in `CREWCATEG` (all periods) and assignments valid today (`ACTIVEBEG <= today <= ACTIVEEND`, inclusive) per non-blank category (166 rows listed, incl. the 5 empty-slot labels):

| CREWCAT | DESC_ | Assignments (all time) | Valid today |
|---|---|---|---|
| 1 | A CHECK A330 | 56 | 23 |
| 2 | B CHECK A330 | 54 | 15 |
| 3 | TRNG CPT | 1 | 1 |
| 4 | CPT en LI - RC | 1388 | 25 |
| 5 | SENIOR CPT | 1 | 0 |
| 6 | JUNIOR CPT | 1083 | 12 |
| 7 | CABIN CREW | 0 | 0 |
| 8 | CPT en RC | 1 | 1 |
| 9 | JUNIOR FO | 1660 | 134 |
| 10 | BLOC RÉGULIER PNT (CC26) | 0 | 0 |
| 11 | BLOC RÉGULIER PNT (CC26) | 1 | 1 |
| 12 | TRNG SO | 0 | 0 |
| 13 | AUGMENTED | 0 | 0 |
| 14 | SIM INSTRUCTOR A330 | 136 | 27 |
| 15 | FO en LI - RC | 1955 | 96 |
| 16 | FO en CMD LI - ( NE PEUT PAS VOLER POF) | 47 | 0 |
| 17 | PERM. CABIN CREW | 1 | 0 |
| 18 | TEMP/SEASONAL  CABIN CREW | 0 | 0 |
| 19 | Pilot  over 60 years old | 131 | 62 |
| 20 | CC FIRST YR OF SERVICE | 0 | 0 |
| 21 | CD Line check de droite A330 | 140 | 32 |
| 22 | CG Line check de gauche A330 | 101 | 5 |
| 23 | CLRD TO OP 2 ENG FERRY | 3 | 3 |
| 24 | RIGHT SEAT QUALIFIED | 97 | 20 |
| 25 | ROUTE CHECK ETOPS | 7 | 2 |
| 26 | -------- Empty  Slot --------- | 0 | 0 |
| 27 | -------- Empty  Slot --------- | 0 | 0 |
| 28 | -------- Empty  Slot --------- | 0 | 0 |
| 29 | -------- Empty  Slot --------- | 0 | 0 |
| 30 | -------- Empty  Slot --------- | 0 | 0 |
| 31 | FLAG CAPT | 0 | 0 |
| 32 | PPC Monitor | 0 | 0 |
| 33 | Pilot over 65 years old | 0 | 0 |
| 34 | A CHECK 1st year | 33 | 2 |
| 35 | Medical Restraint | 36 | 29 |
| 36 | PNT ACTIF | 809 | 751 |
| 37 | FAM FLIGHT | 0 | 0 |
| 38 | INSTRUCTEUR REQUALIFICATION | 29 | 6 |
| 39 | INSTRUCTEUR EET | 3 | 3 |
| 40 | INSTRUCTEUR CPR PNC | 35 | 5 |
| 41 | INSTRUCTEUR INITIALPNC | 34 | 30 |
| 42 | INSTRUCTEUR FIRST AID PNC | 78 | 36 |
| 43 | INSTRUCTEUR ANNUEL PNC | 76 | 40 |
| 44 | INSTRUCTEUR DITCHING PNC | 17 | 3 |
| 45 | REANIMATION CARDIO-RESPIRATOIRE-DEFIB | 541 | 42 |
| 46 | FORMATION INITIALE MOINS D'UN AN | 0 | 0 |
| 47 | BLOC PVHR (CC26) | 0 | 0 |
| 48 | JUILLET FORMATION PNC | 27 | 27 |
| 49 | AOUT FORMATION PNC | 10 | 10 |
| 50 | DETENTEUR POSITION DV | 176 | 161 |
| 51 | DETENTEUR POSITION DA | 110 | 95 |
| 52 | EN ATTENTE POSITION DV | 1 | 1 |
| 53 | EN ATTENTE POSITION DA | 0 | 0 |
| 54 | FEVRIER FORMATION PNC | 151 | 119 |
| 55 | MARS FORMATION PNC | 227 | 217 |
| 56 | AVRIL FORMATION PNC | 416 | 387 |
| 57 | MAI FORMATION PNC | 337 | 281 |
| 58 | JUIN FORMATION PNC | 430 | 390 |
| 59 | SEPTEMBRE FORMATION PNC | 169 | 163 |
| 60 | OCTOBRE FORMATION PNC | 173 | 166 |
| 61 | NOVEMBRE FORMATION PNC | 197 | 182 |
| 62 | JANVIER FORMATION PNC | 94 | 76 |
| 63 | DECEMBRE FORMATION PNC | 85 | 83 |
| 64 | BLOC PVHR | 0 | 0 |
| 65 | BLOC PNT REG | 4 | 4 |
| 66 | BLOC PNT RSV | 0 | 0 |
| 67 | Prog Min Mensuel bonifié | 0 | 0 |
| 68 | BLOC PNT 80 HEURES | 0 | 0 |
| 69 | BLOC PNT SUP 80 HRS | 0 | 0 |
| 70 | POF TRAINING CMD | 376 | 5 |
| 71 | BLOC FORMATION  88 hrs | 1 | 1 |
| 72 | BLOC INACTIF | 932 | 810 |
| 73 | SHARE RSV / MINI RSV | 0 | 0 |
| 74 | PROJET SPECIAUX | 0 | 0 |
| 75 | REGULIER | 5 | 5 |
| 76 | SYNDICAT PNT | 0 | 0 |
| 77 | FORM / PR SPEC. 80 HRS | 0 | 0 |
| 78 | SHARE | 0 | 0 |
| 79 | MINI BLOC | 0 | 0 |
| 80 | RESERVE | 0 | 0 |
| 81 | SYNDICAT 88 HRS 01/08/2009 | 0 | 0 |
| 82 | PETIT PORTEUR | 0 | 0 |
| 83 | SWITCH/DON OVER 85 UNDER65 | 1 | 0 |
| 84 | SWITCH/DON OVER 85 UNDER40 | 27 | 27 |
| 85 | PROJET 85 HEURES | 0 | 0 |
| 86 | CADET UNDER TRAINING | 19 | 8 |
| 87 | CADET with Safety pilot and trainer | 10 | 0 |
| 90 | NEW PNC | 1457 | 167 |
| 91 | DV initiaux | 192 | 166 |
| 92 | DV formation initiale. | 69 | 67 |
| 94 | SYNDICAT 95 HRS 18/10/24 | 0 | 0 |
| 95 | PNC NON QUALIFIE | 4502 | 437 |
| 96 | PNT NON QUALIFIE | 2657 | 85 |
| 98 | ETOPS B737 | 22 | 0 |
| 99 | PERMANENT 737 | 137 | 10 |
| 100 | YOYO 332 a 738 | 222 | 24 |
| 101 | YOYO 313 a 738 | 116 | 8 |
| 102 | FRANÇAIS | 1367 | 1366 |
| 103 | ANGLAIS | 1387 | 1384 |
| 104 | Pilote Instructeur | 117 | 116 |
| 105 | CCQ - A320 | 308 | 245 |
| 106 | CCQ - A330 | 53 | 47 |
| 107 | LIBERATION SYNDICALE PNT (CC26) | 0 | 0 |
| 108 | Nouveau DV | 0 | 0 |
| 110 | Entraineur PERF | 9 | 5 |
| 111 | Entraineur EPT | 30 | 9 |
| 112 | Entraineur PRLI | 8 | 5 |
| 113 | ENTRAINEUR SOP | 10 | 6 |
| 114 | Entraineur PNT Formation Sol | 10 | 9 |
| 115 | Instructeur PNC | 24 | 24 |
| 116 | PNC - B | 1069 | 1065 |
| 117 | PNC - G | 1026 | 1023 |
| 118 | DV coach | 51 | 48 |
| 120 | TSA - FINGER PRINTS. | 180 | 150 |
| 121 | GROUPE 1 - DV | 170 | 170 |
| 122 | GROUPE 2 - DV | 162 | 162 |
| 123 | GROUPE 3 - DV | 72 | 72 |
| 124 | MFF QUALIFIED | 0 | 0 |
| 125 | MFF320 | 36 | 34 |
| 126 | MFF330 | 91 | 77 |
| 127 | ENTRAINEMENT MFF - start 2023 | 33 | 4 |
| 130 | M CHECK PVA A330 | 3 | 1 |
| 131 | M CHECK PVA  A321 | 3 | 1 |
| 132 | A CHECK A321 | 44 | 21 |
| 133 | A CHECK A 310 | 19 | 1 |
| 134 | A CHECK B737 | 22 | 0 |
| 135 | SIM INSTRUCTOR  A313 | 4 | 1 |
| 136 | SIM INSTRUCTOR B738 | 6 | 0 |
| 137 | SIM INSTRUCTOR  A321 | 37 | 23 |
| 138 | SIM TS/CAE INSTRUCTOR | 22 | 10 |
| 140 | right seat qualified A330 | 102 | 42 |
| 141 | right seat qualified A321 | 148 | 67 |
| 142 | right seat qualified A310 | 0 | 0 |
| 143 | right seat qualified B737 | 1 | 0 |
| 145 | POF permanent | 78 | 0 |
| 147 | B CHECK A313 | 16 | 0 |
| 149 | B CHECK B738 | 9 | 0 |
| 151 | B CHECK A321 | 21 | 10 |
| 152 | CD Line check de droite A310 | 21 | 1 |
| 153 | CD Line check de droite B738 | 25 | 0 |
| 154 | CD Line check de droite A321 | 79 | 31 |
| 155 | CG Line check de gauche A310 | 27 | 1 |
| 156 | CG Line check de gauche B738 | 5 | 0 |
| 157 | CG Line check de gauche A321 | 10 | 0 |
| 159 | OPEN PN | 0 | 0 |
| 160 | PNT MAP | 44 | 4 |
| 162 | PNT RAPPELE | 859 | 553 |
| 163 | PNC RAPPELE | 737 | 644 |
| 164 | PNT SOUS-CONTRAT Chine | 0 | 0 |
| 165 | REFUS RAPPEL AUTRE BASE | 37 | 31 |
| 166 | YUL BASE PERMANENTE RAP. AUTRE BASE | 26 | 4 |
| 167 | YYZ BASE PERMANENTE RAP. AUTRE BASE | 46 | 5 |
| 168 | YVR BASE PERMANENTE RAP. AUTRE BASE | 26 | 25 |
| 169 | REFUS RAPPEL | 76 | 70 |
| 170 | PNC non vaccines | 81 | 64 |
| 171 | PNT non vaccines | 4 | 4 |
| 172 | PNC licencies | 30 | 25 |
| 173 | eCrew Access | 109 | 28 |
| 175 | PNC SOUS-CONTRAT HiFly | 13 | 1 |
| 180 | CCQ A321 | 125 | 109 |
| 181 | CCQ A330 | 98 | 90 |
| 190 | FORMATION PELESYS | 3 | 3 |
| 192 | LICENCE CPL | 103 | 73 |
| 222 | No longer with Air Transat | 325 | 321 |
| 239 | Discontinued Expiry | 0 | 0 |
| 240 | Not to fly on certain  AC TAIL | 0 | 0 |

(Categories with 0/0 are defined but never assigned. The largest valid-today groups are "FRANÇAIS", "ANGLAIS", "PNC - B"/"PNC - G", "BLOC INACTIF", "PNT ACTIF", "PNT RAPPELE"/"PNC RAPPELE", "CPT/FO en LI - RC" and the monthly PNC training groups.)

## 9. Open questions / confidence
- High: `CREWCAT` = category number and bit index; `DESC_` = name; name-based matching in the planner; join to `CREWCATEG`.
- Medium (inference): the business interpretation of groups of categories (e.g. "BLOC ..." = work-schedule regime, "(CC26)" = collective agreement reference) comes from the names only.
- Unknown: purpose of `QUAL` and `ISFORECREW` (both constantly 0; the AIMS vendor semantics are not documented in the repo).
- Open: whether the duplicate "BLOC RÉGULIER PNT (CC26)" rows are intentional (only ID 11 has one assignment).
