# 7. Formal Two-Stage Stochastic Program

**Version:** 3.0 (Air Transat instantiation, engineering edition) · **Date:** 2026-08-05

---
## What this section is

The mathematics the optimiser actually minimises. Every formula is followed by a `→ code` restatement
and a worked example with arithmetic you can check by hand.

**The whole thing in one sentence:** *pick the reserve staffing plan and the drafting rules that
minimise (guaranteed staffing cost) + (average cost of the chaos that follows) + (a safety margin for
the worst 5% of months).*

All costs CAD, all coefficients `[CONFIRM: Finance + Crew Planning]` placeholders from §4.4.2.

---

## 7.1 Sets and indices

| Symbol | Meaning | Air Transat MVP value |
|---|---|---|
| `b ∈ B` | Crew bases | `{YUL}` in the MVP; `{YUL, YYZ, YVR}` at scale |
| `f ∈ F` | Fleets | `{A321neoLR}`; A330 is a **separate problem instance**, not another index value (§4.5.1) |
| `p ∈ P` | Positions | `{FO}`; `{CA, FO}` at scale |
| `d ∈ D` | Days in the horizon | 42 days (7 warm-up + 28 measured + 7 cool-down) |
| `k ∈ {1..5}` | Draft impact tiers | §5.6 |
| `c ∈ C` | Crew members | The YUL A321neo LR FO population, `roster_size` |
| `ω ∈ Ω` | Scenarios | In practice a CRN sample `Ω̂ = {ω₁ … ω_N}`, N = 500–2,000 |
| `o ∈ O(ω)` | Open-time items realised in scenario ω | Emergent, not enumerable in advance |

Note the last row. `O(ω)` is not a fixed list you can write down before running the simulation: cascade
items add to it as the scenario unfolds. This is why the problem has no closed form.

---

## 7.2 First stage — the "upfront bill"

Before the bid period opens, Air Transat commits to a fixed reserve establishment. This cost is
deterministic: it is paid whether or not anyone gets called.

$$R = \big(R^{SC}_{b,f,p,d},\; R^{LC}_{b,f,p,d}\big) \in \mathbb{Z}_{\ge 0}$$

$$C_1(R) \;=\; \sum_{b,f,p,d} \Big( \kappa^{SC}\, R^{SC}_{b,f,p,d} + \kappa^{LC}\, R^{LC}_{b,f,p,d} \Big)$$

**In words:** add up the daily guarantee paid to every short-call and long-call reserve, across every
base, fleet, position and day of the bid period.

→ code:

```python
def stage1_cost(R: ReserveVector, costs: Costs) -> float:
    return sum(costs.kappa_sc * R.short_call[b, f, p, d] +
               costs.kappa_lc * R.long_call[b, f, p, d]
               for (b, f, p, d) in R.index)
```

> **The Daily Booking Rule:** This fixed staffing cost must accrue **daily** for each reserve on the ledger, at that exact day's timestamp. It cannot be booked as a single massive lump sum on Day 1, otherwise the financial reporting for specific weeks or weekends will be wildly inaccurate.

### Worked example — one week at YUL

`κ^SC` = $250/day, `κ^LC` = $180/day (§4.4.2).

| Day | Short-call held | Long-call held | Subtotal |
|---|---:|---:|---:|
| Mon | 4 | 2 | 4×250 + 2×180 = $1,360 |
| Tue | 4 | 2 | $1,360 |
| Wed | 4 | 2 | $1,360 |
| Thu | 4 | 2 | $1,360 |
| Fri | 4 | 2 | $1,360 |
| Sat | 5 | 2 | 5×250 + 2×180 = $1,610 |
| Sun | 5 | 2 | $1,610 |
| **Week total** | | | **$10,020** |

Over a 28-day measurement window: **$40,080** committed before a single disruption occurs. That is the
number the recovery savings have to beat.

> **Why §8.3's staffing column looks different.** The reference implementation has no short-call /
> long-call split yet (listed as absent in §8.1), so it charges a flat `κ = $250` per reserve per day:
> `250 × R × 21 measured days`. The two-rate calculation above is the target behaviour, implemented in
> slice 1b together with rule L8. The distinction matters because long-call reserves are cheaper *and*
> less useful — that trade is one of the Stage-1 decisions the optimiser should be making.

