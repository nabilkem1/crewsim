# Slice 1b — Real Rosters & the Full Event Set

**Epic E1b** · 7 stories · Gate: **V2 Erlang-B sanity bound**
Needs datasets **D1, D2**.

This is where the model stops running on synthetic crew and starts running on a real population. Three
of the remaining v2 defects land here (D4, D5, and headcount conservation), and it is the slice that
makes `roster_size` stop being inert.

---

## ⏳ [TODO] S1b-01 — Load D1/D2 into the Crew State Engine
**Size:** `L` | **Depends on:** S1a-12, S0-01 | **Spec:** §5.1, §5.4, §6.1

**As a** modeller **I want** the crew population to come from published rosters
**so that** eligibility and drafting are computed against people who actually exist.

### Acceptance Criteria
- [ ] Crew, quals, seniority and calendar blocks load from D1/D2 into `CrewMember` / `Block`
- [ ] **Only `ACTIVE` crew are rostered.** `LONG_TERM_ABSENCE`, `INITIAL_TRAINING`, `FLEET_TRANSITION`,
  `MANAGEMENT_OR_INSTRUCTOR` and `TERMINATED` are excluded, and the exclusion count is reported
- [ ] Blocks are validated on load: sorted, non-overlapping for duty types (L0 holds on input too)

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_roster_loader.py`
*   🙋 **Manual:** `crewsim roster summary --base YUL --fleet A321neoLR --position FO`
    *   **Expect:** **112** crew rostered from an establishment of **120** — 8 excluded, with reasons listed
    *   **Fails if:** 120 load — non-ACTIVE statuses are being counted as available, overstating the
    *   draft pool by 7% and pushing the recommended reserve level down

---

## ⏳ [TODO] S1b-02 — Headcount conservation
**Size:** `M` | **Depends on:** S1b-01 | **Spec:** §5.10, §7.5

**As a** planner **I want** reserves carved *out* of the roster, not added to it
**so that** a reserve has a real opportunity cost.

### Acceptance Criteria
- [ ] `line_holders + reserves == roster_size` for every candidate R — asserted, not assumed
- [ ] The flying those reserve bidders would have flown enters open time (or is absorbed per config)
- [ ] Reserve bidders selected by the configured bid rule, not arbitrarily

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_headcount.py`
*   🙋 **Manual:** `crewsim roster summary --policy R10 --show-split`
    *   **Expect:** line holders + reserves = `roster_size` exactly, at every R
    *   **Fails if:** the total grows with R — reserves are being minted, as in v2
    *   > This corrects the recommended **level**, not the shape of the cost curve. The curve is already
    *   > U-shaped once staffing is booked correctly (S1a-04); what is missing without this is the opportunity
    *   > cost of the line a reserve is not flying.

---

## ⏳ [TODO] S1b-03 — Reserve lines with rotation and SC/LC split
**Size:** `M` | **Depends on:** S1b-02 | **Spec:** §5.0.2, §5.5, §4.5

**As a** planner **I want** reserve lines to follow rotational rules and Short-Call/Long-Call splits
**so that** I model realistic reserve availability instead of uniform pools.

### Acceptance Criteria
- [ ] Reserve blocks follow an on/off rotation from D2 — **not** one flat horizon-long block
- [ ] Short-call and long-call are distinct, carried through from `d2_rosters.reserve_call_type`
- [ ] Reserve availability is a property of the *individual and the window*, not a scalar count

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_reserve_lines.py`
*   🙋 **Manual:** `crewsim roster reserve-pattern --policy R10`
    *   **Expect:** visible on/off rotation; SC/LC split roughly 60/40
    *   **Fails if:** every reserve is on call every day — eligibility will read ~100% instead of ~30%,
    *   and gate V3 cannot pass

---

## ⏳ [TODO] S1b-04 — Bind sick calls to roster crew  ·  fixes **D5**
**Size:** `M` | **Depends on:** S1b-01 | **Spec:** §5.0.4/E1, §5.2

**As a** modeller **I want** a sick call to remove a specific person
**so that** demand is a consequence of crew state rather than an independent stream.

### Acceptance Criteria
- [ ] Sick calls sample from crew who are **on or about to report for** duty
- [ ] The absent crew member is removed for the sampled duration; multi-day absences break several pairings
- [ ] Their pairing(s) become open-time items with the correct deadline

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_sick_calls.py`
*   🙋 **Manual:** `crewsim explain-event --scenario 0 --event SICK_CALL --first`
    *   **Expect:** a named crew member removed from the pool, and their pairing appearing as open time
    *   **Fails if:** open time appears with nobody removed — demand is still exogenous, which undercuts
    *   the whole emergence claim

