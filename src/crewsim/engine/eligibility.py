from typing import Any, Literal

import numpy as np

from crewsim.engine.legality import is_legal_assignment
from crewsim.engine.state import BlockType, CrewMember, OpenTimeItem


class EligibilityEngine:
    def __init__(self, mode: Literal["FULL", "REDUCED"] = "FULL", p_elig: float = 0.3, cfg: Any = None) -> None:
        self.mode = mode
        self.p_elig = p_elig
        self.cfg = cfg
        self.samples: list[float] = []
        self._sample_times: list[float] = []

    def eligible_reserves(
        self,
        reserves: list[CrewMember],
        item: OpenTimeItem,
        now: float,
        rng: np.random.Generator | None = None,
    ) -> list[CrewMember]:
        if self.mode == "REDUCED":
            if rng is None:
                rng = np.random.default_rng()
            return [r for r in reserves if rng.random() < self.p_elig]
            
        pool = []
        for r in reserves:
            # Pool = reserves whose RESERVE block covers the WHOLE duty
            # window [item.start, item.end], not just the report-time instant
            # -- a reserve whose on-call window ends partway through the duty
            # can't actually take it (S1c-01's own acceptance criterion).
            overlap = r.blocks_in(item.start, item.end)
            has_reserve_coverage = False
            for b in overlap:
                if b.btype == BlockType.RESERVE and b.start <= item.start and b.end >= item.end:
                    has_reserve_coverage = True
                    break

            if has_reserve_coverage:
                pool.append(r)
                
        elig = []
        for r in pool:
            if is_legal_assignment(r, item, now=now, cfg=self.cfg).legal:
                elig.append(r)
                
        if pool:
            self.samples.append(len(elig) / len(pool))
            self._sample_times.append(now)

        return elig

    def get_distribution(self, min_time: float | None = None, max_time: float | None = None) -> list[float]:
        """Return the distribution of realized eligibility fractions.

        S1e-01: optionally restricted to a [min_time, max_time) sim_time
        window, to exclude warm-up/cool-down samples from a KPI report.
        Default (no bounds) is unchanged from before -- the full-horizon
        distribution V3's gate already depends on (S1c-05), which compares
        against a historical reconstruction that similarly spans its whole
        fitting/holdout window rather than a measurement-window analogue.
        """
        if min_time is None and max_time is None:
            return self.samples.copy()
        return [
            f for f, t in zip(self.samples, self._sample_times, strict=False)
            if (min_time is None or t >= min_time) and (max_time is None or t < max_time)
        ]
        
    def check_recommendation_safe(self) -> bool:
        if self.mode == "REDUCED":
            raise RuntimeError("REDUCED mode is active (Bernoulli(p_elig)). Refusing to produce a recommendation.")
        return True
