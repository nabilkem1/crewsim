# Slice 1b — Real Rosters & the Full Event Set

**Epic E1b** · 7 stories · Gate: **V2 Erlang-B sanity bound**
Needs datasets **D1, D2**.

This is where the model stops running on synthetic crew and starts running on a real population. Three
of the remaining v2 defects land here (D4, D5, and headcount conservation), and it is the slice that
makes `roster_size` stop being inert.

---

## 🟢 [DONE] S1b-01 — Load D1/D2 into the Crew State Engine
**Size:** `L` | **Depends on:** S1a-12, S0-01 | **Spec:** §5.1, §5.4, §6.1

**As a** modeller **I want** the crew population to come from published rosters

### Description
We need real crew state, not synthetic models. By loading D2 rosters, the engine respects actual seniorities, fleet qualifications, and base assignments.
**so that** eligibility and drafting are computed against people who actually exist.

### Acceptance Criteria
- [x] Crew, quals, seniority and calendar blocks load from D1/D2 into `CrewMember` / `Block`
- [x] **Only `ACTIVE` crew are rostered.** `LONG_TERM_ABSENCE`, `INITIAL_TRAINING`, `FLEET_TRANSITION`,
  `MANAGEMENT_OR_INSTRUCTOR` and `TERMINATED` are excluded, and the exclusion count is reported
- [x] Blocks are validated on load: sorted, non-overlapping for duty types (L0 holds on input too)

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_roster_loader.py`
*   🙋 **Manual:** `crewsim roster summary --base YUL --fleet A321neoLR --position FO`
    *   **Expect:** **112** crew rostered from an establishment of **120** — 8 excluded, with reasons listed
    *   **Fails if:** 120 load — non-ACTIVE statuses are being counted as available, overstating the
    *   draft pool by 7% and pushing the recommended reserve level down

---

## 🟢 [DONE] S1b-02 — Headcount conservation
**Size:** `M` | **Depends on:** S1b-01 | **Spec:** §5.10, §7.5

**As a** planner **I want** reserves carved *out* of the roster, not added to it

### Description
Reserves are carved out of the existing pool. If an airline has 120 pilots, allocating 10 to reserve means only 110 are left to fly regular lines.
**so that** a reserve has a real opportunity cost.

### Acceptance Criteria
- [x] `line_holders + reserves == roster_size` for every candidate R — asserted, not assumed
- [x] The flying those reserve bidders would have flown enters open time (or is absorbed per config)
- [x] Reserve bidders selected by the configured bid rule, not arbitrarily

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_headcount.py`
*   🙋 **Manual:** `crewsim roster summary --policy R10 --show-split`
    *   **Expect:** line holders + reserves = `roster_size` exactly, at every R
    *   **Fails if:** the total grows with R — reserves are being minted, as in v2
    *   > This corrects the recommended **level**, not the shape of the cost curve. The curve is already
    *   > U-shaped once staffing is booked correctly (S1a-04); what is missing without this is the opportunity
    *   > cost of the line a reserve is not flying.

---

## 🟢 [DONE] S1b-03 — Reserve lines with rotation and SC/LC split
**Size:** `M` | **Depends on:** S1b-02 | **Spec:** §5.0.2, §5.5, §4.5

**As a** planner **I want** reserve lines to follow rotational rules and Short-Call/Long-Call splits

### Description
Reserves don't work 24/7. Modeling their realistic on/off rotations ensures we don't accidentally overstate reserve availability on weekends.
**so that** I model realistic reserve availability instead of uniform pools.

### Acceptance Criteria
- [x] Reserve blocks follow an on/off rotation from D2 — **not** one flat horizon-long block
- [x] Short-call and long-call are distinct, carried through from `d2_rosters.reserve_call_type`
- [x] Reserve availability is a property of the *individual and the window*, not a scalar count

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_reserve_lines.py`
*   🙋 **Manual:** `crewsim roster reserve-pattern --policy R10`
    *   **Expect:** visible on/off rotation; SC/LC split roughly 60/40
    *   **Fails if:** every reserve is on call every day — eligibility will read ~100% instead of ~30%,
    *   and gate V3 cannot pass

---

## 🟢 [DONE] S1b-04 — Bind sick calls to roster crew  ·  fixes **D5**
**Size:** `M` | **Depends on:** S1b-01 | **Spec:** §5.0.4/E1, §5.2

**As a** modeller **I want** a sick call to remove a specific person

### Description
Sick calls must hit real people. This prevents the model from generating phantom sick time and forces the engine to handle real broken pairings.
**so that** demand is a consequence of crew state rather than an independent stream.

### Acceptance Criteria
- [x] Sick calls sample from crew who are **on or about to report for** duty
- [x] The absent crew member is removed for the sampled duration; multi-day absences break several pairings
- [x] Their pairing(s) become open-time items with the correct deadline

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_sick_calls.py`
*   🙋 **Manual:** `crewsim explain-event --scenario 0 --event SICK_CALL --first`
    *   **Expect:** a named crew member removed from the pool, and their pairing appearing as open time
    *   **Fails if:** open time appears with nobody removed — demand is still exogenous, which undercuts
    *   the whole emergence claim

