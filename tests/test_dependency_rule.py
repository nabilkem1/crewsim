"""S0-00b — the engine must not import simpy.

`des.py` orchestrates; every other engine module is a pure function library over
plain dataclasses (§4.2). That is what lets the legality surrogate be tested with
hypothesis in microseconds instead of spinning up a SimPy Environment — the
difference between a suite that runs in ~4 seconds and one that runs in ~4 minutes.
"""
from __future__ import annotations

import re

from crewsim import config

ENGINE = config.repo_root() / "src" / "crewsim" / "engine"
ALLOWED = {"des.py"}                      # the orchestration layer, and only it
IMPORT_SIMPY = re.compile(r"^\s*(import\s+simpy|from\s+simpy\b)", re.MULTILINE)


def test_engine_modules_do_not_import_simpy() -> None:
    offenders = [
        p.name for p in ENGINE.glob("*.py")
        if p.name not in ALLOWED and IMPORT_SIMPY.search(p.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        f"engine modules importing simpy: {offenders}. "
        f"Only des.py may. Move the orchestration into des.py and keep the "
        f"engine a pure library."
    )


def test_des_is_the_designated_orchestrator() -> None:
    assert (ENGINE / "des.py").is_file(), "engine/des.py is missing (§4.2)"
