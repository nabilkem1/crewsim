# vvCREWDB  (View)  - Crew master record (one row per crew member; 287 columns, mostly personal/HR data)

## 1. Purpose & business meaning
`TSC.dbo.vvCREWDB` is the AIMS **crew master ("crew database") view**: one row per crew member (pilots and cabin crew, active and former) holding the person's identity, contact details, nationality and travel documents, licences, next of kin, pay/HR attributes, scheduling settings and some per-person block/limit settings. It is the "who is this crew member" record; everything that *happens* to the crew member lives in other tables (`ROSTER` duties, `CREWQUAL` qualifications, `CREWCATEG` categories, `vvCREXPREC` expiries) keyed by the same `ID`.
Grain: **1 row = 1 crew member**; `ID` is unique (6,151 rows, 6,151 distinct ids, identical to the 6,151 rows of `ROSTERID`). Rows are never deleted when a crew member leaves (category "No longer with Air Transat" exists; 2,823 of the 6,151 crew currently hold a valid qualification).
Writers: AIMS crew administration and HR interfaces (name, addresses, documents), AIMS itself (audit stamp `USER_`/`UPDDATE`/`UPDTIME`), schedulers (block dates, swap settings). Readers in this repo: existence checks for the crew id parameter in R0-R5, name search (`rpt.lookup_crew`), nationality for nationality-based custom rules (R1), and the blocked-date ranges ("PVHR" / mini-bloc) in R0, R5 and `rpt.CalculateCrewFTC`.

### PRIVACY - read before querying
Most of the 287 columns are personal, HR or financial data (name, e-mail, addresses, phones, next of kin, marital/child data, passport/visa/licence/permit numbers, bank and credit-card data, social-security number, salary figures, a password-like binary). **A text-to-SQL agent must only ever select the operational columns listed in section 7** (`ID`, `NATCOD` for code-level aggregates, the `TSC_BLOCKDATES_*` ranges) and never output names, dates of birth, contact data or document numbers. Individual crew ids are person identifiers: prefer aggregates. In this document every personal column is described by meaning only; for them only "non-blank counts" were measured.

## 2. Physical facts
- `TSC.dbo.vvCREWDB`, **VIEW** (definition not retrievable: `view_defs.json` has `def = null`), no row count/index metadata. Measured **6,151 rows**, 287 columns (`cid` 1..287).
- Unique key (by data): `ID`. Because it is a view over an AIMS table, the underlying primary key is presumably `ID`; lookups by `ID` are cheap (the procedures do `WHERE ID = @id`); `Name LIKE '%x%'` (`rpt.lookup_crew`) is a scan of 6,151 rows (acceptable).
- Very wide rows (about 3963 bytes per row, mostly fixed-width nchar): avoid `SELECT *` (privacy and cost); the planner only reads `ID`, `NATCOD`, `NAME` and the eight `TSC_BLOCKDATES_*` columns.
- Character widths below are `len/2` of columns.json (metadata gives bytes). All columns are nullable by metadata, but measured NULL counts are 0 in every column checked.

## 3. Column dictionary
All 287 columns are listed, grouped logically. "profiled" means an aggregate measurement (non-blank / non-zero counts, min/max of non-personal numeric fields) on 2026-11-03; no personal value was read. Day numbers are days since 1980-01-01 (see section 5).

### 3.1 Keys and identity (personal data - describe only)
Names and employee identifiers are personal data: they were counted (non-blank) but never listed.

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| ID | int | Y | Crew member internal AIMS id; **primary key of the view** and the crew id used by every other AIMS table (`ROSTER.ID`, `ROSTERID.ID`, `CREWQUAL.ID`, `CREWCATEG.ID`, `vvCREXPREC.CREW_ID`) | int; unique, 6,151 distinct = 6,151 rows = every `ROSTERID` row; no NULL | profiled; `R0..R5` existence checks `WHERE ID = @Crew_ID`; `rpt.lookup_crew.sql` |
| NAME | nchar(50) | Y | Crew member's display name (surname/given-name combination as shown in AIMS); the planner returns it as `Crew_Name` in `rpt.lookup_crew`. Identical to `ROSTERID.NAME` in all 6,151 rows. **Personal data - never print** | nchar(50), blank-padded; 6,150 of 6,151 non-blank; no comma inside | profiled (counts only); `rpt.lookup_crew.sql` (`Name LIKE '%'+@crew_name+'%'`) |
| SHORTNAME | nchar(6) | Y | Crew member's short name / abbreviation. Personal data | nchar(6); 20 non-blank | profiled (count only) |
| FULLNAME | nchar(50) | Y | Crew member's full legal name (alternate long form). Personal data | nchar(50); 566 non-blank | profiled (count only) |
| IVR_NAME | nchar(30) | Y | Name recorded for the phone (IVR) system. Personal data | nchar(30); all blank | profiled (count only) |
| SECOND_ID | int | Y | Secondary crew id (second system id) - unknown purpose | int; 0 in all rows | profiled |
| EMPLSNR | smallint | Y | Employee-seniority-related number (naming inference; **employee identifier class - do not print**). Not the seniority used by the planner (`ROSTERID.SENIOR`, `CREWQUAL.SENIOR`) | smallint; non-zero in 1,153 rows, 1,154 distinct values | profiled (aggregate only) |
| PAYNUM | nchar(10) | Y | Payroll number. Employee identifier | nchar(10); all blank | profiled (count only) |
| SWIPECARD | nchar(18) | Y | Access/swipe card number. Identifier | nchar(18); all blank | profiled (count only) |
| SUPERVID | int | Y | Supervisor's crew id (naming inference) | int; 0 in all rows | profiled |
| SPRVSOURCE | tinyint | Y | Supervisor source flag (naming inference) | tinyint; 0 in all rows | profiled |