---

## ⏳ [TODO] S1b-05 — Events E6 DUTY_END and E7 REST_END  ·  fixes **D4**
**Size:** `M` | **Depends on:** S1b-03 | **Spec:** §5.0.3, §5.0.4

**As a** modeller **I want** duties and rest periods to explicitly end on schedule
**so that** crews are returned to availability correctly.

### Acceptance Criteria
- [ ] Duty closes at E6; REST inserted per L2; rolling counters updated
- [ ] At E7 the crew member becomes assignable again; a reserve's remaining on-call window is **restored**
- [ ] Assignment **splits** a reserve block around duty + rest — never deletes it

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_events.py -k "duty_end or rest_end"`
*   🙋 **Manual:** `crewsim explain-crew --crew R001 --scenario 0 --timeline`
    *   **Expect:** `RESERVE → duty → REST → RESERVE` — back on call the next day
    *   **Fails if:** the reserve disappears after one use, or is bookable again during rest

---

## ⏳ [TODO] S1b-06 — Event E8 UNCOVERED_DEADLINE
**Size:** `M` | **Depends on:** S1b-05 | **Spec:** §5.0.3, §5.0.4

**As a** modeller **I want** open items held to their deadline
**so that** a reserve who frees up late can still rescue a flight.

### Acceptance Criteria
- [ ] An uncoverable item is **held**, not cancelled on the spot; the pipeline retries as state changes
- [ ] Cancellation and APPR compensation book at the deadline
- [ ] Deadline is configurable and may vary by route type — see `QUESTIONS_TO_ASK.md` §1.6

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_events.py -k deadline`
*   🙋 **Manual:** `crewsim explain-event --scenario 0 --event UNCOVERED_DEADLINE --first`
    *   **Expect:** the item held to its deadline, with at least one retry visible in the trace
    *   **Fails if:** cancellation is booked at the moment of failure — rescues become impossible and
    *   cancellations are overstated

---

## ⏳ [TODO] S1b-07 — V2 Erlang-B sanity bound  ·  **gate V2**
**Size:** `M` | **Depends on:** S1b-06 | **Spec:** §7.8, §9.2

**As a** reviewer **I want** the queueing behaviour checked against a closed-form result
**so that** a machinery bug is caught before any validation gate is attempted.

### Acceptance Criteria
- [ ] Single base, single fleet, cascades disabled, eligibility-thinned Poisson arrivals
- [ ] DES shortfall probability compared against `B(s, a)`; both printed side by side
- [ ] Runs in CI — this is the cheapest possible check that the machinery works at all

### Verification
*   🤖 **Automated:** `pytest tests/gates/test_v2_erlang.py`
*   🙋 **Manual:** `crewsim gate v2 --show-comparison`
    *   **Expect:** DES shortfall inside the Erlang-B confidence interval, shown next to it
    *   **Fails if:** they differ by more than the CI — reserve accounting has a bug; stop and fix it
    *   before attempting V3
    *   ## What to look at once this slice passes
    *   Re-run the reserve sweep. Two things should now be true that were not before:
    *   - `roster_size` stops being inert. Before headcount conservation it made no difference at all — argmin
    *   E[C] sat at R=6 for 100, 120 and 140 — because senior-first drafting only ever reached the top ~21 of
    *   the seniority list.
    *   - The eligibility rate should fall from ~0.8 toward the ~0.3 target, because reserve lines now rotate
    *   and L8 will bind in 1c.
    *   Neither is a gate here. Both are observations that tell you whether 1c is worth starting.

