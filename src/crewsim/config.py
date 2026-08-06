"""Configuration and path resolution.

Every scope, horizon, population and **path** value comes from `configs/`.
Nothing in `src/` may hard-code one — that is enforced by
`tests/test_project_structure.py` (§4.4, §4.4.1b).

This module is deliberately minimal: it resolves paths and returns the raw
mapping. Story **S1a-02** replaces the return type with validated Pydantic
models. The bootstrap literal below is the single exception to the
no-hard-coded-paths rule, and the structure test whitelists it explicitly —
something has to know where the config file lives.
"""
from __future__ import annotations

import pathlib
from typing import Any

# The one bootstrap literal in the codebase. See the module docstring.
_CONFIG_RELPATH = "configs/base.yaml"


def repo_root() -> pathlib.Path:
    """The project root: two levels above this file (src/crewsim/config.py)."""
    return pathlib.Path(__file__).resolve().parents[2]


def load(config_path: str | pathlib.Path | None = None) -> dict[str, Any]:
    """Load the base configuration.

    Raises rather than falling back to defaults: a run against an unknown
    configuration is worse than a run that refuses to start.
    """
    import yaml

    path = pathlib.Path(config_path) if config_path else repo_root() / _CONFIG_RELPATH
    if not path.is_file():
        raise FileNotFoundError(
            f"configuration not found at {path}. "
            f"Every value this simulation uses lives in configs/ (§4.4)."
        )
    cfg = yaml.safe_load(path.read_text()) or {}
    cfg["_config_path"] = str(path)
    return cfg


# Accepted on-disk encodings for a dataset. Polars reads both transparently,
# so callers should never care which one is present.
DATASET_SUFFIXES = (".csv", ".csv.gz")


def dataset_path(cfg: dict[str, Any], name: str) -> pathlib.Path | None:
    """Locate dataset `name` inside the configured corpus, or None.

    The single place in the codebase that knows how a dataset is stored. Callers
    ask for `d2_rosters`; whether it is CSV or gzipped CSV is not their problem.
    """
    corpus = resolve(cfg, "corpus_dir")
    for suffix in DATASET_SUFFIXES:
        candidate = corpus / f"{name}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def resolve(cfg: dict[str, Any], key: str) -> pathlib.Path:
    """Resolve a `paths.*` key to an absolute path.

    >>> resolve(load(), "corpus_dir")   # -> <repo>/src/crewsim/data/corpus
    """
    paths = cfg.get("paths") or {}
    if key not in paths:
        raise KeyError(
            f"paths.{key} is not defined in {cfg.get('_config_path')}. "
            f"Known keys: {sorted(paths)}"
        )
    p = pathlib.Path(paths[key])
    return p if p.is_absolute() else repo_root() / p
