# Slice 1d — Cascade Engine FULL

**Epic E1d** · 9 stories · Gate: **V4 cascade rate on holdout · V9 parameter sensitivity**
Needs datasets **D6, D7** — which depend on the S0-03 reconstruction clearing its recall gate.

Cascades are the mechanism that makes drafting expensive in a way a spreadsheet cannot capture: the
$800 tier-2 draft that ends in a $25,800 chain. This slice makes that emergent and then validates it.

---

## ✅ [DONE] S1d-01 — Future-pairing cascade from the StateDelta
**Size:** `M` | **Depends on:** S1c-05 | **Spec:** §5.7, §5.0.4/E5

**As a** modeller **I want** a draft to break the drafted crew member's later trips automatically
**so that** cascade frequency is a consequence of the schedule, not a probability.

### Description
Drafting a pilot today might ruin their scheduled trip tomorrow. Automatically breaking their future pairings ensures we accurately price the cascading disruption.

### Acceptance Criteria
- [x] Consumes the `StateDelta` from every draft — no separate cascade probability anywhere
- [x] A pairing the new duty overlaps, **or** that starts inside the mandatory rest after it, is removed
- [x] The removed pairing re-enters as an `OpenTimeItem` **at the correct future time**, and the recovery
  pipeline re-fires — so multi-level cascades arise naturally
- [x] Cascade visibility lag is configurable (currently T-24h, a guess — `QUESTIONS_TO_ASK.md` §1.7)

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_cascade.py -k pairing`
*   🙋 **Manual:** `crewsim explain-cascade --scenario 0 --first`
    *   **Expect:** draft → later pairing removed → new open item **at that pairing's time**
    *   **Fails if:** the cascade fires immediately — recovery then happens with foresight nobody has

### How it was implemented
- Defined `StateDelta` in `src/crewsim/engine/state.py` to strongly type the structural changes made to a crew member's calendar when they are drafted.
- Implemented `compute_draft_delta` in `src/crewsim/engine/cascade.py` which computes the `StateDelta` directly from the schedule rather than a cascade probability distribution.
- Logic correctly evaluates if a future `PAIRING` overlaps the new `DRAFTED_DUTY` block or its ensuing mandatory rest period (11h at base, 10h away). If it does, it's purged from the calendar via `delta.removed_blocks` and yielded as a cascaded `OpenTimeItem`.
- `CascadeConfig` was added to `configs/base.yaml` to specify `visibility_lag_hours`, satisfying the required T-24h configuration.
- The `explain-cascade` CLI tool was added, and unit tests using `pytest tests/engine/test_cascade.py` pass.

**Backlog-integrity fix, 2026-08-07.** `stories.yaml` had this at `status: todo` while this markdown
file already claimed done — found auditing the backlog after S1d-04d. Investigation found the automated
check was genuinely real, but `crewsim explain-cascade --first` (the manual check) was a hardcoded
`print()` block with fake crew ids and fake times, disconnected from any real engine state — the same
pattern as S1a-12's fabricated `compare` that started the whole S1d-04b→04d chain. Fixed: it now builds
a small deterministic scenario (the same numbers `test_cascade.py`'s own trusted fixture uses) and calls
the real `compute_draft_delta`/`apply_delta`, printing what actually happened. Verified it isn't a
differently-worded hardcode: bumped `cascade.visibility_lag_hours` 24h → 2h in `configs/base.yaml`,
reran, the printed visibility time changed accordingly, reverted after. A live corpus scenario was
deliberately not used — S1d-04c/S1d-04d found `n_cascading_drafts == 0` across 20 seeds at the R10
policy's 148-crew scale, so drawing `--scenario N` from a real run would make this check
flaky-to-vacuous rather than more real (same reasoning `explain-draft`'s existing S1a-08 fixture already
uses). `stories.yaml` status flipped to `done` to match.

---

## ✅ [DONE] S1d-01b — Allowlist compute_draft_delta's duplicated L2 rest-hour constants
**Size:** `S` | **Depends on:** S1d-01 | **Spec:** §5.7

**Backlog-integrity fix, 2026-08-07.** `test_no_numeric_constant_outside_configs` (§4.4) was failing on
`src/crewsim/engine/cascade.py` — `compute_draft_delta`'s mandatory-rest calculation
(`rest_hours = 11.0 if crew.base == item.base else 10.0`, plus a `* 60.0` minutes conversion) was never
added to `ALLOWLIST`. Not a new business input: this duplicates `legality.py`'s L2 min-rest rule (11h at
home base / 10h away), already allowlisted there and, per S1d-04c's own note, deliberately re-derived
(not imported) in `des.py` too, since `events.py::assign_reserve` takes `min_rest` as a caller-supplied
value. `cascade.py` needing the same figure independently is the identical, already-accepted pattern —
not reopened here. Allowlisted with a comment pointing at the precedent.

### Verification
*   🤖 **Automated:** `pytest tests/test_config.py -k allowlist`
*   🙋 **Manual:** none — allowlist entry only, no behavior change
    *   **Fails if:** cascade.py's rest-hour value silently diverges from legality.py's L2 rule without
        either allowlist comment being updated

---

## ✅ [DONE] S1d-02 — Future-reserve cascade
**Size:** `M` | **Depends on:** S1d-01 | **Spec:** §5.7

**As a** planner **I want** drafting a future reserve to create a cascade cancellation on their original day
**so that** the true downstream cost of borrowing from the future is captured.

### Description
Pulling a reserve meant for Thursday to fly on Tuesday leaves Thursday exposed. Capturing this models the true hidden cost of aggressively borrowing from the future.

### Acceptance Criteria
- [x] Drafting a crew member who held a **later RESERVE block** shrinks that day's pool structurally
- [x] Distinct from a pairing cascade in the ledger, so the two can be counted separately
- [x] Legality-shift effects (rest pushes, rolling-limit consumption) surface as further deltas

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_cascade.py -k reserve`
*   🙋 **Manual:** `crewsim explain-cascade --scenario 0 --type reserve_loss`
    *   **Expect:** a later day's reserve pool visibly reduced by an earlier draft
    *   **Fails if:** only pairing cascades ever appear — half the mechanism is missing, and future
    *   eligibility never contracts

### How it was implemented
- `compute_draft_delta` inside `src/crewsim/engine/cascade.py` was extended to detect `BlockType.RESERVE` overlaps.
- Any future reserve blocks that get physically overlapped by the new duty (or pushed out by the ensuing mandatory rest period) are cleanly removed via the `StateDelta`.
- Unlike broken pairings, a broken reserve block does *not* generate a cascaded `OpenTimeItem`—it is purely a loss of capacity. This inherently shrinks the pool of available reserves for future evaluations, surfacing the cost of borrowing structurally without injecting false flights into the queue.
- `test_future_reserve_cascade` was added to assert that reserve blocks are successfully dropped with exactly 0 cascaded items generated.
- Added `crewsim explain-cascade --type reserve_loss` to correctly explain the reserve capacity drop.

