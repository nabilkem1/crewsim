# Migration plan: CrewSim reads AIMS (TSC) live; Pierre supplies only what AIMS lacks

Date 2026-11-03. **Planning only - nothing was implemented** (no CrewSim code changed, nothing written to AIMS; the only new files are documents and CSV templates in this folder). Inputs: the semantic layer, the four corpus feasibility files, read-only checks on TSC, and a read of the CrewSim loader/config code.

## 0. Decisions taken (2026-11-03)

| # | Decision | Consequence in this plan |
|---|---|---|
| 1 | **Snapshot-first** (live read for development only) | Section 2 as designed; snapshot id in provenance. |
| 2 | **Published roster** (`PROSTER`) is D2's state; as-of (`LOG_ROSTER`) only for event timing | Phase 1 must measure the `PROSTER` publication cadence; D2 will differ from v3 and the difference is reported. |
| 3 | **Pseudonyms: Pierre's v3 key (option A), hosted in `CrewSchedAI` (option C), schema `sim`** (never `dbo`) | Table `sim.crew_key_map`; extraction SQL joins it so CrewSim never sees raw ids; unmapped id = extraction fails. Draft DDL (not executed): [sim_ddl/sim_schema.sql](sim_ddl/sim_schema.sql). The same schema also hosts `sim.activity_code_map` (M01), `sim.user_group_map` (M02), `sim.aircraft_subfleet` (H03). |
| 4 | **Simulate pilots only; cabin-ready by design** | Extraction takes a `crew_group` parameter, validated for pilots only; H01 asked for pilots AND cabin; cabin supplements deferred. |
| 5 | **Extraction SQL = versioned `.sql` files in the CrewSim repo (option a)** | Run by the adapter with a read-only login; because database chaining is OFF on TSC and CrewSchedAI the account needs explicit SELECT on the TSC objects used (list them in each SQL file header) and on `sim`. |
| 6 | Window = what AIMS has (reliable from 2024-05-14); questions for Pierre prepared | [PIERRE_QUESTIONS.md](PIERRE_QUESTIONS.md). |

**Environment note:** the AIMS server reached from here (`PPR-MTLSQLAIMS1\AIMS`, databases `TSC` and `CrewSchedAI`) is the **QAS** environment; the user has administrative rights on it. Its journals are written up to the current day, so it is not a stale restore - how it is fed from production is Question 1 to Pierre. Everything in this plan was developed and checked against QAS; production parity must be confirmed before go-live. The instance is SQL Server 2022 without an availability group (no readable secondary).
## 1. Verdict

**Feasible, with one structural condition and one external dependency.**

* *Condition:* a live read must not mean "every CrewSim run queries production". CrewSim's guarantees (reproducible fits, content-hashed parameter store, common random numbers) need a **frozen input**, and AIMS is mutable (the current `ROSTER` changes daily). So: **extract from AIMS into a versioned snapshot, then read the snapshot** (live read stays available for development).
* *Dependency:* money, agreement parameters, HR facts and a few classifications are not in AIMS (D7 dollars, D10 amounts, D12, hire/termination/status, cancellation cause). They come from Pierre in the 21 supplement files specified in [PIERRE_SUPPLEMENT_SPEC.md](PIERRE_SUPPLEMENT_SPEC.md). Until they arrive CrewSim keeps today's placeholders and says so in its reports (existing behaviour).

Scorecard:

| Area | Rating | Evidence / remark |
|---|---|---|
| Connectivity | GREEN | Connection verified from the dev machine (Windows auth, ODBC Driver 17 present). `pyodbc` is not in CrewSim's `.venv` yet; production needs a service account, not a personal admin login. |
| Operational datasets D1-D5, D8, D11 | GREEN/AMBER | Tested SQL sketches reproduce v3 closely (pairings 99.6-100 % monthly, call-outs +/-2, hours 0.2 %, trainings 0-2 %). Amber = conventions to sign off (block types, report/release, roster state). |
| History / as-of states | AMBER | Published roster since 2022-12-21; change journals since 2024-05-14 (`LOG` partly 2023-11-08). Reliable operational actuals start 2024-05-14 (see 3). |
| D6 schedule changes, drafts | AMBER | Events derivable; `reason_code` and `initiator` are heuristics (no reason field in AIMS). Draft marker itself is exact (`ROSTERDT`). |
| Money (D7, D10, D12, costs) | RED in AIMS | Hours and events only. Needs Pierre (P1 files). |
| Determinism / provenance | AMBER -> GREEN | Solved by snapshot + manifest. |
| Server load / safety (QAS now, production later) | AMBER | 5-year pilot `ROSTER` is only ~1.3 M rows, but some AIMS tables are huge (`MSTLOGCRW` 260 M, `CREXPLOG` 1.8 B). Use a replica / off-peak, month-chunked, index-friendly queries, read-only intent. |
| Privacy (Law 25) | AMBER | AIMS ids look like employee numbers: pseudonymise inside the extraction layer, never persist raw ids; key table H01 from Pierre. |
| Testability / CI | GREEN | Keep the mock CSV corpus and the CSV loader for the 67 test files; AIMS adapter tested with recorded fixtures. |

