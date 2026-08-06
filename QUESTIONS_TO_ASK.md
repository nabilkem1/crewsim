# Questions to Ask — Air Transat IOC & Stakeholders

**Purpose:** every value this model still needs, and every assumption it still makes, turned into a
question someone can actually answer.
**Version:** 1.0 · **Date:** 2026-08-05 · Companion to `spec_sections/` v3.1

---

## How to use this document

Each question carries four things:

| Field | Meaning |
|---|---|
| **Ask** | The question, phrased so it can be forwarded as-is |
| **Why** | What the model does with the answer |
| **If wrong** | The *direction* the result moves if we guess badly — so you can judge whether it is worth chasing |
| **Lands in** | Exactly where the answer goes: a config key, a spec section, or a dataset |

**Two rules that make this work.**

1. **Ask for artefacts, not opinions, wherever one exists.** "How many pilots do we have?" invites an
   estimate. "Send me the published line list for January" produces a fact that answers four questions
   at once. Questions marked 📄 have an artefact you can request instead.
2. **A question with no answer is not a blocker — an unrecorded assumption is.** Where a value is
   unknown, we sweep it (gate V9, §9.2) and report whether the recommendation moves. What must never
   happen is a placeholder quietly hardening into a fact.

### Priority — what blocks what

| Priority | Section | Blocks |
|---|---|---|
| 🔴 **Now, before dates are committed** | §6.1 draft-event reconstruction spike | The whole Phase-1 schedule |
| 🔴 **Now** | §1 IOC behavioural questions | Whether the model's recovery sequence is right at all |
| 🟠 Before slice 1b **validation** | §2 Crew Planning — population & rosters | Headcount conservation, the Erlang-B gate |
| 🟠 Before slice 1c | §6 data availability | Eligibility and cascade validation gates |
| 🟡 Before slice 1e | §3 Finance · §4 Labour Relations · §5 Training | The cost backtest (V6) |
| 🟢 At recommendation time | §7 Executive | Nothing — but the report is incomplete without it |

> Nothing in §1 blocks *coding*. Slice 1a runs on synthetic data and needs none of this. But nothing in
> this document can be skipped before a number reaches a planner.

---

## 1. IOC / Duty Managers — how recovery actually works 🔴

**These are the questions only the IOC can answer.** Everything else on this list is a number someone
looks up; this section is about behaviour, and it decides whether the simulation is modelling the right
sequence of events. Best done as a **60–90 minute session with a duty manager, walking through one real
disruption day** — which doubles as preparation for validation gate **V5** (§9.2).

### 1.1 The recovery sequence

> **Ask:** When a sick call comes in for a trip departing later today, what do you actually do, in
> order? Name every instrument you reach for, including ones we may not have thought of.
>
> **Why:** The model's pipeline is: *eligible reserve → (optional cross-base deadhead) → draft by tier,
> senior first → cancel at the deadline* (§5.3). If there is a step in between, or a step before, the
> model is wrong in a way no amount of calibration fixes.
>
> **If wrong:** Every result. This is the single most important question in this document.
>
> **Lands in:** §5.3 recovery pipeline

### 1.2 Is there a step before drafting? 📄

> **Ask:** Before anyone is drafted, is the open flying offered to crew in some voluntary way — an
> open-time award, a premium pickup, a "who wants it" call? **Or is what we call drafting already that
> step?** If a separate voluntary stage does exist, how often does it cover the problem, and does that
> change by season or by how far ahead the problem appears?
>
> *Context for the answer:* we understand drafting to be premium-paid and offered senior-first, which
> means it may already be the mechanism a voluntary layer would describe elsewhere. Distinguishing "we
> have two stages" from "you are describing our one stage under a different name" is the point of the
> question.
>
> **Why:** §1.4 records that no voluntary layer is modelled and that all uncovered demand goes straight
> to drafting. We deliberately removed the placeholder dial that used to bound this. If a voluntary
> step exists, it needs modelling as it actually works.
>
> **If wrong:** Simulated drafting frequency is **overstated**, and the marginal value of a reserve is
> **overstated** — pushing the recommended reserve level too high.
>
> **Lands in:** §1.4, and possibly a new step in §5.3

### 1.3 Does the tier order match what you actually do?

> **Ask:** When no one is on a day off, what do you actually do next — call someone off a trip, someone
> in training, someone on vacation? Is that order fixed, or does it depend on the day?
>
> **Why:** The model exhausts tier 1 (no duty) before tier 2 (holds a pairing), then training, then
> vacation, then simulator (§5.6). That ordering came from the original specification and has been
> reaffirmed in principle, but it has never been checked against practice — and in the current reference
> run **100% of drafts land in tier 1**, so the tier loop is not observable in the output at all. It
> will start mattering the moment real rosters make day-off crew scarce.
>
> **If wrong:** Which crew get drafted in every scenario, and the cost mix — tiers 3 to 5 are five to
> eight times the cost of a tier-1 draft.
>
> **Lands in:** §5.6 tier table and selection algorithm

