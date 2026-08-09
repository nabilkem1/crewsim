"""Shared engine-test fixtures.

`legality_cfg()` returns the REAL configs/base.yaml, not a hand-built stand-in.

Three test modules previously each kept their own SimpleNamespace mirroring
base.yaml's `legality` block. Being copies, they went stale the moment a rule
gained a knob: adding L1/L2's max_duty_hours / min_rest_hours_home / _away
broke all three at once, and -- worse -- a copy that merely *drifted* (an
out-of-date limit rather than a missing field) would have kept passing while
testing a rule the engine no longer implements. Loading the real config makes
that class of drift impossible.
"""
from __future__ import annotations

import pytest

from crewsim import config


@pytest.fixture(scope="session")
def base_cfg():
    return config.load()


def legality_cfg():
    """Plain function, not a fixture: the engine tests call this from inside
    helper functions and parametrised bodies where a fixture argument would not
    reach."""
    return config.load()
