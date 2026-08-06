# 5. Detailed Implementation Description

**Version:** 3.0 (Air Transat instantiation, engineering edition) · **Date:** 2026-08-05

---
## What this section is

The implementation contract for the simulation core. Every subsection follows the same shape: what the
component is, the formal definition, a `→ code` restatement, and a worked example with real arithmetic.

All numeric constants referenced here live in §4.4. All costs are CAD and all are
`[CONFIRM: Finance + Crew Planning]` placeholders.

---

## 5.0 Formal DES specification — the five-component framework

Any discrete-event simulation is fully specified by five things: the **clock**, the **state**, the
**events**, the **state transitions**, and the **stopping condition**. This subsection pins all five
down. If you have written a queueing simulation before, this will feel familiar — with three
differences, called out as we go:

| | Textbook single-server queue | This system |
|---|---|---|
| State | one integer `N(t)` | a **vector** of calendars, pools, queues, counters |
| Event calendar | two event types, never more than one pending each | **heterogeneous and self-extending** — handlers schedule new future events |
| Stopping | steady state, run until converged | **terminating**, fixed calendar window |

### 5.0.1 Simulation clock

- **Type:** continuous time in **minutes** from horizon start (`t = 0`). Calendar utilities map
  sim-time ↔ local dates, because day-of-week and season drive arrival intensities and legality rules
  operate on *local* report times. Air Transat's YUL base is America/Montreal; a transatlantic pairing
  crosses into Europe/Paris or Europe/London. Store UTC, evaluate legality in local.
- **Advance mechanism:** **next-event time progression**. The clock jumps from one scheduled event to
  the next; nothing happens in between, so no time is simulated where no decision occurs.

  Why a full event calendar and not a simple recursion: a single-server FIFO queue can be simulated by
  the closed-form recursion `D_n = S_n + max(A_n, D_{n−1})` because every customer goes through the
  same fixed event pattern. Here, events are heterogeneous, they interact through shared state, and —
  crucially — a handler can insert new events into the *future* of the calendar. No recursion captures
  that.

- **Start condition:** the system does **not** start empty. At `t = 0` the state is a fully populated
  roster: crew calendars loaded from published rosters, reserve blocks laid out per the Stage-1 policy
  vector. A **7-day warm-up** is still applied, to wash out the artificial "no disruption backlog at
  `t = 0`" condition.

  Note the difference from a queueing model, where warm-up means "discard the first *k* customers".
  Here entities (crew) persist for the whole horizon, so deletion is **by time window**, not by entity
  index: ledger rows with `t < warmup_end` are *booked* but *excluded from KPIs*.

### 5.0.2 The Simulation "Save State" (What the computer remembers)

If you were to pause the simulation exactly halfway through the month like a video game, the computer needs to remember exactly what is happening at that exact millisecond. 

In math terms, this is called the "State of the system" ($S(t)$). But in plain English, it just means the computer is holding a massive snapshot containing exactly six things:

1. **Everyone's Calendar:** Where every single pilot is right now, and what they are scheduled to do tomorrow.
2. **The Backup Roster:** Exactly who is sitting at home on reserve standby.
3. **The "Broken Flight" Queue:** A list of every flight that currently doesn't have a pilot and is in danger of cancelling.
4. **The Legal Clocks:** A running stopwatch for every pilot tracking how many hours they've flown, so we know if they are legally too tired to take a flight.
5. **The Draft Counts:** A tally of how many times each pilot has been forced to work on their day off this month.
6. **The Invoice:** A running ledger of every single dollar the airline has spent fixing problems so far.

→ code:

```python
@dataclass
class SystemState:
    calendars: dict[CrewId, list[Block]]   # Cal_c(t) — sorted, non-overlapping for duty blocks
    reserve_lines: dict[CrewId, list[Block]]  # Res(t)  — RESERVE blocks, see note below
    open_time: list[OpenTimeItem]          # O(t)
    legality: dict[CrewId, LegalityCounters]  # L_c(t)
    draft_counts: dict[CrewId, int]        # n_c(t)
    ledger: CostLedger                     # G(t)
```

**Change from v2 — `Res` is not a scalar count.** v2 modelled the reserve pool as a count
`Res_{b,f,p}(t)`. That cannot represent short-call versus long-call notification windows (rule L8), a
reserve's days off, or the "use them or lose them" selection rule in §5.5 — all of which depend on
*which individual* is on call and *for how much longer*. Reserves are individual crew members holding
`RESERVE` blocks, exactly like line holders hold `PAIRING` blocks.

#### The six components, with Air Transat examples

**1. `Cal_c(t)` — crew calendars.** The scheduled block for every crew member at this minute.

| Crew ID | Current block | Start | End | Draft tier if drafted here |
|---|---|---|---|---|
| `C0041` | `PAIRING` YUL–CDG–YUL | Tue 08:00 | Wed 16:00 | 2 |
| `C0118` | `VACATION` | Mon | Fri | 4 |
| `C0007` | `DAY_OFF` | 00:00 | 23:59 | 1 |
| `R003`  | `RESERVE` (short-call) | Tue 06:00 | Tue 18:00 | — (reserve, not drafted) |

