import os
import re

narratives = {
    "S1b-03": "**As a** planner **I want** reserve lines to follow rotational rules and Short-Call/Long-Call splits\n**so that** I model realistic reserve availability instead of uniform pools.",
    "S1b-05": "**As a** modeller **I want** duties and rest periods to explicitly end on schedule\n**so that** crews are returned to availability correctly.",
    "S1c-02": "**As a** reviewer **I want** reserve notification limits enforced\n**so that** I don't model assigning crews who cannot make it to the airport in time.",
    "S1c-03": "**As a** reviewer **I want** rolling block and duty limits enforced\n**so that** the simulation does not assign illegal schedules leading to violations.",
    "S1c-04": "**As a** reviewer **I want** the mandatory one-duty-free-day-in-seven rule enforced\n**so that** long-term fatigue compliance is properly modeled.",
    "S1d-02": "**As a** planner **I want** drafting a future reserve to create a cascade cancellation on their original day\n**so that** the true downstream cost of borrowing from the future is captured.",
    "S1d-04": "**As a** data scientist **I want** the validation gate run exclusively on the holdout window\n**so that** the cascade accuracy metric is unbiased and reliable.",
    "S1e-01": "**As a** planner **I want** KPIs aggregated accurately over the measurement window\n**so that** warm-up noise is excluded and metrics are comparable.",
    "S1e-02": "**As a** stakeholder **I want** a self-contained HTML report\n**so that** I can easily digest and share the results of the simulation.",
    "S1e-04": "**As a** researcher **I want** an automated runner for grid searches\n**so that** I can evaluate multiple policies systematically without manual intervention.",
    "S1e-06": "**As a** SME **I want** a detailed trace export\n**so that** I can manually step through a simulation day and verify the engine's logical decisions.",
    "S1e-07": "**As a** reviewer **I want** a backtest against historical costs\n**so that** I can validate that the simulation's baseline matches reality.",
    "S2-01": "**As a** researcher **I want** Bayesian optimization over reserve levels\n**so that** I can efficiently find the optimal staffing without an exhaustive grid search.",
    "S2-02": "**As a** researcher **I want** ranking and selection over secondary parameters\n**so that** I can finely tune the rules efficiently.",
    "S2-03": "**As a** modeller **I want** the A330 treated as a separate problem instance\n**so that** the optimization isn't muddied by infeasible cross-fleet interactions.",
    "S2-04": "**As a** developer **I want** the simulation to run on Ray across an AKS cluster\n**so that** it can scale massively without losing reproducibility.",
    "S2-05": "**As a** researcher **I want** stratified sampling by severity regime\n**so that** confidence intervals are narrower and results converge faster.",
    "S2-06": "**As a** planner **I want** cabin crew modeled with their own cost file and multi-position rules\n**so that** I can optimize their distinct staffing requirements.",
    "S3-01": "**As a** developer **I want** to replace the surrogate legality rules with a true rules engine\n**so that** fidelity is maximized and bias is quantified.",
    "S3-02": "**As a** modeller **I want** delay propagation modeled through aircraft rotations\n**so that** aircraft-driven delays properly impact crew availability.",
    "S3-03": "**As a** data scientist **I want** automated monthly refitting with input-drift alerting\n**so that** the system degrades gracefully when reality shifts.",
    "S3-04": "**As a** stakeholder **I want** a dashboard with scenario drill-down\n**so that** I can interactively explore the data instead of just reading static reports.",
    "S3-05": "**As a** stakeholder **I want** a formal V&V accreditation package\n**so that** I can defend the system's recommendations to executive leadership.",
    "S3-06": "**As a** planner **I want** to model the voluntary layer of open-time pickups\n**so that** I can account for cheaper coverage options before forced drafting."
}

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    parts = re.split(r'^(#+\s+(?:⏳ \[TODO\]|🟢 \[DONE\])?\s*S\d+[a-zA-Z]*-\d+[a-zA-Z]*.*?)$', content, flags=re.MULTILINE)
    
    if len(parts) == 1:
        return

    new_content = parts[0]
    
    for i in range(1, len(parts), 2):
        header = parts[i]
        body = parts[i+1]
        
        m = re.search(r'(S\d+[a-zA-Z]*-\d+[a-zA-Z]*)', header)
        if m:
            sid = m.group(1)
            if sid in narratives and "**As a**" not in body:
                # Find the Size/Depends line
                # It starts with **Size:**
                body_lines = body.split('\n')
                new_body_lines = []
                inserted = False
                for j, line in enumerate(body_lines):
                    new_body_lines.append(line)
                    if line.startswith('**Size:**') and not inserted:
                        new_body_lines.append('')
                        new_body_lines.append(narratives[sid])
                        inserted = True
                body = '\n'.join(new_body_lines)
        
        new_content += header + body

    with open(filepath, 'w') as f:
        f.write(new_content)

for root, dirs, files in os.walk('backlog'):
    for file in files:
        if file.endswith('.md') and file != 'README.md' and file != 'COVERAGE_AUDIT.md' and file != '00_phase0_data_foundation.md' and file != '01_slice_1a_foundation.md':
            process_file(os.path.join(root, file))
