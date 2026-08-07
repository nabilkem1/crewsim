# Phase 2 — Optimisation & Scale

**Epics E2.1 – E2.5** · 6 stories · Gate: **recommendation stable under search**

> ## ⚠️ Deliberately coarse. Do not refine yet.
>
> Every story here has `check: TBD` and a `refine_when:` condition. That is intentional, not
> unfinished work.
>
> Phase-2 stories depend on what Phase 1 *learns*. Writing detailed acceptance criteria now would
> encode today's assumptions into next quarter's work — which is exactly how four wrong assumptions
> (protected blocks, the draft cap, selectable junior-first ordering, an invented willingness rate)
> got as far as they did. **Refine an epic only when its predecessor slice has passed its gate.**

---

## The scope correction that shapes this whole phase

At Air Transat, **drafting has no parameters**. The order is mandated (impact tier, then senior first),
nothing is protected, and there is no cap on drafts per crew. Every drafting parameter a generic
two-stage model would optimise is a constant here.

What remains in θ is `reserve_selection` and `allow_cross_base_reserve` — both about **reserve
dispatch**, not drafting.

**Consequences for this phase, which must not be quietly forgotten:**

- The search is dominated by the **integer reserve vector**. Ranking-and-selection over θ is a minor
  component with very little left to rank — budget accordingly.
- The highest-value analytical runs are the **counterfactuals** (S1e-05) that price the mandated rules,
  not a search over rules the airline cannot change.
- The system is a **reserve-sizing tool that models drafting faithfully as the cost consequence of
  under-staffing** — not a drafting-policy optimiser. Phase-2 deliverables should say so.

---

## E2.1 — Optimisation engine

### ⏳ [TODO] S2-01 — Bayesian optimisation over the integer reserve lattice
**Size:** `L`

**As a** researcher **I want** Bayesian optimization over reserve levels
**so that** I can efficiently find the optimal staffing without an exhaustive grid search.

Optuna TPE over R, relaxed-and-rounded. Depends on S1e-07. Spec §7.7.
**Refine when** slice 1e has passed.
*Sketch of the check:* converges to the exhaustive grid's optimum in far fewer runs; **fails if** it
finds a different optimum on the same seed — that is a search bug, not a better answer.

---

### ⏳ [TODO] S2-02 — Ranking & selection over θ
**Size:** `M`

**As a** researcher **I want** ranking and selection over secondary parameters
**so that** I can finely tune the rules efficiently.

OCBA or similar over the small discrete set. Depends on S2-01. Spec §7.3, §7.7.
**Scope note:** θ holds two levers. This is a small story wearing a large story's name.

---

## E2.2 — Multi-fleet & multi-base

---

### ⏳ [TODO] S2-03 — A330 as a separate problem instance
**Size:** `L`

**As a** modeller **I want** the A330 treated as a separate problem instance
**so that** the optimization isn't muddied by infeasible cross-fleet interactions.

Depends on S2-01. Spec §4.5.1.
**Not one larger search space.** No common type rating between A321 and A330 means cross-fleet
substitution is infeasible and cross terms are wasted search. Two loosely-coupled sub-problems sharing
infrastructure and the budget constraint `Σ R ≤ H_b`.
*Sketch:* two independent optimisations, coupled only at budget; **fails if** one search space is built
with infeasible cross-fleet terms.

---

## E2.3 — Scale

---

### ⏳ [TODO] S2-04 — joblib → Ray on AKS
**Size:** `L`

**As a** developer **I want** the simulation to run on Ray across an AKS cluster
**so that** it can scale massively without losing reproducibility.

Depends on S2-01. Spec §4.1, §3. Aligns with the existing digital-twin AKS stack.
*Sketch:* **V7 must still pass distributed.** Reproducibility that holds on one machine and breaks
across a cluster is the same class of defect as D2, one layer up.

---

## E2.4 — Variance reduction

---

### ⏳ [TODO] S2-05 — Stratified sampling by severity regime
**Size:** `M`

**As a** researcher **I want** stratified sampling by severity regime
**so that** confidence intervals are narrower and results converge faster.

Depends on S2-01. Spec §3.
*Sketch:* narrower CI at the same scenario count; **fails if** the point estimate shifts —
stratification must be unbiased, or it is just a different model.

---

## E2.5 — Cabin crew

---

### ⏳ [TODO] S2-06 — Cabin crew, own cost file, multi-position complement
**Size:** `L`

**As a** planner **I want** cabin crew modeled with their own cost file and multi-position rules
**so that** I can optimize their distinct staffing requirements.

Depends on S2-03. Spec §4.5.1, §6.1.
**Refine when** Crew Planning answers which group is the higher-value target
(`QUESTIONS_TO_ASK.md` §2.4).

Two things that must be right from the start:
- **CUPE coefficients per local** (4041 YUL / 4047 YYZ / 4078 YVR). Base is an *agreement boundary* for
  this group, not just a location. Pilot coefficients must not be reused.
- **Multi-position complement.** A sick CA and a sick FO on the same trip is **one** cancellation, not
  two. Note the mock corpus does not model this — each pairing there belongs to a single crew member —
  so it will need extending before this story can be tested.

---

## Other Phase-2 candidates, not yet stories

Raised during Phase-1 work, parked deliberately:

| Candidate | Why it is parked |
|---|---|
| Reserve no-shows / unreachability | D5 carries the field; effect is modest. Needs the §1.5 answer from the IOC |
| Deadhead seat availability | Currently assumed always available; matters most in peak season |
| Crew geography — day off at home vs at a layover station | Two very different tier-1 drafts |
| Draft refusal rate | Likely near zero given drafting is premium-paid, but unconfirmed |
| Roster variability across bid periods | Currently one roster across all scenarios, a stated CRN choice (§5.2) |

