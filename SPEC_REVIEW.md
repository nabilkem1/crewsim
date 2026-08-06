# Review — Crew Reserve & Drafting Policy Optimization System (spec v2)

**Reviewed:** `_initial_requirments/crew_reserve_drafting_simulation_spec v2.md` (v2, 1361 lines),
`_initial_requirments/details.md`, `spec_sections/*` (= the same v2 document split per section with
plain-language "Explained" appendices; no divergent content — reviewed as one spec).

> ## ⚠️ Partially superseded by spec v3 — read this first
>
> This document is the review of **v2**, and it remains the historical record of what v2's reference
> implementation did. It has **not** been rewritten. Two of its numeric findings were superseded once
> the defects were actually fixed and the patched skeleton was re-run (`./crewsim_skeleton.py`);
> current numbers are in **§8.3** of `spec_sections/`.
>
> | Finding below | Status after v3 |
> |---|---|
> | **D8** — eligibility rate 8.3% / 13.3% | **Metric redefined.** v2 computed the eligible fraction against a denominator that did not correspond to anything measurable in history. v3 defines the pool as *reserves whose on-call block covers the duty window*, which is what §6.3-2's historical target actually measures. Under the corrected metric the patched run gives **0.54 → 0.96**. It still fails gate V3, for the structural reasons given in §8.3 — but the old numbers are not comparable to the new ones. |
> | **D1** — "fixing D1 alone does not restore the economics… the minimum sits at R=2, there is still no interior optimum" | **Wrong, and corrected by measurement.** That claim was inferred from post-hoc arithmetic on v2's still-broken run. With D1, D3 (rule L0) and the reserve-block split all fixed, the patched implementation produces a clean U-shaped curve: argmin E[C] at **R=6**, argmin CVaR₀.₉₅ at **R=10**. The staffing price tag alone is sufficient to create an interior optimum. Headcount conservation (§4.1 below) remains a real and necessary improvement, but it corrects the recommended *level*, not the existence of the trade-off. |
>
> Everything else below — D2, D3, D4, D5, D6, D7, D9, D10, and the realism ranking — stands as written.

**Method:** read in full; extracted the inline `crewsim_skeleton.py` (spec lines 800–1325) and ran it.
It reproduces the spec's published smoke output bit-for-bit, so every claim below marked **[verified]**
was observed by execution, not inferred from reading.

---

## 1. Verdict

This is a well-above-average spec for this class of problem. The core modeling stance — **eligibility
and cascades are emergent consequences of crew state, not exogenous Bernoulli parameters** — is the
right call and is the thing that distinguishes this from the reserve-sizing spreadsheets it is meant
to replace. The CRN architecture, the event-level ledger, and the hard-costs-only objective are
genuinely good engineering decisions that most teams get wrong.

The problem is the gap between the document's rigor and the reference implementation's fidelity.
The skeleton is presented as "production-*shaped* … Extend, don't rewrite," and its output is used in
§8 to demonstrate the reserve-vs-drafting tradeoff. **It does not currently demonstrate that tradeoff —
it demonstrates the opposite,** because Stage-1 reserve cost is silently excluded from every reported
number. A team that follows the "extend, don't rewrite" instruction will inherit that and several other
defects, all of which bias the one number the tool exists to produce.

Recommendation: keep the architecture, fix the defects in §3 before any code is written on top of
the skeleton, and re-sequence Phase 1 into five gated slices (§5) rather than one 6–8 week block.

---

## 2. What is strong — preserve these

| | Why it matters |
|---|---|
| **Emergent eligibility & cascades** (§1.3, §5.5, §5.7) | The naive alternative (`p_elig=0.30`, `p_cascade=0.20` as inputs) makes the model structurally incapable of answering the question, because both quantities are *functions of the decision variable*. Getting this right is the spec's central contribution. |
| **CRN as an architectural commitment** (§5.2, §2) | Not an afterthought — the "stream discipline rule" (never draw from a shared RNG whose call order depends on policy) is exactly the subtle thing teams miss. The paired-difference result (±8.5k CI on a 180k mean at N=100) is real and is worth the whole design. |
| **Event-level ledger, nothing only-aggregated** (§2, §5.8) | Makes V&V, drill-down, and cost attribution possible after the fact. Cheap to build now, impossible to retrofit. |
| **Hard costs only; morale/fairness as KPIs and constraints** (§1.3.5, §5.8) | Refusing to bury invented soft-cost weights in the objective is the difference between a tool planners trust and one they argue with. Keep this discipline under pressure. |
| **V1–V8 gate list** (§9), esp. V2 Erlang-B and V7 CRN integrity | An analytic sanity bound plus a reproducibility test is more than most simulation projects ever write down. |
| **Explicit out-of-scope section** (§1.4) with the bias direction stated | Honest. See §4.3 for one out-of-scope claim that needs correcting. |
| **Two fidelities (FULL/REDUCED) behind one interface** (§2) | Right way to keep smoke tests fast without a second codebase. |