### 1.4 Which reserve gets called first?

> **Ask:** When several reserves could all legally take the same trip, what decides which one gets the
> call? Our default is *whoever is closest to running out of on-call time* — "use them or lose them" —
> with seniority breaking ties. Is that right, or is there an operational consideration we have missed
> (proximity to the airport, who is already at the hotel, who has flown the route recently)?
>
> **Note this is a different question from the drafting order.** Drafting is senior-first and mandated —
> that is settled and not in question here. This is only about choosing between reserves who are all
> already on call and all legal.
>
> **Why:** `reserve_selection` is one of only two remaining Stage-2 policy levers (§5.9). If the real
> rule differs, the lever should be set to it and the alternatives evaluated against it.
>
> **If wrong:** Reserve productivity, and therefore how many reserves you need.
>
> **Lands in:** `configs/policies/*.yaml → reserve_selection`, §5.5

### 1.5 Reserves who cannot be used

> **Ask:** How often is a reserve called and unreachable, unable to report in time, or otherwise not
> usable? Is that recorded anywhere?
>
> **Why:** The model treats a legal reserve as a guaranteed resource. Dataset D5 has a `no-show`
> outcome field, which suggests it happens.
>
> **If wrong:** Reserve productivity is **overstated**, so the recommended level is too low.
>
> **Lands in:** §5.5, and a Phase-2 realism item

### 1.6 How long do you hold an open trip before cancelling?

> **Ask:** How close to departure will you keep working an uncovered trip before you cancel it? Does
> that vary by route — long-haul versus sun, high load factor versus low?
>
> **Why:** Event E8 `UNCOVERED_DEADLINE` (§5.0.3) currently uses report time as the deadline. If you
> hold longer in practice, a reserve who frees up late can still rescue the trip — which the model
> cannot currently represent.
>
> **If wrong:** Cancellations are **overstated**, so reserves look more valuable than they are.
>
> **Lands in:** §5.0.4 E8, `OpenTimeItem.deadline`

### 1.7 Cross-base repositioning

> **Ask:** How often do you fly a crew member from another base to cover a trip? What has to be true
> for that to work — how much notice, is a seat always available, who authorises it?
>
> **Why:** `allow_cross_base_reserve` is the other remaining Stage-2 lever. The model currently costs a
> deadhead seat and a hotel but assumes the seat exists.
>
> **If wrong:** Recovery capability is **overstated** if seats are scarce in the peak.
>
> **Lands in:** `configs/policies/*.yaml → allow_cross_base_reserve`, §5.3

### 1.8 When do you find out?

> **Ask:** When a draft breaks something later in the month, when do you actually see it — immediately,
> or when the next day's plan is built?
>
> **Why:** The model surfaces cascade disruptions 24 hours before they bite (§5.3, `_delayed_pipeline`).
> That number is a guess.
>
> **If wrong:** Recovery time for cascades, and therefore cascade cost.
>
> **Lands in:** §5.7, cascade visibility lag

### 1.9 Multi-position shortfalls

> **Ask:** If a trip is missing both a captain and a first officer, is that one problem or two? And how
> do delays turn into crew problems — at what point does a late inbound become a legality issue you
> have to solve?
>
> **Why:** The MVP models one position in isolation (§1.5) and treats delays as cost plus duty
> extension only, with no network propagation (§1.4).
>
> **If wrong:** Tail severity is **understated**, so CVaR — and the risk-averse reserve level — is too
> low.
>
> **Lands in:** §1.4 scope, Phase-2 multi-position work

### 1.10 A day to replay 📄

> **Ask:** Pick a disruption week you remember — an ice storm, a March-break weekend, a peak-season
> meltdown. Can we get the crew-tracking log for it?
>
> **Why:** This is validation gate **V5**: replay it, then walk you through the simulated event log
> hour by hour and ask *"would you have done this?"* A model that reaches the right total by making
> decisions no duty manager would make is not validated.
>
> **Lands in:** §9.2 V5

---

## 2. Crew Planning — population & rosters 🟠

### 2.1 The published line count 📄 — **the single highest-value request in this document**