### 3.2 Contact details and addresses (personal data)
Never selected or profiled beyond non-blank counts.

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| EMAIL | nchar(70) | Y | Primary e-mail address | nchar(70); 4,433 non-blank | naming inference; not used by any procedure |
| EMAIL2 | nchar(70) | Y | Secondary e-mail address | nchar(70); 430 non-blank | naming inference; not used by any procedure |
| ADDRESSES_1 | nchar(40) | Y | Street address line 1 of the home address | nchar(40); line 1 non-blank in 5,714 rows | naming inference; not used by any procedure |
| ADDRESSES_2 | nchar(40) | Y | Street address line 2 of the home address | nchar(40); line 1 non-blank in 5,714 rows | naming inference; not used by any procedure |
| ADDRESSES_3 | nchar(40) | Y | Street address line 3 of the home address | nchar(40); line 1 non-blank in 5,714 rows | naming inference; not used by any procedure |
| CITY | nchar(30) | Y | Home city | nchar(30); 5,555 non-blank | naming inference; not used by any procedure |
| STATE | nchar(2) | Y | Home state/province code | nchar(2); 5,537 non-blank | naming inference; not used by any procedure |
| ZIP | nchar(10) | Y | Home postal code | nchar(10); 5,547 non-blank | naming inference; not used by any procedure |
| MAILADDRESSES_1 | nchar(40) | Y | Street address line 1 of the mailing address (when different from home) | nchar(40); rarely used (line 1: 9 non-blank, lines 2-3 blank) | naming inference; not used by any procedure |
| MAILADDRESSES_2 | nchar(40) | Y | Street address line 2 of the mailing address (when different from home) | nchar(40); rarely used (line 1: 9 non-blank, lines 2-3 blank) | naming inference; not used by any procedure |
| MAILADDRESSES_3 | nchar(40) | Y | Street address line 3 of the mailing address (when different from home) | nchar(40); rarely used (line 1: 9 non-blank, lines 2-3 blank) | naming inference; not used by any procedure |
| MAILCITY | nchar(30) | Y | Mailing address city | nchar(30); 2 non-blank | naming inference; not used by any procedure |
| MAILSTATE | nchar(2) | Y | Mailing address state/province | nchar(2); 2 non-blank | naming inference; not used by any procedure |
| MAILZIP | nchar(10) | Y | Mailing address postal code | nchar(10); 2 non-blank | naming inference; not used by any procedure |
| PHONE_1_NUMBER | nchar(20) | Y | Telephone number slot 1 | nchar(20); non-blank counts 5,419 / 1,836 / 141 / 56 / 9 / 31 for slots 1-6 | naming inference; not used by any procedure |
| PHONE_2_NUMBER | nchar(20) | Y | Telephone number slot 2 | nchar(20); non-blank counts 5,419 / 1,836 / 141 / 56 / 9 / 31 for slots 1-6 | naming inference; not used by any procedure |
| PHONE_3_NUMBER | nchar(20) | Y | Telephone number slot 3 | nchar(20); non-blank counts 5,419 / 1,836 / 141 / 56 / 9 / 31 for slots 1-6 | naming inference; not used by any procedure |
| PHONE_4_NUMBER | nchar(20) | Y | Telephone number slot 4 | nchar(20); non-blank counts 5,419 / 1,836 / 141 / 56 / 9 / 31 for slots 1-6 | naming inference; not used by any procedure |
| PHONE_5_NUMBER | nchar(20) | Y | Telephone number slot 5 | nchar(20); non-blank counts 5,419 / 1,836 / 141 / 56 / 9 / 31 for slots 1-6 | naming inference; not used by any procedure |
| PHONE_6_NUMBER | nchar(20) | Y | Telephone number slot 6 | nchar(20); non-blank counts 5,419 / 1,836 / 141 / 56 / 9 / 31 for slots 1-6 | naming inference; not used by any procedure |
| PHONE_1_COMKIND | tinyint | Y | Kind of communication of phone slot 1 (home, mobile, ...; code table not available) | tinyint code | naming inference; not used by any procedure |
| PHONE_2_COMKIND | tinyint | Y | Kind of communication of phone slot 2 (home, mobile, ...; code table not available) | tinyint code | naming inference; not used by any procedure |
| PHONE_3_COMKIND | tinyint | Y | Kind of communication of phone slot 3 (home, mobile, ...; code table not available) | tinyint code | naming inference; not used by any procedure |
| PHONE_4_COMKIND | tinyint | Y | Kind of communication of phone slot 4 (home, mobile, ...; code table not available) | tinyint code | naming inference; not used by any procedure |
| PHONE_5_COMKIND | tinyint | Y | Kind of communication of phone slot 5 (home, mobile, ...; code table not available) | tinyint code | naming inference; not used by any procedure |
| PHONE_6_COMKIND | tinyint | Y | Kind of communication of phone slot 6 (home, mobile, ...; code table not available) | tinyint code | naming inference; not used by any procedure |
| PHONEMSG_1 | tinyint | Y | Flag: messages (e.g. SMS/voice) may be sent to phone slot 1 | tinyint 0/1 | naming inference; not used by any procedure |
| PHONEMSG_2 | tinyint | Y | Flag: messages (e.g. SMS/voice) may be sent to phone slot 2 | tinyint 0/1 | naming inference; not used by any procedure |
| PHONEMSG_3 | tinyint | Y | Flag: messages (e.g. SMS/voice) may be sent to phone slot 3 | tinyint 0/1 | naming inference; not used by any procedure |
| PHONEMSG_4 | tinyint | Y | Flag: messages (e.g. SMS/voice) may be sent to phone slot 4 | tinyint 0/1 | naming inference; not used by any procedure |
| PHONEMSG_5 | tinyint | Y | Flag: messages (e.g. SMS/voice) may be sent to phone slot 5 | tinyint 0/1 | naming inference; not used by any procedure |
| PHONEMSG_6 | tinyint | Y | Flag: messages (e.g. SMS/voice) may be sent to phone slot 6 | tinyint 0/1 | naming inference; not used by any procedure |
| PHONEORDER_1 | tinyint | Y | Call-order rank of phone slot 1 when contacting the crew member | tinyint | naming inference; not used by any procedure |
| PHONEORDER_2 | tinyint | Y | Call-order rank of phone slot 2 when contacting the crew member | tinyint | naming inference; not used by any procedure |
| PHONEORDER_3 | tinyint | Y | Call-order rank of phone slot 3 when contacting the crew member | tinyint | naming inference; not used by any procedure |
| PHONEORDER_4 | tinyint | Y | Call-order rank of phone slot 4 when contacting the crew member | tinyint | naming inference; not used by any procedure |
| PHONEORDER_5 | tinyint | Y | Call-order rank of phone slot 5 when contacting the crew member | tinyint | naming inference; not used by any procedure |
| PHONEORDER_6 | tinyint | Y | Call-order rank of phone slot 6 when contacting the crew member | tinyint | naming inference; not used by any procedure |
| RESIDENCECTR | nchar(3) | Y | Residence country/centre code | nchar(3); 3,903 non-blank, 14 distinct values | naming inference; not used by any procedure |

### 3.3 Next of kin, family and physical data (personal / sensitive)
Never selected or profiled beyond non-blank counts.

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| KINNAME | nchar(30) | Y | Emergency contact (next of kin) name | nchar(30); 753 non-blank | naming inference; not used by any procedure |
| KINRLTN | nchar(14) | Y | Relationship of the emergency contact | nchar(14); 217 non-blank | naming inference; not used by any procedure |
| KINCONT | nchar(20) | Y | Emergency contact phone/contact | nchar(20); 740 non-blank | naming inference; not used by any procedure |
| MARSTATUS | smallint | Y | Marital status code | smallint code | naming inference; not used by any procedure |
| SPOUSID | int | Y | Crew id of the spouse when the spouse is also crew | int | naming inference; not used by any procedure |
| MARRIAGEDATE | nchar(8) | Y | Marriage date (text) | nchar(8); 4 non-blank | naming inference; not used by any procedure |
| CHILDBD_1 | smallint | Y | Birth date of child 1 (AIMS day number since 1980-01-01; used for family-related rules) | smallint, 0 = none | naming inference; not used by any procedure |
| CHILDBD_2 | smallint | Y | Birth date of child 2 (AIMS day number since 1980-01-01; used for family-related rules) | smallint, 0 = none | naming inference; not used by any procedure |
| CHILDBD_3 | smallint | Y | Birth date of child 3 (AIMS day number since 1980-01-01; used for family-related rules) | smallint, 0 = none | naming inference; not used by any procedure |
| CHILDBD_4 | smallint | Y | Birth date of child 4 (AIMS day number since 1980-01-01; used for family-related rules) | smallint, 0 = none | naming inference; not used by any procedure |
| CHILDBD_5 | smallint | Y | Birth date of child 5 (AIMS day number since 1980-01-01; used for family-related rules) | smallint, 0 = none | naming inference; not used by any procedure |
| CHILDBD_6 | smallint | Y | Birth date of child 6 (AIMS day number since 1980-01-01; used for family-related rules) | smallint, 0 = none | naming inference; not used by any procedure |
| CHILDBD_7 | smallint | Y | Birth date of child 7 (AIMS day number since 1980-01-01; used for family-related rules) | smallint, 0 = none | naming inference; not used by any procedure |
| CHILDBD_8 | smallint | Y | Birth date of child 8 (AIMS day number since 1980-01-01; used for family-related rules) | smallint, 0 = none | naming inference; not used by any procedure |
| CHILDBD_9 | smallint | Y | Birth date of child 9 (AIMS day number since 1980-01-01; used for family-related rules) | smallint, 0 = none | naming inference; not used by any procedure |
| CHILDBD_10 | smallint | Y | Birth date of child 10 (AIMS day number since 1980-01-01; used for family-related rules) | smallint, 0 = none | naming inference; not used by any procedure |
| SMOKER | tinyint | Y | Smoker flag (hotel/room preference) | tinyint | naming inference; not used by any procedure |
| PHYSICALINFO_HEIGHT | int | Y | Height | int | naming inference; not used by any procedure |
| PHYSICALINFO_WEIGHT | int | Y | Weight | int | naming inference; not used by any procedure |
| PHYSICALINFO_EYECLR | nchar(12) | Y | Eye colour | nchar(12); all blank | naming inference; not used by any procedure |
| PHYSICALINFO_HAIRCLR | nchar(12) | Y | Hair colour | nchar(12); all blank | naming inference; not used by any procedure |