## 2. Target architecture

```
 AIMS (TSC, read-only replica)                      Air Transat (Pierre) - supplement files
        |  SQL files (versioned, parametrised by window)         |  f01..f09, h01..h04, m01..m08 CSV
        v                                                        v
 [A] Extraction layer  (crewsim data extract --source aims)   [B] Supplement loader (strict schema, like load_dataset)
        |  pseudonymise (H01 map or keyed HMAC), UTC/local conversion, code maps (m01), sub-fleet (h03)
        v                                                        |
 [C] SNAPSHOT  <snapshot_id>/  d1..d11 in the SAME schemas as today  + MANIFEST.json (window, extracted_at,
        |        SQL hash, server, row counts, quality report, supplement versions)  <---------------+
        v
 existing `loaders.load_dataset(cfg, name)`  ->  calibration / simulation / gates / reports (unchanged contract)
```

* **One seam.** All CrewSim code reads data through `loaders.load_dataset(cfg, name)` (about 30 call sites), `config.dataset_path` (doctor, readiness, coverage, data API, regime) and `loaders.load_agreement_rules` (D12). Keeping the **declared schemas D1-D11 unchanged** means calibration, engine, gates and reports need no change; the migration lives behind the seam (a `data.source: csv | aims_snapshot | aims_live` setting).
* **Snapshot, not live, for results.** `aims_snapshot` (default for real runs): reads the files the extraction produced. `aims_live` (development only): the same extraction into memory; never used for reported results. `csv`: today's behaviour (mock corpus, v3 as regression fixture).
* **Provenance.** The snapshot id goes into the parameter store content hash and the run provenance, so every result names exactly which AIMS extraction it used.
* **Where the SQL lives.** Recommended: versioned `.sql` files in the CrewSim repo (parametrised by window), executed by the adapter with a read-only login. The existing `rpt.*` procedures in `CrewSchedAI` stay as they are. Views in `CrewSchedAI` are an option later if the DBA prefers central control.
* **Time.** AIMS minutes are UTC; journals and `NOTDATE/NOTIME` are server-local (Montreal) time -> one conversion module with DST handling, with D3/D8 local times recomputed from UTC per airport (as Pierre did) and D2 local = base-local.
* **Pseudonymisation** happens inside [A]; raw `ROSTER.ID` never leaves the extraction process. Two options: (1) H01 map supplied by Pierre (keeps v3 continuity, recommended), (2) keyed HMAC with a secret held by Air Transat (then v3 ids are not joinable).

## 3. Data window (relaxed as requested)

Accept what exists. Recommended window: **2024-05-14 -> latest available (about 29 months)**. Reason, measured on 2026-11-03:

* AIMS operational actuals are reliable only from **2024-05-14**: in the 100 days before that date 7,668 of 16,122 non-cancelled scheduled own legs (48 %) have no actual-times row (`LEGTIMES`), against 0 of 7,097 in the 100 days after. This is the same artefact behind v3's "79 % cancelled in the first week of April 2024" (Pierre derived `cancelled` from missing actuals).
* Surface (train) legs of carrier 1 (`FLTYPE 9`, 14,520 legs in that pre-period) are encoded differently before that date; own-leg counts drop from ~11 k to ~3 k per month at the boundary.
* The row-level change journals `LOG_ROSTER`/`LOG_ROSTERDT` start on 2024-05-14 (notification/call/draft timestamps); `LOG` is dense from 2024-03-14.
* Consequence for CrewSim: one complete winter per window (Dec 2024-Apr 2025 fitting, Dec 2025-Apr 2026 holdout), as in v3. Sick-code roster rows exist every month back to 2023-08 (about 220-380 pilot rows a month), so sick-call exposure *could* be extended for the NHPP alone, but D8 actuals (delay/regime model) cannot; recommend **not** extending, and revisit only if AIMS administrators confirm what changed on 2024-05-14 (ask: system migration/upgrade?).
* Pay data in AIMS is only 4 months (2026-06..09): payroll history must come from Pierre (F02) for as far back as it goes.