> **Ask:** For the bid period we are modelling, for **YUL / A321neo LR / First Officer**:
> - how many lines were published?
> - how many of those were **reserve** lines?
> - what total credit or block hours did they cover?
> - who on the seniority list for that scope was **not** awarded a line, and why?
>
> **Why:** One artefact settles four separate ambiguities:
>
> | Settles | Otherwise ambiguous because |
> |---|---|
> | Total vs line-holders-only | Reserves are carved *out* of `roster_size` (§5.10). A line-holder-only figure would silently regrow the workforce as R rises. |
> | Which bid period | Summer Atlantic and winter sun are different problems (§4.5.2) — never an annual average. |
> | The flying covered | `roster_size` alone does not pin the crew-to-flying ratio; every result would scale with an unstated assumption. |
> | Availability edges | "Not awarded a line" catches crew in fleet transition, in initial training, on long-term absence, or management/instructor pilots on partial schedules. |
>
> **Bonus:** the reserve-line count *is* Air Transat's historical `R` for that period — the natural
> baseline for every recommendation the tool produces.
>
> **If wrong:** Too high → too many draft candidates → fewer cancellations → reserves look less
> valuable → **recommended R too low.** Too low, the reverse.
>
> **Lands in:** `configs/base.yaml → population.roster_size` and `demand.pairings_per_bid_period`

### 2.2 Reserve line structure

> **Ask:** What does a reserve line look like — how many days on call in a row, how many off, and how is
> short-call split from long-call across it?
>
> **Why:** The model currently gives reserves a flat on-call block with no rotation and no SC/LC split,
> which is why realised eligibility comes out at 0.54–0.96 against a ≈30% target (§8.3). This is the
> main reason gate V3 fails today.
>
> **If wrong:** Eligibility cannot reproduce its validation target, and V3 stays failed.
>
> **Lands in:** §4.4.1, §5.5, dataset D2

### 2.3 Which bid period, and how many

> **Ask:** Which bid periods should we model first, and how different are they from each other?
>
> **Why:** The deliverable is a reserve vector **per bid period**, not one annual number (§4.5.2).
>
> **Lands in:** `configs/base.yaml → scope.bid_period`, `configs/seasons.yaml`

### 2.4 Phase-2 direction

> **Ask:** Is the reserve question sharper for pilots or for cabin crew?
>
> **Why:** Cabin crew are a much larger population with more statistical signal, but a multi-position
> complement adds modelling work, and CUPE coefficients differ per local.
>
> **Lands in:** §3 Phase 2 scope

---

## 3. Finance — cost coefficients 🟡

**Every cost in the model is currently a placeholder.** They are the right order of magnitude so that
worked examples are checkable; none is an Air Transat figure. Full list in §4.4.2.

| # | Ask | Placeholder | Note |
|---|---|---|---|
| 3.1 | Daily reserve guarantee, short-call and long-call | $250 / $180 per day | The entire fixed cost of the Stage-1 decision |
| 3.2 | Marginal pay when a reserve is actually used | $150 | Delta only — the guarantee is already sunk |
| 3.3 | Draft premium paid on every draft | $500 | |
| 3.4 | Tier surcharges: pairing / training / **vacation** / simulator | 300 / 900 / **2,500** / 4,000 | See 3.5 |
| 3.5 | **Vacation surcharge specifically** | 2,500 | 🔴 **Newly high priority.** With no protected-block rule, tier 4 is *reachable*; and senior-first drafting reaches the crew holding the best vacation. This moved from corner case to live cost driver. |
| 3.6 | Internal cost of cancelling one flight | $25,000 | Aircraft, rebooking, goodwill |
| 3.7 | Cost per minute of delay on a covered flight | $55/min | |
| 3.8 | Deadhead seat, hotel night | $400 / $220 | Or the per-diem tables |
| 3.9 | APPR compensation tiers currently applied | $400 / $700 / $1,000 CAD | Confirm the schedule and large-carrier status with Legal |

> **Why 3.6 and 3.9 matter most:** a single cancelled wide-body rotation with a full cabin can cost more
> than the entire reserve establishment for the month (§7.3). Cancellation cost is the mechanism that
> makes reserves worth buying at all — if it is wrong, everything is wrong.

---

## 4. Labour Relations 🟡

Three v2 assumptions have already been corrected by the business; these are the remaining ones.

> **4.1 — Clause references, for the record.** Which clauses of the ALPA agreement establish the
> senior-first drafting order and the impact-tier ordering? *Why:* the model encodes a reading of the
> agreement; that reading needs a citation (§9.4).
>
> **4.2 — Anything that stops a draft.** Beyond the legality rules and schedule feasibility, is there
> *any* circumstance in which a crew member cannot be drafted? *Why:* we have removed the protected-block
> rule and the monthly cap on your instruction. This question is the safety net against a third such
> assumption (§5.4).
>
> **4.3 — Reporting the earnings distribution.** We report per-crew draft counts and concentration.
> Because drafting is premium-paid, these describe *who earned the premium*. Is that framing correct, and
> is it appropriate to circulate to ALPA and CUPE? *Why:* v2 framed the same metric as a burden
> distribution. Getting the direction wrong in a shared report would be worse than omitting it (§1.3.5,
> §6.2).