---

## 7.3 Second stage — the recourse, or "what the month actually cost"

### The Action Space (What the AI is allowed to do)
When a flight breaks (an open item $o$), the AI looks at the current state of the world ($s$) and must pick exactly one action:

1. **Assign a Reserve** ($r \in E$): Pick an available reserve who is legally allowed to fly.
2. **Draft a Pilot** ($c \in T_k$): Force a regular pilot to fly on their day off (searched in order of impact tiers $k=1 \to 5$, picking the most senior pilot first).
3. **Hold**: Do nothing and let the flight cancel.

$$a(o) \;\in\; \{\text{assign } r,\; \text{draft } c,\; \text{hold}\}$$

### What is $\theta$ (Theta)?
In academic math, $\theta$ represents the "Policy Settings" — the configurable knobs we allow the AI to twist to find a cheaper strategy. 

For example, a generic AI might have these $\theta$ knobs:
*   *Knob 1:* Should I draft Junior pilots first, or Senior pilots first?
*   *Knob 2:* What is the maximum number of times I can draft someone per month?
*   *Knob 3:* Should I use a YYZ reserve to cover a YUL flight, or just draft a YUL pilot?

**However, at Air Transat, almost all of these knobs are glued in place by the Union Agreement.** The AI is *not* allowed to optimize them.

| The Policy Knob ($\theta$) | Can the AI twist this knob? | Air Transat's Rule |
|---|---|---|
| **Drafting Order** | ❌ **No** (Locked) | Must draft by Impact Tier first, then Senior-First. |
| **Protected Days Off** | ❌ **No** (Locked) | No schedule block is exempt from drafting. |
| **Drafting Cap** | ❌ **No** (Locked) | There is no cap. Legality is the only limit. |
| **Cross-Base Reserve (`allow_cross_base`)** | ✅ **Yes** (Configurable) | Should the AI spend money on a deadhead flight to fly a YYZ reserve to YUL? |
| **Reserve Selection (`reserve_selection`)** | ✅ **Yes** (Configurable) | If two reserves are available, who goes first? (e.g., lowest hours, or longest rest?) |

**Why this matters:** Because almost all the drafting rules are locked by the union, the AI isn't really searching for a "smarter drafting policy". It is primarily searching for the right *number of reserves* (Stage 1). It is extremely important not to pretend the AI is optimizing drafting rules that the airline legally cannot change.

---

### The recourse cost

$$Q(R,\theta;\omega) = \sum_{o \in \mathcal{O}(\omega)} \Big[
\underbrace{\mathbb{1}^{res}_o\, q^{res}_o}_{\text{reserve use}}
+ \underbrace{\mathbb{1}^{drf}_o \big( q^{base} + q^{tier}_{k(o)} + q^{pos}_o \big)}_{\text{tiered draft}}
+ \underbrace{\mathbb{1}^{cnl}_o\, \big(q^{cnl} + q^{comp}_o\big)}_{\text{cancellation}}
\Big]
\;+\; q^{dly}(\omega) \;+\; V\big(s_T(\omega)\big)$$

**In words:** the cost of the month equals the cost of using standby crew, plus the penalties for
drafting off-duty crew, plus the cost of cancelling flights and compensating passengers, plus delay
costs, plus a penalty for anything still broken when the horizon ends.

### ⚠️ Crucial Math Rule: Cascade costs are NOT a separate term

Do not try to add a separate "cascade penalty" to the math. **That is a double count.**

Here is why: A cascade (a "domino effect") simply produces a *new* broken flight, which re-enters the list of open items `O(ω)`. It is then handled by the AI just like any other broken flight — so it organically generates its own reserve, draft, or cancellation costs. Adding an explicit cascade penalty on top of that would charge the airline for the same disaster twice.

**The correct statement:** `O(ω)` is defined **recursively**. It contains the exogenous open items from
the scenario stream *and* every item created by cascades, at every depth. `Q` is therefore evaluated by
the DES, not in closed form.

