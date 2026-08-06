# 1. Problem Statement

**Version:** 3.0 (Air Transat instantiation, engineering edition) · **Date:** 2026-08-05

---
## What this section is

The "why does this software exist" section. If you only read one section before writing code, read
this one — every design decision downstream is traceable to something here.

**One-sentence summary:** Air Transat must decide, weeks before each bid period starts, how many crew
members to pay to sit at home doing nothing, and this system simulates that bet thousands of times so
the decision is made from evidence instead of intuition.

---

## 1.1 Operational context

Air Transat's Integrated Operations Centre (IOC) manages crew disruption continuously: sick calls,
delays, irregular operations (IROPS), maintenance events, and weather. Underneath the day-to-day
firefighting sits one recurring, expensive, structural decision — the balance between two ways of
covering flying that has lost its crew:

**Reserve crews.** Crew members paid to be on standby.

- *Short-call (SC):* must be reachable and able to report within roughly two hours. Effectively on
  duty at home.
- *Long-call (LC):* longer notice, typically overnight. Cheaper, less responsive.

A reserve who is never called is pure cost. A reserve who *is* called is the cheapest recovery
instrument available — you are paying the guarantee anyway, so the marginal cost of using them is
small.

**Drafting.** Assigning a crew member who was *not* on reserve — someone on a day off, on a future
pairing, in training, or on vacation — to cover an open assignment, at premium pay.

Two Air Transat facts about drafting shape this entire model, and both differ from what a generic
crew-recovery model would assume:

1. **Drafting is paid at a premium, so crew want it.** It is not a penalty. That is precisely why it is
   allocated **senior first** — seniority gets first call on lucrative work, exactly as it gets first
   call on good trips in a bid. Within each impact tier, the most senior available crew member is taken.
2. **Nothing is exempt and nothing is rationed.** There is no protected-block concept, and no cap on how
   often one person may be drafted in a month. The only limits are the legality rules and whether the
   schedule physically permits it.

The critical property, and the reason a spreadsheet cannot answer this question:

> **Drafting cost is not a constant.** It depends on what the drafted crew member was doing at the
> moment they were drafted, and it can create *new* disruptions later in the schedule.

### Worked example — the same draft, three different prices

An A321neo LR trip out of YUL loses its First Officer on Tuesday morning. No reserve is eligible.
Three candidates exist. All costs CAD, all `[CONFIRM: Finance]` placeholders from §4.4.2:

| Candidate | What they were doing | Tier | Immediate cost | What happens next |
|---|---|---|---|---|
| FO Tremblay | Day off at home in Montréal | 1 | 500 + 0 = **$500** | Nothing. Cheapest possible draft, and the tier the airline reaches first. |
| FO Roy | Holds a pairing departing Thursday | 2 | 500 + 300 = **$800** | Thursday's pairing is now uncovered. That becomes a *new* open item, which may itself need a draft. **The $800 is not the real cost.** |
| FO Bouchard | Week two of annual vacation | 4 | 500 + 2,500 = **$3,000** | **Draftable.** Air Transat has no protected-block concept — vacation is the most expensive tier, not a forbidden one. Reached only once tiers 1–3 are exhausted. |

The naive model prices a draft at one number. The real cost of drafting FO Roy is $800 *plus whatever
Thursday costs*, which might be another draft, or a cancellation at $25,000. That downstream chain is
what this system exists to measure.

### The tension in one line

```
too many reserves  → high guaranteed staffing cost, low utilisation
too few reserves   → frequent drafting → high premium-pay cost and downstream
                     schedule instability (each draft can break a later trip)
```

Both failure modes are expensive. The optimum is interior, and nobody currently knows where it is.

---

## 1.2 The decision problem

> **Determine the reserve staffing level (by base, fleet, crew category, and day of week) and the
> drafting-policy parameters that minimise Air Transat's total expected operational recovery cost over
> a bid period, while maintaining service levels and regulatory compliance.**

