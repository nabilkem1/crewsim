# vvALLWRDC  (View)  - Crew daily allowance / alternate-credit record (per crew member per day); source of the "ALT_J" credits of the FTC calculation

## 1. Purpose & business meaning
`TSC.dbo.vvALLWRDC` is **not** a worldwide regulation/duty-limit table (the "WRD" is not "worldwide"): the code that reads it (`rpt.CalculateCrewFTC`, `dbo.R5_Get_Violation_FTC`) uses it as a
**per-crew, per-day record of allowance / alternate credit entries**. Evidence: it is filtered `WHERE t.Id = @Crew_ID AND t.DAY BETWEEN <period first day> AND <period last day>`; it holds 20 repeating
pairs (`CRED_ARR_n_CCODE_SEL`, `CRED_ARR_n_CREDIT_HRS`); each pair = "an activity code (a `CRCODES.ID`) that earns a credit" + "the credit **in minutes**"; the credits are summed (`Sum(CREDIT_HRS)/60.0`)
and added to the crew member's period Flight Time Credit (FTC) as a separate line `CREDIT_TYPE = 'ALT_J'` next to the normal `ACTIVITY_CREDIT` lines. In AIMS terms this is the crew-pay "allowance record"
(name = ALLoWance Record Day Crew, inference): flight-time credit awarded for absences or ground activities such as sick leave (`MAL`), `CPP4`, `VNR`, `REAF`, `CSS`, `REAT`, ... plus per-day premium flags and
an amount.

Grain: **one row per crew member (`ID`) per day (`DAY`)**; there is a row for essentially every active crew member every day (about 930-1,550 rows per day in 2026), but the **credit pairs are populated only on the first day
of each FTC period** (the day the allowances of that period are posted). Lifecycle: written by AIMS crew-pay/allowance processing (period close or manual entries by crew administration - `REMARKS` shows free-text such as coaching, reassignment...);
history back to 1980-01-01; rows exist up to 2026-11-30 (future days contain a single placeholder row per day). planner-assist only reads it.

## 2. Physical facts
- `TSC.dbo.vvALLWRDC`, view (no definition). Row count measured 2026-11-03: **4,608,770** rows, 4,762 distinct crew ids, `DAY` 0 (1980-01-01) .. 17135 (2026-11-30).
- `(ID, DAY)` is unique (1,550 rows = 1,550 distinct `ID` on 2026-08-01). It is a view over a large AIMS table: **always filter `ID` and a narrow `DAY` range**; an unfiltered `COUNT(DISTINCT ...)`/`SELECT *` over the whole view timed out (60 s).
- No indexes known for the view; the procedures filter `ID` and `DAY` only.
- Type lengths: `nchar` in characters.

## 3. Column dictionary

### 3.1 Key
| Column | Type | Null | Business meaning | Encoding / units | Evidence |
|---|---|---|---|---|---|
| ID | int | yes | Crew member id (internal AIMS crew id = `vvCREWDB.ID` = `ROSTERID.ID` = `ROSTER.ID`) | integer, personal pseudonymous key | `rpt.CalculateCrewFTC.sql:163`, `dbo.R5_Get_Violation_FTC.sql:712` |
| DAY | smallint | yes | AIMS day number of the record: **days since 1980-01-01** (day 0 = 1980-01-01; 17106 = 2026-11-01) | smallint; convert with `DATEADD(DAY, DAY, '1980-01-01')` | `rpt.CalculateCrewFTC.sql:136,164-165` (`CAST(DATEADD(DAY, t.DAY, '1980-01-01') AS DATE)`) |

