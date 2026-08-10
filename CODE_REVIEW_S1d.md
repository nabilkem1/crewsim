# Code review — Epic E1d, Slice 1d (Cascade Engine FULL)

Reviewed 2026-08-09 against `backlog/mvp/04_slice_1d_cascades.md`, story by story, acceptance
criterion by acceptance criterion. Every claim below was checked against running code on the real
corpus, not read off the card.

**Scope note.** All 12 stories are marked `[DONE]` in both surfaces (markdown and `stories.yaml` agree
— only the epic header is wrong). The mechanisms are, with two exceptions, genuinely built. What this
review found is concentrated in the **gate**: V4 renders a confident verdict on a historical band
reconstructed from **zero of 2,584** true drafts, and the acceptance criterion written to prevent
exactly that cannot fire.

---

## Environment finding, before anything else

The parameter store on disk could not be read at the start of this review:

```
KeyError: Parameter store params_v0.1.0_winter_sun.json is missing 'category_levels'
under sick_call_nhpp -- it was fitted before category_levels was added to the
calibration pipeline. Re-run calibration to regenerate it.
```

A concurrent workstream has uncommitted changes to `calibration/nhpp.py`, `calibration/pipeline.py`
and `scenarios/generator.py` that require a store field the committed store predates. **Nothing in the
repo could simulate.** The error is a good one — it names the remedy — and re-running
`crewsim calibrate --season winter_sun --emit` restored a working store, which is what this review then
ran against. Flagged because it is not visible from any test: the suite passes because pytest fixtures
regenerate what they need.

---

## Per-story verdicts

| Story | Verdict | Note |
|---|---|---|
| S1d-01 Future-pairing cascade | **PASS**, stale rationale | Mechanism real. Manual check accepts `--scenario` and ignores it; its justifying premise is now false |
| S1d-01b Allowlist L2 constants | **PASS**, card superseded | S1a-07 removed the duplication the card describes as accepted |
| S1d-02 Future-reserve cascade | **FAIL** | AC2 unmet; AC1 unreachable in the production pipeline; 0 occurrences in 402 real drafts |
| S1d-03 E9 terminal penalty | **PASS**, broken manual check | AC1–AC3 met (AC3 by S1e-01). The documented manual check exits 1 |
| S1d-04 V4 gate | **FAIL** | AC3's warning is dead code, and the condition it guards is live right now |
| S1d-04b Time units / signatures | **PASS** | Verified: block times minutes-scale, pinned by a real regression test |
| S1d-04b2 Corpus generator fix | **PASS** | L0 clean across the corpus |
| S1d-04c `des.py` pipeline | **PASS**, one stale limitation | Cascades now fire; the "never observed" note no longer holds |
| S1d-04d CRN loop + de-mocking | **PASS**, stale limitation section | Its V4 description no longer matches behaviour |
| S1d-04e Remove hardcoded fallback | **PASS** | |
| S1d-05 V9 sensitivity | **PASS** | Both documented inert axes re-confirmed still inert |
| S1d-05b Allowlist gap | **PASS** | |

---

## P0 — the V4 gate reports a verdict it has no basis for

### 1. AC3's recall warning is dead code, and the condition is live

S1d-04's third acceptance criterion:

> If S0-03's recall was marginal, **the report says so on the same page** as the verdict

`gates/v4_cascade.py:22`:

```python
recall_val = hist["draft_recall"].get("rate", 1.0)   # <- key does not exist
if recall_val < marginal:
    recall_warning = True
```

The comment one line above admits the guess: `# Assuming draft_recall has a "rate" or similar`.

What `cascade_target()` actually returns, measured live:

```python
'draft_recall': {'recall': 0.0, 'found': 0, 'true_n': 2584, 'gate': 0.8, 'gate_pass': False}
```

The key is `recall`, not `rate`. `.get("rate", 1.0)` therefore returns **1.0** on every run, `1.0 <
0.90` is never true, and `recall_warning` is **permanently False**. The warning has never fired and
cannot.

