# Improvements Backlog — Code Review Remediation

**Source:** code review of `src/crewsim/` (October 2026). Each story is traceable to the specific
`file:line` evidence that motivated it.
**Format:** same as `backlog/mvp/`. Each story has a user story, acceptance criteria, an automated
check and a manual check (≤ 60 seconds). See `backlog/README.md` → *Definition of done*.

> These stories are **not yet in `stories.yaml`**, so `verify.py` cannot see them. Add them
> there (ids `IMP-xxx`) when an epic is scheduled.

---

## Layout

This folder holds the **must-fix** stories: the ones that make results wrong, or expose data,
today. Everything else is in [low_risk/](low_risk/README.md), where each story has a category
(Conditional / Should / Verify first / Optional) and a trigger that would make it must-fix.

| File | Stories | Theme |
|---|---|---|
| [01_engine_correctness.md](01_engine_correctness.md) | IMP-101 to IMP-105 | Simulation produces the wrong events or illegal calendars |
| [02_calibration_statistics.md](02_calibration_statistics.md) | IMP-201 | Parameter hash is not reproducible |
| [03_api_security_privacy.md](03_api_security_privacy.md) | IMP-303 | Personal data in the package folder |
| [04_jobs_concurrency_robustness.md](04_jobs_concurrency_robustness.md) | IMP-410 | HTML reports crash on Windows |
| [low_risk/](low_risk/README.md) | 59 stories | Conditional, should-fix, verify-first and optional work |
| [findings/](findings/README.md) | 7 stories | Follow-up code analysis: correctness (IMP-116 to 119, IMP-213, IMP-412) and housekeeping (IMP-612) |

---

## Must-fix stories (about 5–6 days)

| # | Story | Size | Why it's must-fix |
|---|---|---|---|
| 1 | IMP-101 Sort within-day sick-call arrivals | S | Distorts every scenario's arrival timing |
| 2 | IMP-102 Reserve duties carry flight minutes | S | L3 flight limit silently undercounts for reserves |
| 3 | IMP-103 Drafting clears TRAINING/SIMULATOR | S | Produces double-booked calendars |
| 4 | IMP-105 Sick calls don't break pairings under way | S | Inflates cancellations with already-late items |
| 5 | IMP-104 No drafting mid-trip or without notice | M | Same; needs SME answer on the notice period |
| 6 | IMP-201 Deterministic parameter-store hash | S | Every recalibration invalidates the scenario cache |
| 7 | IMP-303 Keep real data out of git and the wheel | S | Passenger names one `git add .` away from the repo |
| 8 | IMP-410 UTF-8 for all file I/O | S | Both HTML reports crash on Windows |

**Re-baseline after the must-fix stories.** IMP-101 to IMP-105 change simulated costs. Re-run gates V1–V9 and
record the before and after figures for E[C], CVaR95 and R* in the story's sign-off. A changed
recommendation is an expected outcome, not a regression.

---

## Story id scheme

`IMP-<epic><nn>`: `IMP-1xx` engine, `2xx` calibration, `3xx` security, `4xx` jobs/robustness,
`5xx` data/reporting, `6xx` maintainability.

## Sizes

`S` ≈ half a day · `M` ≈ 1–2 days · `L` ≈ 3–5 days. Anything larger is split.

## Stories that need a decision before building

| Story | Question | Owner |
|---|---|---|
| IMP-104 | May a line holder be drafted while a pairing is in progress? Is there a minimum notice for line holders? | Crew scheduling SME |
| IMP-114 *(low_risk)* | When a sick call hits one duty period of a multi-day pairing, is the whole pairing reopened? | Crew scheduling SME |
| IMP-203 *(low_risk)* | Should the "sick-call" model include FAMILY and INJURY absences? | Crew planning / data owner |
| IMP-302 *(low_risk)* | Which authentication mechanism: API key, Entra ID, or reverse-proxy auth? | Platform owner |
| IMP-503 *(low_risk)* | Are D3 `*_local` times in the base's time zone or the outstation's? | Data owner |