---

## 3. Defects — ranked, all verified against the running skeleton

### D1 — Stage-1 reserve cost is excluded from every reported cost **[verified — blocking]**

`IOCSimulation.__init__` books the entire horizon's `RESERVE_STAFFING` as one row at `t=0.0`
(skeleton §6). `CostLedger.total(warmup_end)` keeps only rows with `t >= warmup_end`, and
`evaluate_policy` passes `warmup_end = 7 days`. **The staffing row is therefore always dropped.**

Observed on one scenario, R=10: ledger contains `RESERVE_STAFFING: 70,000` — reported total excludes
all of it. The consequence, measured over 100 CRN scenarios:

| Reserves | E[C] as the skeleton reports it | E[C] with staffing restored |
|---:|---:|---:|
| 2 | 174,824 | 185,324 |
| 6 | 180,464 | 211,964 |
| 10 | 160,528 | 213,028 |
| 20 | 107,115 | 212,115 |
| 40 | **23,928** | 233,928 |

As coded, cost is **monotonically decreasing in reserve count** — the Phase-2 optimizer would drive
R to its upper bound and report a 7× cost saving. The whole economic tension the system exists to
quantify is absent. The spec's own headline demo (§8: R10 beats R6 by 19,935 ± 8,455, t=4.6) is an
artifact of this bug.

**Note that fixing D1 alone does not restore the economics.** Read the right-hand column again: the
minimum sits at R=2, the smallest value tested, and the curve rises from the boundary — there is still
no interior optimum, only a flat-to-rising band. That is the compounding effect of D1 + D4 + D5 + the
headcount gap (§4.1): reserves in this model are *free extra capacity bolted onto a fixed roster*,
so the model's only remaining preference is to hold as few as possible. Restoring staffing stops the
runaway; it does not make the tradeoff appear.

**Fix:** book `RESERVE_STAFFING` per reserve-day at the day's own timestamp, so warm-up filtering
prorates it correctly — the same treatment every other cost category gets. Unit test: staffing appears
in `E[C]` and scales linearly with R × horizon-days. Do *not* make "E[C] is non-monotone in R" an
acceptance criterion — on current numbers it either fails or passes on noise (the 213,028 → 212,115
dip). Whether an interior optimum exists is an empirical result to observe at slice 1b, after D4/D5
and headcount conservation are in, not a gate on slice 1a.

### D2 — `event_rng` is not reproducible across processes, defeating V7 **[verified — blocking]**

`ScenarioRNG.event_rng` (skeleton §1) seeds from `hash((entropy, stream_name, event_uid))`. Python's
`hash()` of a `str` is salted per interpreter by `PYTHONHASHSEED`. Running the same call under three
seeds returns three different values:

```
PYTHONHASHSEED=0 → 0.4918933424608417
PYTHONHASHSEED=1 → 0.5928589262423052
PYTHONHASHSEED=2 → 0.3314124307446792
```

The MVP's stated parallel path is `joblib` with `n_jobs=-1`, i.e. multiprocessing — so results are not
reproducible run-to-run, and V7 ("same policy, same master seed, twice → bit-identical ledger") fails
by construction the moment this stream is used for anything.

**Fix:** derive deterministically — `hashlib.blake2b(f"{entropy}|{stream}|{uid}".encode(), digest_size=8)`
→ int, or better, pre-spawn a `SeedSequence` child per (stream, uid) block. Make V7 a CI test, not a
manual gate.

### D3 — There is no single-assignment (non-overlap) rule anywhere in the spec **[verified — blocking]**

