# Phase 0 — Data Foundation & Calibration

**Epic E0** · 12 stories (incl. project foundation) · Gate: **draft-event reconstruction ≥ 80% recall**
Runs **in parallel with slice 1a**, which needs no data at all.

> ## ⚠️ This epic contains the project's schedule risk
>
> `S0-03` is the critical path. Air Transat's crew tracking system almost certainly has no
> `was_drafted` column, so drafts must be reconstructed by joining schedule changes (D6) against
> premium pay codes (D7). If recall lands below 80%, **both V3 and V4 degrade to advisory** — and those
> two gates are the entire credibility argument for the system.
>
> Do `S0-03` first, as a one-week spike, **before Phase 1 dates are committed.**

Everything here can be built and proven today against **`src/crewsim/data/corpus/`** — the project's
data source, resolved from `configs/base.yaml → paths.corpus_dir`, never hard-coded. It ships with
`_ground_truth.json`, so each reconstruction can be scored against a known answer.

> **The corpus ships with the code.** `src/crewsim/data/` holds the *loaders* **and** the datasets
> they read, committed, so a fresh checkout runs with no generation step. `generated/` keeps run
> output only (`params/`, `reports/`) and stays git-ignored. Shipping the data does not relax the
> path rule: a loader that opens a literal path instead of the configured one still fails S0-00's
> structure test (§4.4.1b) — the real Air Transat extracts will not live in the package.

---

> ## ✅ Both stories below are **done** (2026-08-05)
>
> `ruff` clean · `mypy --strict` clean on `engine/` · 25 tests passing · `doctor` reports 12/12 datasets.
> The two rules are enforced by tests that were verified to *fail* when deliberately violated.

---

## S0-00 — Create the Python project structure  ·  `M`

**As a** developer **I want** the repository laid out exactly as §4.2 specifies, with the corpus
shipped inside the package **so that** a fresh checkout runs immediately, and the dependency rule and
the no-hard-coded-paths rule are enforced from the first commit instead of retrofitted.

Depends on: — · Spec §4.2, §4.4.1b

**Acceptance — the tree**

```
crew-recovery-sim/
├── pyproject.toml                 # uv-managed, src layout, entry point `crewsim`
├── configs/
│   ├── base.yaml                  # scope, horizon, population, paths, sensitivity
│   ├── costs_pilots.yaml          # ALPA-derived coefficients        (§4.4.2)
│   ├── costs_cabin.yaml           # CUPE — Phase 2, stub only
│   ├── seasons.yaml               # bid-period definitions           (§4.5)
│   └── policies/                  # candidate policy YAMLs           (§5.9)
├── src/crewsim/
│   ├── data/                      # loaders + the corpus they read
│   │   └── corpus/                # the datasets D1–D12, committed  ← the data source
│   ├── calibration/               # NHPP fit, regime model, V&V targets
│   ├── scenarios/                 # ScenarioGenerator, CRN seed management
│   ├── engine/
│   │   ├── state.py               # Crew State Engine                (§5.4)
│   │   ├── legality.py            # Legality surrogate L0–L8         (§5.4)
│   │   ├── eligibility.py         # Reserve Eligibility Engine       (§5.5)
│   │   ├── drafting.py            # Draft Candidate Selection        (§5.6)
│   │   ├── cascade.py             # Cascade Evaluation Engine        (§5.7)
│   │   ├── costs.py               # Cost Engine / event ledger       (§5.8)
│   │   └── des.py                 # SimPy processes & dispatch       (§5.3)
│   ├── optimize/                  # Phase 2 — package stub
│   ├── reporting/                 # KPI aggregation, HTML report
│   └── cli.py                     # crewsim run | compare | calibrate | gate | doctor
├── generated/                     # run output — never committed
│   ├── data/                      # corpus generator + validator scripts
│   ├── params/                    # versioned parameter store        (§6.2)
│   └── reports/                   # HTML reports                     (§9.3)
└── tests/
    ├── data/  calibration/  engine/  reporting/  gates/
```

**Acceptance — the rules the structure exists to enforce**

- **The corpus ships with the package.** `src/crewsim/data/` holds the *loaders* and, under
  `corpus/`, the datasets themselves — committed, so a checkout is runnable with no generation step.
  A test asserts the corpus directory exists, that no `.gitignore` rule excludes it, and that the
  wheel packages `src/crewsim` whole so the data cannot fall out of the distribution.
- **No hard-coded paths.** Every path comes from `configs/base.yaml → paths`. A test greps `src/` for
  string literals containing `generated/`, `corpus`, or `.csv` and fails on any hit. Shipping the data
  inside the package makes this rule *more* load-bearing, not less: Air Transat's real extracts will
  not live there, and repointing must stay a one-line config change.
