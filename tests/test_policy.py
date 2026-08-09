"""S1a-09 -- serialisable policy, hash-pinned.

At tests/test_policy.py, not tests/engine/, because that is the path this
story's own documented automated check names (`pytest tests/test_policy.py`) --
which previously collected nothing at all.
"""
from __future__ import annotations

import itertools
import tempfile
from pathlib import Path

import yaml

from crewsim import config
from crewsim.engine.policy import Policy, load_policy

POLICY_DATA = {
    "policy_id": "test",
    "costs_file": "costs_pilots.yaml@v3.2.1",
    "stage1": {
        "reserves": [
            {"base": "YUL", "fleet": "A330", "position": "FO", "dow": [1, 2],
             "short_call": 1, "long_call": 1}
        ]
    },
    "stage2": {"allow_cross_base_reserve": True, "reserve_selection": "shortest"},
    "mode": "FULL",
    "season": "winter",
}


_TMP = Path(tempfile.mkdtemp(prefix="crewsim-policy-"))
_SEQ = itertools.count()


def _write(data: dict) -> Path:
    path = _TMP / f"policy_{next(_SEQ)}.yaml"
    path.write_text(yaml.safe_dump(data))
    return path


def test_policy_hash_is_stable_across_loads() -> None:
    h1 = load_policy(_write(POLICY_DATA)).get_hash()
    h2 = load_policy(_write(POLICY_DATA)).get_hash()
    assert h1 == h2
    assert isinstance(h1, str) and len(h1) == 12


def test_policy_round_trips_through_yaml_and_keeps_its_hash() -> None:
    """AC1's "round-trips through YAML" -- previously untested: the old version
    dumped the same hand-written dict twice, which never exercised the
    Policy -> YAML direction at all."""
    original = load_policy(_write(POLICY_DATA))

    dumped = _write(original.model_dump(mode="json"))
    reloaded = load_policy(dumped)

    assert reloaded == original
    assert reloaded.get_hash() == original.get_hash()


def test_hash_changes_when_any_field_changes() -> None:
    """A hash that ignores a field cannot pin a result to its policy."""
    base = load_policy(_write(POLICY_DATA)).get_hash()

    for mutation in (
        {"policy_id": "different"},
        {"costs_file": "costs_pilots.yaml@v9.9.9"},
        {"mode": "LITE"},
        {"season": "summer"},
    ):
        assert load_policy(_write({**POLICY_DATA, **mutation})).get_hash() != base, mutation

    deeper = {**POLICY_DATA, "stage1": {"reserves": [
        {**POLICY_DATA["stage1"]["reserves"][0], "short_call": 7}
    ]}}
    assert load_policy(_write(deeper)).get_hash() != base


def test_every_shipped_policy_pins_a_costs_version() -> None:
    """AC2: "pinned to a costs_*.yaml version". A policy naming a bare costs
    file has nothing to regenerate against a year from now."""
    for path in sorted((config.repo_root() / "configs" / "policies").glob("*.yaml")):
        policy = load_policy(path)
        assert "@" in policy.costs_file, (
            f"{path.name} names {policy.costs_file!r} with no @version pin"
        )


def test_counterfactual_keys_cannot_enter_a_policy_file() -> None:
    """S1a-08's AC, enforced here because it is a property of the Policy model:
    junior_first must be structurally impossible to select via YAML."""
    import pytest
    from pydantic import ValidationError

    for bad in ("junior_first", "draft_mode", "myopic_total_cost"):
        with pytest.raises(ValidationError):
            Policy(**{**POLICY_DATA, bad: True})
