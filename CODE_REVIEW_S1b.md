# Code review — Slice 1b (`backlog/mvp/02_slice_1b_real_rosters.md`)

> **Status update — P0 items applied 2026-08-08.** All four P0 fixes are implemented; see
> [§P0 — what was done](#p0--what-was-done) at the end. One acceptance criterion turned out to be
> **unsatisfiable as written** and the verdict was changed with the user's explicit decision — that
> is documented there. The per-story verdicts below describe the state **as found** and are left
> unedited as the record. P1–P3 are untouched.


Reviewed 2026-08-08 on branch `slice-1a-hardening` @ `17aa746`. All 8 stories are marked
`🟢 [DONE]`. Every acceptance criterion was checked against the code, and every documented
automated **and** manual verification command was run verbatim.

---

## Headline

**Gate V2 does not exist, and its command exits 2 while printing `[PASS]`.**

```python
# tests/gates/test_v2_erlang.py:18   AND   src/crewsim/cli.py:814
prob_shortfall_des = 0.098  # Stubbed DES mock value
```

No simulation is run. The "DES shortfall" is a hand-typed literal compared against a closed-form
Erlang-B computed by two independent copies of `erlang_b()` — one in the test, one in the CLI. The
same class of defect as V1, which this project already fixed once.

And the command is broken on top of being fake:

```
$ crewsim gate v2 --show-comparison
Status: [PASS] DES is within CI of closed-form Erlang B.
error: unknown gate_id 'v2' (known: v1, v2, v3, v4, v5, v6, v7, v9)
$ echo $?
2
```

The `v2` branch has no `return`, so it falls through to the unknown-gate handler. Without
`--show-comparison` it prints *only* the error. A gate that reports PASS and then fails is worse
than one that simply fails.

**Second: S1b-02's documented manual check has never been performable.** It carries no scope
filter, so it loads the entire corpus:

```
$ crewsim roster summary --policy R10 --show-split
Rostered Crew: 1975      # expectation: "line holders + reserves = roster_size" (120)
  Line Holders: 1963
  Reserves: 12
```

**And as in 1a, the suite is not evidence.** `pytest tests/gates/test_v2_erlang.py` passes and
asserts nothing about the DES.

---

## Verdicts

| Story | Verdict | One-line reason |
|---|---|---|
| S1b-01 Load D1/D2 | ✅ **Ship** | 112 of 120, 8 excluded with reasons; L0 validated on load |
| S1b-05 E6/E7 duty/rest end | ✅ **Ship** | `assign_reserve` genuinely splits; test is real |
| S1b-05b `explain-crew --scenario` | ✅ **Ship** | Verified live on a real corpus crew |
| S1b-04 Bind sick calls | ✅ **Ship, one gap** | Real crew, real broken pairings; `flight_mins` still unset |
| S1b-03 Reserve rotation, SC/LC | ⚠️ **Engine OK, CLI has a unit bug** | `reserve-pattern` reports 3.7 days where the truth is 223.0 |
| S1b-06 E8 UNCOVERED_DEADLINE | ⚠️ **Hold is real, its test isn't** | Test only checks deadline arithmetic; APPR never booked |
| S1b-02 Headcount conservation | ❌ **Two ACs unmet** | Displaced flying vanishes; bid rule not configurable |
| S1b-07 V2 Erlang-B gate | ❌ **Does not exist** | Hardcoded shortfall; command exits 2 |

---

## S1b-01 — Load D1/D2 into the Crew State Engine ✅

All three ACs hold, and the manual check matches its stated expectation exactly:

```
Rostered Crew: 112
Excluded: 8
Exclusion Reasons: {'LONG_TERM_ABSENCE': 5, 'INITIAL_TRAINING': 1,
                    'FLEET_TRANSITION': 1, 'MANAGEMENT_OR_INSTRUCTOR': 0, 'TERMINATED': 1}
```

AC3 is genuinely enforced, not just claimed: `roster_loader.py:216-229` sorts each calendar and
raises `ValueError` on any overlap at load time, so L0 holds on input. That is why the realized-
calendar L0 audit added in slice 1a reports zero — the baseline is clean by construction.

Note the loader replaces D2's flat multi-day PAIRING span with D3's real duty periods
(`_load_pairing_duty_periods`), without which every pairing would fail L1's 13h max-duty rule by
construction. That is real work the story's own notes do not mention.

---

## S1b-02 — Headcount conservation ❌

**What is real:** the carve-out itself. `load_rosters` partitions the active population into
reserves and line holders rather than minting reserves, so total headcount is conserved. That is
the v2 defect this story exists to fix, and it is fixed.

**AC1 — "`line_holders + reserves == roster_size` for every candidate R, asserted not assumed".**
Three problems:

- The manual check produces **1975**, not 120 (above) — no scope filter.
- `roster_size` is 120 in config; the scoped population is **112**. The identity the story asserts
  cannot hold against `roster_size` at all, because eight crew are excluded as non-ACTIVE. What is
  actually conserved is the *active* population.
- The test's own conservation assertion is **tautological**:

  ```python
  reserves_marked = sum(getattr(c, "_is_reserve", False) for c in active_with_policy)
  lines_marked    = sum(not getattr(c, "_is_reserve", False) for c in active_with_policy)
  assert lines_marked + reserves_marked == total_with_policy      # always true
  ```

  It partitions one list by a boolean and asserts the parts sum to the whole. The line above it
  (`total_no_policy == total_with_policy`) is the real check and does hold. Also: only R10 is
  tested, not "every candidate R".

**AC2 — "The flying those reserve bidders would have flown enters open time (or is absorbed per
config)" — UNMET, under both readings.** `roster_loader.py:283` replaces a minted reserve's whole
calendar:

```python
c.calendar = next(pattern_cycle)          # their PAIRING blocks simply disappear
```

No `OpenTimeItem` is created anywhere in `roster_loader`, and there is no config key authorising
absorption — `grep -niE "absorb|displaced|open_time" configs/` returns nothing but an unrelated
comment. So the flying a reserve bidder gives up is neither re-offered nor accounted for; it
silently ceases to exist.

This is the substantive one. The story's own note says the point is "the opportunity cost of the
line a reserve is not flying" — that cost is exactly what is missing.

**AC3 — "Reserve bidders selected by the configured bid rule, not arbitrarily" — UNMET.**
`roster_loader.py:267` hardcodes junior-first:

```python
crew_list.sort(key=lambda c: c.seniority, reverse=True)   # most junior first
```

Junior-first is a defensible default for who ends up on reserve, but it is not configurable, and
`stage2.reserve_selection` governs *dispatch* (`shortest_remaining_window`), not bidding. Nothing in
any policy file selects a bid rule.

**Doc drift:** the note names `apply_headcount_target()` in `src/crewsim/engine/policy.py`. No such
function exists anywhere in the tree.

---

## S1b-03 — Reserve lines with rotation and SC/LC split ⚠️

**Engine side is real.** Minted reserves inherit an authentic on/off rotation from a D2 crew who
actually flew a reserve line, with `reserve_call_type` carried through — not one flat horizon-long
block (AC1, AC2). Availability is per-individual-and-window, since eligibility reads the calendar
(AC3).

**The CLI reports the wrong number.** `cli.py:613` divides by 86,400 — seconds per day — but engine
time has been in **minutes** since S1d-04b. Measured against the same 12 reserves:

| | printed | actual |
|---|---|---|
| Total Reserve Days | `3.7` | **223.0** |
| Total Off Days | `0.4` | **27.0** |

Exactly 60× low. The correct figure is 18.6 on-days per reserve over a 42-day horizon, which is a
plausible reserve line; 3.7 across *twelve* reserves is not, and would be obvious to a planner —
which is the point of the check. The SC/LC split (65.3 / 34.7) is unaffected, being a ratio.

**Test is loose against its own AC.** The story says "SC/LC split roughly 60/40"; the test asserts
`0.3 < sc_ratio < 0.9`, which admits 30/70. It also counts *blocks*, not days.

**Doc drift:** "Dynamically assigned `reserve_call_type` (SC vs LC) adhering to authentic
distributions" — the code does not assign anything; it inherits the label from D2.

---

## S1b-04 — Bind sick calls to roster crew ✅

