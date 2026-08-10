# Code review — Slice 1c (`backlog/mvp/03_slice_1c_eligibility.md`)

Reviewed 2026-08-08 on branch `slice-1a-1b-hardening` @ `90b578c`. Six stories (the header says five;
S1c-04b was split out later). Every acceptance criterion checked against the code, and every
documented automated **and** manual verification command run verbatim, including the two at their
full documented scale (200 and 100 scenarios).

---

## This slice is materially better than 1a and 1b

Worth saying first, because it changes where review effort is worth spending. Four of six stories
hold up under exactly the scrutiny that found fabricated evidence in **every** slice-1a gate. There
is no hardcoded PASS text here, no stubbed constant standing in for a measurement, no test asserting
a literal against itself.

The prior sessions' "Backlog-integrity fix" notes describe real work, and I verified the substance of
each: the L8 call-time-vs-report-time bug, the L5 span-deduplication bug (2,716 → 713), the
`find_l5_regressions` containment fix, and the pool-covers-the-whole-duty-window fix are all present
in the code and correct. Those notes are accurate — which after three rounds of doc drift is itself a
finding.

Two acceptance criteria are genuinely unmet. Both are about *surfacing*, not about the engine.

---

## Headline

**S1c-05 AC3 is violated, and the story's own commands demonstrate it.** The AC reads: "**Every run
surfaces this**, not just the gate command — a number failing V3 must never reach a planner
silently."

Running S1c-01's documented 200-scenario check produces this, in full:

```
  mean = 0.041
Policy YUL-A321neoLR-FO-R10 -- 200 CRN scenario(s), master_seed='master'
  E[cost]  (measured window) = $2,866,876.75
```

No mention of V3. Meanwhile `gate v3 --window holdout` says:

```
Historical Band: [0.007, 0.012] (Mean: 0.009)
Simulated Mean : 0.040
Verdict: [FAIL]
```

So a planner runs `crewsim run`, receives a $2.87M cost figure, and is told nothing about the model's
central eligibility claim failing its holdout gate by 4.5×. That is precisely the failure mode the AC
was written to prevent. V3 is surfaced only under `run --assert-invariants`, by `gate v3`, and in the
HTML report — never on a plain `run`, and never by `compare`.

---

## Verdicts

| Story | Verdict | One-line reason |
|---|---|---|
| S1c-02 Rule L8, notification time | ✅ **Ship** | Config-driven, applied at call time, binding test — all real |
| S1c-03 Rules L3/L4, rolling limits | ✅ **Ship** | Counters genuinely roll; verified accumulate *and* decay on real data |
| S1c-04 Rule L5, duty-free day | ✅ **Ship** | Both paths, hypothesis suite, delta invariant PASSes at 100 scenarios |
| S1c-04b L5 conservative-bias finding | 🚫 **Blocked, correctly** | Parked pending real data by explicit user decision — not a defect |
| S1c-01 Eligibility engine FULL | ⚠️ **AC4 unmet** | REDUCED mode is unreachable and its refusal is never invoked |
| S1c-05 V3 gate on holdout | ⚠️ **AC3 unmet** | A plain `run` never surfaces V3; the FAIL itself is correct and intended |

---

## S1c-01 — Eligibility engine FULL ⚠️

**AC1 met, and correctly.** `eligibility.py:38` requires `b.start <= item.start and b.end >= item.end`
— the RESERVE block must contain the whole duty window, not merely the report instant. This is the
fix the story's own integrity note describes, and `test_pool_requires_coverage_of_whole_duty_window`
pins it.

**AC2, AC3 met.** Eligible = pool ∩ `is_legal_assignment`. The full per-event distribution is retained
in `self.samples` (with sample times, so S1e-01 can window it) rather than a running mean. The manual
check produces a genuine, non-degenerate histogram over 136,263 events:

```
  [0.0, 0.1) 123263 ##################################################
  [0.2, 0.3)   3648 #
  [0.9, 1.0)   1734 #
  mean = 0.041
```

**AC4 — "`REDUCED` mode still available, and refuses to produce a recommendation" — UNMET on both
halves.**

```python
# des.py:161 -- the ONLY EligibilityEngine construction in src/
self.elig = EligibilityEngine(mode="FULL", cfg=cfg)
```

The mode is a hardcoded literal. `cfg.mode` is read in exactly one place in the entire package —
`cli.py:185`, which *prints* it in `config show`. Setting `mode: REDUCED` in `base.yaml` changes
nothing; the engine still runs FULL. **REDUCED is unreachable from any real path.**

And `check_recommendation_safe()` is called only from `tests/engine/test_eligibility.py`. Nothing in
`src/` invokes it, so the refusal never fires.

**The direction of the accident is safe** — you cannot obtain a REDUCED-mode recommendation because
you cannot obtain REDUCED at all. This is not a live hole. But `base.yaml` carries