---

## 🟢 [DONE] S1b-05 — Events E6 DUTY_END and E7 REST_END  ·  fixes **D4**
**Size:** `M` | **Depends on:** S1b-03 | **Spec:** §5.0.3, §5.0.4

**As a** modeller **I want** duties and rest periods to explicitly end on schedule

### Description
Crew members must return to availability after duty. A drafted reserve needs mandatory rest, but must eventually become available again for another draft.
**so that** crews are returned to availability correctly.

### Acceptance Criteria
- [x] Duty closes at E6; REST inserted per L2; rolling counters updated
- [x] At E7 the crew member becomes assignable again; a reserve's remaining on-call window is **restored**
- [x] Assignment **splits** a reserve block around duty + rest — never deletes it

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_events.py -k "duty_end or rest_end"`
*   🙋 **Manual:** `crewsim explain-crew --crew R001 --scenario 0 --timeline`
    *   **Expect:** `RESERVE → duty → REST → RESERVE` — back on call the next day
    *   **Fails if:** the reserve disappears after one use, or is bookable again during rest

---

## 🟢 [DONE] S1b-06 — Event E8 UNCOVERED_DEADLINE
**Size:** `M` | **Depends on:** S1b-05 | **Spec:** §5.0.3, §5.0.4

**As a** modeller **I want** open items held to their deadline

### Description
Airlines hold open flights to the last minute hoping someone frees up. Delaying the cancellation decision allows late-arriving reserves to rescue trips.
**so that** a reserve who frees up late can still rescue a flight.

### Acceptance Criteria
- [x] An uncoverable item is **held**, not cancelled on the spot; the pipeline retries as state changes
- [x] Cancellation and APPR compensation book at the deadline
- [x] Deadline is configurable and may vary by route type — see `QUESTIONS_TO_ASK.md` §1.6

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_events.py -k deadline`
*   🙋 **Manual:** `crewsim explain-event --scenario 0 --event UNCOVERED_DEADLINE --first`
    *   **Expect:** the item held to its deadline, with at least one retry visible in the trace
    *   **Fails if:** cancellation is booked at the moment of failure — rescues become impossible and
    *   cancellations are overstated

---

## 🟢 [DONE] S1b-07 — V2 Erlang-B sanity bound  ·  **gate V2**
**Size:** `M` | **Depends on:** S1b-06 | **Spec:** §7.8, §9.2

**As a** reviewer **I want** the queueing behaviour checked against a closed-form result

### Description
Queueing theory acts as a mathematical backstop. If the DES engine's shortfall rate drastically deviates from Erlang B, we know the reserve accounting is bugged.
**so that** a machinery bug is caught before any validation gate is attempted.

### Acceptance Criteria
- [x] Single base, single fleet, cascades disabled, eligibility-thinned Poisson arrivals
- [x] DES shortfall probability compared against `B(s, a)`; both printed side by side
- [x] Runs in CI — this is the cheapest possible check that the machinery works at all

### Verification
*   🤖 **Automated:** `pytest tests/gates/test_v2_erlang.py`
*   🙋 **Manual:** `crewsim gate v2 --show-comparison`
    *   **Expect:** DES shortfall inside the Erlang-B confidence interval, shown next to it
    *   **Fails if:** they differ by more than the CI — reserve accounting has a bug; stop and fix it
    *   before attempting V3

---

## 🟢 [DONE] S1b-08 — Scenario Generation from Frozen Parameters
**Size:** `M` | **Depends on:** S0-08b, S1a-05 | **Spec:** §2.5.0, §2.5.1, §5.2

This is Layer 3 of §2.1.

**As a** researcher **I want** to generate scenarios directly from the frozen parameters and a master seed

### Description
Perfect caching avoids re-running expensive simulations. If the transition matrix and seed are identical, we just load the cached scenario ledger.
**so that** simulation caching is perfectly stable and immediately invalidated by parameter changes.

### Acceptance Criteria
- [x] Each simulation day samples (Z_d) from the fitted transition matrix.
- [x] Applies the state's multiplier to both sick calls and delays.
- [x] Materializes the resulting events.
- [x] Writes `scenario_set.parquet`, keyed by `(master_seed, params_content_hash)`.
- [x] A second execution reports a cache hit and generates nothing.

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_scenario_gen.py`
*   🙋 **Manual:** `crewsim scenarios generate --scenarios 100 --master-seed 20260704` (run twice)
    *   **Expect:** Second run reports a cache hit and skips generation.
    *   **Fails if:** Scenario regenerates despite unchanged inputs; or sick calls/delays use different regime multipliers.

---

## What to look at once this slice passes
    *   Re-run the reserve sweep. Two things should now be true that were not before:
    *   - `roster_size` stops being inert. Before headcount conservation it made no difference at all — argmin
    *   E[C] sat at R=6 for 100, 120 and 140 — because senior-first drafting only ever reached the top ~21 of
    *   the seniority list.
    *   - The eligibility rate should fall from ~0.8 toward the ~0.3 target, because reserve lines now rotate
    *   and L8 will bind in 1c.
    *   Neither is a gate here. Both are observations that tell you whether 1c is worth starting.

