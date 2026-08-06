# Crew Reserve & Drafting Policy Optimization System
## Stochastic Simulation for IOC Recovery Policy Design

**Document type:** Technical Specification & Implementation Plan
**Version:** 1.0 (MVP-first)
**Status:** Draft for review
**Scope note:** This system is an **offline policy-simulation and optimization tool**. It is *not* a real-time decision-support system. Its outputs inform monthly/bid-period reserve planning and drafting-policy design, not day-of-operation recovery actions.

---

# 1. Problem Statement

## 1.1 Operational Context

An airline Integrated Operations Center (IOC) continuously manages crew disruptions caused by sick calls, delays, irregular operations (IROPS), maintenance events, and weather. A central, recurring decision is the balance between:

- **Reserve crews** — crew members paid to be on standby (long-call or short-call). Reserves that go unused are pure staffing cost; reserves that are used are the cheapest recovery instrument.
- **Drafting** — involuntarily assigning a crew member who was not on reserve (from a day off, a future pairing, training, or vacation) to cover an open flying assignment. Drafting cost is **not fixed**: it depends on the operational status of the drafted crew member at the moment of drafting, and it may create **cascading disruptions** in the future schedule.

Too many reserves → high fixed staffing cost, low utilization.
Too few reserves → frequent drafting → high variable cost, employee-relations damage, and downstream schedule instability.

## 1.2 Decision Problem

> **Determine the reserve staffing level (by base, fleet, crew category, and day-of-week) and the drafting policy parameters that minimize the airline's total expected operational recovery cost over a planning horizon, while maintaining service levels and regulatory compliance.**

This is a **two-stage stochastic optimization problem**:

- **Stage 1 (here-and-now, bid-period timescale):** the reserve vector — how many reserves, of which category, at which base, on which days.
- **Stage 2 (recourse, day-of-operation timescale):** the drafting policy — given a realized disruption stream and the current crew state, which recovery action is taken (assign eligible reserve, or draft according to the priority/cost rules defined in §5.6).

Stage-1 decisions are committed weeks in advance and cannot be changed on the day of operation. Stage-2 behavior is a *policy* (a parameterized rule), not a per-event free decision — the optimizer searches over policy parameters, and the simulation evaluates each candidate (Stage-1 vector + Stage-2 policy) against a common set of stochastic scenarios.

## 1.3 Key Modeling Principles

The following principles correct known weaknesses of naive reserve-sizing models:

1. **Eligibility is emergent, not exogenous.** When a sick call occurs, only a subset of reserves can legally and practically cover it (qualification, base, position, legality, rest). Historically ≈30% of reserves are eligible for a given sick call. In this model, the 30% figure is a **calibration/validation target**, not an input: eligibility is computed per-event from the Crew State Engine. (A reduced-form Bernoulli(p_elig) variant is retained for fast screening runs only.)
2. **Cascades are emergent, not exogenous.** Drafting Crew A may uncover A's future pairing or destroy A's future reserve block. Whether this happens is a deterministic consequence of A's schedule, computed by the Crew State Engine. The historical ≈20% cascade frequency is again a **validation target**. (A reduced-form Bernoulli(p_cascade) variant is retained for screening.)
3. **Drafting cost is state-dependent.** Each draft's cost is computed from the drafted crew member's status at draft time (no duty / has future pairing / training / vacation-holiday), plus downstream recovery costs (deadhead, hotel, delay, cancellation, cascade).
4. **Correlated disruption streams.** Sick calls, weather disruptions, and delays are *not* independent. A latent daily disruption-severity regime drives all stochastic streams so that tail-risk days (the days that actually size the reserve requirement) are represented realistically.
5. **Hard costs vs. hard constraints.** Monetizable costs (premium pay, hotels, deadhead, compensation) enter the objective. Contractually prohibited actions (where applicable) are hard constraints. Soft impacts (morale, fairness) are reported as KPIs and optional constraints, never as invented cost weights buried in the objective.
6. **Common Random Numbers (CRN).** All candidate policies are evaluated against the *same* pre-seeded scenario set, so policy comparisons are paired comparisons with dramatically reduced variance.

## 1.4 Out of Scope

- **Real-time / day-of decision support.** The system runs offline; a "what-if" live mode is a possible future phase but is explicitly out of scope for this document.
- **Voluntary recovery layer** (open-time award, voluntary pickup at premium). Not modeled in this version. All uncovered demand after reserve assignment goes directly to the drafting policy. *(Consequence: simulated drafting frequency is an upper bound on reality; this is documented and accepted for policy comparison purposes, since the bias applies equally to all candidate policies.)*
- **Full legality engine.** The Crew State Engine uses a **legality surrogate** — a simplified, conservatively-biased rule set (§5.4) — rather than full CARs Part VII + CBA legality. Full-rules integration is a later phase.
- **Aircraft/passenger recovery optimization.** Aircraft and passenger impacts appear only as cost terms (delay, cancellation, compensation), not as recovery decisions.

---