### 3.2 Alternate credits - the part used by planner-assist (20 slots)
| Column | Type | Null | Business meaning | Encoding / units | Evidence |
|---|---|---|---|---|---|
| CRED_ARR_1_CCODE_SEL ... CRED_ARR_20_CCODE_SEL (20 columns: `CRED_ARR_1_CCODE_SEL`, `CRED_ARR_2_CCODE_SEL`, `CRED_ARR_3_CCODE_SEL`, `CRED_ARR_4_CCODE_SEL`, `CRED_ARR_5_CCODE_SEL`, `CRED_ARR_6_CCODE_SEL`, `CRED_ARR_7_CCODE_SEL`, `CRED_ARR_8_CCODE_SEL`, `CRED_ARR_9_CCODE_SEL`, `CRED_ARR_10_CCODE_SEL`, `CRED_ARR_11_CCODE_SEL`, `CRED_ARR_12_CCODE_SEL`, `CRED_ARR_13_CCODE_SEL`, `CRED_ARR_14_CCODE_SEL`, `CRED_ARR_15_CCODE_SEL`, `CRED_ARR_16_CCODE_SEL`, `CRED_ARR_17_CCODE_SEL`, `CRED_ARR_18_CCODE_SEL`, `CRED_ARR_19_CCODE_SEL`, `CRED_ARR_20_CCODE_SEL`) | smallint x20 | yes | **Selected activity code of credit entry n** = the `CRCODES.ID` of the schedule/activity code that generated the credit (stored as a negative number: `-17` = `MAL`, `-394` = `CPP4`, `-130` = `VNR`, `-33` = `REAF`, `-19` = `CSS`, `-208` = `REAT`, `-255` = `CSSM`, `-3` = `IOU`, `-117` = `INV`, `-23` = `DEUI`, `-88` = `NSHW`, `-171` = `N/DC`, `-360` = `CPP`, `-172` = `CONV`, `-395` = `CPNC`); 0 = slot unused | `CRCODES.ID` is negative for 448 of its 449 rows (join: `crc.ID = CCODE_SEL`; 3 of 2,652 credited slots had no match). **Note**: not selected by the FTC code beyond non-null filter; the code only uses `CREDIT_HRS > 0` | `rpt.CalculateCrewFTC.sql:141-166`; profiled |
| CRED_ARR_1_CREDIT_HRS ... CRED_ARR_20_CREDIT_HRS (20 columns: `CRED_ARR_1_CREDIT_HRS` ... `CRED_ARR_20_CREDIT_HRS`) | smallint x20 | yes | **Credit of entry n, in MINUTES** (despite the name "HRS"): the code divides the sum by 60 to get FTC hours. Values 4..4,790 (e.g. 130 = 2:10, 535 = 8:55, 3900 = 65:00). 0 = no credit | minutes; `Sum(CREDIT_HRS)/60.0` = hours added to FTC | `rpt.CalculateCrewFTC.sql:361`, `dbo.R5_Get_Violation_FTC.sql:762` |

Slot usage: slot 1 is by far the most used (5,820 credited rows in DAY 16800-17000 = 2025-12-30..2026-07-18), slot 2: 2,384, slot 3: 1,179; over DAY 16800-17106: slot 5: 494, slot 10: 28, slot 20: 0. The procedures unpivot all 20 slots with `CROSS APPLY (VALUES (1, CRED_ARR_1_CCODE_SEL, CRED_ARR_1_CREDIT_HRS), ... (20, ...))`.