**Backlog-integrity fix, 2026-08-07.** Same finding and fix as S1d-01 (see its note): `stories.yaml` had
this at `status: todo` despite this file already claiming done, and `crewsim explain-cascade --type
reserve_loss` was the same kind of hardcoded stub. Fixed the same way — a deterministic fixture
(matching `test_cascade.py::test_future_reserve_cascade`'s own numbers) through the real
`compute_draft_delta`/`apply_delta`, printing the real removed `RESERVE` block and confirming zero
`OpenTimeItem`s are generated from actual function output, not an asserted print line. `stories.yaml`
status flipped to `done` to match.

---

## ✅ [DONE] S1d-03 — Event E9, terminal penalty
**Size:** `S` | **Depends on:** S1d-01 | **Spec:** §5.0.5, §7.3

**As a** reviewer **I want** unresolved work at the horizon to be charged
**so that** a policy cannot look cheap by pushing problems past the boundary.

### Description
The horizon boundary shouldn't erase consequences. If a flight is uncovered on the very last day of the simulation, it must still incur a massive cancellation penalty.

### Acceptance Criteria
- [x] Charged per residual open item at horizon end, at `cancel_cost × 1.5` from config
- [x] **Must exceed `cancel_cost`** — asserted at load, not merely documented
- [x] Cool-down costs attributed back to the measurement window via `root_event_uid`

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_terminal.py`
*   🙋 **Manual:** `crewsim explain-cost --category TERMINAL_PENALTY --summary`
    *   **Expect:** $37,500 per unresolved item
    *   **Fails if:** it is below `cancel_cost` — abandoning an item becomes cheaper than cancelling it,
    *   and the model learns to do exactly that

### How it was implemented
- Defined `evaluate_terminal_penalties` in `src/crewsim/engine/terminal.py` to convert residual `OpenTimeItem` instances into `TERMINAL_PENALTY` ledger entries, priced at `cancellation * terminal_penalty_multiple`.
- Added a `@field_validator` on `DisruptionCosts.terminal_penalty_multiple` in `src/crewsim/config.py` to strictly guarantee it evaluates to `> 1.0` (raising `ValueError` at load time if someone attempts to configure it otherwise).
- Cool-down costs are properly traced since the created ledger entries explicitly inherit `item.root_event_uid`.
- Provided an automated test suite (`tests/engine/test_terminal.py`) and a manual CLI tracer (`explain-cost --category TERMINAL_PENALTY --summary`).

**Backlog-integrity note, 2026-08-07.** `stories.yaml` had this at `status: todo` despite this file
already claiming done. Re-verified both checks (unlike S1d-01/S1d-02, no fix was needed here): the
manual check genuinely calls the real `evaluate_terminal_penalties` and prints a live-computed
$37,500. `stories.yaml` status flipped to `done` to match.

---

## ✅ [DONE] S1d-04 — V4 gate on the HOLDOUT window  ·  **gate V4**
**Size:** `M` | **Depends on:** S1d-02, S0-05, S0-09 | **Spec:** §9.2, §6.4

**As a** data scientist **I want** the validation gate run exclusively on the holdout window
**so that** the cascade accuracy metric is unbiased and reliable.

### Description
Using the holdout data for cascade verification prevents cheating. The model must prove it can accurately forecast cascade rates on flights it was never trained on.

### Acceptance Criteria
- [x] Realised cascade frequency — the share of drafts producing ≥1 downstream open item or reserve loss —
  compared against the historical band from S0-05, on the **holdout** window
- [x] Verdict stated; the gap reported whichever way it goes
- [x] If S0-03's recall was marginal, **the report says so on the same page** as the verdict

### Verification
*   🤖 **Automated:** `pytest tests/gates/test_v4_cascade.py`
*   🙋 **Manual:** `crewsim gate v4 --window holdout`
    *   **Expect:** simulated rate vs the historical band, verdict stated
    *   **Fails if:** roster composition was adjusted to make it pass — that is calibration wearing
    *   validation's clothes

### How it was implemented
- I extended `cascade_target` inside `src/crewsim/data/cascades.py` to accept a `window_name` parameter, securely filtering the `D6` history down to the bounds configured in `base.yaml` (e.g. `holdout`) before any draft reconstruction or counting begins.
- `src/crewsim/gates/v4_cascade.py` was created to run the V4 validation. It checks the simulated distribution against the historical `ci_low` and `ci_high` bands.
- Importantly, it dynamically checks the draft recall metric inherited from S0-03's `d6_d7_join_pass` against the `d4_link_marginal` boundary and prints a prominent `[WARNING]` right next to the verdict if the data quality was marginal, as required.
- The `crewsim gate v4 --window holdout` CLI binding was added to `src/crewsim/cli.py` to allow manual execution, and unit tests were built in `tests/gates/test_v4_cascade.py`.

**Backlog-integrity note, 2026-08-07.** `stories.yaml` had this at `status: todo` despite this file
already claiming done. Unlike S1d-01/S1d-02, the manual check was fabricated until last turn — S1d-04d
replaced its hardcoded `sim_cascade_rates` with a real 20-scenario CRN loop, which is what makes this
story's manual check genuinely hold today. (S1d-04d's own notes already document that the *verdict* is
not currently trustworthy — both sides degenerate to a rate of 0.0, for separate, already-diagnosed
reasons — but the story's own bar, a real simulated rate compared against the historical band with a
verdict stated, is met.) `stories.yaml` status flipped to `done` to match.

---

## ✅ [DONE] S1d-04b — Reconcile engine time units and legality call signatures
**Size:** `S` | **Depends on:** S1d-03 | **Spec:** §5.3, §4.3

**As a** modeller **I want** every engine module reading and writing time on the same scale **so that**
wiring them together produces a real number instead of a silently-wrong one.

### Description
This story used to be bundled with building the DES loop (`S1d-04c`, below). Split 2026-08-07 on
review: building new orchestration on top of pieces that don't compose yet makes every failure
ambiguous — is the loop wrong, or is a calendar 60x off? Fix the seams first, on their own tests.

Reading the engine end-to-end (nothing has ever run these modules together, so nothing caught this)
turned up three concrete defects:

1. **Unix seconds vs. minutes.** `roster_loader.py`'s `to_ts()` converts D2 timestamps via
   `.timestamp()` — Unix epoch seconds (~1.7 billion). But `legality.py`, `cascade.py` and `costs.py`
   all work in **minutes since horizon start** (`costs.py`'s own comment: *"Sim time in minutes: day *
   24 * 60"*; `11 * 60` for an 11h rest, etc.). Confirmed against the fixtures in
   `tests/engine/test_cascade.py` and `tests/engine/test_eligibility.py`, which use small
   minutes-scale values (900, 1000, 1100…), not Unix-epoch-scale ones — minutes is the engine's actual
   convention, and `roster_loader` is the outlier.
2. **`sick_calls.py`** mixes in seconds-based constants (`86400` for a day, `3600` for an hour) against
   that same minutes convention.
3. **`drafting.py::select_draft_candidate`** calls `is_legal_assignment(c, item)` without `cfg`/`now`.
   `legality.py`'s L3/L4/L8 checks now `raise ValueError` when `cfg` is `None`. `eligibility.py` was
   updated to pass `cfg`/`now` through when those rules were added; `drafting.py` never was, so it
   would crash the first time it's actually exercised against a non-trivial config.

### Unblocked 2026-08-07
The obvious anchor — `scope.bid_period` (`2027-01`) — doesn't work: D2 only covers 2023-08-01 to
2026-07-31, and a *future* bid period is by definition not in the historical corpus. The real question
turned out to be "which historical window stands in for the target bid period's roster pattern," not
"what date is t=0." Resolved with the user:

- Select the most recent **complete `horizon_days`-length (42-day) span** inside `windows.holdout`
  whose calendar months are all within `configs/seasons.yaml[scope.season].months`
  (`scope.season: winter_sun` → `[12, 1, 2, 3, 4]` today).
- That window **is** the full warmup + measurement + cooldown horizon — there is no separate real
  lead-in period spliced on before it.
- The window's own start becomes sim minute 0.
- Using `holdout` data here does **not** reopen S0-09's fitting/holdout split — that rule guards
  statistical calibration (fitting sick-call/delay/regime models) from seeing validation data. This is
  structural roster input to a production run, not model fitting.

### Acceptance Criteria
- [x] `roster_loader.py` (or a new selection step ahead of it) picks the historical window per the
  season-match rule above, and reports which dates it picked
- [x] `roster_loader.py` produces block times on the same minutes-since-horizon-start scale as the
  rest of the engine, anchored to that window's start
- [x] `sick_calls.py`'s deadline and search-window arithmetic use minutes throughout, no `86400`/`3600`
- [x] `select_draft_candidate` accepts and threads `cfg`/`now` through to `is_legal_assignment`, same as
  `eligibility.py` already does — confirmed *not* a case for merging the two candidate-selection paths,
  since reserve dispatch (eligibility) and drafting (roster pull) are genuinely different domain steps

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_roster_loader.py tests/engine/test_drafting.py`
*   🙋 **Manual:** `crewsim roster summary --base YUL --fleet A321neoLR --position FO`
    *   **Expect:** block start/end times are on the same minutes-since-horizon-start scale as every
      other engine module — small numbers, not Unix-epoch-scale; the CLI reports which historical
      window (dates) was selected as the template and why (season match)
    *   **Fails if:** a loaded crew member's block times are ~10 orders of magnitude larger than a
      hand-built test fixture's (Unix seconds vs. minutes), or the selected window's months fall
      outside `scope.season`'s month list

### How it was implemented
- Added `select_template_window(cfg)` to `src/crewsim/engine/roster_loader.py`: walks backward from
  `windows.holdout.end`, finds the most recent complete `horizon_days`-length span whose calendar
  months all fall within `configs/seasons.yaml[scope.season].months`, raising `ValueError` if none
  fits. Confirmed against the real corpus: for `scope.season=winter_sun`, this picks
  **2026-03-20 to 2026-05-01**.
- Rewrote `load_rosters`'s D2 loop: block times are now `(block_dt - window_start_midnight).total_seconds() / 60.0`
  — minutes since the window's start — instead of `.timestamp()` (Unix epoch seconds). Also fixed a
  second latent bug this surfaced: `.timestamp()` on D2's naive ISO strings interprets them in the
  *local system timezone*, making the old numbers non-reproducible across machines; the new code stays
  in naive-`datetime` arithmetic throughout, so it doesn't depend on the machine's timezone. Only
  blocks overlapping `[window_start, window_end)` are loaded — not a crew member's entire multi-year
  D2 history, which is what `load_rosters` was doing before (confirmed via `min`/`max` block time
  across a loaded roster: -12720 to 79440 minutes, i.e. blocks are kept if they overlap the window
  even when they start before it or run past it, which is correct for rest/rolling-limit context at
  the boundary — nothing is clipped).
- `sick_calls.py`: `search_end` now advances by `duration_days * 1440.0` (was `* 86400`), and
  `deadline` subtracts `dl_hours * 60.0` (was `* 3600.0`).
- `drafting.py::select_draft_candidate` gained `cfg: Any = None, now: float | None = None` params,
  threaded into `is_legal_assignment`, matching `eligibility.py`'s existing call. Fixed the same gap in
  `cli.py`'s `explain-draft` command (was calling `select_draft_candidate(roster, duty)` with neither).
- This exposed genuinely pre-existing, unrelated test failures that were already crashing before this
  story touched anything: `tests/engine/test_drafting.py` (3 tests — `ValueError` from the missing
  `cfg`) and `tests/engine/test_sick_calls.py` (`TypeError` — the test was calling `apply_sick_call`
  with a stale, pre-`cfg`-parameter signature). Both are fixed now as a consequence of this story;
  `tests/engine/test_events.py::test_uncovered_deadline_held` was updated to minutes-scale fixture
  values, since it exercises `apply_sick_call` directly.
- Added `roster_loader.py: {60.0}` and updated `sick_calls.py`'s entry from `{86400, 3600.0}` to
  `{1440.0, 60.0}` in `tests/test_config.py`'s `ALLOWLIST`, in the same "time conversion, not a
  business input" category as `legality.py`/`state.py`/`costs.py`'s existing `60`/`24` entries.
- `crewsim roster summary` now prints the selected template window and why (season match).
- **Code review (2026-08-07) found no correctness bugs, but a real coverage gap: the fix was only
  verified manually/ad hoc, not pinned by any test.** Closed:
  - `tests/engine/test_roster_loader.py::test_roster_loader` now asserts every loaded block's start/end
    stays within 10x the horizon in minutes — generous enough not to be brittle, tight enough that a
    regression back to `.timestamp()` (a ~29-million-minute error, confirmed by deliberately checking
    what a 1970-01-01 anchor would produce) fails immediately instead of silently passing.
  - Added `test_select_template_window_picks_most_recent_matching_span` and
    `test_select_template_window_raises_when_nothing_fits` — direct unit tests of the new function's
    boundary math (deliberately off-by-one-prone: `holdout.end - (horizon_days - 1)`) and its error
    path, via a fake `cfg` + `monkeypatch` on `loaders.load_seasons` rather than depending on the real
    corpus/config.
  - `tests/engine/test_sick_calls.py::test_sick_calls` no longer hardcodes `current_time = 0.0` (which
    only worked because of what the real corpus happens to contain at whatever window
    `select_template_window` currently resolves to). It now anchors to the earliest real `PAIRING` in
    the loaded roster, so it stays correct if `scope.season` or `windows.holdout` change later for
    unrelated reasons.
- **Left alone, confirmed pre-existing and out of scope:** `mypy --strict` and `ruff check` both still
  fail elsewhere in `src/crewsim/engine/` (implicit-Optional defaults, missing annotations, dynamic
  `_is_reserve` attribute, deprecated `typing.List`/`Tuple`/`Dict`, unused imports) — none introduced by
  this story, none in the lines it touched after cleanup. `tests/engine/test_eligibility.py`,
  `tests/gates/test_v3_eligibility.py`, and `tests/calibration/test_holdout.py` were already failing
  before this story for unrelated reasons (a test that never constructs a `cfg` hitting the same L3
  `ValueError` class, a `numpy.bool_ is True` identity bug, and S0-09 territory respectively).

---

## ✅ [DONE] S1d-04b2 — Fix mock-corpus generator: D2 PAIRING blocks vs D3 duty-period timing
**Size:** `S` | **Depends on:** S1d-04b | **Spec:** §5.3, §4.3

### Description
Discovered 2026-08-07 implementing S1d-04c. `legality.py`'s L1 (13h max duty) fails for every D2
`PAIRING` block by construction, because D2 rolls up a whole multi-day trip (48-120h) into one block.
The fix — decompose `PAIRING` into D3's real per-duty-period spans (`report_local`..`release_local`,
~4-9h) — surfaced a second, larger problem underneath it.

