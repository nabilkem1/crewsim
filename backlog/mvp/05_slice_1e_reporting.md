# Slice 1e — Reporting, Policy Grid & Backtest

**Epic E1e** · 7 stories · Gate: **V5 SME sign-off · V6 cost backtest**
Needs datasets **D7, D10**.

The slice that turns a validated model into something a planner can act on. Two of its stories are
gates that require humans: an IOC duty manager (V5) and Finance's actual payroll figures (V6).

---

## ⏳ [TODO] S1e-01 — KPI aggregation over the measurement window
**Size:** `M` | **Depends on:** S1d-05 | **Spec:** §2.1, §5.0.5

**As a** planner **I want** KPIs aggregated accurately over the measurement window

### Description
The first 7 days of the simulation are noisy as the engine spins up. Throwing out this warm-up period ensures the final financial KPIs are perfectly stable and trustworthy.
**so that** warm-up noise is excluded and metrics are comparable.

### Acceptance Criteria
- [ ] E[C], CVaR₀.₉₅, uncovered legs, reserve utilisation, eligibility, cascade rate, draft distribution
- [ ] **Warm-up rows booked but excluded**; cool-down costs attributed back when their cause is in-window
- [ ] Draft distribution reported as **premium earnings**, not as burden (§1.3.5)
- [ ] Gini reported with a caveat: when drafts are rare relative to headcount it is arithmetic, not insight

### Verification
*   🤖 **Automated:** `pytest tests/reporting/test_kpis.py`
*   🙋 **Manual:** `crewsim run --policy R6 --scenarios 500 --kpis`
    *   **Expect:** every KPI, with the warm-up window explicitly excluded and stated
    *   **Fails if:** warm-up rows are included, or cool-down costs are dropped

---

## ⏳ [TODO] S1e-02 — Self-contained HTML report
**Size:** `M` | **Depends on:** S1e-01 | **Spec:** §2.2, §9.3

**As a** stakeholder **I want** a self-contained HTML report

### Description
Decision makers need readable dashboards, not terminal output. Generating an HTML artifact lets executives quickly compare policy tradeoffs visually.
**so that** I can easily digest and share the results of the simulation.

### Acceptance Criteria
- [ ] **One file**, no external assets — it has to be emailable to Crew Planning
- [ ] Cost distributions; the trade-off curve with the optimum marked; the λ curve
- [ ] Front page carries: gate status (**including failures**), the provenance chain, and **every
  outstanding `[CONFIRM: …]` the result depends on**

### Verification
*   🤖 **Automated:** `pytest tests/reporting/test_html.py`
*   🙋 **Manual:** `crewsim report --policies R4 R6 R8 R10 R14 --open`
    *   **Expect:** a U-shaped trade-off curve with the optimum marked, in a single file
    *   **Fails if:** it needs a CDN or a local server — it must open from an email attachment

---

## ⏳ [TODO] S1e-03 — Exemplar-scenario drill-down
**Size:** `M` | **Depends on:** S1e-02 | **Spec:** §9.3, §2.3/C2

**As a** planner **I want** to interrogate a recommendation

### Description
"Why 6 reserves?" needs proof. The ability to drill down into a specific day and see exactly how the 6th reserve prevented a massive cascade builds trust.
**so that** "why 6 reserves?" resolves to a specific simulated Tuesday.

### Acceptance Criteria
- [ ] The 5 costliest and 5 most typical scenarios, each as an auditable event timeline
- [ ] Every cost row traceable to its `root_event_uid`, so a cancellation shows its whole causal chain
- [ ] Reachable from the recommendation itself, not buried in an appendix

### Verification
*   🤖 **Automated:** `pytest tests/reporting/test_drilldown.py`
*   🙋 **Manual:** `crewsim report --policy R6 --drilldown costliest`
    *   **Expect:** a readable timeline: sick call → reserve exhausted → draft → cascade → cancellation
    *   **Fails if:** the chain cannot be followed end to end — a planner will not act on an aggregate

---

## ⏳ [TODO] S1e-04 — Policy grid runner
**Size:** `M` | **Depends on:** S1e-01 | **Spec:** §3

**As a** researcher **I want** an automated runner for grid searches

### Description
Testing one policy at a time is too slow. An automated grid runner lets us effortlessly compute the entire cost surface across dozens of reserve counts overnight.
**so that** I can evaluate multiple policies systematically without manual intervention.

### Acceptance Criteria
- [ ] Grid from config: R × reserve-selection × cross-base (24 combinations)
- [ ] **All combinations share one CRN scenario set** — comparisons are paired
- [ ] Parallel via joblib; V7 must still pass with the grid running