This is a gap in the **specification**, not only the skeleton. The legality surrogate L1–L9 (§5.4)
contains rules for duty length, rest, cumulative hours, days off, qualification, base, notification and
protected blocks — but **no rule preventing one crew member from being assigned two duties at the same
instant**. V8 only asserts that no inserted duty silently violates L1–L2. Physical feasibility is more
fundamental than any rest rule, and it is missing.

The skeleton has no overlap guard on either path. `LegalitySurrogate.check` never compares the proposed
duty against the crew's existing blocks, and L2's lookback filter is `b.end <= duty_start`, so a block
that *straddles* `duty_start` is invisible to it. On the drafting path, `status_tier` computes the
overlapping block's tier and then drafts the crew member anyway, inserting an overlapping
`DRAFTED_DUTY`. Measured over 20 CRN scenarios:

| | R=6 | R=10 |
|---|---:|---:|
| Overlapping `DRAFTED_DUTY` pairs held by reserves | 80 | 130 |
| Line-holder drafted duties overlapping another of their own blocks | 1,030 | 909 |

So a reserve is not merely "never consumed" (D4) — it is **multi-booked**, because assignment is
decided at `now` while the duty starts 2–10 h later, and `block_at(now)` still reports `RESERVE`.
Roughly a thousand physically impossible assignments per 20 scenarios means reserve productivity, draft
counts, and the realized eligibility rate are all unreliable in an unknown direction — which is the main
reason the 8–13% eligibility figure in D8 cannot be interpreted yet.

**Fix:** add **L0 — a crew member holds at most one duty assignment at any instant** as the first
surrogate rule, checked against the full block calendar (not just prior duties) on every insertion;
extend V8 to assert it as an invariant under hypothesis-generated schedules. This should be the first
property test written.

### D4 — Reserves are never consumed **[verified]**

§5.0.4 event E3 specifies `Res_{b,f,p} -= 1`. The skeleton's `recovery_pipeline` only *inserts* a
`DRAFTED_DUTY` block into the reserve's calendar; the horizon-long `RESERVE` block is never removed,
so `eligible_reserves`' `block_at(now).btype == RESERVE` test keeps finding the same crew on call.
Observed: reserve `R008` used **3 times** in a single 28-day scenario, `R000/R001/R002/R005` twice.

Combined with D1 and D3, this is the second reason the model thinks reserves are nearly free: they are
uncharged, infinitely reusable, and can be booked into overlapping duties.

**Fix:** on assignment, split the RESERVE block around the duty, insert REST after (L2), and only
restore reserve status at `REST_END` (E7 — currently unimplemented, see D9).

### D5 — Sick calls are disconnected from the roster **[verified]**

`generate_scenario` synthesizes pairings named `P{scenario}-{n}`; roster members hold pairings named
`L{i}-{t}`. No sick call ever refers to a crew member who exists, so E1's specified transition
("remove sick crew's block(s) from `Cal_c`") never fires. Demand is exogenous and **independent of
roster and reserve state** — which directly undercuts the spec's flagship claim that eligibility and
cascades are emergent. A sick call currently costs the airline an open pairing but never removes a
person from the available pool.

**Fix (highest-value single change):** sample sick calls *from crew who are on or about to report for
duty*, per §5.2 item 2 which already specifies this correctly. The gap is implementation-only, but it
is the load-bearing one.

### D6 — `seniority_order` is a dead knob, and inverted **[verified]**

`DraftSelector.select` sorts `reverse=True` for `senior_first` — descending seniority *number*, which
with `seniority=1` meaning most senior yields **most junior first**. Then the `junior_first` branch
re-sorts unconditionally, making the first sort dead code. Measured over 30 CRN scenarios,
`junior_first` and `senior_first` produce **bit-identical** cost vectors (E[C] = 176,202 both).

One of the two Stage-2 policy levers the MVP is supposed to compare currently does nothing.

### D7 — Cascade cost is double-counted (or undefined) in the objective

§5.6 states: "cascade costs are booked later by the cascade chain itself, so no double counting."
But §7.3's recourse function carries a **separate** `Σ_{e∈K(ω)} q^casc_e` term *in addition to* the
cascade items re-entering `O(ω)` and incurring their own reserve/draft/cancellation costs.
`details.md`'s own example for `q^casc` — "Ruined tomorrow's pairing, causing a new $5,000 scramble" —
*is* the recovery cost of the re-entered item.