# 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     HISTORICAL DATA LAYER                        │
│  Rosters │ Pairings │ Sick calls │ Draft events │ Pay │ OTP      │
│                  (Delta Lake / Parquet corpus)                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │  batch ETL + calibration jobs
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                 STATISTICAL CALIBRATION LAYER                    │
│  • Sick-call arrival model (NHPP, covariates: season, DOW,       │
│    base, fleet, category)                                        │
│  • Disruption-severity regime model (latent daily state)         │
│  • Delay / IROPS event models                                    │
│  • Crew-status distributions (for validation targets)            │
│  • Cost parameter calibration (pay rules → $ coefficients)       │
│  Output: fitted parameter store (versioned JSON/Parquet)         │
└───────────────────────────────┬─────────────────────────────────┘
                                │  fitted distributions
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│           SCENARIO GENERATOR  (Monte Carlo, CRN-seeded)          │
│  • SeedSequence-based hierarchical RNG streams                   │
│  • One scenario = one realization of all disruption streams      │
│    over the planning horizon                                     │
│  • Scenario set is FIXED across all candidate policies (CRN)     │
└───────────────────────────────┬─────────────────────────────────┘
                                │  scenario event streams
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              DISCRETE EVENT SIMULATION CORE (SimPy)              │
│                                                                  │
│   ┌──────────────┐   ┌────────────────────┐   ┌──────────────┐  │
│   │ Crew State   │◄──│  Event Dispatcher  │──►│ Reserve      │  │
│   │ Engine       │   │  (sick call, delay,│   │ Eligibility  │  │
│   │ (legality    │   │  duty end, rest    │   │ Engine       │  │
│   │  surrogate)  │   │  end, cascade)     │   │              │  │
│   └──────┬───────┘   └─────────┬──────────┘   └──────┬───────┘  │
│          │                     │                     │          │
│          ▼                     ▼                     ▼          │
│   ┌──────────────┐   ┌────────────────────┐   ┌──────────────┐  │
│   │ Draft        │   │ Cascade Evaluation │   │ Cost Engine  │  │
│   │ Candidate    │──►│ (emergent from     │──►│ (event-level │  │
│   │ Selection    │   │  state updates)    │   │  ledger)     │  │
│   │ (seniority + │   └────────────────────┘   └──────────────┘  │
│   │  impact tier)│                                              │
│   └──────────────┘                                              │
└───────────────────────────────┬─────────────────────────────────┘
                                │  per-scenario cost ledgers + KPIs
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                POLICY OPTIMIZATION ENGINE                        │
│  • Policy = (reserve vector R, drafting-policy params θ)         │
│  • Evaluation: run all CRN scenarios → E[C], CVaR, service KPIs  │
│  • Search: Bayesian optimization (continuous R) +                │
│    ranking & selection (discrete rule variants)                  │
│  • Parallel execution: joblib (MVP) → Ray / AKS (scale)          │
└───────────────────────────────┬─────────────────────────────────┘
                                │  policy comparison results
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                DECISION SUPPORT REPORTING                        │
│  • Recommended reserve vector + drafting parameters              │
│  • E[cost], CVaR₀.₉₅, cost breakdown by category                 │
│  • Reserve utilization, draft frequency by crew-status tier      │
│  • Cascade frequency (validated vs. historical ≈20%)             │
│  • Eligibility rate (validated vs. historical ≈30%)              │
│  • Trade-off curves (reserve level ↔ drafting cost)              │
│  • Drill-down to exemplar scenarios per recommendation           │
└─────────────────────────────────────────────────────────────────┘
```

**Architectural commitments:**

- **Separation of randomness and logic.** All randomness is materialized by the Scenario Generator *before* simulation, or drawn from per-scenario named RNG streams. The DES core is deterministic given a scenario. This is what makes CRN, reproducibility, and debugging possible.
- **Event-level cost ledger.** Every cost is booked as a ledger row (scenario_id, sim_time, event_type, crew_id, cost_category, amount). Aggregates are always derivable; nothing is only-aggregated.
- **Policy as data.** A candidate policy is a serializable object (reserve vector + drafting parameters + cost weights), so runs are reproducible and comparable.
- **Two model fidelities.** `FULL` mode (emergent eligibility/cascades via Crew State Engine) and `REDUCED` mode (Bernoulli p_elig / p_cascade) share the same interfaces; REDUCED is used for smoke tests and coarse screening only.

---

# 3. High-Level Phased Approach

## Phase 0 — Data Foundation & Calibration (2–4 weeks, overlaps Phase 1)
- Land historical extracts (§6) into a Parquet/Delta corpus.
- Reconstruct draft-event history (join pay premium codes × schedule-change records — draft events are typically not directly coded in crew tracking systems).
- Fit the sick-call NHPP with covariates; fit the disruption-severity regime model; extract validation targets (eligibility rate ≈30%, cascade rate ≈20%, crew-status-at-draft distribution).
- Deliverable: versioned parameter store + data-quality report.

## Phase 1 — MVP (the starting phase, 6–8 weeks)
**Goal: a working end-to-end pipeline that can compare two reserve/drafting policies on realistic scenarios, with credible (not perfect) fidelity.**

MVP scope:
- Single fleet, single crew category (e.g., A321 First Officers), 1–3 bases.
- Scenario Generator with CRN seeding and the disruption-severity regime.
- SimPy DES core with the full event set (sick call, reserve assignment, draft, duty end, rest end, cascade insertion).
- Crew State Engine with the **legality surrogate** (§5.4) — simplified duty/rest rules, conservatively biased.
- Reserve Eligibility Engine in FULL mode (emergent).
- Draft Candidate Selection with the **seniority + impact-tier policy** (§5.6).
- Cascade Evaluation in FULL mode (emergent from state).
- Cost Engine with hard costs only (reserve pay, draft premium, tier surcharges, deadhead, hotel, delay, cancellation).
- Policy evaluation over N=500–2,000 CRN scenarios; **grid comparison** of a small hand-picked policy set (no optimizer yet).
- Validation gate: eligibility rate and cascade rate emerge within tolerance of historical targets; backtest one known bad-weather week.
- Reporting: static HTML/notebook report (cost distributions, trade-off table, exemplar-scenario drill-down).

## Phase 2 — Optimization & Scale (6–10 weeks)
- Policy Optimization Engine: Bayesian optimization over the reserve vector (scikit-optimize/Optuna) + ranking-and-selection over discrete drafting-rule variants; CRN-paired comparisons throughout.
- Risk-sensitive objective: E[C] + λ·CVaR₀.₉₅(C); service-level chance constraint.
- Multi-fleet, multi-base, multi-category expansion.
- Parallelization: Ray or joblib on a beefy VM → AKS-hosted workers (aligns with the existing digital-twin AKS/SimPy stack).
- Variance reduction: stratified sampling by severity regime in addition to CRN.
- Horizon hygiene: warm-up period, extended horizon, terminal state-value approximation.

## Phase 3 — Enterprise Hardening (ongoing)
- Replace legality surrogate with rules-engine integration (or expanded surrogate with per-CBA rules).
- Scheduled recalibration + input-drift monitoring from Delta Lake.
- Formal V&V accreditation package (trace validation, Turing-style controller test, historical backtesting bands).
- Reporting dashboard (Power BI / web app) with scenario drill-down; integration into monthly bid-period planning workflow.
- Optional future track (explicitly out of current scope): day-of "what-if" mode seeded from live crew state.


---

# 4. Implementation Framework & Library Stack

| Layer | Technology | Version target | Rationale |
|---|---|---|---|
| Language | Python | 3.11+ | Team standard; SimPy/PyData ecosystem |
| DES core | **SimPy** | ≥4.1 | Process-based DES, pure Python, easy to embed and parallelize |
| RNG / CRN | **NumPy** `random.Generator` + `SeedSequence` | ≥1.26 | Hierarchical, collision-resistant seeding — the backbone of CRN |
| Data frames | **Polars** (primary), pandas (interop) | Polars ≥0.20 | Fast columnar ops on scenario ledgers; pandas for plotting interop |
| Statistical fitting | **statsmodels** (GLM/Poisson/NegBin), **scipy.stats** | latest | NHPP covariate fitting; distribution fitting & tests |
| Data models / config | **Pydantic v2** + YAML | ≥2.5 | Typed, validated policy/config objects; serializable policies |
| Storage | **Parquet** via pyarrow; Delta Lake (Phase 2+) | pyarrow ≥14 | Columnar corpus + ledger output; aligns with ADLS Gen2 stack |
| Parallel execution | **joblib** (MVP) → **Ray** (Phase 2) | — | Embarrassingly parallel across scenarios; Ray for AKS scale-out |
| Optimization (Phase 2) | **Optuna** (TPE/GP sampler) or scikit-optimize | latest | Simulation optimization over reserve vector under noise |
| Testing | **pytest** + **hypothesis** | latest | Property-based tests for legality surrogate & cost engine |
| Reporting (MVP) | **Jupyter** + **Plotly** + static HTML export | latest | Cost distributions, trade-off curves, scenario drill-down |
| Packaging | **uv** or Poetry; src-layout package | — | Reproducible envs |
| Code quality | ruff, mypy (strict on core modules) | — | The Crew State Engine and Cost Engine must be type-safe |

Repository layout:

```
crew-recovery-sim/
├── pyproject.toml
├── configs/
│   ├── base.yaml                 # horizon, fleet/base scope, mode=FULL|REDUCED
│   ├── costs.yaml                # all cost coefficients (versioned)
│   └── policies/                 # candidate policy definitions
├── src/crewsim/
│   ├── data/                     # ETL, schema, corpus loaders
│   ├── calibration/              # NHPP fit, regime model, validation targets
│   ├── scenarios/                # ScenarioGenerator, CRN seed management
│   ├── engine/
│   │   ├── state.py              # Crew State Engine (dataclasses + updates)
│   │   ├── legality.py           # Legality surrogate
│   │   ├── eligibility.py        # Reserve Eligibility Engine
│   │   ├── drafting.py           # Draft Candidate Selection policy
│   │   ├── cascade.py            # Cascade Evaluation Engine
│   │   ├── costs.py              # Cost Engine (event ledger)
│   │   └── des.py                # SimPy processes & event dispatch
│   ├── optimize/                 # Phase 2: policy search
│   ├── reporting/                # KPI aggregation, HTML report
│   └── cli.py                    # `crewsim run`, `crewsim compare`, `crewsim calibrate`
└── tests/
```

---

# 5. Detailed Implementation Description

## 5.0 Formal DES Specification — The Five-Component Framework

Following the standard five-component tracking framework for discrete event simulation (simulation clock, system state, events, state transitions, simulation end), this section specifies the crew recovery simulation formally. The framework is the same one used for elementary single-server queueing models (e.g., a coffee-shop M/G/1 system tracked by a scalar state $N(t)$ and a two-event calendar); the crew recovery system is specified in identical terms, with the differences that its state is a **vector**, its event calendar is **heterogeneous and self-extending** (cascades insert future events), and it is a **finite-horizon (terminating)** simulation rather than a steady-state one.

### 5.0.1 Simulation Clock

- **Type:** continuous time, measured in **minutes** from horizon start ($t = 0$); calendar utilities map sim-time ↔ local dates (day-of-week and season drive arrival intensities; legality rules operate on local report times).
- **Advance mechanism:** **next-event time progression.** The clock jumps from one scheduled event to the next (SimPy's event queue); nothing changes between events, so no time is simulated where no decision occurs. This differs from the customer-index recursion usable in a single-queue model ($A_n = A_{n-1} + H_n$, $D_n = S_n + \max(A_n, D_{n-1})$): that recursion works only because a single-server FIFO system has a fixed, homogeneous event pattern per customer. Here, events are heterogeneous (sick calls, delays, duty ends, cascade disruptions), can be inserted dynamically into the *future* of the calendar by the model itself, and interact through shared state — hence a full event calendar is required.
- **Start condition:** the system does **not** start empty. At $t=0$ the state is initialized to a fully populated roster (crew calendars from published rosters, reserve blocks per the Stage-1 policy vector). A **time-based warm-up** of 7 days is still applied (see 5.0.5) to wash out the artificial "no disruption backlog at $t=0$" initial condition — the analog of discarding the first *warmup* customers in the steady-state queue, except deletion here is by time window, not by entity index, because entities (crew) persist for the whole horizon.

### 5.0.2 State of the System: The "Snapshot" Equation

Where a simple system can be tracked by a single number, the airline recovery system requires a composite state vector (a digital snapshot of the entire airline at an exact minute in time, $t$).

$$S(t) = \Big( \underbrace{\{\text{Cal}_c(t)\}_{c \in \mathcal{C}}}_{\text{crew calendars}},\; \underbrace{\text{Res}_{b,f,p}(t)}_{\text{reserve pool}},\; \underbrace{\mathcal{O}(t)}_{\text{open-time queue}},\; \underbrace{\{L_c(t)\}_{c \in \mathcal{C}}}_{\text{legality counters}},\; \underbrace{\{n_c(t)\}_{c \in \mathcal{C}}}_{\text{draft counts}},\; \underbrace{G(t)}_{\text{cost ledger}} \Big)$$

**Explanation:** "The State of the airline right now ($S(t)$) is a combination of everyone's schedules ($\text{Cal}$), who is on standby ($\text{Res}$), what flights are broken ($\mathcal{O}$), who is legally allowed to work ($L$), how many times people have been drafted ($n$), and the total money spent so far ($G$)."

Here is the detailed breakdown of every variable inside this snapshot:

#### 1. $\text{Cal}_c(t)$: Crew Calendars
This tracks the exact scheduled block for every specific crew member ($c$) out of the entire employee list ($\mathcal{C}$) at this exact minute.
*   **Example 1:** Pilot C001 is actively working a flight pairing from 08:00 to 16:00.
*   **Example 2:** Flight Attendant F022 is on a contractually protected vacation.
*   **Example 3:** Pilot C105 is at home on a scheduled day off.

| Crew ID ($c$) | Name | Current Status Block | Start Time | End Time | Protected? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C001 | Pilot A | `PAIRING` (Working) | 08:00 AM | 04:00 PM | False |
| F022 | FA B | `VACATION` | Monday | Friday | True |
| C105 | Pilot C | `DAY_OFF` | 00:00 AM | 11:59 PM | False |

#### 2. $\text{Res}_{b,f,p}(t)$: Reserve Pool
The total count of backup workers waiting on-call, filtered by base ($b$), fleet/airplane type ($f$), and position ($p$).
*   **Example 1:** There are 5 Short-Call Captains waiting in the crew lounge at JFK for the Boeing 737.
*   **Example 2:** There are 2 Long-Call Flight Attendants waiting by their phones in Chicago for the Airbus A320.
*   **Example 3:** There are 0 backups available in Miami because they have all been assigned to flights.

| Base ($b$) | Fleet ($f$) | Position ($p$) | Call Type | Count Available |
| :--- | :--- | :--- | :--- | :--- |
| JFK | Boeing 737 | Captain | `SHORT_CALL` | 5 |
| ORD | Airbus A320 | Flight Attendant | `LONG_CALL` | 2 |
| MIA | Boeing 777 | First Officer | `SHORT_CALL` | 0 |

#### 3. $\mathcal{O}(t)$: Open-Time Queue (The Emergency List)
The queue of unresolved flights that currently have no crew and will be canceled if not fixed before their deadline.
*   **Example 1:** A 4:00 PM flight needs a Captain because the original one called in sick.
*   **Example 2:** A 6:30 PM flight needs a First Officer because their inbound flight was delayed.
*   **Example 3:** A flight tomorrow needs a Flight Attendant due to a cascading schedule disruption.

| Item ID ($o$) | Missing Role | Affected Flight | Required By (Deadline) | Origin of Problem |
| :--- | :--- | :--- | :--- | :--- |
| O-991 | Captain | Flt 101 | 16:00 | `SICK_CALL` |
| O-992 | First Officer | Flt 303 | 18:30 | `CASCADE_DELAY` |
| O-993 | Flight Attendant | Flt 405 | 09:00 (Next Day) | `CASCADE_DRAFT` |

#### 4. $L_c(t)$: Legality Counters (Surrogate)
A simplified, conservatively biased set of counters to ensure crew assignments satisfy safety and rest rules without calling external APIs.
*   **Example 1:** Pilot A has worked 12.5 hours and is approaching the 13-hour maximum duty limit.
*   **Example 2:** Pilot B just finished a 48-hour rest and is completely legal.
*   **Example 3:** Pilot C is legally rested but does not hold the correct fleet qualifications.

| Crew ID ($c$) | Rolling Duty Hours | Rest Since Last Flight | Qualifications | Legal Status |
| :--- | :--- | :--- | :--- | :--- |
| C001 | 12.5 hrs | 14 hrs | A320 | `WARNING: LIMIT` |
| C002 | 0 hrs | 48 hrs | B737 | `LEGAL` |
| C105 | 0 hrs | 72 hrs | A320 | `ILLEGAL_L6` (Wrong Plane) |

#### 5. $n_c(t)$: Draft Counts
Counters tracking how many times a specific crew member ($c$) has been involuntarily drafted this month, used as a fairness guardrail.
*   **Example 1:** Pilot A has a count of 0 (has not been drafted).
*   **Example 2:** Pilot B has a count of 1.
*   **Example 3:** Pilot C has a count of 2, hitting the contractual maximum, making them ineligible for further drafting.

| Crew ID ($c$) | Drafts This Month ($n$) | Max Allowed | Eligible for Next Draft? |
| :--- | :--- | :--- | :--- |
| C001 | 0 | 2 | Yes |
| C002 | 1 | 2 | Yes |
| C105 | 2 | 2 | No (Limit Reached) |

#### 6. $G(t)$: Cost Ledger
The running cumulative financial receipt of every dollar spent resolving disruptions in the current simulation.
*   **Example 1:** A $150 utilization payout to a reserve worker.
*   **Example 2:** A $4,000 penalty paid for drafting someone out of a vacation block.
*   **Example 3:** A $25,000 baseline cost for canceling a flight entirely.

| Sim Time ($t$) | Affected Crew | Category | Amount Spent |
| :--- | :--- | :--- | :--- |
| 14:05 | C001 | `RESERVE_UTILIZATION` | $150.00 |
| 16:30 | F022 | `DRAFT_TIER4` | $4,000.00 |
| 18:00 | None | `CANCELLATION` | $25,000.00 |

**Sufficiency property (the defining requirement of a state):** knowing $S(t)$ and the remaining scenario event stream is sufficient to continue the simulation — no history beyond $S(t)$ is needed. This is the same principle as "once we know $N(t)$ we have all necessary information to continue," generalized to a vector.

### 5.0.3 Events

Two event classes exist: **exogenous** events replayed from the pre-generated (CRN) scenario stream, and **endogenous** events created by the model's own decisions.

| # | Event | Class | Source |
|---|---|---|---|
| E1 | `SICK_CALL` | exogenous | scenario stream |
| E2 | `DELAY` | exogenous | scenario stream |
| E3 | `RESERVE_ASSIGNED` | endogenous | recovery pipeline decision |
| E4 | `DRAFT_EXECUTED` | endogenous | recovery pipeline decision |
| E5 | `CASCADE_DISRUPTION` | endogenous | Cascade Engine (self-inserted **future** event) |
| E6 | `DUTY_END` | endogenous | schedule (consequence of E3/E4 or roster) |
| E7 | `REST_END` | endogenous | schedule (follows E6) |
| E8 | `UNCOVERED_DEADLINE` | endogenous | OpenTimeItem timeout |
| E9 | `HORIZON_END` | control | clock reaches $T$ |

The coffee-shop model has exactly two events (arrival, service completion) and its calendar never grows beyond one pending event of each type. Here E5 is the structurally new element: an event handler (E4) can schedule new disruption events at **future** times, so the event calendar is self-extending — this is precisely how multi-level cascades arise without any exogenous "cascade probability."

### 5.0.4 State Transitions

Each event maps the state deterministically (given the policy) as follows:

$$
S(t^+) = f_{\text{event}}\big(S(t^-),\ \text{event},\ \pi_\theta\big)
$$

| Event | State transition |
|---|---|
| E1 `SICK_CALL` | Remove sick crew's block(s) from $\text{Cal}_c$; $\mathcal{O} \mathrel{+}= \text{OpenTimeItem(s)}$; immediately invoke recovery pipeline → E3, E4, or hold |
| E2 `DELAY` | Extend affected duty block in $\text{Cal}_c$; update $L_c$; re-check downstream legality — any block made illegal is removed and $\mathcal{O} \mathrel{+}=$ new item; book delay cost in $G$ |
| E3 `RESERVE_ASSIGNED` | Reserve block → drafted-duty block in $\text{Cal}_r$; $\text{Res}_{b,f,p} \mathrel{-}= 1$; $\mathcal{O} \mathrel{-}= o$; schedule E6; book utilization cost in $G$ |
| E4 `DRAFT_EXECUTED` | Insert duty into $\text{Cal}_c$; $n_c \mathrel{+}= 1$; $\mathcal{O} \mathrel{-}= o$; book tier-$k$ draft cost in $G$; **run Cascade Engine on the StateDelta** → possibly schedule E5 event(s) at future times |
| E5 `CASCADE_DISRUPTION` | At the scheduled future time: remove the broken pairing / reserve block from $\text{Cal}_c$ (if reserve: $\text{Res} \mathrel{-}= 1$ structurally); $\mathcal{O} \mathrel{+}=$ new item; invoke recovery pipeline (recursion → multi-level cascades) |
| E6 `DUTY_END` | Duty block closes; insert REST block per L2; update $L_c$ accumulators |
| E7 `REST_END` | Crew becomes assignable again; if crew holds a reserve block, restore to $\text{Res}$ |
| E8 `UNCOVERED_DEADLINE` | $\mathcal{O} \mathrel{-}= o$; flight(s) cancelled; book cancellation + compensation in $G$ |
| E9 `HORIZON_END` | Charge terminal penalty $V(s_T)$ on residual $\mathcal{O}$ and uncovered future state; stop |

Compare the scalar rule $N(t) = N(\text{prev}) \pm 1$: transitions here are structured mutations of the state vector, but the discipline is identical — **every** state change occurs at an event, through an enumerated transition, and (in this implementation) through one of three audited atomic operations (`remove_block`, `insert_block`, `shift/extend`), whose emitted `StateDelta` is what the Cascade Engine consumes.

### 5.0.5 Simulation End (and Warm-up)

- **Terminating (finite-horizon) simulation**, not a steady-state one: the planning question is "expected cost over a bid period," so the horizon is a fixed calendar window, and *seasonality means the system never reaches steady state by design*. End condition: $t \ge T$ where $T$ = 7-day warm-up + 28-day measurement window + 7-day cool-down = 42 days (MVP defaults, configurable).
- **Warm-up:** ledger rows with $t <$ warm-up end are booked but excluded from KPIs — the time-based analog of `TimeInShop = mean(D[warmup+1:n] − A[warmup+1:n])`. The warm-up length is validated with Welch's procedure on the daily open-time count (the same "informed choice of warm-up" question flagged in the elementary treatment; here answered by inspecting when the moving average of $|\mathcal{O}(t)|$ stabilizes across scenarios).
- **Cool-down:** events are simulated for 7 days past the measurement window so cascades seeded inside the window realize their costs; costs booked in cool-down are attributed to the measurement window if their causal chain originates there (ledger rows carry the root event uid).
- **Terminal penalty:** any still-unresolved state at $T$ is charged $V(s_T)$ — this prevents policies from looking cheap by pushing recovery past the boundary, a failure mode that cannot arise in an infinite-horizon steady-state average but is central in terminating simulations.
- **Replication logic:** each scenario is one replication; the estimator is the across-scenario mean (and CVaR) of measurement-window cost, with CRN pairing across policies. There is no "stop after $n_{\max}$ customers" alternative here: the replication unit is the scenario, and the number of replications $N$ is chosen from the paired-difference standard error target, not from within-run entity counts.

## 5.1 Simulation Clock, Horizon & Entities

- **Clock:** continuous time in minutes from horizon start (SimPy default float clock). Calendar mapping utilities convert sim-time ↔ local dates (day-of-week and season drive arrival intensities).
- **Horizon:** MVP default 35 days = 7-day warm-up + 28-day measurement window. Cost ledger rows during warm-up are booked but excluded from KPIs. Cascades generated near the end of the window are captured by a 7-day cool-down extension; residual uncovered state at horizon end is charged a **terminal penalty** V(s_T) (MVP: flat per-uncovered-pairing charge, calibrated to average recovery cost) to prevent policies from gaming the boundary.
- **Entities:**
  - `CrewMember`: id, base, fleet quals, position (CA/FO/…), seniority number, calendar of `ScheduleBlock`s.
  - `ScheduleBlock`: interval [start, end) with type ∈ {PAIRING, RESERVE, DAY_OFF, VACATION, TRAINING, SIMULATOR, REST, DEADHEAD, DRAFTED_DUTY} and metadata (pairing_id, protected flag).
  - `Pairing`: id, base, fleet, position requirements, list of duty periods, credit hours.
  - `OpenTimeItem`: an uncovered flying need (pairing or partial pairing) with a required-by time.

## 5.2 Scenario Generator (Monte Carlo, CRN)

**CRN design (the critical piece):**

- A single master seed defines the experiment. `np.random.SeedSequence(master).spawn(N)` yields one child per scenario; each scenario's SeedSequence is further spawned into **named streams**: `severity`, `sick_calls`, `delays`, `recovery_times`, `tiebreaks`.
- Scenario streams are generated (or lazily regenerated bit-identically from seeds) **independently of any policy**. Every candidate policy is simulated against the identical scenario set → cost differences between policies are paired, and Var(C_A − C_B) collapses.
- **Stream discipline rule:** the DES core must never draw from a shared RNG whose call order depends on policy decisions. Any stochastic quantity that is consumed *conditionally on policy behavior* (e.g., recovery duration of a draft) is drawn from its own dedicated stream keyed by (scenario, event-id), so that random-number alignment across policies is preserved. Implementation: `rng_for(scenario_seed, stream_name, event_uid)` derives a fresh Generator via `SeedSequence(entropy=[scenario_entropy, hash(stream_name), event_uid])`.

**Generated content per scenario:**

1. **Daily severity regime** `Z_d ∈ {CALM, NORMAL, DISRUPTED, SEVERE}` — a 4-state Markov chain fitted from historical daily disruption counts (Phase 0). The regime multiplies intensities of *all* streams, inducing the sick-call/weather/delay correlation that sizes tail risk.
2. **Sick-call arrivals** — non-homogeneous Poisson process; intensity λ(t) = exp(β·x(t)) with covariates: season, day-of-week, base, fleet, category, regime multiplier. Fitted as a Poisson/NegBin GLM on daily counts (statsmodels), then thinned to continuous time. Each arrival is tagged to a *currently-flying or imminently-reporting* crew member (sampled from the roster state), with a sampled absence duration (lognormal fit; multi-day absences generate multiple open-time items).
3. **Delay/IROPS events** — marked point process per station-day, regime-modulated; marks = delay minutes (fitted mixture). MVP uses delays only as cost and as duty-extension triggers for legality; no network propagation.
4. **Recovery/administrative durations** — notification-to-report times, deadhead durations (sampled from fitted distributions).

Output: an immutable `Scenario` object (Parquet-serializable) = ordered event list + per-stream seeds.

## 5.3 DES Core (SimPy)

Event types dispatched through the SimPy environment:

| Event | Trigger | Handler outcome |
|---|---|---|
| `SICK_CALL` | scenario stream | create OpenTimeItem(s); invoke recovery pipeline |
| `DELAY` | scenario stream | book delay cost; extend affected duty; re-check legality of downstream blocks (may spawn OpenTime) |
| `RESERVE_ASSIGNED` | recovery pipeline | convert reserve block → duty; book utilization; schedule DUTY_END |
| `DRAFT_EXECUTED` | recovery pipeline | apply schedule mutation to drafted crew; book tiered cost; run Cascade Evaluation |
| `CASCADE_DISRUPTION` | cascade engine (self-inserted) | new OpenTimeItem or reserve-loss at future time → recovery pipeline re-fires |
| `DUTY_END` / `REST_END` | schedule | update crew state; reserve availability restored after rest |
| `UNCOVERED_DEADLINE` | OpenTimeItem timeout | flight(s) cancelled; book cancellation + compensation cost |

**Recovery pipeline (per OpenTimeItem):**
```
OpenTimeItem created
  → Eligibility Engine: eligible reserves at required base/fleet/position?
      ├─ yes → assign cheapest-to-use eligible reserve (policy tie-break) → done
      └─ no  → (optional per policy: deadhead an eligible reserve from another base,
                if θ.allow_cross_base and time permits — costed with deadhead+hotel)
              → Draft Candidate Selection (§5.6)
                  ├─ candidate found → DRAFT_EXECUTED → Cascade Evaluation
                  └─ none feasible   → hold until UNCOVERED_DEADLINE → cancellation
