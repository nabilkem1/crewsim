# CrewSim Data Dictionary

> Each section below corresponds to a dataset file expected by the simulator.
> The sample CSVs in this folder contain 20 rows each so your colleague can see the exact format, column order, and value patterns required.
> **`used_in_code`** indicates whether the field is actively consumed by simulation, calibration, or validation logic (Yes), or only declared in the schema for completeness / future use (No).

---

## D1 — `d1_crew_master.csv`

Crew roster master list. One row per crew member, containing identity, base assignment, fleet qualification, seniority, and employment status.

| Field | Type | Description | used_in_code |
|---|---|---|---|
| crew_id | string | Opaque surrogate key identifying the crew member (e.g. `P00001`). Must NOT be a real name or employee number (Law 25). | Yes |
| base | string | Home base IATA code (e.g. `YUL`, `YYZ`, `YVR`). | Yes |
| crew_group | string | Crew group: `PILOT` or `CABIN`. Used to filter the population scope. | Yes |
| position | string | Seat position: `CA` (Captain) or `FO` (First Officer) for pilots. | Yes |
| fleet | string | Fleet type the crew member is qualified on (e.g. `A321-200`, `A330-200`). | Yes |
| fleet_family | string | Fleet family grouping (e.g. `A321`, `A330`). Broader than fleet. | No |
| qual_valid_from | date | Start date of the current type-rating qualification period. | No |
| qual_valid_to | date | Expiry date of the current type-rating qualification. | No |
| seniority_number | integer | Company-wide seniority rank (1 = most senior). Drives drafting order. | Yes |
| employment_status | string | Current status: `ACTIVE`, `INITIAL_TRAINING`, `LEAVE`, etc. Only `ACTIVE` crew enter the simulation. | Yes |
| hire_date | date | Date the crew member was hired. | No |
| termination_date | date | Date of termination, if applicable. Empty for active crew. | No |

---

## D2 — `d2_rosters.csv`

Published roster blocks. One row per calendar block (pairing, day off, vacation, reserve, training, simulator) per crew member, covering the full data window.

| Field | Type | Description | used_in_code |
|---|---|---|---|
| crew_id | string | Foreign key to D1. | Yes |
| base | string | Base for this roster period. | Yes |
| fleet | string | Fleet for this roster period. | Yes |
| position | string | Position for this roster period. | Yes |
| block_type | string | Type of block: `PAIRING`, `DAY_OFF`, `VACATION`, `RESERVE`, `TRAINING`, `SIMULATOR`, `REST`. | Yes |
| start_utc | datetime | Block start in UTC (ISO 8601, minute precision). | Yes |
| end_utc | datetime | Block end in UTC. | Yes |
| start_local | datetime | Block start in local (base) time. Used for legality duty-window checks. | Yes |
| end_local | datetime | Block end in local time. | No |
| pairing_id | string | Foreign key to D3 when block_type is `PAIRING`. Empty otherwise. | Yes |
| reserve_call_type | string | `SC` (short-call) or `LC` (long-call) when block_type is `RESERVE`. Empty otherwise. | Yes |

---

## D3 — `d3_pairings.csv`

Pairing header records. One row per pairing (a multi-day trip sequence), with summary attributes.

| Field | Type | Description | used_in_code |
|---|---|---|---|
| pairing_id | string | Unique pairing identifier (e.g. `YULA321-000001`). Foreign key target for D2, D3 legs, D4, D5, D6, D7, D10. | Yes |
| base | string | Originating base for the pairing. | Yes |
| fleet | string | Fleet type assigned to the pairing. | Yes |
| position_complement | string | Required crew complement per position (e.g. `CA:1,FO:1,FA:5`). | No |
| duty_periods | integer | Number of duty periods (work days) in the pairing. | No |
| credit_hours | float | Total credited flight hours for pay purposes. | No |
| layover_stations | string | Pipe-separated list of layover station codes (e.g. `TLS\|VCE\|GCM`). | No |
| start_date | date | Date the pairing begins. | No |
| days | integer | Total calendar days spanned by the pairing. | No |

---

## D3 — `d3_pairing_legs.csv`

Individual flight legs within each pairing. One row per leg, with timing and operational details.

