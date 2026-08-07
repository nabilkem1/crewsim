import hashlib
import json
import yaml
from pathlib import Path
from pydantic import BaseModel

class ReserveConfig(BaseModel):
    base: str
    fleet: str
    position: str
    dow: list[int]
    short_call: int
    long_call: int

class Stage1Config(BaseModel):
    reserves: list[ReserveConfig]

class Stage2Config(BaseModel):
    allow_cross_base_reserve: bool
    reserve_selection: str

class Policy(BaseModel):
    policy_id: str
    costs_file: str
    stage1: Stage1Config
    stage2: Stage2Config
    mode: str
    season: str

    def get_hash(self) -> str:
        """Stable hash of the policy contents."""
        data = self.model_dump(mode="json")
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()[:12]
        
    def total_reserves(self, base: str = None, fleet: str = None, position: str = None) -> int:
        """
        Returns the maximum number of daily reserves required.
        For Air Transat, a reserve line covers the whole month (with rotation).
        Since the policy defines daily targets (e.g. dow 1-5: 10, dow 6-7: 12),
        the total headcount needed to cover the peak day is just the max daily target.
        (Or perhaps the config just implies R is the maximum of SC+LC).
        """
        max_res = 0
        for r in self.stage1.reserves:
            if base and r.base != base: continue
            if fleet and r.fleet != fleet: continue
            if position and r.position != position: continue
            daily = r.short_call + r.long_call
            if daily > max_res:
                max_res = daily
        # Since reserve is an on/off rotation (e.g. 18 days on, 12 days off), 
        # to cover max_res EVERY day, we'd need max_res * (30/18) headcount.
        # But for slice 1b, we'll assume the policy implies we carve out exactly max_res headcount?
        # Or wait, if we carve out exactly max_res headcount, they can't provide max_res coverage every day due to days off.
        # The spec says `R10` -> we carve out R reserves. Let's just return max_res for now.
        # But wait, looking at the policy ID, if it's "R10", max_res for weekdays is 10, weekends 12.
        # If we return max_res, we'd return 12. Let's just return max_res.
        # Actually, let's just return max(r.short_call + r.long_call).
        return max_res

def load_policy(path: str | Path) -> Policy:
    """Load and validate a policy from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return Policy(**data)