### 3.3 Amount, premiums and flags (not used by planner-assist)
| Column | Type | Null | Business meaning | Encoding / units | Evidence |
|---|---|---|---|---|---|
| AMNT | float | yes | Amount of the day's allowance (monetary or quantity, unit unknown); `-99` is a sentinel (1,353 of 50,891 rows in 40 days); positive values such as 2.17, 5.20, 4.00, 8.92, 14.75 (2,735 rows) | float; -99 = not applicable (inference) | profiled |
| LEGFLAGPOS_1 ... LEGFLAGPOS_8 (`LEGFLAGPOS_1`, `LEGFLAGPOS_2`, `LEGFLAGPOS_3`, `LEGFLAGPOS_4`, `LEGFLAGPOS_5`, `LEGFLAGPOS_6`, `LEGFLAGPOS_7`, `LEGFLAGPOS_8`) | tinyint x8 | yes | Leg-flag position bytes: one flag per leg of the day (position of a flagged leg, 1st..8th) | non-zero in a few rows (`LEGFLAGPOS_1`: 443 non-zero rows in DAY 16000-16300 = 2023-10-23..2024-08-18; 14 in DAY 17000-17040) | profiled; semantics inferred |
| SECROWTIME | smallint | yes | Seconds-row time: "second row" time - minutes related to a second allowance row (270, 540, 810 = multiples of 4:30 most frequent) | minutes; 693 non-zero rows in 40 days | profiled; semantics unknown |
| P16_PREM | tinyint | yes | Premium flag "P16" (pay premium type 16) | 0/1; 86 rows in DAY 16000-16300 (2023-10-23..2024-08-18), 1 row in 2026-07-18..08-27 | profiled; naming inference |
| PF_PREM | tinyint | yes | Premium flag "PF" | 0/1; 513 rows in DAY 16000-16300, 0 in 2026-07-18..08-27 | profiled; naming inference |
| PR_PREM | tinyint | yes | Premium flag "PR" | 0/1; 30 rows in DAY 16000-16300, 1 row in 2026-07-18..08-27 | profiled; naming inference |
| OT_PREM | tinyint | yes | Overtime premium flag | 0/1; 0 in samples | profiled; naming inference |
| PREM_039 | tinyint | yes | Premium flag 039 (pay-code 039) | 0/1; 0 in samples | naming inference |
| RSGN_IDX | nchar(2) | yes | Resignation / reason index | blank in all sampled rows | profiled |
| FUT_01 | tinyint | yes | Reserved flag | 0 in all sampled rows | profiled |
| REMARKS | nchar(40) | yes | Free-text remark of the allowance entry (e.g. "OPEN", "SW", "DON", "reaf", "coaching dv", "FAID") - may contain personal remarks; not to be exposed | text; filled on ~1.2% of rows | profiled (fill rate and generic tokens only) |
| CONVERT_BYTE | tinyint | yes | Internal conversion flag | 0 in samples | naming inference |
| FICT_TRN_VAL | smallint | yes | Fictitious training value (hypothetical flight-time credit of a training activity) | 0 in samples | naming inference |
| RESERVED01 | varbinary(13) | yes | Reserved bytes | unused | naming inference |

## 4. Keys & relationships
- Natural key: (`ID`, `DAY`) - unique per row.
- `vvALLWRDC.ID` = `vvCREWDB.ID` = `ROSTERID.ID` = `ROSTER.ID` (N:1 to the crew master; every crew id is a pseudonymous number).
- `vvALLWRDC.CRED_ARR_n_CCODE_SEL` = `CRCODES.ID` (activity/schedule code table; ids are negative numbers such as -17). The FTC code does not join to CRCODES here; the join is only needed to display the activity code.
- Period membership: `DAY` is compared to the period day-range of the custom FTC calendar (January: 01-01..01-30, February: 01-31..03-01, March: 03-02..03-31, April-December calendar months) - see `rpt.CalculateCrewFTC.sql:67-96`, `dbo.R5_Get_Violation_FTC.sql:70-120`.
- Predicate used in both procedures: `WHERE t.Id = @Crew_ID AND t.DAY >= <period first day number> AND t.DAY <= <period last day number> AND (v.CCODE_SEL is not null AND IsNull(v.CREDIT_HRS,0) > 0)`.