```

The DES core is a thin orchestration layer; **all domain logic lives in the engines** so each is unit-testable without SimPy.

## 5.4 Crew State Engine with Legality Surrogate

**State representation.** Per crew member, an interval calendar of `ScheduleBlock`s (kept sorted; O(log n) point queries via bisect). All mutations go through three atomic operations with full audit logging:
- `remove_block(crew, block)` — e.g., sick crew's pairing removed → OpenTimeItem
- `insert_duty(crew, duty, source)` — reserve conversion or draft
- `shift/extend(crew, block, Δ)` — delay-driven duty extension

Every mutation returns a `StateDelta` consumed by the Cascade Evaluation Engine (§5.7) — this is what makes cascades emergent rather than random.

**Legality surrogate (MVP — simplified, conservatively biased).** The surrogate deliberately implements a *small* rule set chosen to capture ~90% of legality binding constraints while remaining fully testable:

| # | Surrogate rule (MVP defaults, configurable in YAML) | Real-world anchor |
|---|---|---|
| L1 | Max duty period: 13 h (any start time) | CARs FDP tables (conservative flat bound) |
| L2 | Min rest before duty: 11 h at home base, 10 h away | CARs rest provisions |
| L3 | Max flight duty in rolling 7 days: 60 h duty / 35 h flight | cumulative limits |
| L4 | Max duty in rolling 28 days: 190 h | cumulative limits |
| L5 | Min 1 day fully free of duty per rolling 7 days | days-off rule |
| L6 | Qualification: fleet type rating + position match required (binary) | quals |
| L7 | Base rule: crew must start duty at own base unless deadheaded (deadhead consumes duty time per L1) | positioning |
| L8 | Reserve call-out: min notification-to-report 2 h (short-call) / 12 h (long-call) | reserve rules |
| L9 | Protected blocks: VACATION and SIMULATOR blocks flagged `protected=True` are **draft-prohibited if policy θ.respect_protected = True** (default True); otherwise draftable at Tier-4/5 cost | CBA protections |

*Conservative bias:* wherever the surrogate simplifies, it simplifies toward *stricter* limits, so surrogate-legal ⇒ (almost always) truly legal. The bias direction is documented per rule and its effect quantified in Phase 3 when the full rules engine is compared.

Implementation: pure functions `is_legal_assignment(crew_state, duty) -> LegalityResult` (result carries the failing rule id for explainability); property-based tests (hypothesis) assert invariants like "inserting any duty never violates L2 silently."

## 5.5 Reserve Eligibility Engine

For an OpenTimeItem `o`:
```
eligible(o) = { r ∈ reserves_on_call(t) :
                  fleet_qual(r) ⊇ o.fleet
                ∧ position(r) = o.position
                ∧ base(r) = o.base            (unless cross-base deadhead allowed by θ)
                ∧ notification_time(r, o) feasible (L8)
                ∧ is_legal_assignment(state[r], o.duties) }   # L1–L7
