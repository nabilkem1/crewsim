# Backlog coverage audit — spec §1–§10 against `stories.yaml`

**Date:** 2026-08-06 · **Scope:** every functional requirement in `spec_sections/*.md` traced to a story.
**Baseline:** 61 stories, `stories.yaml` and `mvp/*.md` at 1:1 parity (verified by id diff).

---

## Verdict

Coverage is good — the legality surrogate (L0–L8), the nine V&V gates, the Phase-0 calibration
pipeline, cascades, headcount conservation and the reproducibility chain are all fully storied, most
with derived acceptance values. The nine gaps below are concentrated in one place: **the parts of the
recovery pipeline and the scenario pipeline that sit between components that *are* storied.**

Three of them are load-bearing:

- **E2 `DELAY` has no handler story** — so `S0-07b` fits a delay model nothing consumes.
- **Neither θ parameter is implemented** — `reserve_selection` and `allow_cross_base_reserve` are the
  only two policy knobs the system has left after v3.1, they ship in every `configs/policies/*.yaml`,
  and `S1e-04`'s grid varies both. No story builds either.
- **Nothing wires the parameter store into the scenario generator** — Layer 3 of the six-layer
  architecture has no story. `S0-08b` emits params; `S1a-05` proves seeding is pure; the connection
  between them is unstoried, along with the Parquet freeze and the `content_hash` cache invalidation.

Plus one **defect already encoded as an acceptance criterion** — see §0, which is the most urgent item
here.

---

## 0. `S1a-04` enshrines the 21-day horizon bug as a passing test

`stories.yaml:277` and `mvp/01_slice_1a_foundation.md:67`:

> **Expect** measured-window total **31,500** = $250 × 6 reserves × **21 measured days**

`configs/base.yaml` sets `measurement_days: 28`. `S1a-02`, in the same slice, expects *"horizon 42
days"*. 21 days is the value the **reference implementation** uses, because
`crewsim_skeleton.py:600,623,638` hard-code `horizon_days=28, warmup_days=7` and never read
`cfg["horizon"]` — documented in `SPEC_REVIEW_v3.md` §1.1.

So the first slice's acceptance criterion is the bug. Implement `S1a-04`, run the manual check, read
31,500, tick it — and the 21-day window becomes load-bearing before slice 1b starts.

**This has been changed** to a formula over config rather than a literal, per §4.4's no-magic-numbers
rule. It is the only *edit* to an existing criterion in this pass; everything else is additive.

**One genuine ambiguity is now flagged on the story rather than silently resolved.** The skeleton
filters the ledger on the lower bound only (`t >= warmup_end`, `crewsim_skeleton.py:338`). With a
42-day horizon and lower-bound-only filtering the total is 35 days = $52,500, not 28 days = $42,000.
Whether cool-down staffing is excluded depends on an upper-bound filter that §5.0.5 implies but no
story specifies — and reserve staffing carries `root_event_uid = None` (§2.3/C2), so it has no causal
chain to attribute back into the window. **Crew Planning / the spec owner should settle this**; it is
worth $10,500 per policy at R = 6.

---

## 1. New stories added

| Id | Slice | Spec | What was missing |
|---|---|---|---|
| `S1a-08b` | 1a | §5.6, §5.8, §4.4.2 | `status_tier` classification and tiered draft-cost booking |
| `S1b-08` | 1b | §2.5.0, §2.5.1, §5.2 | Scenario generator reads the parameter store; freeze + hash invalidation |
| `S1b-09` | 1b | §5.0.3, §5.0.4, §7.3 | Event **E2 `DELAY`** handler |
| `S1c-06` | 1c | §5.5, §3 | Reserve-selection rules (θ parameter 1 of 2) |
| `S1c-07` | 1c | §5.3, §5.8, §7.3 | Cross-base dispatch + positioning costs (θ parameter 2 of 2) |
| `S1e-08` | 1e | §4.5.2, §2.2 | Per-bid-period seasonal deliverable vector |

### Why each lands where it does

**`S1b-09` — E2 `DELAY`.** Epic E1b is titled *"Real rosters & **the full event set**"* and stories
E6, E7, E8. E2 is the missing member of the set it claims to complete. §5.0.4 requires it to extend the
affected duty block, update `L_c`, re-check downstream legality, turn newly-illegal blocks into open
items, and book `q^dly`. It is also the **only** consumer of `shift_or_extend`, one of the three
audited mutations in §5.4, and the only source of the `DELAY` cost category in §5.8 and the `q^dly(ω)`
term in §7.3. Without it, `S0-07b`'s entire delay fit is dead weight and duty overruns never happen —
which understates the summer Atlantic season specifically (§4.5.2).