```yaml
mode: FULL   # REDUCED is for smoke tests only — never a recommendation
```

documenting a mode that does not exist, and a guard written specifically to prevent an unsafe
recommendation is wired to nothing.

---

## S1c-02 — Rule L8, reserve notification time ✅

All three ACs hold. Limits come from `configs/base.yaml → legality` (AC1). Classification uses the
reserve block covering **`now`**, the call time, not `item.start` (AC2) — the bug the story's
integrity note records, with `test_l8_classification_uses_call_time_not_report_time` as the
regression guard, and the note is right that the pre-existing `test_l8_notice_time` could not have
distinguished the two behaviours. AC3's binding-rule fixture is real:

```
[R002 -> TS156] ILLEGAL_L8: Insufficient notice (1.0h < 12.0h for LC)
                (called at t=900, report t=960, 1.0h notice)
```

The output states the resolved call time, report time and notice duration, so the same-day `--call-at`
convention is visible in the result rather than buried in a comment. That is the right instinct.

---

## S1c-03 — Rules L3 and L4, rolling limits ✅

AC1's limits are config-driven. AC2 verified on real corpus data — the counters accumulate *and*
decay:

```
  t=357  (after PAIRING): rolling 7d duty=10.4h flight=7.7h
  t=2832 (after PAIRING): rolling 7d duty=20.1h flight=14.8h  (accumulated)
```

and `test_cli.py` additionally asserts a drop greater than 30h across P00002's real >7-day gap, so
"the number went down slightly" cannot pass for a rolling window.

AC3 ("part of `L_c(t)`, checkpointable with it") is satisfied structurally rather than by a separate
mechanism: `get_rolling_counters` derives from the crew's calendar, so there is no parallel counter
state that could drift from it or be missed by a checkpoint. That is a better answer than a stored
counter, and the story's note says so.

---

## S1c-04 — Rule L5, one duty-free day per rolling 7 ✅

AC1 (both paths) is satisfied by placing L5 inside `is_legal_assignment`, which gates reserve
assignment and drafting alike. AC2's hypothesis test exists (`test_l5_invariant`) alongside L0's.

The manual check passes at its documented scale:

```
$ crewsim run --policy R6 --scenarios 100 --assert-invariants
PASS: no scenario introduced or extended an L5 streak beyond the pre-simulation baseline
      (11200 crew-scenarios checked; baseline itself already has 126 pre-existing streak(s)
       across 80 crew -- see S1c-04b)
```

The delta-not-count design is the right call and is well documented, including *why* a raw count
would be permanently unable to distinguish a regression from baseline noise. `find_l5_regressions` is
extracted as a testable function with its own unit coverage including a case proving it can fail —
the discipline that was missing throughout 1a.

---

## S1c-04b — L5 conservative-bias finding 🚫 Blocked, correctly

Parked by explicit user decision pending real Air Transat data, on the reasoning that 23.5% measured
against a mock corpus cannot distinguish a real day-off-rule mismatch from the generator's own
duty-spacing pattern. That is sound, the blocker is stated, and S1c-04 is unaffected either way.
Nothing to do; flagged here only so it is not mistaken for an oversight.

---

## S1c-05 — V3 gate on the HOLDOUT window ⚠️

**AC1, AC2 and AC4 are met.** The comparison is against the real reconstructed holdout band, the
verdict is explicit with the gap quantified, and a failure names a suspected mechanism rather than a
parameter to nudge. `gate v3` writes a self-contained Plotly page overlaying both distributions, which
the manual check asks for ("both distributions plotted") and which is easy to skip.

`tests/gates/test_v3_eligibility.py` deserves specific credit: it has both a PASS and a FAIL case, and
derives both from the *real* reconstructed band rather than hardcoding, so it stays a genuine
out-of-bounds case if the corpus is regenerated. That is the shape every gate test in 1a lacked.

**AC3 is unmet** — see the headline. V3 reaches a planner only via `--assert-invariants`, `gate v3`,
or the HTML report. A plain `crewsim run` and `crewsim compare` both print cost figures in silence.

**The FAIL itself is correct and intended.** Recorded user decision (2026-08-07): ship it, do not open
a mechanism investigation, because chasing a gap inside mock data is not worth it before real records
land. V3 reporting FAIL against a real target is the gate working. Not a defect.

**One caveat on the numbers.** The simulated rate now reads 0.040–0.041, against the ≈3.9% the story
records. That is not the same measurement: the historical band was reconstructed before slice 1b's
`displaced_flying` default changed the arrival mix. The direction and the verdict are unchanged, but
the gap's magnitude should be re-derived before anyone quotes it.

---

## Cross-cutting

