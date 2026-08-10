from typing import Any, Literal

import numpy as np

from crewsim.engine.legality import is_legal_assignment
from crewsim.engine.state import BlockType, CrewMember, OpenTimeItem


class EligibilityEngine:
    # Only used when a caller supplies neither cfg.reduced_mode nor an explicit
    # p_elig -- the real value lives in configs/base.yaml -> reduced_mode.
    DEFAULT_P_ELIG = 0.3

    def __init__(self, mode: Literal["FULL", "REDUCED"] = "FULL",
                 p_elig: float | None = None, cfg: Any = None) -> None:
        self.mode = mode
        self.p_elig = self.DEFAULT_P_ELIG if p_elig is None else p_elig
        self.cfg = cfg
        self.samples: list[float] = []
        self._sample_times: list[float] = []

    @classmethod
    def from_config(cls, cfg: Any) -> "EligibilityEngine":
        """Build the engine the way configs/base.yaml says to.

        One construction rule, used by both des.py and the CLI's
        recommendation guard -- so the mode a command REFUSES on is
        necessarily the mode the simulation would have RUN in.
        """
        return cls(
            mode="REDUCED" if cfg.mode == "REDUCED" else "FULL",
            p_elig=cfg.reduced_mode.p_elig if cfg.reduced_mode else cls.DEFAULT_P_ELIG,
            cfg=cfg,
        )

    def eligible_reserves(
        self,
        reserves: list[CrewMember],
        item: OpenTimeItem,
        now: float,
        rng: np.random.Generator | None = None,
        record: bool = True,
        is_deadhead: bool = False,
    ) -> list[CrewMember]:
        """Eligible members of `reserves` for `item` at time `now`.

        `is_deadhead=True` tells L7 that this crew member is being POSITIONED to
        the item's base rather than starting duty at their own. L7's own wording
        is "crew must start duty at own base unless deadheaded", and its
        `is_deadhead` parameter has existed unset since the rule was written --
        so every cross-base candidate failed L7 by construction. S1c-07 is the
        first caller that can legitimately set it: it only does so on the branch
        that actually books the deadhead seat and writes the DEADHEAD block.

        `record=False` evaluates without logging a sample into the distribution
        get_distribution() returns. S1c-07 needs it: the cross-base pool is a
        different population at different bases, and gate V3 compares this
        distribution against a historical eligibility reconstruction for
        cfg.scope alone. Mixing another base's rate into that series would move
        V3's number without any in-scope mechanism having changed.
        """
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

        if self.mode == "REDUCED":
            # REDUCED replaces the LEGALITY evaluation with a coin flip, not
            # pool membership. Pool membership is structural and cheap -- the
            # reserve must actually hold a RESERVE block spanning the duty --
            # and des.py's assign_reserve requires it, raising otherwise.
            #
            # This previously thinned `reserves` directly, so REDUCED could
            # return a crew member with no covering block and the run died with
            # "Crew P00453 has no RESERVE block overlapping [...]". It had never
            # been observed because cfg.mode was ignored and the engine
            # hardcoded FULL, making REDUCED unreachable (S1c-01 AC4).
            if rng is None:
                rng = np.random.default_rng()
            elig = [r for r in pool if rng.random() < self.p_elig]
        else:
            elig = [
                r for r in pool
                if is_legal_assignment(
                    r, item, is_deadhead=is_deadhead, now=now, cfg=self.cfg
                ).legal
            ]

        if pool and record:
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
        """S1c-01 AC4: refuse to produce a recommendation from REDUCED mode.

        Called by every command that emits a recommendation -- `grid`, `report`
        and `gate v9` -- not merely defined. It was defined and called from
        nowhere in src/ until S1c-01's P1 pass, so the refusal it exists to
        perform never happened.

        A recommendation derived from Bernoulli(p_elig) is not a weaker
        recommendation, it is a coin flip wearing a reserve level's clothes.
        """
        if self.mode == "REDUCED":
            raise RuntimeError(
                "REDUCED mode is active (eligibility is Bernoulli(p_elig), not computed "
                "from crew state). Refusing to produce a recommendation. Set mode: FULL "
                "in configs/base.yaml, or use `run`/`compare` for a smoke test."
            )
        return True
