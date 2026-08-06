# Backlog — Crew Reserve & Drafting Simulation

**How this backlog works, and how you check that a story is really done.**

---

## The problem this solves

An agent can write code that passes its own tests and still be wrong — the tests encode the same
misunderstanding as the code. Four assumptions in this project turned out wrong that way (protected
blocks, the draft cap, selectable junior-first ordering, an invented willingness rate). Each was caught
by a human looking at a number, not by a test.

So every story here carries **two** gates:

| Gate | Who runs it | What it proves | Cost |
|---|---|---|---|
| **Automated** | Claude, in CI | The code does what the story says | seconds, unattended |
| **Manual check** | You | The *behaviour* is what you expect from the operation | **≤ 60 seconds** |

A story is not done until both pass. The automated gate catches regressions; the manual one catches
misunderstandings, and it is the only one that can.

---

## The 60-second rule

Manual validation fails in practice when it takes effort. So every story's manual check obeys four
rules:

1. **One command.** No notebooks, no multi-step setup, no reading source.
2. **One screen of output.** If it scrolls, the check is wrong.
3. **A stated expected value.** You compare, you do not derive. "Total should read 63,000."
4. **A stated failure mode.** You are told what wrong looks like, not just what right looks like.

If a story cannot be checked this way, that is a signal the story is too big — split it.

---

## Running the checks

One dependency: `pip install pyyaml` (the project already needs it for `configs/base.yaml`).

```bash
python backlog/verify.py S1a-04          # one story: automated test + manual recipe
python backlog/verify.py --phase 1a      # every story in a slice
python backlog/verify.py --status        # the board: todo / in progress / done / blocked
python backlog/verify.py --manual 1a     # print just the manual checklist, to work through
```

`verify.py` reads `stories.yaml`, which is the machine-readable source of truth. The markdown files in
`mvp/` and `product_1/` are the human-readable version of the same data — read those to understand a
story, run `verify.py` to check it.

Stories whose code does not exist yet report `NOT IMPLEMENTED` cleanly rather than failing noisily, so
`--phase` is safe to run at any time.

---

## Story format

```
### S1a-04 — Accrue reserve staffing cost per day

**As a** planner **I want** the reserve guarantee counted in the reported cost
**so that** the cost curve shows a real trade-off instead of falling forever.

Epic E1a · Depends on S1a-03 · Spec §5.8, §7.2 · Size S · Fixes D1

Acceptance
  - RESERVE_STAFFING is booked once per reserve per day, at that day's timestamp
  - the warm-up filter prorates it like every other category
  - E[C] contains a staffing component that scales linearly with R × days

🤖 Claude verifies      pytest tests/engine/test_costs.py -k staffing
🙋 You verify (30s)     crewsim explain-cost --policy R6 --scenario 0 --category RESERVE_STAFFING
   Expect               42 rows of $250 × 6 reserves; measured-window total 31,500
   ❌ Fails if          the total is 0, or one lump row appears at t=0
```

**Sizes:** `S` ≈ half a day · `M` ≈ 1–2 days · `L` ≈ 3–5 days. Anything larger gets split.

**`Fixes D#`** links to a defect in `SPEC_REVIEW.md`, so the reason a story exists stays traceable.

---

## Structure

```
backlog/
├── README.md          ← you are here
├── stories.yaml       ← machine-readable: ids, deps, status, verify commands
├── verify.py          ← the runner
├── mvp/               ← Phase 0 + Phase 1. Refined, ready to build.
│   ├── 00_phase0_data_foundation.md
│   ├── 01_slice_1a_foundation.md
│   ├── 02_slice_1b_real_rosters.md
│   ├── 03_slice_1c_eligibility.md
│   ├── 04_slice_1d_cascades.md
│   └── 05_slice_1e_reporting.md
└── product_1/         ← Phase 2 + Phase 3. Coarse on purpose — do not refine yet.
    ├── 06_phase2_optimisation_and_scale.md
    └── 07_phase3_enterprise_hardening.md
```

**Why `product_1` is deliberately coarse.** Phase-2 stories depend on what Phase 1 learns. Writing
detailed acceptance criteria now would encode today's assumptions into next quarter's work — which is
exactly how the four wrong assumptions got as far as they did. Refine a `product_1` epic only when its
predecessor slice has passed its gate.

---

## The phases

Each slice ends with a gate from `spec_sections/9_…` that **can fail**. A slice with no failable exit
test is not a slice.

| Phase | Step | Epic | Exit Gate | Needs data? |
|---|---|---|---|---|
| 0 | — | **E0** Data foundation & calibration | Draft reconstruction ≥ 80% recall | Yes — this *is* the data work |
| 1 | 1a | **E1a** Ledger, CRN, cost engine, legality core | V1 degeneracy · V7 reproducibility · V8 L0 invariant | **No** — start immediately |
| 1 | 1b | **E1b** Real rosters, headcount conservation, full event set | V2 Erlang-B bound | D1, D2 |
| 1 | 1c | **E1c** Eligibility engine FULL | V3 on **holdout** | D2, D4, D5 |
| 1 | 1d | **E1d** Cascade engine FULL, terminal penalty | V4 on holdout · V9 sensitivity | D6, D7 |
| 1 | 1e | **E1e** Reporting, policy grid, backtest | V5 SME sign-off · V6 cost backtest | D7, D10 |
| 2 | — | **E2** Optimisation & scale | Recommendation stable under search | — |
| 3 | — | **E3** Enterprise hardening | Formal V&V accreditation | — |

**Two things run in parallel from day one:** step 1a (needs no data) and the Phase-0 draft-reconstruction
spike (`S0-03`). The spike is the schedule risk — if recall lands below 80%, two validation gates
degrade and you want to know in week 1, not week 7.

**Where things live** (§4.2, §4.4.1b): code *and* the corpus in `src/crewsim/` — loaders in
`data/`, the committed datasets in `data/corpus/` — parameters in `generated/params/`, reports in
`generated/reports/`. `generated/` holds run output only and is git-ignored in full. No path is ever
hard-coded — they all come from `configs/base.yaml → paths`.

---

## Definition of done

This mirrors §3.1's checklist — the spec is the authority, this adds only the manual gate.

1. **The test is fully automated** and runs in CI, not once on someone's laptop.
2. **You have run the manual check and agreed with it.** *(backlog-specific — the other five are §3.1)*
3. **No hidden magic numbers.** Every cost, probability or rule is loaded from `configs/` or from a
   dataset under `generated/` — never hard-coded. **Paths included.**
4. **Strictly typed:** `mypy --strict` clean on `src/crewsim/engine/`.
5. **We know the test's blind spots.** The story records what its gate catches *and what it can miss*.
6. **Placeholders are managed.** Any `[CONFIRM: …]` the story depends on is either resolved, or
   visibly flagged and listed as a risk in the sign-off.
7. `stories.yaml` status set to `done`, with the date.

**Points 5 and 6 are the ones that get skipped.** A perfectly functioning simulation fed placeholder
costs from a config file, with nobody chasing the SME to verify them, produces a beautifully
mathematically-perfect wrong answer.

---

## What you can try right now

Three checks work today, against artefacts that already exist — run them to see the mechanism before
any story is built:

```bash
python crewsim_skeleton.py                    # U-shaped curve, argmin E[C] at R=6, CVaR at R=10
python generated/data/validate_corpus.py      # 87.7% recall, 30.2% eligibility, 20.1% cascade
python backlog/verify.py --status             # the board
python backlog/verify.py --next               # what is unblocked right now
```

`S0-03`'s manual check *is* `validate_corpus.py`, so that story is already verifiable end to end.