This is a **two-stage stochastic optimisation problem**. The two stages are separated by *when the
decision is made* and *what is known at that moment*:

| | Stage 1 — "here and now" | Stage 2 — "recourse" |
|---|---|---|
| **When** | Weeks before the bid period opens | Day of operation, in real time |
| **Decision** | The reserve vector: how many reserves, of which call type, at which base, on which days | Which recovery action to take for each open item |
| **Known at the time** | Historical distributions only. Nothing about the actual month. | The disruption that just happened, and current crew state |
| **Reversible?** | **No.** Committed and published. | Yes, per event |
| **Represented as** | An integer vector `R` | A *parameterised policy* `θ`, not a free choice |

The second row of "Represented as" is the modelling decision that makes the problem tractable. We do
**not** solve a fresh optimisation for each disruption on each simulated day — that would be a crew
recovery optimiser, a different and much larger system. Instead, Stage 2 is a **rule with knobs**: for
example "search draft candidates by impact tier, senior first within tier, never draft anyone twice
in a month." The optimiser searches over the knob settings; the simulation evaluates each `(R, θ)` pair
against a fixed set of stochastic scenarios.

**At Air Transat, θ contains no drafting parameters at all.** The order is mandated (impact tier first,
then senior first), nothing is protected, and there is no cap on drafts per crew. Every drafting
parameter a generic model would optimise is a constant here. What remains in θ — the reserve-selection
rule and cross-base deadheading — governs *reserve dispatch*, not drafting.

**This changes what the system is.** It is not a drafting-policy optimiser, because there is no drafting
policy to optimise. It is a **reserve-sizing tool that models drafting faithfully as the cost consequence
of under-staffing.** That is arguably a stronger position: the recourse rule is a documented fact rather
than a modelled guess. See §7.3.

### Worked example — what a candidate decision actually looks like

```yaml
policy_id: YUL-A321neoLR-FO-R14-juniorfirst-v3
stage1:                                   # committed weeks in advance, irreversible
  reserves:
    - {base: YUL, fleet: A321neoLR, position: FO, dow: [1,2,3,4,5], short_call: 4, long_call: 2}
    - {base: YUL, fleet: A321neoLR, position: FO, dow: [6,7],       short_call: 5, long_call: 2}
stage2:                                   # the rule the IOC follows on the day
  # Drafting has NO parameters at Air Transat: tier order and senior-first are
  # mandated, nothing is protected, and there is no cap. Only reserve dispatch
  # is configurable.
  allow_cross_base_reserve: true
  reserve_selection: shortest_remaining_window
```

The system's job is to tell Crew Planning which of these YAML files leads to the lowest expected cost —
and, just as importantly, which one survives a bad January.

---

## 1.3 Key modelling principles

These six principles are what separate this model from a reserve-sizing spreadsheet. Each one corrects
a specific, known failure of naive models.

### 1. Eligibility is emergent, not exogenous

When a sick call happens, only a *subset* of reserves can actually cover it — they must hold the right
type rating and position, be at the right base, be legally rested, and be reachable within the required
notice. Historically that subset is roughly **30%** of the reserve pool.

The naive model takes 30% as an input parameter. That is a category error, because **the eligible
fraction is itself a function of the decision you are trying to make**. Add more reserves at YUL and
the eligible fraction changes. Change the short-call/long-call mix and it changes again.

So in this model, eligibility is *computed* per event from the Crew State Engine, and 30% becomes a
**validation target**: if the simulation produces a wildly different number, the model is wrong and we
find out before anyone trusts its output.

> A reduced-form `Bernoulli(p_elig)` variant is retained for smoke tests and coarse screening only. It
> must never be used for a recommendation.

### 2. Cascades are emergent, not exogenous

