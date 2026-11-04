# Mock corpus — datasets D1–D12

**Synthetic stand-in for Air Transat's operational extracts**, built to the schemas in
`spec_sections/6_Detailed_Data_Requirements.md` §6.1.

> ## ⚠️ This is not real data
>
> Volumes, the route network, crew establishment and every dollar figure are **plausible-shaped
> inventions**. Nothing here may be quoted as an Air Transat number, used in a report, or treated as a
> forecast. Its only purpose is to let the ETL, the calibration jobs and the Phase-0 derived datasets be
> built and tested **before real extracts land** — so that when they do, the code is already proven.
>
> Every real value this corpus stands in for is tracked in `QUESTIONS_TO_ASK.md`.

---

## Quick start

```bash
python tools/generate_mock_corpus.py            # regenerate (about 12 s)
python tools/validate_corpus.py                 # score it against ground truth

python tools/generate_mock_corpus.py --compress # .csv.gz, ~10x smaller
python tools/generate_mock_corpus.py --months 12 --seed 7   # smaller / different
```

The generator writes to **`src/crewsim/data/corpus/`** — where this file lives. The corpus ships
inside the package, next to the loaders that read it, and is committed, so a fresh checkout runs with
no generation step. The scripts that build and score it live in `tools/`. Loaders resolve the location
from `configs/base.yaml → paths.corpus_dir` and never from a literal (§4.4.1b).

The generator is **deterministic**: the same seed always produces byte-identical output, in keeping
with the reproducibility discipline the rest of the project runs on (§2.3/C1). Regenerating therefore
rewrites committed files — expect a diff only if the seed, month count or schema changed.

---

## What is in the corpus

Window **2023-08-01 → 2026-07-31** (36 months), seed `20260805`. Total ≈96 MB uncompressed.

| File | Rows | Dataset | What it is for |
|---|---:|---|---|
| `d1_crew_master.csv` | 2,019 | D1 | Crew population: 634 pilots + 1,385 cabin crew, with seniority, type ratings and **employment status** |
| `d2_rosters.csv` | 194,149 | D2 | Published rosters — pairing / reserve / day off / vacation / training / sim blocks, UTC **and** station local, with **SC/LC reserve call type** |
| `d3_pairings.csv` | 119,534 | D3 | Pairing headers: base, fleet, position complement, credit hours, layovers |
| `d3_pairing_legs.csv` | 535,543 | D3 | Leg detail: report / departure / arrival / release times |
| `d4_absences.csv` | 7,736 | D4 | Sick-call log with notification timestamp, duration, affected pairing |
| `d5_reserve_callouts.csv` | 5,294 | D5 | Reserve utilisation: call time, report time, outcome (assigned / released / **no-show**) |
| `d6_schedule_changes.csv` | 3,114 | D6 | Schedule changes — the raw material for **draft reconstruction** |
| `d7_pay_register.csv` | 7,881 | D7 | Pay items with premium codes — the other half of that join |
| `d8_flight_movements.csv` | 67,368 | D8 | OTP: scheduled vs actual, IATA delay codes, cancellations |
| `d9_station_days.csv` | 62,354 | D9 | Station-day disruption class — the generator's TRUE hidden regime. **Not a calibration input since F-42** (the regime is inferred by an HMM from D8/D4/D2); kept only as ground truth for the optional `regime_label_agreement` diagnostic |
| `d10_positioning_invoices.csv` | 745 | D10 | Hotel / deadhead / transport costs |
| `d11_training_sessions.csv` | 5,621 | D11 | Ground and simulator sessions with requalification deadlines |
| `d12_agreement_rules.yaml` | — | D12 | Agreement rules as a document. Confirmed facts marked `CONFIRMED`; the rest `[CONFIRM: …]` |
| `_ground_truth.json` | — | — | **The generating parameters.** See below. |

---

## Three things deliberately built in

### 1. Ground truth — so reconstructions can be *scored*

Real extracts do not come with an answer key. This one does, which is the whole point: prove the §6.3
reconstruction logic against a known answer before pointing it at Air Transat's systems.

```json
{ "drafts_true": 2592, "cascades_true": 522,
  "cascade_rate_true": 0.2014, "eligibility_rate_true": 0.3025,
  "expected_reconstruction_recall": 0.88 }
```

`validate_corpus.py` scores every derived dataset against these. Current result:

| §6.3 reconstruction | Recovered | Target |
|---|---|---|
| Draft events (D6 × D7 join) | **87.7%** recall — 2,273 of 2,592 | gate ≥ 80% |
| Eligibility rate | **30.2%** | ≈30% |
| Cascade rate | **20.1%** | ≈20% |
| `SEVERE → SEVERE` persistence | **40.9%** | clustered, not scattered |

### 2. Deliberate data-quality gaps — so the Phase-0 gates are actually tested

A corpus that passes every gate trivially proves nothing. These are injected on purpose:

| Gap | Rate | Which gate it exercises |
|---|---:|---|
| Draft premium pay code missing from D7 | 12% | §6.2's **≥80% draft-reconstruction recall** — the project's critical path |
| D6 `initiator` field null on older records | 8% | Reconstruction join robustness |
| Absence not linkable to a roster block | 3% | §6.2's **≥95% D4 linkage** |
| Station-day missing from D9 | 2% | Regime fitting with holes |