### 3.4 Nationality, identity documents, licences (personal data)
Document numbers, dates and places are identifiers: never selected. Only **`NATCOD`** is used by the planner (R1 nationality rules).

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| NATCOD | nchar(3) | Y | **Nationality as ICAO country code** (3 letters) of the crew member's principal nationality. Joined to `vvCountries.UNCODE` to obtain the two-letter country code compared with `SPEFREC3.NATIONALITIES` in nationality-based custom rules | nchar(3); 5,263 of 6,151 non-blank, 32 distinct codes. Blank = nationality unknown (the join must exclude blanks: `vvCountries` has 6 rows with a blank `UNCODE`) | `R1_Get_Violations_CertainFlightsCrew.sql` lines 191-202, 492-498 |
| NATCOD2 | nchar(3) | Y | Second nationality (ICAO code) | nchar(3); 6 non-blank | naming inference; not used by any procedure |
| NATLITY | nchar(20) | Y | Nationality (descriptive text) | nchar(20); 5,531 non-blank | naming inference; not used by any procedure |
| NATLITY2 | nchar(20) | Y | Second nationality (text) | nchar(20); 10 non-blank | naming inference; not used by any procedure |
| BIRTHPLACE | nchar(30) | Y | Place of birth (text) | nchar(30); 5,306 non-blank | naming inference; not used by any procedure |
| BIRTHCNTR | nchar(3) | Y | Country of birth code | nchar(3); 5,307 non-blank | naming inference; not used by any procedure |
| OLDBIRTHCNTR | nchar(2) | Y | Previous/legacy country-of-birth code | nchar(2); all blank | naming inference; not used by any procedure |
| BIRTHSTATE | nchar(3) | Y | State/province of birth code | nchar(3); 1,057 non-blank | naming inference; not used by any procedure |
| PASSPORT | nchar(16) | Y | Primary passport number | nchar(16); 5,555 non-blank | naming inference; not used by any procedure |
| PASSPDATE | nchar(8) | Y | Primary passport date (issue/expiry; text) | nchar(8); 5,537 non-blank | naming inference; not used by any procedure |
| PASSPLACE | nchar(16) | Y | Primary passport place of issue | nchar(16); 5,376 non-blank | naming inference; not used by any procedure |
| PASSCNTR | nchar(3) | Y | Primary passport issuing country code | nchar(3); 5,492 non-blank | naming inference; not used by any procedure |
| OLDPASSCNTR | nchar(2) | Y | Legacy issuing-country code of the primary passport | nchar(2); 20 non-blank | naming inference; not used by any procedure |
| PASSPRT2 | nchar(16) | Y | Second passport number | nchar(16); 13 non-blank | naming inference; not used by any procedure |
| PASSPDATE2 | nchar(8) | Y | Second passport date (text) | nchar(8); 12 non-blank | naming inference; not used by any procedure |
| PASSPLACE2 | nchar(16) | Y | Second passport place of issue | nchar(16); 10 non-blank | naming inference; not used by any procedure |
| PASS2CNTR | nchar(3) | Y | Second passport issuing country code | nchar(3); 10 non-blank | naming inference; not used by any procedure |
| OLDPASS2CNTR | nchar(2) | Y | Legacy issuing-country code of the second passport | nchar(2); all blank | naming inference; not used by any procedure |
| PASSPNNAMES_1 | nchar(40) | Y | Name part 1 exactly as printed on the passport (for API/APIS passenger-data messages) | nchar(40); non-blank 4,938 / 4,936 / 124 for parts 1-3 | naming inference; not used by any procedure |
| PASSPNNAMES_2 | nchar(40) | Y | Name part 2 exactly as printed on the passport (for API/APIS passenger-data messages) | nchar(40); non-blank 4,938 / 4,936 / 124 for parts 1-3 | naming inference; not used by any procedure |
| PASSPNNAMES_3 | nchar(40) | Y | Name part 3 exactly as printed on the passport (for API/APIS passenger-data messages) | nchar(40); non-blank 4,938 / 4,936 / 124 for parts 1-3 | naming inference; not used by any procedure |
| VISANUM | nchar(14) | Y | Visa number | nchar(14); 6 non-blank | naming inference; not used by any procedure |
| VISAPLACE | nchar(16) | Y | Visa place of issue | nchar(16); 4 non-blank | naming inference; not used by any procedure |
| VISACNTR | nchar(3) | Y | Visa country code | nchar(3); 4 non-blank | naming inference; not used by any procedure |
| OLDVISACNTR | nchar(2) | Y | Legacy visa country code | nchar(2); all blank | naming inference; not used by any procedure |
| VISANUMFZ | nchar(16) | Y | Second visa/permit number field | nchar(16); all blank | naming inference; not used by any procedure |
| LCNENUM | nchar(22) | Y | Licence 1 number (pilot/cabin licence) | nchar(22); 1,524 non-blank | naming inference; not used by any procedure |
| LCNEDATE | nchar(8) | Y | Licence 1 date (text) | nchar(8); 30 non-blank | naming inference; not used by any procedure |
| LCNEPLACE | nchar(30) | Y | Licence 1 place of issue | nchar(30); 10 non-blank | naming inference; not used by any procedure |
| LCNETYPE | nchar(10) | Y | Licence 1 type | nchar(10); 36 non-blank, 37 distinct across both licence-type columns | naming inference; not used by any procedure |
| LIC_CTR_CODE | nchar(3) | Y | Licence 1 issuing country code | nchar(3); 1,361 non-blank | naming inference; not used by any procedure |
| LCNENUM2 | nchar(22) | Y | Licence 2 number | nchar(22); 3,694 non-blank | naming inference; not used by any procedure |
| LCNEDATE2 | nchar(8) | Y | Licence 2 date (text) | nchar(8); 3,364 non-blank | naming inference; not used by any procedure |
| LCNEPLACE2 | nchar(30) | Y | Licence 2 place of issue | nchar(30); 528 non-blank | naming inference; not used by any procedure |
| LCNETYPE2 | nchar(10) | Y | Licence 2 type | nchar(10); 205 non-blank | naming inference; not used by any procedure |
| LIC_CTR_CODE2 | nchar(3) | Y | Licence 2 issuing country code | nchar(3); 2,872 non-blank | naming inference; not used by any procedure |
| TRETRI_AUTHNBR | nchar(8) | Y | Type-rating examiner / instructor (TRE/TRI) authorisation number - licence-authorisation identifier (inference from the abbreviation) | nchar(8); all blank | naming inference; not used by any procedure |
| PERMIT | nchar(12) | Y | Work/residence permit number | nchar(12); 2 non-blank | naming inference; not used by any procedure |
| CERTIFNUM | nchar(14) | Y | Certificate number | nchar(14); all blank | naming inference; not used by any procedure |
| SOCIALSECRTY | nchar(12) | Y | Social security / insurance number (sensitive) | nchar(12); all blank | naming inference; not used by any procedure |
| TAIBAOZHERGNUMBER | nchar(12) | Y | Number of the Taiwan Compatriot Permit (Taibaozheng) - travel-document identifier required for China-related flights (inference from the name) | nchar(12); all blank | naming inference; not used by any procedure |
| NICNUMBEREXIST | tinyint | Y | Flag: a national identity card number exists (naming inference) | tinyint; 0 in all rows | naming inference; not used by any procedure |
| APISMCL | tinyint | Y | APIS (advance passenger information) flag for the crew list/MCL: 0 = none, 1, 2 = variants (code table not available) | tinyint; 0 = 5,502, 1 = 572, 2 = 77 | naming inference; not used by any procedure |

