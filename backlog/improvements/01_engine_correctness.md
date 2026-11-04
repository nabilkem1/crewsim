# IMP-E1 — Engine Correctness

**5 stories** · **Must fix** · Gate: all V1–V9 re-run green after the epic, with before/after
E[C], CVaR95 and R* recorded.
The remaining engine stories (IMP-106 to IMP-115) are in [low_risk/05_engine_correctness.md](low_risk/05_engine_correctness.md).

The simulation either generates events at the wrong time or allows calendars that a real crew member
could not legally fly. Each defect biases cost and coverage, mostly towards looking **cheaper and
better covered** than reality. That is the dangerous direction for a reserve-sizing recommendation.

> **Epic gate still open:** the code and automated tests are done. The V1–V9 re-run, with
> before/after E[C], CVaR95 and R*, has not been recorded yet. These fixes change simulated costs.

---

## [DONE] IMP-101 — Process sick calls within a day in time order
**Size:** `S` | **Depends on:** — | **Source:** `engine/des.py:358-362`

**As a** planner **I want** sick calls to arrive at the times the model draws
**so that** coverage and cancellation reflect the real intraday arrival pattern.

### Problem
Each arrival `i` draws `current_time = day_start + U(0,1440)`. If a later `i` draws an earlier time,
the `timeout` is skipped. The arrival is then processed at `env.now` while carrying the earlier
timestamp. Arrivals bunch late in the day, and ABSENCE blocks start in the past.

### Acceptance Criteria
- [x] All arrival times for a day are drawn first, then processed in ascending order
- [x] Every arrival is processed at exactly its drawn time (`env.now == current_time`)
- [x] CRN is preserved: the draws for `(day, i)` stay independent of the other arrivals' values (per-arrival `event_rng` is kept)
- [x] No ABSENCE block starts before the simulation time at which it was inserted (follows from the previous point: the absence starts at `current_time == env.now`)
- [x] Regression test (implemented on a real scenario rather than 2 forced arrivals): the sequence of applied times is non-decreasing, and each equals `env.now`

### Verification
*   **Automated:** `pytest tests/engine/test_crn_pairing.py -k intraday_order` (fails on the old code, passes on the new)
*   **Manual:** `crewsim explain-event --scenario 0 --event SICK_CALL --policy R10`
    *   **Expect:** within each day, the listed sick-call times are strictly increasing
    *   **Fails if:** any sick call is shown at a time earlier than the one before it on the same day

### How it was implemented
- `Simulation.sick_call_source` builds `(time, i, rng)` for each arrival of the day, sorts by `(time, i)`, then processes them in that order.
- Each arrival still uses its own `crn.event_rng(stream, "sick_call:{day}:{i}")`, with draws in the same order (time, duration, crew), so the arrival times are unchanged and only the processing order moves.

---

## [DONE] IMP-102 — Reserve duties record their flight minutes
**Size:** `S` | **Depends on:** — | **Source:** `engine/events.py:73`, `engine/state.py:148-150`

**As a** planner **I want** a reserve's flown duties to count towards their flight-time limits
**so that** reserves are not used past the L3 7-day flight limit.

### Problem
`assign_reserve` creates the `DRAFTED_DUTY` block without `flight_mins`. The draft path sets it
(`cascade.py:24`), but the reserve path does not.

### Acceptance Criteria
- [x] `assign_reserve` copies `item.flight_mins` (or equivalent) onto the DRAFTED_DUTY block, as the draft path does
- [x] `get_rolling_counters` reports the flight minutes for a reserve after an assignment
- [x] Regression test: a reserve near the 7-day flight limit becomes ineligible after one covered trip

### Verification
*   **Automated:** `pytest tests/engine/test_events.py -k flight`
*   **Manual:** `crewsim explain-crew --scenario 0 --policy R10 --crew <a reserve that flew> --show-counters`
    *   **Expect:** the 7-day flight counter is greater than 0 after the covered duty
    *   **Fails if:** the duty counter rises but the flight counter stays at 0

### How it was implemented
- `assign_reserve(..., flight_mins=0.0)` takes a new keyword argument and stores it on the DRAFTED_DUTY block.
- Both callers pass `item.flight_mins`: the local reserve path (`_attempt_resolution`) and the cross-base path (`_dispatch_cross_base`).

---

## [DONE] IMP-103 — Drafting a crew member out of training or simulator removes that block
**Size:** `S` | **Depends on:** — | **Source:** `engine/cascade.py:49-79`, `engine/legality.py:24-31`, `engine/drafting.py:56-57`

**As a** planner **I want** a crew member drafted from TRAINING or SIMULATOR to lose that block
**so that** their calendar never holds two overlapping duties and the rolling counters are not double-counted.