Note there is no "protected" column. **Air Transat has no protected-block concept in drafting:** every
block is draftable, and the tier is what makes some of them expensive. See §5.6.

**2. `Res(t)` — reserve lines.** Which individuals are on call, of which call type, until when.

| Crew ID | Base | Fleet | Position | Call type | On call until |
|---|---|---|---|---|---|
| `R001` | YUL | A321neo LR | FO | `SHORT_CALL` | Tue 18:00 |
| `R002` | YUL | A321neo LR | FO | `LONG_CALL` | Wed 06:00 |
| `R003` | YUL | A321neo LR | FO | `SHORT_CALL` | Tue 18:00 |

**3. `O(t)` — open-time queue.** Flying with no crew, which will cancel if not covered by its deadline.

| Item | Missing role | Flight | Cover by | Caused by |
|---|---|---|---|---|
| `O-991` | FO | TS156 YUL–CDG | Tue 16:00 | `SICK_CALL` |
| `O-992` | FO | TS738 YUL–PUJ | Wed 05:30 | `CASCADE_DRAFT` |

**4. `L_c(t)` — legality counters.** A conservatively-biased surrogate for CARs Part VII, kept as
running counters so no external rules API is called inside the simulation loop.

| Crew ID | Rolling duty (7d) | Rest since last duty | Type rating | Status |
|---|---|---|---|---|
| `C0041` | 41.5 h | 9 h | A321neo LR | `ILLEGAL_L2` (insufficient rest) |
| `C0007` | 0 h | 72 h | A321neo LR | `LEGAL` |
| `C0203` | 12 h | 48 h | **A330** | `ILLEGAL_L6` (wrong type rating) |

`C0203` is the §4.5.1 point made concrete: a rested, willing, available A330 pilot is *useless* for an
A321neo LR trip. Qualification is hard-binding, not a cost.

**5. `n_c(t)` — draft counts.** Per-crew drafts this month. **This is a KPI, not a constraint.** There
is no cap: a crew member may be drafted as often as legality and their schedule allow. Because drafting
is premium-paid, the tally is best read as *who earned the premium*, not *who bore the burden*.

| Crew ID | Seniority | Drafts this month | Premium earned | Draftable again? |
|---|---|---|---|---|
| `C0007` | 7 | 3 | $1,500 | Yes — if legal (L0–L8) |
| `C0041` | 41 | 1 | $500 | Yes — if legal |
| `C0118` | 118 | 0 | $0 | Yes — but senior crew are reached first |

**6. `G(t)` — cost ledger.** The itemised receipt. One row per costed event, never an aggregate.

| Sim time | Crew | Category | Amount (CAD) | Root event |
|---|---|---|---|---|
| Day 3 00:00 | `R001` | `RESERVE_STAFFING` | 250.00 | — |
| Day 3 14:05 | `R001` | `RESERVE_UTILIZATION` | 150.00 | `E-4417` |
| Day 3 16:30 | `C0041` | `DRAFT_TIER2` | 800.00 | `E-4417` |
| Day 5 09:00 | — | `CANCELLATION` | 25,000.00 | `E-4417` |

Read that ledger top to bottom: one sick call on day 3 (`E-4417`) consumed a reserve, forced a draft,
and — two days later, via a cascade — still ended in a cancellation. Total attributable cost $25,950,
not the $800 a naive draft-cost model would have recorded. **This is the entire argument for the
event-level ledger.**

#### Sufficiency property

Knowing `S(t)` and the remaining scenario event stream is sufficient to continue the simulation. No
history beyond `S(t)` is required. This is the defining property of a state, and it is what makes the
simulation checkpointable and replayable.

### 5.0.3 Events

Two classes: **exogenous** events replayed from the pre-generated CRN scenario stream, and
**endogenous** events created by the model's own decisions.

| # | Event | Class | Source |
|---|---|---|---|
| E1 | `SICK_CALL` | exogenous | scenario stream |
| E2 | `DELAY` | exogenous | scenario stream |
| E3 | `RESERVE_ASSIGNED` | endogenous | recovery pipeline |
| E4 | `DRAFT_EXECUTED` | endogenous | recovery pipeline |
| E5 | `CASCADE_DISRUPTION` | endogenous | Cascade Engine — **self-inserted future event** |
| E6 | `DUTY_END` | endogenous | schedule |
| E7 | `REST_END` | endogenous | schedule, follows E6 |
| E8 | `UNCOVERED_DEADLINE` | endogenous | `OpenTimeItem` timeout |
| E9 | `HORIZON_END` | control | clock reaches `T` |

**E5 is the structurally new element.** A textbook queue's calendar never grows: one arrival and one
service completion pending, forever. Here, the handler for E4 can schedule new disruption events at
*future* times. The calendar is **self-extending**, and that is precisely how multi-level cascades
arise without any exogenous "cascade probability" parameter.

