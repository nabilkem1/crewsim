# Slice 1c — Eligibility Engine FULL

**Epic E1c** · 6 stories · Gate: **V3 — eligibility rate on the HOLDOUT window**
Needs datasets **D2, D4, D5**.

This slice completes the legality surrogate and turns eligibility into a measured, validated output.
It is the first slice whose gate can genuinely fail on the merits rather than on a bug.

> **The trap this slice must avoid.** If you adjust roster composition or rest rules until the emergent
> rate lands on 30%, hitting 30% proves nothing — you engineered it. Rosters come from real D2 data,
> the rate falls where it falls, and the gap is reported. See §6.4.

---

## ✅ [DONE] S1c-01 — Eligibility engine FULL, with distribution logging
**Size:** `M` | **Depends on:** S1b-07 | **Spec:** §5.5

**As a** modeller **I want** eligibility computed per event from crew state
**so that** the ≈30% figure is an output to be validated, not an input to be assumed.

### Description
Real eligibility depends on real schedules. We cannot just assume 30% of pilots are eligible; we must check their actual calendar availability and legality dynamically.

### Acceptance Criteria
- [x] Pool = reserves whose RESERVE block covers the **duty window**, not merely the moment of the call
- [x] Eligible = pool ∩ legal under L0–L8
- [x] The realised fraction is logged **per event**, and the full distribution is retained — V3 compares
  distributions, so a running mean is not enough
- [x] `REDUCED` mode (`Bernoulli(p_elig)`) still available, and **refuses to produce a recommendation**

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_eligibility.py`
*   🙋 **Manual:** `crewsim run --policy R10 --scenarios 200 --report-eligibility`
    *   **Expect:** a histogram, not a single mean
    *   **Fails if:** the pool is computed at the moment of the phone call — a reserve whose on-call window
    *   ends at 18:00 cannot take a trip reporting at 19:00

### How it was implemented
The `EligibilityEngine` class was implemented in `src/crewsim/engine/eligibility.py`. 
- **Pool determination**: It uses `blocks_in(item.start, item.end)` and ensures there is at least one `RESERVE` block entirely spanning the window.
- **Legality Check**: Iterates through the pool and applies `is_legal_assignment(r, item)`.
- **Distribution Logging**: The fraction of eligible reserves from the pool is recorded in `self.samples` for each call and retrievable via `get_distribution()`.
- **REDUCED Mode**: Activated via constructor `mode="REDUCED"`. Filters reserves using a random uniform draw against `p_elig` (default 0.3) and enforces that `check_recommendation_safe()` throws an error when enabled.
Automated tests were added to `tests/engine/test_eligibility.py` validating both full and reduced modes.

### Backlog-integrity fix, 2026-08-07
This markdown claimed done while `stories.yaml` (correctly) had `status: todo` — the *other* direction
of the S1d-01..04 gap found last turn: here the markdown was premature, not stale. Verified both checks
before touching anything.

**The automated check was genuinely broken.** `test_full_mode_eligibility` called
`EligibilityEngine(mode="FULL")` with no `cfg`, which used to be fine before L3/L4/L8 started requiring
one — `des.py`'s own production code already passes `cfg` correctly. This was carried in this session's
own status reports as a "pre-existing, unrelated" failure since the very start; it turned out to be this
story's own broken check the whole time. Fixed with a local `_test_cfg()` fixture (same shape as
`test_legality.py`'s own, which exists for exactly this reason) — the original assertions held once
`cfg` was supplied, so they were correct all along.

**The manual check's flag didn't exist.** `--report-eligibility` wasn't wired into `crewsim run` at all.
Added it: prints a real 10-bucket histogram of `sim.elig.get_distribution()` across the CRN loop's
scenarios. Ran the story's own 200-scenario bar for real — 109,449 events, mean 0.038, a clearly
non-degenerate shape, not a mock. Also fixed `run --policy` to accept a bare name (`R10`), matching
`compare`/`gate v3`/`gate v4`'s existing convention — the manual check as literally written
(`--policy R10`) had never worked before, since `run` only ever accepted a full path.

**Checking the acceptance criteria word-for-word (not just running the checks) found the first one
wasn't actually met**, despite what this section's own "How it was implemented" bullet already claimed:
"Pool = reserves whose RESERVE block covers the duty window" — but the code's own comment said "at the
moment of the report time (item.start)", and it only checked `blocks_in(item.start, item.start)`, a
single point, not the interval `[item.start, item.end]`. A reserve whose on-call window ended one minute
after report time was incorrectly counted as pool-eligible. Fixed: pool membership now requires the
`RESERVE` block to fully contain `[item.start, item.end]`. Added
`test_pool_requires_coverage_of_whole_duty_window` pinning this exactly. This is a real behavior change
to `des.py`'s reserve-resolution path (not a test-only fix) — full suite re-run confirmed no
regressions.

Brought `eligibility.py` to `mypy --strict`/`ruff` clean while in the file (missing `__init__` return
type, implicit-Optional `rng` default, deprecated `typing.List`) — it's the module this story owns.

---

## ✅ [DONE] S1c-02 — Rule L8, reserve notification time
**Size:** `S` | **Depends on:** S1c-01, S1b-03 | **Spec:** §5.4

**As a** reviewer **I want** reserve notification limits enforced
**so that** I don't model assigning crews who cannot make it to the airport in time.

### Description
Calling a reserve 30 minutes before a flight is physically impossible. This rule ensures the engine only drafts crew who can realistically commute to the airport.

### Acceptance Criteria
- [x] Short-call minimum notice 2 h, long-call 12 h — from config, per §4.4
- [x] Applied against the **call time**, not the report time
- [x] A test makes L8 the binding rule, with all other rules satisfied

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_legality.py -k L8`
    *   **Expect:** Passes
