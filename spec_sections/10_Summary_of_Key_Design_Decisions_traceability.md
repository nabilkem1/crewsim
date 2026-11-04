# 10. Summary of Key Design Decisions (traceability)

**Version:** 3.0 (Air Transat instantiation, engineering edition) · **Date:** 2026-08-05

---
## What this section is

The decision register. Every non-obvious choice in this specification, why it was made, and where it is
implemented. Use it when someone asks "why does it do it *that* way?" six months from now.

---

## 10.1 Scope and purpose

| Decision | Choice | Rationale | Where implemented |
|---|---|---|---|
| System purpose | **Offline policy simulation**, not real-time decision support | Reserve sizing is a planning-timescale problem. A day-of "what-if" mode is a possible future track, explicitly out of scope. | §1.4 |
| Starting phase | **MVP**: single fleet/position/base, hand-picked policy grid, no optimiser | An optimiser searching an unvalidated model finds the model's bugs, not the airline's optimum. | §3 |
| MVP scope | **YUL · A321neo LR · First Officer · pilots (ALPA)** | Principal crew base; no type-rating overlap with the A330 fleet so qualification is hard-binding; small enough population to reason about by hand. | §1.5, §4.4.1 |
| Voluntary recovery layer | **Excluded**, with a swept sensitivity parameter | Scope directive. ⚠️ Corrected from v2: the omission is **not** policy-neutral, because voluntary take-up depends on the reserve level. Bounded rather than assumed away. | §1.4 |
| Legality | **Surrogate** with a small conservatively-biased rule set (L0–L8) | Scope directive; a full rules engine is Phase 3. Surrogate-legal ⇒ almost always truly legal. | §5.4 |
| Season | **An experiment dimension**, not a config default | Air Transat's summer Atlantic and winter sun programmes are different problems with different correct reserve levels. Deliverable is a per-bid-period vector. | §4.5.2 |
| Fleet families | **Separate problem instances**, not extra index values | No common type rating between A321 and A330, so cross-fleet substitution is infeasible and cross terms are wasted search. | §4.5.1, §7.7 |

---

## 10.2 Modelling decisions

| Decision | Choice | Rationale | Where implemented |
|---|---|---|---|
| Eligibility (≈30%) and cascades (≈20%) | **Emergent from crew state**; the historical figures are *validation targets*, not inputs | Both quantities are functions of the decision variable, so taking them as fixed inputs is a category error. This is the model's core contribution. | §5.5, §5.7, §9/V3–V4 |
| Draft selection | **Impact tier first, then SENIOR first** — both mandated, both constants | Air Transat's operating rule, supplied by the business. Not a decision variable. `junior_first` survives only as a labelled counterfactual that may never appear in a recommendation. `[CONFIRM: Labour Relations]` — this is the inverse of the common industry pattern and should be pinned to the agreement clause. | §5.6, §3 |
| Protected blocks | **Removed — the concept does not exist at Air Transat** | ⚠️ v2 defined rule L9 making vacation and simulator blocks draft-prohibited. No schedule block is contractually exempt from drafting here. The rule was deleted rather than defaulted off, since a disabled rule invites re-enabling. Tiers 4 and 5 remain the most expensive options, never forbidden ones. | §5.4, §5.6, §7.5 |
| Draft cap | **Removed — no such cap exists** | ⚠️ v2 capped drafts per crew per month and enforced it in the selector. A crew member may be drafted as often as legality and their schedule permit. `n_c` survives as a KPI. Removing it measurably raised cascades and cost at low reserve levels — the cap was doing structural work the agreement does not require. | §5.6, §7.5, §8.3 |
| Drafting as premium work | **Reframed** | Drafting is paid at a premium, so crew want it — which is *why* it is senior-first. Seniority gets first call on lucrative work, exactly as in bidding. The v2 framing of drafting as an imposed burden with employee-relations damage was wrong, and the fairness KPIs read as earnings distribution, not burden distribution. | §1.1, §1.3.5, §5.6, §9.4 |
| Stage-2 policy space | **Empty of drafting parameters** | Order mandated, nothing protected, no cap. The only remaining θ members govern reserve dispatch. This is a Stage-1 reserve-sizing problem with a fixed recourse rule, and the spec no longer promises a drafting-policy search. | §1.2, §7.3, §7.7 |
| Reserve representation | **Individual crew members** holding RESERVE blocks, not a scalar count | A count cannot express SC/LC notification windows (L8), reserve days off, or the shortest-remaining-window selection rule. | §5.0.2 |
| Headcount | **Conserved** — reserves are carved out of the roster, not added to it | Reserve lines are bid from the same seniority list. +1 reserve = −1 line holder whose flying must be covered. This corrects the recommended *level*, not the shape of the cost curve: without it each candidate `R` is compared against a different, larger workforce, so a reserve's opportunity cost is missing and the model over-recommends. | §5.10 |
| Disruption correlation | **Latent 4-state daily severity regime** driving all streams, fitted per season | Independent streams produce a world where bad things never coincide, tail days vanish, and the model under-staffs. The `SEVERE` self-transition produces multi-day bad stretches. | §5.2 |
| Regime estimation (F-42) | **Hidden Markov model** (hmmlearn, per base × season) inferring the regime from D8 delays/cancellations, D4 sick calls and D2 crew on duty; D9 `disruption_class` is **no longer an input** | The regime is never observed, so a supplied label was an undefined business rule, and quantile cut-points imposed the share of days per state. The HMM learns states, persistence and per-state intensities jointly by maximum likelihood, with a BIC check on the number of states and a holdout log-likelihood. On the mock corpus it recovers the hidden regime on ~82% of days (quantile labels: 25.8%). | §5.2, §6.3-4 |
| Cascade cost | **The recovery cost of the item the cascade creates** — no separate additive term | ⚠️ Corrected from v2, which double-counted by carrying `Σ q^casc` on top of cascade items re-entering the open-time queue. | §5.7, §7.3 |
| Objective | `E[C] + λ·CVaR₀.₉₅` + service-level chance constraint; **hard costs only** | Tail-risk pricing with no invented soft-cost weights. λ is a management dial; the deliverable is the λ curve, not a point. | §7.4 |
| Fairness constraint | **Pathwise** per-crew cap inside each run | ⚠️ Corrected from v2, which wrote it as a bound on the expectation across scenarios. A crew member experiences one month, not an ensemble. | §7.5 |
| Terminal penalty | `cancel_cost × 1.5`, with a mandatory sensitivity sweep | Must exceed cancellation cost or the model learns that abandoning an item beats cancelling it. It is also a dominant CVaR lever, so it cannot be set silently by fiat. | §5.0.5, §9/V9 |
| Horizon | **42 days** = 7 warm-up + 28 measured + 7 cool-down | ⚠️ Corrected from v2, which stated 35 days in one section and 42 in another. | §4.4.1, §5.0.5 |