### 5.0.4 State transitions

$$S(t^+) = f_{\text{event}}\big(S(t^-),\ \text{event},\ \pi_\theta\big)$$

| Event | Transition |
|---|---|
| E1 `SICK_CALL` | Remove the sick crew member's block(s) from `Cal_c` **and mark them unavailable for the absence duration**; `O += OpenTimeItem(s)`; invoke recovery pipeline |
| E2 `DELAY` | Extend the affected duty block; update `L_c`; re-check downstream legality — any block made illegal is removed and becomes a new open item; book delay cost |
| E3 `RESERVE_ASSIGNED` | **Split** the reserve's `RESERVE` block around the duty + mandatory rest; insert `DRAFTED_DUTY` and `REST`; `O −= o`; schedule E6; book utilisation cost |
| E4 `DRAFT_EXECUTED` | Consume the drafted crew's overlapping non-duty block; insert duty + rest; `n_c += 1`; `O −= o`; book tier-`k` cost; **run Cascade Engine on the `StateDelta`** → possibly schedule E5 events |
| E5 `CASCADE_DISRUPTION` | At the scheduled future time: remove the broken pairing or reserve block; `O +=` new item; invoke recovery pipeline (recursion → multi-level cascades) |
| E6 `DUTY_END` | Duty block closes; insert `REST` per L2; update `L_c` accumulators |
| E7 `REST_END` | Crew becomes assignable again; a reserve's remaining on-call window is restored |
| E8 `UNCOVERED_DEADLINE` | `O −= o`; flight cancelled; book cancellation + APPR compensation |
| E9 `HORIZON_END` | Charge terminal penalty `V(s_T)` on residual open items; stop |

**Two corrections from v2 are embedded above.**

*E1 now removes the sick crew member.* In v2's reference implementation, a sick call created open time
but never took anyone out of the available pool — the sick crew member remained draftable. Sick calls
must be sampled from crew who are on or about to report for duty, and must remove them.

*E3 splits rather than deletes.* A reserve who flies a trip on Tuesday is back on call Wednesday.
Deleting the whole `RESERVE` block retires them from the pool after one use; deleting nothing lets them
be booked into overlapping duties forever. Split around `[duty_start, duty_end + min_rest]`.

### 5.0.5 Simulation end, warm-up, and cool-down

This is a **terminating (finite-horizon) simulation**, not a steady-state one. The planning question is
"expected cost over a bid period", the horizon is a fixed calendar window, and seasonality means the
system never reaches steady state by design.

```
t=0                 t=7d                          t=35d              t=42d
 │───── warm-up ─────│────── measurement window ────│──── cool-down ───│
 │  booked, excluded │        KPIs computed here    │ costs attributed │
 │     from KPIs     │                              │  back if caused  │
 │                   │                              │   in-window      │
```

- **Horizon:** `T` = 7-day warm-up + 28-day measurement window + 7-day cool-down = **42 days**.
  *(Fixes **D10** — v2 stated 35 days in §5.1 and 42 days in §5.0.5.)*
- **Warm-up validation:** length is checked with Welch's procedure on the daily open-time count —
  inspect when the moving average of `|O(t)|` stabilises across scenarios. Do not simply assert 7 days.
- **Cool-down:** events continue for 7 days past the measurement window so cascades seeded inside the
  window realise their costs. Costs booked during cool-down are attributed to the measurement window
  **if their causal chain originates there** — which is what `root_event_uid` on every ledger row is
  for.
- **Terminal penalty:** residual open items at `T` are charged `V(s_T)`. Without this, a policy can
  look cheap simply by pushing recovery past the boundary — a failure mode that cannot arise in an
  infinite-horizon average but is central in terminating simulations.

  `V` is defined as `cancel_cost × 1.5` (§4.4.2). It **must** exceed `cancel_cost`, or the model learns
  that abandoning an item is cheaper than cancelling it. It is also a dominant lever on CVaR, so gate
  **V9** requires a sensitivity sweep proving the recommendation is stable across a range of `V`.
- **Replication logic:** one scenario = one replication. The estimator is the across-scenario mean (and
  CVaR) of measurement-window cost, CRN-paired across policies. The number of replications `N` is
  chosen from the **paired-difference** standard error target, not from within-run entity counts.

---

## 5.1 Entities

