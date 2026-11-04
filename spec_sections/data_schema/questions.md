# Placeholder Values Requiring Business Confirmation

> Every value below is currently a **plausible placeholder** — right order of magnitude, but **not** an Air Transat figure.
> No simulation result may inform a real bid-period decision until these are replaced with confirmed values.
> Items are grouped by the team that owns the answer.

---

## Crew Planning

### Q1 — Roster size (total crew in scope)

**Current placeholder:** `120`
**File:** `configs/base.yaml` line 57

How many First Officers are rostered on the A321neoLR out of YUL for the bid period being modelled?
This number includes both line holders and reserves (reserves are carved out of it, not added).
Provide the **published line count** for the target bid period.

**Why we need this:** The entire simulation population is sized from this number. Too high inflates the candidate pool and underestimates drafting pressure; too low does the opposite. The recommended reserve count (R*) is a fraction of this total — an error here shifts R* directly.

---

### Q2 — Reserve bid rule

**Current placeholder:** `senior_first`
**File:** `configs/base.yaml` line 71

When reserve lines are assigned via the seniority bid, do the **most junior** or **most senior** crew end up on reserve?

Options: `junior_first` | `senior_first`

**Why we need this:** This determines who occupies reserve slots and therefore who is available for drafting when reserves are exhausted. Senior reserves have different schedule patterns and legality profiles than junior ones, affecting eligibility rates and cascade behaviour.

---

### Q3 — Pairings per bid period

**Current placeholder:** `480`
**File:** `configs/base.yaml` line 81

How many A321neoLR FO pairings originate from YUL in a typical bid period (28 days)?

**Why we need this:** This sizes the demand side of the model. It is not yet consumed by the simulation engine but is declared for the next development phase when sick calls bind to real roster crew and pairings.

---

### Q4 — Service-level target: max uncovered legs

**Current placeholder:** `u_max = 3`, `epsilon = 0.05`
**File:** `configs/base.yaml` lines 103-104

What is the maximum number of uncovered legs per bid period that is operationally tolerable, and in what fraction of bid periods is it acceptable to exceed that number?

Example: "At most 3 uncovered legs, in no more than 5% of months."

**Why we need this:** This is the chance constraint that filters out candidate reserve levels. If it is too loose, the model recommends fewer reserves than operations actually needs. If too tight, it recommends an unnecessarily expensive pool. Without a confirmed target, no candidate is filtered with real confidence.

---

### Q5 — Reserve shift catalogue

**Current placeholder:** morning 06-18, afternoon 14-02, night 22-08
**File:** `configs/base.yaml` lines 185-188

What are the actual standby shift windows (start hour, duration) used for A321neoLR FO reserves at YUL?

