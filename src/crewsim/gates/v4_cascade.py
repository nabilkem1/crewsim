import numpy as np

from crewsim.data.cascades import cascade_target


def run_v4_gate(cfg, sim_cascade_rates, window="holdout"):
    """
    Validates a simulated distribution of cascade rates against the historical band.
    Returns a dict with pass/fail and metrics.
    """
    hist = cascade_target(cfg, window_name=window)
    
    sim_mean = np.mean(sim_cascade_rates) if len(sim_cascade_rates) > 0 else 0.0
    gap = sim_mean - hist["rate"]
    passed = bool(hist["ci_low"] <= sim_mean <= hist["ci_high"])
    
    # Check draft recall for marginal warning
    recall_warning = False
    if hist.get("draft_recall"):
        marginal = cfg.quality_gates.d4_link_marginal
        # Assuming draft_recall has a "rate" or similar
        recall_val = hist["draft_recall"].get("rate", 1.0)
        if recall_val < marginal:
            recall_warning = True
            
    return {
        "pass": passed,
        "sim_mean": sim_mean,
        "hist_mean": hist["rate"],
        "ci_lower": hist["ci_low"],
        "ci_upper": hist["ci_high"],
        "gap": gap,
        "recall_warning": recall_warning,
        "draft_recall_rate": hist.get("draft_recall", {}).get("rate", 1.0)
    }

def print_v4_report(result, window):
    print(f"Gate V4: Cascade Frequency Validation ({window} window)")
    print(f"Historical Band: [{result['ci_lower']:.3f}, {result['ci_upper']:.3f}] (Mean: {result['hist_mean']:.3f})")
    print(f"Simulated Mean : {result['sim_mean']:.3f}")
    print(f"Gap            : {result['gap']:+.3f}")
    
    if result["recall_warning"]:
        print(f"\n[WARNING] S0-03 Draft Reconstruction recall was marginal ({result['draft_recall_rate']:.3f}).")
        print("          This historical band inherits that poor recall and may underestimate true cascades.")
        
    if result["pass"]:
        print("\nVerdict: [PASS] Simulated cascade rate matches history.")
    else:
        print("\nVerdict: [FAIL] Simulated cascade rate deviates significantly from history.")
        print("Suspect mechanism: Visibility lag, rule implementations, or base composition.")
