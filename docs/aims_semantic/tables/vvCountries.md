# vvCountries  (View)  - Country master (ICAO prefix <-> ISO codes, currency, allowance rates, nationality lookup), 55 columns

## 1. Purpose & business meaning
`TSC.dbo.vvCountries` is the AIMS "vv" view of the **country table**. One row = one country (or former country / special pseudo-country) as AIMS identifies it.
Its primary key, `COUNTRY`, is the **ICAO location-indicator prefix** (1-2 letters: `CY` Canada, `K` USA, `LF` France, `EG` United Kingdom, `LE` Spain, `MM` Mexico,
`Y` Australia ...), which is the code every airport row carries in `vvAirports.COUNTRY`. The row also carries the ISO alpha-3 code (`UNCODE`: CAN, USA, FRA...), the ISO alpha-2
code (`IATACODE`: CA, US, FR...), the country name, currency/language/region indices, VAT, tax-free salary, **per-diem/allowance rates** for crew subsistence (20 rates), passport rules,
ETS-membership and a category bitmap. Grain: one row per country; 138 rows (2026-11-03); static master data maintained in AIMS "Countries".

Role in planner-assist: (1) translate a crew member's nationality (`vvCREWDB.NATCOD`, ISO alpha-3) into the 2-letter code used by nationality rules (R1-5); (2) country of an airport
(through `vvAirports.COUNTRY`) for night-stop country categories; (3) the time zone key `vvZONEIDX.COUNTRY` is the same ICAO prefix (a country has one or more zones there).

## 2. Physical facts
- `TSC.dbo.vvCountries`, view; 138 rows; `COUNTRY` unique (138 distinct); `UNCODE` 133 distinct (6 blank). No indexes/row counts for views.
- Type lengths: `nchar` in characters (columns.json gives bytes). All columns nullable in metadata; empty text is blanks, empty numbers are 0.
- Tiny table, no performance concerns.

## 3. Column dictionary

### 3.1 Codes and names
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| COUNTRY | nchar(2) | yes | **Country key = ICAO location prefix** (1-2 letters, blank padded) | unique; 8 rows are 1 letter (`K` USA, `Y` AUS, `Z` CHN, `V` IND, `W` IDN, `R` JPN, `U` RUS, and the obsolete `C`), 130 are 2 letters; joins `vvAirports.COUNTRY`, `vvZONEIDX.COUNTRY`, `COUNTRYCATEG.COUNTRY` | `dbo.R1_Get_Violations_CertainFlightsCrew.sql:190-199`; profiled |
| NAME | nchar(20) | yes | Country name in English/French, upper case ("CANADA", "UNITED KINGDOM") | free text; obsolete entries are labelled `NE PLUS UTILISER-xx` ("do not use") or are historical (`YUGOSLAVIA`, `ZAIRE(D.R. OF CONGO)`) | profiled |
| UNCODE | nchar(3) | yes | **ISO 3166 alpha-3 code** (CAN, USA, FRA, GBR, ESP, MEX, DOM, ...). Blank for 6 rows (obsolete/default entries `C`, `RJ`, `YM`, `XX` "SSIM DEFAULT", `LY`, `FZ`) | alpha-3; matched to `vvCREWDB.NATCOD` | `dbo.R1_Get_Violations_CertainFlightsCrew.sql:199` |
| IATACODE | nchar(2) | yes | **ISO alpha-2 / IATA country code** (CA, US, FR, GB, ES, MX...) | alpha-2; 25 rows blank | profiled |
| SLOTCORD | nchar(8) | yes | Slot-coordinator address for the country | text; blank for all | profiled |
| SMS_ALT_CODE | tinyint | yes | Alternative country code used in SMS/messaging | 5 rows non-zero | profiled; naming inference |

### 3.2 Economics, currency and allowances (crew subsistence) - not used by planner-assist
| Column | Type | Null | Business meaning | Encoding / units | Evidence |
|---|---|---|---|---|---|
| CURRCY | smallint | yes | Currency id of the country (index into the AIMS currency table; e.g. CA=2, US=27, ES=8, FR=9, GB=5, DE=4, CZ=12, MX=96) | 105 rows set; AIMS currency index, not ISO numeric | profiled |
| VAT | real | yes | VAT rate | 0 for all rows | profiled |
| TAXFREE_SAL_1, TAXFREE_SAL_2, TAXFREE_SAL_3 | float | yes | Tax-free salary thresholds for the country (three bands) | money; 0 for all rows | profiled |
| ALLW_DATE | smallint | yes | Effective date (AIMS day number) of the allowance rates | 0 for all rows | profiled |
| ALLW_RATE_1 ... ALLW_RATE_20 | real x20 | yes | Per-diem / meal-allowance rates (up to 20 rate types; 1 = first rate) in `ALLW_CURRCY` | 73 countries have `ALLW_RATE_1` (max 4.50, e.g. BEL/CZE/MEX 4.25, GBR 4.50); rates 5..20 are 0 | profiled |
| ALLW_CURRCY | smallint | yes | Currency id of the allowance rates | 0 for all rows | profiled |
| ALLW_REGION | tinyint | yes | Allowance region group | 0 for all rows | profiled |