## 5. Encoding conventions & gotchas
- **Credits are minutes although the column says HOURS**; the code divides by 60. Do not add them to hours without dividing.
- `CCODE_SEL` and `CREDIT_HRS` were never NULL in the sampled rows (0 = unused), so the code's `CCODE_SEL is not null` test is effectively always true, so what actually filters is `CREDIT_HRS > 0`. Rows with a non-zero code but 0 credit exist (146 in DAY 16800-17000), rows with a credit and code 0 do not (0 in the sampled days).
- **Credits are posted on the first day of each FTC period**, not on the day of the activity: 2026-01-01 (759 credited rows), 2026-01-31 (813: start of the "February" period), 2026-03-02 (904: start of "March"), 2026-04-01 (868), 2026-08-01 (890), 2026-09-01 (856), 2026-10-01 (847), 2026-11-01 (59). Other days have no credits. A query of a single day (e.g. a pairing day) will return nothing; the whole period range must be scanned (as R5 does: "allowances are stored on the first day of their own period, so only the main period counts (not the previous one)").
- The FTC calendar is **not the calendar month in Jan-Mar**: Jan = 1-30 Jan, Feb = 31 Jan-1 Mar, Mar = 2-31 Mar; Apr-Dec are calendar months.
- `DAY` is a smallint day number from 1980-01-01 (not a date); the view returns future rows (to 2026-11-30) that are empty placeholders.
- Rows exist for most crew every day, so the view is large: always filter on `ID` (and `DAY`).
- `REMARKS` and `ID` are personal data: never output them.
- It is a **credit** source only: nothing in this view stores the 90 h / 65 h / 95 h / 47.5 h limits; they are in `CrewSchedAI.dbo.FtcLegalLimit`.

## 6. How the planner-assist procedures use it
| Procedure | Columns | Filter | Why |
|---|---|---|---|
| `rpt.CalculateCrewFTC` (`:134-167, :358-365`) | `ID`, `DAY`, 20 x (`CCODE_SEL`, `CREDIT_HRS`) | `Id = @Crew_ID`, `DAY BETWEEN period first/last day`, `CREDIT_HRS > 0` | Alt_J CTE: unpivots the 20 slots and adds one `CREDIT_TYPE = 'ALT_J'` row whose `FTC = Sum(CREDIT_HRS)/60.0` to the period's `ACTIVITY_CREDIT` rows; `TOTAL_PERIOD_FTC = SUM(FTC)` is compared to the legal limit from `dbo.FtcLegalLimit` (category PNT/PNC x mini-bloc) |
| `dbo.R5_Get_Violation_FTC` (`:691-718, :757-775`) | same | `Id = @Crew_ID`, `DAY BETWEEN @MainDayFrom AND @MainDayTo`, `CREDIT_HRS > 0` | Part C "Materialize Alt_J Allowances" into `#Alt_J`; added to the activity FTC of the period including the drafted pairing; `Rule_Violation = 'Max FTC exceeded'` when `TOTAL_PERIOD_FTC > LEGAL_LIMIT` (R5) |
Regulation checked: maximum Flight Time Credit per period (pilots PNT 90 h, or 65 h for "mini-bloc" crew with blocked dates in the period; cabin crew PNC 95 h, or 47.5 h mini-bloc); the CAR/collective-agreement article is "to be confirmed" (`FtcLegalLimit.Reference` empty).

