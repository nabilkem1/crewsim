# Low-Risk Improvements

These stories came out of the October 2026 code review. They don't block a trustworthy
**single-user, localhost** result today. The must-fix stories are in the parent folder
([../README.md](../README.md)).

"Low risk" doesn't mean "never". Each story below has a **trigger**: the condition under which it
moves up to must-fix. Re-check the triggers whenever the way the tool is used changes.

## Categories

| Category | Meaning |
|---|---|
| **Conditional** | Becomes must-fix when its trigger applies (deployment, multiple users, an SME/data answer) |
| **Should** | Improves statistical soundness or trust in the gates. Do it before formally defending the recommendation. |
| **Verify first** | Found by reading the code. Write the failing test first; it may turn out to be intended behaviour or very rare. |
| **Optional** | Code quality or speed. No change to results. |

---

## Story index

### [05_engine_correctness.md](05_engine_correctness.md)
| Story | Title | Size | Category | Trigger / note |
|---|---|---|---|---|
| IMP-106 | Rolling limits look forward | M | Should | Matters when rosters are dense near limits |
| IMP-107 | L2 rest before minute 0 | S | Should | Affects day-1 assignments only |
| IMP-108 | Cross-base reserves not double-booked | M | Verify first | Only when `allow_cross_base_reserve` is on |
| IMP-109 | REDUCED mode keeps broken pairings | S | Conditional | Only if REDUCED mode is used |
| IMP-110 | One attempt and one eligibility sample per late item | S | Should | Biases the V3 sample weighting |
| IMP-111 | Cross-base minutes outside the V2 offered load | S | Conditional | Only with cross-base enabled |
| IMP-112 | Validate lag ≥ lead | S | Optional | Not triggered by current config values |
| IMP-113 | Absent crew lose drafted/reserve duties | M | Should | Reserve sickness isn't simulated today |
| IMP-114 | Multi-day pairings broken whole | M | Conditional | Pending SME answer |
| IMP-115 | Policy-independent random-number keys | M | Should | Reduces the noise in policy comparisons |

### [06_calibration_statistics.md](06_calibration_statistics.md)
| Story | Title | Size | Category | Trigger / note |
|---|---|---|---|---|
| IMP-202 | Headcount offset in the sick-call model | M | Should | Biggest statistical improvement |
| IMP-203 | Absence types in scope | S | Conditional | Pending SME decision |
| IMP-204 | Delay distribution with positive support | M | Should | Ambient delay is excluded from E[C], so the impact is limited |
| IMP-205 | Consistent handling of cancelled flights | S | Should | |
| IMP-206 | Regime model: correct initial distribution, kept diagnostics, accurate docs | S | Should | |
| IMP-207 | Clear errors on empty/degenerate data | M | Optional | Only bites with sparse or new data |
| IMP-208 | Refuse unconverged or holdout-leaking store | S | Should | Cheap safety net |
| IMP-209 | CIs that account for correlation | M | Should | Before formal V&V sign-off |
| IMP-210 | V3/V4 compare like with like | M | Should | Before formal V&V sign-off |
| IMP-211 | Calibration fit-quality gate | L | Should | Before formal V&V sign-off |
| IMP-212 | V9 stable and guarded | S | Should | |

### [07_api_security_privacy.md](07_api_security_privacy.md)
| Story | Title | Size | Category | Trigger / note |
|---|---|---|---|---|
| IMP-301 | Policy name allow-list | S | Conditional | **Cheap; do it anyway.** Must-fix before any shared deployment |
| IMP-302 | API authentication | M | Conditional | API reachable by anyone else |
| IMP-304 | Bounded request inputs | S | Conditional | Shared deployment |
| IMP-305 | No path or exception leaks | S | Conditional | Shared deployment |
| IMP-306 | Escaped HTML and a CSP header | S | Conditional | Data-derived labels reach the HTML |
| IMP-307 | Validate dataset names first | S | Conditional | Shared deployment |

### [08_jobs_concurrency_robustness.md](08_jobs_concurrency_robustness.md)
| Story | Title | Size | Category | Trigger / note |
|---|---|---|---|---|
| IMP-401 | Remove the demo worker | S | Conditional | **Affects a single user too**, if Retry is used |
| IMP-402 | A cancel can't be overwritten | M | Conditional | Cancelling jobs |
| IMP-403 | Atomic writes and unique temp files | S | Conditional | Two jobs at once |
| IMP-404 | Safe error handlers | S | Should | Jobs stuck in `running` |
| IMP-405 | Non-blocking SSE | S | Conditional | Several open job pages |
| IMP-406 | Job concurrency limit | M | Conditional | Multiple users |
| IMP-407 | Tape cache invalidated on recalibration | S | Conditional | Recalibrating while the API runs |
| IMP-408 | Delete cancels first | S | Conditional | Deleting running jobs |
| IMP-409 | Cheap, side-effect-free GETs | M | Optional | |
| IMP-411 | CLI errors instead of tracebacks | M | Optional | |

### [09_data_reporting_correctness.md](09_data_reporting_correctness.md)
| Story | Title | Size | Category | Trigger / note |
|---|---|---|---|---|
| IMP-501 | Time-zone-aware UTC columns | S | Conditional | Prerequisite for 502/503 |
| IMP-502 | D4 times converted to UTC | M | Conditional | **Must-fix if the data owner confirms D4 is local time** (V3 target off by 4–5 h) |
| IMP-503 | Per-duty UTC offsets | M | Conditional | Pending data-owner answer |
| IMP-504 | Quality gate matches the reconstruction | S | Should | |
| IMP-505 | Real recall and precision | M | Should | Needs event ids in the ground truth |
| IMP-506 | Unbiased cascade target | M | Should | Affects V4 |
| IMP-507 | Correct profile statistics | M | Optional | Descriptive profile only |
| IMP-508 | Computed narrative claims | S | Optional | |
| IMP-509 | One R* everywhere | S | Should | Report and UI could disagree |
| IMP-510 | Tape shows each event once | S | Optional | |
| IMP-511 | Window and docs consistency | S | Optional | |

### [10_maintainability_performance.md](10_maintainability_performance.md)
| Story | Title | Size | Category | Trigger / note |
|---|---|---|---|---|
| IMP-601 | Load rosters once per policy | M | Optional | **Do first if large grids are slow** |
| IMP-602 | Window rows computed once | S | Optional | |
| IMP-603 | Legality cheapest-first | S | Optional | |
| IMP-604 | Shared CLI/API services | M | Optional | Prevents CLI/API drift |
| IMP-605 | Split `cli.main` | L | Optional | |
| IMP-606 | Break up long functions | M | Optional | |
| IMP-607 | Remove dead code | S | Optional | |
| IMP-608 | Stronger typing | S | Optional | Required by Definition of Done item 4 |
| IMP-609 | Re-enable Ruff complexity rules | S | Optional | |
| IMP-610 | Shared constants | S | Optional | |
| IMP-611 | Repository hygiene | S | Optional | |

---

## Suggested pick-up order (after the must-fix stories)

1. **Quick wins:** IMP-301, IMP-401, IMP-208, IMP-509, all size `S`
2. **Before formal V&V sign-off:** IMP-202, IMP-209, IMP-210, IMP-211, IMP-115
3. **As soon as the SME and data-owner answers arrive:** IMP-114, IMP-203, IMP-502, IMP-503
4. **Before any shared deployment:** the rest of `07_api_security_privacy.md` and `08_jobs_concurrency_robustness.md`
5. **When convenient:** epic 06