```
- FULL mode: computed exactly as above; the *realized eligibility fraction* is logged per event and reported — **validation gate: distribution consistent with historical ≈30%** (tolerance band set in Phase 0).
- REDUCED mode: each reserve independently eligible w.p. `p_elig` (default 0.30) — smoke tests and coarse screening only.
- Among eligible reserves, selection rule (part of θ): default = minimize residual-reserve damage (pick the reserve whose remaining on-call window is shortest — "use them or lose them"), tie-break by seniority order from the dedicated `tiebreaks` stream discipline (deterministic given scenario).

## 5.6 Draft Candidate Selection Engine (seniority + impact tiers)

Per stakeholder direction, drafting priority is determined **first by impact tier of the drafted crew, then by seniority within tier**, with each tier carrying its own cost.

**Impact tiers (ordered — the simulator exhausts tier k before considering tier k+1):**

| Tier | Crew status during the target pairing window | Cost coefficient (configs/costs.yaml) | Notes |
|---|---|---|---|
| 1 | **No duty** in the window (day off / at home, no conflicting block) | `c_tier1` (low) | Least disruptive; premium pay only |
| 2 | **Has a future pairing** overlapping/conflicting | `c_tier2` (medium) | Draft removes their pairing → guaranteed emergent cascade candidate |
| 3 | **Training** (ground/classroom, non-protected) | `c_tier3` (high) | Adds requalification/reschedule cost `c_train_reschedule` |
| 4 | **Vacation / statutory holiday** | `c_tier4` (very high) | Prohibited if `protected=True` and θ.respect_protected |
| 5 | **Simulator session** | `c_tier5` (highest) | Prohibited by default (protected); if allowed, adds sim-slot loss cost |

**Selection algorithm:**
```
candidates(o) = all crew (non-reserve) with fleet/position match, base feasible,
                and is_legal_assignment(state, o.duties) under the surrogate
for tier in 1..5:
    T = {c ∈ candidates(o) : status_tier(c, o.window) == tier
                              and not (protected and θ.respect_protected)}
    if T ≠ ∅:
        order T by seniority per θ.seniority_order   # default: junior-first
                                                     # (ascending company seniority),
                                                     # configurable to senior-first
        apply fairness guard: skip crew already drafted ≥ θ.max_drafts_per_crew_month
        return first remaining candidate
return None   # → item stays open → possible cancellation at deadline
```
- `status_tier` is computed from the crew's ScheduleBlock calendar over the pairing window — again fully deterministic and auditable.
- Draft cost booked = `c_base_draft + c_tier{k} + premium_pay(duty) + positioning costs (deadhead/hotel if any)`; cascade costs are booked later by the cascade chain itself, so no double counting.
- Fairness KPI: per-crew draft counts, max and Gini concentration, reported per policy.

## 5.7 Cascade Evaluation Engine (emergent)

Consumes the `StateDelta` of every draft:
1. **Future-pairing cascade:** if the drafted crew held pairing P starting later in the horizon and the draft (duty + L2 rest + L3/L4 accumulation) makes P illegal or overlapping → remove P → new `OpenTimeItem(P)` inserted into the SimPy queue at the correct future time → recovery pipeline will re-fire (multi-level cascades arise naturally, depth-limited only by the horizon).
2. **Future-reserve cascade:** if the drafted crew held a future RESERVE block now illegal/consumed → reserve pool at that (base, day) is decremented → future eligibility shrinks structurally.
3. **Legality-shift effects:** rest pushes and rolling-limit consumption are recomputed by the Crew State Engine; blocks that become illegal are surfaced as deltas.
- Realized cascade frequency (share of drafts producing ≥1 downstream OpenTimeItem or reserve loss) is logged — **validation gate: consistent with historical ≈20%**.
- REDUCED mode: Bernoulli(`p_cascade`, default 0.20) spawning a synthetic future OpenTimeItem — screening only.

## 5.8 Cost Engine

Event-sourced ledger; every row: `(scenario_id, policy_id, sim_time, event_uid, crew_id, category, amount)`. Categories and default composition:

| Category | Booked when | Calibration source |
|---|---|---|
| `RESERVE_STAFFING` | per reserve-day held (Stage-1 driven, deterministic per policy) | pay registers: reserve guarantee |
| `RESERVE_UTILIZATION` | reserve converted to duty (marginal pay delta) | pay rules |
| `DRAFT_BASE` + `DRAFT_TIER{k}` | DRAFT_EXECUTED | CBA premium (e.g., 150–200%) + tier coefficients validated by Finance |
| `TRAIN_RESCHEDULE` | Tier-3 draft | training dept. cost estimates |
| `DEADHEAD`, `HOTEL`, `TRANSPORT` | positioning events | historical invoices / per-diem tables |
| `DELAY` | delay minutes on covered flights | $/min delay (CIRIUM/A4A-style figure or internal) |
| `CANCELLATION` + `PAX_COMPENSATION` | UNCOVERED_DEADLINE | internal cancellation cost + APPR compensation schedule |
| `TERMINAL_PENALTY` | horizon end, residual uncovered state | calibrated flat charge |

**Design rule:** only *hard, auditable* costs enter the objective. Soft impacts (morale, fairness) are KPIs/constraints, never invented $ weights. All coefficients live in `costs.yaml` with a version hash recorded in every run's metadata.

## 5.9 Policy Object & Evaluation Loop

```yaml
# configs/policies/example_policy.yaml
policy_id: R14-juniorfirst-v3
stage1:
  reserves:                    # Stage-1 decision vector
    - {base: YUL, fleet: A321, position: FO, dow: [1,2,3,4,5], short_call: 4, long_call: 2}
    - {base: YUL, fleet: A321, position: FO, dow: [6,7],       short_call: 5, long_call: 2}
stage2:
  seniority_order: junior_first
  respect_protected: true
  max_drafts_per_crew_month: 2
  allow_cross_base_reserve: true
  reserve_selection: shortest_remaining_window