| Field | Type | Description | used_in_code |
|---|---|---|---|
| pairing_id | string | Foreign key to D3 pairings header. | Yes |
| duty_period | integer | Duty period number within the pairing (1-based). | Yes |
| leg_seq | integer | Leg sequence within the duty period (1-based). | No |
| flight_no | string | Flight number (e.g. `TS238`). | No |
| origin | string | Departure station IATA code. | No |
| destination | string | Arrival station IATA code. | No |
| report_local | datetime | Crew report time in local time (includes pre-flight duty). | Yes |
| dep_local | datetime | Scheduled departure in local time. | No |
| arr_local | datetime | Scheduled arrival in local time. | No |
| release_local | datetime | Crew release time in local time (includes post-flight duty). | Yes |
| block_hours | float | Block time for this leg in hours (chock-to-chock). | Yes |

---

## D4 — `d4_absences.csv`

Crew absence events (sick calls, injuries, family leave). One row per absence occurrence. This is the primary input for calibrating the sick-call arrival model (NHPP).

| Field | Type | Description | used_in_code |
|---|---|---|---|
| absence_id | string | Unique absence identifier (e.g. `A000001`). | Yes |
| crew_id | string | Foreign key to D1. | Yes |
| notification_ts | datetime | Timestamp when the absence was reported (drives notification-to-departure lead time). | Yes |
| absence_start | date | First day of absence. Key date for NHPP arrival counting and regime joining. | Yes |
| absence_end | date | Last day of absence. | Yes |
| duration_days | integer | Total absence duration in calendar days. Used to fit the absence-duration distribution. | Yes |
| absence_type | string | Category: `SICK`, `INJURY`, `FAMILY`. | Yes |
| affected_pairing_id | string | The pairing that was affected (uncovered) by this absence. Foreign key to D3. | Yes |
| base | string | Crew member's base at time of absence. | Yes |
| fleet | string | Crew member's fleet at time of absence. | Yes |
| position | string | Crew member's position at time of absence. | Yes |

---

## D5 — `d5_reserve_callouts.csv`

Reserve activation records. One row per reserve crew member contacted for a coverage assignment.

| Field | Type | Description | used_in_code |
|---|---|---|---|
| callout_id | string | Unique callout identifier (e.g. `R000001`). | No |
| crew_id | string | Foreign key to D1 — the reserve crew member contacted. | Yes |
| call_ts | datetime | Timestamp when the reserve was called. | Yes |
| report_ts | datetime | Timestamp when the reserve reported for duty. | No |
| assigned_pairing_id | string | The pairing the reserve was assigned to cover. Foreign key to D3. | Yes |
| outcome | string | Result of the callout: `assigned`, `released`, `no-show`, `declined`. | Yes |
| base | string | Reserve's base. | Yes |
| fleet | string | Reserve's fleet. | Yes |

---

## D6 — `d6_schedule_changes.csv`

Schedule modification records. One row per roster change event, capturing drafts (`SHORT_NOTICE_COVER`) and cascade effects (`CASCADE_UNCOVERED`). Used to reconstruct historical drafting and validate the cascade model.

| Field | Type | Description | used_in_code |
|---|---|---|---|
| change_id | string | Unique change identifier (e.g. `S000001`). | Yes |
| crew_id | string | Foreign key to D1 — the affected crew member. | Yes |
| change_ts | datetime | Timestamp of the schedule change. | Yes |
| old_block_type | string | Block type before the change (e.g. `DAY_OFF`, `PAIRING`). | Yes |
| new_block_type | string | Block type after the change (e.g. `PAIRING`, `OPEN`). | Yes |
| new_pairing_id | string | The pairing assigned in the change, if applicable. Foreign key to D3. | Yes |
| reason_code | string | Reason: `SHORT_NOTICE_COVER` (draft), `CASCADE_UNCOVERED`, `VOLUNTARY_SWAP`, etc. | Yes |
| initiator | string | Who initiated the change: `IOC` (operations control), `CREW`, or empty. | Yes |

---

## D7 — `d7_pay_register.csv`

Payroll records related to reserve utilization and drafting premiums. Used for backtest cost validation (gate V6).

| Field | Type | Description | used_in_code |
|---|---|---|---|
| crew_id | string | Foreign key to D1. | Yes |
| pay_period | string | Bid period in `YYYY-MM` format (e.g. `2023-08`). | Yes |
| pay_code | string | Payment category: `RESERVE_UTIL`, `DRAFT_PREM`, `POSITIONING`, etc. | Yes |
| amount_cad | float | Payment amount in Canadian dollars. | Yes |
| duty_date | date | The specific duty date this payment relates to. | No |
| linked_pairing_id | string | The pairing this payment is linked to. Foreign key to D3. | Yes |