### 3.3 Region, language, flags
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| REGION | tinyint | yes | World region index (used for reporting/allowance grouping): 1 = 54 countries, 2 = 11, 3 = 7, 4 = 3, 5 = 32 (Europe: BEL, CZE, FRA, GBR, ESP, PRT...), 6 = 14 (DOM...), 7 = 13, 8 = 3 (CAN, USA), 0 = 1 | region code; labels not in view | profiled |
| MU_VOL | tinyint | yes | Measure-unit for volume (fuel) | 19 rows set | profiled; naming inference |
| LANG | smallint | yes | Main language id | 52 rows set | profiled; naming inference |
| CTRYLANG_DOMSEL | tinyint | yes | Domestic-selection flag of the country language list | 0 for all | profiled |
| CTRYLANG_NUM | tinyint | yes | Number of languages in the country language list | 0 for all | profiled |
| CTRYLANG_LANG | tinyint | yes | Language id in the country language list | unknown - not used | naming inference |
| CTRYLANG_POS | tinyint | yes | Crew position the language requirement applies to | unknown - not used | naming inference |
| ISETSMEMBER | tinyint | yes | Country is member of the EU Emissions Trading Scheme | 0 for all rows | profiled; naming inference |
| PASSP1, PASSP2 | tinyint | yes | Passport rule flags (validity/requirement) | 0 for all rows | profiled; naming inference |
| PASSPEXEMP | tinyint | yes | Passport exemption | 0 for all rows | profiled |
| CTRYRULESETS | tinyint | yes | Country-specific rule-set flag | 0 for all rows | profiled |
| NO_DBC | tinyint | yes | No "DBC" (data/dispatch?) flag | 0 for all rows | unknown - not used |
| OPENHOURS | varbinary(14) | yes | Opening hours of the country's offices (binary day-time table) | unknown - not used | naming inference |
| CATEG_CATEGBYT | varbinary(4) | yes | Country-category bitmap (51 rows non-zero); authoritative categories are in `COUNTRYCATEG` | bitmask | profiled |

### 3.4 Maintenance and reserved
| Column | Type | Null | Business meaning | Encoding | Evidence |
|---|---|---|---|---|---|
| USER_ | smallint | yes | Id of the AIMS user who last changed the row (106 rows set) | user id | naming inference |
| UPDDAY | smallint | yes | Last-update day (AIMS day number) | 0 for all rows | profiled |
| UPDTIME | int | yes | Last-update time | unknown - all rows unset | naming inference |
| FUT, FUT1, FUTURE | varbinary(19) / varbinary(22) / varbinary(52) | yes | Reserved bytes | unused | naming inference |

## 4. Keys & relationships
- Natural key: `COUNTRY` (unique). Alternate keys: `UNCODE` (unique except the 6 blanks), `IATACODE` (25 blanks).
- `vvAirports.COUNTRY = vvCountries.COUNTRY` (N:1). 778 of 779 stations match; the unmatched one (`RUN`) has a blank country.
- `vvZONEIDX.COUNTRY = vvCountries.COUNTRY` (1:N: a country has 1..n time zones) - inferred; the functions join zones via `vvAirports`, not via this view.
- `vvCREWDB.NATCOD = vvCountries.UNCODE` (N:1) - nationality: `INNER JOIN TSC.dbo.vvCountries AS c ON c.UNCODE = cd.NATCOD` with guards `LTRIM(RTRIM(cd.NATCOD)) <> '' AND LTRIM(RTRIM(c.Country)) <> ''` (`dbo.R1_Get_Violations_CertainFlightsCrew.sql:196-202`). The result is `vvCountries.COUNTRY` (the ICAO prefix, called "two-letter country code" in the code), which is compared with the codes listed in `SPEFREC3.NATIONALITIES` (separated by `|`).
- `COUNTRYCATEG.COUNTRY = vvCountries.COUNTRY` (country categories with active periods).

