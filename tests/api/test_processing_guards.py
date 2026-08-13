"""api/routers/processing.py's request-time guards.

`_refuse_if_reduced_batch` is the API-side counterpart to cli.py's own
`_refuse_if_reduced` (S1c-01 AC4): a batch run's scoreboard feeds the Results
& Reports policy comparison/recommendation surface, so it must refuse under
REDUCED mode exactly as `crewsim grid`/`report`/`gate v9` already do -- a
recommendation derived from Bernoulli(p_elig) is a coin flip, not a weaker
recommendation.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from crewsim import config
from crewsim.api.routers import processing


def test_reduced_mode_refuses_a_batch_run(monkeypatch: pytest.MonkeyPatch) -> None:
    real_cfg = config.load()
    reduced_cfg = real_cfg.model_copy(update={"mode": "REDUCED"})
    monkeypatch.setattr(config, "load", lambda: reduced_cfg)

    with pytest.raises(HTTPException) as exc_info:
        processing._refuse_if_reduced_batch(season=None)
    assert exc_info.value.status_code == 400
    assert "REDUCED mode" in exc_info.value.detail


def test_full_mode_allows_a_batch_run(monkeypatch: pytest.MonkeyPatch) -> None:
    real_cfg = config.load()
    full_cfg = real_cfg.model_copy(update={"mode": "FULL"})
    monkeypatch.setattr(config, "load", lambda: full_cfg)

    processing._refuse_if_reduced_batch(season=None)  # must not raise


def test_season_override_is_checked_against_the_overridden_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard must evaluate the SAME cfg the worker will actually run
    with -- checking mode on the pre-override cfg would be checking a
    config the run never uses."""
    real_cfg = config.load()
    reduced_cfg = real_cfg.model_copy(update={"mode": "REDUCED"})
    monkeypatch.setattr(config, "load", lambda: reduced_cfg)

    with pytest.raises(HTTPException):
        processing._refuse_if_reduced_batch(season=real_cfg.scope.season)


def test_single_run_job_type_is_not_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    """processing_single is a one-policy smoke test (cli.py's `run`/`compare`
    precedent), not a recommendation -- _queue must only gate 'processing_batch'."""
    from unittest.mock import MagicMock

    real_cfg = config.load()
    reduced_cfg = real_cfg.model_copy(update={"mode": "REDUCED"})
    monkeypatch.setattr(config, "load", lambda: reduced_cfg)
    monkeypatch.setattr(processing, "run_processing_job", lambda *a, **k: None)

    db = MagicMock()
    background_tasks = MagicMock()
    result = processing._queue(db, background_tasks, "processing_single", ["R6"], 10, None, 1)
    assert result["status"] == "queued"  # must not raise under REDUCED mode

    with pytest.raises(HTTPException):
        processing._queue(db, background_tasks, "processing_batch", ["R6", "R10"], 10, None, 1)