```python
@dataclass
class CrewMember:
    crew_id: str          # pseudonymised (§6.2, Law 25)
    base: str             # "YUL" | "YYZ" | "YVR"
    fleet_quals: set[str] # {"A321neoLR"} — no overlap with {"A330"}
    position: str         # "CA" | "FO"
    seniority: int        # 1 = most senior
    calendar: list[Block] # sorted by start; duty blocks never overlap (rule L0)

@dataclass(frozen=True)
class Block:
    start: float          # sim minutes
    end: float
    btype: BlockType      # PAIRING RESERVE DAY_OFF VACATION TRAINING
                          # SIMULATOR REST DEADHEAD DRAFTED_DUTY
                          # DAY_OFF is the model's name for Air Transat's
                          # roster code WFY — no duty assigned (§5.6).
    pairing_id: str | None = None
    # No `protected` flag: nothing is exempt from drafting (§5.6).

@dataclass
class Pairing:
    pairing_id: str
    base: str; fleet: str
    position_complement: dict[str, int]   # {"CA": 1, "FO": 1}
    duty_periods: list[DutyPeriod]        # report/release times
    credit_hours: float

@dataclass(frozen=True)
class OpenTimeItem:
    uid: int
    pairing_id: str
    base: str; fleet: str; position: str
    start: float          # report time
    end: float            # release time
    deadline: float       # cancel if not covered by this time
    origin: str           # "SICK_CALL" | "CASCADE" | "DELAY"
    root_event_uid: int   # for cost attribution across cascade levels
```

---

## 5.2 Scenario Generator (Monte Carlo, CRN)

### The CRN design — the critical piece

- One **master seed** defines an experiment. `SeedSequence(master).spawn(N)` yields one child per
  scenario. Each scenario's `SeedSequence` is spawned again into **named streams**: `severity`,
  `sick_calls`, `delays`, `recovery_times`, `tiebreaks`.
- Scenario streams are generated **independently of any policy**. Every candidate policy sees the
  identical scenario set, so cost differences are paired and `Var(C_A − C_B)` collapses.

**Stream discipline rule.** The DES core must never draw from a shared RNG whose *call order* depends
on policy decisions. Any quantity consumed conditionally on policy behaviour — the recovery duration of
a draft, say — is drawn from a dedicated stream keyed by `(scenario, stream, event_uid)`:

```python
def event_rng(self, stream: str, event_uid: int) -> np.random.Generator:
    return np.random.default_rng(
        np.random.SeedSequence(stable_seed(self._entropy, stream, event_uid))
    )
```

`stable_seed` uses **blake2b**, not Python's `hash()`. `hash()` on a string is salted per interpreter
by `PYTHONHASHSEED`, so under `joblib` multiprocessing the same event would get different random
numbers in different workers — silently destroying reproducibility and gate V7. *(Fixes **D2**.)*

**Worked example of why alignment matters.** Policy A drafts on event 17; policy B finds an eligible
reserve and does not. If both drew from one shared stream, every subsequent draw would be offset by one
between the two policies, and the "same" January would diverge — the scenarios would no longer be
common, and the paired comparison would be worthless. Keying by `event_uid` means event 23 gets the
same number under both policies regardless of what happened at event 17.

### What one scenario contains

1. **Daily severity regime** `Z_d ∈ {CALM, NORMAL, DISRUPTED, SEVERE}` — a 4-state Markov chain fitted
   per season from historical daily disruption counts. The regime multiplies the intensities of *all*
   streams, which is what induces the sick-call/weather/delay correlation that sizes tail risk
   (§1.3.4).

   ```python
   P = [[.70, .25, .04, .01],     # from CALM
        [.20, .60, .15, .05],     # from NORMAL
        [.05, .30, .50, .15],     # from DISRUPTED
        [.02, .18, .40, .40]]     # from SEVERE  ← note the stickiness
   intensity_multiplier = [0.5, 1.0, 2.0, 3.5]
   ```

   The 0.40 self-transition on `SEVERE` is doing real work: it produces *multi-day* bad stretches — an
   ice-storm week, not four unlucky Tuesdays scattered through the month. Those clustered stretches are
   what actually exhaust a reserve pool.

2. **Sick-call arrivals** — a non-homogeneous Poisson process, intensity `λ(t) = exp(β·x(t))` with
   covariates season, day-of-week, base, fleet, category, and the regime multiplier. Fitted as a
   Poisson/NegBin GLM on daily counts, then thinned to continuous time.

   Each arrival is **tagged to a specific crew member who is currently flying or about to report**,
   sampled from the roster state, with a sampled absence duration (lognormal). Multi-day absences
   generate multiple open-time items.

3. **Delay / IROPS events** — a marked point process per station-day, regime-modulated; marks are
   delay minutes from a fitted mixture. MVP uses delays as cost and as duty-extension triggers only;
   no network propagation (§1.4).

4. **Recovery and administrative durations** — notification-to-report times, deadhead durations, from
   fitted distributions.

**Output:** an immutable, Parquet-serialisable `Scenario` = ordered event list + per-stream seeds.

**Note on roster variability.** The line-holder roster is held identical across scenarios by design:
the roster is a Stage-1 given, so holding it fixed is part of the CRN pairing rather than an oversight.
This is a *stated modelling choice*; it suppresses roster-composition variance that a real bid period
has, and Phase 2 should sample rosters across bid periods to reintroduce it.

---

## 5.3 DES core (SimPy)

The recovery pipeline, which is the heart of the model:

```
OpenTimeItem created
  → Eligibility Engine: any eligible reserves at the required base/fleet/position?
      ├─ yes → assign the cheapest-to-use eligible reserve (θ tie-break) → done
      └─ no  → (optional, if θ.allow_cross_base and time permits)
                deadhead an eligible reserve from YYZ/YVR — costed with deadhead + hotel
              → Draft Candidate Selection (§5.6)
                  ├─ candidate found → DRAFT_EXECUTED → Cascade Evaluation
                  └─ none feasible   → hold until UNCOVERED_DEADLINE → cancellation
```

The DES core is a thin orchestration layer. **All domain logic lives in the engines**, so each is
unit-testable without SimPy (§4.2 dependency rule).

---

## 5.4 Crew State Engine & legality surrogate

### State representation

Per crew member, an interval calendar of `Block`s, kept sorted, with `O(log n)` point queries via
`bisect`. All mutations go through three audited atomic operations:

| Operation | Used for |
|---|---|
| `remove_block(crew, block)` | Sick crew's pairing removed → becomes an `OpenTimeItem` |
| `insert_block(crew, block)` | Reserve conversion or draft |
| `shift_or_extend(crew, block, Δ)` | Delay-driven duty extension |

Every mutation returns a `StateDelta`, which the Cascade Evaluation Engine consumes. **This is what
makes cascades emergent rather than random.**

### The legality surrogate

A deliberately *small* rule set, chosen to capture the large majority of binding constraints while
remaining fully testable. It is **not** a compliance tool and must never be described as one.

| # | Rule (MVP defaults, configurable) | Real-world anchor |
|---|---|---|
| **L0** | **Single assignment: a crew member holds at most one duty at any instant.** The checked span is the duty **plus the rest it obliges**, since that rest is as physically binding as the duty. | Physical reality |
| L1 | Max duty period: 13 h (any start time) | CARs FDP tables, flat conservative bound |
| L2 | Min rest before duty: 11 h at home base, 10 h away | CARs rest provisions |
| L3 | Max in rolling 7 days: 60 h duty / 35 h flight | Cumulative limits |
| L4 | Max duty in rolling 28 days: 190 h | Cumulative limits |
| L5 | Min 1 day fully free of duty per rolling 7 days | Days-off rule |
| L6 | Qualification: type rating **and** position must match (binary) | Type ratings — hard-binding across A321/A330 (§4.5.1) |
| L7 | Crew must start duty at own base unless deadheaded; deadhead consumes duty time per L1 | Positioning |
| L8 | Reserve call-out: minimum notification-to-report 2 h (short-call) / 12 h (long-call) | Reserve rules |

> **There is no L9.** v2 defined a rule making `VACATION` and `SIMULATOR` blocks draft-prohibited when
> flagged `protected=True`. **Air Transat has no protected-block concept in drafting** — no schedule
> block is contractually exempt. That rule has been removed rather than defaulted off, because a
> disabled rule invites someone to re-enable it. Vacation and simulator remain the two most expensive
> impact tiers (§5.6); they are never forbidden. `[CONFIRM: Labour Relations]`