Turn any of them down in the generator to see a gate flip.

### 3. Seasonality and correlated disruption

Air Transat's two programmes produce genuinely different months (§4.5.2), and the corpus reflects it:

| Season | Departures | Cancel rate | Typical destinations |
|---|---:|---:|---|
| Winter sun (Dec–Apr) | 28,209 | **1.48%** | CUN, PUJ, SJO, PTP, FDF, CUR |
| Summer Atlantic (Jun–Sep) | 26,992 | 0.70% | MRS, TLS, LYS, BRU, LGW, BCN |
| Shoulder | 12,167 | 0.50% | mixed |

Disruption is driven by a per-station **severity regime** Markov chain fitted per season, with a sticky
`SEVERE` state — so bad *weeks* occur, not four unlucky Tuesdays scattered through a month. That
clustering is what actually exhausts a reserve pool, and it is why the correlation matters (§1.3.4).

### Fitting and holdout windows

The corpus is pre-split to support the discipline in §6.4 — never validate on data you fitted:

```
fitting window   2023-08-01 .. 2025-07-31   (24 months)
holdout window   2025-08-01 .. 2026-07-31   (12 months)
```

---

## Known simplifications

Stated so nobody mistakes an omission for a property of the data.

| Simplification | Consequence |
|---|---|
| **Each pairing is held by one crew member.** `position_complement` says `CA:1,FO:1,FA:5`, but pairing IDs are not shared between the captain and first officer on the same trip. | Fine for the MVP, which models FOs at YUL in isolation (§1.5). **Wrong for Phase-2 multi-position work** — a sick CA and a sick FO on the same trip should be one cancellation, not two. |
| **99% of drafts land on tier 1 (day off).** | Not a bug — with ~120 FOs in a group and only a few drafts a month, somebody is always at home. The same effect appears in the reference implementation (§8.3). But it means **tiers 2–5 are barely exercised**, so the tier-cost logic and the vacation surcharge cannot be tested against this corpus. |
| **Cabin crew are in D1 but not rostered.** | Phase 2. `d2_rosters.csv` is pilots only. |
| **No network delay propagation.** | Delays are independent given the regime. Matches the model's own scope exclusion (§1.4) — tail severity is understated in both. |
| **Recovery is generated, not simulated.** | The corpus embeds target eligibility and cascade rates by construction. It can therefore verify that reconstruction *logic* works; it cannot independently confirm that the *simulation* reproduces those rates. That is what gates V3/V4 on real data are for. |
| **Costs are placeholders.** | Draft premium $500, reserve guarantee $250/day, etc. — order-of-magnitude only. All are `[CONFIRM: Finance]` in §4.4.2. |

---

## Using it

```python
import polars as pl

rosters = pl.read_csv("src/crewsim/data/corpus/d2_rosters.csv")

# The MVP slice (§1.5): YUL / A321neo LR / First Officer
mvp = rosters.filter(
    (pl.col("base") == "YUL")
    & (pl.col("fleet") == "A321neoLR")
    & (pl.col("position") == "FO")
)

# How many are on reserve lines, and what is the SC/LC split?
print(mvp.filter(pl.col("block_type") == "RESERVE")
         .group_by("reserve_call_type").len())
```

`d1_crew_master.employment_status` carries the availability edges that §2.1 of `QUESTIONS_TO_ASK.md`
asks Crew Planning about — `ACTIVE`, `LONG_TERM_ABSENCE`, `INITIAL_TRAINING`, `FLEET_TRANSITION`,
`MANAGEMENT_OR_INSTRUCTOR`, `TERMINATED`. Only `ACTIVE` crew are rostered.

**This makes the §2.1 question concrete.** The YUL / A321neo LR / FO establishment is **120**, matching
`configs/base.yaml → population.roster_size` — but only **112 are actually rostered**, because eight are
in initial training, in fleet transition, on long-term absence, or flying management schedules. Counting
the establishment rather than the rostered population would overstate the draft candidate pool by 7%,
pushing the recommended reserve level down. That is exactly the ambiguity the "who was *not* awarded a
line, and why" part of the request is there to resolve.

Reserve lines in that slice: 18 of the 112 hold them, split roughly 63/37 short-call to long-call —
which is what makes rule L8 testable and is the mechanism the reference implementation still lacks
(§8.1).

---

## Where this fits

| Slice | Uses the corpus for |
|---|---|
| **1a** | Nothing — runs on synthetic scenarios, no data needed |
| **1b** | Real roster loading (D1, D2), headcount conservation, reserve line rotation |
| **1c** | Eligibility engine and gate V3 (D2, D4, D5) |
| **1d** | Cascade engine and gate V4 (D6, D7) |
| **1e** | Cost backtest V6 (D7, D10) |

When real extracts arrive, point the same loaders at them and re-run `validate_corpus.py` with the
ground-truth checks disabled — the completeness gates in §6.2 still apply, and are the ones that matter.