mode: FULL
```
Evaluation: `evaluate(policy, scenario_set) -> PolicyResult{E[C], CVaR95, per-category means, service KPIs, validation stats}` — one SimPy environment per scenario, parallelized with joblib (MVP: `n_jobs=-1`, ~500–2,000 scenarios; a 28-day, 300-crew, single-fleet scenario runs in the low hundreds of milliseconds, so a full policy evaluation is minutes on a workstation).


---

# 6. Detailed Data Requirements

## 6.1 Source Extracts (from crew tracking / ops systems)

| # | Dataset | Grain | Required fields | Used for | Min history |
|---|---|---|---|---|---|
| D1 | **Crew master** | crew member | crew_id (pseudonymized), base, position, fleet qualifications + validity dates, seniority number, employment status, hire/termination dates | Crew State Engine population; seniority ordering | current + 24 mo changes |
| D2 | **Published rosters** | crew × block | crew_id, block type (pairing / reserve / off / vacation / training / sim / other), start/end datetimes (UTC + local), pairing_id, protected flag if available | Initial state per scenario; status-tier computation; reserve supply | 24–36 mo |
| D3 | **Pairing definitions** | pairing × duty × leg | pairing_id, base, fleet, position complement, duty periods (report/release), legs (flight, dep/arr stations & times), credit hours, layover stations | OpenTimeItem construction; legality surrogate inputs | 24–36 mo |
| D4 | **Sick-call / absence log** | absence event | crew_id, notification timestamp, absence start/end, absence type code, affected pairing_id(s), base, fleet, category | NHPP fitting (covariates: season, DOW, base, fleet, category); duration distribution | **36 mo minimum** (need ≥3 seasonal cycles) |
| D5 | **Reserve utilization log** | call-out event | reserve crew_id, call timestamp, report time, assigned pairing_id, outcome (assigned / released / no-show) | Notification-time distributions; historical eligibility-rate target (≈30%) reconstruction; reserve productivity baseline | 24 mo |
| D6 | **Schedule-change / reassignment log** | change event | crew_id, change timestamp, old block, new block, change reason code (if any), initiator (system/planner/IOC) | **Draft-event reconstruction** (see 6.3); cascade-rate target (≈20%) reconstruction | 24–36 mo |
| D7 | **Pay register / premium codes** | pay item | crew_id, pay period, pay code, hours/amount, linked duty date | Draft identification (premium codes), cost coefficient calibration (draft premium, reserve guarantee, overtime) | 24 mo |
| D8 | **OTP / flight-movement data** | flight leg | flight, date, sched vs. actual times, delay codes (IATA), cancellation flag & reason | Delay process fitting; regime-model fitting; cancellation cost frequency | 36 mo |
| D9 | **Weather / IROPS day labels** | station-day | station, date, disruption class (or derivable from D8 delay-code density) | Severity-regime Markov chain fitting | 36 mo |
| D10 | **Hotel / deadhead / transport invoices** (or per-diem tables) | booking | date, station, cost, linked crew/pairing | Positioning cost coefficients | 12–24 mo |
| D11 | **Training & simulator schedule** | session | crew_id, session type, start/end, requal deadline, protected flag | Tier-3/5 classification; reschedule cost logic | 12–24 mo |
| D12 | **Collective agreement cost rules** (document, not data) | — | draft premium %, reserve guarantees, min-day rules, protected-block definitions | costs.yaml calibration; L9/protected flags | current CBA |

## 6.2 Quality & Governance Requirements

- **Pseudonymization at ingestion.** crew_id → surrogate key; no names/employee numbers in the analytics corpus. Seniority retained as ordinal rank only. (Loi 25-consistent: purpose-limited, de-identified analytical use; union governance briefing recommended before Phase 1 results circulate.)
- **Timezone discipline:** all timestamps stored UTC + station local; legality surrogate operates on local report times.
- **Completeness thresholds (Phase 0 gate):** D4 ≥95% of absences linkable to a roster block; D6/D7 join must recover ≥80% of suspected draft events (below that, the draft-frequency validation target is downgraded to "indicative").
- **Versioned parameter store:** every calibration run emits `params_vX.json` (distribution families, fitted coefficients, fit diagnostics, data window) referenced by hash in every simulation run's metadata → full reproducibility chain: data → params → scenarios → policy → results.
- **Drift monitoring (Phase 3):** monthly refit; alert when sick-call intensity or regime transition matrix shifts beyond tolerance.

## 6.3 Derived Datasets (Phase 0 engineering)

1. **Draft-event table (reconstructed).** Crew tracking systems rarely code drafts explicitly. Reconstruction: join D6 schedule changes (IOC-initiated, short-notice insert of duty over a non-duty block) × D7 premium pay codes on (crew_id, duty date). Output: draft timestamp, drafted crew, prior status (→ empirical tier distribution), covering pairing.
2. **Eligibility-rate table.** For each historical sick call in D4: reconstruct the reserve pool on-call at that time from D2, apply surrogate rules L1–L8 → historical eligible fraction. This produces the ≈30% *distribution* (not point estimate) that FULL-mode simulation must reproduce.
3. **Cascade table.** For each reconstructed draft: scan the drafted crew's next 7 days in D6 for follow-on IOC-initiated changes / uncovered pairings → historical cascade frequency ≈20% target with confidence interval.
4. **Daily severity labels.** Cluster station-days by (delay-code density, cancellation count, sick-call count) → 4-state labeling → fit Markov transition matrix per season.

---

# 7. Formal Two-Stage Stochastic Program

## 7.1 Sets and Indices
- $b \in \mathcal{B}$: crew bases; $f \in \mathcal{F}$: fleets; $p \in \mathcal{P}$: positions (CA, FO, …); $d \in \mathcal{D}$: days of the planning horizon; $k \in \{1,\dots,5\}$: draft impact tiers
- $\omega \in \Omega$: scenarios (realizations of all disruption streams), with probability measure $\mathbb{P}$; in practice a CRN sample $\hat\Omega = \{\omega_1,\dots,\omega_N\}$
- $c \in \mathcal{C}$: crew members; $o \in \mathcal{O}(\omega)$: open-time items realized in scenario $\omega$

## 7.2 First-Stage Decision (here-and-now)
Before the month begins, the airline commits to a fixed number of standby reserves.
$$
R = \big(R^{SC}_{b,f,p,d},\; R^{LC}_{b,f,p,d}\big) \in \mathbb{Z}_{\ge 0}^{\,|\mathcal{B}||\mathcal{F}||\mathcal{P}||\mathcal{D}| \times 2}
$$
the number of short-call and long-call reserves held per base, fleet, position, day. First-stage cost is deterministic (guaranteed):
$$
C_1(R) \;=\; \sum_{b,f,p,d} \Big( \kappa^{SC}\, R^{SC}_{b,f,p,d} + \kappa^{LC}\, R^{LC}_{b,f,p,d} \Big)
$$
with $\kappa^{SC}, \kappa^{LC}$ the daily reserve guarantee costs.

**Explanation:** "The upfront cost of our standby plan ($C_1$) is calculated by adding up ($\Sigma$) the daily paychecks ($\kappa$) of every single Short-Call ($SC$) and Long-Call ($LC$) reserve worker ($R$) we hired across all bases, fleets, positions, and days."

#### Variable Details:
*   $\kappa^{SC}$ / $\kappa^{LC}$: The daily flat rate (price tag) paid to a worker just for being on standby.
    *   **Example 1:** $250 per day for a Short-Call pilot.
    *   **Example 2:** $100 per day for a Long-Call flight attendant.
    *   **Example 3:** $300 per day for a premium holiday standby shift.
*   $R^{SC}$ / $R^{LC}$: The actual headcount of reserves scheduled.
    *   **Example 1:** Scheduling 10 Short-Call reserves.
    *   **Example 2:** Scheduling 5 Long-Call reserves.
    *   **Example 3:** Scheduling 0 reserves for a specific low-demand day.

| Date ($d$) | Call Type | Headcount ($R$) | Daily Pay Rate ($\kappa$) | Subtotal |
| :--- | :--- | :--- | :--- | :--- |
| Nov 24 | `SHORT_CALL` | 10 | $250 | $2,500 |
| Nov 24 | `LONG_CALL` | 5 | $100 | $500 |
| Nov 25 | `SHORT_CALL` | 0 | $250 | $0 |

## 7.3 Second-Stage Recourse (policy-parameterized)
The recourse is not a free optimization per scenario but a **parametric policy** $\pi_\theta$ with
$$
\theta = \big(\text{seniority order},\; \text{respect\_protected} \in \{0,1\},\; m_{\max} \text{ (drafts/crew/month)},\; \text{cross-base flag},\; \text{reserve-selection rule}\big)
$$
Given $(R, \theta)$ and scenario $\omega$, the simulation induces a state trajectory $s_t(\omega; R, \theta)$ and recourse actions: for each $o \in \mathcal{O}(\omega)$,
$$
a(o) \;=\; \pi_\theta\big(o,\, s_{t(o)}\big) \;\in\; \{\text{assign } r \in E(o, s),\; \text{draft } c \in T_k(o,s),\; \text{hold}\}
$$
where $E(o,s)$ is the **emergent eligible-reserve set** (L1–L8 applied to current state — this is where the ≈30% arises endogenously) and $T_k(o,s)$ the tier-$k$ draft candidate set (§5.6), searched in tier order $k = 1 \to 5$, ordered within tier by seniority, subject to the fairness guard $n_c(\text{month}) < m_{\max}$ and the protected-block constraint.

**Recourse cost** for scenario $\omega$:
$$
Q(R,\theta;\omega) = \sum_{o \in \mathcal{O}(\omega)} \Big[
\underbrace{\mathbb{1}^{res}_o\, q^{res}_o}_{\text{reserve use}}
+ \underbrace{\mathbb{1}^{drf}_o \big( q^{base} + q^{tier}_{k(o)} + q^{pos}_o \big)}_{\text{tiered draft}}
+ \underbrace{\mathbb{1}^{cnl}_o\, \big(q^{cnl} + q^{comp}_o\big)}_{\text{cancellation}}
\Big]
+ \sum_{e \in \mathcal{K}(\omega)} q^{casc}_e
+ q^{dly}(\omega)
+ V\big(s_T(\omega)\big)
$$
where $\mathcal{K}(\omega)$ is the set of **emergent cascade events** — each cascade re-enters $\mathcal{O}(\omega)$, so $Q$ is defined recursively through the event dynamics (evaluated by the DES, not in closed form) — and $V(s_T)$ is the terminal state-value penalty on residual uncovered demand.

**Explanation:** "The total cost of today's chaos ($Q$) equals: the cost of using standby workers, PLUS the penalties for drafting off-duty workers, PLUS the cost of canceling flights, PLUS the domino-effect of ruined future flights, PLUS delay fees, PLUS a penalty for any flights we gave up on."

Here is the breakdown of every variable in this equation:

#### 1. Reserve Costs: $\mathbb{1}^{res}_o\, q^{res}_o$
*   $\mathbb{1}^{res}_o$ is a switch (1 if a reserve was used, 0 if not).
*   $q^{res}_o$ is the marginal pay delta for utilizing that reserve.
    *   **Example 1:** Standby pilot activated (Switch = 1, Cost = $150).
    *   **Example 2:** Standby FA activated (Switch = 1, Cost = $75).
    *   **Example 3:** No standby available, skipped to drafting (Switch = 0, Cost = $0).

| Open Item ($o$) | Reserve Used? ($\mathbb{1}^{res}$) | Utilization Cost ($q^{res}$) | Math Output |
| :--- | :--- | :--- | :--- |
| O-991 | 1 (Yes) | $150 | $150 |
| O-992 | 1 (Yes) | $75 | $75 |
| O-993 | 0 (No) | $150 | $0 |

#### 2. Drafting Costs: $\mathbb{1}^{drf}_o \big( q^{base} + q^{tier}_{k(o)} + q^{pos}_o \big)$
*   $\mathbb{1}^{drf}_o$ is a switch (1 if a draft occurred, 0 if not).
*   $q^{base}$ is the standard draft premium pay.
*   $q^{tier}_{k(o)}$ is the massive penalty based on the impact tier of the drafted crew (e.g., ruining a day off vs. ruining a vacation).
*   $q^{pos}_o$ covers positioning costs (deadhead flights, hotels).
    *   **Example 1:** Drafted off the couch (Base $500 + Tier 1 $0 + Hotel $0).
    *   **Example 2:** Drafted from training (Base $500 + Tier 3 $900 + Hotel $0).
    *   **Example 3:** Drafted out of town (Base $500 + Tier 1 $0 + Hotel $200).

| Draft Occurred? ($\mathbb{1}^{drf}$) | Base Prem ($q^{base}$) | Tier Penalty ($q^{tier}$) | Positioning ($q^{pos}$) | Math Output |
| :--- | :--- | :--- | :--- | :--- |
| 1 (Yes) | $500 | $0 (Tier 1) | $0 | $500 |
| 1 (Yes) | $500 | $900 (Tier 3) | $0 | $1,400 |
| 1 (Yes) | $500 | $0 (Tier 1) | $200 | $700 |

#### 3. Cancellation Costs: $\mathbb{1}^{cnl}_o\, \big(q^{cnl} + q^{comp}_o\big)$
*   $\mathbb{1}^{cnl}_o$ is a switch (1 if the flight was canceled, 0 if not).
*   $q^{cnl}$ is the internal baseline cancellation cost.
*   $q^{comp}_o$ is passenger compensation payouts.
    *   **Example 1:** Full cancel, no passengers booked (Base $25k + Comp $0).
    *   **Example 2:** Cancel with heavy passenger loads (Base $25k + Comp $10k).
    *   **Example 3:** Flight was saved, not canceled (Switch = 0).

| Canceled? ($\mathbb{1}^{cnl}$) | Base Cost ($q^{cnl}$) | Pax Comp ($q^{comp}$) | Math Output |
| :--- | :--- | :--- | :--- |
| 1 (Yes) | $25,000 | $0 | $25,000 |
| 1 (Yes) | $25,000 | $10,000 | $35,000 |
| 0 (No) | $25,000 | $10,000 | $0 |

#### 4. Cascade Costs: $q^{casc}_e$
The downstream cost of emergent cascade events (e.g., drafting a pilot today means they are legally required to sleep tomorrow, ruining tomorrow's schedule).
*   **Example 1:** Ruined tomorrow's pairing, causing a new $5,000 scramble.
*   **Example 2:** Consumed a future reserve block, shrinking tomorrow's pool (Cost $1,000).
*   **Example 3:** The draft had no future cascade effects (Cost $0).

| Cascade Event ($e$) | Description of Downstream Damage | Cascade Cost ($q^{casc}$) |
| :--- | :--- | :--- |
| E-201 | Future pairing P-55 became illegal | $5,000 |
| E-202 | Future reserve block was consumed | $1,000 |
| N/A | No cascade occurred | $0 |

#### 5. Delay Costs & Terminal Penalty: $q^{dly}(\omega)$ and $V\big(s_T(\omega)\big)$
*   $q^{dly}$ tracks standard delay minutes on covered flights.
*   $V(s_T)$ is an artificial penalty charged if the system reaches the end of the simulation horizon with unresolved open flights (preventing the AI from cheating by just ignoring problems).
    *   **Example 1:** 10 minutes of delays ($500) and 0 unresolved flights at end of sim ($0).
    *   **Example 2:** 60 minutes of delays ($3000) and 1 unresolved flight at end of sim ($50,000 penalty).
    *   **Example 3:** 0 delays ($0) and 2 unresolved flights ($100,000 penalty).

| Delay Cost ($q^{dly}$) | Unresolved Flights at Horizon End | Terminal Penalty ($V$) |
| :--- | :--- | :--- |
| $500 | 0 | $0 |
| $3,000 | 1 | $50,000 |
| $0 | 2 | $100,000 |

## 7.4 The Optimization Problem
$$
\min_{R \in \mathcal{R},\, \theta \in \Theta} \;\;
C_1(R) \;+\; \mathbb{E}_\omega\big[Q(R,\theta;\omega)\big]
\;+\; \lambda \,\mathrm{CVaR}_{0.95}\big[Q(R,\theta;\omega)\big]
$$

**Explanation:** "Find the strategy with the lowest possible total cost ($\min$). To calculate that, add our guaranteed upfront costs ($C_1$), PLUS the average cost of a normal day ($\mathbb{E}$), PLUS a special safety cushion for the absolute worst 5% of days ($\mathrm{CVaR}$)."

#### 1. $\mathbb{E}_\omega$: Expected Value
The mathematical average of the daily chaos cost across thousands of simulated scenarios.
*   **Example 1:** The average cost of a standard, calm Tuesday.
*   **Example 2:** The average cost of a day with light spring rain.
*   **Example 3:** The average cost across all 1,000 simulated days combined.

| Scenario Type | Frequency in Simulation | Average Daily Cost ($\mathbb{E}$) |
| :--- | :--- | :--- |
| `CALM` Regime | 70% of days | $45,000 |
| `NORMAL` Regime | 25% of days | $85,000 |
| All Scenarios | 100% aggregate | $150,000 |

#### 2. $\lambda$: Lambda (The Risk Dial)
A dial that management configures to weight how heavily the system should guard against tail-risk (disasters). 
*   **Example 1:** $\lambda = 0.0$ (Ignore worst-case scenarios, optimize only for cheap average days).
*   **Example 2:** $\lambda = 0.5$ (Balanced approach).
*   **Example 3:** $\lambda = 1.0$ (High risk-aversion, over-staff to ensure the airline survives severe blizzards).

| Risk Setting ($\lambda$) | Management Focus | Expected Optimizer Result |
| :--- | :--- | :--- |
| 0.0 | Lowest possible baseline cost | Recommends minimal reserves |
| 0.5 | Balanced cost and safety | Recommends moderate reserves |
| 1.0 | Absolute operational stability | Recommends maximum reserves |

#### 3. $\mathrm{CVaR}_{0.95}$: Conditional Value at Risk
This isolates the absolute worst 5% of scenarios to ensure the airline survives extreme events.
*   **Example 1:** The average cost of the worst 5 blizzards of the year.
*   **Example 2:** The average cost of days experiencing a major IT network outage.
*   **Example 3:** The average cost of the worst holiday travel weekend meltdowns.

| Metric | Focus Area | Simulated Example Value |
| :--- | :--- | :--- |
| Normal Average ($\mathbb{E}$) | All 1,000 simulated days | $150,000 / day |
| $\mathrm{CVaR}_{0.95}$ (Top 5%) | The 50 worst blizzards | $850,000 / day |
| $\mathrm{CVaR}_{0.99}$ (Top 1%) | The 10 worst disasters | $1,200,000 / day |

subject to:
$$
\begin{aligned}
&\text{(Service level)} && \mathbb{P}\big(\text{UncoveredLegs}(\omega; R,\theta) > u_{\max}\big) \;\le\; \varepsilon \\
&\text{(Protected blocks)} && \text{no draft from blocks with } protected=1 \text{ when } \theta.\text{respect\_protected}=1 \quad \text{(hard, enforced in-policy)}\\
&\text{(Fairness)} && \max_{c \in \mathcal{C}} \; \mathbb{E}\big[n_c^{drafts}/\text{month}\big] \;\le\; m_{\max} \\
&\text{(Legality)} && \text{every assignment satisfies surrogate rules L1–L8 (enforced in-simulation, by construction)} \\
&\text{(Budget/headcount)} && \textstyle\sum_{f,p,d} R^{\cdot}_{b,f,p,d} \le H_b \;\; \forall b
\end{aligned}
$$
Sample-average approximation over the CRN set $\hat\Omega$:
$$
\widehat{J}(R,\theta) = C_1(R) + \frac{1}{N}\sum_{i=1}^{N} Q(R,\theta;\omega_i) + \lambda\, \widehat{\mathrm{CVaR}}_{0.95}
, \qquad
\widehat{\mathrm{CVaR}}_{0.95} = \frac{1}{\lceil 0.05N \rceil} \sum_{i \in \text{worst } 5\%} Q(R,\theta;\omega_i)
$$
**CRN property exploited by the optimizer:** for two candidates $(R,\theta)$ and $(R',\theta')$, $\widehat{J} - \widehat{J}'$ is a paired-sample mean over identical $\omega_i$, so $\mathrm{Var}[\widehat{J}-\widehat{J}'] \ll \mathrm{Var}[\widehat{J}] + \mathrm{Var}[\widehat{J}']$. Phase-2 search: Bayesian optimization (GP/TPE) over the integer lattice of $R$ (relaxed-and-rounded), crossed with ranking-and-selection (e.g., OCBA) over the small discrete set $\Theta$, with interaction terms retained (optimal drafting aggressiveness depends on $R$). MVP: exhaustive comparison of a hand-picked candidate list.

**Remarks for the academic track.** (i) Because eligibility and cascades are emergent, $Q$ has no closed form and is evaluated by simulation — the problem is a simulation-optimization / stochastic program with recourse-by-policy, positioned between classical reserve-sizing newsvendor models and full dynamic-programming crew recovery. (ii) The Erlang-loss sanity bound: treating reserves as $s$ servers and eligibility-thinned sick calls as Poisson arrivals gives $\mathbb{P}(\text{shortfall}) \approx B(s, \lambda_{\text{eff}}/\mu)$; FULL-mode results must be consistent with this in the no-cascade, single-base regime (a required verification test).


---

# 8. SimPy DES Skeleton with CRN Architecture

The complete runnable skeleton is delivered as `crewsim_skeleton.py` (companion file, smoke-tested: `python crewsim_skeleton.py`). It is production-*shaped* — the interfaces, CRN discipline, engine separation, and evaluation loop are the ones the full system keeps — with deliberately simplified domain logic (surrogate rules L1/L2/L6/L7, synthetic roster builder).

**Illustrative output from the smoke test (synthetic data, 100 CRN scenarios, 28-day horizon):**

```
     R6-junior-first  E[C]=180,464  CVaR95=377,040  cascade=0.12  uncovered=6.3
    R10-junior-first  E[C]=160,528  CVaR95=355,340  cascade=0.10  uncovered=5.2

