# SPEC_REVIEW_v3 — analysis of `spec_sections/*.md`

**Reviewed:** all 12 files in `spec_sections/` (3,596 lines), cross-checked against
`configs/base.yaml`, `configs/policies/*.yaml`, `configs/costs_pilots.yaml` and
`crewsim_skeleton.py`.
**Date:** 2026-08-06 · **Reviewer:** static read + config/code cross-check.

---

## The headline

The specification is in good shape as a *document*. The defect register (D1–D10 in
`00_Intro.md:225-236`), the anti-double-counting rule (§5.7), the CRN stream-keying
discipline (§5.2), the bias-direction column on every out-of-scope item (§1.4) and the
holdout rule (§6.4) are all above the standard for this kind of document — several of them
are things most simulation specs get wrong and never discover.

The problems are not conceptual. **They are almost entirely propagation failures from the
v3.1 correction pass.**

On 2026-08-05 the business supplied four corrections: drafting is senior-first and mandated,
no protected blocks exist, no draft cap exists, and drafting is premium-paid work crew want
(`00_Intro.md:251-262`). Those corrections landed cleanly in the *prose* of §1, §5, §7 and §9.
They did **not** propagate into three places:

1. **§2's diagrams and "Expected Artifact Examples"** — which are what an engineer copies.
2. **§10's decision register** — which is what a reviewer consults six months from now.
3. **`00_Intro`'s glossary** — which carries stale measurement figures.

Separately, and independently of v3.1, there is one live **code/config divergence** in the
reference implementation that reproduces defect D10 exactly.

Findings below are ordered by consequence, with `file:line` on each.

---

## 1. Blocks or corrupts implementation

### 1.1 The skeleton ignores the configured horizon — D10, again

`crewsim_skeleton.py` never reads `cfg["horizon"]`. The value is loaded into `DEFAULTS`
(`crewsim_skeleton.py:62`) and then dropped. Three functions hard-code it instead:

```
crewsim_skeleton.py:600   generate_scenario(..., horizon_days=28, ...)
crewsim_skeleton.py:623   build_reserves(policy, horizon_days=28)
crewsim_skeleton.py:638   evaluate_policy(..., horizon_days=28, warmup_days=7, ...)
```

So the reference run executes a **28-day horizon, 7-day warm-up, 21 measured days, and no
cool-down at all** — against a specification that contracts for 7 + 28 + 7 = 42 days with a
28-day measurement window (`4_Implementation:136`, `5_Detailed:218`, `configs/base.yaml`
`horizon:`).

This is arithmetically confirmable from §8.3's own staffing column
(`8_SimPy_DES_Skeleton:76-84`): 31,500 / 52,500 / 157,500 at R = 6 / 10 / 30 are exactly
`250 × R × 21`. §7.2's worked example computes the corresponding quantity over 28 days and
gets $40,080 (`7_Formal:75`). §7.2 *does* carry a footnote reconciling the two
(`7_Formal:78-82`) — but it explains only the flat-κ simplification (no SC/LC split in the
skeleton) and is **silent on the day count**, which is the larger of the two differences.

Three consequences:

- Every headline number quoted across the spec — E[C] = 49,571 at R = 6, CVaR₀.₉₅ = 78,730 at
  R = 10, the −11,390 paired difference — is on a **21-day basis**, while §7.2's contract
  arithmetic is on a 28-day basis. They are not comparable, and nothing says so.
- With no cool-down, §5.0.5's cool-down mechanism and the terminal penalty are **completely
  untested** by the reference run. §8.5 schedules the terminal penalty for slice 1d, but the
  missing cool-down is not listed anywhere in §8.1's "what this does not do" table
  (`8_SimPy_DES_Skeleton:38-43`).
- It contradicts the spec rule at `8_SimPy_DES_Skeleton:16` — *"Scope, horizon and population
  come from config, never from code"* — and the code's own comment five lines above the
  violation (`crewsim_skeleton.py:56`).