If a genuinely non-recovery residual cost is later identified, it may be added back as a separately
named, explicitly defined category — not as a vague catch-all.

### Term-by-term, with examples

**1. Reserve use — `1^res_o · q^res_o`**

`1^res_o` is 1 if a reserve covered item `o`. `q^res_o` is the *marginal* pay delta, not the whole
guarantee — the guarantee is already sunk in `C₁`.

| Item | Reserve used? | `q^res` | Contribution |
|---|---|---:|---:|
| O-991 | yes | 150 | $150 |
| O-992 | yes | 150 | $150 |
| O-993 | no (none eligible) | — | $0 |

**2. Tiered draft — `1^drf_o (q^base + q^tier_k(o) + q^pos_o)`**

| Situation | `q^base` | `q^tier` | `q^pos` | Total |
|---|---:|---:|---:|---:|
| Drafted from a day off at home in Montréal | 500 | 0 (tier 1) | 0 | **$500** |
| Drafted out of ground training | 500 | 900 (tier 3) | 0 | **$1,400** |
| Drafted from a day off, but currently in Punta Cana — needs a deadhead seat and a hotel night | 500 | 0 (tier 1) | 400 + 220 | **$1,120** |

**3. Cancellation — `1^cnl_o (q^cnl + q^comp_o)`**

`q^comp` is APPR compensation, which depends on how late the passengers end up (§4.4.3).

| Situation | `q^cnl` | `q^comp` | Total |
|---|---:|---:|---:|
| Cancelled, passengers rebooked within 3 h | 25,000 | 0 | **$25,000** |
| Cancelled, 180 passengers arrive 7 h late → $700 each | 25,000 | 126,000 | **$151,000** |

That second row is not a rounding error, and it is why cancellation dominates every other term in the
objective. A single cancelled wide-body rotation can cost more than the entire reserve establishment
for the month. **This is the mechanism that makes reserves worth buying**, and modelling APPR
compensation properly is therefore not optional detail.

**4. Delay — `q^dly(ω)`**

Delay minutes on covered flights, at `delay_cost_per_min` (§4.4.2). 60 minutes × $55 = $3,300.

**5. Terminal penalty — `V(s_T(ω))`**

Charged per open item still unresolved when the horizon ends, at `cancel_cost × 1.5` = $37,500.

Its purpose is to stop a policy from looking cheap by pushing recovery past the boundary. It must
exceed `q^cnl`, or the model learns that abandoning an item is cheaper than cancelling it. Because it
is also a dominant lever on the tail, gate **V9** requires a sensitivity sweep showing the recommended
reserve level is stable across a range of `V`.

---

## 7.4 The optimisation problem

$$\min_{R \in \mathcal{R},\, \theta \in \Theta} \;\;
C_1(R) \;+\; \mathbb{E}_\omega\big[Q(R,\theta;\omega)\big]
\;+\; \lambda \,\mathrm{CVaR}_{0.95}\big[Q(R,\theta;\omega)\big]$$

**In words:** find the plan with the lowest total of — guaranteed upfront cost, plus the average cost
of a month, plus a safety margin weighted by how much management cares about disaster months.

→ code:

```python
def objective(R, theta, scenarios, lam) -> float:
    Q = np.array([simulate(R, theta, w).measured_cost for w in scenarios])
    k = ceil(0.05 * len(Q))
    cvar95 = np.sort(Q)[-k:].mean()          # mean of the worst 5%
    return stage1_cost(R) + Q.mean() + lam * cvar95
```

### `E_ω` — expected value

The mean measurement-window cost across the CRN scenario set. Not "an average day" — an average
*month*, since the replication unit is a scenario.

### `λ` — the risk dial

`λ` is **not** a fitted parameter. It is a management input that encodes how much Air Transat is
willing to pay in average cost to avoid a bad month.

| λ | Management stance | Typical effect |
|---|---|---|
| 0.0 | Minimise average cost; accept tail exposure | Leaner establishment |
| 0.5 | Balanced | Moderate |
| 1.0 | Prioritise operational stability through the worst months | Fatter establishment |

