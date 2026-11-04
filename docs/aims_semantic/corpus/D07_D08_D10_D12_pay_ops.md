# Corpus from AIMS (TSC): D7 pay register, D8 flight movements, D10 positioning invoices, D12 agreement rules (D9 note)

Generated 2026-11-03, read-only against `TSC` (10.180.1.10) and `CrewSchedAI`. Method: catalog metadata, aggregate profiling (about 40 queries per dataset at most, every one narrow or indexed), comparison with the real Pierre v3 CSVs (`C:\dev\crewsim\src\crewsim\data\corpus\real_datav2\v3\`) using aggregates only.
No name, id, birth date, address, contact, message text or individual value is reproduced. Columns that hold personal data (`TIMEPNCPNT.CREW_NAME`, `CASIER_MAILBOX`, `TSCPAYID.DATA_BEGIN_END`, `LEGMEMO.MEMODATA`, `LEGPAX`/`PXNAMES2`, `MSGQ`) were **not read**.
Dates: AIMS day number = days since 1980-01-01 (2026-01-01 = 16802, 2026-08-31 = 17044, 2026-11-03 = 17108). Everything labelled *inference* is not a business rule.

## 0. Executive summary

| Dataset | Verdict | One-line reason |
|---|---|---|
| D7 pay register | **PARTIAL** | The pay-relevant timesheet exists in AIMS (`TIMEPNCPNT` = Snowflake `TIMESHEET_PNC_PNT`) and reproduces Pierre's hours almost exactly (BME exact, RESERVE_CREDIT exact), **but it holds credited hours only (no rate, no dollars) and only 4 pay months (2026-06..2026-09)**, vs 2024-04..2026-08 needed. |
| D8 flight movements | **MOSTLY** (history FULL, `cancelled`/`cancel_reason` PARTIAL) | All times, fleet, delay minutes and IATA delay code + subcode + description are in `LEGMAIN`/`LEGTIMES`/`LEGDELAYS`/`DLYCD` from 2023-08 with no gaps. The real cancellation *cause* is not stored (only a 7-value `CNXREASON` whose dictionary is not established) and Pierre's `cancelled` flag is **not** `LEGMAIN.CANCELLED`. |
| D9 station days | not needed | Fully computable from D8 (same legs); only note below. |
| D10 positioning invoices | **PARTIAL** (events yes, dollars NOT POSSIBLE) | AIMS has the deadhead legs, hotel nights and transport lines with crew + pairing links, but **no invoice amount**; the only price-like objects are a 714-row extra-price table (almost nothing after 2023) and a current fare rate card (`CITYCOST`). |
| D12 agreement rules | **PARTIAL** (mostly NOT in AIMS as data) | Reserve **guarantee credit hours** are in `CRCODES` (AM/PM 4.00 h, LCR 3.00 h, old XAM/XPM 3.33 h). Premium multipliers exist only as column names (`T_1_5`, `T_2`). Notice hours, caps, protected blocks, agreement text: not found. SPEFREC*/RULESTBL/RULESETS/ENTRULREC*/ALLWMTHD/PARAM are not pay or reserve agreement rules. |

Key new objects found: `TIMEPNCPNT` (pay timesheet), `LEGDELAYS`+`DLYCD`+`SUBDLY`+`DLYCAT` (delay coding), `LEGTRDELAYS` (propagated delays), `LOG_LEGMAIN` (field audit from 2024-05-13), `TABLES` records `CNXREASONS` and **`MODREAS002` (roster modification reasons: Company/Management Request, Union Request, Operational, CARS, Open Time, "Open Time - choix de Draft", Training, Other)** - the last one is relevant for D6/drafts, not for this group.

---------------------------------------------------------------------------------------------------

## 1. D7 `d7_pay_register`

### 1.1 What the real v3 file contains (aggregates)
Header: `crew_id, base, fleet, fleet_detail, pay_period, pay_code, hours, rate_cad, amount_cad, premium_cad, duty_date, linked_pairing_id, draft_leg_date, draft_flight_no` (schema in `loaders.py` only requires `crew_id, pay_period, pay_code, amount_cad, duty_date, linked_pairing_id`).
198,581 rows, 810 crews, pay periods 2024-04..2026-08 (29), duty_date 2024-04-24..2026-08-31, bases YUL 122,511 / YYZ 76,003 (67 blank), fleet A321 / A330.

| pay_code | rows | hours | rate_cad (constant per code) | note |
|---|---|---|---|---|
| CHV | 144,567 | 1,214,887 | 240 | 1,318 negative rows (min -2.67 h) |
| T_1_4 | 20,069 | 70,278 | 240 | |
| RESERVE_CREDIT | 14,594 | 48,550 | 240 | hours 3.33 until 2026-02-28 (12,842 rows), then 3.0 (1,224) and 4.0 (526) |
| MIN | 5,485 | 13,322 | 240 | |
| DRAFT_THX | 4,620 | 65,085 | 360 until 2026-01-31, **480 from 2026-02-01** | premium_cad is the extra over 240 |
| AJU | 3,950 | 2,460 | 240 | |
| OVERTIME_THX | 3,670 | 44,659 | 360 until 2026-01-31, 480 from 2026-02-01 | |
| DUTY_PREMIUM_P10 / P30 / P16 | 998 / 192 / 27 | 0 | blank | flat **$500 / $1,500 / $2,000 per row** (amount only, no hours) |
| BME | 294 | 1,598 | 240 | |
| DRAFT_T2 | 56 | 721 | 480 | |
| HOLIDAY_T2 | 54 | 622 | 480 | |
| DMG | 5 | 13 | 240 | |

Observations that matter for the mapping:
* `amount_cad = hours x rate_cad` for every code (checked on AJU, CHV, ... totals). `rate_cad` is a **business constant (240 $/h base, 1.5x = 360, 2x = 480)**, not a payroll rate. The 360 -> 480 switch on 2026-02-01 for DRAFT_THX *and* OVERTIME_THX is therefore a rate-table effective date (new collective agreement), not an AIMS datum.
* RED_CAP (named in the brief) is **not** in the v3 file; it appears in AIMS (below) and in older notes.
* v3 D7 has 204 exact duplicate rows (same crew, period, code, hours, date, pairing).

### 1.2 AIMS objects (D7)

| Object | Rows | What it is | Verdict for D7 |
|---|---|---|---|
| **`TIMEPNCPNT`** | 355,053 | Materialised **timesheet PNC/PNT** report output (Snowflake name `TIMESHEET_PNC_PNT`, PierreEmail.md). One row per roster element (flight leg, ground leg or stand-alone activity) of a crew member, with the credited hours per pay code as **columns**. | THE source (hours). |
| `TSCPAYID` | 95,543 | `(ID, IDX, BEGPER, 33-byte blob)`: per crew and period start a *pay id/category* record; `IDX` takes the same values as `TIMEPNCPNT.ROSTER_CAT` (10, 47, 72, 75, 79...), `BEGPER` 7060..18171. Blob not read (may hold a payroll identifier - personal). | Not a source of amounts. Can supply the pay category per period (inference). |
| `ALLWRDC` / `vvALLWRDC` | 4.6M | Per crew per day alternate-credit entries (activity code + credit minutes, posted on the first day of each FTC period) + a float `AMNT` (-99 sentinel; 145 of 1,235 rows non-sentinel on a sample day, 0..20.33) + premium flags (`P16_PREM`, `PF_PREM`, `PR_PREM`, `OT_PREM`). | Credits in minutes, **no dollars**. `AMNT` max 20.33 (hours-like, not money). |
| `ALLWTYPE` | 8 | Allowance types: `Night premium` (window 1080..359 min), `Excess duty time`, `Time away (PNT)`, `Time away (PNC)`, `Training Duty`; `ADP_CODE` is **blank on all rows** (ADP = payroll export code). | Shows a payroll interface was designed but is not configured. |
| `ALLWMTHD` | 13 | Allowance calculation methods; 12 of 13 all-zero, method 1 has FROM/TO/UTC time flags and a multiplier byte 1. | Nothing usable. |
| `POSTINGRULES` | 250 | Monthly posting periods per position (CM=1, PO=2): `PR_TS_DATE_FROM/TO` and `PR_ALLW_DATE_FROM/TO` from 2017-03-02 to 2026-09-30. The calendar is the FTC calendar (2026-01-01..01-30, 01-31..03-01, 03-02..03-31, then calendar months). | Pay period boundaries. **Differs from Pierre's `pay_period`** (his duty 2026-01-31 is in "2026-01", 2026-03-01 in "2026-03"). |
| `EZYPAYROL` | **0** | Payroll rules (position multipliers, duty multipliers, `PAYMENT_TYPE`, `UNT_VALUE`, ...). Structure exists, **empty**. | Proves payroll rules are not configured in TSC. |
| `CREWCOST` | 72 | Costing coefficients by `ELEMENT` (104 = "Salaires PNT": 125 / 80 / 75 for CM / PO / ME per block hour, 105/107 = 1.00, 106 = "salaires PNC" 55 / 45 / 35 for DV / DA / AB) x aircraft type. Element names from `COSTELEM` ("Salaires PNT", "Depenses PNT", "Salaires PNC", ...). | A **flight-costing model**, not payroll (125 $ vs 240 $/h). Unusable as pay rate. |
| `CATRCOST`, `FLTCOST`, `FUELCOST`, `CITYCOST` | 1 / 3,907 / 2 / 4,494 | Costing tables (charter cost, per flight element, fuel, city-pair fares). | Not payroll. |

**Conclusion on amounts: no payroll amount exists in TSC.** Evidence: (1) `TIMEPNCPNT` has 24 pay-code columns, all in hours (CHV max 44.5, sums per code are hour-sized); (2) `EZYPAYROL` is empty and `ALLWTYPE.ADP_CODE` is blank; (3) `ALLWRDC.AMNT` max 20.33; (4) `CREWCOST` rates (125/80/75) are a costing model that does not match the 240/360/480 used by Pierre. `rate_cad`, `amount_cad`, `premium_cad` must come from a business rate table (240 $/h; multiplier 1.5 to 2026-01-31, 2.0 from 2026-02-01) applied to the hours.

### 1.3 `TIMEPNCPNT` in detail (new object)
* Key (clustered, unique): `RUNID, USER_ID, CLONE_ID, PUB_IND, DUTY_ORDER, DUTYDAY, DUTYNO, LEG_DAY, LEG_DEP, LEG_CARRIER, LEG_FLT, LEG_LEGCD, GRDDUTYBEG, ID` (= ROSTER key + run).
* `RUNID` = run timestamp as text `ddMMyyyyHHmmss` (inference: `02082026041235` = 2026-08-02 04:12:35). 18,331 runs; one run holds 1-3 crew (a per-crew or small-batch report job). `USER_ID` always the same user (1 distinct), `CLONE_ID` 4 values, `PUB_IND` always `A`.
* **Two snapshots per crew and pay month** (11,124 crew-months have exactly 2 runs, 3 have 1): a first run about 2 days after the period ends (`02/08` for 07-2026, `02/09` for 08-2026, `02/10` for 09-2026) and a second about 22 days after (`22/08`, `22/09`, `22/10`; for 06-2026 both on 22-23/07). The second run contains adjustments (e.g. pilots 07-2026: T_1_5 rows 342 -> 511, hours 4,121 -> 6,201; CHV 51,567 -> 49,609 h; P10 13 -> 23). **Use the latest run per (crew, TS_MY).**
* `TS_MY` = pay month as text `MM-YYYY`. Present: 06-2026, 07-2026, 08-2026, 09-2026 only (88,371 / 87,941 / 88,828 / 89,913 rows, about 2,780 crew incl. cabin crew; about 715-735 pilots per month).
* Leg dates in the table: `DUTYDAY` 16948 (2026-05-27) .. 17081; `LEG_DAY` 16948 .. 17081 (trips that start in late May / end in early October).
* Grain by element kind (pilots 07-2026, run 22): flights `LEG_FLT > 0` 7,083 rows (all with `TRIP_CODE`, `FLIGHT_NUMBER`), **day-level / activity rows `LEG_FLT = 0`, `LEG_DAY = 0`, `DUTYNO < 0`** 5,182 rows (activity code = `-DUTYNO` = `CRCODES.ID`, text in `TRIP_CODE`, day in `DUTYDAY`), ground legs `LEG_FLT < 0` 110 rows.
* Other columns: `CREW_POS` (CM, PO = pilots; DV, AB, SU = cabin), `CREW_BASE` (YUL, YYZ), `AC_NO` (3-char aircraft type code `321`, `32Q`, `333`, `332` = `vvAIRCTYPE.IATACODE`; never blank, also on activity rows), `ROSTER_CAT` (= `CREWCAT` index at the time: 10/11 "BLOC REGULIER PNT (CC26)", 47 "BLOC PVHR (CC26)", 72 "BLOC INACTIF", 76 "SYNDICAT PNT", 80 "RESERVE", 94 "SYNDICAT 95 HRS 18/10/24" ...), `BLOCK_PR` (block, minutes), 24 pay columns, `SPEC_ACT` (DON, SWITCH, OPEN, REAF, DRAFT B / DRAFT O / DRAFT PV, PICK-GIV...), `CODE1..10`/`VALUE1..10` (absence/credit codes such as MAL, PANN, CPP4, CSS with hours; same code family as `ALLWRDC`).
* Pay columns, pilots, run 22 of 2026-09 (all crew): non-zero rows / total hours: CHV 17,147 / 167,108 (339 negative), AJU 2,137 / 1,258, MIN 1,592 / 4,390, **C_IN 1,115 / 6,086**, R17 939 / 802, DMG 913 / 10,187, T_1_5 744 / 9,047, T_1_4 641 / 2,120, T_1_2 229, T_1_6 219, BME 180 / 1,382, ER1 179, P14 140 (negative), RED_CAP 122 (negative, -264.7 h), P15 65, P10 53 / 652, R15 43, T_2 21 / 154, P30 11 / 170, SEV1 4, SEV2 3, P16 3 (tinyint count), P14P15 0.

### 1.4 Column mapping (one row per corpus column)

| corpus column | status | AIMS source | transformation | evidence | gap / risk |
|---|---|---|---|---|---|
| crew_id | DERIVABLE | `TIMEPNCPNT.ID` (= `ROSTER.ID`) | pseudonymise to `P######` with the same surrogate map as D1/D2 (outside AIMS) | 717/713/728/736 pilot crews per month | the surrogate-key table must be shared with the other datasets; pilots = `CREW_POS IN ('CM','PO')` |
| base | DIRECT | `TIMEPNCPNT.CREW_BASE` | none (YUL/YYZ) | never blank in 12,375 pilot rows | Pierre has 67 blank rows; AIMS has none |
| fleet | DERIVABLE | `TIMEPNCPNT.AC_NO` -> `vvAIRCTYPE.IATACODE` | `321`,`32Q` -> A321; `332`,`333` -> A330 | AC_NO never blank | `AC_NO` semantics on activity rows (crew's fleet?) is inference |
| fleet_detail | DERIVABLE | same | `32Q` -> A321neoLR, `321` -> A321-200, `332` -> A330-200, `333` -> A330-300 | `vvAIRCTYPE.DESC_` | Pierre's v3 D1/D2 vs D7 fleet_detail disagree (his note 8); AIMS is internally consistent |
| pay_period | DERIVABLE | `TIMEPNCPNT.TS_MY` | `MM-YYYY` -> `YYYY-MM` | 4 distinct values | **only 2026-06..2026-09**; `POSTINGRULES` period boundaries differ from Pierre's (Jan-31, Mar-01) - needs a rule on which month a duty belongs to |
| pay_code | PARTIAL | unpivot of the pay columns (below) | see 1.5 | July/Aug 2026 comparison 1.6 | DRAFT vs OVERTIME and DRAFT_T2 vs HOLIDAY_T2 split is not reproducible with AIMS fields found; P10/P16/P30 are hours in AIMS but flat dollars in D7; C_IN, R15/R17, ER1, P14, P15, SEV1/2, T_1_2, T_1_6 exist in AIMS and not in D7 |
| hours | DERIVABLE | the value of the pay column (hours; negatives kept) | `CHV` minus reserve credit rows (1.5) | 1.6 | AJU and DMG hours differ strongly from Pierre (AJU 681 h vs 182 h for 07-2026; DMG 64 h vs 6 h) - his rule for them is unknown |
| rate_cad | **MISSING** | none | business rate table: 240 $/h; THX 360 -> 480 from 2026-02-01; T2 480 | constants in v3; `EZYPAYROL` empty | business input needed (effective dates per agreement) |
| amount_cad | **MISSING** | none (= hours x rate_cad) | compute | all v3 totals = hours x rate | not an AIMS fact; cannot validate V6 against "real pay", only against hours x assumed rate |
| premium_cad | **MISSING** | none | (multiplier-1) x 240 x hours for THX/T2 codes | v3 premium for THX = hours x 120 (360 era) / 240 (480 era) | same |
| duty_date | DERIVABLE | `DUTYDAY` (pairing start) or `LEG_DAY` (flight), activity rows: `DUTYDAY` | `DATEADD(DAY, n, '1980-01-01')`; text `DUTY_DATE_LOCAL` is local date | 22,999 flight rows: `DUTY_DATE_LOCAL` = date(`LEG_DAY`) for 17,404 (UTC vs local) | choose one convention (Pierre: leg date vs duty start differ on 2,035 of 4,676 draft rows between `duty_date` and `draft_leg_date`) |
| linked_pairing_id | DERIVABLE | `RTRIM(TRIP_CODE)` + `_` + `yyyymmdd(DUTYDAY)` | `TRIP_CODE` = `CRROUTE.DESC_` (100% match on 22,999 flight rows); **`TRIP_DAY` is NOT the pairing start** (equals `DUTYDAY` on 12,000 of 22,999) | verified join `CRROUTE (CDATE=DUTYDAY, CROUTE=DUTYNO)` | Pierre fills it only for DRAFT_* rows (4,676); AIMS can fill it for every flight row |
| draft_leg_date (optional) | DERIVABLE | `ROSTERDT` RECTYPE 21 / VALUE1 15,16,19,20 on the same leg key | `LEG_DAY` | 448 of 502 pilot T_1_5 flight rows (07-2026) carry a draft marker (446 x 19, 2 x 20), plus 3 of 4 T_2 rows | marker is per leg; Pierre's DRAFT_THX count differs (below) |
| draft_flight_no (optional) | DERIVABLE | `TIMEPNCPNT.FLIGHT_NUMBER` / `LEG_FLT` of the drafted leg | `'TS' + FLT` | as above | |

### 1.5 pay_code construction (verified)
| D7 code | AIMS rule | status |
|---|---|---|
| CHV | `CHV` column, on all elements **except** rows classified RESERVE_CREDIT | DERIVABLE |
| RESERVE_CREDIT | day-level row (`LEG_FLT = 0`, `DUTYNO < 0`) whose activity code is a reserve code (`CRCODES` reserve flag: byte 101 bit 7 or byte 98 bit 1) and whose `CHV` is 3.0-5.1 h: AM, PM (4.00 h, 240 min) and LCR (3.00 h, 180 min). Credit hours = `CRCODES` FTC minutes (bytes 89-90) / 60 | DERIVABLE (**exact match** for 07-2026: 187 rows / 604.0 h on both sides) |
| T_1_4, MIN, BME | same-named columns | DIRECT (BME exact: 12 / 62.4 h) |
| DRAFT_THX + OVERTIME_THX | `T_1_5` (1.5x credit hours) | PARTIAL: total matches (below); split not reproducible |
| DRAFT_T2 + HOLIDAY_T2 | `T_2` (2x) | PARTIAL |
| DUTY_PREMIUM_P10 / P16 / P30 | `P10`, `P16`, `P30` columns (presence, 23 / 3 / 2 rows in 07-09/2026 runs); Pierre prices them flat ($500 / $2,000 / $1,500) while AIMS stores hours-like values for P10 (281 h) and P30 (29.5 h) | PARTIAL (unit mismatch) |
| AJU | `AJU` column (hours) | PARTIAL (hours differ from Pierre) |
| DMG | `DMG` column | PARTIAL |
| RED_CAP | `RED_CAP` column, negative hours only (122 rows, -264.7 h in 2026-09); **absent in v3 D7** | DIRECT in AIMS |
| *(not in D7)* C_IN, T_1_2, T_1_6, R15, R17, ER1, P14, P15, SEV1, SEV2 | AIMS-only pay columns | UNKNOWN meaning; C_IN has 414 pilot rows / 2,570 h in 07-2026 (about 5% of CHV) and is silently dropped by Pierre |

Evidence for T_1_5 / T_2 draft link: of the 502 pilot flight rows with `T_1_5 <> 0` in 07-2026 (6,172.9 h), 448 (5,643.4 h) have a `ROSTERDT` draft marker on the same ROSTER key and 54 do not; `SPEFREC`-style text in `SPEC_ACT` ("DRAFT B/O/PV") is not populated on these rows.

### 1.6 Comparison with Pierre v3 D7 (pilots, latest run vs `pay_period`)

| pay_period 2026-07 | AIMS rows / hours | Pierre rows / hours |
|---|---|---|
| CHV + RESERVE_CREDIT | 5,212 / 49,609.1 | 5,031 + 187 = 5,218 / 48,925.4 + 604.0 = 49,529.4 (-0.2% hours) |
| of which reserve activity rows | 187 / 604.0 | RESERVE_CREDIT 187 / 604.0 (exact) |
| T_1_4 | 689 / 2,246.4 | 692 / 2,226.8 |
| MIN | 334 / 1,032.3 | 321 / 997.4 |
| BME | 12 / 62.4 | 12 / 62.4 (exact) |
| AJU | 679 / 680.9 | 748 / 182.4 |
| DMG | 13 / 64.3 | 2 / 5.8 |
| T_1_5 | 511 / 6,200.8 | DRAFT_THX 284 / 4,090.2 + OVERTIME_THX 150 / 2,097.5 = 434 / 6,187.7 |
| T_2 | 16 / 112.1 | DRAFT_T2 4 / 60.7 + HOLIDAY_T2 3 / 42.4 = 7 / 103.1 |
| P10 / P30 | 23 / 2 | 21 / 2 |
| RED_CAP / C_IN | 2 (-5.0 h) / 414 (2,570 h) | absent / absent |

pay_period 2026-08: CHV + reserve 5,442 / 51,666.7 vs 5,170 + 242 = 5,412 / 51,074.1; BME 13 / 66.9 exact; T_1_4 728 / 2,511.9 vs 710 / 2,402.8; T_1_5 554 / 6,536.2 vs 319 + 169 = 488 / 6,803.0; DMG 23 / 109.9 vs 0; AJU 581 / 839.1 vs 642 / 248.1.
Reading: the first run (02/08) disagrees with Pierre more than the second (22/08), so Pierre's extract is a later snapshot; small residual differences (0.2-3%) are consistent with different runs/crews and an extra filter on his side. The unexplained gaps are AJU, DMG (hours) and the DRAFT/OVERTIME split.

### 1.7 Tested SQL sketch (pilots, July 2026 pay month, latest run per crew)
```sql
WITH t AS (
  SELECT *, SUBSTRING(RUNID,5,4)+SUBSTRING(RUNID,3,2)+LEFT(RUNID,2)+RIGHT(RUNID,6) AS runkey   -- yyyyMMddHHmmss
  FROM TSC.dbo.TIMEPNCPNT WHERE TS_MY = '07-2026' AND CREW_POS IN ('CM','PO')),
l AS (SELECT *, DENSE_RANK() OVER (PARTITION BY ID, TS_MY ORDER BY runkey DESC) rk FROM t)
SELECT v.pay_code, COUNT(*) rows_nonzero, CAST(SUM(v.hrs) AS decimal(12,1)) hours
FROM l CROSS APPLY (VALUES ('CHV',CAST(l.CHV AS float)),('T_1_4',l.T_1_4),('T_1_5',l.T_1_5),('T_2',l.T_2),('MIN',l.MIN),
                           ('AJU',l.AJU),('BME',l.BME),('DMG',l.DMG),('P10',l.P10),('P30',l.P30),('RED_CAP',l.RED_CAP),('C_IN',l.C_IN)) v(pay_code,hrs)
WHERE l.rk = 1 AND v.hrs <> 0 GROUP BY v.pay_code ORDER BY rows_nonzero DESC;
```
Result: CHV 5,212 / 49,609.1; T_1_4 689 / 2,246.4; AJU 679 / 680.9; T_1_5 511 / 6,200.8; C_IN 414 / 2,570.2; MIN 334 / 1,032.3; P10 23 / 281.5; T_2 16 / 112.1; DMG 13 / 64.3; BME 12 / 62.4; P30 2 / 29.5; RED_CAP 2 / -5.0.
Reserve credit (day-level rows, reserve codes):
```sql
SELECT RTRIM(TRIP_CODE) code, COUNT(*) n, SUM(CHV) chv_h
FROM TSC.dbo.TIMEPNCPNT
WHERE CREW_POS IN ('CM','PO') AND RUNID LIKE '22%' AND TS_MY='07-2026' AND LEG_FLT=0 AND DUTYNO<0 AND CHV BETWEEN 3 AND 5.1
  AND RTRIM(TRIP_CODE) IN (SELECT RTRIM(CC) FROM TSC.dbo.CRCODES
        WHERE CAST(SUBSTRING(DATA_BEGIN_END,101,1) AS tinyint) & 128 = 128 OR CAST(SUBSTRING(DATA_BEGIN_END,98,1) AS tinyint) & 2 = 2)
GROUP BY RTRIM(TRIP_CODE);   -- LCR 144 / 432.0 ; PM 28 / 112.0 ; AM 15 / 60.0  = 187 / 604.0
```

### 1.8 History depth
* `TIMEPNCPNT`: 4 pay months (06-2026 .. 09-2026), runs from 2026-07-22 to 2026-10-22; **no earlier states, no history table**. Needed: 2024-04..2026-08; CrewSim ideal: 36 months from 2023-08.
* Pierre states longer history depends on a Snowflake evaluation of `TIMESHEET_PNC_PNT` (PierreEmail.md) - i.e. the history lives in Snowflake, not in TSC.
* Recomputing hours from `ROSTER`/`CREWLEG`/`LEGTIMES`/`CRCODES` for earlier months would need the pay-credit rules (minimum credit, T_1_4, THX/T2 conditions, C_IN meaning); not attempted - `rpt.CalculateCrewFTC` computes FTC for legality, not the pay register. Untested hypothesis.

### 1.9 Verdict D7: **PARTIAL**
Hours of CHV, RESERVE_CREDIT, T_1_4, MIN, BME and the total of the 1.5x/2x premium hours can be read directly from `TIMEPNCPNT` (and match Pierre within about 0.2%), with pairing and draft-leg links richer than Pierre's. But AIMS contains no rate and no dollars, the draft/overtime/holiday split and AJU/DMG are not reproduced, and the history is only 4 months, so the 28-month backtest dataset cannot be produced from TSC today.
Missing, in order: (1) history before 2026-06 (Snowflake `TIMESHEET_PNC_PNT` or a scheduled archive of `TIMEPNCPNT` runs from now on); (2) rate table with effective dates (240 $/h; 1.5x until 2026-01-31, 2x from 2026-02-01; DRAFT vs OVERTIME definitions) [CONFIRM Pierre/Finance]; (3) Pierre's rule that separates DRAFT_THX from OVERTIME_THX and DRAFT_T2 from HOLIDAY_T2, and his AJU/DMG filters; (4) meaning of C_IN, R15, R17, ER1, P14, P15, SEV1/2, T_1_2, T_1_6; (5) unit of P10/P16/P30 (hours in AIMS, flat $ in D7); (6) which month a duty belongs to (Pierre calendar months vs FTC calendar in `POSTINGRULES`); (7) pseudonymisation key.

---------------------------------------------------------------------------------------------------

## 2. D8 `d8_flight_movements`  (and D9 note)

### 2.1 What the real v3 file contains
65,760 rows, dates 2024-04-23..2026-08-31, 13 columns + `fleet_detail`, `delay_subcode`, `delay_description`. Per month about 1,730-2,650 rows.
* `cancelled = 1`: 2,617 rows (`cancel_reason` NOT_OPERATED_4_1 2,610, NO_ACTUAL_TIMES 7); none has actual times; 2 non-cancelled rows lack actual departure.
* First week: 2024-04-23..30 has 311-345 rows/day and 1,801 of 2,286 April rows flagged cancelled: by fleet TRN 1,129, P295 454, PDH4 97, 7M8 77, W737 14, B737 10, W738 10, W7S8 4, W7M8 2, A321 4.
* From 2024-05-01: 816 cancelled (A321 472, A330 248, 343C 28, 332C 22, 7M8 44, P295 2), about 15-60 a month.
* 708 rows with origin = destination; 713 duplicate rows on (flight_no, date, origin, destination).
* `delay_minutes` = **max(0, actual departure - scheduled departure)** (verified on 4,726 rows of Jan-Feb 2026: 2,532 equal the signed difference, 2,194 are early departures clipped to 0, 0 other).
* `iata_delay_code` non-blank on 13,341 rows (about 49% of delayed rows; Jan 2026: 629 coded of 1,274 delayed); codes are the 2-3 digit AIMS/IATA numbers (89 ATC/ground movement 1,911, 70 weather rotational 1,388, 81 ATC clearance/slots 1,340, 80, 41, 40, 99, 82, 84, 50, 83, 121...); `delay_description` = text of `DLYCD.DESC_`; `delay_subcode` 0 on 12,453 rows, otherwise 24..33.

### 2.2 AIMS objects (D8)

| Object | Rows | Grain / content | Date range | How written (inference) |
|---|---|---|---|---|
| `LEGMAIN` | 1.23M (carrier 1: 821k) | one leg `(DAY, DEP, CARRIER, FLT, LEGCD)`: STD/STA (UTC min), `AC`, `CANCELLED` (0/1/2), `LEGSTATUS`, `CNXREASON`, `ONDAY`/`ONTIME`, `DDLY`, `ADLY` | complete months from 2023-08 to 2026-10 (10,000-12,000 legs/month until 2024-04 because of 1,285 train legs a week; 2,100-3,200 afterwards) | schedule build + ops control |
| `LEGTIMES` | 429k | actuals (`OPSATD/OPSATA`, `BLOF/BLON`, `TKOF/TDOWN`, ETD/ETA), 1:0..1 with LEGMAIN | to 2026-10-28; every live own-fleet leg since 2024-05 has a row (live = with_times in all months 2024-06..2026-09) | movement messages |
| `vvAIRCTYPE` | 35 | `ACTYPE`, `IATACODE`, `DESC_`: 4 = 332 A330-200, 6 = 333 A330-300, 14 = 321 A321, 16 = 32Q A321neo, 18 = 320, **17 = TRN Train SNCF**, 33 = P295 Embraer E195-E2, 30 = PDH4 Dash 8-400, 31 = 7M8 and 26 = W7M8 (737 MAX 8), 28 = W7S8, 23 = W737, 25 = W738, 34 = 332C, 35 = 343C | - | master data |
| `LEGDELAYS` | 768k (carrier 1) | per leg and delay line `(DAY,DEP,CARRIER,FLT,LEGCD,KIND,INDEX_)`: `DLYC` (code id), `DLYSUBC`, `DLYT` (minutes), `OPSDLYC/OPSDLYSUBC/OPSDLYT` (ops-recorded code), `PRIM` | 2002..2026; about 15k-17k legs a year since 2022 (2024: 16,242 legs, 2025: 15,248, 2026: 14,780) | **KIND 1 = one line per delayed leg, `DLYT` = `DDLY` (departure delay) in 99% (1,246 of 1,262 legs), code almost always 99 "NOT ELSEWHERE"; KIND 2 = coded cause lines, their minutes sum to `ADLY` (1,646 of 1,678 legs)** (inference: the cause coding is entered against the arrival delay) |
| `DLYCD` | 255 | `DLYCD` (id), `CODE` ('089', '070'...), `DESC_` (100 chars), `CATIX` -> `DLYCAT` (1 Airports, 2 Tech Ops, 3 Flight Ops, 4 Inflight, 5 Operations, 6 Procurement, 7 Cargo & permits, 8 Rotational, 9 ACMI & contracts, 10 Others), `UNCNTRLBLE`, `AIRLINERESP`, `REACTIONARY`, `ALTCODE` (blank) | - | setup |
| `SUBDLY` | 39 | sub-codes (letters) per delay code, e.g. 52 A..K (Groundhandler, Maintenance, Catering, Fuelling, De-icing, Weather, Bird strike, Airport authority, Passenger, Crew caused damage); 83 A..E; 82 A "ATC short staff" | - | setup |
| `LEGTRDELAYS` | 236k | propagated (rotational / reactionary) delay: leg `(DAY,...)` <- source leg `FROM*`, with `DLYC`, `DLYSUBC`, `DLYT`, `ORDER_` | 2024-04-23..2026-08-31: 35,437 rows | derived |
| `LEGADDINFO` | 92k | fuel/payload plan, `NEW_DLY_NO`, `PRIM_DLY` (blank on all 1,129 rows in the window) | - | not usable for delay |
| `LEGMEMO` | 53.8k | free text; category 19 = delay remarks (34,661 rows, 22,130 legs in 2024-05..2026-08), 15, 13, 5, 16, 11 ... | - | **content not read**, count only; 33 of the 8,858 cancelled legs of 2025-01..2026-08 have a memo (2.5) |
| `CNGRSN` | 32 | index table 1..32, `CATEGORIES` blank | - | empty |
| `TABLES` record `CNXREASONS` (900 B) | 1 | 15-char labels: `NONE`, `ROSTER CHANGE`, `SICKNESS`, `AUTHORIZED SWAP`, `OPERATIONAL`, `COMMERCIAL`, `OWN WAY TRAVEL`, `PRIVATE ACCOMM`, `HOTEL CHANGE`, then empty | - | looks like a **crew/roster** cancellation-reason list, not a flight cancel list (inference) |
| `TABLES` record `OCNGRS0001..32` | 32 | operational change reasons: only #1 defined ("DO NOT CHANGE AIRCRAFT REGISTRATION") | - | setup |
| `LOG_LEGMAIN` | 1.33M | field-level audit of LEGMAIN (`AIMSFIELDID`, `OLDVALUE`, `NEWVALUE`, `ONDAY/ONMIN/ONSEC`, user) | **2024-05-13 .. 2026-10-27** (2024: 281,638; 2025: 595,718; 2026: 454,930) | AIMS audit trigger; indexed on `DAY,DEP,CARRIER,FLT,LEGCD,...` and on `ONDAY,...` |
| `LOG_LEGTIMES`, `LOG_LEGDELAYS` (455k), `LOG_LEGMEMO` (750k) | | same pattern | not profiled further | |

### 2.3 Why Pierre's weird rows exist (explained from AIMS)
* **TRN / P295 / 7M8 / PDH4 / 343C / 332C / W737 / W738 / W7S8 / W7M8 = AIRCTYPE codes other than own metal.** TRN (`AC = 17`, FLTYPE 9, flight numbers 6500-6540) are SNCF train legs: 1,285 legs in 2024-04-23..30 with `CANCELLED = 0` and **no LEGTIMES row** (they stopped after 2024-04: 'surface vehicle' FLTYPE 9 169,419 legs 2019-05..2024-04). The others are wet-lease/ACMI/charter aircraft (AC 33, 30, 31, 23, 25, 26, 28, 34, 35). All have no LEGTIMES. So the "79% cancelled" first week is Pierre's rule "no actual times = not operated" applied to non-flown, non-TSC-metal legs. Filter `AC IN (4,6,14,16,18)` (own metal) or `FLTYPE <> 9` removes them; there is no "real" cancellation hidden there.
* **origin = destination rows** = return legs: `LEGCD` A/B/C (return to ramp, LEGSTATUS 5) and D (return from airborne, LEGSTATUS 6), `DEP = ARR` (490 own-carrier legs in 2024-04-23..2026-08-31: A 438 + 3, B 16 + 1, C 3, D 22, plus a few). They have LEGTIMES. Pierre has 708 such rows (246 "cancelled"), so his extract also duplicates other rows; AIMS keeps them distinct through `LEGCD` (PK). **Duplicates on (flight, date, origin, destination) are the original leg + its return leg(s); there are no true duplicate rows in AIMS.**
* `fleet` for `TRN` and the others = `vvAIRCTYPE.IATACODE`; `A321` / `A330` = AC 14, 16 / 4, 6.

### 2.4 Column mapping

| corpus column | status | AIMS source | transformation | evidence | gap / risk |
|---|---|---|---|---|---|
| flight_no | DERIVABLE | `vvCarriers.ALTCODE` (TS for `CARRIER = 1`) + `LEGMAIN.FLT` | `'TS' + FLT` | vvCarriers row 1 CODE TSC / ALTCODE TS | `LEGCD` must be kept to avoid ambiguity |
| date | DERIVABLE | `LEGMAIN.DAY` + `STD` | **local** date of scheduled departure (`std_utc + offset`) | Pierre's local recomputation | day number is UTC; shift by station offset |
| origin / destination | DIRECT | `LEGMAIN.DEP` / `ARR` | `RTRIM` | | self-loops = return legs (see 2.3) |
| fleet | DERIVABLE | `LEGMAIN.AC` -> `vvAIRCTYPE.IATACODE` | 4,6 -> A330; 14,16,18 -> A321 (320 -> A320); others keep code | 2.2 | choice of A320 grouping is a business decision |
| fleet_detail | DERIVABLE | `vvAIRCTYPE.DESC_` | `16 -> A321neoLR`, `14 -> A321-200`, `4 -> A330-200`, `6 -> A330-300`, `18 -> A320-200` | | |
| sched_dep_local / sched_arr_local | DERIVABLE | `DATEADD(MINUTE, STD or STA, DATEADD(DAY, DAY, '1980-01-01'))` + `CrewSchedAI.dbo.GetEffectiveOffsetUtc(DEP or ARR, utc_instant)` hours | local = UTC + offset (arrival date = `DAY + STA/1440`) | function resolved the offset for 2,895 of 2,895 January-2026 own legs | 5 airports (`ECP,YTM,BYJ,TSF,CAX`, `ZONENO = 0`) return NULL per README; Pierre states AIMS' own local columns are wrong |
| actual_dep_local | DERIVABLE | `LEGTIMES.OPSATD`, fall back `BLOF` (off-block) | same conversion | `OPSATD = BLOF` on 98% (README); `OPSATD` NULL on 8 of 51 checked legs and 53 of 2,259 legs in 2026-06 | Pierre's rule for which one he uses is unknown |
| actual_arr_local | DERIVABLE | `LEGTIMES.OPSATA`, fall back `BLON` | same | | |
| delay_minutes | DERIVABLE | `max(0, actual_dep - sched_dep)` = `max(0, LEGMAIN.DDLY)` | equals `DDLY` where positive | `DDLY = BLOF - STD` in 98.9% (README); Pierre's delay = clipped dep diff on 4,726 of 4,726 rows | **arrival delay** (`ADLY`) is a different number (Pierre's equals it on 272 rows only) |
| iata_delay_code | DERIVABLE | `LEGDELAYS` (KIND 2 lines) `DLYC` -> `DLYCD.CODE` | main code per leg = KIND 2 line with largest `DLYT`; Pierre's values are the numeric id (89 = '089') | Jan 2026: 1,485 of 1,485 legs with `ADLY > 0` have a coded line (100%); 1,259 of 1,259 legs with `DDLY > 0` have a KIND 1 line; Pierre codes 629 of 1,274 delayed legs | AIMS KIND 2 `DLYC = 89` has 14,329 lines in 2024-05..2026-08 vs 1,911 in Pierre: his selection rule (one code per leg? departure side only? exclude 73/99?) is unknown. Code **99 "NOT ELSEWHERE" is the placeholder** (24 of 1,492 coded legs in Jan 2026) |
| delay_subcode | DERIVABLE | `LEGDELAYS.DLYSUBC` | Pierre keeps the raw tinyint (24..33); letters in `SUBDLY` = rank 24 -> A ... 33 -> K skipping I (inference from `DLYC = 52`, ten letters A-K without I) | Pierre's subcodes 24,25,27,30,26,28,29,33,31 | `SUBDLY` defines only 39 sub-codes; e.g. code 82 shows sub 24..27 in data but only A is defined |
| delay_description | DERIVABLE | `DLYCD.DESC_` | trimmed (Pierre's text is the first 48-50 characters) | Pierre sample for 89, 70, 81 equals `DESC_` | |
| cancelled | **PARTIAL** | `LEGMAIN.CANCELLED`, `LEGSTATUS = 1` (CA), `ONDAY` | see 2.5; **Pierre's flag is not CANCELLED** | June 2026: of his 46 cancelled rows, matched on (date, flight, dep, arr), 42 are `CANCELLED = 0` with a LEGTIMES row (only 8 of the 51 matched legs have `OPSATD` NULL); AIMS has 470 `CANCELLED <> 0` legs in that month vs his 46 | business definition of "cancelled" needed |
| cancel_reason | **PARTIAL / UNKNOWN** | `LEGMAIN.CNXREASON` (1..7); cancelled legs have no delay lines and only 33 memos in 8,858 legs | | 2.5 | true cause (weather / crew / technical) is **not recorded** as coded data |

### 2.5 Cancellations and the "true cause"
* `LEGMAIN.CANCELLED`: 0 live, 1 cancelled with a reason, 2 removed/cancelled (documented as unresolved). Own carrier 2025-01..2026-08: **1 = 644 legs (all with `CNXREASON > 0`, 642 with `ONDAY`)**, 2 = 8,214 legs (4,438 with reason, 3,776 without; `LEGSTATUS = 1` "CA" on 3,301 of the 3,573 scheduled-service legs without reason).
* Decision lead (`DAY - ONDAY`): CANCELLED 1: 427 > 30 d, 24 3-7 d, 132 1-2 d, 54 same day; CANCELLED 2: 3,891 no ONDAY, 3,882 > 30 d, 143 3-7 d, 80 1-2 d, 62 same day. So about 330 legs in 20 months (about 16 a month) are cancelled within 2 days of departure (operational cancellations); most `CANCELLED <> 0` legs are schedule-level removals decided more than 30 days ahead.
* `CNXREASON` over 2023-08..2026-10 own legs: 0 = 4,929 (all CANCELLED 2), 1 = 22,465 (1,551 x CANCELLED 1), 2 = 76, 3 = 148, 4 = 97, 5 = 12, 6 = 28, 7 = 375. The only dictionary found, `TABLES.CNXREASONS`, lists crew-oriented labels (NONE, ROSTER CHANGE, SICKNESS, AUTHORIZED SWAP, OPERATIONAL, COMMERCIAL, OWN WAY TRAVEL, PRIVATE ACCOMM, HOTEL CHANGE); with either 0-based or 1-based indexing the mapping to flights makes no sense (code 1, the vast majority, would be NONE or ROSTER CHANGE; code 7 on flights would be OWN WAY TRAVEL / PRIVATE ACCOMM). **Do not decode `CNXREASON` without confirmation from the AIMS administrator.** `LEGMAIN.CHANGE_REASON`, `PLAN_CHANGE_REASON`, `CREW_REL_CHANGE_REASON` are all zero; `CNGRSN` is empty; cancelled legs have **0** `LEGDELAYS` rows and 33 `LEGMEMO` rows in 8,858 legs.
* Therefore: weather / crew / technical cancellation cause: **MISSING in AIMS coded data**; it could only be recovered from free-text memos (not read here) or from the operations-control system.
* `LOG_LEGMAIN` (from 2024-05-13) can show when/who cancelled and the sequence of changes (field ids 19397..19453), but not a cause.

### 2.6 Coverage comparison (month by month)
Pierre's D8 rows per month (about 1,730-2,650) equal AIMS own-metal live legs: June 2026 AIMS 2,259 live (+470 cancelled) vs Pierre 2,307; January 2026 AIMS 2,513 live vs Pierre 2,564. 2024-05..2026-08: every month has a LEGTIMES row for every live leg (`with_times = live`). Only CANCELLED = 2 legs (about 400-1,800 a month before mid-2025) are not in Pierre's file, i.e. **Pierre's D8 contains almost none of AIMS' cancellations** (his 816 vs about 12,500 `CANCELLED <> 0` legs since 2024-05). Whether those are real cancellations or schedule changes is the open business question; the CrewSim cancel-probability calibration (his note 3: 29 cancellations from YUL/YYZ in the fitting window) depends on it.
Delay-code coverage: AIMS has a code for all delayed legs; Pierre has it for about 49%.

### 2.7 Tested SQL sketch (January 2026 = LEG_DAY 16802..16832)
```sql
WITH leg AS (
 SELECT lm.DAY, lm.DEP, lm.ARR, lm.CARRIER, lm.FLT, lm.LEGCD, lm.AC, lm.CANCELLED, lm.LEGSTATUS, lm.CNXREASON, lm.DDLY, lm.ADLY,
        lt.OPSATD, lt.OPSATA, lt.BLOF, lt.BLON,
        DATEADD(MINUTE, lm.STD, DATEADD(DAY, lm.DAY, '1980-01-01')) AS std_utc,
        DATEADD(MINUTE, lm.STA, DATEADD(DAY, lm.DAY, '1980-01-01')) AS sta_utc
 FROM TSC.dbo.LEGMAIN lm
 LEFT JOIN TSC.dbo.LEGTIMES lt ON lt.DAY=lm.DAY AND lt.DEP=lm.DEP AND lt.CARRIER=lm.CARRIER AND lt.FLT=lm.FLT AND lt.LEGCD=lm.LEGCD
 WHERE lm.CARRIER = 1 AND lm.DAY BETWEEN 16802 AND 16832)
SELECT COUNT(*) legs, SUM(CASE WHEN AC IN (4,6,14,16,18) AND CANCELLED=0 THEN 1 ELSE 0 END) own_live,
       SUM(CASE WHEN AC IN (4,6,14,16,18) AND CANCELLED=0 AND DEP<>ARR THEN 1 ELSE 0 END) own_live_no_return_leg,
       SUM(CASE WHEN AC IN (4,6,14,16,18) AND CANCELLED=1 THEN 1 ELSE 0 END) own_cancelled_1,
       SUM(CASE WHEN o.Effective_UTC_Offset IS NOT NULL THEN 1 ELSE 0 END) dep_offset_resolved
FROM leg l OUTER APPLY CrewSchedAI.dbo.GetEffectiveOffsetUtc(l.DEP, l.std_utc) o;
-- run: legs 2,895; own_live 2,513; own_live_no_return_leg 2,474; own_cancelled_1 12; cancelled any 382; live with OPSATD 2,435; offsets 2,895/2,895
```
Delay code (main KIND 2 line per leg, same window): 2,513 live legs, 1,485 with `ADLY > 0`, 1,492 with a code, **1,485 of 1,485 delayed legs coded**, 24 coded 99, 2 codes not in `DLYCD`:
```sql
WITH d AS (SELECT DAY,DEP,CARRIER,FLT,LEGCD,DLYC,DLYSUBC,DLYT,
   ROW_NUMBER() OVER (PARTITION BY DAY,DEP,CARRIER,FLT,LEGCD ORDER BY DLYT DESC, INDEX_) rn
   FROM TSC.dbo.LEGDELAYS WHERE KIND=2 AND CARRIER=1 AND DAY BETWEEN 16802 AND 16832)
SELECT d.DLYC, RTRIM(c.CODE) code, RTRIM(c.DESC_) descr, d.DLYSUBC
FROM d LEFT JOIN TSC.dbo.DLYCD c ON c.DLYCD=d.DLYC WHERE d.rn=1;
```

### 2.8 History depth (D8)
`LEGMAIN` / `LEGTIMES` / `LEGDELAYS`: continuous, own-carrier legs every month from 2023-08 (the first month checked) to 2026-10 (2023-08: 10,715 legs ... 2026-10: 2,148), so **2024-04-23..2026-08-31 and the 36-month ideal from 2023-08 are both covered**. The first week of April 2024 is clean in AIMS (see 2.3). Past states: only `LOG_LEGMAIN` from 2024-05-13 (original schedule via `ORGSTD/ORGSTA/ORGDAY`; cancellations via `ONDAY`).

### 2.9 D9 note
D9 (station-day disruption class from mean departure delay, cancellation count and thresholds 5/20/45) is a deterministic function of D8; the D8 coverage above (every leg since 2023-08) is sufficient, so D9 needs no separate AIMS source.

### 2.10 Verdict D8: **MOSTLY**
Times, fleet, delay minutes, IATA code, sub-code and description can be produced directly with 36-month coverage and better code coverage than Pierre's file; the odd rows he asked about are explained (non-own-metal types incl. train, return legs). The cancel flag and cause cannot be reproduced: his flag is not `LEGMAIN.CANCELLED`, AIMS has about 15 true late cancellations a month plus schedule removals, and no coded cause.
Missing, in order: (1) the business definition of "cancelled" (which of `CANCELLED` 1 / 2, `LEGSTATUS` 1, lead time) and Pierre's own rule (NOT_OPERATED_4_1); (2) cancellation cause: confirm `CNXREASON` dictionary with the AIMS admin, otherwise unavailable; (3) Pierre's rule for the main delay code per leg; (4) A320/A321 fleet grouping; (5) whether to include wet-lease / ACMI types.

---------------------------------------------------------------------------------------------------

## 3. D10 `d10_positioning_invoices`

### 3.1 What the real v3 file contains
7,086 rows, dates 2025-05..2026-08 (2025-05: 2, 2025-06: 43, 2025-07: 397 ... 2026-03: 731, 2026-08: 285), cost types DEADHEAD 6,103 rows ($3.56 M, avg 583), HOTEL 828 ($2.18 M, avg 2,637, max $157,965), TRANSPORT 155 ($75 k); **272 negative amounts** (credits), 982 rows (13.9%) without crew_id, 2,505 (35%) without pairing_id, 16 exact duplicates, stations are all airport codes (YYZ 1,731, YUL 1,613, LIS 352, YHZ 348, CDG 341 ...). "PNT costs only" (PierreEmail.md).
Per-night hotel volume in AIMS is about 9,300 live crew lines in January 2026 vs 627 D10 rows for the month in total: D10 holds **invoice lines**, not bookings.

### 3.2 AIMS objects (D10)

| Object | Rows | Content | Prices? |
|---|---|---|---|
| `HOTAC` | 8.35M | booking lines. Category 0 = hotel (supplier -> `HOTEL`), 1 and 4 = transport/transfer (inference), 2, 3, 5 unknown. 14 columns: `PROCESSSTATUS, CREWID, CHECKINDAY, CATEGORY, SUPPLIERSTN, SUPPLIER, REPLACEDWITHID, NAMECHANGESTATUS, FLTNO, LEFTSTN, CROUTE, CDATE, AUTOINC, DATA_BEGIN_END` | **No price column.** The 1,089-byte blob holds check-in/out day+minute, flags, positions; byte profile of 444 category-0 rows shows time/flag fields in bytes 1-46 and 148-234, nothing identifiable as money (not decoded as IEEE floats; 'undecoded' remains) |
| `HOTEL` | 1,199 | hotel master; name carries contract tags (`-20H`, PNT, PNC); bytes 525-538 hold float32 values (95.0, 180.0, 13.0, 75.0, 50.9...) next to the 2-byte transit minutes at 539-540 | Possibly distances; **meaning unknown, not shown to be a room rate** |
| `HOTELDT` | 1,981 | hotel date/time windows (types 0, 1, 13) | no |
| **`HOTACPRICE0`** | 714 | `(CREWID, SUPPLIERSTN, SUPPLIER, BOOKINGDATE, EXTRAPRICEIDX 1-5, EXTRAPRICEVALUE)`: ad-hoc extra price lines, values 2.99..3,552.81 | **Only real prices in TSC, but dead**: last booking date per index 2013-2023 except idx 2 (212 rows, to 2026-05-24); 0 negatives |
| `CITYCOST` | 4,494 | fare rate card per `(carrier, DEP, ARR)`: `PREVIOUSRATEY` (0..5,870, avg 653.7 on 3,566 non-zero rows, 118 carriers, 394 pairs with YUL) + doubles in the blob | Fare **rate card**, current only, no transaction history; usable only as an estimator of deadhead cost |
| `DEADHEAD` | 203,982 | timetable of partner flights for positioning (SDAY 2026-09-22 .. LDAY about 2027-12, 66 carriers, 1,731 city pairs): future schedule, not tickets | no |
| `CREWLEG` (`PAX = 1`) | | deadhead flag per pairing leg. Own carrier 398 crew-legs and partner/surface 1,972 in January 2026 (1,231 pairings) | no |
| `FLTCOST`, `CREWCOST`, `COSTELEM`, `vvAIRCTYPE.OPERATING_COST` | | flight/crew costing model (not invoices) | model only |

### 3.3 Events, depth and joins
* Live hotel stays (`PROCESSSTATUS = 0 AND CATEGORY = 0`) by check-in year: 2022: 3, **2023: 30,033, 2024: 116,742, 2025: 118,735, 2026: 126,085** (crew rows nearly 100%; negative `CREWID` = vacancy placeholders). So the event history starts in about 2023-09 and covers all of D10's window (2025-05..) and the CrewSim 36-month ideal only from 2023-09.
* Deadhead crew-legs (`CREWLEG.PAX = 1`, `REMOVED = 0`) by year: 2022: 19,314, 2023: 21,653, 2024: 23,542, 2025: 20,131, 2026: 22,941 (partner/surface about 75-77%). Crew on the leg: join `ROSTER` (key = leg key + pairing).
* January 2026 (CHECKINDAY 16802..16832, `PROCESSSTATUS = 0`): category 0: 9,333 crew lines in 42 hotel stations, 1,861 pairings, 1,659 crew (+2 vacancy lines); category 1: 2,481 (1 supplier station); category 4: 13,062 (1,905 pairings); category 2: 78; 3: 17; 5: 449.
* Pairing link: `HOTAC.CDATE/CROUTE` -> `CRROUTE.DESC_` (pairing code) gives the D10 `pairing_id` convention; for deadhead `CREWLEG.CDATE/CROUTE`.

### 3.4 Column mapping

| corpus column | status | AIMS source | transformation | evidence | gap / risk |
|---|---|---|---|---|---|
| date | PARTIAL | `HOTAC.CHECKINDAY` (hotel/transport), `CREWLEG.DAY` (deadhead) | day number -> date; **event date, not invoice date** | 3.3 | invoice date unknown; Pierre's file starts 2025-05-28 |
| station | DERIVABLE | `HOTAC.SUPPLIERSTN` (cat 0), `LEFTSTN` (cat 1,4), deadhead `DEP` | `RTRIM`; IATA codes | 42 hotel stations Jan 2026 | no `CEP8/FCO1`-style codes issue found |
| cost_type | DERIVABLE | `CATEGORY = 0` -> HOTEL, `CATEGORY IN (1,4)` -> TRANSPORT (inference), `PAX = 1` -> DEADHEAD | event type | `CREWLEG.PAX` documented | categories 2, 3, 5 unknown (545 lines in Jan 2026) |
| amount_cad | **MISSING** | none | at best estimate: deadhead = `CITYCOST` fare (current rate card); hotel = `HOTACPRICE0` extra price (714 rows) | no price column in HOTAC; `HOTEL` floats unexplained | invoices (incl. 272 credits, group bills up to $158k) cannot be rebuilt |
| crew_id | DERIVABLE | `HOTAC.CREWID` (>0), deadhead via `ROSTER.ID` of the PAX leg | pseudonymise; filter pilots with `ROSTER.POS` / `CREWQUAL` | 100% of cat 0 lines carry a crew id or a vacancy placeholder | AIMS gives a crew for nearly every line; Pierre's 13.9% blanks come from invoice-level billing |
| pairing_id | DERIVABLE | `CRROUTE.DESC_` + `_` + date(`CDATE`) | join `CROUTE, CDATE` | 1,861 pairings with hotel lines in Jan 2026 | transport lines of category 4 with `FLTNO = 1` placeholder need the pairing from `CROUTE/CDATE` too |

### 3.5 Tested SQL sketch (January 2026)
```sql
-- live hotel / transport event lines per category (all crew), HOTAC indexes start with PROCESSSTATUS
SELECT CATEGORY, CASE WHEN CREWID>0 THEN 'crew' ELSE 'vacancy' END kind, COUNT(*) n,
       COUNT(DISTINCT SUPPLIERSTN) hotel_stns, COUNT(DISTINCT CONCAT(CDATE,'|',CROUTE)) pairings, COUNT(DISTINCT CREWID) crews
FROM TSC.dbo.HOTAC WHERE PROCESSSTATUS=0 AND CHECKINDAY BETWEEN 16802 AND 16832 GROUP BY CATEGORY, CASE WHEN CREWID>0 THEN 'crew' ELSE 'vacancy' END;
-- cat 0 crew: 9,333 lines / 42 stations / 1,861 pairings / 1,659 crew ; cat 4: 13,062 ; cat 1: 2,481
SELECT CASE WHEN cl.CARRIER=1 THEN 'own' ELSE 'partner/surface' END carr, COUNT(*) crewlegs,
       COUNT(DISTINCT CONCAT(cl.DAY,'|',cl.DEP,'|',cl.CARRIER,'|',cl.FLT)) flights
FROM TSC.dbo.CREWLEG cl WHERE cl.PAX=1 AND cl.REMOVED=0 AND cl.DAY BETWEEN 16802 AND 16832 GROUP BY CASE WHEN cl.CARRIER=1 THEN 'own' ELSE 'partner/surface' END;
-- own 398 crew-legs / 260 flights ; partner/surface 1,972 / 1,479
```

### 3.6 Verdict D10: **PARTIAL (events) / NOT POSSIBLE (invoice amounts)**
AIMS can list every deadhead leg, hotel night and transfer with crew, pairing, station and date from 2023-09 (hotels) / 2022 (deadheads), cleaner than Pierre's invoices. It cannot give what was paid: there is no amount, credit note or invoice date in TSC; the only price tables are dead (`HOTACPRICE0`) or a rate card without history (`CITYCOST`). Without the amounts D10 cannot calibrate costs, only drive an event-count x unit-cost estimate.
Missing, in order: (1) the invoice amounts (finance/procurement export or Snowflake source), including credits; (2) unit costs per hotel contract and per deadhead fare if an estimate is accepted (`CITYCOST` and the undecoded `HOTEL` floats to be explained by the AIMS admin); (3) meaning of `HOTAC` categories 2, 3, 5 and of byte 149 flag values; (4) rule to select PNT crew; (5) invoice-to-event matching rule.

---------------------------------------------------------------------------------------------------

## 4. D12 agreement rules

The mock D12 (`d12_agreement_rules.yaml`, every value `[CONFIRM: Labour Relations + Finance]`; real.yaml reuses it) has: ALPA pilots, term 2025-05-01..2030-04-30, drafting `order tier_then_senior_first` (CONFIRMED), `protected_blocks none` (CONFIRMED), `max_drafts_per_crew_month null` (CONFIRMED), `premium_pct 200` [CONFIRM], reserve `guarantee_per_day_cad {short_call 250, long_call 180}`, `notice_hours {short_call 2, long_call 12}`; CUPE cabin crew locals 4041 / 4047 / 4078.

### 4.1 Objects searched
| Object | Content | Finding |
|---|---|---|
| `SPEFREC1..6`, `SPEFRECDATA` | 199 custom scheduling rules per type (with/with-not, certain flights for certain crew, ...), `MSG` rule texts | scheduling-pattern rules by crew category/position; 5 of 199 `SPEFREC1` rows have a message, **0 contain** notice / draft / reserve / premium / guarantee keywords (same on `SPEFREC2`). No pay or reserve agreement content. |
| `RULESTBL` (31,607) / `LOG_RULESTBL` (3,236, changes 2024-06-05..2026-10-21, 153 rules touched) | AIMS legality-rule parameters: keys `ACT, AC, CKCB, PLAN_DAY, KIND (1-9, 11), RULENO (1..80, 200-220, 1000-6600, 7100-7870, 9120-9330), SUBRULENO`, parameters in a binary `RULEDATA` (3..3,500 bytes) | **Undecodable without the AIMS rule dictionary**; these are duty/rest/limit rules (FDP, rest), not pay. Could contain reserve call/notice parameters under `RULESETS` "CALL", unproven. |
| `RULESETS` | 4 rows: `2&3` Subpart 2 or 3, `CALL` Members on call, `TRD` Trip trades, `EASA` | confirms a "members on call" ruleset exists; no values |
| `ENTRULREC1/2/3/6` | days-off / vacation **entitlement** rules (12 + 99 + 99 + 1 rows); ENTRULREC1 all inactive, ENTRULREC2 4 active (e.g. 29 days, 4 days, period types 3-5), ENTRULREC3/6 none active | leave entitlement, not drafting/reserve/pay |
| `POSTINGRULES` | monthly posting calendar for CM / PO (2017-03-02..2026-09-30, FTC calendar) | period boundaries only |
| `ALLWTYPE`, `ALLWMTHD` | 8 allowance types (night premium 18:00-05:59, excess duty, time away PNT/PNC, training duty), 13 methods; `ADP_CODE` blank | structure only, no rates |
| `PARAM` / `PARAMW` | per-user form/program settings (`FIXED_USERNUMBER`, `FIXED_FORMNAME`, 16-byte data) | UI preferences, irrelevant |
| `EZYPAYROL` | **0 rows** | payroll-rule engine not used |
| `CRCODES` | activity-code dictionary with FTC credit minutes, effectivity days | **the reserve guarantee credit lives here** |
| `CREWCAT` | categories such as "BLOC REGULIER PNT (CC26)", "BLOC PVHR (CC26)", "SYNDICAT PNT", "SYNDICAT 95 HRS 18/10/24" | labels that tag the CC 2026 regime per crew; not rule values |
| `CrewSchedAI.dbo.R0_GetDraftList` + `draft_order10_crews` | 13-step PNT draft order implemented in code | evidence for `drafting.order` (code, not data) |

### 4.2 Field-by-field

| D12 field | status | AIMS evidence | note |
|---|---|---|---|
| `pilots.drafting.order` (tier_then_senior_first) | PARTIAL | the draft order is hard-coded in `R0_GetDraftList` (13 steps), not stored as data | cross-check CrewSim against R0 instead of a data table |
| `protected_blocks: none`, `max_drafts_per_crew_month: null` | MISSING (absence cannot be proven) | no object with a cap or protected block; `RULESTBL`/`SPEFREC` hold other rule families | confirmed by business only |
| `premium_pct 200` | PARTIAL | `TIMEPNCPNT` has `T_1_5` and `T_2` columns (1.5x and 2x credit hours); draft-marked legs sit in `T_1_5` in 07-2026 (448 of 502 rows) and `T_2` (3 of 4); the 1.5x -> 2x switch for DRAFT_THX/OVERTIME_THX on **2026-02-01** is visible only in Pierre's `rate_cad` (360 -> 480) | the AIMS column name does not move; the multiplier-by-date table is a payroll fact |
| `reserve.guarantee_per_day_cad` | **DERIVABLE in hours** | `CRCODES` FTC minutes (bytes 89-90), effective days (85-88): `AM` 240 min from 2026-01-06 (day 16807), `PM` 240, `PM1` 240 from 2026-01-06, `LCR` 180 min from **2026-03-01** (16861), `XAM`/`XPM` 200 min (3.33 h) from 2003 to 2026-01-06 (XAM) - XPM still open-ended, `AM0`/`PM0`/`REA1` 0 | hours: short call (AM/PM) 4.00, long call (LCR) 3.00, legacy 3.33. At 240 $/h: $960 / $720 / $799.20 (the 3.33 h x 240 = 799.20 in Pierre3.md). The mock 250 / 180 $ is wrong. v3 D7 pays 3.33 h until **2026-02-28** (12,842 rows) and 3.0/4.0 from 2026-03-01: the pay effective date (03-01) differs from the code creation date (01-06) |
| `reserve.notice_hours` {short 2, long 12} | **MISSING** | `CRCODES` report/debrief minutes are 0/0 for the reserve codes; `RULESETS CALL` exists but `RULESTBL` is undecodable | derive empirically from `ROSTER`/`LOG_ROSTER` (time between assignment and report) - not done here; business confirmation required |
| `cabin_crew.agreement`, locals 4041/4047/4078, term | MISSING | none | `CREWCAT` has "SYNDICAT PNT / 88 HRS / 95 HRS" labels only |

### 4.3 Verdict D12: **PARTIAL**
Only the reserve guarantee (as credited hours, by effective date) can be taken from AIMS; the premium multiplier is observable from `T_1_5`/`T_2` but its date table is not; notice hours, caps, protected blocks, order and cabin-crew terms are not stored as data in TSC. D12 stays a document owned by Labour Relations/Finance.
Missing, in order: (1) notice hours (short/long call) [Labour Relations]; (2) multiplier table with effective dates (1.5x until 2026-01-31, 2x from 2026-02-01; applies to DRAFT and OVERTIME) and the rate 240 $/h [Finance]; (3) pay effective date of the new reserve credits (2026-03-01 vs 2026-01-06) [Pierre/Finance]; (4) confirmation that AM/PM = short call and LCR = long call (inference from names "RESERVE AM/PM PNT" and "LONG CALL RESERVE"); (5) cabin-crew rules (phase 2).

---------------------------------------------------------------------------------------------------

## 5. Notes on every new AIMS object relied upon

| Object | What it is | Key / grain | Rows | Date range | How written (inference) |
|---|---|---|---|---|---|
| `TIMEPNCPNT` | timesheet PNC/PNT report snapshots with credited hours per pay code | ROSTER key + `RUNID, USER_ID, CLONE_ID, PUB_IND, DUTY_ORDER` | 355,053 | pay months 06-2026..09-2026 (runs 2026-07-22..2026-10-22) | a user job runs the timesheet report per crew twice per pay month (about +2 d and +22 d) and stores the rows; `CREW_NAME`/`CASIER_MAILBOX` present (not read) |
| `TSCPAYID` | per crew pay-category record per period (`IDX` = category, `BEGPER` day) with a 33-byte blob | `(ID, IDX, BEGPER)` | 95,543 | `BEGPER` 7060..18171 | written by crew administration; blob not read |
| `ALLWRDC` / `vvALLWRDC` | per crew per day alternate credits (see vvALLWRDC.md) | `(ID, DAY)` | 4.6M | 1980..2026-11 | period close |
| `ALLWTYPE`, `ALLWMTHD`, `POSTINGRULES`, `EZYPAYROL`, `CREWCOST`, `COSTELEM`, `CATRCOST`, `FLTCOST`, `FUELCOST`, `CITYCOST` | allowance/payroll/costing setup | small | 8 / 13 / 250 / 0 / 72 / 19 / 1 / 3,907 / 2 / 4,494 | | AIMS setup screens |
| `LEGDELAYS` | delay lines per leg (KIND 1 dep delay placeholder code 99, KIND 2 coded causes) | `(DAY,DEP,CARRIER,FLT,LEGCD,KIND,INDEX_)` | 768,457 | 2002..2026 | ops control delay entry; ops duplicates in `OPS*` columns |
| `DLYCD`, `DLYCAT`, `SUBDLY` | delay code dictionaries (255 / 30 / 39) | code id | | | setup |
| `LEGTRDELAYS` | propagated delay from a previous leg | leg + `FROM*` leg + code | 236,045 | to 2026-08 | derived/ops entry |
| `LOG_LEGMAIN` | audit log of LEGMAIN field changes | `TABLELOGID` | 1,332,286 | 2024-05-13..2026-10-27 | AIMS audit trigger |
| `TABLES.CNXREASONS`, `TABLES.MODREAS002`, `TABLES.OCNGRS*` | label lists (see 2.2) | record | 1 / 1 / 32 | | setup |
| `HOTAC` price items: `HOTACPRICE0` | ad-hoc extra price lines | `(CREWID, SUPPLIER, BOOKINGDATE, IDX)` | 714 | 2013..2026-05 | hotel desk entry |
| `DEADHEAD` | positioning timetable | `DEADHEAD_ID` | 203,982 | 2026-09-22 .. about 2027-12 | loaded timetable (future only) |
| `RULESTBL`, `RULESETS`, `ENTRULREC*`, `SPEFREC1..6` | rule engines | see 4.1 | | | AIMS setup |