**`S1b-08` — the scenario generator.** §2.5.1 step 6 ("The Freeze") and §2.5.0's "Strict Cache
Invalidation" describe a `scenario_set.parquet` keyed to the params `content_hash`. `S1a-05` proves
scenario generation is a pure function of the seed; `S0-08b` proves the calibrator emits a hashed
parameter store. Nothing connects them. Placed in 1b rather than 1a because slice 1a is explicitly
"needs no data" and this consumes calibration output.

> This story carries a **spec contradiction that must be resolved before it is built**:
> `2_HighLevel_Architecture.md:799` says the chain starts each scenario in `NORMAL`;
> `:610` and `:469` say Day 1 draws from π₀. See `SPEC_REVIEW_v3.md` §1.3.

**`S1c-06` and `S1c-07` — the two θ parameters.** Both need the eligibility pool from `S1c-01`.
`S1c-06` also unblocks `S1e-04`: the grid is specified as `R × reserve-selection × cross-base`, and
neither of the two varying dimensions is currently implemented by anything.

**`S1a-08b` — tier classification.** `S1a-08` covers *ordering* (tier before seniority, senior first)
but never the tier *classification* or its cost. §5.6 calls `status_tier` *"fully deterministic and
auditable"*; §5.8 names `DRAFT_BASE`, `DRAFT_TIER{k}` and `TRAIN_RESCHEDULE` as separate ledger
categories. Since v3.1 made tiers 4 and 5 reachable, `tier_cost[4]` is a live cost driver (§4.4.2)
rather than a corner case — this is now the difference between a $500 draft and a $3,000 one.

**`S1e-08` — the seasonal deliverable.** §4.5.2 closes with *"The final output of the tool is never
'You need 10 reserves.' It must always be a seasonal list."* Calibration is correctly per-season
(`S0-06`, `S0-07`, `S0-07b`), but nothing reads `configs/seasons.yaml` and no story produces the
per-bid-period vector that is the actual deliverable.

---

## 2. Added as acceptance bullets on existing stories

