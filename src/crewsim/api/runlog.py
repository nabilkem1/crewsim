"""The execution log a processing job writes as it runs.

Every line here is a record of something that happened, written after it
happened, with values read back from the thing that did it -- the parameter
store's real version and hash, the real wall-clock duration, the real scenario
and policy counts. Nothing is narrated alongside the run.

That constraint is the point. A "[1/4] loading parameter store params_v3.2.1"
line that was hardcoded next to the code that loads the store would be
indistinguishable from one that reports it, and this codebase has already paid
for that class of mistake several times over (see the API/web-UI review in git
history: `git show 7b34d3b:CODE_REVIEW_API_WEBUI.md`).
So `detail` is always derived, and when a value is unavailable the line says so
-- `params_version: MISSING` is a real, common state on a fresh checkout, and it
is reported rather than smoothed over.
"""

from __future__ import annotations

import time
from typing import Any

# Wall-clock seconds are a measurement, not a business input; 1000 is the
# millisecond conversion used for display only.
_MS_PER_SECOND = 1000


class RunLog:
    """Append-only step log with real timings, persisted after every write.

    `flush` is called with the current list on every change so the worker can
    commit it to the job row -- the SSE endpoint reads that row, so a step is
    visible to the browser as soon as it is recorded rather than at the end.
    """

    def __init__(self, total_steps: int, flush: Any) -> None:
        self.total_steps = total_steps
        self._flush = flush
        self._entries: list[dict[str, Any]] = []
        self._step = 0
        self._started_at: float | None = None
        self._last_flush = 0.0

    @property
    def entries(self) -> list[dict[str, Any]]:
        return list(self._entries)

    def start(self, message: str, detail: str | None = None) -> None:
        """Open a step. Its duration is measured when `done` is called."""
        self._step += 1
        self._started_at = time.monotonic()
        self._entries.append(
            {
                "step": self._step,
                "total": self.total_steps,
                "message": message,
                "detail": detail,
                "status": "running",
                "duration_ms": None,
                "progress_done": None,
                "progress_total": None,
                "artifact": None,
            }
        )
        self._last_flush = time.monotonic()
        self._flush(self.entries)

    def progress(self, done: int, total: int, detail: str, min_interval_s: float = 0.4) -> None:
        """Update the open step's live counters.

        Throttled by wall clock: a 5-policy x 1000-scenario grid would
        otherwise commit 5,000 times and push 5,000 SSE frames for a bar that
        can only render ~100 distinct positions. The final call is never
        dropped -- `done == total` always flushes -- so the step cannot be left
        showing a stale count.
        """
        if not self._entries:
            return
        entry = self._entries[-1]
        entry["progress_done"] = done
        entry["progress_total"] = total
        entry["detail"] = detail

        now = time.monotonic()
        if done >= total or now - self._last_flush >= min_interval_s:
            self._last_flush = now
            self._flush(self.entries)

    def done(self, detail: str | None = None) -> None:
        """Close the open step with its measured duration."""
        if not self._entries:
            return
        entry = self._entries[-1]
        if self._started_at is not None:
            entry["duration_ms"] = int((time.monotonic() - self._started_at) * _MS_PER_SECOND)
        entry["status"] = "done"
        if detail is not None:
            entry["detail"] = detail
        self._flush(self.entries)

    def note(self, message: str, level: str = "info", artifact: str | None = None) -> None:
        """A line that is not a step -- a warning, a gate verdict, a file written.

        `artifact` is the BARE FILENAME of something the run produced, carried
        as data rather than embedded in `message`. The UI turns it into a
        download link; parsing a path back out of prose would break the first
        time the wording changed, and putting a URL here would hard-code the
        API's routing into the log.
        """
        self._entries.append(
            {
                "step": None,
                "total": self.total_steps,
                "message": message,
                "detail": None,
                "status": level,
                "duration_ms": None,
                "progress_done": None,
                "progress_total": None,
                "artifact": artifact,
            }
        )
        self._flush(self.entries)

    def fail(self, message: str) -> None:
        """Mark the open step failed and record why."""
        if self._entries and self._entries[-1]["status"] == "running":
            entry = self._entries[-1]
            entry["status"] = "failed"
            if self._started_at is not None:
                entry["duration_ms"] = int((time.monotonic() - self._started_at) * _MS_PER_SECOND)
        self.note(message, level="error")