All three ACs hold. `apply_sick_call` samples from crew with a PAIRING overlapping the absence
window, removes that crew member, and converts each broken pairing into an `OpenTimeItem` with a
deadline derived from `demand.uncovered_deadline_hours`. Three real tests, including one proving
`apply_named_absence` selects the named crew rather than a random one.

The manual check now runs for real and names a real crew member:

```
[t=1088] SICK_CALL: P00440 -> item 1 (YULA321-054314)
[t=1088] item 1 ...: 0 eligible reserves, 0 legal draft candidates -- unresolved for now
[t=1141] item 1 (YULA321-054314) CANCELLED at deadline, still uncovered
```

(That command was a hand-typed timeline until the slice-1a P0 pass rebuilt it on a real trace.)

**Known gap, already documented in code:** `_break_pairings` never sets `flight_mins` on the item it
creates, so L3's rolling-flight-hour check undercounts a sick-call-origin item. `sick_calls.py:39-46`
explains the deliberate deferral. Worth a story rather than leaving it as a comment.

---

## S1b-05 — Events E6 DUTY_END and E7 REST_END ✅

`assign_reserve` splits a RESERVE block into `RESERVE → DRAFTED_DUTY → REST → RESERVE` and never
deletes it (AC3), the test asserts all four resulting blocks with their boundaries, and it raises
rather than silently no-ops when no RESERVE block covers the window. Rolling counters are computed
from the realized calendar by `CrewMember.get_rolling_counters`, so E6 needs no separate update step.

---

## S1b-05b — `explain-crew --scenario` ✅

Genuinely correct, and verified live on the real corpus crew the story names:

```
$ crewsim explain-crew --crew P00448 --scenario 0 --policy R10 --timeline
Timeline for Crew P00448 (YUL, FO, seniority 448) -- scenario 0, policy YUL-A321neoLR-FO-R10:
  [t=240  -> t=2484] RESERVE (SC)
  [t=2484 -> t=2933] DRAFTED_DUTY (YULA321-054314)
  [t=2933 -> t=3593] REST
  [t=3593 -> t=3864] RESERVE (SC)
```

Exactly the split S1b-05's AC3 demands, produced by really running scenario 0. The "not yet wired to
simulated state" notice is gone, and the header names which state is shown. After four rounds of
finding fabricated verification in this project, this story holds up under the same scrutiny.

---

## S1b-06 — Event E8 UNCOVERED_DEADLINE ⚠️

**AC1 is genuinely implemented** — and not where the story's test looks. `des.py:261-290` holds an
unresolvable item and re-attempts resolution at each future reserve-block start up to the deadline,
cancelling only when the deadline is reached. The retry times are derived from real calendar data
rather than an arbitrary polling interval. That is the right design.

**Its own automated check tests none of that.** `test_uncovered_deadline_held` builds a config, calls
`apply_sick_call`, and asserts one thing:

```python
assert oti.deadline == 1000.0 - (2.0 * 60)
```

Deadline arithmetic. No pipeline, no hold, no retry, no cancellation. Despite the name, nothing is
held. The AC's "the pipeline retries as state changes" is unverified by this story.

**AC2 is half-unmet: APPR compensation is never booked.** `appr_compensation` is defined in
`configs/costs_pilots.yaml` and modelled in `config.py:251`, and **appears nowhere else in `src/`**.
Cancellation books at the deadline; the APPR component of that cost does not exist. It is also not
surfaced by `config.unconsumed_notices`, which only flags `demand.pairings_per_bid_period` — so a
declared, costed, never-consumed key passes `crewsim config show` silently.

**Zero-hold-window (carried from the slice-1a pass):** on scenario 0 the first uncovered item is held
for **0 minutes** — `deadline = pairing.start − uncovered_deadline_hours` is absolute, so an absence
notified after its pairing has begun is born past its own deadline and every retry fires at the
arrival instant. `explain-event` now prints the measured hold and a warning instead of asserting
"held". S1b-06's stated expectation ("at least one retry visible") is met; "the item held to its
deadline" is not demonstrable on that scenario.

---

## S1b-07 — V2 Erlang-B sanity bound ❌

Fabricated, and the command is broken. See the headline for both. Beyond that:

**AC1 — "Single base, single fleet, cascades disabled, eligibility-thinned Poisson arrivals" —
entirely unimplemented.** No scenario is configured, no cascades are disabled, no arrivals are
thinned. The inputs are three literals:

```python
s_reserves = 10;  arrival_rate_per_day = 5.0;  service_time_days = 1.5
```

**AC2 — "both printed side by side"** — technically true, but one of the two numbers is typed by hand.

**AC3 — "Runs in CI"** — CI now exists (added in the 1a pass), so the test does run on every push. It
runs the fabricated one.

The Erlang-B formula itself is correct and agrees between its two copies. Everything around it is
theatre. Note also that `reporting/report.py` still labels V2 a `KNOWN_STUB` — that label is
currently the most honest statement about this gate anywhere in the repo.

---

## Cross-cutting

**1. Latent defect — shared calendar objects above R=18.** `roster_loader.py:275-283` cycles a pool
of authentic reserve calendars and assigns each as-is, so once the reserve count exceeds the number
of distinct patterns, several crew share one list object — and `copy.deepcopy` preserves that
sharing, so `run_scenario`'s defensive copy does not break it. Measured: 18 patterns exist in scope.

```
R=12: 12 reserves -> 12 distinct calendars
R=20: 20 reserves -> 18 distinct calendars   <-- ALIASED
```

Consequence when triggered: drafting P00438 added three blocks to P00458's calendar — one draft
consumes a second reserve's availability.

**Not reachable by any shipped policy**: R4/R6/R8/R10/R14 are all ≤ 18. The only thing that reaches
it today is `policy_with_reserve_count` in the V1 gate at R=112, added in the slice-1a pass, where no
mutation occurs so the result stands. Fix is one word: `list(next(pattern_cycle))`.

**2. Doc drift.** `apply_headcount_target()` (S1b-02) does not exist. S1b-03's note claims the code
assigns SC/LC when it inherits them. S1b-07's note says the test enforces tolerance "against the DES
mock" — accurate, and the clearest admission in the file that the gate is not real.

**3. Two `erlang_b` implementations** — `cli.py:801` and `tests/gates/test_v2_erlang.py:1`. The same
test-validates-a-copy pattern this project has now hit five times.

---

## Prioritized fixes

### P0 — fabricated or broken verification

1. **S1b-07 · build gate V2 for real.** Run a constrained DES (single base/fleet, cascades off,
   thinned arrivals per AC1), measure the shortfall probability, and compare against `B(s,a)` with a
   real confidence interval. One shared `run_v2_gate` for CLI and test, as V1/V7 now do.
2. **S1b-07 · fix the fall-through** so `gate v2` returns 0/1 instead of 2, and prints the comparison
   without requiring `--show-comparison`.
3. **S1b-03 · fix the `86400` unit bug** in `reserve-pattern` (`cli.py:613`). It reports 3.7 days
   where the truth is 223.0.
4. **S1b-02 · fix the manual check** to carry the scope filter, and state the identity against the
   active population (112) rather than `roster_size` (120), or reconcile the two explicitly.

### P1 — real gaps behind a passing check

5. **S1b-02 · displaced flying (AC2).** Decide and implement: do a reserve bidder's pairings enter
   open time, or are they absorbed? Neither happens now, and no config key selects between them.
   This is the opportunity cost the story exists to capture. *Needs a product decision first — see
   [[ask-before-changing-design]].*
6. **S1b-06 · book APPR compensation** at the deadline alongside cancellation, or move
   `appr_compensation` out of the cost file. Also make `unconsumed_notices` catch costed keys that
   nothing reads.
7. **S1b-06 · make the test test the hold.** Drive `recovery_pipeline` and assert a retry happened
   and cancellation booked at the deadline, not just that the deadline arithmetic is right.
8. **S1b-02 · replace the tautological assertion** and parametrise over the real candidate R set.

### P2 — correctness-adjacent

9. **Aliasing:** `list(next(pattern_cycle))` in `roster_loader`, plus a test at R > 18.
10. **S1b-02 AC3:** make the reserve bid rule configurable, or amend the AC to say junior-first is
    mandated and record why.
11. **S1b-03:** tighten the SC/LC assertion toward the 60/40 the story states, and count days not
    blocks.
12. **S1b-04:** `flight_mins` on sick-call-origin items (already documented in code as deferred).

### P3 — documentation