---

## 10.3 Engineering decisions

| Decision | Choice | Rationale | Where implemented |
|---|---|---|---|
| Variance control | **CRN** via hierarchical `SeedSequence` streams, with per-event derived generators | Turns policy comparison into a paired comparison. Measured: ±$4,139 CI at N=100 against a per-policy σ on the order of the mean. | §5.2, §7.6 |
| Seed derivation | **blake2b**, never Python's `hash()` | `hash()` on strings is salted per interpreter by `PYTHONHASHSEED`, so reproducibility silently breaks under multiprocessing — the MVP's stated parallel path. | §4.3, §8.2 |
| Cost accounting | **Event-level ledger**; nothing is only-aggregated; every row carries `root_event_uid` | Lets a Thursday cancellation be attributed to the Tuesday sick call three cascade levels back. Cheap now, impossible to retrofit. | §2.3/C2, §5.8 |
| Cost accrual timing | Costs booked **when incurred** — reserve staffing accrues per reserve per day | ⚠️ Corrected from v2, which booked the whole horizon at `t=0` where the warm-up filter discarded it, making E[C] fall monotonically in reserve count. | §5.8, §8.1 |
| Legality rule set | **L0 added** as the first rule: single assignment, checked over duty + obliged rest | ⚠️ v2 had no single-assignment rule at all; running it produced 1,030 physically impossible assignments across 20 scenarios. Physical feasibility precedes every other rule. | §5.4, §9/V8 |
| Policy representation | **Serialisable Pydantic object**, hash-pinned to a cost-coefficient file version | Full reproducibility chain: data → params → scenarios → policy → results. | §2.3/C3, §5.9 |
| Model fidelities | **FULL** and **REDUCED** behind one interface; REDUCED never produces a recommendation | REDUCED assumes away the two things the model exists to compute. | §2.3/C4 |
| Engine isolation | `engine/` must not import `simpy` | Unit tests run in microseconds instead of spinning up an `Environment`. | §4.2 |
| Parameters | **One registry** (§4.4); no numeric constants anywhere else | v2's numbers had already drifted (35 vs 42-day horizon) across sections. | §4.4 |
| Validation discipline | **Fitting window and holdout window**, strictly separated | ⚠️ Corrected from v2, which proposed tuning inputs until the emergent rates matched the targets — calibration wearing validation's clothes. | §6.4, §9.2 |
| Delivery | **Five gated slices**, each with a test that can fail | v2's Phase 1 was one 6–8 week block ending in a single gate — a two-month bet on an unchecked foundation. | §3 |
| Stack | Python 3.11 · SimPy · NumPy `SeedSequence` · Polars · Pydantic · Parquet · joblib→Ray · Optuna | Aligns with the existing AKS + Delta Lake digital-twin architecture. | §4.1 |

