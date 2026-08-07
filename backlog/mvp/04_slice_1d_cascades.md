# Slice 1d — Cascade Engine FULL

**Epic E1d** · 5 stories · Gate: **V4 cascade rate on holdout · V9 parameter sensitivity**
Needs datasets **D6, D7** — which depend on the S0-03 reconstruction clearing its recall gate.

Cascades are the mechanism that makes drafting expensive in a way a spreadsheet cannot capture: the
$800 tier-2 draft that ends in a $25,800 chain. This slice makes that emergent and then validates it.

---

## ⏳ [TODO] S1d-01 — Future-pairing cascade from the StateDelta
**Size:** `M` | **Depends on:** S1c-05 | **Spec:** §5.7, §5.0.4/E5

**As a** modeller **I want** a draft to break the drafted crew member's later trips automatically
**so that** cascade frequency is a consequence of the schedule, not a probability.

### Acceptance Criteria
- [ ] Consumes the `StateDelta` from every draft — no separate cascade probability anywhere
- [ ] A pairing the new duty overlaps, **or** that starts inside the mandatory rest after it, is removed
- [ ] The removed pairing re-enters as an `OpenTimeItem` **at the correct future time**, and the recovery
  pipeline re-fires — so multi-level cascades arise naturally
- [ ] Cascade visibility lag is configurable (currently T-24h, a guess — `QUESTIONS_TO_ASK.md` §1.7)

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_cascade.py -k pairing`
*   🙋 **Manual:** `crewsim explain-cascade --scenario 0 --first`
    *   **Expect:** draft → later pairing removed → new open item **at that pairing's time**
    *   **Fails if:** the cascade fires immediately — recovery then happens with foresight nobody has

---

## ⏳ [TODO] S1d-02 — Future-reserve cascade
**Size:** `M` | **Depends on:** S1d-01 | **Spec:** §5.7

### Acceptance Criteria
- [ ] Drafting a crew member who held a **later RESERVE block** shrinks that day's pool structurally
- [ ] Distinct from a pairing cascade in the ledger, so the two can be counted separately
- [ ] Legality-shift effects (rest pushes, rolling-limit consumption) surface as further deltas

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_cascade.py -k reserve`
*   🙋 **Manual:** `crewsim explain-cascade --scenario 0 --type reserve_loss`
    *   **Expect:** a later day's reserve pool visibly reduced by an earlier draft
    *   **Fails if:** only pairing cascades ever appear — half the mechanism is missing, and future
    *   eligibility never contracts

---

## ⏳ [TODO] S1d-03 — Event E9, terminal penalty
**Size:** `S` | **Depends on:** S1d-01 | **Spec:** §5.0.5, §7.3

**As a** reviewer **I want** unresolved work at the horizon to be charged
**so that** a policy cannot look cheap by pushing problems past the boundary.

### Acceptance Criteria
- [ ] Charged per residual open item at horizon end, at `cancel_cost × 1.5` from config
- [ ] **Must exceed `cancel_cost`** — asserted at load, not merely documented
- [ ] Cool-down costs attributed back to the measurement window via `root_event_uid`

### Verification
*   🤖 **Automated:** `pytest tests/engine/test_terminal.py`
*   🙋 **Manual:** `crewsim explain-cost --category TERMINAL_PENALTY --summary`
    *   **Expect:** $37,500 per unresolved item
    *   **Fails if:** it is below `cancel_cost` — abandoning an item becomes cheaper than cancelling it,
    *   and the model learns to do exactly that

---

## ⏳ [TODO] S1d-04 — V4 gate on the HOLDOUT window  ·  **gate V4**
**Size:** `M` | **Depends on:** S1d-02, S0-05, S0-09 | **Spec:** §9.2, §6.4

### Acceptance Criteria
- [ ] Realised cascade frequency — the share of drafts producing ≥1 downstream open item or reserve loss —
  compared against the historical band from S0-05, on the **holdout** window
- [ ] Verdict stated; the gap reported whichever way it goes
- [ ] If S0-03's recall was marginal, **the report says so on the same page** as the verdict

### Verification
*   🤖 **Automated:** `pytest tests/gates/test_v4_cascade.py`
*   🙋 **Manual:** `crewsim gate v4 --window holdout`
    *   **Expect:** simulated rate vs the historical band, verdict stated
    *   **Fails if:** roster composition was adjusted to make it pass — that is calibration wearing
    *   validation's clothes

---

## ⏳ [TODO] S1d-05 — V9 parameter sensitivity  ·  **gate V9**
**Size:** `M` | **Depends on:** S1d-03 | **Spec:** §9.2

**As a** planner **I want** to know which of my inputs the answer actually depends on
**so that** a recommendation resting on a judgement call is visible as such.

### Acceptance Criteria
- [ ] Sweeps from `configs/base.yaml → sensitivity`: `roster_size`, `terminal_penalty`, `lambda`
- [ ] Recommended R reported as a **surface**, not a point
- [ ] Instability is reported prominently, not buried — an R\* that moves is a finding

### Verification
*   🤖 **Automated:** `pytest tests/gates/test_v9_sensitivity.py`
*   🙋 **Manual:** `crewsim gate v9 --surface`
    *   **Expect:** a small table of R\* against each swept parameter
    *   **Fails if:** R\* moves materially and the report does not say so on the front page
    *   > **Known baseline.** Before headcount conservation, `roster_size` was completely inert — argmin E[C]
    *   > was R=6 at 100, 120 and 140, because senior-first drafting only ever reached the top ~21 of the
    *   > seniority list. After slice 1b it should start to bite. If it still does not, that is worth
    *   > understanding before trusting the recommendation.