> **L0 is new in v3.** v2's rule list ran L1–L9 with no single-assignment rule anywhere, and gate V8
> only checked L1–L2. Running v2's reference implementation produced **1,030 physically impossible
> assignments** (a crew member's drafted duty overlapping another of their own blocks) across 20
> scenarios, plus 80–130 reserve double-bookings. Physical feasibility is more fundamental than any
> rest rule. *(Fixes **D3**.)*

**Conservative bias.** Wherever the surrogate simplifies, it simplifies toward *stricter* limits, so
surrogate-legal ⇒ almost always truly legal. The bias direction is documented per rule, and its
magnitude is quantified in Phase 3 when the full rules engine is available for comparison.

**Implementation:** pure functions `is_legal_assignment(crew_state, duty) -> LegalityResult`, where the
result carries the failing rule id for explainability. Property-based tests (hypothesis) assert the
invariants listed in §4.3.

### Worked example — the surrogate rejecting a plausible assignment

Open item: TS156 YUL–CDG, FO, report Tuesday 16:00, release Wednesday 02:00 (10 h duty).

| Candidate | Situation | Verdict |
|---|---|---|
| `R001` | On short-call reserve until Tue 18:00; last duty ended Mon 20:00 (20 h rest) | **LEGAL** |
| `R002` | On long-call reserve; call placed Tue 15:00, report Tue 16:00 → 1 h notice | `ILLEGAL_L8` (long-call needs 12 h) |
| `C0041` | Free, but already holds a drafted duty Tue 14:00–Tue 22:00 | `ILLEGAL_L0` (double assignment) |
| `C0203` | Free and rested, A330 type rating | `ILLEGAL_L6` (wrong type rating) |
| `C0007` | Free, rested, correct rating, but based at YYZ and `θ.allow_cross_base = false` | `ILLEGAL_L7` (base) |

Five candidates, one usable. That is the ≈30% eligibility figure from §1.3.1 arising from mechanism
rather than from a parameter.

---

## 5.5 Reserve Eligibility Engine

For an `OpenTimeItem` `o`:

$$E(o) = \{\, r \in \text{ReservesOnCall}(o) \;:\; \text{L0–L8 all satisfied for } r \text{ over } o\text{'s duty window} \,\}$$

→ code:

```python
def eligible_reserves(reserves, o, now) -> list[CrewMember]:
    # "On call" means a RESERVE block covers the DUTY WINDOW, not merely the
    # moment the phone rings. A reserve whose on-call period ends at 18:00
    # cannot take a trip reporting at 19:00.
    pool = [r for r in reserves
            if any(b.btype is BlockType.RESERVE for b in r.blocks_in(o.start, o.end))]
    elig = [r for r in pool if is_legal_assignment(r, o).legal]
    log_eligibility_sample(len(elig) / len(pool) if pool else None)   # → gate V3
    return elig
```

- **FULL mode:** computed exactly as above. The realised eligibility fraction is logged per event.
  **Gate V3:** its distribution must be consistent with the historical band from §6.3-2 — measured on
  a **holdout** period.
- **REDUCED mode:** each reserve independently eligible w.p. `p_elig` (default 0.30). Smoke tests and
  screening only.
- **Selection among eligible reserves** (part of `θ`): default `shortest_remaining_window` — pick the
  reserve whose remaining on-call period ends soonest ("use them or lose them"), tie-broken by
  seniority via the dedicated `tiebreaks` stream so the result is deterministic given the scenario.

  *Rationale:* a reserve whose window ends at 18:00 is worth nothing after 18:00; a reserve on call
  until Friday retains option value. Spend the perishable one first.

---

## 5.6 Draft Candidate Selection Engine

Per Air Transat's stated policy, drafting priority is determined **first by the impact tier of the
drafted crew member, then by seniority within tier — most senior first**, with each tier carrying its
own cost.

**Why senior-first, and why it is not a decision variable.** Drafting is paid at a premium, so it is
work crew *want*. Allocating it senior-first is the same seniority principle that governs bidding —
seniority gets first call on lucrative work. It is a fact about the agreement, not a lever the optimiser
may vary. `junior_first` exists in the code solely as a labelled counterfactual (§3) and may never
appear in a candidate policy.

**No cap and no exemptions.** There is no limit on how often one crew member may be drafted in a month,
and no schedule block is protected. The binding constraints are the legality rules L0–L8 and whether the
schedule physically permits the assignment — nothing else.

**Tier 1 in Air Transat's own terms.** A tier-1 candidate is a crew member whose roster block for that
window is **`WFY`** — the schedule code meaning they have no duty assigned. There is no opt-in or
willingness list: if the block says `WFY` and the legality rules pass, the crew member is a candidate,
and the most senior of them is taken.

### Impact tiers

The simulator exhausts tier `k` before considering tier `k+1`.

| Tier | Crew status during the target window | Cost coefficient | Notes |
|---|---|---|---|
| 1 | **No duty** — day off, at home, nothing conflicting | `tier_cost[1]` = 0 | Least disruptive; premium pay only |
| 2 | **Holds a future pairing** that conflicts | `tier_cost[2]` = 300 | Removing them from that pairing is a guaranteed cascade candidate |
| 3 | **Ground training** | `tier_cost[3]` = 900 | Adds `train_reschedule_cost` |
| 4 | **Vacation or statutory holiday** | `tier_cost[4]` = 2,500 | **Reachable.** Not prohibited — Air Transat has no protected-block rule. Reached once tiers 1–3 are exhausted. |
| 5 | **Simulator session** | `tier_cost[5]` = 4,000 | **Reachable.** Adds the cost of the lost simulator slot. |

### Selection algorithm

```python
def select(roster, o, θ) -> CrewMember | None:
    # No cap on drafts per crew: legality and schedule feasibility are the
    # only limits. drafts_this_month is a KPI, never a filter.
    candidates = [c for c in roster if is_legal_assignment(c, o).legal]   # L0–L8

    by_tier: dict[int, list[CrewMember]] = {}
    for c in candidates:
        # No protected-block filter: every tier is reachable.
        by_tier.setdefault(status_tier(c, o.start, o.end), []).append(c)

    for tier in (1, 2, 3, 4, 5):
        if by_tier.get(tier):
            # SENIOR FIRST, always. seniority == 1 is the most senior crew
            # member, so this is ascending seniority number.
            by_tier[tier].sort(key=lambda c: c.seniority)
            return by_tier[tier][0]
    return None                       # → item stays open → possible cancellation
```

> **This was the most consequential code defect in v2.** Its selector sorted twice with the sense
> inverted, so *both* settings returned the most **junior** candidate — meaning the only rule Air
> Transat actually uses, senior-first, was implemented backwards. Because the two settings produced
> *bit-identical* cost vectors, there was no way to notice from the output. *(Fixes **D6**.)*

> **Senior-first is fixed, not chosen.** It is Air Transat's mandated order and is therefore a constant
> in this model, not a parameter the optimiser may vary. `junior_first` survives in the code **only** as
> a labelled counterfactual for pricing the mandated rule (§3); it must never appear in a candidate
> policy or a recommendation. Worth noting for reviewers: senior-first drafting is the inverse of the
> common industry pattern, in which seniority confers protection — so it should be pinned to the
> specific agreement clause. `[CONFIRM: Labour Relations]`

- `status_tier` is computed from the crew member's calendar over the pairing window — fully
  deterministic and auditable.
- Draft cost booked = `base_draft_cost + tier_cost[k] + premium_pay(duty) + positioning`. Cascade costs
  are booked later by the cascade chain itself (see §5.7 for the anti-double-counting rule).
- **Distribution KPIs:** per-crew draft counts, maximum, and Gini concentration, reported per policy.
  Read these as the distribution of **premium earnings**, not of an imposed burden (§1.3.5). A high Gini
  is the expected result of senior-first allocation, not a warning sign. Interpret the maximum with
  care too: with no cap, one crew member being drafted four times in a month is now possible and legal.

### Worked example — full arithmetic for one draft

Open item `O-991`: TS156 YUL–CDG, FO, Tuesday. No reserve eligible. Drafting has no parameters — tier
order and senior-first are mandated.

| Step | Result |
|---|---|
| Legal candidates after L0–L8 | 14 crew members |
| No draft cap — prior drafts do not disqualify anyone | 14 remain |
| No protected-block filter — every block is draftable | 14 remain |
| Tier 1 (day off) | 2 candidates: `C0007` (seniority 7), `C0102` (seniority 102) |
| Senior-first ⇒ lowest seniority number first | **`C0007` selected** |
| Cost booked | `500 (base) + 0 (tier 1) = $500`, category `DRAFT_TIER1` |
| Cascade evaluation | `C0007` holds no pairing within duty + 11 h rest → **no cascade** |
| Total attributable cost | **$500** |

Now change one thing: suppose no tier-1 candidate existed and the algorithm fell through to tier 2,
selecting `C0088`, who holds TS738 YUL–PUJ departing Wednesday 05:30.

| Step | Result |
|---|---|
| Cost booked immediately | `500 + 300 = $800`, category `DRAFT_TIER2` |
| Cascade evaluation | TS738 starts inside `C0088`'s post-duty rest → **pairing removed**, new `OpenTimeItem O-992` inserted at Wed 05:30 − 24 h |
| Recovery of `O-992` | No reserve eligible at 05:30; no legal draft candidate |
| Outcome | Cancellation: `25,000 + APPR compensation` |
| **Total attributable cost** | **$25,800 + compensation**, all tagged `root_event_uid = O-991` |

The tier-2 draft cost $800 on the books and $25,800 in reality. Reproducing that gap is the reason this
system exists.

---

## 5.7 Cascade Evaluation Engine (emergent)

Consumes the `StateDelta` of every draft and produces downstream disruptions:

1. **Future-pairing cascade.** If the drafted crew member held pairing `P` that the new duty overlaps,
   or that starts inside the mandatory rest following it, `P` is removed → a new `OpenTimeItem(P)` is
   inserted into the SimPy queue at the correct future time → the recovery pipeline re-fires.
   Multi-level cascades arise naturally, depth-limited only by the horizon.
2. **Future-reserve cascade.** If the drafted crew member held a future `RESERVE` block now consumed or
   made illegal, the reserve pool at that day shrinks — future eligibility contracts *structurally*.
3. **Legality-shift effects.** Rest pushes and rolling-limit consumption are recomputed; blocks that
   become illegal surface as further deltas.

**Gate V4:** the realised cascade frequency — the share of drafts producing ≥1 downstream open item or
reserve loss — must be consistent with the historical band from §6.3-3, on a holdout period.

**REDUCED mode:** `Bernoulli(p_cascade)` (default 0.20) spawning a synthetic future open item.
Screening only.

### The anti-double-counting rule — read this before touching the Cost Engine

> A cascade's cost is **the recovery cost of the open item it creates**, booked by the recovery pipeline
> when that item is handled. There is no separate additive "cascade cost" term.

v2's §7.3 carried a separate `Σ q^casc_e` term *in addition to* cascade items re-entering the open-time
queue and incurring their own reserve/draft/cancellation costs — and v2's own worked example for
`q^casc` ("ruined tomorrow's pairing, causing a new $5,000 scramble") **was** the recovery cost of the
re-entered item. That is a double count in the objective function. *(Fixes **D7**.)*

If a genuinely non-recovery residual cost is later identified — reputational damage, a knock-on
crew-morale effect, an aircraft swap cost — it may be added back as an explicitly named, separately
defined category. It must not be a vaguely-defined catch-all.

---

## 5.8 Cost Engine

Event-sourced ledger. Every row:
`(scenario_id, policy_id, sim_time, event_uid, root_event_uid, crew_id, category, amount)`.

| Category | Booked when | Calibration source |
|---|---|---|
| `RESERVE_STAFFING` | **Per reserve, per day**, at that day's timestamp | Pay registers: reserve guarantee |
| `RESERVE_UTILIZATION` | Reserve converted to duty (marginal pay delta) | Pay rules |
| `DRAFT_BASE` + `DRAFT_TIER{k}` | `DRAFT_EXECUTED` | ALPA premium + tier coefficients, Finance-validated |
| `TRAIN_RESCHEDULE` | Tier-3 or tier-5 draft | Training department |
| `DEADHEAD`, `HOTEL`, `TRANSPORT` | Positioning events | Historical invoices / per-diem tables |
| `DELAY` | Delay minutes on covered flights | CAD per minute, Finance |
| `CANCELLATION` + `PAX_COMPENSATION` | `UNCOVERED_DEADLINE` | Internal cancellation cost + APPR schedule (§4.4.3) |
| `TERMINAL_PENALTY` | Horizon end, residual open items | `cancel_cost × 1.5` (§4.4.2) |

> **`RESERVE_STAFFING` accrues per day, not as a lump at `t = 0`.** v2 booked the whole horizon as one
> row at `t = 0.0`, which the warm-up filter (`keep rows where t ≥ warmup_end`) then discarded — so the
> entire fixed cost of the Stage-1 decision was absent from every reported number and expected cost
> fell monotonically in the reserve count. The model would have recommended the maximum possible number
> of reserves. *(Fixes **D1** — the single most consequential defect found in v2.)*

**Design rule:** only *hard, auditable* costs enter the objective. Soft impacts (morale, fairness) are
KPIs and optional constraints, never invented dollar weights (§1.3.5). All coefficients live in
`costs_pilots.yaml` with a version hash recorded in every run's metadata.

---

## 5.9 Policy object & evaluation loop

```yaml
# configs/policies/YUL-A321neoLR-FO-R14-juniorfirst-v3.yaml
policy_id: YUL-A321neoLR-FO-R14-juniorfirst-v3
costs_file: costs_pilots.yaml@v3.2.1        # hash-pinned
stage1:
  reserves:
    - {base: YUL, fleet: A321neoLR, position: FO, dow: [1,2,3,4,5], short_call: 4, long_call: 2}
    - {base: YUL, fleet: A321neoLR, position: FO, dow: [6,7],       short_call: 5, long_call: 2}
stage2:
  # Drafting is fully determined: impact tier, then senior first, no cap,
  # nothing protected. Only reserve dispatch is configurable.
  allow_cross_base_reserve: true
  reserve_selection: shortest_remaining_window
mode: FULL
season: winter_sun
```

**Evaluation:** `evaluate(policy, scenario_set) -> PolicyResult{E[C], CVaR95, per-category means,
service KPIs, validation stats}`. One SimPy environment per scenario, parallelised with joblib
(`n_jobs=-1`). A 28-day, 120-crew, single-fleet scenario runs in the low hundreds of milliseconds, so a
full 1,000-scenario policy evaluation is a couple of minutes on a workstation.

---

## 5.10 Headcount conservation — the modelling rule v2 was missing

> **A reserve is not extra capacity. It is a line holder who is not flying a line.**

At Air Transat, as at any airline, reserve lines are bid from the same seniority list as flying lines.
Adding one reserve therefore does **two** things simultaneously:

1. It removes one crew member from the draftable line-holder pool.
2. It puts that person's flying into open time, where somebody else must cover it.

v2's reference implementation minted reserves as *new* crew on top of a fixed 120-person roster, so
total headcount varied with the decision variable and reserves were free extra capacity. §7.4's
`Σ R ≤ H_b` constraint caps the total but does not model the coupling.

**Implementation (slice 1b):** partition one fixed roster of size `population.roster_size`
(`configs/base.yaml`, §4.4.1) into reserve lines and flying lines per policy.

```python
def build_population(roster: list[CrewMember], policy: Policy) -> tuple[list, list]:
    """Reserves are CARVED OUT of the roster, never added to it."""
    n = policy.total_reserves()
    reserve_crew = select_reserve_bidders(roster, n)      # by seniority/bid rules
    line_crew    = [c for c in roster if c not in reserve_crew]
    # The pairings the reserve crew would have flown now need covering — they
    # enter open time or are absorbed by the published schedule, per config.
    return line_crew, reserve_crew
```

**What this fixes, precisely.** It does *not* create the trade-off — the reference implementation in
§8.3 has no headcount conservation and still produces a clean U-shaped cost curve, because the staffing
price tag alone is enough to make an interior optimum exist once reserve cost is booked correctly
(D1) and reserves can be reused correctly (D3, plus the reserve-block split).

What headcount conservation fixes is the **level**, not the shape. Without it, every candidate `R` is
evaluated against a *different, larger* total workforce, so the true opportunity cost of a reserve — the
line they are not flying, which someone else must cover — is missing from the comparison. The optimum
is therefore biased **low in opportunity cost**, meaning the model understates what reserves really
cost the operation and will recommend more of them than it should. The shape is right; the number is
wrong. Since the number is the deliverable, this remains a slice-1b requirement.
