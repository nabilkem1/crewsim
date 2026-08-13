"""Read-only views over the effective configuration.

Everything here derives from `crewsim.config` -- schemas from the pydantic
models, values from `load()`. Nothing is hardcoded.
"""

from __future__ import annotations

import logging
from typing import Any, get_args, get_origin

from fastapi import APIRouter, HTTPException

from crewsim.config import BaseConfig, load

router = APIRouter(prefix="", tags=["config"])

log = logging.getLogger(__name__)


@router.get("/categories", response_model=list[str])
def list_categories() -> list[str]:
    """List all available configuration categories."""
    return list(BaseConfig.model_fields.keys())


def _unwrap_optional(annotation: Any) -> Any:
    """`X | None` -> `X`; anything else unchanged."""
    origin = get_origin(annotation)
    if origin is not None and getattr(origin, "__name__", "") in ("Union", "UnionType"):
        for arg in get_args(annotation):
            if arg is not type(None):
                return arg
    return annotation


@router.get("/schema/{category}")
def get_category_schema(category: str) -> dict[str, Any]:
    """Get the JSON schema and current values for a configuration category."""
    if category not in BaseConfig.model_fields:
        raise HTTPException(status_code=404, detail=f"Category '{category}' not found")

    model_class = _unwrap_optional(BaseConfig.model_fields[category].annotation)
    schema = (
        model_class.model_json_schema()
        if hasattr(model_class, "model_json_schema")
        else {"type": "string", "description": "Not a pydantic model"}
    )

    current_value = getattr(load(), category, None)
    if hasattr(current_value, "model_dump"):
        current_value = current_value.model_dump(mode="json")

    return {"schema": schema, "current_values": current_value}


@router.get("/")
def get_full_config() -> dict[str, Any]:
    """Get the full configuration object."""
    return load().model_dump(mode="json")


@router.get("/search")
def search_config(q: str) -> list[dict[str, Any]]:
    """Search across all configuration parameters."""
    results: list[dict[str, Any]] = []
    query = q.lower()

    def traverse(data: Any, path: list[str]) -> None:
        if isinstance(data, dict):
            for k, v in data.items():
                traverse(v, [*path, k])
        elif isinstance(data, list):
            for i, v in enumerate(data):
                traverse(v, [*path, str(i)])
        elif any(query in p.lower() for p in path) or query in str(data).lower():
            results.append({"path": ".".join(path), "value": data})

    traverse(load().model_dump(mode="json"), [])
    return results


@router.get("/validate")
def validate_config() -> dict[str, Any]:
    """Validate the effective config against its bounds/CONFIRM markers."""
    from crewsim.config import all_confirm_markers

    markers = all_confirm_markers(load())
    return {
        "is_valid": not markers,
        "markers": [m.model_dump() for m in markers],
    }


@router.get("/policies")
def get_policies() -> list[dict[str, Any]]:
    """Load the policy set for the Policy Browser."""
    from crewsim.config import repo_root
    from crewsim.engine.policy import load_policy

    policies_dir = repo_root() / "configs" / "policies"
    policies = []
    for path in sorted(policies_dir.glob("*.yaml")) if policies_dir.exists() else []:
        try:
            pol = load_policy(path)
        except Exception:
            log.exception("Skipping unloadable policy file %s", path)
            continue
        policies.append(
            {"filename": path.name, "policy": pol.model_dump(mode="json"), "hash": pol.get_hash()}
        )
    return policies


@router.get("/costs")
def get_costs() -> dict[str, Any]:
    """Get the cost structure for visualisation."""
    from crewsim.config import load_costs

    return load_costs(load()).model_dump(mode="json")


@router.get("/seasons")
def get_seasons() -> dict[str, Any]:
    """The seasons a run may be scoped to.

    Served from `configs/seasons.yaml` via the same `load_seasons` every other
    caller uses, so the UI cannot drift from it. The processing form used to
    offer a hardcoded "W26"/"S26" -- those are calibration *parameter filenames*,
    not seasons, and neither has ever been a valid `scope.season`.
    """
    from crewsim.data.loaders import load_seasons

    cfg = load()
    return {"seasons": sorted(load_seasons(cfg)), "current": cfg.scope.season}
