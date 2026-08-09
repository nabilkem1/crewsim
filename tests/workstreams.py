"""Trees that the repo-wide source guards deliberately skip.

`src/crewsim/api/` is the web-API workstream (backlog/mvp/web/), under active
development by a separate stream. The guards in tests/test_config.py (no numeric
constant outside configs/) and tests/test_project_structure.py (no hard-coded
data paths in src/) scan the whole package, so without this the slice-1a CI
would be permanently red on another stream's in-flight files -- which is how a
CI signal becomes something people learn to ignore.

This is a scheduling carve-out, NOT an exemption from the rules. Both rules
apply to that tree and it currently breaks both:

  * api/routers/results.py returns hardcoded simulation results
    ("Baseline Simulation", 12,500 events, 0.98 success rate) that no engine
    ever produced -- exactly the fabricated-evidence pattern the numeric guard
    exists to catch.
  * api/routers/provenance.py hardcodes "s3://bucket/data.csv" as a data
    source, which is the literal-path defect the other guard exists to catch.

test_config.py::test_api_exclusion_is_still_necessary fails the moment the tree
stops tripping these, so the carve-out cannot quietly outlive its reason.
"""
from __future__ import annotations

EXCLUDED_TREES = ("src/crewsim/api",)


def is_excluded(rel_path: str) -> bool:
    """True if `rel_path` (repo-relative, posix) is inside an excluded tree."""
    return any(rel_path.startswith(t) for t in EXCLUDED_TREES)
