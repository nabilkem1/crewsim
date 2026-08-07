from crewsim.engine.policy import load_policy
import tempfile
import yaml

def test_policy_hashing():
    data = {
        "policy_id": "test",
        "costs_file": "costs_pilots.yaml@v3.2.1",
        "stage1": {
            "reserves": [
                {"base": "YUL", "fleet": "A330", "position": "FO", "dow": [1, 2], "short_call": 1, "long_call": 1}
            ]
        },
        "stage2": {
            "allow_cross_base_reserve": True,
            "reserve_selection": "shortest"
        },
        "mode": "FULL",
        "season": "winter"
    }
    
    with tempfile.NamedTemporaryFile("w", suffix=".yaml") as f:
        yaml.dump(data, f)
        f.flush()
        
        p = load_policy(f.name)
        
    assert p.policy_id == "test"
    h = p.get_hash()
    assert isinstance(h, str)
    assert len(h) == 12
    
    # Verify stability (should be exactly the same hash for the same data)
    with tempfile.NamedTemporaryFile("w", suffix=".yaml") as f2:
        yaml.dump(data, f2)
        f2.flush()
        p2 = load_policy(f2.name)
        assert p2.get_hash() == h