**Report the whole λ curve, not one number.** The right deliverable is "at λ=0 the answer is 6, at λ=1
it is 10, and here is what each buys you" — because that is a decision Crew Planning and Finance should
make jointly, not one the model should make for them.

### `CVaR₀.₉₅` — conditional value at risk

The mean cost of the worst 5% of scenarios. Not the worst case (too noisy, driven by a single outlier)
and not the 95th percentile (says nothing about how bad the tail gets beyond it) — the *average of
everything past the 95th percentile*.

For Air Transat this is concretely: the January ice-storm weeks, the March break peak with a sick-call
cluster, the summer Atlantic peak with an ATC disruption in Europe.

### Worked example — why λ matters, from the reference run

From the patched reference implementation (§8), 100 CRN scenarios, synthetic roster:

| Reserves `R` | E[C] | CVaR₀.₉₅ |
|---:|---:|---:|
| 4 | 61,198 | 189,130 |
| **6** | **49,571** ← min | 109,860 |
| 8 | 52,359 | 89,670 |
| **10** | 60,961 | **78,730** ← min |
| 14 | 81,364 | 89,340 |

- At **λ = 0**, the answer is **R = 6**.
- At **λ = 1**, the objective at R=6 is 49,571 + 109,860 = 159,431; at R=10 it is 60,961 + 78,730 =
  **139,691**. The answer becomes **R = 10**.

Four extra reserves cost about $11,400 more in an average month and save about $31,000 in a bad one.
Whether that trade is worth making is a business judgement — and the model's job is to price it, not to
make it.

---

## 7.5 Constraints

$$
\begin{aligned}
&\text{(Service level)} && \mathbb{P}\big(\text{UncoveredLegs}(\omega; R,\theta) > u_{\max}\big) \;\le\; \varepsilon \\
&\text{(Legality)} && \text{every assignment satisfies L0–L8} \\
&\text{(Budget / headcount)} && \textstyle\sum_{f,p,d} R^{\cdot}_{b,f,p,d} \;\le\; H_b \quad \forall b
\end{aligned}
$$

### How each constraint is actually enforced

| Constraint | Enforcement | Can it be violated at runtime? |
|---|---|---|
| Service level | Evaluated after the run; infeasible policies are filtered from the candidate set | Yes — it is a chance constraint on the output |
| Legality L0–L8 | **In-simulation**: no illegal assignment is ever produced | No — by construction |
| Budget | Bounds the Stage-1 search space | No — the optimiser never proposes an infeasible `R` |

### Why there is no "Fairness" or "Draft Cap" Constraint

There is no mathematical constraint capping the maximum number of times a pilot can be drafted per month. **No such cap exists at Air Transat.** A crew member may be drafted as often as the legality rules and their schedule permit. 

Two consequences worth stating:

- Drafting frequency survives as a **reported KPI** on the final dashboard, not as a mathematical limit on the AI. And because drafting pays premium overtime, it measures the distribution of *wealth*, not an imposed burden.
- Uncapped drafting means the AI will repeatedly target the most senior crew. This concentration of disruption on a few schedules actually *increases* the risk of future cascade failures. The AI must accurately simulate this pain, not artificially cap it.

### Headcount conservation

`Σ R ≤ H_b` caps the total establishment but does **not** capture the real coupling: at Air Transat,
reserve lines are bid from the same seniority list as flying lines, so **+1 reserve means −1 line
holder** whose flying must be covered by someone else (§5.10). The budget constraint is a bound; the
carve-out is a *mechanism*, implemented in the population builder.

---

## 7.6 Sample-average approximation and the CRN property (The Weather Control Check)

Because we can't test every possible future, we test a sample of $N$ scenarios (usually $N=100$) and average them out. This is the math for taking that sample average:

$$\widehat{J}(R,\theta) = C_1(R) + \frac{1}{N}\sum_{i=1}^{N} Q(R,\theta;\omega_i) + \lambda\, \widehat{\mathrm{CVaR}}_{0.95},
\qquad
\widehat{\mathrm{CVaR}}_{0.95} = \frac{1}{\lceil 0.05N \rceil} \sum_{i \in \text{worst } 5\%} Q(R,\theta;\omega_i)$$

