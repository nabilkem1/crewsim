from joblib import Parallel, delayed
from crewsim.engine import crn

def run_mock_scenario(stream):
    rng = crn.event_rng(stream, "test_event")
    draws = [float(rng.random()) for _ in range(1000)]
    return crn.stable_seed(draws)

def test_v7_crn_multiprocess():
    """
    Gate V7: Reproducibility under multiprocessing.
    Must guarantee bit-identical output regardless of process topology.
    """
    master_key = "v7_master_seed"
    n_scen = 20
    
    # Baseline (single process)
    streams_seq = crn.generate_streams(master_key, n_scen)
    hashes_seq = [run_mock_scenario(s) for s in streams_seq]
    
    # Parallel (joblib)
    streams_mp = crn.generate_streams(master_key, n_scen)
    hashes_mp = Parallel(n_jobs=4)(
        delayed(run_mock_scenario)(s) for s in streams_mp
    )
    
    assert hashes_seq == hashes_mp