### Acceptance Criteria
- [x] `compute_draft_delta` lists overlapping TRAINING and SIMULATOR blocks in `removed_blocks` for tier 3 and tier 5 drafts
- [x] After `apply_delta`, `find_l0_violations` reports no duty/duty overlap for the drafted crew
- [x] The training-reschedule fee is still booked exactly once (`draft_cost` is unchanged)
- [x] Regression test covering both TRAINING (tier 3) and SIMULATOR (tier 5)

### Verification
*   **Automated:** `pytest tests/engine/test_cascade.py -k training`
*   **Manual:** `crewsim run --policy R6 --scenarios 5 --assert-invariants`
    *   **Expect:** invariants pass with zero L0 duty-overlap violations
    *   **Fails if:** any DRAFTED_DUTY overlaps a TRAINING or SIMULATOR block

### How it was implemented
- `compute_draft_delta` also removes TRAINING and SIMULATOR blocks that overlap `[item.start, item.end + rest)`. This is the same window `determine_tier` uses.
- The whole session goes, because it is rescheduled outside the model. No open item is created.

---

## [DONE] IMP-104 — Line holders cannot be drafted part-way through a trip, or without notice
**Size:** `M` | **Depends on:** SME answer (see README) | **Source:** `engine/legality.py:13-22,128,186-196`

**As a** planner **I want** drafting to respect what a line holder is already doing
**so that** we never "draft" someone off an aircraft they are currently flying.

### Problem
- L0 ignores PAIRING blocks.
- L2 only considers duties with `end <= item.start`.
- L8 notice only applies to reserves.

So a crew member whose pairing started before `now` can be drafted, and the pairing they are flying is broken into an item that is already late.

### Acceptance Criteria
- [x] A crew member with a PAIRING where `start <= now < end` is not a draft candidate (when that pairing overlaps the draft's duty+rest window)
- [x] A minimum line-holder notice period is read from `configs/base.yaml` (no literal), and enforced as an extension of L8
- [x] `[CONFIRM: …]` marker on the notice value until the SME confirms it
- [x] Regression tests: one for in-progress exclusion, one for the notice boundary (exactly at the minimum notice is legal)

### Verification
*   **Automated:** `pytest tests/engine/test_legality.py -k "in_progress or line_notice"` and `pytest tests/engine/test_des.py -k reopens_flying`
*   **Manual:** `crewsim explain-recovery --scenario 0 --policy R6 --trace`
    *   **Expect:** no draft line names a crew member whose pairing has already started
    *   **Fails if:** a CASCADE item is created whose report time is already in the past at creation

### How it was implemented
- New `check_l0_pairing_in_progress(crew, start, end, now)`, run inside `is_legal_assignment` right after L0. It fails `ILLEGAL_L0` if the duty+rest window overlaps a pairing already under way at the call.
- New config key `legality.line_holder_draft_notice_hours`:
  - Required field in `LegalityConfig`.
  - Set to `0.0 # [CONFIRM: Crew Planning]` in `base.yaml`. 0.0 keeps the AUD-10 decision of no invented floor.
  - L8 now applies it to anyone not on reserve at the call. Even at 0.0, a call after the report time is illegal.
- **Open:** the real notice value still needs the SME answer. Change it in `base.yaml` only, no code.

---

## [DONE] IMP-105 — Sick calls do not reopen pairings that are already under way
**Size:** `S` | **Depends on:** IMP-101 | **Source:** `engine/sick_calls.py:47,103-108,149-151`

**As a** planner **I want** a sick call to break only future duty
**so that** we don't create open items that are already past their deadline.

### Acceptance Criteria
- [x] `apply_sick_call` only breaks PAIRING blocks with `start >= current_time`
- [x] A pairing in progress at the time of the sick call is handled as a documented rule: the crew member **completes** the duty in progress, and the absence removes them from everything that starts later
- [x] Every generated sick-call and cascade item has `start >= creation time` (asserted by a test on a real scenario). *Amended from "deadline ≥ creation": with a non-zero `uncovered_deadline_hours`, a sick call shortly before report legitimately produces a deadline that has already passed, so start time is the right invariant.*
- [x] The comment at `sick_calls.py:149-151` matches the behaviour

### Verification
*   **Automated:** `pytest tests/engine/test_sick_calls.py -k in_progress` and `pytest tests/engine/test_des.py -k reopens_flying` (fails on the old code)
*   **Manual:** `crewsim explain-event --scenario 0 --event SICK_CALL --first --policy R10`
    *   **Expect:** every item's start time is at or after the sick call's time
    *   **Fails if:** an item starts before the call

### How it was implemented
- Crew are candidates only if they have a PAIRING that starts at or after the call and inside the absence window. Only those pairings are broken.
- A crew member whose only pairing is already in progress is not selected.
- The invariant is enforced by a test, not yet by `run --assert-invariants`.