**Why we need this:** The shift catalogue shapes the mock data generator. With real data this becomes moot (the engine reads each D2 roster row's own start/end verbatim), but until real rosters are loaded, the simulated reserve availability windows come from these shifts. Wrong windows distort eligibility and legality check outcomes.

---

### Q6 — Maximum duty period

**Current placeholder:** `13.0` hours
**File:** `configs/base.yaml` line 196

What is the maximum flight duty period (FDP) allowed under the current collective agreement and CARs for A321neoLR pilots?

**Why we need this:** This is legality rule L1. Every candidate assignment is checked against this limit. An incorrect value either blocks legal assignments (too low) or permits illegal ones (too high), directly affecting how many open items can be resolved by reserves.

---

### Q7 — Minimum rest periods

**Current placeholder:** `11.0` hours (home base), `10.0` hours (away)
**File:** `configs/base.yaml` lines 197-198

What are the minimum rest periods between duties at home base and away from base?

**Why we need this:** Legality rule L2. Rest violations cascade — if a draft forces a duty that violates rest, the crew member's next block is also broken, generating more open items. Getting this wrong amplifies or dampens cascade chains.

---

### Q8 — Reserve notification windows

**Current placeholder:** short-call `2.0` hours, long-call `14.0` hours
**File:** `configs/base.yaml` lines 199-200

How many hours of advance notice must a short-call reserve receive before reporting? And a long-call reserve?

**Why we need this:** Legality rule L8. A reserve whose notification window has already passed is ineligible. Shorter windows increase the eligible pool; longer windows shrink it. This directly drives how many reserves are "available" at any given moment.

---

### Q9 — Rolling duty and flight time limits

**Current placeholder:** 7-day duty `60.0h`, 7-day flight `35.0h`, 28-day duty `190.0h`
**File:** `configs/base.yaml` lines 201-203

What are the rolling 7-day duty hour limit, 7-day flight hour limit, and 28-day duty hour limit under the CBA/CARs?

**Why we need this:** Legality rules L3 and L4. These limits are the most common reason a reserve becomes ineligible mid-window. Incorrect limits distort the eligibility fraction the NHPP model is calibrated against, and shift the entire cost curve.

---

### Q10 — Does reserve on-call time count as duty?

**Current placeholder:** `true`
**File:** `configs/base.yaml` line 213

Do hours spent on standby (on call but not flying) accrue toward the rolling duty limits (L3/L4) and the L5 work-streak rule?

**Why we need this:** This is the single most consequential modelling assumption. If reserve hours count as duty, 6 consecutive standby days at 12h/day = 72h, exceeding L3's 60h limit by day 5. If they don't count, reserves stay eligible far longer. The recommended reserve level changes materially either way. The simulation can run both ways and report the gap, but the final recommendation requires knowing which interpretation the CBA mandates.

---

### Q11 — Deadhead duration for cross-base positioning

**Current placeholder:** `4.0` hours
**File:** `configs/base.yaml` line 229

What is the assumed duty time consumed by a deadhead positioning flight (e.g. YYZ→YUL to cover a YUL open item)?

**Why we need this:** A positioning leg eats into the crew member's duty-period budget (L1) and rolling limits (L3/L4). The engine uses this to decide whether a cross-base reserve is legally assignable after the deadhead. Too short makes cross-base look free; too long makes it look impossible.

---

### Q12 — Hotel on every deadhead?

**Current placeholder:** `true`
**File:** `configs/base.yaml` line 234

Does every cross-base deadhead positioning also incur a hotel night?

**Why we need this:** This determines whether the positioning cost is just the seat ($400) or seat + hotel ($400 + $220 = $620). Across hundreds of simulated cross-base dispatches, this is a material cost difference that shifts the breakpoint where cross-base becomes too expensive relative to drafting.

---

### Q13 — Cascade visibility lag

**Current placeholder:** `24.0` hours
**File:** `configs/base.yaml` line 258

How many hours after a draft occurs does the cascade impact (broken future blocks) become visible to the recovery pipeline?

**Why we need this:** This controls when cascade-generated open items enter the queue. A shorter lag means cascades compete with the original sick-call recovery; a longer lag means they arrive later, potentially after reserve pools are replenished. Affects cascade chain length and cost.

---

### Q14 — Fitting/holdout date boundary

**Current placeholder:** fitting `2023-08-01 to 2025-07-31`, holdout `2025-08-01 to 2026-07-31`
**File:** `configs/base.yaml` lines 33-34

What date range of historical data should be used for model fitting, and what range reserved for validation (holdout)?

**Why we need this:** The calibration pipeline refuses to fit on holdout data or validate on fitting data. When real data arrives, the split boundary must reflect the actual data span and any known regime changes (fleet introductions, base openings, CBA changes) that would make older data non-representative.

---

## Finance

### Q15 — Reserve guarantee per day

**Current placeholder:** short-call `$250/day`, long-call `$180/day`
**File:** `configs/costs_pilots.yaml` lines 14-15

What is the daily guarantee rate (CAD) paid to a short-call reserve and a long-call reserve, regardless of whether they are used?

**Why we need this:** This is the dominant structural cost component. Every additional reserve × every day × this rate = the fixed cost of the reserve pool. An error of $50/day × 6 reserves × 28 days = $8,400/bid-period — enough to shift R* by one or two levels.

---

### Q16 — Reserve utilisation delta

**Current placeholder:** `$150`
**File:** `configs/costs_pilots.yaml` line 16

What is the marginal cost (CAD) paid when a reserve is actually called out for a duty, on top of the daily guarantee?

**Why we need this:** This is the variable cost of actually using a reserve. It affects the marginal cost comparison between "use a reserve" vs. "draft a line holder."

---

### Q17 — Draft base premium and tier surcharges

**Current placeholder:** base `$500`, tier surcharges: day-off `$0`, pairing `$300`, training `$900`, vacation `$2,500`, simulator `$4,000`, training reschedule `$1,200`
**File:** `configs/costs_pilots.yaml` lines 19-26

What is the base premium paid on every draft, and what are the additional surcharges by disruption tier (what the drafted crew member was doing)?

**Why we need this:** Draft costs are the counterweight to reserve costs. If draft costs are understated, the model recommends fewer reserves (drafting looks cheap). If overstated, it recommends too many. The tier structure determines which kinds of disruption the model tries hardest to avoid.

---

### Q18 — Draft premium percentage

**Current placeholder:** `200%`
**File:** `d12_agreement_rules.yaml` line 11

What percentage premium does the collective agreement specify for drafted duty?

**Why we need this:** This multiplier is applied to draft compensation calculations. It must match the actual ALPA agreement terms.

---

### Q19 — Positioning costs (deadhead, hotel, transport)

**Current placeholder:** deadhead `$400`, hotel `$220`, transport `$402.54`
**File:** `configs/costs_pilots.yaml` lines 33-34, 47

What are the planning rates (CAD) for a deadhead positioning flight, a hotel night, and ground transport when positioning crew for cross-base coverage?

Note: the transport placeholder ($402.54) is currently derived from the D10 invoice mean — it is not a planning rate like the other two. Finance should provide the actual planning rate.

**Why we need this:** These three costs determine whether cross-base dispatch is cost-effective. The model decides between "draft a local line holder" vs. "fly in a reserve from another base" partly on this cost. Incorrect rates shift the boundary where cross-base becomes preferable.

---

### Q20 — Disruption costs (cancellation, delay)

**Current placeholder:** cancellation `$25,000`, delay `$55/minute`, terminal penalty `1.5× cancellation`
**File:** `configs/costs_pilots.yaml` lines 50-52

What is the internal cost attributed to cancelling one flight? What is the per-minute delay cost? What multiplier on cancellation cost should be used for the end-of-horizon terminal penalty?

**Why we need this:** The cancellation cost is the "ceiling" of the recovery pipeline — it is what happens when neither a reserve nor a draft can cover a flight. It anchors the entire cost function: if it is too low, the model accepts more cancellations than operations would tolerate; if too high, it over-invests in reserves.

---

### Q21 — Ground transport on every deadhead?

**Current placeholder:** `true`
**File:** `configs/base.yaml` line 245

Does every cross-base deadhead positioning incur a ground transport cost (airport ↔ hotel)?

**Why we need this:** Adds ~$400 per cross-base dispatch if true. Combined with Q12 (hotel), determines the full positioning bundle cost. Finance needs to confirm whether transport is always bundled with the hotel or billed independently.

---

## Legal

### Q22 — APPR compensation band for cancellations

**Current placeholder:** `hours_9_plus` ($1,000 per passenger)
**File:** `configs/costs_pilots.yaml` lines 55-65

Under the Canadian Air Passenger Protection Regulations (APPR), which delay band applies to a flight cancellation for purposes of costing? Is the current CTA schedule still valid?

Options: `hours_3_to_6` ($400) | `hours_6_to_9` ($700) | `hours_9_plus` ($1,000)

**Why we need this:** A cancelled flight incurs statutory APPR compensation per affected passenger. The band determines the per-passenger rate. Since the model does not simulate re-accommodation, the cancellation is assumed to fall in one band. This is a conservative-vs-optimistic choice that affects the total cost of leaving a flight uncovered.

---

## Labour Relations

### Q23 — Reserve on-call hours and duty accrual (same as Q10)

**Current placeholder:** `true`
**File:** `configs/base.yaml` line 213

Confirm with Labour Relations: under the current ALPA collective agreement, does time spent on reserve standby (on call but not flying) count toward the rolling duty-hour limits (L3: 60h/7d, L4: 190h/28d) and the L5 work-streak rule?

**Why we need this:** (See Q10 above.) This is the question that most affects the recommended reserve level. If Labour Relations and Crew Planning give different answers, the simulation should be run both ways and the gap reported.

---

## Data Science

### Q24 — Bernoulli eligibility parameter (REDUCED mode)

**Current placeholder:** `p_elig = 0.3`
**File:** `configs/base.yaml` line 113

What probability should REDUCED-mode smoke tests use for the Bernoulli eligibility coin flip?

**Why we need this:** REDUCED mode replaces real crew-state evaluation with a coin flip for fast testing. The probability should approximate the real eligibility fraction observed historically. This never affects production recommendations (REDUCED mode is blocked from producing them), but a wildly wrong value makes smoke tests misleading.

---

### Q25 — Bernoulli cascade probability (REDUCED mode)

**Current placeholder:** `p_cascade = 0.2`
**File:** `configs/base.yaml` line 116

What probability should REDUCED-mode use for generating synthetic cascade follow-on items?

**Why we need this:** Same rationale as Q24 — screening only. Should approximate the real cascade rate from D6 data.

---

### Q26 — D4 link marginal threshold

**Current placeholder:** `0.90`
**File:** `configs/base.yaml` line 131

What is the marginal-pass threshold for the D4 sick-call linkage quality gate (the pass threshold is 0.95)?

**Why we need this:** Below this threshold, the data quality gate fails outright. Between marginal and pass, it warns. This is not spec-cited — it was an implementation judgment call. Data Science should confirm or adjust based on what fraction of sick calls they expect to link to a pairing in real data.

---

### Q27 — Station-day coverage threshold (was: D9 completeness)

**Current placeholder:** `0.98`
**File:** `configs/base.yaml` → `quality_gates.station_day_coverage_pass`

**F-42 change:** D9 is no longer an input — the daily regime is computed by a hidden Markov model from
D8/D4/D2 (spec §6.3-4) — so its completeness is no longer gated. The gate now measures the fraction of
days, at each crew base, on which D8 records departures.

What fraction of base-days must carry D8 departures for the coverage quality gate to pass?

**Why we need this:** A missing day is uninformative to the regime model, and a run of missing days
blinds it to the streaks it is meant to learn. This is not spec-cited. Data Science should confirm what
coverage level is acceptable for the regime model to fit reliably.

### Q27b — Regime model settings (new, F-42)

**Current placeholders:** `delay_threshold_minutes: 15`, `min_state_share: 0.01`
**File:** `configs/base.yaml` → `calibration.regime_hmm`

1. Should a departure count as "delayed" for the regime model at ≥ 15 min (industry on-time
   definition), or at another threshold?
2. Does Air Transat keep an operational disruption log (weather / ATC / IROPS declarations)? If so it
   can be supplied as D9 to *cross-check* the computed labels — it is never required.

**Why we need this:** The threshold decides which days look disrupted to the model. A state holding
fewer than 1% of days is flagged as "degenerate" — a sign the data supports fewer than four regimes
(the store's BIC model selection reports which number of states the data prefers).

---

### Q28 — V2 Erlang-B confidence level

**Current placeholder:** `0.95`
**File:** `configs/base.yaml` line 251

What confidence level should the V2 verification gate use when comparing DES blocking probability against the Erlang-B analytical solution?

**Why we need this:** A higher level makes the gate harder to pass (wider confidence interval). This is a verification tolerance — it determines how much statistical noise is acceptable before the gate flags a discrepancy between the simulation and the closed-form solution.

---

### Q29 — Welch warm-up tolerance

**Current placeholder:** `0.5`
**File:** `configs/base.yaml` line 255

What fractional tolerance should the Welch warm-up diagnostic use to determine whether the daily open-item mean has settled?

**Why we need this:** If the warm-up period is too short, initial transients contaminate the KPIs. This tolerance controls how close the warm-up mean must be to the measurement-window mean before the simulation is considered "settled." A tighter tolerance may require a longer warm-up.