### What was wrong
Replacing D2's flat block with D3's real duty-period timing made **62.4% of crew (368/590) fail L0**
(calendar overlap). 87% of conflicts were the pairing's real last release spilling past D2's own end
boundary into whatever D2 scheduled next (`DAY_OFF`/`VACATION`/`TRAINING`/`RESERVE`/`SIMULATOR`); the
rest were consecutive same-pairing duty periods overlapping each other (an overnight duty's real
release landing after the next day's independently-sampled report time).

**A wrong diagnosis shipped first and was caught before it stuck.** The first read of this was "rare
cross-pairing noise" (0.16% of transitions, measured corpus-wide), and a `CALENDAR_CONFLICT` exclusion
bucket was added to `roster_loader.py` to quietly drop the offending crew member rather than raise.
Re-measuring directly against the real `load_rosters` logic (not a proxy transition-rate query) found
the true rate was 62.4%, not 0.16% — the exclusion bucket was masking a systemic problem as "excluded
crew," which is worse than the crash it replaced (a crash is visible; a roster silently down from 112
to 43 crew is not). **The exclusion was reverted — L0 raises again — before anything else.**

### Resolution
Presented the corrected finding to the user with three options: make D3 authoritative (clip the
adjacent D2 block), make D2 authoritative (truncate D3's duty periods), or fix the root cause in the
corpus generator itself. User chose the third and pointed at `tools/generate_mock_corpus.py`.

### How it was implemented
- `_make_pairing` now tracks and returns the true last-release datetime (the last duty period's
  `report + positioning + block + release-buffer`, not the nominal calendar-day span).
- The D2 `PAIRING` block's day-span is padded (`math.ceil`) so D2 always fully *contains* D3's real
  timing, and the roster-generation walk cursor (`d`) advances past that padded end — not the naive
  day count — so the next scheduled block never lands before the pairing actually releases the crew
  member. This eliminated the 62.4%-of-crew case entirely (verified: 0 conflicts).
- Each day's report time is floored to `(previous overnight duty's real release + 0.5h)` — reusing the
  same 0.5h release buffer already used elsewhere in this function, not a new invented constant — when
  the previous duty period spilled into the current day. This eliminated the residual same-pairing
  overlap case (was 802/399,913 duty-period pairs, 6.95% of crew; now 0).
- Corpus regenerated with the unchanged default seed/months; `_ground_truth.json` updated accordingly
  since pairing/duty counts shift slightly with the padding.
- `roster_loader.py`'s `CALENDAR_CONFLICT` exclusion bucket and its (wrong) comment were removed; L0
  violations raise `ValueError` again, now pointed at this story if it ever regresses.

### Verification
- `pytest tests/engine/test_roster_loader.py` — 13/13 passing.
- `load_rosters(cfg, base="YUL", position="FO", fleet="A321")` runs to completion with zero L0
  exceptions across the full corpus (was 62.4%/57.5% depending on diagnosis stage).
- `des.run_scenario(...)` end-to-end (S1d-04c's WIP pipeline) now produces a non-degenerate ledger —
  190 `DRAFT_TIER1`, 54 `RESERVE_UTILIZATION`, 200 `CANCELLATION` — where before this fix every single
  `OpenTimeItem` failed legality immediately and 100% cancelled ($7.4M, 0 drafts).

---

## ✅ [DONE] S1d-04c — `des.py`: single-scenario recovery pipeline
**Size:** `M` | **Depends on:** S1d-04b, S1d-04b2 | **Spec:** §5.3, §4.3

**As a** modeller **I want** one OpenTimeItem to flow through reserve → draft → cascade → hold → cancel
using the real engine modules **so that** the pipeline shape is proven correct before it's run at scale.

### Description
`src/crewsim/engine/des.py` is still its S0-00 placeholder — one docstring, no dispatch loop. No story
in this backlog was ever assigned to build it. Auditing this slice on 2026-08-07 turned up that
**S1a-12** and **S1d-04** are both marked `done`, but their CLI paths return fabricated numbers instead
of engine output (`crewsim compare` seeds two `np.random.normal` arrays; `gate v3`/`gate v4` compare
against hardcoded `sim_fractions`/`sim_cascade_rates`). None of that is malicious — the comments say
outright "since full DES isn't generating cascades yet" — but it means nothing downstream has a real
`E[C]` to work with.

This story was originally "wire the whole DES loop," sized `L`. Narrowed 2026-08-07 on advisor review:
bundling the recovery pipeline with the CRN multi-scenario loop and the CLI rewiring means a wrong
aggregate number could come from either — undebuggable without splitting them. This story is just the
pipeline, on one scenario, with a printable ledger. **S1d-04d** picks up the CRN loop and CLI rewiring
once this is proven correct.

`crewsim_skeleton.py`'s `IOCSimulation` class is the control-flow reference (reserve-first → draft →
cascade re-enqueue → cancel) — its own simplified inline legality/cascade/draft-selector/eligibility
logic gets replaced by the real `engine/*` modules everywhere.

Three things confirmed before writing any code, so they don't get invented mid-build:
- **`copy.deepcopy` is required**, not `dataclasses.replace`: `roster_loader` sets `_is_reserve` as a
  dynamic attribute, and `replace` silently drops it (verified directly).
- **`RESERVE_STAFFING` must be booked per reserve PER DAY**, off that day's actual `RESERVE` block's
  `reserve_call_type`, not a per-crew-member SC/LC label — 8 of the 12 reserves in the current template
  window carry *both* SC and LC blocks, so "this reserve is SC" isn't a well-defined question.
- **The sick-call duration `sick_calls.py` needs is real, already-calibrated data** —
  `output/params/params_v*_winter_sun.json → sick_call_nhpp.duration_lognorm_shape/scale` (S0-07) — not
  a number invented for this story.

**E8 (hold-until-deadline) is in scope**, per the user, rather than deferred to match the skeleton's own
documented shortcut. Re-check times for a pending item are the reserve pool's own future `RESERVE`-block
start times, up to the item's deadline — derived from calendar data already loaded, not an arbitrary
polling interval.

**Known, deliberately out-of-scope defect surfaced while doing this:** `sick_calls.py` (S1b-04, marked
`done`) breaks a sick crew member's pairings but never marks that crew member unavailable — they remain
fully draftable during their own sick leave. Called as-is; not patched here.

### Acceptance Criteria
- [x] A SimPy `Environment` in `des.py` drives one scenario's dispatch (sick-call arrivals → recovery
  pipeline) by calling into the pure `engine/` modules — `engine/` itself still imports no `simpy`
  (S0-00b's rule stays enforced, checked the same way)
- [x] Recovery order per `OpenTimeItem`: eligible reserves tried first (real `EligibilityEngine`), then
  draft (real `select_draft_candidate`), then cascade re-enqueue for any broken future pairings/reserves
  (real `compute_draft_delta`/`apply_delta`, respecting `cascade.visibility_lag_hours`), then held until
  its deadline with re-checks as reserves free up, then `CANCELLATION` if still uncovered
- [x] `RESERVE_STAFFING` booked per reserve-day at the real SC/LC rate from that day's actual block
- [x] Residual open items at horizon end go through the real `evaluate_terminal_penalties`
- [x] All costs land in a real `CostLedger`, traceable back to `root_event_uid`

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_des.py`
*   🙋 **Manual:** `crewsim explain-recovery --scenario 0 --trace`
    *   **Expect:** one legible trace — an `OpenTimeItem` enters, reserve/draft/cascade/hold/cancel
      resolution is shown step by step with real crew ids and real costs from `configs/costs_pilots.yaml`
    *   **Fails if:** the same item's outcome is unchanged when `configs/costs_pilots.yaml` or
      `configs/base.yaml` legality limits are edited

### How it was implemented
Closed out 2026-08-07 once S1d-04b2 unblocked it. `des.py`'s `Simulation` class and `run_scenario()`
(sick-call source → `recovery_pipeline` → `_attempt_resolution` reserve-then-draft → `_delayed_pipeline`
for cascades → E8 hold-with-retry → terminal penalties) were already fully written from earlier in the
session; finishing the story was four things:

- **`tests/engine/test_des.py`** (6 tests): every item resolves (`open_items == {}` after `env.run()`);
  outcomes are mixed (reserve + draft + cancel present, not the all-cancel degenerate pipeline
  S1d-04b2's history describes); CRN reproducibility under a fixed `master_seed` (byte-identical ledger
  rows across two runs); a different `master_seed` changes the outcome (the rng is actually wired in);
  cascade items get distinct nonzero `event_uid`s (cascade.py hands them uid=0 by design — collisions
  would silently merge two different items' costs in the ledger); trace only populates when
  `trace=True`.
- **`crewsim explain-recovery --scenario --policy --master-seed --trace`** wired into `cli.py`, calling
  the real `des.run_scenario()` and printing the step-by-step trace plus ledger category totals — not a
  mock, unlike `compare`/`gate v3`/`gate v4` (S1d-04d's job to fix).
- **mypy --strict clean on `des.py`.** Added `scipy-stubs` as a dev dependency (same pattern as the
  existing `types-PyYAML`): `des.py` is the first `crewsim.engine.*` module to import `scipy` under the
  strict override, so this gap didn't exist before it. Annotated the three SimPy generator methods'
  return types. Narrowed `cfg.cascade` (`CascadeConfig | None`) to a `self._cascade_cfg` attribute once
  in `__init__`, instead of mypy needing a fresh assert in every method that reads
  `visibility_lag_hours`.
- **Closed the `tests/test_config.py` ALLOWLIST gap** for `des.py`'s genuinely structural constants:
  `1440.0`/`60.0` (minutes-per-day/-hour, same category as `sick_calls.py`/`roster_loader.py`), `16`
  (blake2b `digest_size`, matching `crn.py`'s own entry), `11`/`10` hours (×`60.0`) for reserve
  assignment's min-rest — duplicating `legality.py`'s already-allowlisted L2 constants because
  `events.py::assign_reserve` takes `min_rest` as a caller-supplied value rather than deriving it
  itself — and `3`/`5` (draft tiers, matching `drafting.py`'s own tier entries).
  **One constant was *not* allowlisted:** the sick-call duration floor (`max(0.5, duration_days)`) was
  written earlier in the session without asking — a genuine business assumption (the S0-07 lognormal
  fit's support runs down near 0, so *some* floor is needed, but 0.5 days specifically wasn't confirmed
  with anyone). Asked the user; moved it to `calibration.sick_call_min_duration_days` in
  `configs/base.yaml` instead of hiding it as a code literal.

**A vacuous test, caught before landing.** `test_cascade_items_get_distinct_nonzero_uids` asserted
`n_cascading_drafts <= n_drafts`, which is trivially true at `n_cascading_drafts == 0` — and across 20
different `master_seed`s against the real corpus + R10 policy (148-crew roster), it *was* always 0.
`select_draft_candidate` always found a tier-1 (day-off) candidate before a tier-2 (conflicts with a
future pairing) candidate was ever needed, so `_attempt_resolution`'s `cascaded` branch, the
`dataclasses.replace`-based uid reassignment, and `_delayed_pipeline`'s visibility-lag wait were never
actually exercised by any test, corpus-driven or otherwise. Not a code defect —
`tests/engine/test_cascade.py` already verifies `compute_draft_delta`'s cascade logic in isolation — but
a real gap between "the acceptance criterion is checked `[x]`" and "a test would catch a regression
here." Worth knowing for S1d-04 (the V4 cascade-rate gate, already `done`) too: if cascades are this rare
at this roster size, that gate's own historical-rate comparison should be read with that in mind.

Closed directly: added `test_cascade_path_fires_end_to_end`, a single-candidate synthetic roster whose
only legal draft choice also holds a future pairing inside the drafted duty's mandatory-rest
window — the same scenario `test_cascade.py::test_future_pairing_mandatory_rest_cascade` uses to prove
`compute_draft_delta` itself, but here driving it through a real `Simulation` object end-to-end. It
caught a genuine bug in its own first draft: a manually-assigned `item.uid=1` collided with
`next_uid()`'s first cascade uid, because the test hadn't advanced `sim._uid` the way
`sick_call_source` does before creating an item. Fixed by setting `sim._uid = item.uid` before calling
`_attempt_resolution` — itself evidence the assertion isn't vacuous the way the corpus-driven one was.

### Verified
- `pytest tests/engine/test_des.py` — 7/7 passing; full suite 195 passing, same 7 pre-existing failures
  as before this story (confirmed unrelated — cfg-threading and CLI-argument gaps in
  `eligibility.py`/`legality.py`/`cli.py` left over from before S1d-04b, none touched by this story).
- `crewsim explain-recovery --scenario 0` on the real corpus: mixed outcomes (190 `DRAFT_TIER1`, 54
  `RESERVE_UTILIZATION`, 200 `CANCELLATION`, structural `RESERVE_STAFFING`) — not the 100%-cancellation
  degenerate case S1d-04b2 fixed the root cause of.

### Known, documented limitations
- The cascade re-enqueue path is proven correct by a direct/forced test
  (`test_cascade_path_fires_end_to_end`) and by `test_cascade.py`'s unit tests of `compute_draft_delta`,
  but has not been observed firing under the real corpus at the R10 policy's roster size across 20 seeds
  tried. Left as a documented fact, not silently smoothed over — see S1d-04d/S1d-05 if a policy or roster
  size where cascades actually occur turns out to matter for those gates' numbers.
- `Simulation.sick_call_source` generates arrivals across the *entire* horizon (warm-up +
  measurement + cooldown), not just warm-up + measurement. `configs/base.yaml`'s own comment on
  `cooldown_days` — "lets late cascades realise their cost" — reads as cooldown being a drain period
  for events *already in flight*, not a window with its own fresh arrivals. Found during S1d-04d while
  reasoning about what `measured_window_costs` should include; not fixed here — it's a change to
  S1d-04c's already-`done` sick-call generation, not S1d-04d's own scope. If a future story addresses
  it, `des.py`'s `measured_window_costs` convention (`min_time=warmup_end`, no `max_time` — S1a-04's
  own precedent) already assumes cooldown-sourced costs are legitimate, so that part would not need
  to change.

---

## ✅ [DONE] S1d-04d — CRN scenario loop + `crewsim run`/`compare`/`gate v3`/`gate v4` off their mocks
**Size:** `M` | **Depends on:** S1d-04c | **Spec:** §5.3, §4.3

**As a** modeller **I want** the proven single-scenario pipeline run across CRN-paired scenarios per
policy **so that** `compare`/gate commands report a real `E[C]`, not fabricated data.

### Description
The other half of the original "wire the DES loop" story. Runs the S1d-04c pipeline across N CRN-paired
scenarios per policy (`crn.generate_streams`, `copy.deepcopy`-ing the roster per scenario per S1d-04c's
finding), aggregates `E[cost]`/`CVaR95`, and replaces `cli.py`'s mocked `compare` (`np.random` Gaussians)
and `gate v3`/`gate v4`'s hardcoded `sim_fractions`/`sim_cascade_rates` with this loop's real output.
This is what actually makes S1a-12's and S1d-04's manual checks (both marked `done`) mean something, and
is what S1d-05 (V9) needs a real `E[C]` from.

### Acceptance Criteria
- [x] `crewsim run`, `crewsim compare`, `gate v3`, and `gate v4` read their numbers from the CRN loop —
  the mocked arrays and `np.random` draws currently in `cli.py` are removed
- [x] CRN streams (S1a-05) seed each scenario's stochastic draws so paired policy comparisons stay
  low-variance, not independently-seeded noise
- [x] The roster is deep-copied per scenario so mutations from one scenario never leak into the next
  (already true of `run_scenario`, S1d-04c; `run_policy_crn` just calls it N times)

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_des_crn.py`
*   🙋 **Manual:** `crewsim compare --policies R6 R10 --scenarios 100`
    *   **Expect:** the paired CRN diff moves when a cost or legality parameter in `configs/base.yaml`
      is edited
    *   **Fails if:** the output is unchanged when `configs/base.yaml` costs are edited — that means
      it's still reading mocked data, not the engine

### How it was implemented
- `des.py` gained three functions: `run_policy_crn` (N calls to `run_scenario` across
  `scenario_id` 0..N-1, same `master_seed` — CRN-paired by construction, since
  `_load_daily_sick_calls` never reads `policy`), `measured_window_costs` (per-scenario
  `CostLedger.total_cost(min_time=warmup_end)`, no `max_time` — S1a-04's own established convention,
  cited from `tests/engine/test_costs.py`, not invented here), and `cvar95` (closed-form: mean of the
  worst 5% of scenario costs).
- `cli.py`: `run`'s bare path (previously `return _todo("run")`) now runs the CRN loop and prints
  `E[cost]`/`CVaR95`/min-max. `compare` replaced its `np.random.seed(42)` mock with two real
  `run_policy_crn` calls (same `master_seed` → paired) feeding the same t-test/CI statistics that were
  already there. `gate v3`/`gate v4` gained `--policy`/`--scenarios`/`--master-seed` and now build
  `sim_fractions`/`sim_cascade_rates` from real `Simulation` objects instead of 4-element hardcoded
  lists.

### A real bug this story's own testing exposed
`scenarios/generator.py`'s scenario-cache key was `f"{master_seed}_{content_hash}"` — **it never
included `n_scenarios`**. A cache file written for a small request (e.g. 3 scenarios) was silently
reused by a later, larger request (e.g. 20) under the same `master_seed`, because the key matched; the
extra `scenario_id`s then had no rows in the cached parquet, and `des.py`'s `_load_daily_sick_calls`
read that as all-zero sick-call counts, with no error. Confirmed directly: 17 of 20 scenarios silently
produced zero drafts. Nothing before this story ever called `generate_scenarios` with varying
`n_scenarios` under one `master_seed`, so it never surfaced — S1d-04c's own tests always used
`n_scenarios == 1` call-for-call. Fixed by adding `n_scenarios` to the cache key in both
`scenarios/generator.py` and its duplicate in `des.py::_scenario_cache_path`; confirmed
`crn.generate_streams`' own per-scenario streams stay prefix-stable across different `n_scenarios`
(numpy `SeedSequence.spawn` semantics — scenario 0 is identical whether requested as part of a
3-scenario or a 20-scenario set), so the fix doesn't lose that property. Covered by two regression
tests in `test_des_crn.py`.

Also fixed, while in the area: `gates/v3_eligibility.py::run_v3_gate` returned a bare numpy bool for
`"pass"` (`np.True_ is True` fails an identity comparison) — the same one-line `bool(...)` wrap
`run_v4_gate` already had. Closed 2 of the session's 7 pre-existing test failures.
`tests/test_cli.py::test_cli_compare` already invoked the real CLI with `--scenarios 100`, written
before `compare` was real — once wired, that made it a genuine ~4-minute simulation on every test run.
Reduced to 3 scenarios; the story's own 100-scenario bar is the manual check, not the automated suite.

### A second vacuous mock, caught the same way as S1d-04c's
`crewsim run --assert-invariants` fed `run_v3_gate` a `np.random.normal(hist["mean"], 0.01, 100)` array
— a Gaussian centred *on* the historical mean by construction, so the pre-flight V3 check it drove
could structurally never fail. Same shape as S1d-04c's `n_cascading_drafts <= n_drafts` finding.
Restructured `run` so the CRN loop runs once (`sims`) and both `--assert-invariants` (real
`sim_fractions` from `sims`, same construction `gate v3` uses) and the cost aggregation reuse it — no
extra simulation cost. Consequence, confirmed by running it: `run --assert-invariants` now correctly
returns 1 on every real invocation, since real simulated eligibility (~0.04) never matches the
fabricated historical band. That's an honest, correct result of wiring real data in, not a new bug —
and it stays this way until slice 1c's real eligibility reconstruction exists.

### Verified
- `pytest tests/engine/test_des_crn.py` — 7/7 passing (scenario count/reproducibility, the cache-key
  regression and its prefix-stability counterpart, `measured_window_costs`, `cvar95`).
- Full suite: 204 passing, 5 pre-existing failures (down from 7 — the two `test_v3_eligibility.py`
  fixes above), ~32s (not ~4 minutes — the `test_cli_compare` fix).
- `crewsim run --policy configs/policies/R10.yaml --scenarios 3`: real `E[cost]`/`CVaR95`, not `_todo`.
- Config-sensitivity check (the story's own `fails_if`): bumped `draft.base_premium` 500 → 5000 in
  `configs/costs_pilots.yaml`, reran the same `master_seed`; `E[cost]` moved from $3,056,053.33 to
  $3,602,053.33 — exactly $546,000 = 182 drafts × $3,000, confirming it's reading the real per-draft
  cost, not a cached/mocked number. Reverted after.
- The real manual check, run in full: `crewsim compare --policies R6 R10 --scenarios 100` →
  `Mean Difference: $9,642.00`, `95% CI: [$-11,082.62, $30,366.62]`, `t-statistic: 0.92 (p=0.3582)` —
  a real paired CRN comparison, not a fabricated Gaussian draw.

### Known limitation — neither gate can currently produce a trustworthy verdict
Both gates' *historical* sides are unreliable, independent of anything this story changed on the
simulated side:
- **Gate V3**: `reconstruct_eligibility` (`data/eligibility_target.py`) is entirely fabricated —
  `np.random.seed(42)` binomial draws standing in for a real D1/D2/D3/D4 reconstruction. Slice 1c
  ("Eligibility engine FULL") is 0/5 done — this was never built. Running `gate v3` against real
  simulated data now correctly **FAILS** (simulated mean ≈0.04 vs. the fake historical band
  [0.29, 0.31]) — that FAIL is the story working as intended, not a regression.
- **Gate V4**: `cascade_target` *is* a real D6×D7 reconstruction, but returns `n_drafts=0` for the
  holdout window (confirmed directly: `cascade_target(cfg, "holdout")` →
  `{"rate": 0.0, "n_drafts": 0, "draft_recall": {"recall": 0.0}}`) — a real, pre-existing S0-03
  reconstruction defect, out of this story's scope. `gate v4` currently "passes" only because both
  sides degenerate to 0.0, not because anything was validated — reinforced by S1d-04c's own finding
  that `n_cascading_drafts` is 0 across every scenario tried at R10's 148-crew scale.

S1d-04 and S1a-12 were marked `done` on the strength of the mocks these gates used to read before this
story. That basis no longer holds now that the simulated side is real, and should be revisited.

---

## ✅ [DONE] S1d-04e — Remove v4_cascade.py's redundant hardcoded d4_link_marginal fallback
**Size:** `S` | **Depends on:** S1d-04 | **Spec:** §6.2, §9.2

**Backlog-integrity fix, 2026-08-07.** `test_no_numeric_constant_outside_configs` (§4.4) was failing on
`src/crewsim/gates/v4_cascade.py` — `getattr(cfg.quality_gates, "d4_link_marginal", 0.90)` hardcoded a
fallback default that shadows a value already defined in `configs/base.yaml:93`
(`d4_link_marginal: 0.90`). This wasn't a missing config value needing a fallback —
`QualityGateThresholds` (`config.py`) already requires the field, so the `getattr`'s default branch was
dead code that also happened to duplicate a magic number. Fixed by reading
`cfg.quality_gates.d4_link_marginal` directly, matching the line immediately above it
(`d6_d7_join_pass`), which never had this pattern.

### Verification
*   🤖 **Automated:** `pytest tests/gates/test_v4_cascade.py && pytest tests/test_config.py -k allowlist`
*   🙋 **Manual:** `python -c "from crewsim import config; cfg = config.load(); print(cfg.quality_gates.d4_link_marginal)"` → `0.9`, read from `configs/base.yaml`, not a hardcoded `getattr` default
    *   **Fails if:** v4_cascade.py's marginal threshold silently diverges from configs/base.yaml when
        the config value is edited

---

## 🟢 [DONE] S1d-05 — V9 parameter sensitivity  ·  **gate V9**
**Size:** `M` | **Depends on:** S1d-04d | **Spec:** §9.2, §7.4

**As a** planner **I want** to know which of my inputs the answer actually depends on
**so that** a recommendation resting on a judgement call is visible as such.

### Description
Parameters are estimates. By sweeping a range of values (like terminal penalty), we can prove to stakeholders whether a specific assumption fundamentally changes the answer.

### Acceptance Criteria
- [x] Sweeps from `configs/base.yaml → sensitivity`: `terminal_penalty`, `lambda` (real); `roster_size`
      is swept but confirmed inert — see "Known baseline" below and the implementation note
- [x] Recommended R reported as a **surface**, not a point
- [x] Instability is reported prominently, not buried — an R\* that moves is a finding

### Verification
*   🤖 **Automated:** `pytest tests/gates/test_v9_sensitivity.py`
*   🙋 **Manual:** `crewsim gate v9 --scenarios 20 --surface`
    *   **Expect:** a small table of R\* against each swept parameter
    *   **Fails if:** R\* moves materially and the report does not say so on the front page
    *   > **Known baseline.** Before headcount conservation, `roster_size` was completely inert — argmin E[C]
    *   > was R=6 at 100, 120 and 140, because senior-first drafting only ever reached the top ~21 of the
    *   > seniority list. After slice 1b it should start to bite. If it still does not, that is worth
    *   > understanding before trusting the recommendation.

### How it was implemented
Unblocked and implemented 2026-08-07. The stated blocker ("no code defines how `lambda_risk_dial`
blends `E[cost]` and `CVaR95`") turned out to be answered by the spec itself, not something to invent:
**§7.4 gives the objective verbatim** — `stage1_cost(R) + Q.mean() + lam * cvar95` — and
`des.run_policy_crn`/`measured_window_costs`/`cvar95` (S1d-04d) are exactly the real inputs it needs.
Confirmed directly (not assumed) that `measured_window_costs` already includes stage-1 reserve staffing
cost (`RESERVE_STAFFING` is booked inside the simulation, `des.py:180`, and scales with R: $21.7K/scenario
at R4 vs $59.4K at R10) — so the real objective in this codebase is simply `mean_cost + lam * cvar95`, no
separate `C1(R)` term, and adding one would have double-counted.

Implemented `build_r_star_lookup(cfg, costs, n_scenarios, master_seed, policies, terminal_penalties)`
(`gates/v9_sensitivity.py`): runs the REAL CRN pipeline for each of 5 real candidate reserve policies
(R4/R6/R8/R10/R14 — these already existed as real policy files and match spec §7.4's own worked-example
table exactly) × each `terminal_penalty` value, producing real (mean, CVaR95) pairs. Varying
`terminal_penalty` for real required overriding a frozen pydantic model
(`costs.disruption.model_copy(update=...)`, since `DisruptionCosts` is `frozen=True`) — verified the
override actually takes effect, not a silent no-op. `_real_r_recommender(r_lookup)` returns a
`mock_r_function`-shaped closure that argmins the real objective over the real simulated candidates for a
given (terminal_penalty, lambda) — `run_v9_gate` keeps its existing `mock_r_function` injection seam
unchanged (both pre-existing tests still pass verbatim), and now also accepts `r_lookup` for the real
path; calling with neither raises instead of silently falling back to the old `default_mock_r`
"completely hypothetical relationship for demonstration" formula, which has been deleted.

**Two real findings from actually running this, not assumed:**
1. `TERMINAL_PENALTY` never fires across 50 real simulation runs (5 policies × 10 scenarios) at this
   corpus/roster scale — every open item resolves before the horizon ends, so the `terminal_penalty`
   axis is real and correctly wired but currently empirically inert, the same character as the
   pre-existing `roster_size` finding above.
2. ~~R\* itself is essentially flat (=4) across every lambda...~~ **Corrected 2026-08-07 (S1e-01):** this
   flatness was an artifact of a real bug in `des.measured_window_costs` found and fixed while
   implementing S1e-01 (see its own card) — the old cost attribution wrongly counted 15–33% of every
   scenario's cost as cool-down activity that never should have been in-window. Re-ran the identical real
   5-R × 20-scenario sweep after the fix: **R\* now genuinely flips from 4 (λ=0.0) to 10 (λ≥0.25)** —
   qualitatively matching spec §7.4's own worked-example pattern (risk-neutral picks low R, risk-averse
   picks higher R). The V9 mechanism itself (real R sweep, real terminal_penalty override, real lambda
   blend) was correct all along; only the upstream cost figure it consumed was wrong. Re-verified, not
   assumed — same discipline as S1c-04's 2,716→713 correction.

**`roster_size` scope**, discussed with the user 2026-08-07: this story's own acceptance criterion names
three sweep axes; only two are real. `cfg.population.roster_size` has exactly one consumer in the entire
codebase — a print statement in `config show` — confirmed by grep, not inferred. The real roster is
always the fixed 112-crew mock corpus regardless of this value, so sweeping it would change nothing.
Making it real needs the mock corpus generator to emit multiple population sizes — materially bigger, out
of this story's scope, and not invented here. The CLI now prints an explicit `[NOTICE]` saying so on
every real `gate v9` run rather than silently reporting a flat, meaningless `roster_size` axis.

`gate v9` (CLI) was previously entirely unwired — `args.gate_id == "v9"` had no dispatch branch at all,
so it fell through to the unknown-`gate_id` error. Added it: builds the real `r_lookup` via
`build_r_star_lookup`, prints the real simulation-count/`roster_size` notices, then
`run_v9_gate`/`print_v9_report`. At the default `--scenarios 20`, `gate v9` runs 5 policies × 4 valid
`terminal_penalty` values × 20 scenarios = 400 real simulations (~7 minutes) — far past other gates'
≤60s manual-check convention, an inherent cost of a real 2-axis sweep, not something to fake down.
`--scenarios 3` (used for this story's own local verification) still ran end-to-end and correctly
reported `[STABLE]`, R\*=4.

---

## ✅ [DONE] S1d-05b — Fix v9_sensitivity.py's ALLOWLIST gap without touching S1d-05's blocked scope
**Size:** `S` | **Depends on:** S1d-05 | **Spec:** §9.2

**Backlog-integrity fix, 2026-08-07.** `test_no_numeric_constant_outside_configs` (§4.4) was failing on
`src/crewsim/gates/v9_sensitivity.py` (8 offenders). S1d-05 itself is correctly `status: blocked` —
`lambda_risk_dial` has no real objective-blend consumer, and that is **not** invented here. Split the 8
offenders by what they actually are:

1. `default_mock_r`'s `0.1`/`1.5`/`4.0` — its own comment already says *"a completely hypothetical
   relationship for demonstration,"* only reached when no real `mock_r_function` is injected (both
   existing tests inject their own) — allowlisted, pointing at S1d-05's blocked status.
2. The findings-list truncation (`3`), report separator width (`55`), and middle-sample-row index
   (`2` in `surface[len(surface)//2]`) — presentation, same category as `profile_html.py`'s styling
   entries — allowlisted.
3. The instability threshold (`max(rs) - min(rs) > 2`, appearing twice) is **not** presentation and
   **not** part of the mock — it's the gate's actual PASS/FAIL decision boundary (matches this story's
   own "Fails if: R\* moves materially"), live in both currently-passing tests regardless of which
   R-function is used. That one does not belong on the allowlist: added
   `sensitivity.instability_threshold: 2` to `configs/base.yaml` and `SensitivityConfig` (`config.py`),
   read via `cfg.sensitivity.instability_threshold` in both call sites instead of a literal `2`.

### Verification
*   🤖 **Automated:** `pytest tests/gates/test_v9_sensitivity.py && pytest tests/test_config.py -k allowlist`
*   🙋 **Manual:** none — allowlist entries plus one config migration, no behavior change
    *   **Fails if:** `default_mock_r` is implemented for real here — that is S1d-05's own blocked
        deliverable, not this story's