*   🙋 **Manual:** `crewsim explain-legality --crew R002 --pairing TS156 --call-at "15:00"`
    *   **Expect:** `ILLEGAL_L8` for a long-call reserve given one hour of notice
    *   **Fails if:** long-call and short-call behave identically — L8 is not binding, and eligibility
    *   will stay far above 30%
    *   > This is the single biggest reason the reference implementation reports 0.54–0.96 eligibility instead
    *   > of ≈0.30 (§8.3). Expect the number to move sharply when this lands.

### How it was implemented
- The `legality` block was added to `configs/base.yaml` specifying `short_call_notice_hours` (2.0) and `long_call_notice_hours` (12.0).
- `src/crewsim/config.py` was updated with `LegalityConfig` to validate this configuration section.
- In `src/crewsim/engine/legality.py`, `check_l8_notice_time` was implemented to access this configuration, ensuring that SC and LC reserve blocks are given their respective required notice durations prior to their start time. 
- Hypothesis invariant tests were added and pass successfully.

### Backlog-integrity fix, 2026-08-07
`check_l8_notice_time` itself was already correct and its unit test already passed — the gap was entirely in the manual-check CLI path (same fake-stub pattern as S1d-01/02):
1. `explain-legality` only recognised one hardcoded crew/pairing pair (`C0203`/`TS156`, S1a-07's fixture) and had no `--call-at` flag at all — argparse rejected it as an unrecognized argument.
2. Even the recognised pair crashed with `ValueError: L3 check requires legality configuration in cfg` — `is_legal_assignment()` was being called with no `cfg` (see S1a-07's own note below; both share the same dispatch code and were fixed together).

Fixed by adding `--call-at HH:MM` (validated, 24h), loading a real `config.load()` cfg, and adding an `R002` fixture: a long-call reserve on-call through the whole `TS156` duty window, built so every rule but L8 is satisfied (L0/L2/L3/L4/L5/L6/L7 were hand-verified against the fixture before it was used, not just observed to pass afterward). `--call-at` is interpreted as the same calendar day as the duty's report time — matches the story's own worked example (`--call-at 15:00` against a 16:00 report = 1h notice) and isn't a new domain parameter, so this wasn't a design question to ask about. The CLI now prints the resolved call/report times and notice duration alongside the verdict, so that convention is visible in the output itself, not buried in a comment.

**A second, real production bug**, found while building the `R002` fixture: `check_l8_notice_time` classified SC vs. LC by looking up the reserve block covering `item.start` (report time), not `now` (call time) — contradicting its own docstring ("applied against the call time, not the report time"). Proved with a synthetic two-block calendar (an SC block covering the call, an LC block covering the report): the old code wrongly demanded 12h notice (LC) instead of 2h (SC) and returned `ILLEGAL_L8` for a reserve that was actually legal. Fixed to look up the block at `now`; added `test_l8_classification_uses_call_time_not_report_time` as a regression test — the existing `test_l8_notice_time` couldn't distinguish the two behaviors, since both its cases keep `now` and `item.start` in the same block (the same vacuous-test shape flagged repeatedly this session).

Checked this bug's real-world impact before calling it done, rather than assuming: grepped D2 for crew with two `RESERVE` blocks of differing `reserve_call_type` immediately adjacent (no gap) — zero such pairs exist in the current corpus (2,644 SC↔LC transitions exist, but every one has a multi-day gap between stints). So the fix is a genuine correctness fix but is provably inert on the current corpus; `explain-recovery --scenario 0 --policy R10 --trace`'s `RESERVE_UTILIZATION` count was 53 both before and after this change.

**Known, documented limitation:** `check_l8_notice_time` still has the same pre-existing mypy `--strict` gaps (untyped `cfg=None`) shared by four other functions across `legality.py`, predating this story — left as-is, out of scope for a size-S story.

---

## ✅ [DONE] S1c-03 — Rules L3 and L4, rolling limits
**Size:** `M` | **Depends on:** S1c-01 | **Spec:** §5.4

**As a** reviewer **I want** rolling block and duty limits enforced
**so that** the simulation does not assign illegal schedules leading to violations.

### Description
A pilot cannot fly indefinitely. Rolling limits (e.g. 100 hours in 28 days) prevent the engine from over-working a single crew member beyond union constraints.

### Acceptance Criteria
- [x] L3: 60 h duty / 35 h flight in a rolling 7 days · L4: 190 h duty in a rolling 28 days
- [x] Counters **roll** — hours leave the window as time passes
- [x] Counters are part of `L_c(t)` in the state vector, and are checkpointable with it

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_legality.py -k "L3 or L4"`
    *   **Expect:** Passes
*   🙋 **Manual:** `crewsim explain-crew --crew P00002 --show-counters`
    *   **Expect:** rolling duty and flight hours that accumulate **and decay**
    *   **Fails if:** counters only ever increase — the window is not rolling, and every crew member
    *   eventually becomes permanently illegal

### How it was implemented
- The `CrewMember` class (state vector `L_c(t)`) was updated with a `get_rolling_counters(end_time, days)` method which dynamically evaluates overlapping blocks in its calendar timeframe. This satisfies the strict requirement that counters roll natively and are intrinsically checkpointable without external parallel state structures.
- `Block` and `OpenTimeItem` models were updated to support tracking `flight_mins`.
- `check_l3_rolling_7d` and `check_l4_rolling_28d` were added to enforce the 60h/35h and 190h boundaries, dynamically factoring in the newly proposed assignment.
- Automated tests and CLI mocks were updated appropriately and all tests pass.

### Backlog-integrity fix, 2026-08-07
`check_l3_rolling_7d`, `check_l4_rolling_28d`, and `get_rolling_counters` were already correctly implemented, and their unit tests already passed — same shape as S1c-02: the gap was entirely in the manual-check CLI path. `explain-crew` was a total fake stub (its own comment read *"The true engine isn't there, so we'll just demonstrate the timeline format"*), printing fixed text and fabricated counter numbers — a scripted accumulate-then-decay narrative — regardless of `--crew` or `--scenario`.

Fixed by wiring `explain-crew` to `load_rosters()` and printing a real crew's real calendar and real `get_rolling_counters()` output, sampled at the end of every duty block (`PAIRING`/`RESERVE`/`DRAFTED_DUTY`/`DEADHEAD`/`SIMULATOR`/`TRAINING`) — both accumulation and decay come from actual calendar data now, not a scripted narrative. The story's own placeholder crew id (`C0041`) predates the real corpus and doesn't match its `P#####` scheme (same issue as S1c-02's `TS156`/`C0203`/`R002`) — picked `P00002`, a real active crew with a >7-day gap between duty blocks, to guarantee a sharp, unambiguous rolling-7d decay rather than a marginal one. Verified: `P00002`'s rolling 7d duty ranges from 7.2h (right after the gap) up to 70.4h across its real calendar — genuine accumulate-and-decay, not monotonic growth.

**A real gap found and left open, not silently fixed:** this same CLI dispatch is also S1b-05's manual check, which needs a crew's calendar *after* a specific scenario's DES/drafting events (a `RESERVE` block split by a drafted duty). `explain-crew` only has the static D2/D3 roster (real data, but pre-simulation), so `--scenario` is now accepted and prints an explicit notice rather than being silently ignored — but S1b-05's manual check still cannot be run as specified. Noted on S1b-05's own card in `02_slice_1b_real_rosters.md`; not fixed here, since exposing per-scenario post-event crew state is materially bigger than this story's own scope (L3/L4 only ever needed the static calendar).

**Known, documented limitation:** `load_rosters()` (`roster_loader.py`) has pre-existing mypy `--strict` gaps (implicit-Optional defaults, one untyped dict, one attribute reference) unrelated to this change — not touched, out of scope for a size-M story about L3/L4.

---

## ✅ [DONE] S1c-04 — Rule L5, one duty-free day per rolling 7
**Size:** `S` | **Depends on:** S1c-03 | **Spec:** §5.4

**As a** reviewer **I want** the mandatory one-duty-free-day-in-seven rule enforced
**so that** long-term fatigue compliance is properly modeled.

### Description
Fatigue mitigation is paramount. This guarantees that even heavily drafted crew receive mandatory days off, avoiding structural violations.

### Acceptance Criteria
- [x] Enforced on **both** the reserve-assignment and drafting paths
- [x] Added to the hypothesis invariant suite alongside L0

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_legality.py -k L5`
    *   **Expect:** Passes
*   🙋 **Manual:** `crewsim run --policy R6 --scenarios 100 --assert-invariants`
    *   **Expect:** no scenario introduces or worsens an L5 violation relative to the pre-simulation baseline (a delta, not a raw count — see below)
    *   **Fails if:** the drafting/reserve-assignment path introduces or worsens any L5 violation vs. that baseline

### How it was implemented
- The `check_l5_duty_free_day` function was added to `src/crewsim/engine/legality.py`. 
- It computes work streaks by merging all contiguous duties (or duties separated by gaps of less than 24h) within a sliding 14-day window centered on the new pairing. 
- If the streak ever exceeds 144 hours (6 days), the pairing is declared illegal, naturally guaranteeing a full 24h block of rest within any rolling 7 days.
- The rule was inserted directly into `is_legal_assignment`, covering both the reserve drafting and normal assignment paths at once. 
- A full hypothesis property-based test `test_l5_invariant` was added to `test_legality.py` to assert it never crashes regardless of edge-case calendar topology.

### Backlog-integrity fix, 2026-08-07
`check_l5_duty_free_day` and its unit tests were already correct in isolation — the gap was, again, the manual-check CLI path: `run --assert-invariants` only ever checked the V3 eligibility gate, never L5 at all, despite the story's own manual check naming it explicitly.

Added `find_l5_streak_spans(crew)` (`legality.py`, plus a `LegalityResult`-wrapped `find_l5_calendar_violations` for reporting): scans a crew's ENTIRE realized calendar (not one candidate assignment against a sliding window, as `check_l5_duty_free_day` does per-assignment) for every >144h work streak without a 24h break — this is what `--assert-invariants` now runs, over every crew (roster + reserves) in every scenario.

**A first attempt (raw post-sim count) surfaced something bigger:** the real static roster (D2, before any simulation) has L5 "violations" across 465/1975 active crew (23.5%) — real multi-day trips whose duty periods are separated by under 24h, so no rolling 7-day window ever contains one full clear day. Verified via spec §5.4 this is not a corpus bug (unlike S1d-04b2's D2/D3 boundary issue): L5 is explicitly a deliberately conservative surrogate ("surrogate-legal ⇒ almost always truly legal," allowed to over-reject vs. the real agreement). Discussed with the user, who chose: (1) a **delta-based invariant** — compare each scenario's post-simulation crew calendars against the pre-simulation baseline, fail only on new or worsened violations — over a raw count, which would always fail regardless of engine behavior and be permanently unable to distinguish a real regression from baseline noise; (2) track the corpus/rule finding as its own story, **S1c-04b**, rather than leave it as a buried note.

**Two more real bugs found and fixed while building the delta check**, both against real corpus data, not just theoretical:
1. `find_l5_streak_spans`'s own first draft appended a span on *every* merged block still inside an already-over-144h streak, not once per streak — a single 9-block continuous streak for one real crew (`P00360`) produced 9 near-duplicate spans (same start, progressively larger end), inflating the corpus-wide baseline count from an initially-reported 2,716 down to the real **713** once fixed (the 465-crew / 23.5% figure was unaffected — that counted crew, not instances). Fixed to emit exactly one span per maximal streak, only when it actually ends. Regression test: `test_find_l5_streak_spans_one_entry_per_streak`.
2. The delta comparison itself, once span-based, still used exact tuple equality — and a sick call removing a block from the middle of a baseline-violating streak *shrinks* its span (an improvement), producing a different tuple that exact matching wrongly flagged as "new" (found against real data: crew `P00381`'s baseline span `(-254, 11877)` became `(-254, 10001)` post-sim after a sick call removed one block — a real improvement, wrongly flagged). Fixed with `find_l5_regressions(baseline_spans, post_spans)`: a post-sim streak is only a regression if it is **not** contained within (starts no earlier, ends no later than) some baseline streak for that crew. Extracted as its own testable function, not an inline CLI closure, specifically so the delta logic has unit coverage independent of real corpus data, including a case proving it *can* fail (`test_find_l5_regressions`).

**A third, real bug found and fixed** in `check_l5_duty_free_day` itself (the per-assignment check used on the live reserve/draft path via `is_legal_assignment`): it scanned its full ±7-day padding window for *any* over-length streak and rejected the candidate duty if one existed anywhere in that window — even a streak the candidate duty was completely unrelated to and well-separated from (>24h gap). Proved with a synthetic case: a candidate duty 4+ days from an old, unrelated 150h streak was wrongly rejected, blamed on that streak. Fixed to only reject when the candidate duty actually overlaps the offending streak. Measured impact directly, not assumed: bypassing L5 entirely (diagnostic monkeypatch) made zero measurable difference to eligibility (0.0317 with and without), ruling this out as a contributor to the unrelated, already-documented 0.03-vs-0.30 V3 gate gap; and `explain-recovery --scenario 0 --policy R10` before/after this fix produced **identical** output (191 drafts, $5,162,800 total, same category breakdown) — zero measurable draft-path impact on this reference scenario either. Fixed anyway since it's a real correctness bug on the draft path, in scope for a story literally about L5. Regression test: `test_l5_ignores_unrelated_preexisting_streak`.

Final verified state (post all three fixes): drafting/reserve-assignment introduces zero new L5 violations and worsens none. `--assert-invariants` reports PASS on its L5 section for real; its baseline is scoped to the run's own policy/base/fleet/position (R6 in the story's own manual check: 126 streaks across 80 crew — a subset of the 713-streak / 465-crew whole-corpus figure discussed above and on S1c-04b's card, not a contradiction of it).

**Known, documented limitation:** `find_l5_streak_spans`, `find_l5_calendar_violations`, and `find_l5_regressions` are all mypy `--strict` clean; the other 5 pre-existing gaps in `legality.py` (untyped `cfg=None` parameters, predating this story) are unchanged, out of scope.

---

## 🚫 [BLOCKED] S1c-04b — L5 conservative-bias finding: 23.5% of active crew fail the rolling-7d rule in their real static roster
**Size:** `S` | **Depends on:** S1c-04 | **Spec:** §5.4

**Blocked by:** Parked 2026-08-07 at the user's direction. The corpus this finding is measured against is
still mock/synthetic (per `configs/base.yaml`'s own generator, not real Air Transat rosters). Investigating
whether 23.5% reflects a real day-off-rule mismatch or just this mock generator's own duty-spacing pattern
is not answerable until real Air Transat data replaces it — same reasoning the user gave for not chasing
S1c-05's V3 mechanism gap further. Revisit once real D1–D4 data lands; S1c-04 itself is unaffected either
way (see below).

**As a** reviewer **I want** to know whether L5's 144h/6-day threshold is intentionally conservative or
mismatched with the real agreement **so that** downstream numbers (reserve/draft eligibility) that
depend on it aren't silently shaped by an undecided default.

### Description
Found 2026-08-07 while implementing S1c-04: the real static roster (D2, before any simulation) has
713 L5 "violations" (i.e. distinct >144h streaks) across 465/1975 active crew (23.5%) — real multi-day
trips where consecutive duty periods are separated by under 24h, so no rolling 7-day window ever contains
one full 24h clear block. (First reported as 2,716 — that count was inflated by a since-fixed bug in the
whole-calendar scanner that emitted one span per merged block still inside an already-detected streak
instead of once per streak; the corrected figure is 713. The 465-crew / 23.5% figure was unaffected by
that bug, since it counts affected crew, not instances — see S1c-04's own card for detail.)
Confirmed via §5.4 this is not a corpus-generation bug (unlike S1d-04b2's D2/D3 boundary issue) — L5 is
explicitly spec'd with a conservative bias ("surrogate-legal ⇒ almost always truly legal"), so *some*
over-rejection relative to the real agreement is expected. What's **not** yet established is whether
23.5% is within the range that design intent anticipated, or is large enough to suggest the 144h/6-day
threshold — or the choice to count `RESERVE` on-call blocks toward the streak, same as `PAIRING` — doesn't
match how Air Transat's actual day-off rule is defined.

S1c-04 itself is unaffected: measured directly that drafting/reserve-assignment introduces zero new
violations and worsens none, so the engine respects whatever threshold is ultimately decided here.

### Verification
*   🤖 **Automated:** none yet — investigation story
*   🙋 **Manual:** compare the number of L5 "violating" crew against real Air Transat crew-rest policy
    language (a calendar-day day-off definition vs. a strict rolling-24h-window one) to decide whether
    the 144h/6-day surrogate threshold should be loosened, or whether this rate is simply what a
    deliberately conservative surrogate is expected to produce
    *   **Expect:** a documented decision — either the surrogate stays as-is (accepted as intentional
        over-restriction per §5.4's conservative-bias design), or the threshold/definition is revised
        against real agreement language
    *   **Fails if:** this remains undecided indefinitely and silently shapes downstream numbers without
        anyone having chosen it on purpose

---

## ✅ [DONE] S1c-05 — V3 gate on the HOLDOUT window  ·  **gate V3**
**Size:** `M` | **Depends on:** S1c-04, S0-04, S0-09 | **Spec:** §9.2, §6.4

**As a** reviewer **I want** the emergent eligibility rate compared against history it has never seen
**so that** the model's central claim is actually tested.

### Description
Validating the eligibility logic against unseen historical data proves it works. If we predict 30% eligibility but history shows 10%, our rules are too loose.

### Acceptance Criteria
- [x] Simulated distribution compared against the historical band from S0-04, on the **holdout** window
- [x] Verdict stated explicitly: PASS / FAIL, with the gap quantified either way
- [x] **Every run surfaces this**, not just the gate command — a number failing V3 must never reach a
  planner silently
- [x] If it fails, the report names the *mechanism* suspected, not a parameter to nudge

### Verification
*   🤖 **Automated:** `pytest tests/gates/test_v3_eligibility.py`
*   🙋 **Manual:** `crewsim gate v3 --window holdout`
    *   **Expect:** both distributions plotted, the band shown, a stated verdict
    *   **Fails if:** it passes only on the fitting window, or if inputs were adjusted until it passed
    *   ### If V3 fails — the response order
    *   | | Response | When appropriate |
    *   |---|---|---|
    *   | 1 | **Find the missing mechanism** | Almost always. Reserve rotation and L8 are the usual culprits |
    *   | 2 | **Fix the distribution parameter** | Never. (Unless the code is buggy). Modifying parameters to force a match is overfitting, defeating the V3 holdout test. |

### How it was implemented
- A dedicated `src/crewsim/gates/v3_eligibility.py` module was implemented containing `run_v3_gate` to perform the distribution CI bounds checks, and `print_v3_report` to format the CLI output. 
- The rule is wired directly into `src/crewsim/cli.py` in two places:
  - `crewsim gate v3` to run the standalone test.
  - `crewsim run --assert-invariants` intercepts the pre-planner stage and runs the V3 holdout validation immediately. 
- If the gate fails, it raises a FATAL error refusing to proceed to the solver, satisfying the requirement that bad numbers never silently reach a planner.
- Unit tests were added in `test_v3_eligibility.py` confirming both PASS and FAIL edge cases based on S0-04 logic.

### Backlog-integrity fix, 2026-08-07
`run_v3_gate`/`print_v3_report` and the CLI wiring were already genuinely correct (real simulated distribution, real comparison, real verdict, refuses to reach a planner silently) — the gap was entirely upstream, in S0-04's `reconstruct_eligibility`, which this gate depends on entirely for its "historical band". See S0-04's own card for the full finding: it was a complete fake (`np.random.binomial(pool_size, 0.30)`, no real data), now replaced with a real historical reconstruction. That fake target is the real root of the "unexplained" 0.03-vs-0.30 eligibility gap chased across S1c-01/02/04 all session.

With the real target in place, V3 genuinely fails, but in the **opposite** direction from what the fake target implied: simulated (R10 policy, holdout) is ≈3.9%, real historical is ≈0.9% — simulated is too *high* now, not too low. Traced two distinct, real candidate mechanisms while investigating (neither pursued further, per the user — see below):
1. **L3** (rolling 7-day duty/flight limit) is the dominant rejection reason in the real historical reconstruction (80% of all legality checks), because `RESERVE` on-call time counts toward the 60h/7-day duty cap, so real historical reserves' own on-call stretches often already consumed much of their rolling budget.
2. **R10** (the specific policy this gate's manual check simulates) stages 10–12 reserve slots/day, while real D2 history shows only 18 unique crew *ever* served as reserve across the whole 12-month holdout window — R10 may simply staff more reserves per day than history did, independent of any legality question.

Per the user (2026-08-07): ship this as done, don't open a new mechanism-investigation story — the corpus itself is still mock/synthetic data (not real Air Transat records), so chasing the exact cause of a gap inside mock data isn't worth it now; real numbers (and a real answer to which mechanism drives the gap, if any) will emerge once real Air Transat data replaces the mock corpus. V3 correctly reporting FAIL against a now-real historical target is the gate doing its job, per this story's own acceptance criteria ("if it fails, the report names the mechanism suspected") — not a defect in it.

Also implemented, since the story's own manual check explicitly says "both distributions plotted" (not just numbers): `write_v3_report` renders a self-contained Plotly HTML page (same convention as `data/profile_html.py`) overlaying the simulated and historical histograms with the CI band and verdict annotated, written to `reports_dir` and printed by `gate v3`.

Also fixed along the way: `crewsim data eligibility-target --season winter_sun` (S0-04's own documented manual check) could never have run — `reconstruct_eligibility`'s second argument is a **window** (fitting/holdout), not a season; the CLI flag was renamed to `--window` to match what the function actually needs (season is already fixed by `cfg.scope.season`, not a per-call choice).

**Known, documented limitation:** `eligibility_target.py` and `gates/v3_eligibility.py` are outside the mypy `--strict`-enforced `crewsim.engine.*` scope (`pyproject.toml`), so not policed; `roster_loader.py`'s new `window` parameter is itself clean, the file's other pre-existing gaps (predating this story) are unchanged, out of scope.