Drafting FO Roy (from the §1.1 example) removes them from Thursday's pairing. Whether that creates a
new problem is not a coin flip — it is a **deterministic consequence of Roy's calendar**, which the
model already holds. Historically ≈20% of drafts cascade. Same treatment as above: computed, then
validated against 20%.

### 3. Drafting cost is state-dependent

See the three-candidate table in §1.1. Cost is computed from the drafted crew member's status at the
moment of drafting, plus every downstream cost the draft causes.

### 4. Disruption streams are correlated

Sick calls, weather disruptions, and delays are **not** independent. A February ice storm at YUL
produces delays *and* elevated absence *and* duty overruns, all on the same day.

This matters more than it sounds. The days that determine how many reserves you need are precisely the
bad days. If you model each stream independently, you generate a world where bad things never coincide,
tail days effectively vanish, and the model confidently under-staffs. This system therefore drives all
streams from a shared **latent daily severity regime** (§5.2).

### 5. Hard costs versus hard constraints

| Kind of thing | Where it goes | Example |
|---|---|---|
| Monetisable cost | **Into the objective function** | Draft premium, hotel, deadhead, APPR compensation |
| Contractually prohibited action | **A hard constraint** | An assignment that breaks a duty or rest limit (rules L0–L8). *Note: at Air Transat there is no protected-block prohibition — see §5.4 — so this row currently has fewer members than at most airlines.* |
| Soft impact (fatigue perception, earnings distribution) | **A reported KPI, never a constraint** | How premium-pay drafts are distributed across the seniority list |

Soft impacts are never converted into invented dollar weights buried in the objective. The moment you
price morale at "$X per draft", every result becomes an argument about X instead of about the
operation. Report it as a KPI; let humans weigh it.

**Note the direction of the fairness KPI here.** Because drafting is premium-paid and senior-first,
concentration of drafts is *not* a burden falling unevenly — it is premium income accruing to senior
crew, which is the agreement working as intended. The KPI is reported so the distribution is visible,
not because an even distribution is the goal. Getting this backwards in a report shared with ALPA would
be worse than omitting the metric.

### 6. Common Random Numbers (CRN)

All candidate policies are evaluated against the **same** pre-generated set of scenarios. This turns
policy comparison into a *paired* comparison and collapses the variance of the difference.

**Why this is not optional.** Per-scenario cost has a standard deviation on the order of its own mean —
a bad January costs several times an average one. Comparing two policies on two *different* random
samples would need tens of thousands of runs to resolve a 5% difference. Comparing them on the *same*
scenarios needs hundreds. Concretely, from the §8 reference run at N=100 scenarios:

```
Paired CRN difference (R6 − R10):  −11,390 ± 3,207 (95% CI),  t = −7.0
```

An unpaired comparison at the same sample size would have been statistically inconclusive.

---

## 1.4 Out of scope

Each exclusion below states the **direction of the resulting bias**, so nobody mistakes a modelling
limit for a modelling result.

| Excluded | Why | Bias it introduces |
|---|---|---|
| **Real-time / day-of decision support** | This is a planning tool that runs offline against synthetic months. A live "what-if" mode seeded from current crew state is a possible future track. | None — different product. |
| **Voluntary recovery layer** (open-time award, voluntary pickup at premium) | Not modelled separately. All uncovered demand goes straight to drafting. ⚠️ At Air Transat the boundary between the two is narrower than v2 assumed — see below. | Direction now unclear rather than a clean upper bound. |
| **Full legality engine** | The Crew State Engine uses a **legality surrogate** (§5.4): a small, conservatively-biased rule set, not CARs Part VII plus the full ALPA agreement. | Surrogate-legal ⇒ almost always truly legal. Some genuinely legal assignments are rejected, so recovery capability is understated. |
| **Aircraft and passenger recovery optimisation** | Aircraft and passengers appear only as cost terms (delay, cancellation, APPR compensation), never as recovery decisions. | Understates the airline's real recovery options; overstates crew-side cost. |
| **Network delay propagation** | Delays extend duty and cost money but do not propagate through aircraft rotations. | **Understates tail severity**, therefore understates CVaR. Partially compensated by the severity regime — see §5.2. |