- `pyproject.toml` declares the `crewsim` entry point, so `crewsim …` works after `uv sync`.
- Every package has an `__init__.py` and imports cleanly — empty modules are fine at this stage,
  the point is that the shape is fixed before anyone builds inside it.
- `generated/` — run output only — is git-ignored in full.
- `crewsim doctor` reports the structure and resolves every configured path.

🤖 `pytest tests/test_project_structure.py`
🙋 `PYTHONPATH=src python -m crewsim doctor`  *(or `crewsim doctor` after `uv sync`)*
   **Expect** every §4.2 module present, and `corpus_dir` resolving to `src/crewsim/data/corpus`
   with **12 datasets found**
   **Fails if** the corpus is missing from the package, or a path is hard-coded instead of read
   from config

> **Why this is `M` and not `S`.** Getting the shape right now is what makes the engine testable in
> microseconds later. Shipping the corpus in-package costs a ~97 MB repository; it buys a checkout
> that is runnable on clone, with every gate scored against the exact bytes the loaders were written
> against. Retrofitting either decision is expensive.

---

## S0-00b — Tooling, CI and the engine dependency rule  ·  `S`

**As a** reviewer **I want** the quality bar automated **so that** §4.3's standards are enforced by
the pipeline rather than by memory.

Depends on: S0-00 · Spec §4.1, §4.3

**Acceptance**
- `uv` lockfile; ruff configured; **`mypy --strict` on `src/crewsim/engine/` specifically** — the rest
  of the tree is not strict, per §4.3
- **`engine/` must not import `simpy`.** Only `des.py` may. Enforced by a test, not by convention
- CI runs lint, types and tests on every push, and fails the build on any of them
- `hypothesis` wired in, ready for the L0 property test in S1a-06 (slice 1a)

🤖 `ruff check src && mypy --strict src/crewsim/engine && pytest tests/test_dependency_rule.py`
🙋 `grep -rn 'import simpy' src/crewsim/engine | wc -l`
   **Expect** `0`
   **Fails if** anything above 0 — the engine stops being unit-testable without a SimPy
   `Environment`, and the test suite goes from ~4 seconds to ~4 minutes

---

## S0-01 — Typed corpus loader for D1–D12  ·  `M`

**As a** developer **I want** every dataset to load through one typed, validated loader
**so that** schema drift fails loudly at ingestion instead of silently at calibration.

Depends on: S0-00 · Spec §6.1, §4.2, §4.4.1b

**Acceptance**
- Reads from `paths.corpus_dir` (`src/crewsim/data/corpus`) — resolved from config, never a literal
- Polars-backed loader per dataset, with a declared schema; unknown or missing columns raise
- Timestamps parsed as UTC **and** station local; legality later operates on local (§6.2)
- `crew_id` treated as an opaque surrogate key — no name or employee number anywhere (Law 25)
- Reads both `.csv` and `.csv.gz`

🤖 `pytest tests/data/test_loaders.py`
🙋 `crewsim data head --dataset d2_rosters --rows 5`
   **Expect** 5 roster rows; `start_utc` and `start_local` differ by the base offset (YUL = 4h)
   **Fails if** UTC and local are identical — timezone discipline is not implemented

---

## S0-02 — Data-quality report against the §6.2 gates  ·  `S`

**As a** data lead **I want** the completeness gates checked automatically
**so that** a corpus that cannot support validation is caught before anyone fits a model to it.

Depends on: S0-01 · Spec §6.2

**Acceptance**
- Reports D4 linkage, D6/D7 join recovery, D9 completeness, each against its threshold
- States PASS / MARGINAL / FAIL per gate, never a bare percentage
- Exits non-zero when a hard gate fails, so it can run in CI

🤖 `pytest tests/data/test_quality_gates.py`
🙋 `crewsim data quality-report`
   **Expect** D4 linkage ≈92%, D9 completeness ≈98% — the injected gaps show up
   **Fails if** every gate reads 100% — the deliberate gaps in the mock corpus are being missed

---

## S0-02b — Descriptive data profile  ·  `M`

**As a** modeller **I want** to see the distribution of every quantity I am about to fit
**so that** I choose distribution families from evidence rather than from habit, and notice a broken
extract before it becomes a fitted parameter.

Depends on: S0-01 · Spec §5.2, §6.1, §4.4.1b

> **Not the same as S0-02.** That one asks *"can we use this data?"* — completeness gates, linkage,
> recall. This one asks *"what does this data actually say?"* Both are needed, and this one must come
> **before** the fitting stories: S0-06 and S0-07 now depend on it, because choosing Negative Binomial
> over Poisson is a decision that should be made looking at a variance-to-mean ratio, not by default.

