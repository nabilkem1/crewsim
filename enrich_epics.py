import os
import re
import glob

enrichments = {
    "S0-00": {
        "desc": "The DES core simulates event progression over time. For example, if a delay occurs, it must push the end-time back dynamically so downstream impacts are caught.",
        "impl": "Implemented using a custom event loop in the DES engine that handles chronologically ordered events."
    },
    "S0-01": {
        "desc": "We need robust validation data to prove the model's accuracy. By compiling 3 years of payload data, we ensure edge cases are represented.",
        "impl": "Implemented via data pipelines that ingest and cleanse historical Air Transat delay and disruption data."
    },
    "S0-02": {
        "desc": "Separating fitting and holdout data prevents overfitting. For instance, tuning parameters on 2024 data and validating on unseen 2025 data guarantees the model generalizes.",
        "impl": "Added windowing configuration in `base.yaml` that explicitly separates fitting and holdout date ranges."
    },
    "S0-02b": {
        "desc": "To properly analyze seasonality, we must partition the dataset into logical seasons (e.g., winter vs summer). This ensures delay distributions are seasonally accurate.",
        "impl": "Implemented by mapping dates to seasons based on the configured mapping file and filtering DataFrames accordingly."
    },
    "S0-03": {
        "desc": "Reconstructing actual draft events validates the baseline model. We cross-reference schedule changes with payroll data to confidently identify drafted crew.",
        "impl": "Implemented a robust join query that matches short-notice reason codes in D6 with premium pay codes in D7."
    },
    "S0-04": {
        "desc": "Open time items represent uncovered duties that trigger the drafting engine. Tracking these historically lets us benchmark our model's generation rate.",
        "impl": "Filtered the dataset to identify unassigned flights and explicitly modeled them as `OpenTimeItem` instances."
    },
    "S0-05": {
        "desc": "Cascades happen when a delay causes a crew member to miss their next flight. Knowing this historical rate lets us tune the downstream impact multiplier.",
        "impl": "Built a 7-day lookahead script that scans a drafted pilot's schedule to count instances where later trips were dropped."
    },
    "S0-06": {
        "desc": "Simulating delays requires knowing the frequency of specific delay regimes. We extract this from D5 to seed our Random Number Generator realistically.",
        "impl": "Used empirical historical delays to fit distribution parameters across Calm, Normal, and Disrupted days."
    },
    "S0-07": {
        "desc": "Delay distributions are not uniform. Fitting a model allows us to sample realistic delays, properly representing the long tail of massive disruptions.",
        "impl": "Leveraged Gaussian Mixture Models (GMM) to accurately fit the dual peaks of short and long delays."
    },
    "S0-07b": {
        "desc": "A single GMM doesn't capture the regime shift on bad weather days. This splits the fitting by severity, allowing the simulation to model \"snowstorm\" days accurately.",
        "impl": "Partitioned the historical dataset by regime quantiles (Calm, Normal, Disrupted) before fitting independent GMMs."
    },
    "S0-08": {
        "desc": "Randomness must be reproducible. By locking the transition matrix seed, identical inputs yield identical weather patterns, allowing fair policy comparisons.",
        "impl": "Generated a statically seeded Markov chain transition matrix for weather regime state sampling."
    },
    "S0-08b": {
        "desc": "Expanding the transition matrices ensures the model supports multiple seasons and regimes seamlessly, rather than hardcoding a single sequence.",
        "impl": "Handled the serialization and retrieval of multiple transition matrices indexed by season configuration."
    },
    "S0-09": {
        "desc": "Strict data boundaries prevent data leakage. If the engine accidentally looks at the validation holdout window during calibration, its metrics are compromised.",
        "impl": "Enforced a strict validation check in `cli.py` and `config.py` that blocks reading the holdout window during fitting runs."
    },
    "S1a-01": {
        "desc": "The configuration drives the engine and must be immutable during a run. This prevents accidental state mutation and ensures reproducible behavior.",
        "impl": "Migrated all parameters to strict Pydantic models in `config.py` with `frozen=True`."
    },
    "S1a-02": {
        "desc": "Moving loose constants into strict configurations stops hardcoded assumptions. For instance, L2 rest duration is now a configurable knob rather than a magic number.",
        "impl": "Extracted all magic numbers from the codebase and populated them into `configs/base.yaml`."
    },
    "S1a-03": {
        "desc": "We need explicit cost files to isolate payroll negotiations from codebase logic. This allows finance to tweak compensation rates without touching python code.",
        "impl": "Created `costs_pilots.yaml` and loaded it via the `CostsConfig` Pydantic model."
    },
    "S1a-04": {
        "desc": "Removing manual constants ensures all logic respects the configuration. If a user sets the horizon to 30 days, the engine shouldn't silently assume 42.",
        "impl": "Refactored the codebase to dynamically read values like horizon length from the Pydantic configuration tree."
    },
    "S1a-05": {
        "desc": "Common Random Numbers (CRN) keep noise low. By using the same seed across scenarios, any cost difference is guaranteed to be from policy, not luck.",
        "impl": "Integrated the `Random` class throughout the simulation to bind scenario generation tightly to a deterministic seed."
    },
    "S1a-06": {
        "desc": "Physical impossibility (being on two flights at once) must be structurally prevented. This validates that the core calendar assignment engine works.",
        "impl": "Added interval overlap checks during calendar updates to reject intersecting block insertions."
    },
    "S1a-07": {
        "desc": "Realistic schedules require real-world constraints like minimum rest. This ensures the drafted crew member gets legal downtime before their next flight.",
        "impl": "Implemented surrogate legality checks for rest duration (L2) and block limits in the state engine."
    },
    "S1a-08": {
        "desc": "Drafting must emulate union rules. For example, a junior reserve is drafted before a senior line holder, accurately mimicking the cost structure.",
        "impl": "Enforced tier sorting and seniority-based tie-breaking in the `DraftingEngine` selection logic."
    },
    "S1a-09": {
        "desc": "Tracing outputs to inputs builds trust. Hashing the policy file guarantees we know exactly which parameter set generated a specific result.",
        "impl": "Computed a SHA-256 hash of the resolved configuration and stored it in the output ledger."
    },
    "S1a-10": {
        "desc": "Sanity checks ensure baseline math works. If a scenario with 0 disruptions costs money, we know the accounting logic has a critical flaw.",
        "impl": "Built `test_v1_degeneracy.py` that asserts exactly $0 cost under empty boundary conditions."
    },
    "S1a-11": {
        "desc": "Multiprocessing often breaks random number generation. This gate proves that running 10 parallel jobs yields identical results to running sequentially.",
        "impl": "Wrapped the simulation loop in `joblib.Parallel` and asserted equality against sequential runs in `test_v7_multiprocessing.py`."
    },
    "S1a-12": {
        "desc": "Planners need a simple interface, not Python scripts. A unified CLI lets them easily test policies and view the financial ledger breakdowns.",
        "impl": "Added a comprehensive `argparse` tree in `cli.py` to route users to configuration, running, and explanation tasks."
    },
    "S1b-01": {
        "desc": "We need real crew state, not synthetic models. By loading D2 rosters, the engine respects actual seniorities, fleet qualifications, and base assignments.",
        "impl": "Parsed `d2_rosters.csv` to instantiate `CrewMember` objects and populated their initial calendars."
    },
    "S1b-02": {
        "desc": "Reserves are carved out of the existing pool. If an airline has 120 pilots, allocating 10 to reserve means only 110 are left to fly regular lines.",
        "impl": "Added policy-driven target logic in `policy.py` that identifies and converts junior line-holders into reserves to conserve headcount."
    },
    "S1b-03": {
        "desc": "Reserves don't work 24/7. Modeling their realistic on/off rotations ensures we don't accidentally overstate reserve availability on weekends.",
        "impl": "Harvested authentic reserve patterns directly from D2 and cycled them onto newly minted reserves dynamically."
    },
    "S1b-04": {
        "desc": "Sick calls must hit real people. This prevents the model from generating phantom sick time and forces the engine to handle real broken pairings.",
        "impl": "Built an `apply_sick_call` function that selectively removes `PAIRING` blocks from active crew and generates `OpenTimeItem` entries."
    },
    "S1b-05": {
        "desc": "Crew members must return to availability after duty. A drafted reserve needs mandatory rest, but must eventually become available again for another draft.",
        "impl": "Structured event transitions to cleanly split `RESERVE` blocks around `DRAFTED_DUTY` and L2 `REST` blocks."
    },
    "S1b-06": {
        "desc": "Airlines hold open flights to the last minute hoping someone frees up. Delaying the cancellation decision allows late-arriving reserves to rescue trips.",
        "impl": "Added `uncovered_deadline_hours` to configuration and delayed item cancellation in the event loop until the deadline expires."
    },
    "S1b-07": {
        "desc": "Queueing theory acts as a mathematical backstop. If the DES engine's shortfall rate drastically deviates from Erlang B, we know the reserve accounting is bugged.",
        "impl": "Computed analytical Erlang B bounds and created an automated test ensuring DES mocked values stay within a 5% confidence interval."
    },
    "S1b-08": {
        "desc": "Perfect caching avoids re-running expensive simulations. If the transition matrix and seed are identical, we just load the cached scenario ledger.",
        "impl": "Passed deterministic parameters into the engine and exposed the generation flow in `crn.py`."
    },
    "S1c-01": {
        "desc": "Real eligibility depends on real schedules. We cannot just assume 30% of pilots are eligible; we must check their actual calendar availability and legality dynamically.",
        "impl": ""
    },
    "S1c-02": {
        "desc": "Calling a reserve 30 minutes before a flight is physically impossible. This rule ensures the engine only drafts crew who can realistically commute to the airport.",
        "impl": ""
    },
    "S1c-03": {
        "desc": "A pilot cannot fly indefinitely. Rolling limits (e.g. 100 hours in 28 days) prevent the engine from over-working a single crew member beyond union constraints.",
        "impl": ""
    },
    "S1c-04": {
        "desc": "Fatigue mitigation is paramount. This guarantees that even heavily drafted crew receive mandatory days off, avoiding structural violations.",
        "impl": ""
    },
    "S1c-05": {
        "desc": "Validating the eligibility logic against unseen historical data proves it works. If we predict 30% eligibility but history shows 10%, our rules are too loose.",
        "impl": ""
    },
    "S1d-01": {
        "desc": "Drafting a pilot today might ruin their scheduled trip tomorrow. Automatically breaking their future pairings ensures we accurately price the cascading disruption.",
        "impl": ""
    },
    "S1d-02": {
        "desc": "Pulling a reserve meant for Thursday to fly on Tuesday leaves Thursday exposed. Capturing this models the true hidden cost of aggressively borrowing from the future.",
        "impl": ""
    },
    "S1d-03": {
        "desc": "The horizon boundary shouldn't erase consequences. If a flight is uncovered on the very last day of the simulation, it must still incur a massive cancellation penalty.",
        "impl": ""
    },
    "S1d-04": {
        "desc": "Using the holdout data for cascade verification prevents cheating. The model must prove it can accurately forecast cascade rates on flights it was never trained on.",
        "impl": ""
    },
    "S1d-05": {
        "desc": "Parameters are estimates. By sweeping a range of values (like terminal penalty), we can prove to stakeholders whether a specific assumption fundamentally changes the answer.",
        "impl": ""
    },
    "S1e-01": {
        "desc": "The first 7 days of the simulation are noisy as the engine spins up. Throwing out this warm-up period ensures the final financial KPIs are perfectly stable and trustworthy.",
        "impl": ""
    },
    "S1e-02": {
        "desc": "Decision makers need readable dashboards, not terminal output. Generating an HTML artifact lets executives quickly compare policy tradeoffs visually.",
        "impl": ""
    },
    "S1e-03": {
        "desc": "\"Why 6 reserves?\" needs proof. The ability to drill down into a specific day and see exactly how the 6th reserve prevented a massive cascade builds trust.",
        "impl": ""
    },
    "S1e-04": {
        "desc": "Testing one policy at a time is too slow. An automated grid runner lets us effortlessly compute the entire cost surface across dozens of reserve counts overnight.",
        "impl": ""
    },
    "S1e-05": {
        "desc": "Union rules cost money. Running counterfactual scenarios (e.g. what if L5 was relaxed?) quantifies exactly how much a specific rule constraints operations.",
        "impl": ""
    },
    "S1e-06": {
        "desc": "Subject Matter Experts need to trust the engine's logic. Exporting a detailed, step-by-step trace allows a planner to verify the engine handles Edge Case X correctly.",
        "impl": ""
    },
    "S1e-07": {
        "desc": "The ultimate proof is historical accuracy. If the simulation's baseline cost is drastically different from what finance actually paid last year, the model is invalid.",
        "impl": ""
    }
}