### Verification
*   🤖 **Automated:** `pytest tests/test_grid.py`
*   🙋 **Manual:** `crewsim grid --config configs/grid_mvp.yaml --scenarios 1000`
    *   **Expect:** 24 combinations, paired, minutes not hours
    *   **Fails if:** each combination regenerates its own scenarios — the comparison becomes unpaired
    *   and needs ~100× the runs to resolve anything

---

## ⏳ [TODO] S1e-05 — Counterfactual runs
**Size:** `M` | **Depends on:** S1e-04 | **Spec:** §3, §5.6

**As a** decision-maker **I want** the price of the mandated rules quantified

### Description
Union rules cost money. Running counterfactual scenarios (e.g. what if L5 was relaxed?) quantifies exactly how much a specific rule constraints operations.
**so that** keeping them is a choice made with a number attached.

### Acceptance Criteria
- [ ] Two counterfactuals: `junior_first` ordering, and a `myopic_total_cost` selector that ranks by
  (draft cost + predicted cascade cost) rather than strictly by tier
- [ ] **Structurally impossible** to select either as a candidate policy — a separate analysis flag
- [ ] Output labelled **NOT A RECOMMENDATION** wherever it appears

### Verification
*   🤖 **Automated:** `pytest tests/test_counterfactuals.py`
*   🙋 **Manual:** `crewsim counterfactual --vs-mandated`
    *   **Expect:** the cost delta of each mandated rule, clearly labelled
    *   **Fails if:** a counterfactual can appear in a recommendation
    *   > With drafting fully determined at Air Transat, these are the most informative runs available — there
    *   > is no drafting policy to search, only a mandated one to price.

---

## ⏳ [TODO] S1e-06 — V5 trace export for the SME walkthrough  ·  **gate V5**
**Size:** `M` | **Depends on:** S1e-03 | **Spec:** §9.2

**As a** SME **I want** a detailed trace export

### Description
Subject Matter Experts need to trust the engine's logic. Exporting a detailed, step-by-step trace allows a planner to verify the engine handles Edge Case X correctly.
**so that** I can manually step through a simulation day and verify the engine's logical decisions.

### Acceptance Criteria
- [ ] Replay a real disruption week; export an **operational timeline**, not a log dump
- [ ] Each decision shows the alternatives considered and why they were rejected
- [ ] Formatted for a 60–90 minute session — you get one hour of a duty manager's attention

### Verification
*   🤖 **Automated:** `pytest tests/gates/test_v5_trace.py`
*   🙋 **Manual:** `crewsim gate v5 --week 2026-01-12 --format timeline`
    *   **Expect:** hour-by-hour, readable by someone who has never seen the code
    *   **Fails if:** it reads as debug output
    *   > **The question to ask the SME is "would you have done this?"** — not "is this number right". A model
    *   > that reaches the right total by making decisions no duty manager would make is not validated.
    *   > Expect to learn about a recovery instrument the model does not have; that is a **successful** V5.

---

## ⏳ [TODO] S1e-07 — V6 cost backtest against actuals  ·  **gate V6**
**Size:** `L` | **Depends on:** S1e-06 | **Spec:** §9.2

**As a** reviewer **I want** a backtest against historical costs

### Description
The ultimate proof is historical accuracy. If the simulation's baseline cost is drastically different from what finance actually paid last year, the model is invalid.
**so that** I can validate that the simulation's baseline matches reality.

### Acceptance Criteria
- [ ] Feed **actual** historical disruption streams through the model; compare against real payroll and
  invoice cost for the same period
- [ ] Report the **bias decomposition** from §9.2, not just the headline gap
- [ ] State the direction each exclusion pushes: voluntary layer, conservative surrogate, no network
  propagation, no aircraft/passenger recovery

### Verification
*   🤖 **Automated:** `pytest tests/gates/test_v6_backtest.py`
*   🙋 **Manual:** `crewsim gate v6 --period 2026-01`
    *   **Expect:** simulated vs actual, with the decomposition shown
    *   **Fails if:** it lands inside tolerance with no decomposition — offsetting biases that cancel by
    *   luck are worth less than a miss in the predicted direction and magnitude
    *   ## Exiting Phase 1
    *   Once V5 and V6 pass, the model may inform a bid-period decision — subject to §9.3's reporting
    *   obligations, which include listing every outstanding `[CONFIRM: …]` the result depends on.
    *   **Only then refine the `product_1/` epics.** Writing detailed Phase-2 acceptance criteria before this
    *   point encodes today's assumptions into next quarter's work.