**Acceptance — what the report covers**

| Stream | What it profiles | What it decides |
|---|---|---|
| **Sick calls** (D4) | Daily count distribution and **variance-to-mean ratio**; rate by season, day-of-week, base, fleet, position; absence-duration distribution with a Q-Q plot; notification lead time; per-crew concentration | Poisson vs NegBin (§5.2); which covariates earn their place in S0-07; the duration family |
| **Reserve utilisation** (D5) | Call-out rate; outcome mix (assigned / released / **no-show**); notification-to-report time; utilisation per reserve-day | The L8 notice thresholds; whether reserve no-shows are material enough to model |
| **Rosters** (D2) | Block-type mix; reserve on/off rotation and SC/LC split; how many crew are free on a typical day | Why tier 1 dominates; whether reserve lines rotate enough for eligibility to fall to ~30% |
| **Pairings** (D3) | Duration, credit hours, duty length, layover mix | Open-time item construction; legality inputs |
| **Delays & OTP** (D8) | Delay-minute distribution (mixture check), by regime; cancellation rate by season; delay-code mix | The delay model's family |
| **Severity regime** (D9) | State occupancy and **run lengths**, per season | Whether the chain produces bad *weeks* |
| **Drafts** (D6×D7, after S0-03) | Prior-status distribution → the empirical **tier mix**; drafts per crew | The tier cost coefficients; the earnings-distribution KPI |
| **Cross-stream** | Sick calls × cancellations × delays on the same station-day | **Direct evidence for or against the severity-regime design (§1.3.4)** |

**Acceptance — the mechanics**
- One self-contained HTML file written to `paths.reports_dir` (`generated/reports/data_profile.html`)
- Every figure states its **n** and its window; nothing is plotted without saying how much data is behind it
- Run **separately for the fitting and holdout windows** — a visible difference between them is a
  finding, not a nuisance
- Every distribution the spec assumes a family for gets an explicit overlay of that family against the
  empirical data, so a bad assumption is visible rather than inferred

🤖 `pytest tests/data/test_profile_report.py`
🙋 `crewsim data profile --open`

**Expect** — measured on the current corpus, so these are checkable today:

| | Value | Why it matters |
|---|---|---|
| Sick calls/day, variance ÷ mean | **3.3** | > 1 ⇒ overdispersed ⇒ NegBin, not Poisson |
| Winter vs summer rate | **9.6** vs **5.7** per day | Season is a real covariate, not decoration |
| Absence duration | median **1**, mean **2.0**, max **38** | Right-skewed ⇒ lognormal is the right family |
| Reserve outcomes | 88.7% assigned · 7.3% released · **3.9% no-show** | A reserve is not a guaranteed resource |
| Roster mix | PAIRING 62% · DAY_OFF 29% · RESERVE 3% | Explains why tier 1 absorbs nearly every draft |
| Regime gradient (per station-day) | sick **0.039 → 0.405**, cancel **0.001 → 0.061**, delay **1.2 → 55.4 min** across CALM → SEVERE | The three streams move together — this *is* the evidence for §1.3.4 |
| SEVERE run length | mean **1.70** days, max **12** | Bad weeks, not scattered bad days |

**Fails if** the variance-to-mean ratio is ≈1.0 — S0-07's NegBin choice would then be unjustified — or
the three streams do **not** move together across regimes, which would mean the severity-regime design
in §5.2 has no support in the data and the correlation the model relies on is invented.

> **Why this earns its place.** §1.3.4 asserts that disruption streams are correlated, and the whole
> severity-regime machinery exists to reproduce that. This report is where that assertion is either
> confirmed or falsified, on real data, before anything is fitted to it.

---

## S0-03 — Draft-event reconstruction (D6 × D7)  ·  `L`  ·  ★ CRITICAL PATH

**As a** data lead **I want** historical drafts reconstructed from schedule changes and pay codes
**so that** the tier distribution and the cascade target have a factual basis.

Depends on: S0-01 · Spec §6.3-1, §6.2

**Acceptance**
- Join is configurable, not hard-coded: premium pay codes, the short-notice window, the initiator
  filter are all parameters, because every one of them is an assumption about Air Transat's systems
- Emits the draft-event table: timestamp, crew, **prior status** (→ tier distribution), covering pairing
- Reports recall against a labelled sample; on the mock corpus, against `_ground_truth.json`
- Handles null `initiator` on older records without dropping the row silently

