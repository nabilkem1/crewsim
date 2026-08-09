# CrewSim Web UI: Product Vision

## 1. Product Vision Statement
The CrewSim Web UI transforms the Air Transat Crew Reserve & Drafting Policy Optimization System from a specialized, command-line engineering tool into an accessible, professional decision-support platform. By exposing the powerful two-stage stochastic program engine through a structured, visual interface, we enable Operations and Planning teams to continuously evaluate, calibrate, and compare reserve sizing policies without requiring software engineering expertise, ultimately minimizing expected costs and mitigating tail-risk in pilot rostering.

## 2. Problem Statement
Currently, the optimization system is highly capable but constrained by its CLI-only interface.
* **Accessibility:** Planners and domain experts cannot run simulations or configure experiments without a developer. 
* **Disconnected Workflows:** Configuration editing, calibration, simulation execution, and result analysis are disjointed steps. 
* **Provenance Tracking:** Linking an output report back to the exact parameter set, scenario seeds (CRN), and calibration data that produced it is a manual, error-prone process.
* **Opaque Engine Dynamics:** While the engine outputs detailed HTML/CSV reports, explaining *why* a specific cascade occurred or *why* a legality rule failed requires manual log parsing.

The Web UI solves this by providing a unified lifecycle manager that enforces provenance, validates configurations visually, and surfaces explainability tools as integrated interactive dashboards.

## 3. User Personas

### 3.1. Simulation Operator
* **Role:** Operations Analyst, Planner.
* **Goals:** Configure parameter sets for upcoming bid periods, execute single policies or grid sweeps, and ensure simulations finish successfully.
* **Tasks:** Edit configurations, launch simulations, monitor job queues, download reports.
* **Pain Points:** JSON syntax errors in configs, losing track of which config ran which simulation, waiting for long jobs without status visibility.

### 3.2. Simulation Analyst
* **Role:** Quantitative Analyst, Senior Planner.
* **Goals:** Determine the optimal reserve sizing, analyze cost distributions, and compare counterfactual policies (E[C] + λ·CVaR₀.₉₅).
* **Tasks:** Compare paired CRN runs, evaluate grid matrices, drill down into cascade eligibility bands and Gini coefficients.
* **Pain Points:** Correlating high-level KPIs to underlying events, comparing two different simulation outputs side-by-side.

### 3.3. Domain Expert (SME)
* **Role:** Union Rep, Chief Pilot, Compliance Officer.
* **Goals:** Ensure the simulation adheres to reality, particularly union drafting rules and legality layers (L0-L8).
* **Tasks:** Review verification gates (V1-V9), analyze narrative traces for peak disruption weeks, inspect legality explanations for specific assignments.
* **Pain Points:** Lack of trust in "black box" models, inability to easily query why a specific crew member was bypassed in the drafting sequence.

## 4. Design Principles
Derived from the core product guidelines, the CrewSim UI must embody:

1. **Professional Engineering Aesthetic:** Precision over polish. Favor dense, high-utility data tables, monospace fonts for identifiers, and clear data hierarchy over spacious marketing-style layouts.
2. **State Always Visible:** Simulation state (queued, running, completed, failed, cancelled) and system health must be globally visible. Loading states should use contextual skeletons, never full-page blockers.
3. **Progressive Disclosure:** Navigate from high-level KPIs (e.g., Total Cost) to detailed summaries (e.g., cascade rates) to raw engine logs and traces (e.g., L2 Min Rest failure).
4. **Accessibility as First-Class Constraint:** Strict adherence to WCAG 2.2 AA. Form inputs must have explicit labels, validation on blur, and preserve user input on error. Charts must include accessible alternatives (data tables) and clear axes/legends.
5. **Responsive Adaptation:** Fluid scaling from desktop (complex grids, side-by-side comparison) to tablet (monitoring, report reviewing) to mobile (status checks, job alerts).
6. **Consistent Design Language:** Semantic use of colors (e.g., status indicators) and domain-specific terminology (Reserve vs. Draft vs. Cascade).
7. **Simulation Lifecycle Explicit:** The pipeline (Data → Calibration → Scenarios → Execution → Reporting) should guide the UI layout, preventing users from running simulations on uncalibrated data.
8. **Provenance Built-In:** Every output must cryptographically link (blake2b hashes) back to its inputs. Artifacts are immutable.

## 5. Non-Goals
* **Real-Time Dispatching:** This is strictly an offline planning and simulation tool for the 28-day bid period, not a live Day-of-Ops crew scheduling system.
* **Engine Re-write:** The web UI wraps the existing Python (SimPy/NumPy) engine; it does not reimplement the Monte Carlo or stochastic optimization logic.
* **Generic BI Tool:** We are building domain-specific, purpose-built visualizations for crew reserve cascades and legality, not a generic drag-and-drop dashboarding tool.

## 6. Success Metrics
* **Time to Execute:** Reduction in time from creating a configuration to successfully launching a simulation matrix.
* **Operator Adoption:** Percentage of runs initiated by non-engineers via the Web UI vs CLI.
* **Error Rate:** Reduction in failed jobs due to JSON malformations or misaligned configuration states.
* **Decision Velocity:** Time taken for an Analyst to compare two policies and export a final recommendation report.
