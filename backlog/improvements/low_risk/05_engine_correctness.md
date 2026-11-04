# IMP-E1 — Engine Correctness

**10 stories** · **Low risk** (see [README](README.md) for each story's category) · Gate: all V1–V9
re-run green, with before/after E[C], CVaR95 and R* recorded.
The must-fix engine stories (IMP-101 to IMP-105) are in [../01_engine_correctness.md](../01_engine_correctness.md).

The simulation either generates events at the wrong time or allows calendars that a real crew member
could not legally fly. Each defect biases cost and coverage, mostly towards looking **cheaper and
better covered** than reality. That is the dangerous direction for a reserve-sizing recommendation.

---

## [TODO] IMP-106 — Rolling duty and flight limits look forward as well as backward
**Size:** `M` | **Depends on:** IMP-102 | **Source:** `engine/legality.py:221,246`, `engine/state.py:129`

**As a** planner **I want** L3 and L4 to reject an assignment that pushes later rostered duties over a limit
**so that** a legal-looking assignment today does not make next week illegal.

### Acceptance Criteria
- [ ] L3 (7-day) and L4 (28-day) check every rolling window that contains the new duty, not only the window ending at `item.start`
- [ ] The L5 approach (±window scan) is reused, not reimplemented
- [ ] Regression test: a duty that is legal looking backward but breaches the limit with the next rostered pairing is rejected

### Verification
*   **Automated:** `pytest tests/engine/test_legality.py -k forward_window`
*   **Manual:** `crewsim explain-legality --crew C0203 --pairing TS156`
    *   **Expect:** the L3/L4 lines state the window that was evaluated (start–end)
    *   **Fails if:** only a backward window is reported

---

## [TODO] IMP-107 — L2 rest considers duties that ended before minute 0
**Size:** `S` | **Depends on:** — | **Source:** `engine/legality.py:124-131`

**As a** planner **I want** rest to be checked against duties that ended just before the horizon starts
**so that** day-1 assignments respect rest.

### Acceptance Criteria
- [ ] `latest_duty_end` starts as `None` (or `-inf`), not `0.0`, and negative block times are considered
- [ ] Regression test: a duty ending at minute −60 makes an assignment at minute 300 illegal when the minimum rest is 10 h

### Verification
*   **Automated:** `pytest tests/engine/test_legality.py -k pre_horizon_rest`
*   **Manual:** n/a (boundary case). The automated test is the check.

---

## [TODO] IMP-108 — Cross-base reserves are never double-booked over their own pairings
**Size:** `M` | **Depends on:** — | **Source:** `engine/roster_loader.py:345-351`, `engine/events.py:55-60`, `engine/legality.py:13-22`

**As a** planner **I want** a cross-base reserve with rostered pairings to be handled consistently
**so that** a rescue never overlaps a trip they are already scheduled to fly.

### Acceptance Criteria
- [ ] Either (a) `assign_reserve` removes overlapping PAIRINGs and reopens them as items, as `compute_draft_delta` does, or (b) a reserve with any PAIRING overlapping `[duty_start, duty_end + rest)` is ineligible. The chosen option is documented in the story sign-off.
- [ ] No calendar ends with DRAFTED_DUTY or REST overlapping a PAIRING (new invariant)
- [ ] Regression test with a cross-base reserve whose later pairing falls inside the rest window

### Verification
*   **Automated:** `pytest tests/engine/test_positioning.py -k own_pairing`
*   **Manual:** `crewsim run --policy R6 --scenarios 5 --assert-invariants`
    *   **Expect:** the "duty over pairing" invariant reports 0
    *   **Fails if:** above 0

---

## [TODO] IMP-109 — REDUCED mode does not silently lose real broken pairings
**Size:** `S` | **Depends on:** — | **Source:** `engine/des.py:708-728`

**As a** modeller **I want** pairings removed by a draft in REDUCED mode to still produce an item or a cost
**so that** flying never disappears without a trace.

### Acceptance Criteria
- [ ] In REDUCED mode, either `apply_delta` does not remove the real pairings, or each removed pairing is accounted for (item or ledger row)
- [ ] Ledger invariant: total pairing minutes are conserved (assigned + open + cancelled = original) in both FULL and REDUCED modes

### Verification
*   **Automated:** `pytest tests/engine/test_des.py -k reduced_conservation`
*   **Manual:** n/a. Covered by the conservation invariant in `--assert-invariants`.

---

## [TODO] IMP-110 — Late items get one attempt and one eligibility sample
**Size:** `S` | **Depends on:** — | **Source:** `engine/des.py:487-504`, `engine/eligibility.py:145-147`

**As a** modeller **I want** each resolution attempt to be meaningful and each item sampled once
**so that** the V3 eligibility distribution is not weighted towards items that waited longest.

### Acceptance Criteria
- [ ] When `deadline <= now`, the pipeline cancels directly after the first failed attempt (no immediate identical retry)
- [ ] The eligible fraction is recorded **once per item** (first attempt), or the choice is configurable and documented
- [ ] The hold loop computes the next wake-up as a single `min()`, not a sort of the whole list

### Verification
*   **Automated:** `pytest tests/engine/test_eligibility.py -k one_sample_per_item`
*   **Manual:** `crewsim run --policy R10 --scenarios 5 --report-eligibility`
    *   **Expect:** number of eligibility samples ≤ number of open items
    *   **Fails if:** more samples than items

---

## [TODO] IMP-111 — Cross-base on-call minutes are excluded from the in-scope offered load
**Size:** `S` | **Depends on:** — | **Source:** `engine/des.py:265-270,586`

**As a** validator **I want** the V2 offered load to count only in-scope reserves
**so that** the Erlang-B comparison uses the right server count.

### Acceptance Criteria
- [ ] `_dispatch_cross_base` books its on-call minutes to a separate counter, not `reserve_oncall_minutes`
- [ ] V2 output shows both figures separately

### Verification
*   **Automated:** `pytest tests/gates/test_v2_erlang.py -k cross_base`
*   **Manual:** `crewsim gate v2`
    *   **Expect:** in-scope and cross-base on-call minutes reported on separate lines
    *   **Fails if:** a single combined figure

---

## [TODO] IMP-112 — Configuration rejects a visibility lag shorter than the cancellation lead
**Size:** `S` | **Depends on:** — | **Source:** `engine/des.py:767,889`, `config.py`

**As a** modeller **I want** an invalid combination of lags to fail at load time
**so that** delayed items are never cancelled the moment they become visible.

### Acceptance Criteria
- [ ] Pydantic validator: `visibility_lag_hours >= uncovered_deadline_hours`, with a message naming both keys
- [ ] The visible-at calculation exists in one helper (removes the duplication at `des.py:767`/`889`)

### Verification
*   **Automated:** `pytest tests/test_config.py -k visibility_lag`
*   **Manual:** temporarily set the lag below the lead in a copy of `base.yaml`, then run `crewsim config show`
    *   **Expect:** a validation error naming both keys
    *   **Fails if:** it loads

---

## [TODO] IMP-113 — An absent crew member's drafted or reserve duties are reopened
**Size:** `M` | **Depends on:** IMP-105 | **Source:** `engine/sick_calls.py:37-38,106`

**As a** planner **I want** a sick crew member to lose every duty in the absence window, not only original pairings
**so that** reserve sickness and drafted-crew sickness reduce capacity as they do in reality.

### Acceptance Criteria
- [ ] `_break_pairings` also reopens DRAFTED_DUTY blocks (as CASCADE or SICK_CALL items) and removes RESERVE blocks inside the absence
- [ ] Reserves are eligible to call sick (the selection pool includes them), behind a config flag defaulting to on
- [ ] Regression test: a reserve who calls sick is not assigned during the absence

### Verification
*   **Automated:** `pytest tests/engine/test_sick_calls.py -k "drafted or reserve_sick"`
*   **Manual:** `crewsim explain-event --scenario 0 --event SICK_CALL --first --policy R10`
    *   **Expect:** if the sick crew member held a drafted duty, it appears as a new open item
    *   **Fails if:** an ABSENCE block overlaps a DRAFTED_DUTY on the same calendar

---

## [TODO] IMP-114 — Multi-day pairings are broken as a whole
**Size:** `M` | **Depends on:** SME answer (see README) | **Source:** `engine/roster_loader.py:197-207`, `engine/sick_calls.py:105`, `engine/cascade.py:46`

**As a** planner **I want** a broken pairing to reopen all its remaining duty periods
**so that** a crew member is not left down-route on the rest of a trip they no longer operate.

### Acceptance Criteria
- [ ] Breaking any duty period of a `pairing_id` reopens all of that pairing's future duty periods as one item (or linked items with one `root_event_uid`)
- [ ] No two open items share a `pairing_id` and an overlapping time range
- [ ] Rule and SME confirmation recorded in the story sign-off

### Verification
*   **Automated:** `pytest tests/engine/test_cascade.py -k multi_day`
*   **Manual:** `crewsim explain-recovery --scenario 0 --policy R6 --trace`
    *   **Expect:** a broken 3-day pairing appears as one item spanning 3 days
    *   **Fails if:** only the overlapping day appears

---

## [TODO] IMP-115 — CRN keys are independent of the policy
**Size:** `M` | **Depends on:** — | **Source:** `engine/des.py:376,408,764,801,655`, `engine/sick_calls.py:113`, `engine/eligibility.py:136`

**As a** researcher **I want** "the same scenario" to mean the same random events under every policy
**so that** paired policy differences have the variance reduction the method promises.

### Problem
- Item uids are offset by the number of displaced pairings, which depends on R.
- The sick crew member is picked by index into a list whose contents differ by policy.
- REDUCED eligibility shares one generator across a pool whose size depends on the policy.

### Acceptance Criteria
- [ ] Random keys use stable identifiers (`day`, `i`, `pairing_id`, `crew_id`), never run-dependent uids
- [ ] Sick crew selection is keyed on a policy-invariant ordering, such as sorted `crew_id`s over the full roster before carve-out
- [ ] REDUCED eligibility draws use `event_rng(stream, f"elig:{item_key}:{crew_id}")`
- [ ] Test: under R6 and R10, the first N sick calls have identical (time, crew_id, duration)

### Verification
*   **Automated:** `pytest tests/engine/test_crn_pairing.py -k policy_invariant`
*   **Manual:** `crewsim compare --policies R6 R10 --scenarios 20`
    *   **Expect:** the paired standard error is smaller than before this story (record both)
    *   **Fails if:** it is unchanged or larger