---

## 5. Training 🟡

> **5.1** — What does it cost to reschedule a ground-training session? (`train_reschedule_cost`,
> placeholder $1,200.)
>
> **5.2** — What does a lost simulator slot cost, and how far ahead are slots booked?
>
> **5.3** — If a crew member misses a training event because they were drafted, what triggers a full
> requalification, and what does that cost? *Why:* the tier-3 and tier-5 costs are the least-grounded
> coefficients in the model, and both tiers are now reachable.

---

## 6. Data & IT 🔴🟠

### 6.1 The draft-reconstruction spike 🔴 — **do this in week 1**

> **Ask:** Does the crew tracking system record anywhere that an assignment was a **draft**? If not: can
> we get one month of schedule-change records (D6) and one month of the pay register (D7), and can an
> IOC duty manager label the actual drafts in one known week so we can measure our reconstruction
> against ground truth?
>
> **Why:** Almost no airline codes drafts explicitly. They have to be inferred by joining schedule
> changes against premium pay codes (§6.3-1). §6.2 sets the gate at **≥80% recall**. Below that, *both*
> the tier distribution and the cascade validation target degrade to "indicative" — and those two are the
> entire credibility argument for the system.
>
> **If wrong:** Gates V3 and V4 become advisory, and no output can carry a validation claim.
>
> **This is the critical path.** Slice 1a needs no data and runs in parallel, so the spike costs nothing
> on the schedule — but Phase-1 dates should not be committed until it comes back.

### 6.2 Dataset availability 📄

For each of D1–D12 (§6.1): does it exist, how far back, at what grain, and who owns it? The ones with
non-obvious answers:

| Dataset | The specific worry |
|---|---|
| **D2** Published rosters | Does it carry the **reserve call type (SC/LC)**? Without it, rule L8 cannot be implemented and eligibility cannot reproduce ≈30%. |
| **D4** Sick-call log | **36 months minimum** — three seasonal cycles. Are ≥95% of absences linkable to a roster block? |
| **D5** Reserve utilisation | Is the `no-show` outcome actually populated? |
| **D6** Schedule changes | Is the `initiator` field (system / planner / IOC) populated on older records? |
| **D9** Weather / IROPS labels | Does it exist, or must it be derived from D8 delay-code density? |

### 6.3 Fitting and holdout windows

> **Ask:** What date range can we use? We need two non-overlapping windows: one to fit on, one held back
> to validate against.
>
> **Why:** Fitting inputs until the outputs hit 30% and 20% proves nothing. Gates V3 and V4 must be
> measured on data the fit never saw (§6.4).

### 6.4 Privacy sign-off

> **Ask:** Who signs off pseudonymisation under Law 25, and is a union governance briefing expected
> before results circulate? (§6.2)

---

## 7. Executive / Finance — the risk dial 🟢

> **Ask:** How much extra cost in an average month is Air Transat willing to pay to avoid a bad one?
>
> **Why:** That is λ in the objective (§7.4). It is **not** a fitted parameter — it is a management
> input. In the current reference run the risk-neutral answer is R=6 and the risk-averse answer is R=10:
> four extra reserves cost about $11,400 more in an average month and save about $31,000 in a bad one.
>
> **How to ask it:** do not ask for a number. Present the λ curve with its price tag and let the choice
> be made against real figures. The deliverable is the curve, not a point.

---

## Appendix — recording the answers

Answers go in **one** of three places. Nothing lives in prose only.

| Kind of answer | Goes to |
|---|---|
| A value we do not know yet | `configs/base.yaml` or `configs/costs_pilots.yaml` — replacing the `[CONFIRM: …]` marker |
| A fact about how the operation works | The relevant `spec_sections/` file, plus a row in §10 decision register |
| A dataset fact | §6.1, and the Phase-0 data-quality report |

Two habits worth keeping:

- **Record who said it and when.** Three v2 assumptions turned out wrong; the correction was cheap
  because the assumption was written down and attributable.
- **When an answer closes a question, strike the row rather than deleting it** (see §10.5). The
  historical record of what was assumed, and when it was corrected, is worth more than a tidy list.

**Reminder for every report:** §9.3 requires any outstanding `[CONFIRM: …]` that a result depends on to
be listed in that report. A fully validated pipeline running on placeholder cost coefficients produces a
beautifully reproducible wrong answer.