Either `q^casc` double-counts, or it denotes something else (residual disruption cost not captured by
recovery) that is never defined. This corrupts the objective function, not just the prose. Decide and
write it down; if `q^casc` is kept, define it as strictly non-recovery residual cost.

### D8 — Validation targets are tunable, so V3/V4 are not gates

§8 states Phase 0 "tunes roster composition and rest rules until the emergent rate matches the
historical ≈20% band." That is calibration wearing validation's clothes: if you fit the inputs until
the output hits 20%, hitting 20% proves nothing about the model.

This matters more than it looks, because emergent-eligibility/cascade validation *is* the spec's
credibility mechanism — it's the argument for why anyone should believe the reserve number.

Also worth noting: the skeleton's realized eligibility rate is **8.3% (R=6) / 13.3% (R=10)** against a
30% target — and the spec's published §8 output block silently drops the `elig=` field that the code
prints. The one metric that currently fails its own validation gate is the one missing from the
showcase. (Cause is mostly D3/D4/D5 plus non-rotating reserves; but it should be stated, not omitted.)

**Fix:** take roster composition from actual D2 rosters, let the rates fall where they fall, and
report the gap. If tuning is unavoidable, split calibration and holdout periods and validate on
holdout only.

### D9 — Skeleton implements 4 of 9 specified events

Missing: `DELAY` (E2, no delay stream at all), `DUTY_END`/`REST_END` (E6/E7 — hence D4),
`UNCOVERED_DEADLINE` (E8 — cancellation is booked *immediately* on failure to cover rather than at the
deadline, so an item can never be rescued by a later-freeing reserve), `HORIZON_END` terminal penalty
(E9). Fine for a skeleton, but Phase 1 claims "the full event set" in 6–8 weeks — budget it explicitly.

### D10 — Smaller inconsistencies to close before implementation

- **Horizon contradiction.** §5.0.5 says T = 7 + 28 + 7 = 42 days; §5.1 says "MVP default 35 days =
  7-day warm-up + 28-day measurement window." Pick one (42 is the correct one — cool-down is needed
  for cascades seeded near the window edge).
- **Terminal penalty `V` is set by fiat.** §5.1 says "calibrated to average recovery cost";
  `details.md` shows $50,000 per unresolved flight against a $25,000 cancellation. `V` must exceed
  cancellation or policies game the boundary — but at 2× it becomes a dominant CVaR lever chosen
  arbitrarily. Specify the rule (e.g. `V = q^cnl × (1 + margin)`) and add a sensitivity test showing
  the recommended R is stable across a range of `V`.
- **Fairness constraint stated two ways.** §7.4 writes `max_c E[n_c^drafts/month] ≤ m_max` (an
  expectation across scenarios); the simulation enforces a *pathwise* per-crew cap inside each run.
  These are different constraints. Align the math to the code (pathwise is the operationally
  meaningful one — a crew member cares about their own month, not the ensemble average).
- **Identical roster in every scenario.** `build_roster` is called inside the scenario loop with a
  fixed seed, so the only cross-scenario variability is sick-call timing. This is defensible as a CRN
  choice (roster is a Stage-1 given), but it must be a *stated* choice — right now it reads as
  accidental, and it suppresses roster-composition variance that a real bid period has.
- **`TIER_OF_STATUS` defaults unknown block types to tier 2** via `.get(b.btype, 2)`; `REST` and
  `DRAFTED_DUTY` blocks therefore silently classify as "has a future pairing." Make unmapped types an
  error.

---

## 4. Realism gaps — ranked by leverage on the recommended reserve number

Ordered by how much each moves the output, not by how interesting it is.

### 4.1 Headcount is conserved in reality, but not in the model

`build_reserves` mints **new** crew (`R000…`, seniority 1000+i) disjoint from the 120 line holders, and
`n_line=120` is fixed regardless of `policy.n_reserves`. Total headcount is therefore 120 + R — it
*varies with the decision variable*. The model can buy reserves without giving anything up.

In reality reserve lines are bid from the same seniority list: **+1 reserve means −1 line holder**,
which simultaneously (a) shrinks the draftable pool and (b) puts that line holder's flying into open
time for someone else to cover. §7.4's `Σ R ≤ H_b` caps the total but does not model the coupling.