### What is the "CRN Property"?

**CRN** stands for **Common Random Numbers**. It is the most powerful variance-reduction trick in simulation, and it works like this:

Imagine testing two cars (Policy A and Policy B) for fuel efficiency. 
*   **The Bad Way (Unpaired):** You drive Car A through a blizzard up a mountain, and Car B down a sunny highway. If Car B gets better mileage, you don't know if it's because Car B is a better car, or just because it had better weather.
*   **The CRN Way (Paired):** You force both cars to drive through the *exact same blizzard* up the *exact same mountain*. Now, any difference in fuel efficiency is 100% due to the car itself.

In our AI, we use the master "seed" to force Policy A (e.g. 6 reserves) and Policy B (e.g. 10 reserves) to experience the *exact same* 100 months of sick calls.

Because the weather is identical, the mathematical variance between the two runs shrinks drastically. This allows the optimiser to confidently detect small differences without needing to run a million simulations.

$$\mathrm{Var}[\widehat{J}-\widehat{J}'] \;\ll\; \mathrm{Var}[\widehat{J}] + \mathrm{Var}[\widehat{J}']$$

→ code (notice how the arrays are subtracted element-by-element, comparing identical months):

```python
def compare(policy_a, policy_b, scenarios) -> dict:
    qa = np.array([simulate(policy_a, w).measured_cost for w in scenarios])
    qb = np.array([simulate(policy_b, w).measured_cost for w in scenarios])
    
    # CRN allows this exact PAIRED subtraction:
    diff = qa - qb                       
    
    se = diff.std(ddof=1) / np.sqrt(len(diff))
    return {"mean_diff": diff.mean(), "ci95": 1.96 * se, "t": diff.mean() / se}
```

### Worked example, from the reference run at N = 100

```
R6 vs R10 paired difference: −$11,390 ± $3,207 (95% CI), t = −7.0   → strongly significant
```

If we hadn't used the CRN trick (if we let the sick calls be completely random between runs), the "noise" of the bad weather would have completely drowned out the $11,390 difference, and the AI would have been flying blind. CRN costs nothing but programming discipline (Gate V7), but it is what makes a 100-scenario run actually informative.

---

## 7.7 Search strategy

| Phase | Method |
|---|---|
| **MVP** | Exhaustive comparison of a hand-picked candidate grid (§3). No optimiser — an optimiser searching an unvalidated model finds the model's bugs, not the airline's optimum. |
| **Phase 2** | Bayesian optimisation (GP/TPE) over the integer lattice of `R` (relaxed-and-rounded). Ranking-and-selection (e.g. OCBA) over `Θ` is retained but is now a **minor** component: with draft ordering mandated and no protected-block choice, `Θ` holds only the reserve-selection rule, the cross-base flag and the draft cap (§7.3). Budget the effort accordingly — this is mostly a Stage-1 search. |

**Structure the Phase-2 search by fleet family.** A321 and A330 share no type rating, so cross-fleet
terms are almost entirely infeasible. Two coupled sub-problems, not one search space with twice the
dimensions (§4.5.1).

---

## 7.8 Where this sits in the literature

Two remarks for the academic track:

1. **Why there is no closed form.** Because eligibility and cascades are emergent, `Q` is only
   evaluable by simulation. The problem is a **simulation-optimisation / stochastic program with
   recourse-by-policy**, positioned between classical newsvendor-style reserve-sizing models (closed
   form, but assume eligibility away) and full dynamic-programming crew recovery (exact, but
   intractable at this scale).

2. **The Erlang-loss sanity bound — a required verification test (gate V2).** Treat reserves as `s`
   servers and eligibility-thinned sick calls as Poisson arrivals with offered load `a = λ_eff / μ`.
   The shortfall probability should approximate the Erlang-B formula:

   $$B(s, a) = \frac{a^s / s!}{\sum_{i=0}^{s} a^i / i!}$$

   In the no-cascade, single-base regime, FULL-mode DES results **must** fall within the confidence
   interval of this analytic value. If they do not, the simulation has a bug — this is the cheapest
   available check that the machinery works at all, and it should be in CI.
