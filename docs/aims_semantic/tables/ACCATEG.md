# ACCATEG  (Table)  - Aircraft-registration -> aircraft category membership (with validity period)

## 1. Purpose & business meaning
Assigns individual **aircraft (tail registrations)** to planner-defined **aircraft categories** for a validity window. A category is a property of a tail, not of a fleet type: e.g. "ACT equipped aircraft", "aircraft with only one A.D.F.", "LD low-density aircraft / 332 seats".
Row grain: one (registration, category, active-from, active-to). A tail may carry several categories and a category may be re-assigned over time (several rows with different windows).
Maintained by AIMS administrators in the aircraft-category setup; read by the planner-assist procedures to answer rules of kind **SEL 18 "Flights with aircraft of categories"** (in R1 "Certain flights for certain crews" and R2 "Schedule with / with-not").
The category *names* are not in this table: category index `CATEGIDX` n is named by the `TABLES` record `AIRCATEGnn` (`TABLES.RECDESC = 'AIRCATEG' + RIGHT('0'+n,2)`), **not** by GENCAT.
The sibling `ACCATEG2` (empty) is the "additional category" variant that uses GENCAT type 18.

## 2. Physical facts
* `TSC.dbo.ACCATEG`, base table, **41 rows** (2026-11-03).
* PK/unique clustered index `ACCATEG_INDEX_0` on (ACREG, CATEGIDX, ACTIVEBEG, ACTIVEEND): access is "by registration" (seek on ACREG, then validity filter). No other index. No identity column, no audit columns.
* (The metadata extract `columns.json` reports `nchar` lengths in **bytes**; the real declared lengths in characters are half of that and are used below.)

## 3. Column dictionary
| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| ACREG | nchar(12) | N | Aircraft tail registration the category applies to. | Printable registration with hyphen, e.g. `C-FDAT`; observed length 6 (declared nchar(12), space padded: trim before comparing; `LEGMAIN.REG` joins on equality - 2,245 legs of DAY 17000-17100 matched). | rpt.Get_Detailed_Pairing.sql:250 (`acc.ACREG = REG`); profiled |
| CATEGIDX | smallint | N | Aircraft category number (1..32). Name = `TABLES` record `AIRCATEG<nn>`; also bit nn of `SPEFRECDATA.CTRCAT` when the rule's `SEL = 18`. | Observed 5, 7, 8 (see profile). | rpt.Get_Detailed_Pairing.sql:249-251 (`acc.CATEGIDX = acref.Index_`) |
| ACTIVEBEG | smallint | N | First day (AIMS day number) on which the registration belongs to the category. | Days since 1980-01-01 (`DATEDIFF(DAY,'1980-01-01',date)`). 0 = "since always". | rpt.Get_Detailed_Pairing.sql:250; R2 comment "ACTIVEBEG and ACTIVEEND are inclusive day numbers" |
| ACTIVEEND | smallint | N | Last day the membership holds. | Days since 1980-01-01; **32767 (= 2069-09-17) = open ended** (all 41 rows). Treat as inclusive. | same; profiled |

