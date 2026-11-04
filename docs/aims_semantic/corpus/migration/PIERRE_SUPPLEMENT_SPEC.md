# CrewSim - complementary data request to Air Transat (supplement files)

Version 1.1 - 2026-11-03. Open questions about your v3 files are in `PIERRE_QUESTIONS.md`. Audience: Pierre and the Finance / Payroll / HR / Crew Planning contacts he designates.

## 1. Why this request

CrewSim is moving from CSV extracts to **reading the AIMS database (TSC) directly** for everything AIMS knows: crew qualifications and bases, rosters (current, published and as-of), pairings and legs, absences, reserve call-outs, drafts (`ROSTERDT`), flight movements, delays, hotel and deadhead events, training activities and credited hours. That removes the need for the 11 big extracts (D1-D8, D10, D11).

AIMS **does not contain** what is below: money (pay, rates, invoices), the collective-agreement parameters, HR facts, some business classifications and a few operational facts (cancellation cause...). These are the only files we still need from Air Transat. **We accept the history that exists**: there is no need for 36 months; the reliable AIMS window starts 2024-05-14 and anything from that date to the latest closed period is enough. A shorter history for a file is acceptable.

**Scope:** CrewSim simulates **pilots only** for now, so every file below is requested for pilots, except `h01_crew_key_map` which must cover **all** crew (pilots and cabin) so the key never needs to be re-issued. All schemas carry `crew_group`; cabin rows can follow later at no schema cost.

## 2. What we do NOT need any more
D1, D2, D3, D3 legs, D4, D5, D6, D8, D9, D11 extracts (read from AIMS). The v3 files stay as the reference to validate our AIMS extraction.

## 3. Delivery conventions (all files)
* UTF-8 CSV, comma separator, header row exactly as in `templates\<file>.csv`, one file per schema, no extra columns (extra columns are refused by the loader).
* Dates `YYYY-MM-DD`; datetimes `YYYY-MM-DDTHH:MM` (minute precision, no seconds, no offset) in **UTC unless the column says otherwise**. State the time zone if it is not UTC.
* Numbers with a decimal point, no thousands separator; amounts in CAD unless `currency` says otherwise; empty cell = unknown/not applicable (never `NULL`, `N/A`, `0` as filler).
* **Identifiers:** `crew_id` = the same `P######` pseudonym as in v3 (see H01); `pairing_id` = `<AIMS pairing code>_<yyyymmdd of the pairing start day>` as in D3 (e.g. `C0290_20260714`); flights = `flight_no` (carrier code + number, e.g. `TS238`) + `flight_date` (same meaning as D8 `date`) + `origin`.
* **Law 25:** no names, birth dates, addresses, phone, e-mail, SIN/employee numbers, passenger names, bank data or free text that can identify a person. `crew_id` only. H01 (the key table) goes through the approved secure channel and is never committed.
* Corrections: send the complete file again with a new date in the filename (`f02_pay_register_20261201.csv`); stable ids (`pay_line_id`, `invoice_line_id`) let us deduplicate.
* Tell us the extraction date, the system of origin and the period covered in a short cover note per delivery.

## 4. Priority and owners

| Priority | Files | Why it matters |
|---|---|---|
| **P1 - blocks realistic costs and the V6 backtest** | F01 pay code dictionary, F02 pay register, F03 pay rates, F04 agreement rules, F05 positioning invoices, F06 cost coefficients, H01 crew key map, H02 employment | Without them the simulator prices drafts and reserves with placeholders and cannot be compared to real pay |
| **P2 - improves accuracy and scope** | F07 pairing credit, F08 disruption costs, F09 pay profile, H03/H04 sub-fleet, M01 activity code map (we pre-fill), M02 user -> group map, M07 training rules | Better cost per draft, neoLR scope, correct block/absence classification, correct `initiator` |
| **P3 - nice to have** | M03 cancellation cause, M04 older journal archive, M05 call-out outcomes, M06 draft trigger, M08 duty conventions | Calibration refinements; only if the data exists |

Minimal viable delivery (to start): **F01, F02, F03, F04, F06, H01, H02** (F05 right after).

## 5. Reconciliation CrewSim will run when files arrive (so you know what is checked)
* F02: hours per crew x pay period vs AIMS credited hours (`TIMEPNCPNT`) within 1 %; every `crew_id` exists in H01/H02; every `linked_pairing_id` exists in AIMS pairings; draft lines vs AIMS draft markers (`ROSTERDT` type 21).
* F05: `crew_id`/`pairing_id` resolved against AIMS bookings; share of lines without a crew or pairing reported (v3: 13.9 % / 35 %).
* F04/F06/F03: every key CrewSim needs is present for the whole window, otherwise the report states which values are still placeholders.
* H02: crew with AIMS qualifications but no employment row, and the reverse, are listed.

## 6. Per-file schemas (one `templates\<file>.csv` and one synthetic `examples\<file>.example.csv` per section)

Examples are **synthetic** (ids like `P000001`, `EXAMPLE` references): they show the format only. `prefilled\m01_activity_code_map.prefilled.csv` is the list of the 450 AIMS activity codes with description and usage that Crew Planning only has to classify.
### F01 - `f01_pay_code_dictionary.csv` - Pay code dictionary