This is not hypothetical. Draft reconstruction on the holdout window currently finds **0 of 2,584**
true drafts — recall 0.0, `gate_pass: False`, catastrophically below the 0.90 marginal bar. The report
says nothing.

**Why it survived**: `tests/gates/test_v4_cascade.py:21` builds its own input —

```python
"draft_recall": {"rate": 0.85}   # Below 0.9 -> marginal
```

— using the key the *code* reads rather than the key the *real function* returns. The test asserts
`recall_warning is True` and passes. It validates a copy of the mechanism, not the mechanism. Same
defect class as S1a-04's duplicate staffing implementation, S1b-07's stubbed shortfall, S0-04's
fabricated eligibility target, and S1c-07's structural `$0.00` in V6.

**Fix**: read `recall`; drive at least one test through the real `cascade_target` shape rather than a
hand-built dict.

### 2. The verdict is arithmetically incapable of meaning anything

```python
passed = bool(hist["ci_low"] <= sim_mean <= hist["ci_high"])
```

The holdout band is `[0.000, 0.000]`, built from `n_drafts: 0`. Containment in a zero-width interval
means the gate **passes only if the simulated rate is exactly 0.0**, and fails otherwise. Live run:

```
Historical Band: [0.000, 0.000] (Mean: 0.000)
Simulated Mean : 0.043
Verdict: [FAIL] Simulated cascade rate deviates significantly from history.
Suspect mechanism: Visibility lag, rule implementations, or base composition.
```

Every named suspect is on the **simulated** side. The actual problem is that the historical side is
empty. The epic documents this gate as *"currently 'passes' only because both sides degenerate to
0.0"* — that is now stale in the worst direction: cascades began firing (slice 1b/1c changes), so the
gate flipped from a meaningless PASS to a confident, misdirected FAIL.

**Fix**: when `n_drafts == 0` (or recall fails its own gate), refuse to render PASS/FAIL and say why —
the same disposition V3 already takes. A gate that cannot be informative should not look decisive.

---

## P1

### 3. S1d-02's reserve cascade is both uncounted and unreachable

Two acceptance criteria, neither met as written.

**AC2 — "Distinct from a pairing cascade in the ledger, so the two can be counted separately."**
`cascade.py:71-75` removes the RESERVE block and books nothing. No ledger row exists, and
`des.py:565` increments `n_cascading_drafts` only when `cascaded` (pairing items) is non-empty. A
reserve-only cascade is invisible to the ledger *and* to every counter. The two cannot be counted
separately because one of them cannot be counted at all.

**AC1 — "Drafting a crew member who held a later RESERVE block shrinks that day's pool."** Draft
candidates come from `self.roster`, and `roster_loader.py:300` strips RESERVE blocks from every line
holder when the pool is carved:

```python
c.calendar = [b for b in c.calendar if b.btype != BlockType.RESERVE]
```

So a draftee cannot hold a RESERVE block by construction. Measured across 4 real R10 scenarios:

| | count |
|---|---:|
| drafts | 402 |
| broke a future PAIRING (counted) | 17 |
| broke a future RESERVE (counted by nothing) | **0** |

The branch is unreachable from the production pipeline, not merely rare. The manual check
(`explain-cascade --type reserve_loss`) builds a crew member holding both a draftable slot and a future
RESERVE block — a shape `load_rosters` never produces — so it cannot detect this.

Note this is arguably *correct* modelling: reserves are assigned, not drafted, and capacity shrink from
an assignment already happens via `assign_reserve`'s REST block. If so, the story's ACs describe a
mechanism the design deliberately doesn't have, and should say so rather than claim `[x]`.

### 4. S1d-03's manual check cannot run

Documented check and expectation:

```
crewsim explain-cost --category TERMINAL_PENALTY --summary
Expect: $37,500 per unresolved item
```

Actual:

```
error: category 'TERMINAL_PENALTY' not in this scenario's ledger
(present: ['APPR_COMPENSATION', 'CANCELLATION', 'DRAFT_TIER1', 'DRAFT_TIER2',
           'RESERVE_STAFFING', 'RESERVE_UTILIZATION'])
```