Paired CRN diff (A-B): 19,935 ± 8,455 (95% CI), t=4.6
```

Note what CRN delivers: with only 100 scenarios, the *paired* cost difference between the two policies is estimated with a ±8.5k confidence interval on a ~180k mean — a naive unpaired comparison at the same sample size would be statistically inconclusive (per-policy std is on the order of the mean). Cascade rate emerges at 10–12% from the synthetic roster; Phase-0 calibration tunes roster composition and rest rules until the emergent rate matches the historical ≈20% band.

Full source:

```python
"""
crewsim_skeleton.py
===================
SimPy DES core skeleton for the Crew Reserve & Drafting Policy Simulation,
with Common Random Numbers (CRN) scenario architecture built in.

MVP-fidelity skeleton: interfaces and control flow are production-shaped;
domain logic is deliberately simplified (legality surrogate rules L1/L2/L6/L7,
tiered draft selection, emergent cascades). Extend, don't rewrite.

Run:  python crewsim_skeleton.py
Deps: simpy>=4.1, numpy>=1.26
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field, replace
from enum import Enum, auto
from typing import Optional

import numpy as np
import simpy

MIN_PER_DAY = 1440.0

# ----------------------------------------------------------------------------
# 1. CRN SCENARIO ARCHITECTURE
# ----------------------------------------------------------------------------
# Master seed -> SeedSequence.spawn(N) -> one child per scenario.
# Each scenario child spawns NAMED streams. Policy-dependent draws use
# per-event derived generators so random-number alignment across policies
# is preserved (the heart of CRN).

STREAMS = ("severity", "sick_calls", "delays", "recovery", "tiebreak")


class ScenarioRNG:
    """Named, isolated RNG streams for one scenario (CRN discipline)."""

    def __init__(self, scenario_seed: np.random.SeedSequence):
        self._entropy = scenario_seed.entropy
        children = scenario_seed.spawn(len(STREAMS))
        self.streams = {name: np.random.default_rng(ss)
                        for name, ss in zip(STREAMS, children)}

    def stream(self, name: str) -> np.random.Generator:
        return self.streams[name]

    def event_rng(self, stream: str, event_uid: int) -> np.random.Generator:
        """Fresh generator keyed by (scenario, stream, event) -- use for any
        draw whose *call order* depends on policy decisions, so that two
        policies consuming different numbers of draws stay aligned."""
        ss = np.random.SeedSequence(
            entropy=[abs(hash((self._entropy, stream, event_uid))) % (2**63)]
        )
        return np.random.default_rng(ss)


def make_scenario_seeds(master_seed: int, n_scenarios: int):
    return np.random.SeedSequence(master_seed).spawn(n_scenarios)


# ----------------------------------------------------------------------------
# 2. DOMAIN MODEL (Crew State Engine)
# ----------------------------------------------------------------------------

class BlockType(Enum):
    PAIRING = auto()
    RESERVE = auto()
    DAY_OFF = auto()
    VACATION = auto()
    TRAINING = auto()
    SIMULATOR = auto()
    DRAFTED_DUTY = auto()
    REST = auto()


# Draft impact tiers (policy: exhaust tier k before tier k+1)
TIER_OF_STATUS = {
    BlockType.DAY_OFF: 1,        # no duty -> least disruptive
    BlockType.PAIRING: 2,        # has a pairing -> cascade candidate
    BlockType.TRAINING: 3,
    BlockType.VACATION: 4,
    BlockType.SIMULATOR: 5,
}
PROTECTED_DEFAULT = {BlockType.VACATION, BlockType.SIMULATOR}


@dataclass(frozen=True)
class Block:
    start: float                 # sim minutes
    end: float
    btype: BlockType
    pairing_id: Optional[str] = None
    protected: bool = False


@dataclass
class Crew:
    crew_id: str
    base: str
    fleet: str
    position: str                # "CA" / "FO"
    seniority: int               # 1 = most senior
    blocks: list[Block] = field(default_factory=list)   # sorted by start
    drafts_this_month: int = 0

    # -- calendar queries ---------------------------------------------------
    def block_at(self, t: float) -> Optional[Block]:
        i = bisect.bisect_right([b.start for b in self.blocks], t) - 1
        if i >= 0 and self.blocks[i].start <= t < self.blocks[i].end:
            return self.blocks[i]
        return None

    def blocks_in(self, start: float, end: float) -> list[Block]:
        return [b for b in self.blocks if b.start < end and b.end > start]

    def status_tier(self, start: float, end: float) -> int:
        """Impact tier over a window = worst tier of any overlapping block;
        empty window -> tier 1 (no duty)."""
        overlapping = self.blocks_in(start, end)
        if not overlapping:
            return 1
        return max(TIER_OF_STATUS.get(b.btype, 2) for b in overlapping)

    def is_protected_in(self, start: float, end: float) -> bool:
        return any(b.protected for b in self.blocks_in(start, end))

    # -- atomic mutations (all state changes go through these) ---------------
    def remove_block(self, block: Block) -> "StateDelta":
        self.blocks.remove(block)
        return StateDelta(self.crew_id, removed=[block], inserted=[])

    def insert_block(self, block: Block) -> "StateDelta":
        keys = [b.start for b in self.blocks]
        self.blocks.insert(bisect.bisect_left(keys, block.start), block)
        return StateDelta(self.crew_id, removed=[], inserted=[block])


@dataclass
class StateDelta:
    """Audit record of a mutation -- consumed by the Cascade Engine."""
    crew_id: str
    removed: list[Block]
    inserted: list[Block]


@dataclass(frozen=True)
class OpenTimeItem:
    uid: int
    pairing_id: str
    base: str
    fleet: str
    position: str
    start: float                 # report time (sim minutes)
    end: float                   # release time
    deadline: float              # must be covered by this time or cancel
    origin: str = "SICK_CALL"    # or "CASCADE"


# ----------------------------------------------------------------------------
# 3. LEGALITY SURROGATE  (simplified, conservatively biased -- see spec §5.4)
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class LegalityResult:
    legal: bool
    failed_rule: Optional[str] = None


class LegalitySurrogate:
    MAX_DUTY_MIN = 13 * 60          # L1
    MIN_REST_MIN = 11 * 60          # L2 (home-base value, conservative)

    def check(self, crew: Crew, duty_start: float, duty_end: float,
              o: OpenTimeItem) -> LegalityResult:
        if duty_end - duty_start > self.MAX_DUTY_MIN:                 # L1
            return LegalityResult(False, "L1_max_duty")
        # L2: min rest before duty vs. previous duty-type block
        prev = [b for b in crew.blocks
                if b.end <= duty_start
                and b.btype in (BlockType.PAIRING, BlockType.DRAFTED_DUTY)]
        if prev and duty_start - max(b.end for b in prev) < self.MIN_REST_MIN:
            return LegalityResult(False, "L2_min_rest")
        if crew.fleet != o.fleet or crew.position != o.position:      # L6
            return LegalityResult(False, "L6_qualification")
        if crew.base != o.base:                                       # L7 (MVP: no cross-base)
            return LegalityResult(False, "L7_base")
        # L3/L4/L5/L8 omitted in skeleton -- same pattern, add here.
        return LegalityResult(True)


# ----------------------------------------------------------------------------
# 4. POLICY OBJECT  (serializable candidate: Stage-1 vector + Stage-2 params)
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Policy:
    policy_id: str
    n_reserves: int                     # Stage-1 (skeleton: single base/fleet/pos)
    seniority_order: str = "junior_first"   # or "senior_first"
    respect_protected: bool = True
    max_drafts_per_crew_month: int = 2
    # Stage-2 tier cost coefficients (hard costs; see costs.yaml in full system)
    tier_cost: tuple = (0., 300., 900., 2500., 4000., 6000.)  # index by tier 1..5
    base_draft_cost: float = 500.0
    reserve_day_cost: float = 250.0     # kappa (reserve guarantee per day)
    cancel_cost: float = 25000.0


# ----------------------------------------------------------------------------
# 5. ENGINES: eligibility, draft selection, cascade, cost ledger
# ----------------------------------------------------------------------------

class CostLedger:
    def __init__(self):
        self.rows: list[tuple] = []   # (sim_time, event_uid, crew_id, category, amount)

    def book(self, t, uid, crew_id, category, amount):
        self.rows.append((t, uid, crew_id, category, float(amount)))

    def total(self, warmup_end: float = 0.0) -> float:
        return sum(a for (t, *_, a) in self.rows if t >= warmup_end)


class EligibilityEngine:
    """FULL mode: eligibility is EMERGENT from state + surrogate rules.
    The realized eligible fraction is logged for validation vs. ~30%."""

    def __init__(self, legality: LegalitySurrogate):
        self.legality = legality
        self.samples: list[float] = []   # realized eligibility fractions

    def eligible_reserves(self, reserves_on_call: list[Crew],
                          o: OpenTimeItem, now: float) -> list[Crew]:
        pool = [r for r in reserves_on_call]
        elig = [r for r in pool
                if self.legality.check(r, o.start, o.end, o).legal
                and r.block_at(now) is not None
                and r.block_at(now).btype == BlockType.RESERVE]
        if pool:
            self.samples.append(len(elig) / len(pool))
        return elig


class DraftSelector:
    """Tier-first (impact on drafted crew), seniority-within-tier policy."""

    def __init__(self, policy: Policy, legality: LegalitySurrogate):
        self.p = policy
        self.legality = legality

    def select(self, roster: list[Crew], o: OpenTimeItem) -> Optional[Crew]:
        cands = [c for c in roster
                 if self.legality.check(c, o.start, o.end, o).legal
                 and c.drafts_this_month < self.p.max_drafts_per_crew_month]
        by_tier: dict[int, list[Crew]] = {}
        for c in cands:
            if self.p.respect_protected and c.is_protected_in(o.start, o.end):
                continue
            by_tier.setdefault(c.status_tier(o.start, o.end), []).append(c)
        for tier in (1, 2, 3, 4, 5):
            tier_list = by_tier.get(tier, [])
            if tier_list:
                reverse = self.p.seniority_order == "senior_first"
                tier_list.sort(key=lambda c: c.seniority, reverse=reverse)
                # junior_first = highest seniority NUMBER first:
                if self.p.seniority_order == "junior_first":
                    tier_list.sort(key=lambda c: -c.seniority)
                return tier_list[0]
        return None


class CascadeEngine:
    """EMERGENT cascades: consume the StateDelta of a draft; any future
    pairing of the drafted crew made overlapping/illegal becomes a new
    OpenTimeItem re-injected into the DES queue. Realized cascade frequency
    is logged for validation vs. ~20%."""

    def __init__(self, legality: LegalitySurrogate):
        self.legality = legality
        self.n_drafts = 0
        self.n_cascading_drafts = 0

    def evaluate(self, crew: Crew, drafted: Block) -> list[Block]:
        self.n_drafts += 1
        broken: list[Block] = []
        for b in list(crew.blocks):
            if b.btype != BlockType.PAIRING or b.start <= drafted.start:
                continue
            overlaps = b.start < drafted.end + LegalitySurrogate.MIN_REST_MIN
            if overlaps:
                crew.remove_block(b)
                broken.append(b)
        if broken:
            self.n_cascading_drafts += 1
        return broken

    @property
    def cascade_rate(self) -> float:
        return self.n_cascading_drafts / self.n_drafts if self.n_drafts else 0.0


# ----------------------------------------------------------------------------
# 6. SIMPY DES CORE
# ----------------------------------------------------------------------------

class IOCSimulation:
    def __init__(self, env: simpy.Environment, scenario: "Scenario",
                 policy: Policy, roster: list[Crew], reserves: list[Crew]):
        self.env = env
        self.scn = scenario
        self.p = policy
        self.roster = roster            # draftable line holders
        self.reserves = reserves        # reserve pool (Stage-1 sized)
        self.legality = LegalitySurrogate()
        self.elig = EligibilityEngine(self.legality)
        self.drafter = DraftSelector(policy, self.legality)
        self.cascade = CascadeEngine(self.legality)
        self.ledger = CostLedger()
        self._uid = 0
        self.uncovered = 0
        # Stage-1 cost: reserve guarantee, booked per reserve-day
        horizon_days = scenario.horizon_min / MIN_PER_DAY
        for r in reserves:
            self.ledger.book(0.0, -1, r.crew_id, "RESERVE_STAFFING",
                             policy.reserve_day_cost * horizon_days)

    def next_uid(self) -> int:
        self._uid += 1
        return self._uid

    # -- processes ------------------------------------------------------------
    def run(self):
        self.env.process(self.sick_call_source())
        self.env.run(until=self.scn.horizon_min)

    def sick_call_source(self):
        """Replays the scenario's pre-generated (CRN) sick-call event list."""
        for t_arrival, pairing in self.scn.sick_calls:
            yield self.env.timeout(max(0.0, t_arrival - self.env.now))
            o = OpenTimeItem(
                uid=self.next_uid(), pairing_id=pairing["id"],
                base=pairing["base"], fleet=pairing["fleet"],
                position=pairing["position"], start=pairing["start"],
                end=pairing["end"],
                deadline=pairing["start"],   # must cover by report time
                origin="SICK_CALL",
            )
            self.recovery_pipeline(o)

    def recovery_pipeline(self, o: OpenTimeItem):
        now = self.env.now
        # 1) try reserves (eligibility is emergent)
        elig = self.elig.eligible_reserves(self.reserves, o, now)
        if elig:
            # reserve-selection rule: shortest remaining on-call window
            elig.sort(key=lambda r: (r.block_at(now).end, r.seniority))
            r = elig[0]
            delta = r.insert_block(Block(o.start, o.end, BlockType.DRAFTED_DUTY,
                                         o.pairing_id))
            self.ledger.book(now, o.uid, r.crew_id, "RESERVE_UTILIZATION", 150.0)
            return
        # 2) draft (tier-first, seniority-within-tier)
        c = self.drafter.select(self.roster, o)
        if c is not None:
            tier = c.status_tier(o.start, o.end)
            duty = Block(o.start, o.end, BlockType.DRAFTED_DUTY, o.pairing_id)
            c.insert_block(duty)
            c.drafts_this_month += 1
            cost = self.p.base_draft_cost + self.p.tier_cost[tier]
            self.ledger.book(now, o.uid, c.crew_id, f"DRAFT_TIER{tier}", cost)
            # 3) emergent cascade: broken future pairings re-enter the queue
            for b in self.cascade.evaluate(c, duty):
                casc = OpenTimeItem(
                    uid=self.next_uid(), pairing_id=b.pairing_id or "casc",
                    base=o.base, fleet=o.fleet, position=o.position,
                    start=b.start, end=b.end, deadline=b.start,
                    origin="CASCADE",
                )
                self.env.process(self._delayed_pipeline(casc))
            return
        # 4) nothing feasible -> cancellation at deadline
        self.uncovered += 1
        self.ledger.book(now, o.uid, None, "CANCELLATION", self.p.cancel_cost)

    def _delayed_pipeline(self, o: OpenTimeItem):
        # cascade disruptions surface when the IOC would see them (MVP: T-24h)
        visible_at = max(self.env.now, o.start - MIN_PER_DAY)
        yield self.env.timeout(visible_at - self.env.now)
        self.recovery_pipeline(o)