---

## 10.4 Air Transat instantiation

| Item | Value | Source |
|---|---|---|
| Crew bases | YUL (Montréal), YYZ (Toronto), YVR (Vancouver) `[CONFIRM: Crew Planning]` | This list is inferred from the three CUPE cabin-crew locals; **the pilot base list has not been verified and may differ.** MVP uses YUL only. |
| Fleet families | A321 family (A321neo LR, A321-200) · A330 family (A330-200, A330-300) | Separate problem instances — no common type rating |
| Pilot agreement | ALPA, five-year term 1 May 2025 – 30 April 2030 | `configs/costs_pilots.yaml` |
| Drafting order | **Impact tier, then senior first** — always. No junior-first option. | Supplied by the business |
| Why senior-first | Drafting is **premium-paid**, so it is sought-after work allocated by seniority — the same principle as bidding | Supplied by the business |
| Protected blocks | **No such concept.** Every schedule block is draftable; tier cost is the only differentiator. | Supplied by the business |
| Draft cap | **None.** A crew member may be drafted as often as legality and their schedule permit. | Supplied by the business |
| Cabin crew agreement | CUPE Locals 4041 (YUL), 4047 (YYZ), 4078 (YVR) | `configs/costs_cabin.yaml`, Phase 2. Base is an *agreement boundary* for this group, not just a location. |
| Crew regulation | CARs Part VII, Subpart 700 (flight duty and rest) | Approximated by the legality surrogate; **not** a compliance tool |
| Passenger compensation | APPR — large carrier: $400 / $700 / $1,000 CAD for 3–6 h / 6–9 h / ≥9 h within carrier control | `[CONFIRM: Legal]` — verify current CTA schedule |
| Privacy | Québec Law 25 — pseudonymisation at ingestion, seniority as ordinal rank only | §6.2 |
| Seasons | Winter sun (Dec–Apr) · Summer Atlantic (Jun–Sep) · Shoulder (May, Oct–Nov) | `configs/seasons.yaml`; regime model fitted per season |
| Currency | CAD throughout | §4.4.2 |

> **All cost coefficients in this specification are `[CONFIRM: Finance + Crew Planning]` placeholders**
> chosen to be the right order of magnitude so that worked examples are arithmetically checkable. None
> is an Air Transat figure. §9.3 requires every outstanding placeholder to be listed in any report whose
> result depends on it.

---

## 10.5 Open decisions

Things this specification deliberately does not settle, listed so they are not mistaken for oversights.

| Open question | Who decides | By when |
|---|---|---|
| Actual cost coefficients (κ, tier surcharges, cancellation cost, delay per minute) | Finance + Crew Planning | Before slice 1e (V6 cost backtest) |
| **The published line count** for the bid period — total lines, how many were reserve lines, total credit/block hours covered, and who on the list was not awarded a line. Now a config knob (`population.roster_size`, `demand.pairings_per_bid_period`) and swept by V9, so it does not block coding — but slice 1b cannot be validated without the real figure. See §1.5. | Crew Planning | Before slice 1b **validation** |
| ~~Whether drafting from protected blocks is ever permitted~~ | **Answered: no protected-block concept exists.** Rule L9 removed. | Closed 2026-08-05 |
| ~~Is `max_drafts_per_crew_month` real?~~ | **Answered: no. No cap exists** — legality and schedule feasibility are the only limits. | Closed 2026-08-05 |
| ~~Is senior-first the inverse of the industry norm?~~ | **Answered: no.** Drafting is premium-paid, so senior-first is the ordinary seniority principle applied to desirable work. | Closed 2026-08-05 |
| Clause reference for the senior-first order and the tier definitions, for the record | Labour Relations | Before slice 1e |
| λ (the risk dial) | Executive / Finance | At recommendation time — report the whole curve, not a point |
| Whether cabin crew or pilots is the higher-value Phase 2 target | Crew Planning | End of Phase 1 |
| Whether draft-event reconstruction clears the ≥80% recall gate | Data spike, week 1 | **Before Phase 1 dates are committed** |

The last row is the one that can move the schedule. See the warning in §3.