The skeleton already has an unconsumed-key notice mechanism (`crewsim_skeleton.py:66-68`,
documented at `8_SimPy_DES_Skeleton:18-23`), currently wired only to
`demand.pairings_per_bid_period`. `horizon.*` is silently ignored with no notice at all —
which is precisely the failure mode that mechanism exists to prevent.

**Fix:** read `cfg["horizon"]` in `evaluate_policy` and derive
`horizon_days = warmup + measurement + cooldown`; regenerate §7.4 and §8.3's tables; add the
missing cool-down to §8.1.

### 1.2 Commitment C3's policy YAML contains three retired fields

`2_HighLevel_Architecture.md:306-318` ships this as the canonical "Expected Artifact Example":

```yaml
seniority_order: "senior-first"
respect_protected_blocks: true
allow_tier4_5_drafts: true
```

All three were deleted by v3.1. `respect_protected` and `Block.protected` were removed
outright (`00_Intro.md:259`, `5_Detailed:411-415`); `seniority_order` became a constant
(`00_Intro.md:258`); tiers 4–5 are unconditionally reachable (`5_Detailed:512-513`).

This is the example an engineer copies into a Pydantic model. It is also the *only* policy
YAML in §2, so a reader who starts at "read §2.3 even if you skip the diagram"
(`2_HighLevel_Architecture.md:8-10`) meets the retired schema first.

The correct schema is §5.9 (`5_Detailed:655-669`) — and the real
`configs/policies/*.yaml` already follow it exactly. **The shipped configs are right and the
spec example is the outlier**, which is the strongest available evidence for which one to
delete.

### 1.3 The Markov chain has two contradictory start conditions

| Location | Day-1 rule |
|---|---|
| `2_HighLevel_Architecture.md:799` | *"The chain starts each scenario in `NORMAL`"* |
| `2_HighLevel_Architecture.md:610` | *"For Day 1, it draws from the steady-state baseline probability π₀"* |
| `2_HighLevel_Architecture.md:469` | *"If this were Day 1 … it would draw from the historical steady-state probability vector π₀"* |

Two-to-one is not a resolution — this is a coin flip on the first draw of every scenario. It
changes the severity path, therefore the event stream, therefore every cost figure, and it is
CRN-relevant (it shifts stream consumption on day 1). One of these must be deleted, in the
section that §4.4 names as authority.

Related, and worth fixing while you are there: `markov_steady_state_pi0`
(`2_HighLevel_Architecture.md:508-513`) is labelled *steady state* but is the empirical
quantile marginal — (0.50, 0.30, 0.15, 0.05) are exactly the CALM/NORMAL/DISRUPTED/SEVERE
quantile cuts defined at `:455`. It is not stationary under the `P` printed directly beneath
it: πP = (0.506, 0.275, 0.139, 0.080). Rename it `pi0_empirical` or fit the actual stationary
vector — but do not call a quantile marginal a steady state in a document that a
statistician will read.

### 1.4 The shipped sensitivity sweep includes a value the spec forbids

`5_Detailed:230` — *"It **must** exceed `cancel_cost`, or the model learns that abandoning an
item is cheaper than cancelling it."*
`configs/costs_pilots.yaml` — *"terminal_penalty_multiple: 1.5 # MUST exceed 1.0"*

But `configs/base.yaml` ships `sensitivity.terminal_penalty: [1.0, 1.25, 1.5, 2.0, 3.0]`, and
`9_Verification:127` prescribes sweeping *"at 1x, 2x, and 3x"*. `00_Intro.md:134` repeats
"1.0x to 3.0x".

At exactly 1.0× the model becomes indifferent between abandoning and cancelling, which is the
degenerate case §5.0.5 exists to exclude. Either drop 1.0 from the sweep, or state explicitly
that 1.0 is included as a *known-degenerate* lower bound and that the recommendation at that
point is expected to be invalid.

### 1.5 §8.4 reports four verification checks as passing; none of them exists

`8_SimPy_DES_Skeleton:124-144` states four checks and marks each **✓ passes today**:

| Claim | Stated result |
|---|---|
| CRN integrity across machines | *"Identical to the 12th decimal place. ✓"* |
| Rule L0, 100 months scanned | *"0 violations found. ✓"* |
| Payroll linearity, 2 vs 20 reserves | *"Linear math confirmed. ✓"* |
| Senior-first selection | *"Confirmed. ✓"* |

Those are gates V7, V8 and V1 respectively — all three placed at slice 1a by §9.1
(`9_Verification:25,31,32`).

They exist nowhere in the repository. `crewsim_skeleton.py` contains no `assert`, no
verification function and no violation scan (grep for `assert |def verify|def check_|violat`
returns nothing). `tests/` contains exactly two test modules —
`test_project_structure.py` and `test_dependency_rule.py` — and `tests/engine/`,
`tests/gates/`, `tests/calibration/`, `tests/data/` and `tests/reporting/` are empty
directories holding only `__init__.py`.

This collides with the spec's own definition of done: `3_HighLevel:158` — *"The Exit Gate test
must be written into the code's automated testing pipeline (CI). It cannot just be a script
that one engineer ran once on their laptop."* §8.4 is a laptop result, reported in the past
tense with checkmarks, for three of the nine gates that §9 says must all pass before any
output informs a decision.

**Fix:** either land the four checks in `tests/gates/` and keep the claims, or restate §8.4 as
*"checks to implement in slice 1a"* and move the ✓ marks out until CI produces them. The
second is cheap and honest; the first is the one §3.1 actually requires.

---

## 2. Misleads a reader or fails an audit

### 2.1 §7 contradicts itself about the draft cap

`7_Formal:352` — *"`Θ` holds only the reserve-selection rule, the cross-base flag and **the
draft cap** (§7.3)."*

§7.3's own table, 240 lines earlier in the same file (`7_Formal:111`), marks the drafting cap
❌ **Locked**, and §7.5 has a heading titled *"Why there is no 'Fairness' or 'Draft Cap'
Constraint"*. The cross-reference points at the section that refutes it.

### 2.2 §10's decision register carries three superseded rows

The register is explicitly the artefact for answering *"why does it do it that way?"* six
months from now (`10_Summary:8-9`). Three rows will give the wrong answer:

| Line | Says | Superseded by |
|---|---|---|
| `10_Summary:20` | Voluntary layer excluded *"with a swept sensitivity parameter"* | `1_Problem_Statement.md:237-239` — the `voluntary_absorption_rate` dial was **removed**: *"No placeholder parameter is used for this."* |
| `10_Summary:42` | *"Fairness constraint — **Pathwise** per-crew cap inside each run"* | Row 34 of the **same table** (`10_Summary:34`): the cap was removed entirely. §7.5 has no such constraint. |
| `10_Summary:32` | *"this is the inverse of the common industry pattern"* | Row 102 of the **same table** (`10_Summary:102`): *"Answered: no."* |

Row 42 and row 34 contradict each other inside one table; row 32 and row 102 do the same.

### 2.3 The retired "inverse of the industry norm" claim survives in §5.6

`5_Detailed:545-547` still tells reviewers senior-first drafting *"is the inverse of the
common industry pattern, in which seniority confers protection."* `00_Intro.md:262` records
this concern as explicitly **retired**: drafting is premium-paid, so senior-first is the
ordinary seniority principle, not an inversion.

This one matters beyond tidiness — §6.2 warns that getting the framing backwards in an
ALPA-facing artefact is worse than omitting the metric (`6_Detailed:69`).

### 2.4 `juniorfirst` appears inside candidate policy identifiers

`1_Problem_Statement.md:116` and `5_Detailed:656-657` both use
`policy_id: YUL-A321neoLR-FO-R14-juniorfirst-v3` — in sections presenting *"what a candidate
decision actually looks like"* and the canonical policy object.

`5_Detailed:492` states `junior_first` *"may never appear in a candidate policy."* The
specification's own two illustrative candidate policies violate its own rule. (The shipped
`configs/policies/*.yaml` correctly do not.)