### 3.5 Pay, contract and entitlement data (HR / financial - sensitive)
Never profiled beyond zero/non-zero counts.

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| SALARY | tinyint | Y | Salary class/code | tinyint (not profiled) | naming inference; not used by any procedure |
| ST_SALARY | nchar(2) | Y | Salary status code (text) | nchar(2); all blank | naming inference; not used by any procedure |
| WAGECTG | tinyint | Y | Wage category | tinyint; 0 in all rows | naming inference; not used by any procedure |
| BANKACC | nchar(16) | Y | Bank account (sensitive) | nchar(16); 2,244 non-blank | naming inference; not used by any procedure |
| CREDITYPE | nchar(6) | Y | Credit card type (sensitive) | nchar(6); all blank | naming inference; not used by any procedure |
| CREDITNUM | nchar(22) | Y | Credit card number (sensitive) | nchar(22); all blank | naming inference; not used by any procedure |
| CREDITEXP | nchar(5) | Y | Credit card expiry (sensitive) | nchar(5); 17 non-blank | naming inference; not used by any procedure |
| CREDITBALANCE | int | Y | Credit-hours balance carried forward | int | naming inference; not used by any procedure |
| PREVMONTHLYSALARY | real | Y | Previous-month salary figure | real (not profiled) | naming inference; not used by any procedure |
| NEXTMONTHLYSALARY | real | Y | Next-month salary figure | real (not profiled) | naming inference; not used by any procedure |
| GUARANTEE | smallint | Y | Monthly pay guarantee (minutes/hours) | smallint; 0 in all rows | naming inference; not used by any procedure |
| GUARANTNIGHTS | smallint | Y | Guaranteed number of nights (naming inference) | smallint; non-zero in 427 rows (max 8,224) | naming inference; not used by any procedure |
| DOFFCLAIMSRATE | real | Y | Rate applied to days-off claims | real | naming inference; not used by any procedure |
| CONTRACT | nchar(10) | Y | Contract type/number | nchar(10); all blank | naming inference; not used by any procedure |
| COMP_START | nchar(8) | Y | Company start (hire) date (text, personal) | nchar(8); all blank | naming inference; not used by any procedure |
| OWNTRAN | smallint | Y | Flag: crew member provides own transportation | smallint; 1 in a single row | naming inference; not used by any procedure |
| OFFDAYS | smallint | Y | Entitled off days | smallint; 0 in all rows | naming inference; not used by any procedure |
| FACTOREDHRS | int | Y | Factored (credited) hours | int; 0 in all rows | naming inference; not used by any procedure |
| FACTHRSDATE | smallint | Y | Date of the factored-hours figure | smallint day number; 0 in all rows | naming inference; not used by any procedure |
| SICK_BALANCE | smallint | Y | Sick-leave balance | smallint; 0 in all rows | naming inference; not used by any procedure |
| VACATION_BALANCE | smallint | Y | Vacation balance | smallint; 0 in all rows | naming inference; not used by any procedure |
| TRAINING_MMG | smallint | Y | Training minimum-guarantee figure (naming inference) | smallint; 0 in all rows | naming inference; not used by any procedure |
| CONFID | tinyint | Y | Confidentiality flag (hide details from others) | tinyint 0/1; 1 in 4,236 rows | naming inference; not used by any procedure |
| WEBIVRACCESS | tinyint | Y | Flag: access to web / IVR self-service allowed | tinyint; 1 in one row | naming inference; not used by any procedure |
| FAMILYPASSWORD | varbinary(32) | Y | Credential-like binary field (family/web access password hash; **sensitive, never select**) | varbinary(32) | naming inference; not used by any procedure |

