# Slice 1c — Eligibility Engine FULL

**Epic E1c** · 5 stories · Gate: **V3 — eligibility rate on the HOLDOUT window**
Needs datasets **D2, D4, D5**.

This slice completes the legality surrogate and turns eligibility into a measured, validated output.
It is the first slice whose gate can genuinely fail on the merits rather than on a bug.

> **The trap this slice must avoid.** If you adjust roster composition or rest rules until the emergent
> rate lands on 30%, hitting 30% proves nothing — you engineered it. Rosters come from real D2 data,
> the rate falls where it falls, and the gap is reported. See §6.4.

---

## ⏳ [TODO] S1c-01 — Eligibility engine FULL, with distribution logging
**Size:** `M` | **Depends on:** S1b-07 | **Spec:** §5.5

**As a** modeller **I want** eligibility computed per event from crew state

### Description
Real eligibility depends on real schedules. We cannot just assume 30% of pilots are eligible; we must check their actual calendar availability and legality dynamically.
**so that** the ≈30% figure is an output to be validated, not an input to be assumed.

### Acceptance Criteria
- [ ] Pool = reserves whose RESERVE block covers the **duty window**, not merely the moment of the call
- [ ] Eligible = pool ∩ legal under L0–L8
- [ ] The realised fraction is logged **per event**, and the full distribution is retained — V3 compares
  distributions, so a running mean is not enough
- [ ] `REDUCED` mode (`Bernoulli(p_elig)`) still available, and **refuses to produce a recommendation**

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_eligibility.py`
*   🙋 **Manual:** `crewsim run --policy R10 --scenarios 200 --report-eligibility`
    *   **Expect:** a histogram, not a single mean
    *   **Fails if:** the pool is computed at the moment of the phone call — a reserve whose on-call window
    *   ends at 18:00 cannot take a trip reporting at 19:00

---

## ⏳ [TODO] S1c-02 — Rule L8, reserve notification time
**Size:** `S` | **Depends on:** S1c-01, S1b-03 | **Spec:** §5.4

**As a** reviewer **I want** reserve notification limits enforced

### Description
Calling a reserve 30 minutes before a flight is physically impossible. This rule ensures the engine only drafts crew who can realistically commute to the airport.
**so that** I don't model assigning crews who cannot make it to the airport in time.

### Acceptance Criteria
- [ ] Short-call minimum notice 2 h, long-call 12 h — from config, per §4.4
- [ ] Applied against the **call time**, not the report time
- [ ] A test makes L8 the binding rule, with all other rules satisfied

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_legality.py -k L8`
*   🙋 **Manual:** `crewsim explain-legality --crew R002 --pairing TS156 --call-at "15:00"`
    *   **Expect:** `ILLEGAL_L8` for a long-call reserve given one hour of notice
    *   **Fails if:** long-call and short-call behave identically — L8 is not binding, and eligibility
    *   will stay far above 30%
    *   > This is the single biggest reason the reference implementation reports 0.54–0.96 eligibility instead
    *   > of ≈0.30 (§8.3). Expect the number to move sharply when this lands.

---

## ⏳ [TODO] S1c-03 — Rules L3 and L4, rolling limits
**Size:** `M` | **Depends on:** S1c-01 | **Spec:** §5.4

**As a** reviewer **I want** rolling block and duty limits enforced

### Description
A pilot cannot fly indefinitely. Rolling limits (e.g. 100 hours in 28 days) prevent the engine from over-working a single crew member beyond union constraints.
**so that** the simulation does not assign illegal schedules leading to violations.

### Acceptance Criteria
- [ ] L3: 60 h duty / 35 h flight in a rolling 7 days · L4: 190 h duty in a rolling 28 days
- [ ] Counters **roll** — hours leave the window as time passes
- [ ] Counters are part of `L_c(t)` in the state vector, and are checkpointable with it

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_legality.py -k "L3 or L4"`
*   🙋 **Manual:** `crewsim explain-crew --crew C0041 --show-counters`
    *   **Expect:** rolling duty and flight hours that accumulate **and decay**
    *   **Fails if:** counters only ever increase — the window is not rolling, and every crew member
    *   eventually becomes permanently illegal

---

## ⏳ [TODO] S1c-04 — Rule L5, one duty-free day per rolling 7
**Size:** `S` | **Depends on:** S1c-03 | **Spec:** §5.4

**As a** reviewer **I want** the mandatory one-duty-free-day-in-seven rule enforced

### Description
Fatigue mitigation is paramount. This guarantees that even heavily drafted crew receive mandatory days off, avoiding structural violations.
**so that** long-term fatigue compliance is properly modeled.

### Acceptance Criteria
- [ ] Enforced on **both** the reserve-assignment and drafting paths
- [ ] Added to the hypothesis invariant suite alongside L0

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_legality.py -k L5`
*   🙋 **Manual:** `crewsim run --policy R6 --scenarios 100 --assert-invariants`
    *   **Expect:** no crew member ever works 7 consecutive days
    *   **Fails if:** any violation appears — L5 is being checked on one path but not the other

---

## ⏳ [TODO] S1c-05 — V3 gate on the HOLDOUT window  ·  **gate V3**
**Size:** `M` | **Depends on:** S1c-04, S0-04, S0-09 | **Spec:** §9.2, §6.4

**As a** reviewer **I want** the emergent eligibility rate compared against history it has never seen

### Description
Validating the eligibility logic against unseen historical data proves it works. If we predict 30% eligibility but history shows 10%, our rules are too loose.
**so that** the model's central claim is actually tested.

### Acceptance Criteria
- [ ] Simulated distribution compared against the historical band from S0-04, on the **holdout** window
- [ ] Verdict stated explicitly: PASS / FAIL, with the gap quantified either way
- [ ] **Every run surfaces this**, not just the gate command — a number failing V3 must never reach a
  planner silently
- [ ] If it fails, the report names the *mechanism* suspected, not a parameter to nudge

### Verification
*   🤖 **Automated:** `pytest tests/gates/test_v3_eligibility.py`
*   🙋 **Manual:** `crewsim gate v3 --window holdout`
    *   **Expect:** both distributions plotted, the band shown, a stated verdict
    *   **Fails if:** it passes only on the fitting window, or if inputs were adjusted until it passed
    *   ### If V3 fails — the response order
    *   | | Response | When appropriate |
    *   |---|---|---|
    *   | 1 | **Find the missing mechanism** | Almost always. Reserve rotation and L8 are the usual culprits |
    *   | 2 | Widen the band with written justification | When the historical target itself is uncertain |
    *   | 3 | Downgrade to advisory, stated in every report | Last resort |
    *   | ✗ | Adjust inputs until it passes | **Never** |