Exit 1. Every open item resolves before the horizon, so the category is never booked — independently
confirmed by S1d-05's own finding #1. The *code* is right (`evaluate_terminal_penalties` is real and
unit-tested); the documented check is unrunnable and has been since the pipeline became real.

---

## P2

### 5. `explain-cascade` ignores the `--scenario` it prints

`cli.py:1511` interpolates `args.scenario` into the header and never reads it again — both `--first`
and `--type reserve_loss` print a fixed synthetic fixture (`C1`, `P_DRAFT`, `P_FUTURE`). A flag that
appears to select real data and does not is misleading even when the fixture choice is defensible.

Its justification is also now false. The comment reads:

> S1d-04c/S1d-04d found real cascades are rare at production roster scale
> (`n_cascading_drafts == 0` across 20 seeds at R10)

Measured today: **17 cascading drafts in 402**, 4.2%. Slice 1b's displaced flying and slice 1c's
cross-base dispatch changed the draft mix. Either drive the check from a real scenario now that one
exists, or drop `--scenario` and state the fixture plainly.

### 6. S1d-04's AC1 describes a comparison that would be wrong

> the share of drafts producing ≥1 downstream open item **or reserve loss**

The simulated side counts pairing cascades only. That is **correct**, because the historical side
(`reconstruct_cascades`) counts `CASCADE_UNCOVERED` flight events and cannot see a reserve loss either.
Including reserve losses would make the two sides incomparable. The AC wording, not the code, is what
needs correcting.

### 7. A wrong pointer I introduced in the S1c pass

`config.py`'s `DECLARED_NOT_YET_CONSUMED` says of `disruption.delay_per_minute`:

> the engine does not model delay propagation yet — no code path books a per-minute delay cost
> **(S1d-03 owns this)**

S1d-03 is E9, the terminal penalty. Delay is **E2**, owned by **S1b-09** per `COVERAGE_AUDIT.md:63`.
The notice prints on every command, so the wrong pointer is highly visible.

---

## P3

8. **Epic header says 9 stories; there are 12.** Both markdown and `stories.yaml` carry all 12 and
   agree on status — only the header is stale. (Same class as the 5→6 fix in slice 1c.)
9. **S1d-01b's card describes a duplication that no longer exists.** It documents `cascade.py`
   re-deriving L2's 11h/10h rest as an accepted pattern; S1a-07 collapsed all four copies into
   `legality.min_rest_minutes`, and `cascade.py:31` now calls it. The ALLOWLIST entry was correctly
   reduced to `{60.0}`; the story text was not updated.
10. **S1d-04c's and S1d-04d's "known limitations" sections are stale** on cascades never firing and on
    V4 passing vacuously. Both statements were true when written and are now misleading.

---

## Confirmed still true (not defects, re-verified)

- **Sick calls are generated across the full 42-day horizon**, cooldown included (S1d-04c's documented
  limitation). `measured_window_costs` correctly compensates via `rows_in_measurement_window`'s
  root-origin attribution rule (S1e-01), so this does not corrupt reported cost — but the arrival
  process still does not match `base.yaml`'s own description of cooldown as a drain period.