## 4. Final source map

| Dataset | Source after migration | From Pierre (supplement) |
|---|---|---|
| D1 crew master | AIMS (`CREWQUAL`, `ROSTERID`, positions), effective-dated | H02 (status, hire/termination, seniority), H04 (neoLR qualification), H01 (key) |
| D2 rosters | AIMS (`ROSTER`+`CRCODES`; state = published/as-of/current: decision needed) | M01 (code classification), M08 (conventions) |
| D3 pairings / legs | AIMS (`CRROUTE`,`CREWLEG`,`CRLEGGROUND`,`LEGMAIN`) | F07 (pay credit), M08 |
| D4 absences | AIMS (`ROSTER` sick codes, `LOG` notification, `PROSTER` affected pairing) | M01 (absence types) |
| D5 reserve call-outs | AIMS (`PROSTER`/`ROSTER`, `LOG`, first leg) | M05 (declined / no-show / released), M01 (SC/LC) |
| D6 schedule changes + draft export | AIMS (`LOG`, `LOG_ROSTER`, `ROSTERDT`) | M02 (initiator group), M06 (draft trigger), M04 (older journals) |
| D7 pay register | **Pierre** (AIMS gives hours only) - F02/F01/F03; AIMS `TIMEPNCPNT` used to reconcile | F01, F02, F03 |
| D8 flight movements | AIMS (`LEGMAIN`,`LEGTIMES`,`LEGDELAYS`,`DLYCD`) | M03 (cancellation cause), H03 (sub-fleet) |
| D9 | computed by CrewSim | - |
| D10 positioning | AIMS events (`HOTAC`, `CREWLEG.PAX`) + **Pierre** amounts | F05 |
| D11 training | AIMS (`ROSTER` training codes) | M07 (intervals, reschedule cost), M01 |
| D12 agreement rules | **Pierre** (AIMS has only reserve guarantee hours) | F04, F06, F03 |

## 5. Phased plan

| Phase | Content | Exit criterion | Depends on | Rough effort (1 developer; estimate) |
|---|---|---|---|---|
| 0 Access and governance | Create schema sim and the key/mapping tables in CrewSchedAI on QAS (draft DDL ready, not executed); read-only service account; reporting copy or off-peak window for production; `ApplicationIntent=ReadOnly`; DBA review of query load; Law 25 review of pseudonymisation and storage; decisions in section 8; send the Pierre request now | Account works from the CrewSim host; written approval; Pierre request sent | DBA, security, privacy officer | 1-2 weeks elapsed (waiting) |
| 1 Spike: AIMS -> CSV (old schemas) | Implement extraction SQL for D1-D5, D8, D11 into **the existing CSV schemas** for 2024-05-14..2026-08-31; run CrewSim on both the v3 files and the AIMS files and compare | Reconciliation report within thresholds (3) and `crewsim data readiness` passes on the AIMS corpus | Phase 0 (a dev login suffices to start) | 1.5-2 weeks |
| 2 Adapter and snapshot | `data.source` setting; extraction CLI with month chunking, retries, manifest, hashes; snapshot folder under `output/`; provenance in the parameter store; connection/driver packaging; recorded fixtures for tests | `crewsim calibrate` and `compare` run from a snapshot; same snapshot id -> same parameter store hash; CI green without a DB | Phase 1 | 2-3 weeks |
| 3 Supplements (parallel to 2) | Strict loaders for the f/h/m files (same style as `load_dataset`), reconciliation against AIMS, generation of `costs_*.yaml` and `real.yaml` pay-code maps from F01/F04/F06 with provenance, replacement of placeholders | Report lists which coefficients are real vs placeholder; V6 runs on real pay if F02 arrived | Pierre deliveries | 2 weeks after first files |
| 4 AIMS-only capabilities | Published/as-of roster for V3 (eligible reserves), real `notification_ts`, `ROSTERDT` draft export replacing D6 x D7 reconstruction, IATA delay codes, neoLR by registration (H03), cabin crew (phase 2 scope) | V3 gate computes on real events; draft counts agree with D6 `DRAFT` and pay | Phases 1-3 | 2-3 weeks |
| 5 Cutover | v3 files frozen as regression fixture; v3-specific limitations retired (`d8_cancel_artefact`, null notification, self-loops) and AIMS-specific ones added; runbook; monthly snapshot refresh | Team signs off; old path documented as fallback | Phase 4 | 1 week |

Total roughly 8-12 weeks elapsed for one developer, driven mostly by approvals (Phase 0) and by Pierre's deliveries (Phase 3); the technical risk is concentrated in Phases 1-2.

