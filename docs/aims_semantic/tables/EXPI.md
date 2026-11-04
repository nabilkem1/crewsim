# EXPI  (Table)  - Expiry / currency type dictionary (certificates, checks, medicals, recurrent training, landing currency)

## 1. Purpose & business meaning
`TSC.dbo.EXPI` is the AIMS **definition table of "expiries"** - everything a crew member must keep valid: licences/medicals (MEDICAL, IFR licence follow-up), recurrent checks (PPC "Pilot Proficiency Test", system exam, route check, line check), recurrent training (EPT, dangerous goods, first aid, CPR, fire, CRM, PELESYS annual training), documents (passport, UK ETA, visa Brazil), and **flight-experience currency** (landings / take-offs in the last 90 or 180 days, night landings, "line exposure").
One row = one expiry **type** (not a crew member's record). For each type the table defines: code and name, the **positions** it applies to, the **aircraft types** it applies to, the **crew categories** to include/exclude, how its validity period is counted (`DAYTYP`, `MAXDUE`), the schedule/activity codes that renew it (`CREWCODE1..20`), display/warning attributes, and the validity window of the definition itself (`EFFECTIVE_BEG`/`EFFECTIVE_END`).
The per-crew data (last check date, computed expiry date) lives in `vvCREXPREC` (view over the crew-expiry record table), keyed by `EXPI.EXPI`.
188 definitions exist, but only 52 are "live" (`EFFECTIVE_END = 0` and a non-blank `SHORTDESC`); the others are retired variants (per-fleet duplicates such as "PPC Test 738/313/332", "CAT II 313", etc.) or empty slots.
Maintained by AIMS crew-training/administration; read by planner-assist to detect **expired certificates** of crew candidates (`R0_GetDraftList`) and to list the certificates a crew member must hold and their expiry dates (`rpt.get_crew_certifications`).

## 2. Physical facts
- `TSC.dbo.EXPI`, **USER_TABLE**, **188 rows**, 46 columns (rowcounts.json; measured identical). Primary key `EXPI_INDEX_0` (unique) on `EXPI`.
- Expiry numbers are sparse and not contiguous (1..200, plus 272); 5 slots have a blank `SHORTDESC` (EXPI 76, 81, 84, 85, 272).
- Binary bitmap columns have fixed widths: `POS` binary(3) (24 bits = `vvPositions` slots), `CREWCAT` binary(30) (240 bits), `EXCLUDECAT` binary(30), `MULT_AC` binary(12) (96 bits), `RTECAT` binary(4).
- Tiny table - the planner materialises it once into temp tables; scanning it is free.
- `SHORTDESC` is unique among the non-blank values (no duplicates measured); `DESC_` is not (e.g. two "Dangerous Goods", two "A320 Differences", three "Elementary Mtce").

## 3. Column dictionary
Character widths = `len/2` of columns.json (metadata is in bytes).

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| EXPI | smallint | N | Expiry type number = primary key; referenced by `vvCREXPREC.EXPIIDX` | 1..200, 272; not contiguous | profiled; `R0_GetDraftList.sql` lines 351, 571 (`cr.EXPI = A.EXPIIDX`), `rpt.get_crew_certifications.sql` line 100 (`A.EXPIIDX = C.EXPI`) |
| SHORTDESC | nchar(6) | Y | Short certificate code shown to schedulers and returned by the planner as `Certificate_Code` (MED, PPC, IFR, DG, A320DT, RC332, LAND2, TOFF3N ...) | blank-padded, 5 rows blank, unique among non-blank | `R0_GetDraftList.sql` line 352; `rpt.get_crew_certifications.sql` line 14 |
| DESC_ | nchar(20) | Y | Certificate description (`Certificate_Description`), French/English mixed | blank-padded; not unique | `R0_GetDraftList.sql` line 353; `rpt.get_crew_certifications.sql` line 15 |
| CREWCODE1 | smallint | Y | 1st **activity (schedule) code that renews this expiry**: `-CREWCODE1 = CRCODES.ID` of the roster code (inference, strongly supported: all 154 non-zero values across CREWCODE1..10 match a `CRCODES` row when negated and the code names correspond, e.g. REUI -> `REUI`, EPT/EPTP -> `EPTP`, DG -> `DG`, FDMEET -> `DV1`,`DV2`,`DV3`, LAND -> `PPC2`,`PPC3`,`ALO3`) | positive number n = `CRCODES.ID = -n` (CRCODES.ID is 0 or negative); 0/NULL = none; non-zero in 66 rows (83 NULL) | profiled; not used by any procedure |
| CREWCODE2 | smallint | Y | 2nd renewing activity code (same encoding) | non-zero in 27 rows | profiled |
| CREWCODE3 | smallint | Y | 3rd renewing activity code | non-zero in 13 rows | profiled |
| CREWCODE4 | smallint | Y | 4th renewing activity code | non-zero in 13 rows | profiled |
| CREWCODE5 | smallint | Y | 5th renewing activity code | non-zero in 13 rows | profiled |
| CREWCODE6 | smallint | Y | 6th renewing activity code | non-zero in 9 rows | profiled |
| CREWCODE7 | smallint | Y | 7th renewing activity code | non-zero in 4 rows | profiled |
| CREWCODE8 | smallint | Y | 8th renewing activity code | non-zero in 3 rows | profiled |
| CREWCODE9 | smallint | Y | 9th renewing activity code | non-zero in 3 rows | profiled |
| CREWCODE10 | smallint | Y | 10th renewing activity code | non-zero in 3 rows | profiled |
| CREWCODE11..CREWCODE20 (10 columns: CREWCODE11, CREWCODE12, CREWCODE13, CREWCODE14, CREWCODE15, CREWCODE16, CREWCODE17, CREWCODE18, CREWCODE19, CREWCODE20) | smallint | Y | 11th..20th renewing activity codes (spare slots) | all 0/NULL in the data | profiled |
| POS | binary(3) | Y | **Bitmap of positions** the expiry applies to: bit (`vvPositions.ID` - 1) set = applies | byte `(ID-1)/8 + 1`, mask `2^((ID-1)%8)`; bits 1-8 meaningful (CM, PO, ME, SP, DV, DA, AB, SU); 185 of 188 rows non-zero | `R0_GetDraftList.sql` lines 364-372; `rpt.get_crew_certifications.sql` lines 58-68 |
| CREWCAT | binary(30) | Y | **Bitmap of crew categories to INCLUDE**: the expiry applies only to crew holding at least one set category; empty bitmap = applies to everybody (subject to position/aircraft) | bit (`CREWCAT.CREWCAT` - 1), converted `CONVERT(binary(32), E.CrewCat)`; 32 rows non-empty | `R0_GetDraftList.sql` lines 382-391; `rpt.get_crew_certifications.sql` lines 18-28 |
| DAYTYP | tinyint | Y | Rule that turns `MAXDUE` into an expiry date from the last check date (inferred from data, see 5): 1 = `MAXDUE` is a number of **days**; 2 = **months, expiry rolled to the end of the month** (75% of expiry dates fall on a month end); 5 = **months, same-day anniversary** (17% month-end); 4 = no fixed validity period (event/one-off items such as MEL, CINDOC, WB, RNAV); 0 = none/undefined; 3 and 6 = rare variants (1 and 7 types) | counts: 0 = 8 rows, 1 = 21, 2 = 53, 3 = 1, 4 = 8, 5 = 90, 6 = 7 | profiled (compared with `vvCREXPREC.EXPIDATE - CHKLAST`); not used by any procedure |
| EXTINFO | tinyint | Y | "Extended information" code - unknown meaning (possibly the type of extra data recorded with the check). Not used by any procedure | 0 (62 rows), 12 (89), 10 (14), 9 (12), 8 (4), 1,3,5,14,15,19 (1 each) | profiled; unknown |
| MINDUE | smallint | Y | Inferred: lead window in **days** before the due date (warning / early-renewal window). Not used by any procedure | 0 (30 rows), 90 (119), 30 (22), 45 (10), 60 (4), 1, 10, 99 (1 each) | profiled; naming inference |
| MAXDUE | smallint | Y | Validity length of the expiry after the last check, in the unit given by `DAYTYP` (days for 1, months for 2/5): e.g. MED 12 (months), IFR 24, PPC 6, HAT/EPTP 36, LAND* 90 (days), TOFF/LAND night 180 (days). `9999` = effectively never expires (ETOPS in-flight experience), 0 = no validity length | 0 (19), 1, 3 (4), 6 (19), 12 (77), 24 (13), 36 (33), 45 (2), 50, 90 (11), 99, 180 (4), 182, 9999 (2) | profiled (e.g. average gap between last check and expiry date is 90 days for the DAYTYP 1 / MAXDUE 90 types, about 1,090 days for 36-month types); not used by any procedure |
| DISPBASEM | tinyint | Y | Inferred: show the expiry in the crew member's "base month" display (cf. `vvCREWDB.BASEMONTH`) | 0 (173 rows), 1 (15 rows, mostly cabin-crew training items such as THE3, FAIDI, DGCA, SIM3, SIM1, CRM, THE1, PBS3, FIRE, FAID, DEFIB, B737, A320) | profiled; naming inference |
| SEVERITY | tinyint | Y | Severity/behaviour flags of a lapsed expiry - looks like a bit mask (values 0, 4, 6, 12, 14, 32, 36, 46 = combinations of 2, 4, 8, 32). Meaning of each bit unknown | 14 (81 rows), 4 (57), 46 (24), 0 (9), 12 (8), 32 (7), 6, 36 (1 each) | profiled; unknown |
| FORMULA_NO | tinyint | Y | Special computation formula number for the expiry date (0 = standard rule from `DAYTYP`/`MAXDUE`). Unknown details | 0 (149), 9 (31 types: IFR, SYS, SIM1, CRM, RNP10, DEICEA, CAT2G, CAT3G and fleet variants), 7 (6), 3 (1), 5 (1) | profiled; unknown |
| RTECAT | binary(4) | Y | Bitmap of route categories (inference from name) | all zero in all 188 rows | profiled |
| MULT_AC | binary(12) | Y | **Bitmap of aircraft types** the expiry applies to. **Bit index = `vvAIRCTYPE.ACORDER` - 1 (NOT `ACTYPE`)** | byte `(ACORDER-1)/8 + 1`, mask `2^((ACORDER-1)%8)`; ACORDER 1=332, 2=333, 8=320, 17=321, 19=32Q, 20=TRN ...; 183 of 188 rows non-zero | `R0_GetDraftList.sql` lines 356-363 (`@CertAircraftOrders` = 1,2,8,17,19,20); `rpt.get_crew_certifications.sql` lines 44-55 |
| TXTCOLOR | int | Y | Display colour of the expiry text in AIMS screens (inference: 24-bit Windows colour value, max 11,534,387 < 2^24) | 0 = default (112 rows); 13 distinct values | profiled; naming inference |
| REALTIMCK | tinyint | Y | Probably "real-time check" flag (validate while rostering). Unused: 0 in all rows | 0 | profiled |
| AIRPBRIEF | tinyint | Y | Probably "airport briefing" flag. Unused: 0 in all rows | 0 | profiled |
| ISSUEWRN | tinyint | Y | Probably "issue warning" - raise a warning when the expiry lapses | 1 = 137 rows, 0 = 51 | profiled; naming inference |
| SCHECODECHANGED | tinyint | Y | Probably "schedule codes changed" flag set when `CREWCODEn` were edited (re-computation needed) | 1 = 97 rows, 0 = 91 | profiled; naming inference |
| EXCLUDECAT | binary(30) | Y | **Bitmap of crew categories to EXCLUDE**: crew holding any set category are not subject to this expiry | same bit layout as `CREWCAT`; only 3 rows non-empty (categories 99 "PERMANENT 737", 127 "ENTRAINEMENT MFF - start 2023") | `R0_GetDraftList.sql` lines 393-402; `rpt.get_crew_certifications.sql` lines 31-41 |
| EFFECTIVE_BEG | smallint | Y | First day on which the definition is in force (day number since 1980-01-01); 0 = no start | 72 rows non-zero; latest 2026-07-01 | profiled; `rpt.get_crew_certifications.sql` (commented-out use) |
| EFFECTIVE_END | smallint | Y | Last day the definition is in force; **0 = open-ended (still valid)** - NOT 32767 as in other tables | 0 for 56 rows; 131 rows ended in the past (earliest 2000-01-01); 1 row ends in the future (SIMACT, 2027-12-31) | profiled; `R0_GetDraftList.sql` lines 375, 386, 398 (`WHERE E.EFFECTIVE_END = 0`); `rpt.get_crew_certifications.sql` lines 73, 172 |
| E_CREW_VISIBLE | tinyint | Y | Probably "visible in the e-Crew (crew self-service portal)" flag | 1 = 87 rows, 0 = 101 | profiled; naming inference (category 173 "eCrew Access" exists) |
| EXPUSERDEFINED | tinyint | Y | Probably "user-defined expiry" flag. 0 in all rows | 0 | profiled |
| USERDEFINEDCATEGORY | smallint | Y | Probably a user-defined category for the expiry. NULL in 79 rows, 0 in 109, never non-zero | NULL/0 | profiled |
| KINDFLIGHT | tinyint | Y | Probably the kind of flight the expiry relates to. NULL in 80 rows, 0 in 108, never non-zero | NULL/0 | profiled |

(All 46 columns are covered: CREWCODE1..CREWCODE10 individually, CREWCODE11..CREWCODE20 in the grouped row.)

## 4. Keys & relationships
- Primary key `EXPI`.
- `vvCREXPREC.EXPIIDX = EXPI.EXPI` (1:N: one type -> many crew records; measured 0 orphans among the 145,012 records). Predicates: `INNER JOIN #CertRules cr ON cr.EXPI = A.EXPIIDX` (`R0_GetDraftList.sql` line 570-571), `LEFT OUTER JOIN TSC.dbo.EXPI C ON A.EXPIIDX = C.EXPI` (`rpt.get_crew_certifications.sql` line 100).
- `EXPI.POS` -> `vvPositions.ID` via bitmap (N:M). `EXPI.MULT_AC` -> `vvAIRCTYPE.ACORDER` via bitmap (N:M; note ACORDER, not ACTYPE; `CREWQUAL.AC` is an ACTYPE, so match through `vvAIRCTYPE` or compare the IATA code as the procedures do). `EXPI.CREWCAT`/`EXCLUDECAT` -> `CREWCAT.CREWCAT` via bitmap (N:M).
- `EXPI.CREWCODEn` -> `CRCODES.ID` as `-CREWCODEn` (inference; schedule/activity code that renews the expiry).
- The planner decides whether a certificate type applies to a crew member by combining: position code in the position list, aircraft IATA code in the aircraft list, no excluded category held, and (no include categories or at least one included category held) - `R0_GetDraftList.sql` lines 568-587.

## 5. Encoding conventions & gotchas
- **Bitmaps:** all four bitmaps are little-endian bit arrays: bit `k` (0-based) is in byte `k/8 + 1` (1-based `SUBSTRING`) with mask `2^(k%8)`. Positions: k = `vvPositions.ID - 1`. Aircraft: k = `vvAIRCTYPE.ACORDER - 1`. Categories: k = `CREWCAT - 1`. The columns are shorter than the largest bit index the planner scans, so the code converts them to `binary(32)`/`binary(12)` first (`CONVERT(binary(32), E.CrewCat)`), which zero-pads. (`SPEFREC2/3.CATEG1/2` use a different offset - category bits start at byte 3.)
- **Live-definition filter:** the planner uses `EFFECTIVE_END = 0` (open-ended) plus `ISNULL(SHORTDESC,'') != ''`. `EFFECTIVE_END` is 0 for "no end" here, unlike `ACTIVEEND = 32767` elsewhere. A definition that is still valid but has a future end date (currently only SIMACT, ending 2027-12-31) is therefore ignored by the planner; one that ended in the past correctly drops out. Records of ended types still exist in `vvCREXPREC` (89,782 of 145,012 records belong to ended types), so always filter by `EFFECTIVE_END = 0` when you want current obligations.
- R0 additionally ignores the types `WB`, `IFRLIC`, `SIMDUT` (`@ExcludedCertCodes`) and only evaluates aircraft with `ACORDER` in (1,2,8,17,19,20) = 332, 333, 320, 321, 32Q, TRN (`@CertAircraftOrders`); a candidate on any other type makes R0 fail with `EXPIRY_CHECK_NOT_CONFIGURED`.
- **Validity computation (inferred from `vvCREXPREC`):** the stored `vvCREXPREC.EXPIDATE` already contains the result; the planner never recomputes it. `DAYTYP`/`MAXDUE` are only needed to *explain* a date (e.g. "12 months, end-of-month").
- **Position list built from `DESC_` is fragile** (see `vvPositions.md`): R0 matches the candidate's two-letter `CODE` against a string built from `vvPositions.DESC_` and can never match DV/DA.
- **Variants per fleet:** the same business certificate may exist as several types (e.g. SYSTEM EXAM: `SYS` (generic, retired), `SYS320`, `SYS332`, `SYS738` (retired) ...). Use `SHORTDESC` + `EFFECTIVE_END = 0` + the aircraft/position bitmap to pick the live one for a crew member.
- Names contain accents (Réunion, "VOL OPÉRÉ ENV ETOPS", "PNC 1ere année"); the database collation is accent-sensitive, so type them exactly.
- 5 rows have a blank `SHORTDESC` and are excluded by every consumer.

## 6. How the planner-assist procedures use it
- `dbo.R0_GetDraftList` (candidate crew list for a pairing): builds three temp tables once - `#CertRules` (live types with `Aircraft_List` and `Position_List` decoded from `MULT_AC` and `POS`), `#CertCatInc` and `#CertCatExc` (category names decoded from `CREWCAT` and `EXCLUDECAT`) - and then, for each pool member, aggregates `Certificate_Code (expiry date)` for every `vvCREXPREC` record with `EXPIDATE < @PairingEndNum` whose type matches the member's position, aircraft and categories. The result is the `Expired_Cert_List` / "Expiry_Warnings" shown for each candidate: i.e. the certificate would be expired at the end of the pairing (regulatory/qualification currency check: a crew member with a lapsed PPC, medical, route check, etc. must not be scheduled).
- `rpt.get_crew_certifications`: for one crew member lists each live certificate type that applies to his position/aircraft/categories with its `EXPIDATE`; it first builds `#TempCertificates` with `Crew_Categories_To_Include`, `Crew_Categories_To_Exclude`, `Aircraft_List` (restricted to ACORDER 1,2,8,17,19,20) and `Position_List` (IDs 1-10), skipping `SHORTDESC = 'WB'`.
- No other procedure reads `EXPI` (R1-R5 do not check currency).

## 7. Typical query patterns
```sql
-- live certificate types with validity rule
SELECT e.EXPI, LTRIM(RTRIM(e.SHORTDESC)) AS Certificate_Code, LTRIM(RTRIM(e.DESC_)) AS Certificate_Description,
       e.DAYTYP, e.MAXDUE
FROM TSC.dbo.EXPI AS e
WHERE e.EFFECTIVE_END = 0 AND LTRIM(RTRIM(ISNULL(e.SHORTDESC, N''))) <> N''
ORDER BY e.SHORTDESC;

-- certificates of one crew member with real dates (EXPIDATE 0 = not set, 32767 = never expires)
SELECT LTRIM(RTRIM(e.SHORTDESC)) AS Certificate_Code,
       CASE WHEN r.CHKLAST  = 0     THEN NULL ELSE CAST(DATEADD(DAY, r.CHKLAST,  '1980-01-01') AS DATE) END AS Last_Check,
       CASE WHEN r.EXPIDATE IN (0, 32767) THEN NULL ELSE CAST(DATEADD(DAY, r.EXPIDATE, '1980-01-01') AS DATE) END AS Expiry_Date,
       r.EXPIDATE
FROM TSC.dbo.vvCREXPREC AS r
JOIN TSC.dbo.EXPI       AS e ON e.EXPI = r.EXPIIDX
WHERE r.CREW_ID = @crew_id
  AND e.EFFECTIVE_END = 0 AND LTRIM(RTRIM(ISNULL(e.SHORTDESC, N''))) <> N''
ORDER BY e.SHORTDESC;

-- which live types apply to captains on the A330 (position bit 1, aircraft ACORDER 1 = 332)
SELECT LTRIM(RTRIM(e.SHORTDESC)) AS Certificate_Code
FROM TSC.dbo.EXPI AS e
WHERE e.EFFECTIVE_END = 0
  AND (CONVERT(tinyint, SUBSTRING(CONVERT(binary(32), e.POS),     1, 1)) & 1) > 0   -- position ID 1 (CM): byte 1, mask 1
  AND (CONVERT(tinyint, SUBSTRING(CONVERT(binary(12), e.MULT_AC), 1, 1)) & 1) > 0;  -- ACORDER 1 (332): byte 1, mask 1

-- number of crew whose record of a type is already past due (aggregate)
SELECT LTRIM(RTRIM(e.SHORTDESC)) AS Certificate_Code, COUNT(*) AS Past_Due_Records
FROM TSC.dbo.vvCREXPREC AS r JOIN TSC.dbo.EXPI AS e ON e.EXPI = r.EXPIIDX
WHERE e.EFFECTIVE_END = 0 AND r.EXPIDATE BETWEEN 1 AND DATEDIFF(DAY, '1980-01-01', GETDATE()) - 1
GROUP BY e.SHORTDESC ORDER BY Past_Due_Records DESC;
```

## 8. Data profile (measured 2026-11-03)
- 188 rows; 56 with `EFFECTIVE_END = 0` of which 52 have a non-blank `SHORTDESC` (the live named types; 4 live rows are blank slots), 132 definitions with an end date (131 ended in the past, 1 ends 2027-12-31). R0 additionally excludes `WB`/`IFRLIC`/`SIMDUT`: only IFRLIC is live, so R0 evaluates 51 types.
- Position coverage (types whose `POS` bitmap contains the position): CM 159, PO 152, ME 44, SP 36, DV 31, DA 18, AB 31, SU 25 (all 188 rows counted).
- Aircraft coverage (types containing the aircraft; ACORDER): 332 125, 333 120, 321 89, 32Q 87, 313 54, 738 49, 320 47, 737 25, 752 9, L15 3, W7S8 3, 738C 2, 763 1, 737E 1, 738T 1, 733 1.
- Categories: 32 types have an include bitmap, 3 have an exclude bitmap.
- Live types with their decoded position/aircraft/category bitmaps and the number of crew records they have in `vvCREXPREC` (145,012 records in total, any crew, including crew who left):

| EXPI | SHORTDESC | DESC_ | DAYTYP | MINDUE | MAXDUE | Positions | Aircraft | Include categories (CREWCAT numbers) | Exclude categories | Records in vvCREXPREC |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | MED | MEDICAL | 2 | 30 | 12 | CM,PO | 332,333,320,321,32Q |  |  | 1281 |
| 2 | REUI | Réunion Instructeurs | 2 | 90 | 6 | CM,PO | 332,333,320,321,32Q | 104 |  | 163 |
| 5 | UKETA | UK - ETA TRAVEL AUTH | 1 | 90 | 0 | CM,PO,ME,SP,DV,DA,AB,SU | 332,333,320,321,32Q |  |  | 2904 |
| 6 | REUP | Réunion Pilotes | 5 | 90 | 12 | CM,PO | 332,333,320,321,32Q |  |  | 899 |
| 7 | FDMEET | FD Meeting | 5 | 90 | 6 | DV,AB | 332,333,320,321,32Q |  |  | 1338 |
| 13 | EPT | EPT Requirements | 5 | 90 | 12 | CM,PO,ME | 332,333,320,321,32Q |  |  | 1322 |
| 19 | DG | Dangerous Goods | 5 | 30 | 24 | CM,PO,ME | 332,333,320,321,32Q |  |  | 1330 |
| 20 | DGPNC | Dangerous Goods | 2 | 0 | 24 | DV,AB,SU | 332,333,320,321,32Q |  |  | 3122 |
| 33 | PVTA | Check Pilot Trn | 5 | 90 | 36 | CM,PO | 332,333,320,321,32Q | 1,2,132,133,134,151 |  | 107 |
| 34 | PPCM | PPC Monitor | 5 | 90 | 12 | CM | 332,333,320,321,32Q | 32 |  | 2 |
| 35 | PVTAM | CCP Monitor | 5 | 90 | 12 | CM,PO | 332,333,320,321,32Q | 34 |  | 51 |
| 36 | PASS | Passeport | 1 | 0 | 0 | CM,PO,ME,DV,DA,AB,SU | 332,333,320,321,32Q |  |  | 5412 |
| 37 | MOT | RAIC/CIZR | 1 | 90 | 0 | CM,PO,ME,DV,AB,SU | 332,333,320,321,32Q |  |  | 4223 |
| 41 | IFRLIC | Suivi Lic. IFR | 1 | 0 | 90 | CM,PO | 332,333,320,321,32Q |  |  | 1178 |
| 51 | MONIT | Moniteur instructeur | 5 | 90 | 36 | CM,PO,SP | 332,333,320,321,32Q | 2,14,21,22,110,111,112,113,114,137,151,154,157 |  | 200 |
| 56 | ETFLT | VOL OPÉRÉ ENV ETOPS | 5 | 60 | 12 | CM,PO,ME | 332,333,320,321,32Q |  |  | 961 |
| 57 | PVAM2 | Moniteur PVA 2 ans | 5 | 90 | 24 | CM,PO,SP | 332,333,313,738,321,32Q | 1,34,132,133,134 |  | 65 |
| 59 | BKLT | Aviation Booklet | 1 | 90 | 0 | CM,PO,ME,SP | 332,333,320,321,32Q |  |  | 1146 |
| 70 | MPVA | Moniteur TC - 3 ans | 0 | 90 | 0 | CM,SP | 332,333,321,32Q | 130,131 |  | 3 |
| 82 | ETP321 | EN VOL - ETOPS  A321 | 2 | 90 | 9999 | CM,PO | 320,321,32Q |  |  | 746 |
| 83 | ETP330 | EN VOL - ETOPS A330 | 2 | 90 | 9999 | CM,PO | 332,333 |  |  | 452 |
| 88 | FAIDI | INSTRUCTOR FIRST AID | 6 | 30 | 1 | DV,AB | 332,333,320,321,32Q | 42 |  | 89 |
| 89 | CPRI | INSTRUCTOR CPR | 2 | 30 | 12 | SP,DV,AB | 332,333,320,321,32Q | 40 |  | 70 |
| 100 | INI | INITIAL TRAINING | 1 | 10 | 90 | SP,DV,AB | 332,333 | 46 |  | 0 |
| 105 | GEN | GEN Requirements | 5 | 60 | 12 | CM,PO | 332,333,320,321,32Q |  |  | 926 |
| 106 | A321 | A320 Qual / PPC | 5 | 60 | 6 | CM,PO | 320,321,32Q |  |  | 926 |
| 107 | A330 | A330 Qual / PPC | 5 | 60 | 6 | CM,PO,SP | 332,333 |  |  | 925 |
| 108 | SYS320 | SYSTEM EXAM 320 | 5 | 90 | 12 | CM,PO | 320,321,32Q |  |  | 1011 |
| 115 | RC332 | ROUTE CHECK 332 | 5 | 90 | 12 | CM,PO | 332,333 |  | 127 | 913 |
| 118 | SYS332 | SYSTEM EXAM 330 | 5 | 90 | 12 | CM,PO | 332,333 |  |  | 1076 |
| 135 | RS332 | RIGHT SEAT 332 | 5 | 90 | 12 | CM,PO | 332,333 | 140 |  | 207 |
| 160 | NEW | PNC 1ere année 90jrs | 1 | 30 | 90 | DV,AB,SU | 332,333,320,321,32Q | 90 |  | 1463 |
| 161 | RS320 | RIGHT SEAT 320 | 5 | 90 | 12 | CM,PO | 321,32Q | 132,151,154 |  | 303 |
| 166 | A320DT | A320 Differences | 2 | 90 | 36 | CM,PO,SP | 320 |  |  | 2872 |
| 167 | A320D | A320 Differences | 2 | 30 | 12 | DV,AB,SU | 320 |  |  | 2388 |
| 170 | LANDMF | LANDING MFF | 1 | 45 | 45 | CM,PO | 332,333,320,321,32Q | 127 |  | 79 |
| 171 | LAND3 | LANDING 330 | 1 | 45 | 90 | CM,PO | 332,333 |  |  | 471 |
| 172 | LAND2 | LANDING 321 | 1 | 45 | 90 | CM,PO | 320,321,32Q |  |  | 780 |
| 173 | LEG330 | Line Exposure 330 | 1 | 45 | 90 | CM,PO | 332,333 |  |  | 465 |
| 174 | LEG321 | Line Exposure 321 | 1 | 45 | 90 | CM,PO | 320,321,32Q |  |  | 765 |
| 180 | RC320 | ROUTE CHECK 320 | 5 | 90 | 12 | CM,PO | 320,321,32Q |  | 127 | 878 |
| 181 | LCMFF | LINE CHECK MFF | 5 | 90 | 12 | CM,PO | 332,333,321,32Q | 127 |  | 4 |
| 190 | ANNP | ANNUEL PELESYS | 2 | 45 | 12 | DV,AB,SU | 332,333,320,321,32Q |  |  | 3123 |
| 191 | FAIDP | FIRST AID PELESYS | 2 | 30 | 36 | DV,AB,SU | 332,333,320,321,32Q |  |  | 3124 |
| 192 | FIREP | FIRE PELESYS | 2 | 30 | 36 | DV,AB,SU | 332,333,320,321,32Q |  |  | 3123 |
| 193 | TOFF2 | TAKE OFF 320 | 1 | 45 | 90 | CM,PO | 320,321,32Q |  |  | 495 |
| 194 | TOFF3 | TAKE OFF 330 | 1 | 45 | 90 | CM,PO | 332,333 |  |  | 340 |
| 195 | TOFFMF | TAKE OFF MFF | 1 | 45 | 45 | CM,PO | 332,333,320,321,32Q | 127 |  | 3 |
| 196 | TOFF2N | TAKE OFF 321 NIGHT | 1 | 90 | 180 | CM,PO | 320,321,32Q |  |  | 449 |
| 197 | TOFF3N | TAKE OFF 330 NIGHT | 1 | 90 | 180 | CM,PO | 332,333 |  |  | 304 |
| 198 | LAND2N | LANDING 321 NIGHT | 1 | 90 | 180 | CM,PO | 320,321,32Q |  |  | 449 |
| 199 | LAND3N | LANDING 330 NIGHT | 1 | 90 | 180 | CM,PO | 332,333 |  |  | 304 |

## 9. Open questions / confidence
- High: purpose, key, `SHORTDESC`/`DESC_`, the bitmap layouts and their decode (taken from working planner code), `EFFECTIVE_END = 0` semantics, join to `vvCREXPREC`.
- Medium-high (inference verified on data): `CREWCODEn` = `-CRCODES.ID`; `DAYTYP` 1 = days, 2 = months/end-of-month, 5 = months/anniversary; `MAXDUE` = validity length.
- Low / unknown: `EXTINFO`, `MINDUE` (warning window?), `SEVERITY` bit meanings, `FORMULA_NO`, `DISPBASEM`, `REALTIMCK`, `AIRPBRIEF`, `ISSUEWRN`, `SCHECODECHANGED`, `E_CREW_VISIBLE`, `EXPUSERDEFINED`, `USERDEFINEDCATEGORY`, `KINDFLIGHT`, `TXTCOLOR`: names suggest a meaning but nothing in the repo uses them; treat as informational.
- Verified count: 52 live named types; R0's exclusion list removes only IFRLIC (WB and SIMDUT are ended definitions), leaving 51 (measured: 51 rows pass `EFFECTIVE_END = 0`, non-blank `SHORTDESC` and the exclusion list).