* **Priority:** P1   **Suggested owner:** Payroll / Finance
* **Feeds CrewSim:** Replaces the 14 pay codes whose meaning is `[CONFIRM: Pierre]` in `configs/real.yaml` (`data.pay_codes`): lets CrewSim classify each paid line as draft premium, reserve guarantee, flying, overtime, holiday, adjustment, duty premium...
* **Grain:** one row per (pay_code, crew_group, effective period)   **Key:** `pay_code + crew_group + effective_from`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `pay_code` | str | Y | Code exactly as it appears in `f02_pay_register.pay_code` (e.g. DRAFT_THX, RESERVE_CREDIT, CHV, T_1_4, MIN, AJU, BME, DMG, OVERTIME_THX, HOLIDAY_T2, DUTY_PREMIUM_P10, RED_CAP) | `DRAFT_THX` |
| `description_fr` | str | Y | Official description (French) | `Prime de draft - temps et demi` |
| `description_en` | str | N | English description | `Draft premium - time and a half` |
| `crew_group` | str | Y | PILOT or CABIN (one row per group if the code applies to both) | `PILOT` |
| `category` | str | Y | One of: FLYING, DRAFT, RESERVE_GUARANTEE, RESERVE_UTILISATION, OVERTIME, HOLIDAY, DUTY_PREMIUM, ADJUSTMENT, DAMAGE, MINIMUM_GUARANTEE, TRAINING, OTHER | `DRAFT` |
| `unit` | str | Y | HOURS (the register carries hours x rate) or AMOUNT (flat dollars) | `HOURS` |
| `pay_multiplier` | float | N | Multiple of the base hourly rate (1.0 = straight time, 1.5, 2.0). Empty if not a multiple | `1.5` |
| `is_premium_on_top` | bool | Y | 1 if the amount is ONLY the extra above straight time (premium_cad semantics), 0 if it is the whole payment | `0` |
| `is_draft_related` | bool | Y | 1 if this code is paid because a crew member was drafted (assigned at short notice outside reserve) | `1` |
| `is_reserve_related` | bool | Y | 1 if paid because the crew member was on reserve (guarantee or call-out) | `0` |
| `agreement_clause` | str | N | Collective agreement article that creates this payment | `ALPA CC 2026 art. 14.x` |
| `effective_from` | date | Y | First day the meaning/multiplier is valid | `2024-05-01` |
| `effective_to` | date | N | Last day valid (empty = still valid) |  |
| `comment` | str | N | Anything we should know (e.g. negative amounts = corrections) |  |

* Ask: one line for each of the ~15 codes seen in the v3 D7 (CHV, T_1_4, MIN, AJU, BME, DMG, OVERTIME_THX, HOLIDAY_T2, DUTY_PREMIUM_P10/P16/P30, RED_CAP, DRAFT_THX, DRAFT_T2, RESERVE_CREDIT).
* Resolves Pierre3.md point 5 and the 'what is SHORT_NOTICE_COVER vs DRAFT payment' question for the pay side.

### F02 - `f02_pay_register.csv` - Pay register (actual paid lines)