## 6. Acceptance thresholds (from the measured comparison with v3)

| Dataset | Check | Target |
|---|---|---|
| D3 pairings | monthly pairing count vs v3; `position_complement`, `duty_periods`, `days` | >= 99.5 %; 100 % on those three columns |
| D3 legs | `dep_local` equality on aligned legs | >= 96 % (v3 itself has DST/offset issues); explain the rest |
| D2 | block counts per type per month (vacation, simulator, reserve) | within 1-2 % (reserve within the code-set decision) |
| D4/D5 | sick runs and call-outs per month vs v3; `notification_ts` completeness | counts +/-2 %; >= 99 % of sick runs with a journal timestamp from 2024-05-14 |
| D8 | legs per month, delay minutes, IATA code coverage | counts equal after the v3 odd-row rules are applied; code coverage 100 % of delayed legs |
| D11 | sessions per type per month | within 2 % except `INITIAL_GROUND` (code list to agree) |
| F02 vs AIMS | hours per crew x period vs `TIMEPNCPNT` | within 1 % |
| Whole | CrewSim quality gates / readiness on the AIMS snapshot vs on v3 | no gate worse, V3 now computable |

## 7. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Queries load the production AIMS server | operational impact, DBA veto | replica or off-peak, month chunks, narrow indexed predicates, read-only intent, cap rows, never touch `MSTLOGCRW`/`CREXPLOG`/`LOG_LEGPAX`/`MSGQ`/`WEBLOGNG` |
| AIMS data changes between runs | non-reproducible results | snapshot + manifest + hash in provenance; refresh is an explicit action |
| Convention differences vs Pierre's logic (cancelled flag, SICK code set, report offsets, `credit_hours`) | numbers shift, gates change | define conventions explicitly in reference tables (M01, M08, rules file), version them, show the diff against v3 in the reconciliation report |
| Journal/clock semantics (server-local time, `MOVEMENT.EXE` not in `LOG`) | wrong lead times | single time module, use `LOG_ROSTER` for IOC changes, validate on known cases before use |
| Journals start 2024-05-14 | no event timestamps before | accept window; M04 archive if it exists |
| Raw crew ids leak | Law 25 breach | pseudonymise in the extraction process, H01 in a secret store, never persisted or logged, banned-column loader check kept |
| neoLR scope not derivable | wrong fleet cell | H03/H04 from Pierre; until then simulate the A321 family (current behaviour) |
| Pierre's files late or partial | placeholders remain | CrewSim already reports placeholder-dependent results as outstanding; ship in priority order (minimal set F01-F04, F06, H01, H02) |
| AIMS schema or codes change (code vocabulary shifts over time) | silent breakage | versioned code maps with validity dates, a schema-drift check on the extraction (like the CSV header check) |
| Dependence on a personal admin login | outage / audit finding | service account; no personal credentials in config |
| Overconfidence in inferred meanings | wrong mapping | every mapping carries confidence from the semantic layer; ask the business to validate (M01, M02) |

## 8. Remaining decisions (the numbered decisions above are closed)

1. **Snapshot-first** (recommended) vs live-only reads.
2. **Which roster state D2 represents**: published (what crew were told), as-of the event date, or current. Recommended: published for D2/D4 pairing links; as-of for event reconstruction.
3. **Pseudonymisation**: reuse Pierre's v3 key (H01) or new keyed HMAC.
4. **Window**: 2024-05-14 -> latest (recommended), no extension before.
5. **Scope**: A321 family now; A321neoLR once H03/H04 arrive. Cabin crew (CUPE) as phase 2 using the same extraction.
6. **Where the extraction SQL lives and who may run it** (repo files vs views in `CrewSchedAI`; service account owner).
7. **Who signs the mapping tables** (M01 activity codes, M02 user groups) at Crew Planning / IOC.

## 9. What was verified and what was not

Verified: the connection and read-only access; `PROSTER` (2022-12-21 ->), `LOG_ROSTER` (from 2024-05-14, with old/new values, user, program), `TIMEPNCPNT` (4 pay months), the 2024-05-14 actuals boundary (counts above), CRCODES sign convention (`ROSTER.LEG_FLT = CRCODES.ID`, both <= 0; several semantic files had the opposite sign and were corrected today), CrewSim's single loading seam.
Taken from the four investigations (queries and counts in their files): all reconciliation percentages and every statement about meaning of the journals.
Not done: any code change, an end-to-end extraction run over the whole window, performance timing on the full window (do it in Phase 1), a DBA/security review, contact with Pierre.