# ----------------------------------------------------------------------------
# 7. SCENARIO GENERATION (pre-materialized; identical across policies = CRN)
# ----------------------------------------------------------------------------

@dataclass
class Scenario:
    scenario_id: int
    horizon_min: float
    sick_calls: list[tuple]       # (arrival_time, pairing dict), time-ordered


def generate_scenario(scenario_id: int, seed: np.random.SeedSequence,
                      horizon_days: int = 28, base="YUL", fleet="A321") -> Scenario:
    rng = ScenarioRNG(seed)
    sev = rng.stream("severity")
    sick = rng.stream("sick_calls")
    horizon = horizon_days * MIN_PER_DAY

    # daily severity regime (Markov chain, 4 states -> intensity multiplier)
    P = np.array([[.70, .25, .04, .01],
                  [.20, .60, .15, .05],
                  [.05, .30, .50, .15],
                  [.02, .18, .40, .40]])
    mult = np.array([0.5, 1.0, 2.0, 3.5])
    z = 1
    events = []
    for d in range(horizon_days):
        z = sev.choice(4, p=P[z])
        lam_day = 1.8 * mult[z]                      # calibrated in Phase 0
        n = sick.poisson(lam_day)
        for _ in range(n):
            t = d * MIN_PER_DAY + sick.uniform(0, MIN_PER_DAY)
            report = t + sick.uniform(2 * 60, 10 * 60)     # report 2-10h later
            events.append((t, {
                "id": f"P{scenario_id}-{len(events)}", "base": base,
                "fleet": fleet, "position": "FO",
                "start": report, "end": report + sick.uniform(6, 11) * 60,
            }))
    events.sort(key=lambda e: e[0])
    return Scenario(scenario_id, horizon, events)