### 3.6 Scheduling attributes, limits, base and month settings
Operational crew-scheduling attributes held on the crew master record. Most are unused (constant 0) at this airline.

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| OPENBASES | varbinary(20) | Y | Bitmap of the **bases from which the crew member accepts/is open for assignments** (inference from the name; one bit per base number) | non-zero in 2,679 rows | naming inference; not used by any procedure |
| OLD_OPENBASES | nchar(7) | Y | Legacy text form of the open-bases list | nchar(7); all blank | naming inference; not used by any procedure |
| BASEMONTH | varbinary(60) | Y | Per-month base assignment array (12 months x 5 bytes; inference) | varbinary(60); all zero | naming inference; not used by any procedure |
| FUTBASEMONTH | varbinary(40) | Y | Future (next-period) base-month assignments | varbinary(40); non-zero in 725 rows | naming inference; not used by any procedure |
| TSC_MONTH | tinyint | Y | Month number (0-12; 32 = special) used by a TSC (unknown abbreviation) setting; 0 = none | tinyint; 0 = 1,931 rows, 1-12 = 157..1,009 each (most: 11 = 1,009, 10 = 519), 32 = 15 | naming inference; not used by any procedure |
| TSCREASON | nchar(20) | Y | Free-text reason attached to the TSC setting (1,854 distinct texts - free text, may contain personal remarks; never print) | nchar(20); 3,763 non-blank | naming inference; not used by any procedure |
| TSCREASONPRV | nchar(20) | Y | Previous TSC reason text (free text, never print) | nchar(20); 3,467 non-blank | naming inference; not used by any procedure |
| TSCNOTONMCL | tinyint | Y | TSC flag: crew member not on the monthly crew list (MCL) (naming inference) | tinyint 0/1; 77 rows = 1 | naming inference; not used by any procedure |
| MCL_DEL_SENT | tinyint | Y | Flag: MCL deletion message already sent | tinyint 0/1; 53 rows = 1 | naming inference; not used by any procedure |
| MAXBLOCK | smallint | Y | Individual maximum block time override (minutes; inference) | smallint; non-zero in 15 rows (max 600) | naming inference; not used by any procedure |
| MAXLAND | smallint | Y | Individual maximum number of landings override | smallint; 0 in all rows | naming inference; not used by any procedure |
| OVRLIMIT | tinyint | Y | Flag: legality limit override allowed | tinyint; 0 in all rows | naming inference; not used by any procedure |
| OVRLIMIT2 | tinyint | Y | Second legality limit override flag | tinyint; 0 in all rows | naming inference; not used by any procedure |
| SBYBEG | smallint | Y | Standby begin (date) | smallint; 0 in all rows | naming inference; not used by any procedure |
| CON17DAYS | tinyint | Y | Rule flag on 17 consecutive days (naming inference) | tinyint; 0 in all rows | naming inference; not used by any procedure |
| TRNREQ | tinyint | Y | Training-required flag/type | tinyint; 0 = 6,135 rows, 32 = 16 rows | naming inference; not used by any procedure |
| TRAINBEG | smallint | Y | Training begin date | smallint day number; non-zero in 3 rows | naming inference; not used by any procedure |
| TRAINEND | smallint | Y | Training end date | smallint day number; 0 in all rows | naming inference; not used by any procedure |
| TRAINER | bigint | Y | Trainer assignment/qualification bitmask (naming inference) | bigint; 0 in all rows | naming inference; not used by any procedure |
| TRAINELIG | tinyint | Y | Training eligibility flag | tinyint; 0 in all rows | naming inference; not used by any procedure |
| GATEWAYELIG | tinyint | Y | Gateway (overseas layover) eligibility flag | tinyint; 0 in all rows | naming inference; not used by any procedure |
| GATEHOTEL | nchar(4) | Y | Preferred gateway hotel code | nchar(4); all blank | naming inference; not used by any procedure |
| USEPERCENT | tinyint | Y | Utilisation percentage #1 (part-time / reduced-schedule share of full time; e.g. 50 or 100) valid between `USE_EFF_ST` and `USE_EFF_ED` | tinyint; 0 = 6,128 rows, 50 = 2, 100 = 21 | naming inference; not used by any procedure |
| USE_EFF_ST | smallint | Y | Effective start day of utilisation record #1 | smallint day number; non-zero in 3,529 rows (note: far more rows have dates than percentages) | naming inference; not used by any procedure |
| USE_EFF_ED | smallint | Y | Effective end day of utilisation record #1 | smallint day number; non-zero in 2,892 rows | naming inference; not used by any procedure |
| USE_ST_PRV | smallint | Y | Previous effective start day (history of utilisation #1) | smallint day number | naming inference; not used by any procedure |
| USE_ED_PRV | smallint | Y | Previous effective end day (history of utilisation #1) | smallint day number | naming inference; not used by any procedure |
| USEPERCENT2 | tinyint | Y | Utilisation percentage #2 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| USEPERCENT3 | tinyint | Y | Utilisation percentage #3 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| USEPERCENT4 | tinyint | Y | Utilisation percentage #4 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| USEPERCENT5 | tinyint | Y | Utilisation percentage #5 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| USEPERCENT6 | tinyint | Y | Utilisation percentage #6 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| USE_EFF_ST2 | smallint | Y | Effective start day of utilisation record #2 | smallint day number | naming inference; not used by any procedure |
| USE_EFF_ST3 | smallint | Y | Effective start day of utilisation record #3 | smallint day number | naming inference; not used by any procedure |
| USE_EFF_ST4 | smallint | Y | Effective start day of utilisation record #4 | smallint day number | naming inference; not used by any procedure |
| USE_EFF_ST5 | smallint | Y | Effective start day of utilisation record #5 | smallint day number | naming inference; not used by any procedure |
| USE_EFF_ST6 | smallint | Y | Effective start day of utilisation record #6 | smallint day number | naming inference; not used by any procedure |
| USE_EFF_ED2 | smallint | Y | Effective end day of utilisation record #2 | smallint day number | naming inference; not used by any procedure |
| USE_EFF_ED3 | smallint | Y | Effective end day of utilisation record #3 | smallint day number | naming inference; not used by any procedure |
| USE_EFF_ED4 | smallint | Y | Effective end day of utilisation record #4 | smallint day number | naming inference; not used by any procedure |
| USE_EFF_ED5 | smallint | Y | Effective end day of utilisation record #5 | smallint day number | naming inference; not used by any procedure |
| USE_EFF_ED6 | smallint | Y | Effective end day of utilisation record #6 | smallint day number | naming inference; not used by any procedure |
| GRPPERCPT | tinyint | Y | Group-percent participation (naming inference) | tinyint; 0 in all rows | naming inference; not used by any procedure |
| NONSOURCED | tinyint | Y | Flag: crew member not sourced from the HR interface (naming inference) | tinyint; 0 in all rows | naming inference; not used by any procedure |
| IOE_COMPL | smallint | Y | Initial operating experience completion date | smallint day number; 0 in all rows | naming inference; not used by any procedure |
| IOE_REL | smallint | Y | Initial operating experience release date | smallint day number; 0 in all rows | naming inference; not used by any procedure |
| LD_UPGRD | smallint | Y | Line-director / upgrade date (naming inference) | smallint day number; 0 in all rows | naming inference; not used by any procedure |
| ACTIVECMDAYS | smallint | Y | Active days as captain (counter) | smallint; 0 in all rows | naming inference; not used by any procedure |
| ACTIVEFADAYS | smallint | Y | Active days as flight attendant (counter) | smallint; 0 in all rows | naming inference; not used by any procedure |
| UPUNTILDATE | smallint | Y | Up-until (date) marker | smallint day number; 0 in all rows | naming inference; not used by any procedure |
| PERMANENTFO | smallint | Y | Permanent first-officer marker/date | smallint; 0 in all rows | naming inference; not used by any procedure |
| INVIOLATEDAYS | tinyint | Y | Inviolate (protected) days count | tinyint; 0 in all rows | naming inference; not used by any procedure |
| RMNDAYSPLACEON | tinyint | Y | Reminder: days placed on (flag) | tinyint; 0 in all rows | naming inference; not used by any procedure |
| RMNDAYSPLACEDAYS | tinyint | Y | Reminder: number of days placed | tinyint; 0 in all rows | naming inference; not used by any procedure |
| RMNDAYSPLACEDATE | smallint | Y | Reminder: date placed | smallint day number; 0 in all rows | naming inference; not used by any procedure |
| REENTRY | smallint | Y | Re-entry (return from leave) date | smallint day number; 0 in all rows | naming inference; not used by any procedure |
| SAP1_SAP2 | tinyint | Y | SAP 1 / SAP 2 selector (naming inference) | tinyint; 0 in all rows | naming inference; not used by any procedure |
| CONFLICTRES | tinyint | Y | Conflict-resolution setting | tinyint; 0 in all rows | naming inference; not used by any procedure |
| SWAPSETTINGS | smallint | Y | Trip-swap preference bits (bidding/trading settings; bit field) | smallint; non-zero in all 6,151 rows, 179 distinct values | naming inference; not used by any procedure |
| FUTSWAPSETTINGS | tinyint | Y | Future (next-period) swap settings | tinyint; non-zero in 2,463 rows, 21 distinct values | naming inference; not used by any procedure |
| CHCWORKPRACTICES | tinyint | Y | CHC-specific work-practice code (helicopter-operator module; unused) | tinyint; 0 in all rows | naming inference; not used by any procedure |
| CHC_COMPANYCODES_CODE1 | tinyint | Y | CHC company code #1 (unused) | tinyint; 0 in all rows | naming inference; not used by any procedure |
| CHC_COMPANYCODES_CHNGDATE | smallint | Y | CHC company code change date (unused) | smallint day number | naming inference; not used by any procedure |
| CHC_COMPANYCODES_CODE2 | tinyint | Y | CHC company code #2 (unused) | tinyint; 0 in all rows | naming inference; not used by any procedure |
| WEBPERSSETCONF | smallint | Y | Web personal-settings confirmation (bit field/date) | smallint | naming inference; not used by any procedure |
| PRIVACYPREFERENCES | smallint | Y | Privacy preferences (which personal data may be shown to other crew; bit field) | smallint; non-zero in 6,001 rows, 42 distinct values | naming inference; not used by any procedure |
| PLACECONV | tinyint | Y | Place-conversion setting (naming inference) | tinyint; 1 in all rows | naming inference; not used by any procedure |
| DONOTPRINTLABELS | tinyint | Y | Flag: do not print mailing labels | tinyint; 0 in all rows | naming inference; not used by any procedure |
| AIRPMARKUPD | tinyint | Y | Flag: airport markup (annotation) updated | tinyint; 1 in 4 rows | naming inference; not used by any procedure |

### 3.7 Blocked dates / mini-bloc / PVHR (used by the planner)
The four `TSC_BLOCKDATES_n` groups hold up to two blocked date ranges each (BEGD = first day, ENDD = last day, inclusive; AIMS day numbers since 1980-01-01, 0 = unused, 32767 = open-ended). The planner reads only groups **1 and 3**: a crew member with a range covering a day is treated as being in a 'PVHR' / **mini-bloc** period (R0 draft priority and FTC legal limit).

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| TSC_BLOCKACT_1 | tinyint | Y | Flag: blocked-date group 1 is active/applied (group 1: 93 rows = 1, group 3: 186 rows = 1, groups 2 and 4: never) | tinyint 0/1 | profiled; not used by any procedure |
| TSC_BLOCKACT_2 | tinyint | Y | Flag: blocked-date group 2 is active/applied (group 1: 93 rows = 1, group 3: 186 rows = 1, groups 2 and 4: never) | tinyint 0/1 | profiled; not used by any procedure |
| TSC_BLOCKACT_3 | tinyint | Y | Flag: blocked-date group 3 is active/applied (group 1: 93 rows = 1, group 3: 186 rows = 1, groups 2 and 4: never) | tinyint 0/1 | profiled; not used by any procedure |
| TSC_BLOCKACT_4 | tinyint | Y | Flag: blocked-date group 4 is active/applied (group 1: 93 rows = 1, group 3: 186 rows = 1, groups 2 and 4: never) | tinyint 0/1 | profiled; not used by any procedure |
| TSC_BLOCKDATES_1_BEGD1 | smallint | Y | Group 1, range 1: first blocked day | smallint day number; 0 = none; non-zero in 428 rows | `R0_GetDraftList.sql` lines 542-545; `rpt.CalculateCrewFTC.sql` 116-119; `R5_Get_Violation_FTC.sql` 127-130 |
| TSC_BLOCKDATES_1_ENDD1 | smallint | Y | Group 1, range 1: last blocked day (inclusive) | smallint day number; 32767 in 5 rows (open-ended); non-zero in 427 rows | same |
| TSC_BLOCKDATES_1_BEGD2 | smallint | Y | Group 1, range 2: first blocked day | smallint day number; non-zero in 212 rows | same |
| TSC_BLOCKDATES_1_ENDD2 | smallint | Y | Group 1, range 2: last blocked day | smallint day number; non-zero in 211 rows | same |
| TSC_BLOCKDATES_2_BEGD1 | smallint | Y | Group 2, range 1: first blocked day (group never used) | smallint; 0 in all rows | profiled; ignored by the planner |
| TSC_BLOCKDATES_2_ENDD1 | smallint | Y | Group 2, range 1: last blocked day | smallint; 0 in all rows | profiled; ignored by the planner |
| TSC_BLOCKDATES_2_BEGD2 | smallint | Y | Group 2, range 2: first blocked day | smallint; 0 in all rows | profiled; ignored by the planner |
| TSC_BLOCKDATES_2_ENDD2 | smallint | Y | Group 2, range 2: last blocked day | smallint; 0 in all rows | profiled; ignored by the planner |
| TSC_BLOCKDATES_3_BEGD1 | smallint | Y | Group 3, range 1: first blocked day | smallint day number; non-zero in 1,427 rows (earliest 2012-09-01) | `R0_GetDraftList.sql` lines 544-545; `rpt.CalculateCrewFTC.sql`; `R5_Get_Violation_FTC.sql` |
| TSC_BLOCKDATES_3_ENDD1 | smallint | Y | Group 3, range 1: last blocked day (inclusive); latest 2028-04-30 | smallint day number; non-zero in 1,427 rows | same |
| TSC_BLOCKDATES_3_BEGD2 | smallint | Y | Group 3, range 2: first blocked day | smallint day number; non-zero in 850 rows | same |
| TSC_BLOCKDATES_3_ENDD2 | smallint | Y | Group 3, range 2: last blocked day | smallint day number; non-zero in 850 rows | same |
| TSC_BLOCKDATES_4_BEGD1 | smallint | Y | Group 4, range 1: first blocked day (1 row only) | smallint day number | profiled; ignored by the planner |
| TSC_BLOCKDATES_4_ENDD1 | smallint | Y | Group 4, range 1: last blocked day | smallint day number | profiled; ignored by the planner |
| TSC_BLOCKDATES_4_BEGD2 | smallint | Y | Group 4, range 2: first blocked day | smallint; 0 in all rows | profiled; ignored by the planner |
| TSC_BLOCKDATES_4_ENDD2 | smallint | Y | Group 4, range 2: last blocked day | smallint; 0 in all rows | profiled; ignored by the planner |
| BLOCKBID_ST | smallint | Y | Block-bid period start day | smallint day number; 0 in all rows | naming inference; not used by any procedure |
| BLOCKBID_ED | smallint | Y | Block-bid period end day | smallint day number; 0 in all rows | naming inference; not used by any procedure |
| BLOCKBIDREASON1 | nchar(50) | Y | Block-bid reason text #1 | nchar(50); all blank | naming inference; not used by any procedure |
| BLOCKBIDREASON2 | nchar(50) | Y | Block-bid reason text #2 | nchar(50); all blank | naming inference; not used by any procedure |

### 3.8 Flight-hour history, last-aircraft dates, layover restriction
All unused (constant 0) in this database.

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| HISTHRS_1_TOTBLOCK | int | Y | Historical total block time carried over for history slot 1 | int; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_2_TOTBLOCK | int | Y | Historical total block time carried over for history slot 2 | int; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_3_TOTBLOCK | int | Y | Historical total block time carried over for history slot 3 | int; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_4_TOTBLOCK | int | Y | Historical total block time carried over for history slot 4 | int; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_5_TOTBLOCK | int | Y | Historical total block time carried over for history slot 5 | int; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_6_TOTBLOCK | int | Y | Historical total block time carried over for history slot 6 | int; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_7_TOTBLOCK | int | Y | Historical total block time carried over for history slot 7 | int; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_8_TOTBLOCK | int | Y | Historical total block time carried over for history slot 8 | int; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_1_POS | tinyint | Y | Position (vvPositions.ID) of history slot 1 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_2_POS | tinyint | Y | Position (vvPositions.ID) of history slot 2 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_3_POS | tinyint | Y | Position (vvPositions.ID) of history slot 3 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_4_POS | tinyint | Y | Position (vvPositions.ID) of history slot 4 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_5_POS | tinyint | Y | Position (vvPositions.ID) of history slot 5 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_6_POS | tinyint | Y | Position (vvPositions.ID) of history slot 6 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_7_POS | tinyint | Y | Position (vvPositions.ID) of history slot 7 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_8_POS | tinyint | Y | Position (vvPositions.ID) of history slot 8 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_1_AC | tinyint | Y | Aircraft type (ACTYPE) of history slot 1 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_2_AC | tinyint | Y | Aircraft type (ACTYPE) of history slot 2 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_3_AC | tinyint | Y | Aircraft type (ACTYPE) of history slot 3 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_4_AC | tinyint | Y | Aircraft type (ACTYPE) of history slot 4 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_5_AC | tinyint | Y | Aircraft type (ACTYPE) of history slot 5 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_6_AC | tinyint | Y | Aircraft type (ACTYPE) of history slot 6 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_7_AC | tinyint | Y | Aircraft type (ACTYPE) of history slot 7 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| HISTHRS_8_AC | tinyint | Y | Aircraft type (ACTYPE) of history slot 8 | tinyint; 0 in all rows | naming inference; not used by any procedure |
| LASTACDAY_1 | smallint | Y | Last day the crew member flew aircraft-type slot 1 (day number) | smallint; 0 in all rows | naming inference; not used by any procedure |
| LASTACDAY_2 | smallint | Y | Last day the crew member flew aircraft-type slot 2 (day number) | smallint; 0 in all rows | naming inference; not used by any procedure |
| LASTACDAY_3 | smallint | Y | Last day the crew member flew aircraft-type slot 3 (day number) | smallint; 0 in all rows | naming inference; not used by any procedure |
| LASTACDAY_4 | smallint | Y | Last day the crew member flew aircraft-type slot 4 (day number) | smallint; 0 in all rows | naming inference; not used by any procedure |
| LASTACDAY_5 | smallint | Y | Last day the crew member flew aircraft-type slot 5 (day number) | smallint; 0 in all rows | naming inference; not used by any procedure |
| LASTACDAY_6 | smallint | Y | Last day the crew member flew aircraft-type slot 6 (day number) | smallint; 0 in all rows | naming inference; not used by any procedure |
| LASTACDAY_7 | smallint | Y | Last day the crew member flew aircraft-type slot 7 (day number) | smallint; 0 in all rows | naming inference; not used by any procedure |
| LASTACDAY_8 | smallint | Y | Last day the crew member flew aircraft-type slot 8 (day number) | smallint; 0 in all rows | naming inference; not used by any procedure |
| LASTACDAY_9 | smallint | Y | Last day the crew member flew aircraft-type slot 9 (day number) | smallint; 0 in all rows | naming inference; not used by any procedure |
| LASTACDAY_10 | smallint | Y | Last day the crew member flew aircraft-type slot 10 (day number) | smallint; 0 in all rows | naming inference; not used by any procedure |
| LASTACDAY_11 | smallint | Y | Last day the crew member flew aircraft-type slot 11 (day number) | smallint; 0 in all rows | naming inference; not used by any procedure |
| LASTACDAY_12 | smallint | Y | Last day the crew member flew aircraft-type slot 12 (day number) | smallint; 0 in all rows | naming inference; not used by any procedure |
| LASTACDAY_13 | smallint | Y | Last day the crew member flew aircraft-type slot 13 (day number) | smallint; 0 in all rows | naming inference; not used by any procedure |
| LASTACDAY_14 | smallint | Y | Last day the crew member flew aircraft-type slot 14 (day number) | smallint; 0 in all rows | naming inference; not used by any procedure |
| LASTACDAY_15 | smallint | Y | Last day the crew member flew aircraft-type slot 15 (day number) | smallint; 0 in all rows | naming inference; not used by any procedure |
| LASTACDAY_16 | smallint | Y | Last day the crew member flew aircraft-type slot 16 (day number) | smallint; 0 in all rows | naming inference; not used by any procedure |
| KKLAYOVER_BEGD | smallint | Y | Layover-restriction period begin | smallint day number; 0 in all rows | naming inference; not used by any procedure |
| KKLAYOVER_ENDD | smallint | Y | Layover-restriction period end | smallint day number; 0 in all rows | naming inference; not used by any procedure |
| KKLAYOVER_AIRP_1 | nchar(4) | Y | Layover-restriction airport 1 | nchar(4); all blank | naming inference; not used by any procedure |
| KKLAYOVER_AIRP_2 | nchar(4) | Y | Layover-restriction airport 2 | nchar(4); all blank | naming inference; not used by any procedure |
| KKLAYOVER_FUT | varbinary(12) | Y | Reserved area of the layover-restriction group | varbinary(12) | naming inference; not used by any procedure |

### 3.9 System, audit and reserved fields

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| USER_ | smallint | Y | AIMS user id that last modified the crew record | smallint; 85 distinct values; non-zero in all rows | naming inference; not used by any procedure |
| UPDDATE | smallint | Y | Date of last modification of the record | smallint day number; 5,987 non-zero; 2005-09-22 .. 2026-10-26 | naming inference; not used by any procedure |
| UPDTIME | int | Y | Time of last modification | int; 0..77,153 - probably seconds since midnight (inference from the range) | naming inference; not used by any procedure |
| IVRFIRST | smallint | Y | First day the crew member used the phone (IVR) system | smallint day number; 0 in all rows | naming inference; not used by any procedure |
| IVRLAST | smallint | Y | Last day the crew member used the IVR system | smallint day number; 0 in all rows | naming inference; not used by any procedure |
| IVRNUM | smallint | Y | Number of IVR calls | smallint; 0 in all rows | naming inference; not used by any procedure |
| TOUCHFIRST | smallint | Y | First day of touch-screen/kiosk use | smallint day number; 0 in all rows | naming inference; not used by any procedure |
| TOUCHLAST | smallint | Y | Last day of touch-screen/kiosk use | smallint day number; 0 in all rows | naming inference; not used by any procedure |
| TOUCHNUM | smallint | Y | Number of touch-screen/kiosk sessions | smallint; 0 in all rows | naming inference; not used by any procedure |
| FUTURE | varbinary(196) | Y | Reserved area of the AIMS record | varbinary(196) | profiled as binary; unknown - not used by any procedure |

## 4. Keys & relationships
- `vvCREWDB.ID` = `ROSTERID.ID` (1:1, 6,151 = 6,151; `NAME` identical in all rows) = `ROSTER.ID` (1:N duties) = `CREWQUAL.ID` (1:N qualification rows) = `CREWCATEG.ID` (1:N category assignments) = `vvCREXPREC.CREW_ID` (1:N expiry records). Measured: 0 orphan ids in `CREWQUAL`, `CREWCATEG`, `vvCREXPREC` relative to `vvCREWDB`.
- `vvCREWDB.NATCOD` -> `vvCountries.UNCODE` (N:1): `INNER JOIN TSC.dbo.vvCountries AS c ON c.UNCODE = cd.NATCOD WHERE cd.ID = @Crew_Id_To_Draft AND LTRIM(RTRIM(cd.NATCOD)) <> ''` (`R1_Get_Violations_CertainFlightsCrew.sql` lines 197-202). The result `c.Country` (two-letter code) is compared with `SPEFREC3.NATIONALITIES`. Measured: 5,261 of the 5,263 non-blank `NATCOD` values join to a country row.
- `vvCREWDB.SPOUSID` -> `vvCREWDB.ID` (spouse also crew; not used).
- Block dates are per crew (1:1 columns), compared with `ROSTER.LEG_DAY` / calendar days by the planner.

## 5. Encoding conventions & gotchas
- **Dates are AIMS day numbers**: `smallint` days since **1980-01-01** (`DATEADD(DAY, n, '1980-01-01')`); `0` = not set; `32767` = open-ended (2069-09-17). Some dates are stored as **text** in `nchar(8)` (`PASSPDATE`, `LCNEDATE`, `MARRIAGEDATE`, `COMP_START`...), format not documented - these are personal fields anyway. `UPDTIME` is an `int` time-of-day (probably seconds).
- **Block-date ranges** (`TSC_BLOCKDATES_n_BEGDm` / `ENDDm`): both ends inclusive (R5/FTC compare `DATEADD(day, End,'1980-01-01') >= @FilterDateFrom AND DATEADD(day, Beg,'1980-01-01') <= @FilterDateTo`); a pair is valid only when **both** `Beg > 0` and `End > 0`. The planner ignores groups 2 and 4 (unused / 1 row).
- **Padding:** all `nchar` fields are blank-padded; always `LTRIM(RTRIM())` (e.g. `NATCOD`).
- **Nationality:** `NATCOD` is the *ICAO* three-letter code; blank = unknown (888 of 6,151 crew overall, but only 1 of the 2,823 crew with a valid qualification today). A blank must never be joined to `vvCountries.UNCODE` (6 rows there have a blank `UNCODE`; R1 explicitly guards this).
- **Constant columns:** many columns are constant (all 0 / all blank) in this database - they are listed with "0 in all rows" - and carry no information. Do not build logic on them.
- **`NAME` is also in `ROSTERID`** (identical): prefer `ROSTERID` for name lookups if only the name is needed (`R0` takes `rid.NAME`).
- **Two seniority concepts exist elsewhere** (`ROSTERID.SENIOR`, `CREWQUAL.SENIOR`); `vvCREWDB` has none of them (`EMPLSNR` is not the planner's seniority).
- **Free text columns** (`TSCREASON`, `TSCREASONPRV`: 1,854 / 1,920 distinct) can contain personal remarks - never print.
- **Performance:** wide view, so projecting only what is needed matters; `CROSS APPLY (VALUES ...)` unpivots of the block dates are fine because the planner always filters by `ID` (R5, FTC) or runs it once for the candidate pool (R0).

## 6. How the planner-assist procedures use it
- **Existence validation of the crew id parameter**: `IF NOT EXISTS (SELECT 1 FROM TSC.dbo.vvCREWDB WHERE ID = TRY_CAST(@Crew_ID AS INT)) THROW ...` in `R1` (`@Crew_Id_To_Draft`, line 38), `R2` (line 31), `R3` (line 19), `R3_..._Batch` (line 31, per crew of the batch), `R4` (line 117), `R5` (line 58) and `rpt.CalculateCrewFTC` (line 35).
- **`rpt.lookup_crew`**: `SELECT ID AS Crew_ID, Name AS Crew_Name FROM vvCREWDB WHERE ID = @crew_id` or `WHERE Name LIKE '%' + @crew_name + '%'` - the MCP tool that resolves a crew name to an id (the only place where a name is returned deliberately). `rpt.get_crew_certifications` also returns `B.NAME`.
- **`R1_Get_Violations_CertainFlightsCrew`**: `NATCOD` -> two-letter nationality of the drafted crew member, to evaluate rules that filter crew by nationality (custom rule type "Nationality", R1-5). Unknown nationality => the rule matches nobody and a note is emitted.
- **`R0_GetDraftList`** (CTE `pvhr_list`): unpivots `TSC_BLOCKDATES_1_BEGD1/ENDD1`, `_1_BEGD2/ENDD2`, `_3_BEGD1/ENDD1`, `_3_BEGD2/ENDD2` into (crew, begin date, end date) for ranges with `Beg > 0 AND End > 0`, expands them over the calendar days of the search window, and marks the crew member's days as `Is_PVHR` (PVHR = "blocked/mini-bloc" period). The flag feeds the 13-step PNT draft order (steps 1-8: "regular schedule (no PVHR)" vs "PVHR"; priority numbers 1.1/1.2, 3.1/3.2 ...).
- **`rpt.CalculateCrewFTC`** and **`dbo.R5_Get_Violation_FTC`**: derive `IS_CREW_MINI_BLOC = 1` when any of those four ranges overlaps the period under check (`DATEADD(day, v.Beg,'1980-01-01') <= @FilterDateTo AND DATEADD(day, v.[End],'1980-01-01') >= @FilterDateFrom`); the mini-bloc status selects the legal flight-time-credit limit from `dbo.FtcLegalLimit` (by `Pos_Category` and `Is_Mini_Bloc`). In R5 the caller's `@IS_CREW_MINI_BLOC` value is ignored and recomputed from these columns.
- No procedure uses any of the other ~270 columns.

## 7. Typical query patterns
Only operational columns. Never select names, contact data, documents, dates of birth or pay columns.
```sql
-- does a crew id exist?
SELECT CASE WHEN EXISTS (SELECT 1 FROM TSC.dbo.vvCREWDB WHERE ID = @crew_id) THEN 1 ELSE 0 END AS Crew_Exists;

-- resolve a crew name to ids (the only sanctioned name lookup; returns id + display name, as rpt.lookup_crew does)
SELECT ID AS Crew_ID, NAME AS Crew_Name
FROM TSC.dbo.vvCREWDB
WHERE NAME LIKE N'%' + @crew_name + N'%';

-- blocked-date (PVHR / mini-bloc) ranges of one crew member, as real dates
SELECT v.Grp,
       CAST(DATEADD(DAY, v.Beg, '1980-01-01') AS DATE) AS Block_From,
       CASE WHEN v.[End] = 32767 THEN NULL ELSE CAST(DATEADD(DAY, v.[End], '1980-01-01') AS DATE) END AS Block_To   -- NULL = open-ended
FROM TSC.dbo.vvCREWDB AS t
CROSS APPLY (VALUES (1, t.TSC_BLOCKDATES_1_BEGD1, t.TSC_BLOCKDATES_1_ENDD1),
                    (1, t.TSC_BLOCKDATES_1_BEGD2, t.TSC_BLOCKDATES_1_ENDD2),
                    (3, t.TSC_BLOCKDATES_3_BEGD1, t.TSC_BLOCKDATES_3_ENDD1),
                    (3, t.TSC_BLOCKDATES_3_BEGD2, t.TSC_BLOCKDATES_3_ENDD2)) AS v(Grp, Beg, [End])
WHERE t.ID = @crew_id AND v.Beg > 0 AND v.[End] > 0;

-- how many crew with a valid qualification today are in a blocked period today (aggregate)
DECLARE @d INT = DATEDIFF(DAY, '1980-01-01', GETDATE());
SELECT COUNT(DISTINCT t.ID) AS Crew_In_Block
FROM TSC.dbo.vvCREWDB AS t
CROSS APPLY (VALUES (t.TSC_BLOCKDATES_1_BEGD1, t.TSC_BLOCKDATES_1_ENDD1), (t.TSC_BLOCKDATES_1_BEGD2, t.TSC_BLOCKDATES_1_ENDD2),
                    (t.TSC_BLOCKDATES_3_BEGD1, t.TSC_BLOCKDATES_3_ENDD1), (t.TSC_BLOCKDATES_3_BEGD2, t.TSC_BLOCKDATES_3_ENDD2)) AS v(Beg, [End])
WHERE v.Beg > 0 AND v.[End] > 0 AND v.Beg <= @d AND v.[End] >= @d
  AND EXISTS (SELECT 1 FROM TSC.dbo.CREWQUAL AS q WHERE q.ID = t.ID AND q.ACTIVBEG <= @d AND q.ACTIVEND >= @d);
```

## 8. Data profile (measured 2026-11-03; aggregates only)
- 6,151 rows; `ID` unique; 6,150 non-blank `NAME`; `NAME` = `ROSTERID.NAME` in all rows; `SECOND_ID` = 0 and `PLACECONV` = 1 in all rows.
- Population: 2,823 crew have a valid qualification today (`CREWQUAL`); 4,721 have a category valid today; 5,511 have expiry records.
- Contact/identity completeness (non-blank counts): e-mail 4,433; address line 1 5,714; phone 1 5,419; passport number 5,555; nationality ICAO code (`NATCOD`) 5,263 (32 distinct codes); next-of-kin name 753.
- Blocked dates (non-zero counts): group 1 range 1 = 428 (open-ended in 5), range 2 = 212; group 3 range 1 = 1,427, range 2 = 850; group 4 = 1 row; group 2 = none. Group 3 earliest begin 2012-09-01, latest end 2028-04-30. `TSC_BLOCKACT_1` = 1 in 93 rows, `TSC_BLOCKACT_3` = 1 in 186 rows. Crew with a blocked range covering today: 275 (69 via group 1, 206 via group 3).
- `TSC_MONTH`: 0 for 1,931 crew; 1..12 for the others (November = 1,009, October = 519, May = 389); 32 for 15 crew.
- Constant-zero/blank columns: all `HISTHRS_*`, `LASTACDAY_*`, `KKLAYOVER_*`, `USEPERCENT2..6`, `IVR*`, `TOUCH*`, `SBYBEG`, `MAXLAND`, `GUARANTEE`, `SICK_BALANCE`, `VACATION_BALANCE`, etc.; `USEPERCENT` non-zero in 23 rows (50 or 100).
- `UPDDATE` (last record update) between 2005-09-22 and 2026-10-26; `USER_` 85 distinct users.

## 9. Open questions / confidence
- High: `ID` as the crew key and its relationships; `NAME`, `NATCOD` semantics (documented in code); the use of the block-date groups 1 and 3 as PVHR/mini-bloc (documented in code comments, `R5` line 120-123, `R0` line 1108).
- Medium: grouping and meaning of the personal-data columns (inferred from AIMS-style naming; values deliberately not inspected); `OPENBASES`, `SWAPSETTINGS`, `PRIVACYPREFERENCES` as bitfields.
- Low / unknown: meaning of the "TSC" prefix (`TSC_MONTH`, `TSCREASON`, `TSC_BLOCKACT_n`, `TSC_BLOCKDATES_n`) - possibly an AIMS module abbreviation; why groups 1 and 3 (not 2 and 4) are the PVHR ranges (business convention, 2 and 4 are unused); `APISMCL` codes; `EMPLSNR`; `UPDTIME` unit.
- Business question: whether `TSC_BLOCKACT_n` (flag) should be required in addition to the date ranges (today 337 crew have group-1 dates with `TSC_BLOCKACT_1 = 0` and 1,243 have group-3 dates with `TSC_BLOCKACT_3 = 0`; the planner ignores the flag and uses the dates alone).
