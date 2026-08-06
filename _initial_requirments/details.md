# Crew Reserve & Drafting Policy Optimization System
## Stochastic Simulation for IOC Recovery Policy Design

**Document type:** Technical Specification & Implementation Plan
**Version:** 2.0 (Enriched Educational Edition)
**Status:** Draft for review
**Scope note:** This system is an **offline policy-simulation and optimization tool**. It is *not* a real-time decision-support system. Its outputs inform monthly/bid-period reserve planning and drafting-policy design, not day-of-operation recovery actions.

---

# 1. Problem Statement

## 1.1 Operational Context

An airline Integrated Operations Center (IOC) continuously manages crew disruptions caused by sick calls, delays, irregular operations (IROPS), maintenance events, and weather. A central, recurring decision is the balance between:

*   **Reserve crews** — crew members paid to be on standby (long-call or short-call). Reserves that go unused are pure staffing cost; reserves that are used are the cheapest recovery instrument.
*   **Drafting** — involuntarily assigning a crew member who was not on reserve (from a day off, a future pairing, training, or vacation) to cover an open flying assignment. Drafting cost is **not fixed**: it depends on the operational status of the drafted crew member at the moment of drafting, and it may create **cascading disruptions** in the future schedule.

Too many reserves → high fixed staffing cost, low utilization.
Too few reserves → frequent drafting → high variable cost, employee-relations damage, and downstream schedule instability.

## 1.2 Decision Problem

> **Determine the reserve staffing level (by base, fleet, crew category, and day-of-week) and the drafting policy parameters that minimize the airline's total expected operational recovery cost over a planning horizon, while maintaining service levels and regulatory compliance.**

This is a **two-stage stochastic optimization problem**:

*   **Stage 1 (here-and-now, bid-period timescale):** the reserve vector — how many reserves, of which category, at which base, on which days.
*   **Stage 2 (recourse, day-of-operation timescale):** the drafting policy — given a realized disruption stream and the current crew state, which recovery action is taken (assign eligible reserve, or draft according to the priority/cost rules defined in §5.6).

## 1.3 Key Modeling Principles

The following principles correct known weaknesses of naive reserve-sizing models:

1.  **Eligibility is emergent, not exogenous.** When a sick call occurs, only a subset of reserves can legally and practically cover it. Historically ≈30% of reserves are eligible for a given sick call. In this model, the 30% figure is a **calibration/validation target**, not an input: eligibility is computed per-event from the Crew State Engine.
2.  **Cascades are emergent, not exogenous.** Drafting Crew A may uncover A's future pairing or destroy A's future reserve block. Whether this happens is a deterministic consequence of A's schedule.
3.  **Drafting cost is state-dependent.** Each draft's cost is computed from the drafted crew member's status at draft time.
4.  **Correlated disruption streams.** Sick calls, weather disruptions, and delays are *not* independent.
5.  **Hard costs vs. hard constraints.** Monetizable costs enter the objective. Contractually prohibited actions are hard constraints.
6.  **Common Random Numbers (CRN).** All candidate policies are evaluated against the *same* pre-seeded scenario set to dramatically reduce variance.

---

# 5. Detailed Implementation Description & Mathematical State

## 5.0 Formal DES Specification — The Five-Component Framework

Following the standard five-component tracking framework for discrete event simulation, this section specifies the crew recovery simulation formally. 

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

---

# 7. Formal Two-Stage Stochastic Program

This section defines the mathematical formulas used by the optimization engine to evaluate and score different airline management strategies. 

## 7.2 First-Stage Decision (The "Upfront Bill")

Before the month begins, the airline commits to a fixed number of standby reserves. This cost is deterministic (guaranteed).

$$C_1(R) \;=\; \sum_{b,f,p,d} \Big( \kappa^{SC}\, R^{SC}_{b,f,p,d} + \kappa^{LC}\, R^{LC}_{b,f,p,d} \Big)$$

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

## 7.3 Second-Stage Recourse (The "Disaster Receipt")

This formula acts as an itemized receipt for a specific simulated day of operation. It adds up every action taken to fix the emergencies that occurred.

$$Q(R,\theta;\omega) = \sum_{o \in \mathcal{O}(\omega)} \Big[ \mathbb{1}^{res}_o\, q^{res}_o + \mathbb{1}^{drf}_o \big( q^{base} + q^{tier}_{k(o)} + q^{pos}_o \big) + \mathbb{1}^{cnl}_o\, \big(q^{cnl} + q^{comp}_o\big) \Big] + \sum_{e \in \mathcal{K}(\omega)} q^{casc}_e + q^{dly}(\omega) + V\big(s_T(\omega)\big)$$

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

## 7.4 The Optimization Problem (The "Holy Grail" Equation)

This is the ultimate command given to the optimization engine to find the best policy.

$$\min_{R \in \mathcal{R},\, \theta \in \Theta} \;\; C_1(R) \;+\; \mathbb{E}_\omega\big[Q(R,\theta;\omega)\big] \;+\; \lambda \,\mathrm{CVaR}_{0.95}\big[Q(R,\theta;\omega)\big]$$

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
