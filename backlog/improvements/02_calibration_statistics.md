# IMP-E2 — Calibration & Statistical Validity

**1 story** · **Must fix** · Gate: parameter store reproducible byte-for-byte.
The remaining calibration stories (IMP-202 to IMP-212) are in [low_risk/06_calibration_statistics.md](low_risk/06_calibration_statistics.md).

Calibration feeds every scenario, so any bias here reaches every number in the report. The gates
are meant to catch that, but several of their confidence intervals are too narrow, which makes
their verdicts overconfident.

---

## [DONE] IMP-201 — Parameter-store hash is deterministic
**Size:** `S` | **Depends on:** — | **Source:** `calibration/pipeline.py:79,119-121`

**As a** researcher **I want** the same data and config to produce the same parameter hash
**so that** the scenario cache is invalidated only when parameters really change.

### Acceptance Criteria
- [x] `fitted_at` (and any other run metadata) is excluded from the hashed content and stored alongside it
- [x] Two runs of `crewsim calibrate --season winter_sun --emit` on unchanged inputs produce the same `content_hash` (verified: `blake2b:746926b1…` both times)
- [x] The test no longer needs to monkeypatch `datetime`
- [x] Design-matrix row order is fixed (explicit sort before fitting) so floats are bit-stable

### Verification
*   **Automated:** `pytest tests/calibration/test_calibrator_pipeline.py`
*   **Manual:** run `crewsim calibrate --season winter_sun --emit` twice
    *   **Expect:** the same `content_hash` printed both times
    *   **Fails if:** the hashes differ

### How it was implemented
- `pipeline.content_hash(store)` hashes the store after dropping `RUN_METADATA_KEYS` (`fitted_at`, `content_hash`, `_saved_path`). `fitted_at` is added only after hashing.
- `nhpp.fit_sick_calls` sorts the design matrix by every key column before fitting.
- The test now writes to `tmp_path`, not `/tmp`. `/tmp` does not exist on Windows, so the test could never pass there. It also checks that changing content changes the hash.
- Side effect: the first recalibration after this change produces a new hash, so the scenario cache rebuilds once.