* **Priority:** P1   **Suggested owner:** Payroll
* **Feeds CrewSim:** Replaces D7. Source of truth for the V6 backtest (simulated cost vs real pay), for the real cost of a draft and of a reserve day, and for validating AIMS credited hours (`TIMEPNCPNT`).
* **Grain:** one row per pay line (crew x pay code x duty date x pairing/flight if known x posting)   **Key:** `pay_line_id`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `pay_line_id` | str | Y | Unique, stable id of the line in the payroll system (so re-deliveries can be deduplicated) | `PL-2026-07-000123` |
| `crew_id` | str | Y | Pseudonymised crew id, SAME key as `h01_crew_key_map` (P######) | `P000123` |
| `pay_period_id` | str | Y | Pay period / bid period identifier as used by payroll | `2026-07` |
| `pay_period_start` | date | Y | First day of the pay period (periods are not always calendar months: e.g. 31 Jan - 1 Mar) | `2026-07-01` |
| `pay_period_end` | date | Y | Last day of the pay period | `2026-07-31` |
| `pay_code` | str | Y | Code, defined in `f01_pay_code_dictionary` | `DRAFT_THX` |
| `duty_date` | date | Y | Day the payment relates to (state in the notes which date convention: duty start vs flight date) | `2026-07-14` |
| `linked_pairing_id` | str | N | `<pairing code>_<yyyymmdd>` of the pairing (same as D3 `pairing_id`). Fill for EVERY line that belongs to a pairing, not only drafts | `C0290_20260714` |
| `linked_flight_no` | str | N | Flight number if the line is per flight (TS238) |  |
| `linked_flight_date` | date | N | Operating date of that flight |  |
| `hours` | float | N | Hours paid or credited (negative for corrections). Empty for AMOUNT codes | `8.5` |
| `rate_cad` | float | N | Hourly rate applied in CAD (before multiplier if `pay_multiplier` is given) | `240.00` |
| `pay_multiplier` | float | N | Multiplier actually applied (1.0, 1.5, 2.0) | `1.5` |
| `amount_cad` | float | Y | Gross amount of the line in CAD (negative for corrections/reversals) | `3060.00` |
| `premium_cad` | float | N | Part of `amount_cad` that is the premium above straight time (empty if not applicable) | `1020.00` |
| `posting_status` | str | Y | FINAL, ADJUSTED or REVERSED | `FINAL` |
| `adjustment_of_pay_line_id` | str | N | `pay_line_id` that this line corrects, if any |  |
| `posted_ts` | datetime | N | When the line was posted in payroll (minute precision) | `2026-08-05T14:30` |

* Pilots first (cabin crew phase 2 - same schema, `crew_group` known through h02).
* Period: whatever payroll holds from 2024-05-01 to the latest closed period; shorter history is acceptable.
* Reconciliation done by CrewSim: sum(hours) per crew x period for flying/reserve/draft codes must match AIMS `TIMEPNCPNT` within 1 % (v3 matched within 0.2 %).
* Do NOT include names, SIN, bank or any employee number; `crew_id` only.

### F03 - `f03_pay_rates.csv` - Hourly pay rates and multipliers (effective-dated)

* **Priority:** P1   **Suggested owner:** Payroll / Compensation
* **Feeds CrewSim:** Converts hours into dollars for every cost the simulator prices (draft, reserve guarantee, utilisation, overtime); replaces the flat 240 $/h assumption; records the 1.5x -> 2x draft premium switch.
* **Grain:** one row per (agreement, crew_group, position, fleet_family, pay_step, rate_type, effective period)   **Key:** `agreement + crew_group + position + fleet_family + pay_step + rate_type + effective_from`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `agreement` | str | Y | ALPA (pilots) or CUPE (cabin crew) | `ALPA` |
| `crew_group` | str | Y | PILOT or CABIN | `PILOT` |
| `position` | str | Y | CA, FO, ... or ALL | `FO` |
| `fleet_family` | str | Y | A321, A330, A320... or ALL | `A321` |
| `pay_step` | str | Y | Seniority/years-of-service step of the pay scale (1, 2, ... or ALL if a single rate) | `7` |
| `rate_type` | str | Y | BASE_HOURLY, DRAFT_PREMIUM_MULTIPLIER, OVERTIME_MULTIPLIER, HOLIDAY_MULTIPLIER, RESERVE_GUARANTEE_HOURS_SHORT_CALL, RESERVE_GUARANTEE_HOURS_LONG_CALL, PER_DIEM_DOMESTIC, PER_DIEM_INTERNATIONAL, OTHER | `BASE_HOURLY` |
| `value` | float | Y | Rate in CAD/hour, a multiplier, or hours, according to `rate_type` | `240.00` |
| `unit` | str | Y | CAD_PER_HOUR, MULTIPLIER, HOURS, CAD_PER_DAY | `CAD_PER_HOUR` |
| `effective_from` | date | Y | First day valid | `2025-05-01` |
| `effective_to` | date | N | Last day valid (empty = current) |  |
| `source_reference` | str | N | Article / letter of agreement / pay scale table | `ALPA CC 2025-2030 sch. A` |

* The v3 notes say 240 $/h straight time and draft paid at time-and-a-half until 2026-01-31, double time from 2026-02-01 (AIMS side: CRCODES guarantee 4.00 h AM/PM from 2026-01-06, 3.00 h LCR from 2026-03-01, legacy 3.33 h). Please confirm or correct with dates.
* If a pay scale by seniority step exists, provide it fully; CrewSim can then price a draft per crew (see f09).

### F04 - `f04_agreement_rules.csv` - Collective agreement rules relevant to drafting and reserve (D12, tabular)

* **Priority:** P1   **Suggested owner:** Labour Relations / Finance
* **Feeds CrewSim:** Replaces the mock `d12_agreement_rules.yaml` (every value marked `[CONFIRM]`): premium percentage, reserve notice hours and guarantee, drafting order, caps, protected blocks, agreement term, cabin crew rules. Drives the legality and cost rules of the simulator.
* **Grain:** one row per rule parameter and effective period   **Key:** `agreement + crew_group + rule_key + effective_from`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `agreement` | str | Y | ALPA or CUPE | `ALPA` |
| `crew_group` | str | Y | PILOT or CABIN | `PILOT` |
| `rule_key` | str | Y | Dotted key, e.g. drafting.order, drafting.premium_multiplier, drafting.max_per_crew_month, drafting.protected_blocks, drafting.min_notice_hours, reserve.short_call.notice_hours, reserve.long_call.notice_hours, reserve.short_call.guarantee_hours, reserve.long_call.guarantee_hours, reserve.max_consecutive_days, agreement.term_start, agreement.term_end | `reserve.short_call.notice_hours` |
| `value` | str | Y | Value as text (number, date, code or short phrase) | `2` |
| `unit` | str | N | HOURS, DAYS, CAD, PERCENT, MULTIPLIER, TEXT, DATE, COUNT | `HOURS` |
| `effective_from` | date | Y | First day valid | `2025-05-01` |
| `effective_to` | date | N | Last day valid |  |
| `clause_reference` | str | Y | Article / paragraph / letter of understanding that states it | `ALPA CC art. EXAMPLE` |
| `confidence` | str | Y | CONFIRMED (read from the agreement) or INTERPRETED (operational practice) | `CONFIRMED` |
| `confirmed_by` | str | N | Role or department (not a person's name) that confirms it | `Labour Relations` |
| `comment` | str | N | Exceptions, grandfathering |  |

* Facts already marked CONFIRMED in the mock file (2026-08-05): no protected blocks, no cap on drafts per crew and month, drafting order tier_then_senior_first - please re-state them here with the clause.
* Open values: premium_pct, short/long-call notice hours (v3 D5 shows medians of ~10 h short and ~46 h long - to be checked), guarantee hours, agreement term.

### F05 - `f05_positioning_invoices.csv` - Positioning and crew-travel cost lines (D10 replacement)

* **Priority:** P1   **Suggested owner:** Finance / Accounts payable
* **Feeds CrewSim:** Replaces D10. Calibrates the cost of deadhead, hotel and ground transport when a pairing is covered away from base, and validates the positioning ledger of the simulator. AIMS (`HOTAC`, `CREWLEG.PAX`) provides the EVENTS; this file provides the DOLLARS.
* **Grain:** one row per invoice line   **Key:** `invoice_line_id`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `invoice_line_id` | str | Y | Unique stable id of the invoice line | `INV-123456-1` |
| `invoice_id` | str | Y | Invoice / credit-note number (no supplier bank data) | `INV-123456` |
| `invoice_date` | date | Y | Invoice date | `2026-07-20` |
| `service_date` | date | Y | Date the service was consumed (check-in date, travel date) | `2026-07-14` |
| `cost_type` | str | Y | HOTEL, DEADHEAD, TRANSPORT, MEAL, OTHER | `HOTEL` |
| `station` | str | Y | IATA airport code where the cost was incurred (airport codes only) | `CDG` |
| `supplier_code` | str | N | Supplier code AS IN AIMS if available (HOTAC.SUPPLIER / hotel code) so lines can be linked to bookings | `H123` |
| `quantity` | float | N | Nights, seats, trips | `1` |
| `unit_price_cad` | float | N | Unit price in CAD | `210.00` |
| `amount_cad` | float | Y | Line amount in CAD (negative for credit notes) | `210.00` |
| `original_amount` | float | N | Amount in invoice currency if not CAD |  |
| `currency` | str | N | ISO currency of the original amount | `EUR` |
| `is_credit_note` | bool | Y | 1 if the line reverses a previous charge | `0` |
| `is_group_bill` | bool | N | 1 if one invoice covers several crew/rooms (then crew_id/pairing_id may be empty) | `0` |
| `crew_id` | str | N | Pseudonymised crew id (same key as h01). Empty if the line is not attributable to a person | `P000123` |
| `pairing_id` | str | N | `<pairing code>_<yyyymmdd>` the cost belongs to | `C0290_20260714` |
| `aims_booking_ref` | str | N | Booking reference in AIMS hotel/transport module if known (HOTAC AUTOINC) |  |

* Names of passengers/crew MUST NOT appear (a real D10 extract once contained passenger names; the loader refuses such columns).
* v3 D10 starts at 2025-06-28; anything earlier that finance still holds is welcome but not required.
* Please also tell us how invoices are matched to bookings today (key) so we can link them to AIMS `HOTAC`.

### F06 - `f06_cost_coefficients.csv` - Planning cost coefficients (replaces the placeholders)

* **Priority:** P1   **Suggested owner:** Finance + Crew Planning
* **Feeds CrewSim:** Replaces EVERY value in `configs/costs_pilots.yaml` / `costs_cabin.yaml` (all marked `[CONFIRM: Finance]`): reserve guarantee per day, reserve utilisation delta, draft base premium and tier premiums, training reschedule cost, deadhead/hotel/transport planning rates, cancellation cost, delay cost per minute, terminal penalty, APPR compensation bands.
* **Grain:** one row per coefficient and effective period   **Key:** `crew_group + coefficient_key + effective_from`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `crew_group` | str | Y | PILOT or CABIN | `PILOT` |
| `coefficient_key` | str | Y | One of: reserve.guarantee_per_day.short_call, reserve.guarantee_per_day.long_call, reserve.utilisation, draft.base_premium, draft.tier.1_day_off, draft.tier.2_conflicting_pairing, draft.tier.3_ground_training, draft.tier.4_vacation, draft.tier.5_simulator, draft.train_reschedule, positioning.deadhead, positioning.hotel, positioning.transport, disruption.cancellation, disruption.delay_per_minute, disruption.terminal_penalty_multiple, appr.hours_3_to_6, appr.hours_6_to_9, appr.hours_9_plus | `draft.base_premium` |
| `value_cad` | float | Y | Value in CAD (or multiple for terminal_penalty_multiple) | `500` |
| `basis` | str | Y | PLANNING_RATE (finance standard), ACTUAL_MEAN (average of real invoices/payments), CONTRACTUAL (agreement), LEGAL (regulation) | `PLANNING_RATE` |
| `effective_from` | date | Y | First day valid | `2025-05-01` |
| `effective_to` | date | N | Last day valid |  |
| `owner` | str | Y | Department that owns the figure (not a person) | `Finance` |
| `source_reference` | str | N | Document/system the value comes from |  |
| `comment` | str | N | Assumptions |  |

* AIMS already gives the reserve guarantee in HOURS (AM/PM 4.00 h from 2026-01-06, LCR 3.00 h from 2026-03-01, legacy 3.33 h = 799.20 $ at 240 $/h); finance confirms the dollar treatment.
* If a coefficient does not exist in the company, say NOT_USED rather than leaving it empty (put it in `comment`).

### H01 - `h01_crew_key_map.csv` - Crew pseudonym key (AIMS id -> crew_id)  -  SENSITIVE, secure channel only

* **Priority:** P1   **Suggested owner:** HR systems / Pierre (key holder)
* **Feeds CrewSim:** Lets CrewSim join live AIMS rows to every file Pierre sends (the v3 `P######` ids) without ever storing real ids in the repository. Alternative if this cannot be shared: Pierre tells us the keyed algorithm (e.g. HMAC-SHA256 with a secret) so the same pseudonyms are regenerated inside the extraction layer.
* **Grain:** one row per crew member   **Key:** `aims_crew_id`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `aims_crew_id` | int | Y | AIMS crew id (`ROSTER.ID` / `CREWDB.ID`) | `123456` |
| `crew_id` | str | Y | The pseudonym used in the v3 files and in every future file (P######) | `P000123` |

* This is the ONLY file that links real ids to pseudonyms. Deliver through the company's approved secure transfer; it is loaded by us into the table `CrewSchedAI.sim.crew_key_map` (access limited to the extraction role), never stored in the CrewSim repository, and raw ids never reach CrewSim.
* Include every crew member (pilots and cabin crew) so future files need no new key.

### H02 - `h02_crew_employment.csv` - Employment status, hire/termination dates, seniority (effective-dated)

* **Priority:** P1   **Suggested owner:** HR
* **Feeds CrewSim:** Fills D1 columns that AIMS cannot provide: `hire_date`, `termination_date`, `employment_status`, absolute `seniority_number` (AIMS only offers current order among active crew and proxies from qualification validity).
* **Grain:** one row per crew member and status period   **Key:** `crew_id + status_from`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `crew_id` | str | Y | Pseudonymised crew id (h01) | `P000123` |
| `crew_group` | str | Y | PILOT or CABIN | `PILOT` |
| `employment_status` | str | Y | ACTIVE, INACTIVE, TERMINATED, LONG_TERM_ABSENCE, MANAGEMENT_OR_INSTRUCTOR, INITIAL_TRAINING, FLEET_TRANSITION (add others if they exist, with a definition) | `ACTIVE` |
| `status_from` | date | Y | First day of this status | `2019-03-04` |
| `status_to` | date | N | Last day (empty = current) |  |
| `hire_date` | date | Y | Date of hire | `2012-05-14` |
| `termination_date` | date | N | Date of termination (empty if active) |  |
| `seniority_number` | int | N | Company seniority rank valid from `status_from` (1 = most senior); state in the notes which list (company-wide / by base) | `321` |
| `seniority_date` | date | N | Seniority date used to rank crew | `2012-05-14` |
| `union_local` | str | N | Union local (cabin crew: 4041, 4047, 4078...) |  |
| `pay_step` | str | N | Step in the pay scale (same coding as f03) | `7` |

* Seniority drives the drafting order (D12 `tier_then_senior_first`), so its history matters more than the other columns.
* No names, birth dates or addresses.

### F07 - `f07_pairing_credit.csv` - Pay credit per pairing

* **Priority:** P2   **Suggested owner:** Crew Planning / Payroll
* **Feeds CrewSim:** D3 `credit_hours` in v3 is the sum of scheduled block hours, not a pay credit. This gives the real credited hours of each pairing (greater-of rules, minimum guarantees) so the cost of a draft can be computed bottom-up.
* **Grain:** one row per pairing instance (and crew_group)   **Key:** `pairing_id + crew_group`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `pairing_id` | str | Y | `<pairing code>_<yyyymmdd>` as in D3 | `C0290_20260714` |
| `crew_group` | str | Y | PILOT or CABIN | `PILOT` |
| `credit_hours` | float | Y | Paid credit hours of the pairing | `17.25` |
| `block_hours` | float | N | Block hours of the pairing | `15.10` |
| `duty_hours` | float | N | Duty hours | `21.00` |
| `tafb_hours` | float | N | Time away from base | `58.5` |
| `credit_basis` | str | N | BLOCK, DUTY_RATIO, TAFB_RATIO, MINIMUM_DAILY, OTHER (the rule that produced the credit) | `DUTY_RATIO` |
| `computed_at` | datetime | N | When the credit was computed (it can change) |  |

* If the credit is only available per pay line, aggregate to pairing in f02 instead and skip this file.

### F08 - `f08_disruption_costs.csv` - Cost of flight cancellations and delays (realised)

* **Priority:** P2   **Suggested owner:** Finance / OCC
* **Feeds CrewSim:** Calibrates `disruption.cancellation` (25,000 placeholder), `delay_per_minute` (55) and the APPR band assumption; allows the simulator to price a cancelled flight from observed company costs.
* **Grain:** one row per flight event with a cost (or monthly aggregate if row level is impossible)   **Key:** `flight_no + flight_date + origin + event_type + cost_component`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `flight_no` | str | Y | Flight number (TS238) | `TS238` |
| `flight_date` | date | Y | Operating date (same definition as D8 `date`) | `2026-07-14` |
| `origin` | str | Y | Departure airport IATA | `YUL` |
| `destination` | str | N | Arrival airport IATA | `CDG` |
| `event_type` | str | Y | CANCELLATION or DELAY | `CANCELLATION` |
| `delay_minutes` | int | N | Delay in minutes for DELAY events |  |
| `cost_component` | str | Y | PASSENGER_COMPENSATION_APPR, PASSENGER_CARE, REBOOKING, AIRCRAFT, CREW, OTHER | `PASSENGER_COMPENSATION_APPR` |
| `amount_cad` | float | Y | Cost in CAD | `21000.00` |
| `passengers_affected` | int | N | Number of passengers | `250` |
| `aggregation_level` | str | Y | FLIGHT (row level) or MONTH_FLEET (aggregate; then flight_no empty and flight_date = first day of month) | `FLIGHT` |

* Aggregates are acceptable if row-level costs are not available.

### F09 - `f09_crew_pay_profile.csv` - Crew pay profile (optional)

* **Priority:** P2   **Suggested owner:** Payroll
* **Feeds CrewSim:** Prices a draft per crew member by seniority/pay step instead of a flat rate (cost of drafting a senior pilot vs a junior one).
* **Grain:** one row per crew member and period   **Key:** `crew_id + effective_from`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `crew_id` | str | Y | Pseudonymised crew id | `P000123` |
| `pay_step` | str | Y | Step in the pay scale (same coding as f03) | `7` |
| `base_hourly_rate_cad` | float | Y | Resulting base hourly rate in CAD | `240.00` |
| `effective_from` | date | Y | First day valid | `2025-05-01` |
| `effective_to` | date | N | Last day valid |  |

* Skip if f02 carries `rate_cad` per line: the rate can be derived from there.

### H03 - `h03_aircraft_subfleet.csv` - Aircraft registration -> sub-fleet

* **Priority:** P2   **Suggested owner:** Fleet / Flight Ops
* **Feeds CrewSim:** Defines the simulation scope `A321neoLR`. In AIMS the type 32Q = A321neo exists but `LR` is not distinguished and no pilot holds a neoLR qualification; the registration identifies it.
* **Grain:** one row per aircraft registration and period   **Key:** `registration + in_service_from`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `registration` | str | Y | Aircraft registration as in AIMS (`AIRCRAFT.REG` / `LEGMAIN.REG`) | `C-XXXX` |
| `aims_ac_type` | str | Y | AIMS aircraft type code (IATA code in `AIRCTYPE`: 321, 32Q, 320, 332, 333...) | `32Q` |
| `subfleet` | str | Y | A320ceo, A321ceo, A321neo, A321neoLR, A330-200, A330-300, ... | `A321neoLR` |
| `in_service_from` | date | Y | Start of this sub-fleet assignment | `2023-06-01` |
| `in_service_to` | date | N | End (empty = current) |  |
| `long_range_tank` | bool | N | 1 for LR configuration | `1` |

* AIMS lists 22 aircraft of type 32Q and 25 of type 321; a one-page list is enough.

### H04 - `h04_crew_subfleet_qualification.csv` - Crew qualification history by sub-fleet (neoLR)

* **Priority:** P2   **Suggested owner:** Training / Crew Planning
* **Feeds CrewSim:** Pierre's own question 8 (qualification history per sub-fleet): AIMS shows every A321 pilot holding the 321 and 32Q ratings with identical dates, so who is actually qualified on the neoLR is not visible.
* **Grain:** one row per crew member, sub-fleet and qualification period   **Key:** `crew_id + subfleet + qualified_from`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `crew_id` | str | Y | Pseudonymised crew id | `P000123` |
| `position` | str | Y | CA or FO | `FO` |
| `subfleet` | str | Y | Same vocabulary as h03 | `A321neoLR` |
| `qualified_from` | date | Y | Qualification start | `2023-09-01` |
| `qualified_to` | date | N | End (empty = current) |  |
| `source` | str | N | Training record / checkride reference type |  |

* Only needed if the scope stays A321neoLR; otherwise CrewSim simulates the whole A321 family (current behaviour).

### M01 - `m01_activity_code_map.csv` - Roster activity code classification (AIMS `CRCODES`)

* **Priority:** P2   **Suggested owner:** Crew Planning (validates our pre-filled list)
* **Feeds CrewSim:** Decides D2 `block_type` (PAIRING/DAY_OFF/VACATION/RESERVE/TRAINING/SIMULATOR/ABSENCE/OFFICE/OTHER), D4 `absence_type` (SICK/FAMILY/INJURY...), D5 reserve type (SC vs LC), D11 `session_type`, and who counts as available for drafting. WE PRE-FILL code, description and usage counts (`prefilled\m01_activity_code_map.prefilled.csv`, 450 codes; 181 used by pilots since 2024-05-14); Crew Planning only completes the blank columns for the codes in use.
* **Grain:** one row per AIMS activity code   **Key:** `aims_code_id`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `aims_code_id` | int | Y | AIMS code id (negative integer as stored in the roster) | `-17` |
| `crew_code` | str | Y | Code as seen by planners | `MAL` |
| `description` | str | Y | AIMS description (pre-filled) | `MALADIE - SICK` |
| `pilot_roster_rows_since_2024_05_14` | int | N | Usage in the window (pre-filled; use it to prioritise) | `9018` |
| `block_type` | str | Y | PAIRING, DAY_OFF, VACATION, RESERVE, TRAINING, SIMULATOR, ABSENCE, OFFICE, OTHER, REST | `ABSENCE` |
| `absence_type` | str | N | If ABSENCE: SICK, FAMILY, INJURY, LONG_TERM, PARENTAL, OTHER | `SICK` |
| `session_type` | str | N | If TRAINING/SIMULATOR: SIM, GROUND, PPC, CRM, RECURRENT, INITIAL_GROUND, EXAM, OTHER |  |
| `reserve_call_type` | str | N | If RESERVE: SC (short call) or LC (long call) |  |
| `counts_as_unavailable` | bool | Y | 1 if a crew member with this code cannot be drafted that day | `1` |
| `valid_from` | date | N | First day the code is used with this meaning |  |
| `valid_to` | date | N | Last day |  |
| `validated_by` | str | N | Department that validated |  |
| `comment` | str | N |  |  |

* Use the pre-filled CSV; fill the blank columns. Codes with 0 usage can be ignored.

### M02 - `m02_user_group_map.csv` - AIMS user and program -> organisational group (for `initiator`)

* **Priority:** P2   **Suggested owner:** IOC / Crew Control / IT
* **Feeds CrewSim:** D6 `initiator` and the draft export: who made a roster change (IOC/SOCC, crew planners, the crew member, an automated program such as bid award or movement control). AIMS stores user id and program name on each change but not the group.
* **Grain:** one row per AIMS user id or program   **Key:** `aims_user_or_program`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `kind` | str | Y | USER or PROGRAM | `PROGRAM` |
| `aims_user_or_program` | str | Y | AIMS user id / executable name as in the journal (`AIMSUSER`, `EXTERNALAPPL`) | `MOVEMENT.EXE` |
| `group` | str | Y | IOC, CREW_CONTROL, CREW_PLANNING, CREW_SELF_SERVICE, SYSTEM_AUTOMATIC, OTHER | `IOC` |
| `active_from` | date | N |  |  |
| `active_to` | date | N |  |  |

* User ids are staff login names: keep this file inside the company; CrewSim only needs the resulting group, so Pierre may instead return a ready-made mapping keyed by a pseudonymous user token that we generate (we can send him the distinct ids from the journal).

### M07 - `m07_training_rules.csv` - Training session rules and reschedule costs

* **Priority:** P2   **Suggested owner:** Training / Finance
* **Feeds CrewSim:** D11 `requalification_deadline` (AIMS holds only current expiry dates, manually overwritten) and `reschedule_cost_cad_estimate` (no source in AIMS).
* **Grain:** one row per session_type and period   **Key:** `session_type + effective_from`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `session_type` | str | Y | SIM, GROUND, PPC, CRM, RECURRENT, INITIAL_GROUND, EXAM, OTHER (same vocabulary as m01) | `PPC` |
| `crew_group` | str | Y | PILOT or CABIN | `PILOT` |
| `requalification_interval_days` | int | Y | Days between the session and the deadline of the next one | `365` |
| `reschedule_cost_cad` | float | N | Cost if the session must be rescheduled because the crew member is drafted | `1200` |
| `reschedule_cost_basis` | str | N | ACTUAL_MEAN, PLANNING_RATE, ESTIMATE | `ESTIMATE` |
| `effective_from` | date | Y |  | `2024-05-01` |
| `effective_to` | date | N |  |  |
| `source_reference` | str | N | Regulation / training manual |  |

* AIMS shows a 6-month PPC interval while v3 assumes 365 days: please state the correct one.

### M03 - `m03_cancellation_cause.csv` - Cancellation cause per flight

* **Priority:** P3   **Suggested owner:** IOC / OCC
* **Feeds CrewSim:** D8 `cancel_reason` (v3: a single value NOT_OPERATED_4_1; AIMS stores only an undecoded index CNXREASON 1-7). Needed to separate weather/technical/crew cancellations and to model crew-driven cascades.
* **Grain:** one row per cancelled flight leg   **Key:** `flight_no + flight_date + origin`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `flight_no` | str | Y | Flight number | `TS238` |
| `flight_date` | date | Y | Operating date (same as D8 `date`) | `2026-07-14` |
| `origin` | str | Y | Departure airport IATA | `YUL` |
| `destination` | str | N | Arrival airport IATA | `CDG` |
| `cancel_cause_category` | str | Y | WEATHER, TECHNICAL, CREW, ATC, AIRPORT, SCHEDULE_CHANGE, COMMERCIAL, SECURITY, OTHER | `WEATHER` |
| `cancel_cause_detail` | str | N | Short coded detail (no free text with personal data) |  |
| `decided_ts` | datetime | N | When the cancellation was decided (UTC) |  |
| `source_system` | str | N | OCC log, IROPS tool... |  |

* Note: only ~16 cancellations per month are decided within 2 days of departure; the rest are schedule-level removals - say if `SCHEDULE_CHANGE` rows should be excluded by CrewSim.

### M04 - `m04_event_journal_archive.csv` - Roster change journal before 2024-05-14 (only if an archive exists)

* **Priority:** P3   **Suggested owner:** AIMS administrators / Pierre
* **Feeds CrewSim:** AIMS journals `LOG_ROSTER`/`LOG_ROSTERDT` start on 2024-05-14 and `LOG` on 2023-11-08 (dense from 2024-03-14). If an archive or backup holds older journals, it extends the draft/notification history; otherwise CrewSim accepts the shorter depth.
* **Grain:** one row per roster change event   **Key:** `event_id`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `event_id` | str | Y | Unique id in the archive |  |
| `event_ts` | datetime | Y | When the change was made (state the time zone) |  |
| `event_type` | str | Y | INSERT, DELETE, UPDATE | `DELETE` |
| `crew_id` | str | Y | Pseudonymised crew id |  |
| `roster_day` | date | Y | Day of the roster element |  |
| `old_code_or_pairing` | str | N | Activity code or pairing id before |  |
| `new_code_or_pairing` | str | N | Activity code or pairing id after |  |
| `user_or_program` | str | N | As journalled (see m02) |  |

* A restore of the old journal tables into a sandbox and a yes/no answer is enough at this stage; we do not need a CSV unless it is easy.

### M05 - `m05_reserve_callout_outcomes.csv` - Reserve call-out outcomes not recorded in AIMS

* **Priority:** P3   **Suggested owner:** Crew Control
* **Feeds CrewSim:** D5 `outcome`: AIMS only records the assignment; declined, no-show and released-without-flying are rare or absent in AIMS codes.
* **Grain:** one row per call-out   **Key:** `callout_id`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `callout_id` | str | Y | Id in the call log |  |
| `crew_id` | str | Y | Pseudonymised crew id |  |
| `reserve_call_type` | str | Y | SC or LC | `SC` |
| `call_ts` | datetime | Y | Time the crew member was called (UTC) |  |
| `response_ts` | datetime | N | Time of the answer |  |
| `outcome` | str | Y | ASSIGNED, RELEASED, NO_SHOW, DECLINED, NOT_REACHED | `ASSIGNED` |
| `assigned_pairing_id` | str | N | `<code>_<yyyymmdd>` if assigned |  |

* Only if a call log / SMS / IVR system exists outside AIMS.

### M06 - `m06_draft_trigger.csv` - Why a draft happened (trigger)

* **Priority:** P3   **Suggested owner:** IOC / Crew Control
* **Feeds CrewSim:** Draft export field `trigger_reason`: not stored in AIMS; links drafts to sick calls, cancellations and delays for cascade validation.
* **Grain:** one row per draft (crew x pairing)   **Key:** `crew_id + pairing_id`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `crew_id` | str | Y | Drafted crew member (pseudonymised) |  |
| `pairing_id` | str | Y | `<code>_<yyyymmdd>` of the pairing assigned |  |
| `trigger_reason` | str | Y | SICK_CALL, CANCELLATION, DELAY_CASCADE, REST_VIOLATION, OPEN_TIME, SCHEDULE_CHANGE, OTHER | `SICK_CALL` |
| `trigger_ref` | str | N | Reference of the originating event (flight, absence) |  |

* Optional bonus; skip if no record exists.

### M08 - `m08_duty_conventions.csv` - Report / release and reserve window conventions

* **Priority:** P3   **Suggested owner:** Crew Planning
* **Feeds CrewSim:** D3 legs `report_local` / `release_local` (not stored per leg in AIMS; v3 used 60 min before departure and 30 min after arrival, planner code uses 15 min debrief) and D2 reserve window times.
* **Grain:** one row per crew_group, fleet family and period   **Key:** `crew_group + fleet_family + effective_from`

| Column | Type | Req | Description | Example |
|---|---|---|---|---|
| `crew_group` | str | Y | PILOT or CABIN | `PILOT` |
| `fleet_family` | str | Y | A321, A330, ... or ALL | `ALL` |
| `report_offset_minutes` | int | Y | Minutes before scheduled departure the crew reports (first duty of the day) | `60` |
| `release_offset_minutes` | int | Y | Minutes after scheduled arrival the crew is released | `30` |
| `subsequent_duty_report_offset_minutes` | int | N | Same for later duty days | `60` |
| `reserve_am_start_local` | str | N | HH:MM base-local start of the AM reserve window | `05:00` |
| `reserve_am_end_local` | str | N | HH:MM end | `13:00` |
| `reserve_pm_start_local` | str | N | HH:MM | `13:00` |
| `reserve_pm_end_local` | str | N | HH:MM | `21:00` |
| `effective_from` | date | Y |  | `2024-05-01` |
| `effective_to` | date | N |  |  |

* AIMS codes AM/PM exist; the actual time windows are not stored as data we could find.

## 7. Message d'accompagnement (brouillon, en francais)

Objet : CrewSim - lecture directe d'AIMS et donnees complementaires dont on a besoin de ta part

Bonjour Pierre,

Merci pour les trois envois. On change l'architecture de CrewSim : au lieu de charger des CSV, il va lire **directement la base AIMS (TSC)** en lecture seule (rosters, rotations, absences, reserves, drafts via `ROSTERDT`, vols, retards, hotels, formation, heures creditees). On a verifie que c'est possible et que les chiffres collent aux tiens (rotations 99,6-100 %, heures de paie a 0,2 %, call-outs de reserve a +/-2 par mois). On n'a donc plus besoin des extractions D1-D6, D8, D9, D11. On accepte aussi l'historique qui existe : pas besoin de 36 mois, a partir du 14 mai 2024 (debut fiable dans AIMS) c'est suffisant.

Par contre, certaines choses **ne sont pas dans AIMS**, surtout cote finance. Je t'envoie 21 schemas CSV (un modele vide + un exemple synthetique chacun) :

1. **Priorite 1 (finance/paie/RH)** : dictionnaire des codes de paie, registre de paie en dollars (heures, taux, montant, prime, rotation liee), taux horaires et multiplicateurs avec dates d'effet (dont le passage draft 1,5x -> 2x), regles de la convention (preavis reserve courte/longue, garantie, prime de draft, plafonds, duree), factures de positionnement (hotel/deadhead/transport avec montants), coefficients de cout de planification (remplacent nos valeurs fictives), la table de pseudonymes `crew_id` (canal securise, jamais dans le depot) et le statut d'emploi / dates d'embauche et de fin / anciennete.
2. **Priorite 2** : credit de paie par rotation, couts reels d'annulation et de retard, liste des immatriculations A321neoLR et l'historique de qualification neoLR, validation de notre classification des codes d'activite (on a deja pre-rempli les 450 codes), correspondance utilisateur AIMS -> groupe (IOC, planification...), regles de formation.
3. **Priorite 3 (si ca existe)** : cause reelle des annulations, anciens journaux AIMS avant le 14 mai 2024, issues des appels de reserve (refus, absence), cause des drafts, conventions de presentation/liberation.

Pour demarrer, le minimum utile est : codes de paie, registre de paie, taux, regles de la convention, coefficients de cout, table de pseudonymes et statut d'emploi. Les regles de format, de pseudonymisation (Loi 25) et les controles de coherence qu'on fera a la reception sont dans le document joint.

Si c'est plus simple, un appel de 30 minutes avec la paie, les RH et Crew Control suffira pour repartir les fichiers.

Merci !
Nabil


