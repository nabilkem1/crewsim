import hashlib
import json
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class _Model(BaseModel):
    """extra="forbid": an unrecognised policy-file key is a typo, not a
    silent no-op. S1e-05 depends on this directly -- its own AC requires a
    counterfactual (e.g. junior_first) to be structurally impossible to
    select via a policy YAML, not merely unconsumed; without this, an extra
    key would validate silently and do nothing, which is safe but not the
    loud rejection the AC asks for."""
    model_config = ConfigDict(extra="forbid")

class ReserveConfig(_Model):
    base: str
    fleet: str
    position: str
    dow: list[int]
    short_call: int
    long_call: int

class Stage1Config(_Model):
    reserves: list[ReserveConfig]

class Stage2Config(_Model):
    allow_cross_base_reserve: bool
    reserve_selection: str

class Policy(_Model):
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
        
    def total_reserves(
        self, base: str | None = None, fleet: str | None = None, position: str | None = None
    ) -> int:
        """Reserve headcount this policy carves out, optionally within one group.

        The PEAK daily target: max(short_call + long_call) over the matching
        stage-1 entries. A policy states a target per day-of-week group (e.g.
        4+2 Mon-Fri, 5+2 Sat-Sun); the headcount that has to exist is the
        largest of those, since the same carved-out pool covers every day.

        This is the definition roster_loader.load_rosters implements when it
        carves the pool, so the two agree by construction -- see its
        `target_reserves` computation, which is the same max over the same key.

        Known simplification, deliberately not hidden: a reserve line is an
        on/off rotation (roughly 18 days on, 12 off in this corpus), so a pool
        of exactly `max_res` crew does NOT deliver `max_res` bodies on every
        single day -- days off reduce same-day availability. Sizing the pool to
        guarantee daily coverage would need max_res * (cycle_length / days_on),
        which is a policy-design question (what does "R10" promise: 10 carved
        out, or 10 available daily?) that has not been settled with Crew
        Planning. Until it is, "R10" means ten crew carved out, matching both
        the policy_id convention and roster_loader. See [[ask-before-changing-design]].
        """
        return max(
            (
                r.short_call + r.long_call
                for r in self.stage1.reserves
                if (base is None or r.base == base)
                and (fleet is None or r.fleet == fleet)
                and (position is None or r.position == position)
            ),
            default=0,
        )

def load_policy(path: str | Path) -> Policy:
    """Load and validate a policy from a YAML file."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Policy(**data)