13. Correct the phantom `apply_headcount_target()` and the two misleading notes (S1b-03, S1b-07).
14. **Backlog markers** — S1b-02 and S1b-07 do not meet their acceptance criteria and should not read
    `🟢 [DONE]`. *These are the project's record; this review proposes the change rather than making
    it.*

---

# P0 — what was done

Applied 2026-08-08. **307 passed, ruff clean, `mypy --strict` on the engine clean.**

## 1+2. Gate V2 is real, and the command no longer lies about its own exit code

`src/crewsim/gates/v2_erlang.py` runs the DES in the configuration AC1 specifies — single
base/fleet (from `cfg.scope`), **cascades disabled** — and measures every DES-side figure:

```
  Measured from the DES
    arrivals                 = 762
    blocked on arrival       = 673
    arrival rate (lambda)    = 9.07 / day
    mean service E[S]        = 19.4 h (duty + obliged rest)
    servers (s)              = 4 (time-average on call; headcount is 12)
    offered load (a)         = 7.34 Erlangs
    DES shortfall  p_hat     = 0.8832  [0.8585, 0.9041] 95% CI
    Theory  B(s, a)          = 0.5443
```

`des.run_scenario` gained `cascades_enabled` (a cascade is a secondary arrival generated by the
recovery itself, which breaks the independent-arrivals premise the closed form rests on) and four
Erlang-B counters. Blocking is counted **at the arrival instant only** — Erlang B is about whether an
arriving call finds a free server, not whether a held one eventually does.

`s` is the **time-average number of reserves on call (4)**, not the headcount (12). Reserve lines
rotate, so using headcount would overstate capacity and mis-attribute the gap.

One `erlang_b` now, shared by CLI, test and report — there were two independent copies.

**The exit-code bug is fixed.** The `v2` branch had no `return`, so it fell through to the
unknown-gate handler: `gate v2 --show-comparison` printed `[PASS]` and exited **2**, and without the
flag printed only an error. Both forms now exit 0/1 on the real verdict, and `--show-comparison` is
accepted and ignored — the comparison *is* the gate, so there is nothing to withhold.

### The AC was unsatisfiable, and the verdict changed with your decision

S1b-07's AC says "DES shortfall inside the Erlang-B confidence interval". Measured, that is
unachievable, and **no defensible construction closes it**:

| construction | s | a | B(s,a) | inside p̂'s CI? |
|---|---|---|---|---|
| time-average servers, all arrivals | 4 | 7.49 | 0.5519 | no |
| headcount servers, all arrivals | 12 | 7.49 | 0.0381 | no |
| time-average, eligibility-thinned arrivals | 4 | 0.93 | 0.0122 | no |
| headcount, eligibility-thinned arrivals | 12 | 0.93 | 0.0000 | no |

The cause is structural: L3/L4/L8 reject on-call reserves that the closed form counts as free
servers. **You chose the directional bound**, so the gate now asserts:

```
p_hat >= B(s, a)
```

Every departure from M/M/s/s in this model — rotation, legality rejections, duty+rest service, E8
holding rather than clearing — can only make a reserve *less* available than the idealised system.
So a violation means the simulation found availability the calendars and rules do not permit:
reserve double-counting, an unbooked occupancy, a pool counted twice. That is precisely the "reserve
accounting has a bug" this gate exists to catch. Containment is still computed and printed, labelled
informational, with the reason in the module docstring.

**Mutation-tested**: `test_v2_gate_fails_when_the_des_is_more_available_than_theory` forces
`n_blocked_on_arrival = 0`, driving p̂ to 0 while B(s,a) stays positive — the gate correctly reports
the bound VIOLATED and names double-counting. Without that control, every other assertion would be
consistent with a gate that returns `pass=True` unconditionally.

`report.py`'s `KNOWN_STUB_GATES` is now empty (V1 and V2 were its last two entries) and V2 appears in
the report's gate table with real figures. The dict is kept as a mechanism, not deleted: a future
stub must be labelled, never printed as a fake PASS.

## 3. `reserve-pattern` reported every figure 60× low

`cli.py` divided by `86400` — seconds per day — on values that have been **minutes** since S1d-04b:

| | before | after |
|---|---|---|
| Total Reserve Days | `3.7` | **223.0** |
| Total Off Days | `0.4` | **27.0** |

