"""WN-008: on-demand per-policy drill-down (api/routers/processing.py's
launch_drilldown). The real generation path (run_drilldown_job actually
tracing scenarios) is exercised live, not here -- these cover the request-time
validation, matching the style of test_processing_guards.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from crewsim.api.routers import processing


def test_launch_drilldown_404_when_batch_job_missing():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        processing.launch_drilldown("nonexistent", "R4", MagicMock(), db=db)
    assert exc_info.value.status_code == 404


def test_launch_drilldown_400_when_batch_job_not_completed():
    source = MagicMock(status="running", results=None)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = source
    with pytest.raises(HTTPException) as exc_info:
        processing.launch_drilldown("job-1", "R4", MagicMock(), db=db)
    assert exc_info.value.status_code == 400
    assert "not completed" in exc_info.value.detail


def test_launch_drilldown_400_when_policy_not_in_scoreboard():
    source = MagicMock(
        status="completed",
        results={"scoreboard": [{"policy": "R6"}, {"policy": "R10"}], "num_scenarios": 10, "season": "winter_sun"},
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = source
    with pytest.raises(HTTPException) as exc_info:
        processing.launch_drilldown("job-1", "R4", MagicMock(), db=db)
    assert exc_info.value.status_code == 400
    assert "R4" in exc_info.value.detail


def test_launch_drilldown_reuses_the_source_jobs_own_scenario_count_and_season():
    """The whole point (see run_drilldown_job's own docstring): this must hit
    the SAME cached CRN scenario set the scoreboard's numbers came from, not
    a fresh unrelated draw -- so it must pass the source job's own
    num_scenarios/season through, never re-derive or default them."""
    source = MagicMock(
        status="completed",
        results={"scoreboard": [{"policy": "R4"}], "num_scenarios": 37, "season": "shoulder"},
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = source
    background_tasks = MagicMock()

    result = processing.launch_drilldown("job-1", "R4", background_tasks, db=db)

    assert result["status"] == "queued"
    background_tasks.add_task.assert_called_once()
    args = background_tasks.add_task.call_args[0]
    assert args[0] is processing.run_drilldown_job
    assert args[2] == "R4"
    assert args[3] == 37  # source job's num_scenarios, not a default
    assert args[4] == "shoulder"  # source job's season, not the configured default