**The unconsumed-key notice only catches one key.** `config.unconsumed_notices` flags
`demand.pairings_per_bid_period` and nothing else. Two declared, meaningful keys are consumed nowhere:

- `mode` (this slice) — read only by `config show`'s own print statement.
- `appr_compensation` (found in slice 1b, since fixed) — was defined, modelled, and booked nowhere.

That is two instances of the same class. The notice mechanism is special-cased to one key rather than
derived from what the code actually reads, so it cannot catch the next one either. Worth treating as
one problem, not two.

---

## Prioritized fixes

### P0 — an unmet acceptance criterion with a safety rationale

1. **S1c-05 AC3 · surface V3 on every run.** A plain `crewsim run` (and `compare`) must state the V3
   verdict alongside the cost, or refuse to print a cost when V3 fails. The AC's own wording — "must
   never reach a planner silently" — is a safety requirement, and a $2.87M figure currently ships
   with no indication that eligibility fails its gate by 4.5×. *Whether it should warn loudly or
   refuse outright is a product decision; I would not pick that unilaterally.*

### P1 — an AC unmet in a currently-harmless direction

2. **S1c-01 AC4 · make REDUCED reachable and its refusal real,** or delete the mode. Two coherent
   options: honour `cfg.mode` in `des.py` and call `check_recommendation_safe()` on the paths that
   emit a recommendation (`run`, `compare`, `report`, `grid`); or remove `mode` from `base.yaml` and
   `EligibilityEngine` and stop advertising a smoke-test mode that does not exist. Either is
   defensible; shipping a documented mode that silently does nothing is not.

### P2 — the pattern behind it

3. **Make `unconsumed_notices` derive from real usage** rather than naming one key. Even a crude
   AST/grep check over `src/` for each config field would have caught both `mode` and
   `appr_compensation`.

### P3 — documentation

4. **The epic header says "5 stories"; there are six.** S1c-04b was split out later and the count was
   not updated.
5. **Backlog markers.** S1c-01 and S1c-05 do not currently meet every acceptance criterion. The
   remaining gaps are narrow and both are about surfacing rather than engine behaviour, so whether
   that warrants un-marking `[DONE]` is a judgement call — *this review proposes it rather than
   making the change.*

**Not proposed:** rewriting the "How it was implemented" notes. Unlike 1a and 1b, they describe the
code that exists.

---

# P0 — what was done

Applied 2026-08-08. **334 passed, ruff clean, `mypy --strict` on the engine clean.**

## S1c-05 AC3 — V3 is no longer silent

`cli._print_v3_verdict` runs the gate against the distribution the sims already produced, and both
`run` and `compare` now print the verdict **before** the figures it qualifies — the caveat is read
ahead of the number, not after it:

```
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!! GATE V3 FAILED -- simulated eligibility 0.026 vs historical [0.007, 0.012] (holdout)
!! Gap +0.016 over 1,298 events.
!! Suspect mechanism: reserve rotation or L8 notice time (NOT a parameter to nudge).
!! The figures below are UNVALIDATED. Run `crewsim gate v3` for the full report.
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

Policy YUL-A321neoLR-FO-R6 -- 2 CRN scenario(s), master_seed='master'
  E[cost]  (measured window) = $3,249,430.00
```

Cost: one `reconstruct_eligibility` (~0.8s) and **no extra simulation** — the distribution comes from
sims that have already run.

### Why it warns rather than refuses

The review flagged this as a product decision and it resolved itself on inspection: **refusing to
print a cost whenever V3 fails would today produce no output at all, for any policy.** V3 fails by
design against the mock corpus — that is a recorded decision (S1c-05, 2026-08-07), not a bug to fix —
so a hard refusal would make the tool unusable rather than safe.

`run --assert-invariants` keeps its hard failure and non-zero exit. That flag is the explicit "I am
about to trust this" mode, which is the right place for a refusal. Verified: plain `run` exits 0 with
the banner; `--assert-invariants` still exits 1.

If the intent is that *no* cost figure should ever be printable while V3 fails, that is a one-line
change — say so and I will make it.

### Tests

Five, in `tests/test_cli.py`:

- a plain `run` prints both an `E[cost]` **and** a `GATE V3` verdict;
- `compare` does the same;
- when V3 fails the banner says `UNVALIDATED` and points at `gate v3` — a verdict a reader can skip
  past is not a verdict;
- the **PASS branch**, exercised directly with an in-band distribution. It is unreachable against the
  current corpus, so without this only the failure path would ever execute;
- **zero eligibility events reports "not evaluated", not FAIL.** An empty distribution means a mean of
  0.0, which sits below the historical band and would read as a failing gate. Absence of evidence is
  not evidence of failure, and the output has to say which one it is.

## Not done

P1–P3 are untouched:

- **S1c-01 AC4** — REDUCED remains unreachable (`des.py:161` hardcodes `mode="FULL"`) and
  `check_recommendation_safe()` is still called only from tests. Two coherent fixes (honour `cfg.mode`
  and call the guard, or delete the mode); the choice is a product one.
- **`unconsumed_notices` still names one key**, so it would not catch the next `mode` or
  `appr_compensation`.
- The epic header still says "5 stories"; there are six.
- `[DONE]` markers untouched. S1c-05 now meets AC3; S1c-01's AC4 gap remains.

---

# P1 / P2 / P3 — what was done

Applied 2026-08-09. **340 passed, ruff clean, `mypy --strict` on the engine clean.**

## P1 — S1c-01 AC4, and a crash it was hiding

The AC asks for REDUCED to exist *and* refuse, so it was wired rather than deleted.

- `des.py` calls `EligibilityEngine.from_config(cfg)` instead of hardcoding `mode="FULL"`.
  `p_elig` comes from `base.yaml → reduced_mode`, not a default argument.
- `check_recommendation_safe()` is now called by the three commands that emit a recommendation —
  `grid`, `report`, `gate v9` — before any simulation runs. Each exits 1 with a message naming the
  command. Verified against a temporarily-REDUCED `base.yaml`, then restored.
- `run` and `compare` are deliberately **not** guarded. They report a scenario's cost, not a reserve
  level to adopt, and REDUCED exists precisely so those can serve as a fast smoke test. They print a
  `[REDUCED MODE]` banner marking the figures as smoke-test output.
- `from_config` is one construction rule shared by the engine and the guard, so the mode a command
  refuses on is necessarily the mode the simulation would have run in.

**Making the mode reachable immediately exposed that it had never worked:**

```
ValueError: Crew P00453 has no RESERVE block overlapping [9518.0, 9850.0]
```

REDUCED thinned *all* reserves at random, ignoring pool membership, so it could hand back a crew
member with no covering RESERVE block — and `assign_reserve` raises on exactly that. REDUCED replaces
the **legality evaluation** with a coin flip, not the structural pool check, which is cheap and which
the assignment path depends on. Fixed, and it also now records its distribution (it returned early
before, so `--report-eligibility` and V3 would have seen an empty series).

A REDUCED run now completes end to end and reports mean eligibility 0.293 against `p_elig=0.3`.

Four tests: the mode is reachable from config; pool membership is respected (with `p_elig=1.0`, so
anything wrongly returned is a pool bug rather than a sampling artefact); the distribution is
recorded; and a real REDUCED scenario runs.

## P2 — the guard, and what it found

`tests/test_config.py::test_every_config_field_is_read_by_some_code_path` walks `src/` for every
attribute name and string constant, and requires each config model field to appear. It has a negative
control, and its known limitation is documented: a field whose name collides with an unrelated
attribute reads as consumed, so it catches *nothing anywhere touches it* — which is the case that
actually occurred, twice.

**It immediately found three more**, all the same class as APPR:

| field | status |
|---|---|
| `disruption.delay_per_minute` | declared, costed, **never booked** — no delay-propagation model |
| `positioning.deadhead` | declared, costed, **never booked** — gate v6 *reports* D10's real invoices but nothing charges them |
| `positioning.hotel` | same |

These are features that do not exist yet, not bugs to fix in a review pass, so they are recorded in
`config.DECLARED_NOT_YET_CONSUMED` **with reasons** and now surface at runtime:

```
$ crewsim config show
[NOTICE] disruption.delay_per_minute is declared but not yet consumed by any code path
         (the engine does not model delay propagation yet -- S1d-03 owns this)
[NOTICE] positioning.deadhead is declared but not yet consumed by any code path
         (D10's real invoices are reported by gate v6 but never charged to a scenario)
```

That dict is the **single source of truth**: `unconsumed_notices()` renders it and the test imports
it, so a key cannot be exempted from the guard while staying invisible at runtime. Previously the
notice named one key by hand, which is why it missed `mode` and `appr_compensation`.

`test_absent_demand_triggers_no_notice` was rescoped (and renamed) — it asserted the notice list was
*empty* with `demand` absent, which is no longer the point.

## P3

- Epic header corrected: **6 stories**, not 5.
- **`[DONE]` markers needed no change.** S1c-05 now meets AC3 and S1c-01 now meets AC4, so both
  became accurate rather than needing to be flipped. Nothing in the status column was edited.
- The "How it was implemented" notes were left alone — unlike 1a and 1b they describe the code that
  exists.

## Still open

- **V3 still FAILS**, by design against the mock corpus (recorded decision). It is now impossible to
  miss.
- **S1c-04b** remains correctly parked pending real data.
- **Three unbooked cost quantities** (above) are now visible rather than fixed. `delay_per_minute`
  belongs to S1d-03; positioning has no owning story yet and probably needs one.