def build_roster(seed: np.random.SeedSequence, n_line=120,
                 horizon_days=28) -> list[Crew]:
    """Synthetic line-holder roster (replace with D2 roster loader)."""
    rng = np.random.default_rng(seed)
    roster = []
    for i in range(n_line):
        c = Crew(f"C{i:04d}", "YUL", "A321", "FO", seniority=i + 1)
        t = 0.0
        while t < horizon_days * MIN_PER_DAY:
            btype = rng.choice(
                [BlockType.PAIRING, BlockType.DAY_OFF, BlockType.TRAINING,
                 BlockType.VACATION, BlockType.SIMULATOR],
                p=[.55, .33, .05, .05, .02])
            dur = rng.uniform(1, 4) * MIN_PER_DAY
            c.insert_block(Block(t, min(t + dur, horizon_days * MIN_PER_DAY),
                                 btype, pairing_id=f"L{i}-{int(t)}",
                                 protected=btype in PROTECTED_DEFAULT))
            t += dur
        roster.append(c)
    return roster


def build_reserves(policy: Policy, horizon_days=28) -> list[Crew]:
    res = []
    for i in range(policy.n_reserves):
        r = Crew(f"R{i:03d}", "YUL", "A321", "FO", seniority=1000 + i)
        r.insert_block(Block(0.0, horizon_days * MIN_PER_DAY,
                             BlockType.RESERVE))
        res.append(r)
    return res


# ----------------------------------------------------------------------------
# 8. CRN POLICY EVALUATION LOOP
# ----------------------------------------------------------------------------

def evaluate_policy(policy: Policy, master_seed=20260704, n_scenarios=200,
                    horizon_days=28, warmup_days=7):
    """Evaluate one policy over the CRN scenario set. The SAME master seed
    (hence identical scenarios & rosters) must be used for every policy."""
    seeds = make_scenario_seeds(master_seed, n_scenarios)
    roster_seed = np.random.SeedSequence(master_seed + 1)  # shared across policies
    costs, elig_rates, casc_rates, uncov = [], [], [], []
    for i, s in enumerate(seeds):
        scn = generate_scenario(i, s, horizon_days)
        roster = build_roster(roster_seed, horizon_days=horizon_days)
        reserves = build_reserves(policy, horizon_days)
        sim = IOCSimulation(simpy.Environment(), scn, policy, roster, reserves)
        sim.run()
        costs.append(sim.ledger.total(warmup_end=warmup_days * MIN_PER_DAY))
        if sim.elig.samples:
            elig_rates.append(float(np.mean(sim.elig.samples)))
        casc_rates.append(sim.cascade.cascade_rate)
        uncov.append(sim.uncovered)
    c = np.array(costs)
    k = max(1, int(0.05 * len(c)))
    return {
        "policy_id": policy.policy_id,
        "E[cost]": float(c.mean()),
        "CVaR95": float(np.sort(c)[-k:].mean()),
        "std": float(c.std(ddof=1)),
        "mean_eligibility_rate": float(np.mean(elig_rates)) if elig_rates else None,
        "mean_cascade_rate": float(np.mean(casc_rates)),
        "mean_uncovered": float(np.mean(uncov)),
        "costs": c,   # keep per-scenario vector for paired CRN comparison
    }


def compare_policies_crn(pa: Policy, pb: Policy, **kw):
    """Paired CRN comparison: identical scenarios -> low-variance difference."""
    ra, rb = evaluate_policy(pa, **kw), evaluate_policy(pb, **kw)
    diff = ra["costs"] - rb["costs"]              # PAIRED by scenario
    se = diff.std(ddof=1) / np.sqrt(len(diff))
    return ra, rb, {"mean_diff": float(diff.mean()),
                    "se_paired": float(se),
                    "t_stat": float(diff.mean() / se) if se > 0 else np.inf}


if __name__ == "__main__":
    A = Policy("R6-junior-first", n_reserves=6)
    B = Policy("R10-junior-first", n_reserves=10)
    ra, rb, cmp_ = compare_policies_crn(A, B, n_scenarios=100)
    for r in (ra, rb):
        print(f"{r['policy_id']:>20}  E[C]={r['E[cost]']:>12,.0f}  "
              f"CVaR95={r['CVaR95']:>12,.0f}  elig={r['mean_eligibility_rate']}"
              f"  cascade={r['mean_cascade_rate']:.2f}  "
              f"uncovered={r['mean_uncovered']:.1f}")
    print(f"\nPaired CRN diff (A-B): {cmp_['mean_diff']:,.0f} "
          f"± {1.96*cmp_['se_paired']:,.0f} (95% CI), t={cmp_['t_stat']:.1f}")
```

---

# 9. Verification & Validation Plan (Gate before any planning use)

| Gate | Test | Pass criterion |
|---|---|---|
| V1 | **Degeneracy tests**: 0 reserves / ∞ reserves / 0 sick calls | Costs collapse to analytically predictable values |
| V2 | **Erlang-loss sanity bound**: single base, no cascades, eligibility-thinned Poisson arrivals | DES shortfall probability within CI of Erlang-B formula |
| V3 | **Emergent-eligibility validation** | FULL-mode eligibility-rate distribution consistent with historical ≈30% band (from derived dataset 6.3-2) |
| V4 | **Emergent-cascade validation** | Cascade frequency consistent with historical ≈20% band (6.3-3) |
| V5 | **Trace validation**: replay a real historical disruption week; walk IOC duty managers through the simulated event log hour by hour | SME sign-off that recovery sequencing is plausible |
| V6 | **Cost backtest**: feed actual historical disruption streams | Simulated total recovery cost within tolerance band of actual payroll/invoice cost for the same period |
| V7 | **CRN integrity**: same policy, same master seed, twice | Bit-identical cost ledger |
| V8 | **Legality invariants** (hypothesis property tests) | No inserted duty ever silently violates L1–L2; surrogate bias direction confirmed conservative |

Only after V1–V8 pass does any output inform a bid-period reserve decision. Recommendation reports must always include drill-down links to exemplar scenarios (the 5 costliest and 5 most typical) so planners can audit *why* a reserve level is recommended.

---

# 10. Summary of Key Design Decisions (traceability)

| Decision | Choice | Rationale |
|---|---|---|
| System purpose | Offline policy simulation, **not** real-time decision support | Explicit scope directive; reserve sizing is a planning-timescale problem |
| Starting phase | **MVP** (single fleet/category, grid policy comparison, no optimizer) | Fastest path to a validated end-to-end pipeline |
| Voluntary recovery | **Excluded** | Scope directive; documented as an upper-bound bias on draft frequency, neutral across compared policies |
| Legality | **Surrogate with simplified rules** (L1–L9, conservatively biased) | Scope directive; full rules engine deferred to Phase 3 |
| Draft selection | **Impact tier first (no-duty → pairing → training → vacation/holiday), seniority within tier, per-tier costs** | Stakeholder-specified policy; implemented in §5.6 and `DraftSelector` |
| Eligibility (~30%) & cascades (~20%) | **Emergent from crew state; historical figures are validation targets** (Bernoulli reduced-form kept for screening) | Structural causality is the model's core contribution; avoids the exogenous-parameter contradiction |
| Variance control | **CRN via hierarchical SeedSequence streams** + severity-regime stratification (Phase 2) | Paired policy comparison; demonstrated in skeleton output |
| Objective | E[C] + λ·CVaR₀.₉₅ + service-level chance constraint; hard costs only; protections and fairness as constraints | Tail-risk pricing; no invented soft-cost weights |
| Stack | Python 3.11 / SimPy / NumPy SeedSequence / Polars / Pydantic / Parquet / joblib→Ray / Optuna | §4; aligns with existing AKS + Delta Lake digital-twin architecture |

*End of document.*