---

## D8 — `d8_flight_movements.csv`

Operational flight records with scheduled vs. actual times. Used to calibrate the delay distribution model and — since F-42 — as the main input of the **regime hidden Markov model** that infers each day's disruption severity (daily departures, delayed ≥ 15 min and cancelled, per crew base). D8 must cover every day at every crew base (quality gate `station_day_coverage_pass`).

| Field | Type | Description | used_in_code |
|---|---|---|---|
| flight_no | string | Flight number (e.g. `TS793`). | Yes |
| date | date | Operating date of the flight. | Yes |
| origin | string | Departure station IATA code. | Yes |
| destination | string | Arrival station IATA code. | Yes |
| fleet | string | Aircraft fleet type. | Yes |
| sched_dep_local | datetime | Scheduled departure in local time. | No |
| sched_arr_local | datetime | Scheduled arrival in local time. | No |
| actual_dep_local | datetime | Actual departure in local time. | No |
| actual_arr_local | datetime | Actual arrival in local time. | No |
| delay_minutes | integer | Departure delay in minutes (0 = on time). Key field for delay model calibration. | Yes |
| iata_delay_code | string | IATA standard delay code (e.g. `41` = technical, `93` = crew). | No |
| cancelled | integer | Cancellation flag: `0` = operated, `1` = cancelled. | Yes |
| cancel_reason | string | Reason for cancellation, if applicable. | No |

---

## D9 — `d9_station_days.csv` *(optional — no longer an input, F-42)*

**D9 does not need to be supplied.** The daily severity regime (`CALM`, `NORMAL`, `DISRUPTED`,
`SEVERE`) is now **computed** by a hidden Markov model (`calibration/regime.py`) from D8 (departures,
delays, cancellations), D4 (sick calls) and D2 (crew on duty) — see spec §6.3-4. Nobody at Air Transat
has to define or assign these classes.

If a D9 file is present it is read **only** by the optional diagnostic `regime_label_agreement`, which
reports how often the computed labels match it. In the mock corpus D9 holds the generator's *true*
hidden regime, so that diagnostic measures how well the model recovers it.

| Field | Type | Description | used_in_code |
|---|---|---|---|
| station | string | Station IATA code (e.g. `AMS`, `YUL`). | Diagnostic only |
| date | date | Calendar date. | Diagnostic only |
| disruption_class | string | Severity regime: `CALM`, `NORMAL`, `DISRUPTED`, `SEVERE`. | Diagnostic only |
| season | string | Season label: `winter_sun`, `summer_atlantic`, `shoulder`. | No |
| intensity_multiplier | float | Numeric multiplier reflecting disruption intensity (e.g. `0.5` for CALM, `1.0` for NORMAL). | No |

---

## D10 — `d10_positioning_invoices.csv`

Positioning cost invoices (deadhead flights, hotels, ground transport) incurred when covering open pairings away from base. Used for backtest cost validation.

| Field | Type | Description | used_in_code |
|---|---|---|---|
| date | date | Invoice date. | Yes |
| station | string | Station where the cost was incurred. | Yes |
| cost_type | string | Category: `DEADHEAD`, `HOTEL`, `TRANSPORT`. | No |
| amount_cad | float | Invoice amount in Canadian dollars. | Yes |
| crew_id | string | Foreign key to D1 — the crew member being positioned. | Yes |
| pairing_id | string | Foreign key to D3 — the pairing being covered. | Yes |

---

## D11 — `d11_training_sessions.csv`

Crew training and simulator session records. One row per session. Currently declared in the schema for future use (drafting tier classification for training disruption).

| Field | Type | Description | used_in_code |
|---|---|---|---|
| crew_id | string | Foreign key to D1. | Yes |
| session_type | string | Training type: `SIM` (simulator) or `GROUND` (classroom). | No |
| start_date | date | Session start date. | Yes |
| end_date | date | Session end date. | Yes |
| requalification_deadline | date | Deadline by which this training must be completed to maintain qualification. | No |
| reschedule_cost_cad_estimate | float | Estimated cost in CAD to reschedule this session if disrupted by a draft. | No |