- **`TERMINAL_PENALTY` never fires** at this corpus/roster scale (S1d-05 finding #1).
- **`roster_size` is inert** — one consumer, a `config show` print. The `[NOTICE]` on `gate v9` is
  still accurate.
- **S1d-03 AC3 is met**: cool-down costs are attributed back through `root_event_uid` by
  `rows_in_measurement_window`. Implemented by S1e-01 rather than S1d-03, and the card doesn't say so,
  but the criterion holds.

---

## Suggested order

1. **P0-1** — fix the key, and make one V4 test go through the real `cascade_target` shape.
2. **P0-2** — refuse a verdict when the historical band is degenerate.
3. **P1-4** — repoint S1d-03's manual check at a command that runs.
4. **P1-3** — decide whether reserve-loss cascades are a real mechanism or a design non-goal, then make
   the card and the code agree.
5. **P2/P3** — the stale rationales, the wrong pointer, the header.

P0-1 and P0-2 are the same 20 minutes of work and together turn V4 from misleading into honest. They
do not make it *pass* — that needs S0-03's holdout reconstruction to find any drafts at all, which is
outside this epic.

---

# What was done — 2026-08-09

Fixed in the requested order. **377 passed, ruff clean, `mypy --strict` clean on `crewsim.engine`.**

## P0 — V4 now says what it actually knows

**The dead warning.** `_recall_of()` reads `recall` (the key `score_recall` returns) and **raises** on an
unrecognised shape instead of defaulting. Defaulting was the whole defect: `.get("rate", 1.0)` is
indistinguishable from "recall is fine", which is how a criterion stayed silent through every run this
gate ever did.

**The test that let it through.** `test_v4_cascade.py` built its stand-in with the key the *code* read.
Now every mock uses the real shape, and `test_the_mock_matches_the_real_cascade_target_contract` drives
the real `cascade_target` and asserts the keys those mocks depend on — so the two cannot drift again.
Added regressions: the warning firing on the real key, the old shape raising, absent ground truth
(real data ships none) not being mistaken for bad recall.

**The verdict.** V4 gained `INCONCLUSIVE`, returned when the historical side cannot support a
comparison — zero reconstructed drafts, zero recall, or no simulated drafts — listing which
precondition failed and stating that the simulated side is not implicated. It exits 1 (it is not a
pass) but is no longer confusable with FAIL, because the two demand opposite responses. Two tests pin
that a 0.0-vs-`[0,0]` coincidence can never again read as PASS.

## P1

**Reserve-loss cascades are counted.** `n_reserve_loss_cascades` / `n_reserve_blocks_lost` on
`Simulation`, surfaced by `explain-recovery`. **Counters, not a ledger row** — losing a future reserve
block has no direct cost in §4.4.2, and booking one would have meant inventing a coefficient. And the
more important half: a test pins that the branch is *unreachable* from the production draft pool, and
fails the moment `load_rosters` stops stripping RESERVE blocks from line holders.

**S1d-03's manual check runs.** `ledger.BOOKABLE_CATEGORIES` maps every category the engine can emit to
the condition that emits it, so the CLI distinguishes *did not happen* (report `$0.00`, name the
condition, exit 0) from *cannot exist* (error, list what is bookable, exit 1).

## P2

`explain-cascade --first` traces a **real** cascade from the requested scenario, falling back to the
fixture only when that scenario produced none — and saying which it showed. `des.py` gained the trace
line the cascade enqueue never had. The `reserve_loss` variant stays a fixture (it must — the path is
unreachable) but prints its own unreachability note and no longer accepts a `--scenario` it ignores.
`config.py`'s notice now attributes `delay_per_minute` to S1b-09 (E2), not S1d-03 (E9).

## P3

Epic header 9 → 12. S1d-01b marked superseded (S1a-07 collapsed the duplication it documents).
S1d-04c's and S1d-04d's limitation sections corrected — cascades fire at 4.2%, and V4 no longer
"passes vacuously". All findings mirrored into `stories.yaml` under `review_2026_08_09`.

## What this does not fix

**V4 still cannot PASS**, and shouldn't: `cascade_target` finds 0 of 2,584 drafts on the holdout window
(recall 0.000). That is S0-03's reconstruction, outside this epic. The change is that the gate now
reports its own blindness instead of blaming the simulation for it.

**Two mechanisms remain empirically inert** and are documented as findings, not smoothed over:
`TERMINAL_PENALTY` never fires at this corpus scale, and `roster_size` has one consumer (a print).

## Note on the working tree

A concurrent workstream removed the `src/crewsim/api/` carve-out from the numeric-constant guard while
this work was in progress, which puts their in-flight files inside its scope. One full-suite run went
red on `test_no_numeric_constant_outside_configs` mid-edit and was green on the next run with no change
from this side. Worth knowing if CI flickers there.