🤖 `pytest tests/data/test_draft_reconstruction.py`
🙋 `python generated/data/validate_corpus.py`
   **Expect** recall **87.7%** against a ground truth of 2,592 drafts — above the 80% gate
   **Fails if** recall < 80% — escalate immediately; two validation gates degrade to advisory

> **When this runs on real data**, the ground-truth file will not exist. Recall must instead be measured
> against a week that an IOC duty manager has labelled by hand — see `QUESTIONS_TO_ASK.md` §6.1.

---

## S0-04 — Eligibility-rate table from history  ·  `M`

**As a** modeller **I want** the historical eligible fraction as a *distribution*
**so that** gate V3 has something to compare a distribution against.

Depends on: S0-01 · Spec §6.3-2

**Acceptance**
- For each historical sick call, reconstruct the reserve pool on call **for that duty window**
- Apply surrogate rules L0–L8; emit the eligible fraction per event
- Output carries mean, CI and the full distribution — not a point estimate
- Computed per season (§4.5.2)

🤖 `pytest tests/data/test_eligibility_table.py`
🙋 `crewsim data eligibility-target --season winter_sun`
   **Expect** a distribution with mean ≈30% and a printed confidence interval
   **Fails if** only a single number appears — V3 compares distributions

---

## S0-05 — Cascade table from reconstructed drafts  ·  `M`

**As a** modeller **I want** the historical cascade frequency **so that** gate V4 has a target.

Depends on: S0-03 · Spec §6.3-3

**Acceptance**
- For each reconstructed draft, scan the drafted crew's next 7 days in D6 for follow-on IOC changes
- Emit rate + CI; inherits and **reports** S0-03's recall limitation

🤖 `pytest tests/data/test_cascade_table.py`
🙋 `crewsim data cascade-target`
   **Expect** ≈20% with a CI; count consistent with S0-03's reconstructed drafts
   **Fails if** cascades outnumber drafts

---

## S0-06 — Severity regime, fitted per season  ·  `M`

**As a** modeller **I want** a per-season Markov chain over daily disruption state
**so that** bad *weeks* are generated, not scattered bad days.

Depends on: S0-01 · Spec §6.3-4, §5.2, §4.5.2

**Acceptance**
- Cluster station-days by delay-code density, cancellation count and sick-call count into 4 states
- Fit the transition matrix **per season** — one matrix for the year describes neither season
- Emit intensity multipliers alongside the matrix

🤖 `pytest tests/calibration/test_regime.py`
🙋 `crewsim calibrate regime --season winter_sun --show-matrix`
   **Expect** 4×4 matrix, rows summing to 1.0, `SEVERE→SEVERE` > 0.25
   **Fails if** `SEVERE→SEVERE` < 0.15, or one matrix is fitted across all seasons

---

## S0-07 — Sick-call NHPP with covariates  ·  `L`

Depends on: S0-01, S0-06 · Spec §5.2

**Acceptance**
- Poisson / NegBin GLM on daily counts with season, day-of-week, base, fleet, category, regime
- Negative Binomial where overdispersed — absence counts always are
- Thinning to continuous time is tested against the fitted daily intensity
- Absence duration fitted separately (lognormal)

🤖 `pytest tests/calibration/test_nhpp.py`
🙋 `crewsim calibrate sick-calls --show-coefficients`
   **Expect** coefficients per covariate; NegBin dispersion > 1
   **Fails if** dispersion ≈ 1 — Poisson has been assumed where it does not hold

---

## S0-08 — Versioned parameter store  ·  `S`

Depends on: S0-06, S0-07 · Spec §2.2, §6.2

**Acceptance**
- One artefact per calibration run: version, fitted-at, data window, season, coefficients,
  diagnostics, validation targets, **content hash**
- Every simulation run records that version and hash in its metadata

🤖 `pytest tests/calibration/test_param_store.py`
🙋 `crewsim calibrate --emit params/ && cat params/params_v*.json | head -20`
   **Expect** all of `params_version`, `fitted_at`, `data_window`, `season`, `content_hash`
   **Fails if** there is no content hash — the data → params → results chain is broken

---

## S0-09 — Enforce the fitting / holdout split  ·  `S`

**As a** reviewer **I want** it to be impossible to fit on the validation window
**so that** V3 and V4 mean something.

Depends on: S0-08 · Spec §6.4, §9.2

**Acceptance**
- Windows declared in config; the fitter refuses the holdout window with an explicit error
- Validation commands refuse the *fitting* window unless `--i-know` is passed, and say why
- The window used is stamped into every emitted artefact

🤖 `pytest tests/calibration/test_holdout.py`
🙋 `crewsim calibrate --window holdout --emit /tmp/x`
   **Expect** a refusal with a clear message
   **Fails if** it runs — nothing then prevents fitting on validation data