files = glob.glob("backlog/mvp/*.md")

for fp in files:
    with open(fp, "r") as f:
        content = f.read()
    
    # We will process each story separately.
    # Find all story blocks. A block starts with ## and a status, then SXX-XX.
    # We will use string replacement.
    
    for sid, data in enrichments.items():
        if sid in content:
            # Inject description right before ### Acceptance Criteria
            desc_str = f"### Description\n{data['desc']}\n\n"
            
            # Find the story block
            pattern_story = re.compile(rf"(## [^\n]+{sid}.*?)(### Acceptance Criteria|\*\*Acceptance)", flags=re.DOTALL)
            match_story = pattern_story.search(content)
            
            if match_story and "### Description" not in match_story.group(1):
                new_block = match_story.group(1) + desc_str + match_story.group(2)
                content = content.replace(match_story.group(0), new_block)

            # Inject Implementation if it exists
            impl_str = f"### How it was implemented\n{data['impl']}\n\n"
            if data["impl"]:
                # We need to insert it at the end of the story.
                # Let's find the whole story block from this title to the next ## or EOF, or ---.
                # Actually, appending it right before the next `---` or `## ` is safe.
                pattern_end = re.compile(rf"(## [^\n]+{sid}.*?)(?=\n---|\n## |\Z)", flags=re.DOTALL)
                match_end = pattern_end.search(content)
                if match_end:
                    block = match_end.group(1)
                    if "### How it was implemented" not in block:
                        if not block.endswith("\n\n"):
                            block += "\n\n" if block.endswith("\n") else "\n\n\n"
                        new_block = block + impl_str
                        content = content.replace(match_end.group(1), new_block)
            
    with open(fp, "w") as f:
        f.write(content)

print("Enrichment complete.")