### 2.5 §9/V6 asserts a bias direction §1.4 explicitly retracted

`9_Verification:98` — voluntary pickup *"**Overstates** drafting cost."*
`1_Problem_Statement.md:222,233-235` — the direction is *"now unclear rather than a clean
upper bound,"* because premium-paid senior-first drafting may already occupy much of the same
space.

V6 is the cost backtest, and §9.2 explicitly asks reviewers to check whether the miss lands
*"in the exact predicted direction"* (`9_Verification:102`). Predicting a direction §1.4 says
is unknown converts a validation gate into a rubber stamp.

### 2.6 §3 states two different grid sizes

`3_HighLevel:90` — *"We run 24 different strategy combinations."*
`3_HighLevel:109` — *"(6 reserve levels) × (5 callout rules) × (2 cross-base rules) = 60
total strategies,"* repeated at `:111` and `:129`.

60 is the one the arithmetic supports.

### 2.7 Three different figures for the same reference measurement

The paired CRN difference is quoted four times with three different values:

| Location | Figure |
|---|---|
| `1_Problem_Statement.md:207`, `2_HighLevel:385`, `7_Formal:340` | −11,390 ± 3,207, t = −7.0 |
| `00_Intro.md:128`, `10_Summary:52` | ± 4,139 |
| `00_Intro.md:129` | −10,154 ± 4,139, t = −4.8 |

The three-way agreement at −11,390 ± 3,207 is presumably current; `00_Intro`'s glossary and
§10's register are stale. Worth fixing precisely because §1.3.6 uses this number as the
argument for why CRN is not optional — a reader who checks it against the glossary finds a
different number and a different t-statistic.

### 2.8 Residual involuntary-framing language

v3.1's most consequential reframing — drafting is *premium-paid work crew want* — has not
reached the plain-language passages:

- `5_Detailed:63` — *"how many times each pilot has been **forced** to work on their day off"*
- `2_HighLevel:745` — *"the airline must Draft. It **forces** a normal pilot to fly on their
  day off, paying a massive premium multiplier"*
- `3_HighLevel:118` — *"What if we drafted junior pilots first"* framed as an "illegal"
  strategy rather than a counterfactual pricing exercise

Grouped here rather than filed as cosmetic because §6.2 and §9.4 both identify this exact
framing as the thing that must not appear in anything shared with ALPA.

---

## 3. Minor

- `00_Intro.md:183` points at `spec_sections/_v2_original/` for the v2 documents. **The
  directory does not exist.** (`crewsim_skeleton.py`, `SPEC_REVIEW.md`, `QUESTIONS_TO_ASK.md`
  and `configs/base.yaml` all resolve correctly.)
- `4_Implementation:49` names the repository root `crew-recovery-sim/`; the actual root is
  `draft-sim/`.
- `2_HighLevel:455` explains regime stickiness with *"a **60% chance** tomorrow will also be
  SEVERE"*; `:805` explains the same mechanism with *"the **0.40** self-transition is doing
  real work."* The two matrices are deliberately different (illustrative-vs-fitted, flagged at
  `:498-500`) — but explaining one mechanism with two numbers in one file is a readability
  defect. Add a half-sentence at `:455` pointing at the flag.
- `00b_glossary.md` duplicates a subset of `00_Intro.md`'s glossary. The overlapping entries
  are currently verbatim-identical — so this is a maintenance risk, not drift, but it is two
  files that must now be edited together.
- §8.3's output table (`8_SimPy_DES_Skeleton:76-84`) is not reproducible from the shipped
  `__main__`, which evaluates R6 vs R10 and sweeps R ∈ {4,6,8,10} — it never runs R = 0, 2 or
  30. Either the table is from an older driver, or the driver needs a `--sweep` mode that
  reproduces it. Relevant because gate V1 requires the R = 0 case
  (`9_Verification:53`), and `mean_eligibility_rate` returns `None` at R = 0
  (`crewsim_skeleton.py:668`) into a `:.2f` format string at `:697`.