Too small to be stories in their own right (the README's 60-second rule cuts both ways), but each is an
explicit spec requirement with no home:

| Added to | Requirement | Spec |
|---|---|---|
| `S1b-05` | `RESERVE_UTILIZATION` / `q^res` marginal booking on assignment | §5.8, §7.3 term 1 |
| `S1d-01` | `REDUCED` mode `Bernoulli(p_cascade)` + the C4 warning banner | §2.3/C4, §5.7 |
| `S1e-01` | Warm-up length validated by **Welch's procedure**, not asserted at 7 | §5.0.5 |
| `S1e-01` | The `C₁ + E[Q] + λ·CVaR` objective as the ranking function, λ from config | §7.4 |
| `S1e-04` | Service-level chance constraint filters infeasible policies from the candidate set | §7.5 |

---

## 3. Corrected: the policy grid size

`stories.yaml:710` and `mvp/05_slice_1e_reporting.md:69,75` say **24 combinations**. §3 states both
*"24 different strategy combinations"* (`3_HighLevel:90`) and *"(6 reserve levels) × (5 callout rules)
× (2 cross-base rules) = **60** total strategies"* (`:109`, repeated at `:111` and `:129`). The
backlog inherited the wrong one.

Corrected to 60 — and note the coupling: **60 was unreachable anyway**, because no story implemented
the 5 callout rules. Fixing the count and adding `S1c-06` are the same finding.

---

## 4. Not a story gap — a data-contract gap. Needs escalation.

**APPR passenger compensation has no input data.**

`S1b-06` does book it (*"Cancellation and APPR compensation book at the deadline"*), so it is not
unstoried. But §4.4.3 defines the schedule as **$400 / $700 / $1,000 per passenger** by delay band, and
**nothing in D1–D12 carries a passenger count or a load factor.** D8 (OTP / flight movement) carries
scheduled vs actual times and cancellation flags; it does not carry seats sold.

§7.3 states this term dominates the objective — its own worked example is $126,000 of compensation
against a $25,000 base cancellation cost, *"often larger than every crew cost combined"* — and §7.3
concludes *"modelling APPR compensation properly is therefore not optional detail."*

**This belongs in `QUESTIONS_TO_ASK.md`, not in a story.** The question for Commercial / Revenue
Management is: *for the scope and bid period in `configs/base.yaml`, what load factor (or passenger
count per departure) should be assumed, and is it available per flight in an existing extract or does
D8 need extending?* Until it is answered, the largest term in the objective rests on an unstated
assumption — exactly the failure mode §3.1 rule 5 warns about.

---

## 5. Noted, deliberately not acted on

- **`product_1/` was not touched.** `README.md:106-109` states Phase-2 stories are coarse on purpose
  and *"refine a `product_1` epic only when its predecessor slice has passed its gate."* Adding detail
  there would break a stated rule of the backlog.
- **§5.2's roster-variability note** — *"Phase 2 should sample rosters across bid periods to
  reintroduce it"* — has no placeholder story in `product_1/`. Recorded here rather than added, for the
  reason above.
- **`S1a-01` does not exist.** Slice 1a numbering starts at `S1a-02`. Either it was folded into
  `S0-00` / `S0-00b` during a renumber, or it is a hole. Worth a one-line answer so the gap is not
  mistaken for a lost story.
- **Pseudonymisation (Law 25, §6.2)** is covered as an acceptance bullet on the Phase-0 loader
  (`mvp/00_phase0_data_foundation.md:172`) rather than as its own story. That is the right size —
  flagged only so it is not thought missing.

---

## 6. Corroboration for `SPEC_REVIEW_v3.md`

The backlog schedules V1, V7 and V8 as `todo` (`S1a-10`, `S1a-11`, `S1a-06`) with no implementation.
`8_SimPy_DES_Skeleton:124-144` reports the corresponding four checks as **✓ passing today**.

The backlog is right and the spec is wrong: `crewsim_skeleton.py` contains no assertion, no
verification function and no violation scan, and `tests/gates/` is an empty package. **The backlog is
the more honest artefact here** — which is a point in favour of its two-gate discipline.

---

## Coverage summary after this pass

| Area | Before | After |
|---|---|---|
| Events E1–E9 | 8 of 9 (E2 missing) | 9 of 9 |
| Legality L0–L8 | 9 of 9 | 9 of 9 |
| θ parameters | 0 of 2 | 2 of 2 |
| Ledger categories (§5.8) † | 4 of 12 | **12 of 12 storied · 11 of 12 computable** |
| Architecture layers (§2.1) | 5 of 6 (Layer 3 partial) | 6 of 6 |
| V&V gates V1–V9 | 9 of 9 | 9 of 9 |
| Architectural commitments C1–C4 | 3 of 4 (C4 partial) | 4 of 4 |
| **Stories** | **61** | **67** |

† Denominator is the twelve **named categories** in §5.8's eight rows: `RESERVE_STAFFING`,
`RESERVE_UTILIZATION`, `DRAFT_BASE`, `DRAFT_TIER{k}`, `TRAIN_RESCHEDULE`, `DEADHEAD`, `HOTEL`,
`TRANSPORT`, `DELAY`, `CANCELLATION`, `PAX_COMPENSATION`, `TERMINAL_PENALTY`.

**Two of those twelve are storied but not yet computable, and the table above should not be read as
closing them:**

- **`PAX_COMPENSATION`** — no passenger count or load factor exists in D1–D12. See §4. This is the
  term §7.3 says dominates the objective, so treat this row as open, not closed.
- **`TRANSPORT`** — §5.8 names it; §4.4.2 prices only `deadhead_cost` and `hotel_cost`. No coefficient
  exists in the registry. Flagged on `S1c-07` with an instruction **not** to invent one: either
  Finance supplies it from D10, or §5.8 drops the category.

---

## Open items this pass does **not** close, in priority order

| # | Item | Owner | Why it matters |
|---|---|---|---|
| 1 | **The measurement-window question** (§0) — does the measured window exclude cool-down staffing? | Spec owner | Worth $10,500 per policy at R = 6, and it gates the very first slice |
| 2 | **The Markov Day-1 contradiction** — `NORMAL` vs π₀ | Spec owner | Blocks `S1b-08`; changes every generated scenario |
| 3 | **APPR passenger count** (§4) | Commercial / Revenue Mgmt | The largest term in the objective has no input data |
| 4 | **`TRANSPORT` coefficient** | Finance | Named category, unpriced |
| 5 | **`S1a-01` does not exist** | Backlog owner | One line to confirm it was a renumber, not a lost story |

**A note on `S1b-08`'s status.** It carries a blocking spec contradiction but is left `todo`, not
`blocked`. `stories.yaml` reserves `blocked` for waiting on an **external** answer — `S3-06` is
blocked on the IOC. Item 2 above is a one-line edit to §5.2 that the team controls, so it is a note on
the story rather than a status. If it is still unresolved when 1b starts, flip it.
