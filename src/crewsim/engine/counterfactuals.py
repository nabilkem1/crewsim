"""S1e-05: labelled counterfactual draft-selection strategies.

NOT A RECOMMENDATION. Air Transat's drafting order (impact tier, then
senior-first within tier) is mandated by the collective agreement, not a
lever the model may vary (spec Sec5.6). These exist only to price the
mandated rule against a hypothetical -- structurally kept off Policy /
Stage2Config (both `extra="forbid"`, see tests/test_counterfactuals.py) so
no policy YAML can select one, and never read by `run`/`compare`/`grid`.
"""
from typing import Any

from .cascade import compute_draft_delta
from .drafting import determine_tier
from .legality import is_legal_assignment
from .state import CrewMember, OpenTimeItem


def _draft_cost(costs: Any, tier: int) -> float:
    cost = costs.draft.base_premium + costs.draft.tier.get(tier, 0.0)
    if tier in (3, 5):
        cost += costs.draft.train_reschedule
    return float(cost)


def select_myopic_total_cost(
    roster: list[CrewMember],
    item: OpenTimeItem,
    costs: Any,
    cfg: Any,
    now: float | None = None,
) -> CrewMember | None:
    """"Pure Cost-Ranked" (spec Sec3): ignore impact tier entirely, draft
    whoever is cheapest RIGHT NOW -- draft cost for their own tier plus a
    predicted cascade cost.

    predicted_cascade_cost = len(cascaded_items) * costs.draft.base_premium:
    compute_draft_delta (cascade.py) is a pure function -- it returns which
    pairings a draft would break without mutating any crew state, so it's
    safe to call once per candidate purely to rank them. Each broken
    pairing is assumed to cost at least a base-rate (tier-1) draft to
    re-resolve -- a real existing cost figure, not an invented constant,
    and a deliberate lower bound (a multi-step cascade, or one resolved by
    a higher-tier draft, costs more than this predicts). User confirmed
    this fidelity level over a real one-step lookahead resolution.
    """
    legal = [c for c in roster if is_legal_assignment(c, item, now=now, cfg=cfg).legal]
    if not legal:
        return None

    def total_cost(c: CrewMember) -> float:
        tier = determine_tier(c, item, cfg)
        _, cascaded = compute_draft_delta(c, item, cfg, now if now is not None else 0.0)
        return _draft_cost(costs, tier) + len(cascaded) * float(costs.draft.base_premium)

    legal.sort(key=lambda c: (total_cost(c), c.seniority))
    return legal[0]