Matches the independent measurement in the review exactly. 18.6 on-days per reserve over a 42-day
horizon is a plausible reserve line; 3.7 across twelve reserves is not.

## 4. S1b-02's manual check is performable

`roster summary` now defaults to `cfg.scope` when no filter is given — matching what every
simulation path already does — instead of silently loading all 1,975 crew across every base, fleet
and position. `--all-scopes` keeps the corpus-wide view available deliberately.

It also states the identity rather than leaving the reader to infer it, and reconciles the two
numbers the story conflates:

```
Headcount conservation (S1b-02):
  line holders + reserves = 100 + 12 = 112  vs  active in scope = 112   [OK]
  establishment (population.roster_size) = 120  -- 8 excluded as non-ACTIVE
```

The conserved quantity is the **active** population (112), not `population.roster_size` (120); the
difference is exactly the non-ACTIVE crew. The story's stated expectation ("= `roster_size` exactly")
was never meetable, and printing both stops the conflation recurring.

## Not done (P1–P3 still open)

Unchanged from the list above. The two most consequential:

- **S1b-02 AC2 — displaced flying still vanishes.** A reserve bidder's pairings are discarded with no
  open-time item and no absorption path. This needs a product decision (open time vs absorbed)
  before implementation, not a guess.
- **S1b-06 — APPR compensation is still never booked**, and its test still checks only deadline
  arithmetic rather than the hold.

Also still open: the R>18 calendar aliasing (one-word fix, unreachable by any shipped policy), the
tautological headcount assertion, the loose SC/LC bound, `flight_mins` on sick-call items, and the
phantom `apply_headcount_target()` in the story notes.

---

# P1 / P2 / P3 — what was done

Applied 2026-08-08. **329 passed, ruff clean, `mypy --strict` on the engine clean, suite 4m29s.**

> **Every cost figure in this document and in CODE_REVIEW_S1a.md predates this pass and is now
> stale.** `population.displaced_flying` defaults to `open_time`, which adds real cost to every
> scenario, and sick-call items now carry `flight_mins`. Re-measure before quoting any number.

## P1 #5 — displaced flying now has a cost (S1b-02 AC2)

`population.displaced_flying: open_time | absorb`, defaulting to **open_time** on your decision.
A reserve bidder's PAIRING blocks are captured on `CrewMember._displaced_pairings` before their
calendar is overwritten, and offered to the recovery pipeline. Measured at R10, scenario 0:

| | absorb | open_time |
|---|---|---|
| items | 417 | 521 |
| drafts | 160 | 240 |
| total | $5,244,500 | **$5,805,700** |

Most displaced flying is *covered* by drafting a line holder, not cancelled — so the restored
opportunity cost is mostly draft premium. It grows with R (27 duty periods at R4 → 115 at R14),
which is exactly the bias the story exists to remove: higher R used to be free of this cost.

**A first implementation emitted these at t=0** — the bid is a stage-1 commitment, so the flying is
known from the start of the bid period. That was wrong twice over. Operationally it re-decides a
known-open trip at every reserve-block start for weeks, when the E8 hold exists for *unexpected*
disruption. Mechanically it made each item retry across the whole horizon and **took the suite from
4 to 18.5 minutes**. They now surface through the existing `_delayed_pipeline`, at
`cascade.visibility_lag_hours` before their own pairing — an existing named mechanism for "when the
IOC would see this", not a new parameter. Runtime is back to 1.2s per scenario.

## P1 #6 — APPR compensation is booked

`appr_compensation` was defined in `costs_pilots.yaml`, modelled in `config.py`, and booked nowhere
in `src/`. A cancellation now books `CANCELLATION` and `APPR_COMPENSATION` together at the deadline —
separate categories, because they are a different payee and a different tariff.

