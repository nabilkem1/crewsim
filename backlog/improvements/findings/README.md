# Findings — Code Analysis Follow-up

**Source:** code analysis of the working tree (October 2026), after the improvements backlog in
[../README.md](../README.md) was written. The format is the same as the rest of `backlog/improvements/`.
Story ids continue each epic's numbering (see *Story id scheme* in the parent README).

> These stories are **not yet in `stories.yaml`**, so `verify.py` cannot see them.

| File | Stories | Theme |
|---|---|---|
| [01_correctness_findings.md](01_correctness_findings.md) | IMP-116, IMP-117, IMP-118, IMP-119, IMP-213, IMP-412 | Wrong or unverifiable results. It also lists 7 correctness issues already covered by existing stories. |
| [02_housekeeping.md](02_housekeeping.md) | IMP-612 | Committed artifacts, dead code, stale comments, duplicated logic, uncommitted work |

## Story index

| Story | Title | Size | Category | Status | Note |
|---|---|---|---|---|---|
| IMP-116 | L8 notice uses the same reserve block as eligibility | S | Must fix | DONE | Cost effect under 0.6%. R6/R8, R* and the V1–V9 re-run are still open. |
| IMP-117 | Long-call reserves are either usable or not bought | M | Verify first | DONE | Measured: long-call reserves are used (R10: 41 assignments/scenario). New SC/LC usage KPI. |
| IMP-118 | Reserve bid rule, comment and test agree | S | Must fix | DONE | `senior_first` raises E[C] by 41–78%; R* unchanged (4). Confirmed 2026-10-20. |
| IMP-119 | A reserve shortfall is reported, not silent | S | Should | DONE | |
| IMP-213 | Swept and declared parameters have an effect | M | Should | DONE | `roster_size` reported as NOT_EXERCISED |
| IMP-412 | Version is the same installed or not | S | Should | DONE | |
| IMP-612 | Housekeeping | M | Optional | DONE | Spec HTML, committing the deletions and untracked files: won't do, owner's decision |

## Suggested order

1. **IMP-118:** restores a green test suite.
2. **IMP-116, then IMP-117:** IMP-116 changes long-call utilisation, so measure IMP-117 after it.
3. **IMP-412, IMP-119:** cheap.
4. **IMP-213:** before V9 is used as sign-off evidence.
5. **IMP-612:** with IMP-607 and IMP-611.

## Decisions needed

| Story | Question | Owner | Interim decision |
|---|---|---|---|
| IMP-117 | What is the long-call notice (D12 says 12 h, the working tree says 14 h)? Are long-call reserves on longer shifts than short-call? | Crew Planning | 14 h, set in `configs/base.yaml` only |
| IMP-118 | Does a reserve bid take the most junior or the most senior crew? | Crew Planning | **Confirmed 2026-10-20:** `senior_first` |
