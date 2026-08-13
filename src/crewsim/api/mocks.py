"""One way to say "this response is not real output".

`src/crewsim/api/` shipped several endpoints whose bodies were hardcoded
literals, served over the same JSON shape as real results and therefore
indistinguishable from them at the UI. Three of those routers were deleted
outright rather than filled in; the ones that remain declare themselves here.

The convention follows what `gates/v5_trace.py` already established on the
simulation side: placeholder output is allowed to exist, but it must announce
itself in the payload so no caller can render it as a measured figure by
accident.

Note what `not_implemented` does *not* do: it does not carry plausible sample
values. An endpoint with nothing real to report returns an empty collection.
Invented business figures in `src/` are precisely what
`tests/test_config.py::test_no_numeric_constant_outside_configs` exists to
catch, and a `mock: true` flag next to a fabricated dollar amount still leaves
the dollar amount on screen for anyone who misses the banner.
"""

from __future__ import annotations

from typing import Any

IMPLEMENTED_FIELD = "implemented"
NOTICE_FIELD = "notice"


def not_implemented(payload: dict[str, Any], notice: str) -> dict[str, Any]:
    """Tag `payload` as a declared-but-unimplemented endpoint.

    `payload` should carry empty collections or nulls in place of the data --
    enough for the caller to keep its shape, with nothing invented in it.
    """
    return {**payload, IMPLEMENTED_FIELD: False, NOTICE_FIELD: notice}