This is the single highest-leverage realism gap, and it is the missing force that would produce the
interior optimum §3/D1 shows is currently absent: without it, more reserves is always more capacity,
and the only thing pushing back is their price tag.

**MVP fix — cheap, needs no new data:** partition one fixed roster into reserve lines and flying lines
per policy, so raising R removes line holders and their pairings enter open time. This is also a
prerequisite for the reserve-line rotation work in §4.4.

### 4.2 Tail days drive CVaR, and the tail mechanism is the one excluded

CVaR₀.₉₅ is in the objective, and tail days are precisely when reserve capacity binds. But §5.2 item 3
models delays as cost + duty-extension only, with **no network propagation** — so the mechanism that
actually manufactures bad days (a delay cascading through aircraft rotations, stranding crew out of
base, breaking multiple downstream pairings at once) is absent. The severity regime multiplies
*intensities*, which produces more independent sick calls, not correlated structural breakage.

**MVP-compatible fix (do not build a network model):** calibrate the 4-state regime so that
*regime-conditional open-time volume and its within-day clustering* match historical bad days — let
the regime empirically absorb propagation. Then state explicitly in the V&V package that propagation
is represented in reduced form, and that CVaR is a *lower* bound on tail cost. Full propagation is a
Phase 3 item.

### 4.3 "Excluding voluntary pickup is neutral across policies" is wrong in a specific way

§1.4 accepts the omission on the grounds that the bias "applies equally to all candidate policies."
It does not. Voluntary open-time pickup is a substitute for **both** reserves and drafting, and take-up
depends on the premium offered and on how much open time exists — which depends on R. The omission
therefore inflates the marginal value of a reserve most in exactly the regions where drafting is
expensive. A bias that scales with the decision variable is not neutral; it shifts the optimum.

**MVP fix without building the layer:** one scalar `voluntary_absorption_rate ∈ [0, 0.4]` applied to
open-time items before the drafting branch, swept as a sensitivity. Phase 1 then *bounds* the bias
instead of asserting it away — and if the recommended R is stable across the sweep, that is a strong
result you can defend. If it isn't stable, you've learned the voluntary layer is Phase 2, not Phase 3.

### 4.4 Reserves need to be individuals with on/off patterns, not a count

§5.0.2 models `Res_{b,f,p}(t)` as a scalar count, and `build_reserves` gives each reserve a single
`RESERVE` block spanning the entire horizon. Real reserve lines have rotating on-call days, days off,
and distinct short-call (2 h notice) vs long-call (12 h) windows — L8 in the spec's own surrogate.

Without rotation you cannot reproduce: the L8 notification constraint, the "use them or lose them"
shortest-remaining-window selection rule §5.5 depends on, reserve utilization rates, or the 30%
eligibility target. This is a large part of why realized eligibility is 8–13% rather than 30%.

**Fix (MVP, cheap):** generate reserve *lines* (e.g. 5-on/3-off patterns with SC/LC designation) from
D2 rather than a headcount. The Stage-1 decision vector already has the right shape
(`{dow, short_call, long_call}` per §5.9) — the skeleton just doesn't honor it.

### 4.5 Tier-then-seniority is a policy being evaluated, not an optimum — say so

Strict tier ordering can be locally expensive: a Tier-1 draft (day off) whose own next pairing then
breaks costs more than a Tier-2 draft with nothing downstream. The mandated rule should stay — it's
the stakeholder's policy and the incumbent baseline — but the spec presents it as *the* selection
algorithm rather than as one candidate.

**Fix:** add a `myopic_total_cost` variant to the Phase-1 comparison grid that ranks candidates by
(draft cost + predicted cascade cost) rather than by tier. Quantifying the price of the mandated rule
is precisely what this tool is for, and it costs ~40 lines.

### 4.6 Second-order realism items (Phase 2+, listed so they aren't forgotten)

- **Sick-call clustering per crew** — absence propensity is heavily overdispersed across individuals
  and autocorrelated (a 4-day absence, not 4 independent 1-day ones). §5.2 samples duration but treats
  crew as exchangeable. NegBin at the crew level fixes most of it.
- **Reserve no-shows / unreachability** — D5 already carries the `no-show` outcome; a reserve is not a
  guaranteed resource. Modest effect, near-zero cost to add.