- Untracked `spec_sections/2_HighLevel_Architecture.html` is 17 MB — larger than the entire
  rest of the repository. §4.4.1b already accepts a ~97 MB repo for the corpus with an
  explicit justification; a generated render deserves a `.gitignore` entry rather than a
  second size decision.

---

## 4. Things that are correct and worth not breaking

Checked and confirmed sound, listed so a later edit does not "fix" them:

- **The two transition matrices** (§2.5.0's fitted-example vs §2.5.4/§5.2's illustrative) are a
  deliberate, well-flagged distinction (`2_HighLevel:489-500`), not a drift defect. §5.2 is
  correctly named as authority.
- **The eligibility estimator** in `crewsim_skeleton.py:356-366` implements §5.5's definition
  exactly — fraction of the on-call pool that is legal, with `None` on an empty pool. The
  0.54 → 0.96 rise across R in §8.3 is the documented consequence of missing L8 and reserve
  rotation (`8_SimPy_DES_Skeleton:42`), not a mis-specified metric.
- **All four §2.5.4 matrix rows sum to 1.00**, and the mermaid diagram agrees with the table.
- **The shipped configs are consistent with the spec's corrected sections** — `R6.yaml` carries
  only `allow_cross_base_reserve` and `reserve_selection` in `stage2`, exactly per §5.9.
- **The story references resolve.** `S0-06`, `S0-07` and `S0-07b`, cited as the authority for
  the fitted matrix, NHPP and delay mixture (`2_HighLevel:456,761,789`), all exist in
  `backlog/stories.yaml:149,163,177` with the dependency edges the spec implies.

---

## 5. Recommendation — close the gap that let this happen

§4.4 establishes a single source of truth for every **number**, and §2.5.4 names §5.2 as
authority for the matrix. That rule worked: no numeric drift was found outside the two items
in §1.1 and §2.7.

Nothing governs **domain facts and schemas**, and that is exactly where v3.1 leaked. Extend
the §4.4 rule to cover two more things:

1. **One canonical policy schema.** §5.9 is the authority; §2.3/C3 and §1.2 reference it
   rather than restating it. `configs/policies/*.yaml` are already the de-facto conformance
   test — make that explicit and add a schema test that fails on any retired field.
2. **One canonical θ-membership list.** §7.3's table is the authority. §7.7, §2.1, §10.2 and
   §5.9 reference it. Every occurrence of "drafting params θ" in §2.1's pipeline diagram
   (`2_HighLevel:78,80,88`) is currently a claim the system no longer makes.

The v3.1 corrections turned this from a drafting-policy optimiser into a reserve-sizing tool
with a fixed recourse rule (`00_Intro.md:264-271`). §1, §5, §7 and §9 say so. §2 and §10 have
not caught up — and §2 is the section engineers read first.

---

## Suggested order of work

| # | Item | Why first |
|---|---|---|
| 0 | §1.5 land the four §8.4 checks in `tests/gates/`, or drop the ✓ marks | Everything below is verified by tests that do not exist yet |
| 1 | §1.1 horizon: read `cfg["horizon"]`, regenerate §7.4/§8.3 tables | Every published number depends on it |
| 2 | §1.3 Markov start state: pick one, delete the other | Changes every scenario |
| 3 | §1.2 delete C3's retired policy YAML, point at §5.9 | Highest chance of being copied into code |
| 4 | §1.4 drop or annotate the 1.0× terminal-penalty sweep point | Ships today in `base.yaml` |
| 5 | §2.1–2.5 sweep for stale v3.1 language (§7.7 draft cap, §10 rows 20/32/42, §5.6 "inverse", `juniorfirst` ids, §9/V6 bias) | One editing pass, mechanical |
| 6 | §2.7 reconcile the CRN figures to one value | Cheap, and it is the number that carries the CRN argument |
| 7 | §5 add the schema/θ authority rules to §4.4 | Prevents the next v3.2 pass leaking the same way |