## 7. Typical query patterns
```sql
-- alternate credits (minutes and hours) of one crew member for one FTC period (here the November 2026 period: 2026-11-01..2026-11-30)
-- @crew is the numeric crew id; day numbers are days since 1980-01-01
DECLARE @crew INT = 0;  -- set the crew id
DECLARE @d1 INT = DATEDIFF(DAY,'1980-01-01','2026-11-01'), @d2 INT = DATEDIFF(DAY,'1980-01-01','2026-11-30');
SELECT t.ID, DATEADD(DAY, t.DAY, '1980-01-01') AS Posted_On, v.Slot, v.CCODE_SEL AS CRCODES_ID, c.CC AS Activity_Code,
       v.CREDIT_MIN, v.CREDIT_MIN / 60.0 AS Credit_Hours
FROM TSC.dbo.vvALLWRDC t
CROSS APPLY (VALUES (1, t.CRED_ARR_1_CCODE_SEL, t.CRED_ARR_1_CREDIT_HRS), (2, t.CRED_ARR_2_CCODE_SEL, t.CRED_ARR_2_CREDIT_HRS),
                    (3, t.CRED_ARR_3_CCODE_SEL, t.CRED_ARR_3_CREDIT_HRS), (4, t.CRED_ARR_4_CCODE_SEL, t.CRED_ARR_4_CREDIT_HRS),
                    (5, t.CRED_ARR_5_CCODE_SEL, t.CRED_ARR_5_CREDIT_HRS)) v (Slot, CCODE_SEL, CREDIT_MIN)
LEFT JOIN TSC.dbo.CRCODES c ON c.ID = v.CCODE_SEL
WHERE t.ID = @crew AND t.DAY BETWEEN @d1 AND @d2 AND ISNULL(v.CREDIT_MIN, 0) > 0;
-- (add slots 6..20 to the VALUES list for a complete result; R5 unpivots all 20)

-- how many crew members got alternate credit on each period-start day (aggregate only)
SELECT t.DAY, DATEADD(DAY, t.DAY, '1980-01-01') AS Posted_On, COUNT(*) AS Rows_That_Day,
       SUM(CASE WHEN t.CRED_ARR_1_CREDIT_HRS > 0 THEN 1 ELSE 0 END) AS With_Credit_In_Slot1
FROM TSC.dbo.vvALLWRDC t
WHERE t.DAY BETWEEN 17014 AND 17016
GROUP BY t.DAY;
```

## 8. Data profile (measured 2026-11-03)
- 4,608,770 rows; 4,762 distinct `ID`; `DAY` 0..17135 (1980-01-01 .. 2026-11-30); future days after 2026-11-04 have 1 placeholder row per day (27 rows with DAY > 17108).
- Rows per day in 2026: about 930-1,550 (e.g. 1,214 on 2026-07-18; 1,550 on 2026-08-01). Crew count per period-start day: credited rows 759 (01-01), 813 (01-31), 904 (03-02), 868 (04-01), 890 (08-01), 856 (09-01), 847 (10-01), 59 of 63 (11-01).
- Most frequent credited activity codes (slot 1, 2026-08-01..11-01): `MAL` (id -17) 1,410, `CPP4` (-394) 324, `VNR` (-130) 217, `REAF` (-33) 169, `CSS` (-19) 147, `REAT` (-208) 79, `CSSM` (-255) 52, `IOU` (-3) 40, `INV` (-117) 34, `DEUI` (-23) 32, `NSHW` (-88) 23, `N/DC` (-171) 22, `CPP` (-360) 18, `CONV` (-172) 17, `CPNC` (-395) 10. Credits (minutes) range from 4 to 4,790 (e.g. `MAL` 95-2,535; `CSS` 130-4,030).
- Of the 2,652 credited slot-1 entries 2026-08-01..11-01, 3 have a code that is not in `CRCODES`.
- `AMNT`: -99 in 1,353 rows, positive in 2,735 rows, 0 in 46,803 rows (2026-07-18..08-27).

## 9. Open questions / confidence
- High: structure (per crew per day, 20 credit slots), credit unit = minutes, join to the FTC period, role in FTC (`ALT_J`), codes are negative `CRCODES.ID`.
- Medium: business reading of the name ("allowance record"); the AIMS term for the credits ("alternate J" credit) is not documented in the code - `Alt_J` is only the code's label.
- Unknown / not used: `AMNT`, `SECROWTIME`, premium flags, `LEGFLAGPOS_*`, `RSGN_IDX`, `FICT_TRN_VAL`, `CONVERT_BYTE`, `RESERVED01`; whether credits are posted exclusively on the period start day for every activity type (observed for the sampled periods).
- Whether `CRED_ARR_n_CCODE_SEL` positive values (148 rows with +1 etc.) have a different meaning (e.g. a code list index rather than a CRCODES id) is unknown; they carry no credit.