- **Deadhead feasibility** — cross-base repositioning currently costs money but is always available.
  In reality it depends on a seat existing on a flight that arrives in time.
- **Crew geography** — "day off at home base" vs "day off at a layover station" are very different
  Tier-1 drafts.
- **Draft refusal / grievance rate** — an involuntary assignment is not always accepted. Even a flat
  refusal probability changes the effective cost of aggressive drafting policies.
- **Multi-position pairings** — a sick FO and a sick CA on the same pairing are one cancellation, not
  two; MVP's single-category scope hides this until Phase 2 expansion.

---

## 5. Re-sequenced MVP — five gated slices instead of one block

Phase 1 as written (FULL eligibility + FULL cascades + 9 events + validation + reporting in 6–8 weeks,
with Phase 0 landing in parallel) is a single gate at the end of two months, on a foundation whose
correctness is currently unverified. Split it so every slice has an exit test that can fail early.

| Slice | Content | Exit gate | Phase-0 data needed (dataset ids from spec §6.1) |
|---|---|---|---|
| **1a** | Ledger + cost engine + policy object + CRN plumbing. Fix D1, D2, D3, D6. Synthetic data only. | **V1** (degeneracy: 0 reserves / ∞ reserves / 0 sick calls collapse to hand-computable values) + **V7** (bit-identical under `joblib`, in CI) + staffing scales linearly with R×horizon | **No** — start here immediately |
| **1b** | Real D2 rosters loaded; sick calls attach to actual crew blocks (D5); headcount conservation (§4.1); reserve lines with rotation + SC/LC (§4.4); E6/E7/E8 events (D4, D9) | **V2** (Erlang-B bound: single base, cascades off, shortfall probability within CI of the analytic formula) | Datasets D1/D2 only |
| **1c** | Eligibility Engine FULL, L0–L8 complete | **V3** on a **holdout** period, not the fitting period (§D8) | Datasets D2/D4/D5 |
| **1d** | Cascade Engine FULL; terminal penalty with sensitivity sweep | **V4** on holdout + recommended-R stability across `V` and across `voluntary_absorption_rate` (§4.3) | Datasets D6/D7 (draft reconstruction) |
| **1e** | Grid comparison over hand-picked policies + HTML report + exemplar drill-down | **V5** (SME trace walkthrough) + **V6** (cost backtest) | Datasets D7/D10 |

**Schedule risk the spec buries:** slices 1c and 1d both gate on Phase-0 derived datasets, and the
draft-event reconstruction (§6.3-1, D6 × D7 join) must recover ≥80% of drafts or *both* the tier
distribution and the cascade target degrade to "indicative" (§6.2). That single join is the critical
path for the two validation gates that give the whole system its credibility.

**Recommendation: run a one-week data spike on D6/D7 before committing Phase 1 dates.** Pull one month,
attempt the join, measure the recovery rate. If it lands below 80%, you need a different draft-identification
strategy (e.g. IOC action logs, or direct SME labelling of a sample) and you want to know that in week 1,
not week 7. Slice 1a runs in parallel and needs no data at all.

---

## 6. Immediate checklist

Before writing any code on top of the skeleton:

1. Fix D1 (per-day reserve staffing booking) — one line, invalidates every published number until done.
2. Fix D2 (`blake2b` instead of `hash()`) — one line, and make V7 a CI test.
3. Fix D3 (add L0 non-overlap invariant + property test) and D6 (seniority sort) and delete the dead re-sort.
4. Decide D7 (`q^casc` double-count) and amend §7.3 in the spec.
5. Reconcile the 35-day/42-day contradiction (D10) and the fairness-constraint mismatch (D10).
6. Add the sentence to §1.4 correcting the "voluntary pickup omission is policy-neutral" claim, and
   add `voluntary_absorption_rate` as an MVP sensitivity parameter.
7. Restore the `elig=` field to the §8 illustrative output and state the current 8–13% vs 30% gap with
   its cause.
8. Rewrite the §8 note so that Phase 0 calibrates *inputs from data* and validates on holdout — remove
   "tunes … until the emergent rate matches."

Repro artifacts for this review are in the session scratchpad: extracted skeleton, the staffing-cost
table, and the PYTHONHASHSEED reproducibility check.