## 5. Encoding conventions & gotchas
- **Three different country codes in one row**: `COUNTRY` (ICAO prefix, key), `UNCODE` (alpha-3), `IATACODE` (alpha-2). Rules and procedures say "two-letter country code" but compare the ICAO prefix (`CA` is *not* the key for Canada; `CY` is). Choose the column that matches the source: nationality of crew -> `UNCODE`; airport country -> `COUNTRY`.
- **Blank `UNCODE`**: 6 rows have `UNCODE = ''`. Never join `NATCOD = UNCODE` without excluding blank `NATCOD` (888 of 6151 crew records have a blank `NATCOD` and would match 6 wrong countries) - `dbo.R1_Get_Violations_CertainFlightsCrew.sql:194-195`. 2 crew records carry a non-blank `NATCOD` that has no row here.
- `COUNTRY` is blank-padded `nchar(2)`; 1-letter codes (`K`, `Y`...) have a trailing space. `=` comparisons are fine; `LEFT(...,2)` or `LIKE` are not.
- Obsolete rows are kept and named `NE PLUS UTILISER-x` ("no longer use"): exclude them by `UNCODE <> ''`.
- No soft-delete/active-period columns; `UPDDAY`/`UPDTIME` are not populated.
- Allowance columns exist but only `ALLW_RATE_1` has data; do not report them as crew pay data.

## 6. How the planner-assist procedures use it
- `dbo.R1_Get_Violations_CertainFlightsCrew` (R1-5, nationality custom rules): derives the nationality of the drafted crew member as `vvCountries.COUNTRY` where `UNCODE = vvCREWDB.NATCOD` and compares it to the nationalities of the rule; a blank/unknown nationality means "rule matches nobody" and a message is emitted (`:490-504`).
- `rpt.Get_Detailed_Pairing:166-169, 288-291`: country categories (`COUNTRYCATEG`) of the night-stop airport/country (through `vvAirports.COUNTRY`, not through this view).
- Not otherwise referenced.

## 7. Typical query patterns
```sql
-- nationality code (ICAO prefix) from an ISO alpha-3 nationality; skip blank codes
SELECT LTRIM(RTRIM(c.COUNTRY)) AS ICAO_Prefix, LTRIM(RTRIM(c.NAME)) AS Country_Name
FROM TSC.dbo.vvCountries c
WHERE c.UNCODE = 'CAN' AND LTRIM(RTRIM(c.UNCODE)) <> '';

-- active (non-obsolete) countries with all three codes
SELECT LTRIM(RTRIM(COUNTRY)) AS Icao_Prefix, LTRIM(RTRIM(UNCODE)) AS Iso3, LTRIM(RTRIM(IATACODE)) AS Iso2, LTRIM(RTRIM(NAME)) AS Name
FROM TSC.dbo.vvCountries
WHERE LTRIM(RTRIM(UNCODE)) <> ''
ORDER BY NAME;

-- country of a station
SELECT a.AIRPORT, LTRIM(RTRIM(c.NAME)) AS Country
FROM TSC.dbo.vvAirports a LEFT JOIN TSC.dbo.vvCountries c ON c.COUNTRY = a.COUNTRY
WHERE a.AIRPORT = 'CDG';
```
(Do not join to crew nationality in an ad-hoc query beyond what is needed: nationality is personal data.)

## 8. Data profile (measured 2026-11-03)
- 138 rows, 138 distinct `COUNTRY` (8 of length 1, 130 of length 2), 133 distinct `UNCODE` (6 blank), 25 blank `IATACODE`.
- `REGION` counts: 0 -> 1, 1 -> 54, 2 -> 11, 3 -> 7, 4 -> 3, 5 -> 32, 6 -> 14, 7 -> 13, 8 -> 3.
- Sample mapping (ICAO / ISO3 / ISO2 / CURRCY / REGION): CY/CAN/CA/2/8, K/USA/US/27/8, LF/FRA/FR/9/5, EG/GBR/GB/5/5, LE/ESP/ES/8/5, MM/MEX/MX/96/1, MD/DOM/DO/62/6, LP/PRT/PT/65/5, LK/CZE/CZ/12/5, EB/BEL/BE/79/5, Y/AUS/AU/0/1.
- Blank-`UNCODE` rows: `C`, `RJ`, `YM` ("NE PLUS UTILISER"), `XX` ("SSIM DEFAULT"), `LY` (Yugoslavia), `FZ` (Zaire).
- Non-zero counts: `CURRCY` 105, `LANG` 52, `ALLW_RATE_1` 73, `MU_VOL` 19, `CATEG_CATEGBYT` 51, `USER_` 106; `VAT`, `TAXFREE_SAL_*`, `ALLW_DATE`, `ALLW_CURRCY`, `ISETSMEMBER`, `PASSP*`, `CTRYRULESETS` are 0 for every row.

## 9. Open questions / confidence
- High: `COUNTRY` = ICAO prefix; `UNCODE` = ISO alpha-3 matching `NATCOD`; `IATACODE` = ISO alpha-2 (by values).
- Medium: `REGION` numbering meaning (labels not in the view); `CURRCY` is an AIMS currency index (labels in another table).
- Unknown: `NO_DBC`, `MU_VOL`, `CTRYLANG_*`, `OPENHOURS`, `SMS_ALT_CODE` (naming only, not used).