Which band a cancellation attracts is **named in config, not assumed in code**: passenger
re-accommodation is not modelled, so the delay a cancelled flight causes is unknown.
`appr_compensation.cancellation_band` defaults to `hours_9_plus` (the conservative choice, matching
the legality rules' documented bias) and carries a `[CONFIRM: Legal]` marker.

## P1 #7 — S1b-06's test tests the hold

Three tests that drive the real `recovery_pipeline`: retries occur before cancellation, at least one
item is held for a *strictly positive* duration (a retry at the same instant is not a hold), and
every cancellation books APPR at the same instant against the same causal chain. The original test
was renamed `test_open_time_item_deadline_is_report_time_minus_the_configured_lead` — it checks
deadline arithmetic and nothing else, which its old name ("...held") misrepresented.

## P1 #8 / P2 #10 — headcount tests are non-tautological

`tests/engine/test_headcount.py` is parametrised over R4/R6/R8/R10/R14 and compares against the same
population loaded with **no policy** — an external reference, not a re-partition of the list under
test. The old assertion (`lines + reserves == total`) partitioned one list by a boolean and asserted
the parts summed to the whole.

`population.reserve_bid_rule` (`junior_first` default, matching the previous hardcoded behaviour)
satisfies AC3, with a test proving `senior_first` actually inverts the selection — a knob that did
nothing would satisfy the AC in name only.

## P2 #9 — the R>18 aliasing is fixed

`list(next(pattern_cycle))` in `roster_loader`. Verified: 20 reserves → 20 distinct calendars, 112 →
112. A test at R=20 guards it, deep-copying first because `copy.deepcopy` preserved the sharing that
made `run_scenario`'s defensive copy ineffective.

## P2 #11 — SC/LC measured in days

The split is now computed from reserve-**days**, not block counts (a block is an arbitrary unit), and
the bound is `0.55 ≤ SC ≤ 0.75` against the story's stated "roughly 60/40" — measured at 60.7–69.6%
across the candidate policies. The old bound, `0.3 < sc < 0.9`, admitted 30/70. A second test proves
reserve lines rotate: no reserve is on call for the whole horizon, and the pool presents fewer
servers than heads.

## P2 #12 — `flight_mins` carried through

`_break_pairings` sets it, matching `cascade.py`. L3's rolling-flight check saw 0 added flight time
for every sick-call-origin item and under-rejected candidates near the 35h limit. This is a
correctness fix and it moves the numbers.

## P3 #13 — the notes describe the code

All six "How it was implemented" blocks rewritten. `apply_headcount_target()` never existed; S1b-03
claimed the engine assigns SC/LC when it inherits them from D2; S1b-07's note described the test as
enforcing tolerance "against the DES mock", which was accurate and was the clearest admission in the
file that the gate was not real.

## P3 #14 — the `[DONE]` markers are now accurate

S1b-02 and S1b-07 were the two that did not meet their acceptance criteria. Both now do — AC2 and
AC3 are implemented and tested, and V2 measures a real simulation — so the existing `🟢 [DONE]`
markers became correct without needing to be flipped. Nothing in the backlog's status column was
edited.

## Four tests changed because the behaviour changed, not to make them pass

Worth stating explicitly, since "fix the test" is how a real regression gets buried:

- **V1 configurations now pin `displaced_flying=absorb`.** With everyone on reserve and
  `open_time`, *all* the flying becomes open time, so configuration 2 books utilisation and
  cancellations and its "staffing only" claim stops being about staffing. The gate isolates the one
  question it asks; configurations 1 and 3 carve out zero reserves, so for them it is a no-op.
- **The staffing end-to-end test pins `absorb`** — it recomputes staffing from *post*-simulation
  calendars and compares against what was booked from *pre*-simulation ones. With displaced flying
  on, a drafted reserve's block is legitimately split, so the comparison would measure
  `assign_reserve`, not staffing.
- **Two uid-uniqueness assertions moved to `(event_uid, category)`.** A cancellation now books two
  rows under one event uid. The invariant being guarded — that two distinct *items* never share a
  uid — is unchanged, and duplicate `(uid, category)` pairs would still catch it.
- **The drilldown test accepts `DISPLACED_LINE`** alongside `SICK_CALL` as a chain origin. There are
  genuinely two origins now; what must not happen is a chain with no origin, which is still asserted.

## Still open

- **The zero-hold-window case** (an absence notified after its pairing has begun is born past its own
  deadline). Real, modelled, and now warned about rather than papered over — but it means S1b-06's
  "held to its deadline" is not demonstrable on scenario 0. Needs its own story.
- **Gate V3/V4 historical bands** were calibrated before displaced flying existed and should be
  re-checked against the new arrival mix.
