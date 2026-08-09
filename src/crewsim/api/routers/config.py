from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from crewsim.config import BaseConfig, load

router = APIRouter(prefix="", tags=["config"])

@router.get("/categories", response_model=List[str])
def list_categories() -> List[str]:
    """List all available configuration categories."""
    return list(BaseConfig.model_fields.keys())

@router.get("/schema/{category}")
def get_category_schema(category: str) -> Dict[str, Any]:
    """Get the JSON schema and current values for a specific configuration category."""
    if category not in BaseConfig.model_fields:
        raise HTTPException(status_code=404, detail=f"Category '{category}' not found")
    
    field_info = BaseConfig.model_fields[category]
    annotation = field_info.annotation
    
    # Handle Optional (Union[..., NoneType])
    from typing import get_args, get_origin
    
    origin = get_origin(annotation)
    if origin is not None and getattr(origin, '__name__', '') in ('Union', 'UnionType'):
        args = get_args(annotation)
        # Find the first non-NoneType argument
        for arg in args:
            if arg is not type(None):
                model_class = arg
                break
        else:
            model_class = annotation
    else:
        model_class = annotation
        
    try:
        if hasattr(model_class, "model_json_schema"):
            schema = model_class.model_json_schema()
        else:
            schema = {"type": "string", "description": "Not a pydantic model"}
    except Exception:
        schema = {}

    try:
        current_config = load()
        current_value = getattr(current_config, category, None)
        if hasattr(current_value, "model_dump"):
            current_value_dict = current_value.model_dump(mode="json")
        else:
            current_value_dict = current_value
    except Exception:
        current_value_dict = None

    return {
        "schema": schema,
        "current_values": current_value_dict
    }

@router.get("/")
def get_full_config() -> Dict[str, Any]:
    """Get the full configuration object."""
    try:
        current_config = load()
        return current_config.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
def search_config(q: str) -> List[Dict[str, Any]]:
    """Search across all configuration parameters."""
    results = []
    query = q.lower()
    
    try:
        current_config = load()
        dump = current_config.model_dump(mode="json")
        
        def traverse(data: Any, path: List[str]):
            if isinstance(data, dict):
                for k, v in data.items():
                    traverse(v, path + [k])
            elif isinstance(data, list):
                for i, v in enumerate(data):
                    traverse(v, path + [str(i)])
            else:
                key_match = any(query in p.lower() for p in path)
                val_match = query in str(data).lower()
                if key_match or val_match:
                    results.append({
                        "path": ".".join(path),
                        "value": data
                    })
                    
        traverse(dump, [])
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate")
def validate_config() -> Dict[str, Any]:
    """Validate a config against bounds/CONFIRM markers."""
    try:
        current_config = load()
        from crewsim.config import all_confirm_markers
        markers = all_confirm_markers(current_config)
        return {
            "is_valid": len(markers) == 0,
            "markers": [m.model_dump() for m in markers]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/policies")
def get_policies() -> List[Dict[str, Any]]:
    """Load policies for Policy Browser."""
    from crewsim.engine.policy import load_policy
    from crewsim.config import repo_root
    policies_dir = repo_root() / "configs" / "policies"
    policies = []
    if policies_dir.exists():
        for path in policies_dir.glob("*.yaml"):
            try:
                pol = load_policy(path)
                policies.append({
                    "filename": path.name,
                    "policy": pol.model_dump(mode="json"),
                    "hash": pol.get_hash()
                })
            except Exception as e:
                pass
    return policies


@router.get("/costs")
def get_costs() -> Dict[str, Any]:
    """Get cost structure for visualization."""
    try:
        current_config = load()
        from crewsim.config import load_costs
        costs = load_costs(current_config)
        return costs.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