## 4. Keys & relationships
* Natural key = the whole PK (ACREG, CATEGIDX, ACTIVEBEG, ACTIVEEND).
* `ACCATEG.ACREG` -> `LEGMAIN.REG` (N:M by registration; the leg's aircraft). Used as `acc.ACREG = REG` inside the leg row context of rpt.Get_Detailed_Pairing.sql:250.
* `ACCATEG.CATEGIDX` -> `TABLES` record `AIRCATEG<nn>` (name) via `CAST(SUBSTRING(RECDESC,9,2) AS INT) = CATEGIDX` (rpt.Get_Detailed_Pairing.sql:65-71). **Not** GENCAT.
* Rule side: `SPEFRECDATA.CTRCAT` bit CATEGIDX (when SPEFREC2/3.SEL = 18) - compared by *name*, not by number.

## 5. Encoding conventions & gotchas
* Day numbers, not dates: `ACTIVEBEG/ACTIVEEND = DATEDIFF(DAY,'1980-01-01', date)`; `smallint` => the end of time is 32767 = 2069-09-17.
* **Off-by-one in the consumer**: rpt.Get_Detailed_Pairing tests `acc.ACTIVEBEG < (DAY + (STD/1440)) AND acc.ACTIVEEND > (DAY + (STA/1440))` with *integer* division. `STD/1440` is 0 for a same-day departure and `STA/1440` is 0 or 1; the comparisons are **strict**, so a registration that enters a category on the very day of the flight (ACTIVEBEG = DAY) is *not* matched, and one whose ACTIVEEND = DAY is not matched. Elsewhere (R2 crew categories) the window is documented as inclusive. With all rows today at 0..32767 the bug is latent.
* A registration may appear in 2 categories (41 rows, 39 distinct registrations).
* Case/spacing: `nchar(12)` padded; the proc compares `acc.ACREG = REG` directly (relies on both being padded identically).
* An index that has no name in `TABLES.AIRCATEGnn` (blank) is silently dropped by the inner join to `#AIRCAT_REF`.

## 6. How the planner-assist procedures use it
* `rpt.Get_Detailed_Pairing`: for each flight leg builds `Aircraft_Categories` = `'| '`-joined names of the categories of `LEGMAIN.REG` valid at the leg (`#AIRCAT_REF` names).
* `dbo.R1_Get_Violations_CertainFlightsCrew` / `dbo.R2_Get_Violations_Schedule_WithWithNot`: rule kind 18 matches when the leg's `Aircraft_Categories` text intersects the rule's `Aircraft_Category` JSON list (derived from `SPEFRECDATA.CTRCAT` bits + `TABLES AIRCATEGnn`). Used to say e.g. "crew type X may (not) fly aircraft that are in category Y".
* R3/R4/R5 do not use it.

## 7. Typical query patterns
```sql
-- 1. Aircraft category names and member tails valid on a date
DECLARE @n int = DATEDIFF(DAY,'1980-01-01','2026-11-03');
SELECT LTRIM(RTRIM(a.ACREG)) AS Registration, a.CATEGIDX,
       LTRIM(RTRIM(CONVERT(nchar(40), SUBSTRING(CONVERT(varbinary(max),t.FIELDS),1,80)))) AS CategoryName
FROM TSC.dbo.ACCATEG a
JOIN TSC.dbo.TABLES t ON t.RECDESC = 'AIRCATEG' + RIGHT('0'+CAST(a.CATEGIDX AS varchar(2)),2)
WHERE a.ACTIVEBEG <= @n AND a.ACTIVEEND >= @n
ORDER BY a.CATEGIDX, a.ACREG;

-- 2. Categories of the tails flown by legs of a narrow LEGMAIN.DAY window
SELECT DISTINCT LTRIM(RTRIM(l.REG)) AS Reg, a.CATEGIDX
FROM TSC.dbo.LEGMAIN l JOIN TSC.dbo.ACCATEG a ON a.ACREG = l.REG
WHERE l.DAY BETWEEN 17100 AND 17110;
```

## 8. Data profile (measured 2026-11-03)
41 rows / 39 distinct registrations / all `ACTIVEBEG = 0`, all `ACTIVEEND = 32767`. Rows per CATEGIDX: 5 -> 3 tails ("ACFT WITH ONLY ONE A.D.F"), 7 -> 28 tails ("ACT equiped aircraft"), 8 -> 10 tails ("LD Low Density aircraft / 332 seats"). Registration length always 6.
The A.D.F. category (5) is probably the aircraft-side counterpart of airport category 7 "2x A.D.F REQUIREMENT" (`PORTCATEG`/GENCAT type 3) - inference from the names, not stated in any procedure.

## 9. Open questions / confidence
* High confidence on structure and joins (code + data). Medium on the exact business rule text because the rules that currently use SEL 18 are not in the live `SPEFREC2/3` data (all active rules use SEL 3 or SEL 4): the aircraft-category path is implemented but dormant.
* Whether ACTIVEEND is inclusive in AIMS itself is inferred from the R2 comment, not from AIMS documentation.