### The voluntary layer, revisited

v2 argued the exclusion was harmless because "the bias applies equally to all candidate policies." That
reasoning does not hold, but the reason has changed since v2 was written.

Because drafting at Air Transat is **premium-paid and allocated by seniority**, it already occupies much
of the space a separate "voluntary open-time pickup at premium" layer would occupy elsewhere. The two
mechanisms are closer than v2 assumed, so "excluding voluntary pickup overstates drafting" is no longer
a clean claim — the model may already be representing the substance of it under a different name.

**No placeholder parameter is used for this.** An earlier draft of this specification introduced a
`voluntary_absorption_rate` dial to bound the effect. It has been removed: a knob invented to cover an
unmodelled mechanism reads as a claim that the mechanism has been characterised, when it has not.

The limitation is therefore stated plainly and left stated: **all uncovered demand in this model goes to
drafting, and if Air Transat has a voluntary layer that is not represented, simulated drafting frequency
is correspondingly overstated.** If that layer exists and matters, it should be described by Crew
Planning and modelled as it actually works — not approximated by a scalar.

---

## 1.5 Scope statement for the MVP

| Dimension | MVP value | Rationale |
|---|---|---|
| Base | YUL (Montréal–Trudeau) | Principal crew base. |
| Fleet | A321neo LR | The narrow-body transatlantic type. No type-rating overlap with the A330 fleet, so qualification is hard-binding (§4.5.1). |
| Position | First Officer | |
| Crew group | Pilots (ALPA agreement) | Small enough to reason about by hand; highest cost per head. Cabin crew (CUPE 4041/4047/4078) follow in Phase 2 with their own `costs_cabin.yaml`. |
| Season | Reported **per bid period**, not annually | Air Transat's summer Atlantic and winter sun programmes are different problems (§4.5.2). |
| Roster size | `configs/base.yaml → population.roster_size` (placeholder 120) | Reserve count is meaningless without the population it is carved out of. See below. |
| Flying covered | `configs/base.yaml → demand.pairings_per_bid_period` (placeholder 480) | And roster size is meaningless without the flying that population covers. |

### What `roster_size` still needs from Crew Planning

Both values above are now configuration, so they can be changed without touching code and are swept by
gate V9 (§9.2). What is still needed is the *right* values, and the request is more specific than "how
many pilots":

**Ask for a published artefact, not a headcount.** For the bid period in `scope.bid_period`, for
YUL / A321neo LR / First Officer: *how many lines were published, how many of those were reserve lines,
and what total credit or block hours did they cover?* Also: who on the seniority list for that scope was
**not** awarded a line, and why?

That one request settles four things at once:

| It pins down | Why it would otherwise be ambiguous |
|---|---|
| **Total, not line holders only** | Reserves are carved *out* of `roster_size` (§5.10). A line-holder-only figure would silently regrow the workforce as `R` increases — the exact defect that headcount conservation exists to fix. |
| **Which bid period** | Air Transat's summer Atlantic and winter sun programmes are different problems (§4.5.2). This is one number per bid period, never an annual average. |
| **The flying it covers** | `roster_size` on its own does not pin the crew-to-flying ratio, so every result would scale with an unstated assumption. |
| **Availability edges** | The "not awarded a line" note catches crew who are on the list but unavailable: in fleet transition, in initial training, on long-term absence, or management and instructor pilots flying partial schedules. Counting them inflates the draft candidate pool. |

**Bonus:** the reserve-line count in that same answer is Air Transat's **historical `R`** for the period —
the natural baseline against which every recommendation should be compared.

*Population membership rules are deliberately not config knobs.* From slice 1b the population comes from
real D1/D2 rosters, so those belong in the data loader as row filters, not as numbers to dial.
