# 9. Verification & Validation Plan

**Version:** 3.0 (Air Transat instantiation, engineering edition) · **Date:** 2026-08-05

---
## What this section is

This section defines the "Gate List" — the final exams the AI must pass before it is allowed to touch any real-world business decisions at Air Transat. 

> **CRITICAL RULE:** No output from this software can be used to inform an Air Transat bid-period decision until all nine gates (V1-V9) are passed.

These gates are split into two completely different concepts that people often confuse:

| Concept | The Question It Answers | How It Is Tested | The Gates |
|---|---|---|---|
| **Verification** | *Did we build the thing right?* (Is the underlying math correct?) | Purely technical tests that are fully automated by engineers. | **V1, V2, V7, V8, V9** |
| **Validation** | *Did we build the right thing?* (Does this describe reality?) | Requires historical data and human IOC experts to pass the "smell test". | **V3, V4, V5, V6** |

---

## 9.1 The Gate List

| Gate | Type | The Test (What we are doing) | The Pass Criterion (How we know it works) | Phase |
|---|---|---|---|---|
| **V1** | Verification | **The Extremes:** Run the math with 0 sick calls, 0 reserves, and infinite reserves. | The simulation outputs exactly $0 where expected. | 1a |
| **V2** | Verification | **The Textbook Check:** Strip away all complex rules and run a basic textbook math scenario (Erlang-B). | The simulation's answer matches the textbook math formula exactly. | 1b |
| **V3** | Validation | **The 30% Usability Rule:** Measure how often reserves were actually legal to fly on historical days. | The simulation's usability rate matches the historical data (using the strict "Testing Vault"). | 1c |
| **V4** | Validation | **The Domino Effect:** Measure how often drafting a pilot causes a future flight to break. | The simulation's domino rate matches the historical data (using the strict "Testing Vault"). | 1d |
| **V5** | Validation | **The Expert Walkthrough:** Replay a massive real-world storm week. Ask the real IOC Duty Managers to review the AI's choices hour-by-hour. | The experts agree that the AI's choices make logical, real-world sense. | 1e |
| **V6** | Validation | **The Receipt Check:** Feed historical disruption data into the AI. | The AI's total calculated cost matches Air Transat's real historical payroll & invoice receipts for that exact same week. | 1e |
| **V7** | Verification | **The Weather Control Check:** Run the exact same simulated month twice across different computers. | The financial ledger matches down to the exact penny. | 1a |
| **V8** | Verification | **The Laws of Physics Check:** Run 100 months of chaos and scan every pilot's calendar. | Zero instances of pilots being assigned to two flights at once (Rule L0). | 1a |
| **V9** | Verification | **The Judgement Call Check:** Massively change the "assumed" penalty costs to see if the AI panics. | The AI's final recommendation doesn't drastically flip just because we tweaked an assumption. | 1d |

**Why V9 is critical:** Two inputs are not yet measured from Air Transat data — the terminal penalty
(§5.0.5), which is a judgement call, and `roster_size` (§1.5), which is simply not yet supplied — and
both have heavy leverage on the answer. Sweeping them (testing massive variations) tells you whether the AI's recommendation is resting entirely on these flimsy assumptions.

**Current result for `roster_size`: the recommendation does not move at all** — the best answer is 6 reserves whether the roster is 100, 120, or 140 pilots. That is not reassurance yet, and the reason is worth understanding. Under senior-first drafting with no cap, only the top of the seniority list is ever reached: across 30 simulated bid periods, **17 distinct crew members were ever drafted, all within the top 21 of the list**, regardless of roster size. Everyone junior to that is never a candidate, so adding them changes nothing.

The sweep will become meaningful at Phase 1b, when headcount conservation (§5.10) makes `roster_size` determine how many line holders remain after reserves are carved out. Until then, the gate is correctly reporting that the parameter is inert — which is itself information, and exactly what a sensitivity sweep is for. A recommendation that flips when a judgement call is nudged is not a recommendation; it is a coin toss with error bars. Sweep them and say what happens.

---

## 9.2 How to run each gate

### V1 — The Degeneracy Check (The Extremes)
Run the math on three extreme configurations that you can easily compute on paper. If the simulation disagrees with basic arithmetic, stop and fix it before writing any more code.

| Configuration | Expected Result |
|---|---|
| **0 reserves, 0 sick calls, 0 delays** | Total cost must be exactly $0. |
| **Everyone is on reserve** | Zero drafts, zero cancellations. Total cost = pure staffing. |
| **0 reserves, normal sick calls** | Every broken flight is either drafted or cancelled. Zero staffing costs. |

### V2 — The Erlang-B Bound (The Textbook Check)
Erlang-B is a 100-year-old mathematical formula originally used by telephone companies to figure out how many operators they needed before callers started getting a busy signal. We use it the exact same way, but instead of "phone operators," we are counting "reserve pilots," and instead of a "busy signal," it's a "flight cancellation."

To run this test, we temporarily strip the AI down to the basics: we turn off the complex union rules, disable the domino effect, and pretend there is only one airport. Then we compare the AI's output against the classic textbook math.

| The Test | The Example |
|---|---|
| **The Setup** | We ask both the AI and the Textbook Math: *"If we have 5 reserves, and we average 3 sick calls a day, how often will we run out of pilots?"* |
| **The Pass Criterion** | The AI must independently arrive at the exact same answer as the classic textbook math. |
| **If it fails** | If the Textbook math says we should run out of pilots **11%** of the time, but the AI says we will only run out **3%** of the time, the AI's core queueing logic is fundamentally broken. It might be hallucinating that reserves are returning from flights faster than they actually are. |

### V3 & V4 — The Emergent-Rate Gates (The Trap)

> **The Golden Rule: Never fit inputs to hit the target.**
> If you secretly tweak the AI's math until the Usability Rate magically hits 30%, you haven't proven the AI is smart; you just engineered a fake pass.

| The Honest Procedure |
|---|
| 1. Take roster schedules from **actual historical data**, not a fake synthetic generator. |
| 2. Train the AI's disruption models on the **Training Vault** only. |
| 3. Measure the AI's Usability and Domino rates on the completely unseen **Testing Vault**. |
| 4. Report the gap honestly, whatever it is. |

**If a gate fails, you have three options (in order of preference):**
1. **Find the missing mechanism:** (e.g., Did we forget to code the strict 12-hour rest rule?)
2. **Widen the tolerance band:** Only allowed with explicit written permission from the business.
3. **Downgrade the gate:** Label the entire simulation as "advisory only" and print a warning on every report.

### V5 — Trace Validation (The Expert Walkthrough)
Pick a real, memorable Air Transat disruption week (like a massive January ice storm at YUL) and replay it in the AI. Then, sit with real IOC Duty Managers and walk them through the AI's log hour-by-hour.

| The Rule | The Action |
|---|---|
| **The Question to Ask** | Do *not* ask "Is this number right?" Ask: **"Would you have actually done this in real life?"** |
| **The Goal** | A model that gets the right final cost by making completely bizarre, illegal decisions is not validated; it just got lucky. |
| **The Expected Outcome** | You will likely learn about a real-world recovery trick the AI doesn't know yet. That is a successful test, not a failed one. |

### V6 — Cost Backtest (The Receipt Check)
Feed actual historical disruptions into the AI and compare its total calculated cost against Air Transat's real payroll and invoice receipts for that exact same week.

| Excluded Mechanism | How it Biases the AI's Cost |
|---|---|
| **Voluntary Pickup** (Not coded yet) | **Overstates** drafting cost (AI drafts when a human might have volunteered). |
| **Conservative Legal Rules** | **Overstates** cost (AI rejects legal assignments because it's being too safe). |
| **No Network Delay Propagation** | **Understates** cost on terrible weather days. |

*A backtest that lands perfectly on the dollar by accident (because massive errors cancelled each other out) is worth less than a test that misses in the exact predicted direction.*

### V7 — CRN Integrity (The Weather Control Check)
Run the exact same reserve policy with the exact same master "seed" twice, and compare the financial ledgers byte-for-byte.

| The Rule | The Action |
|---|---|
| **How to run it** | You must run this using multiprocessing (`joblib`), not on a single CPU thread. |
| **Why it matters** | If the random number generator isn't strictly controlled across all CPU cores, the math will silently produce different results every time you click 'Run'. |

### V8 — Legality Invariants (The Laws of Physics Check)
Run thousands of automated property tests to ensure the AI never breaks the fundamental laws of space and time.

| The Invariant | The Code Check |
|---|---|
| **Rule L0 (Single Assignment)** | No pilot can ever hold two overlapping duties. |
| **Rule L2 (Minimum Rest)** | Mandatory sleep is treated as a hard, physical block on the calendar that cannot be overwritten. |

*Physical feasibility is more fundamental than any union rule. If the AI hallucinates teleporting pilots, its cost savings are fake.*

### V9 — Parameter Sensitivity (The Judgement Call Check)
Two massive inputs are currently based on "judgement calls" rather than hard data: the massive `terminal_penalty` for a broken flight, and the overall `roster_size`.

| The Sweep Test | The Expected Outcome |
|---|---|
| **Run the AI** with `terminal_penalty` at 1x, 2x, and 3x the normal cost. | The recommended number of reserves should stay relatively stable. |
| **If it fails** | If the AI says "buy 5 reserves" at 1x cost, but flips to "buy 40 reserves" at 2x cost, the AI is completely unstable. The recommendation is resting on a flimsy assumption and cannot be trusted. |

---

## 9.3 The Reporting Obligations (The "No Black Box" Rule)

If this software tells the business to "hire 14 reserves next month", the business must be able to ask *why* and get a mathematically provable answer. 

Every single recommendation report generated by the system **must** include the following five items:

| The Requirement | Why it is mandatory |
|---|---|
| **1. Drill-down Links** | The planner must be able to click on the recommendation and see exactly *why*. "Why 14?" must resolve to a specific simulated Tuesday where 13 wasn't enough, not just a vague average. |
| **2. The Reproducibility Chain** | An engineer must be able to type in the exact master "seed" and data hashes a year later and get the exact same answer down to the penny. |
| **3. The Gate Status (V1-V9)** | The report must clearly show if it passed all 9 Verification & Validation gates. If a test failed, it must be printed clearly on the front page. |
| **4. The "Reality Check" Table** | It must show the AI's Usability and Domino rates directly compared to the real historical rates, even (and especially) when the AI's numbers missed the mark. |
| **5. Outstanding `[CONFIRM: SME]` Flags** | If the AI is recommending a budget based on a placeholder "guess" (like assuming a hotel costs $150), that placeholder must be flagged. A perfectly validated AI running on fake cost data will produce a beautifully reproducible wrong answer. |

---

## 9.4 What this plan does not cover

Stated so nobody assumes otherwise:

- **Regulatory compliance.** The legality surrogate approximates CARs Part VII; it is not a compliance
  tool and no output of this system should be used to assert that an assignment is legal.
- **Collective agreement interpretation.** The impact-tier definitions and the senior-first drafting
  order encode a *reading* of the ALPA agreement. That reading needs sign-off from
  Labour Relations, and the validation plan cannot substitute for it. Three items are already known to
  have been wrong in v2 — it assumed junior-first drafting was selectable, that vacation and simulator
  blocks were draft-protected, and that a per-crew monthly draft cap existed. None is the case at
  Air Transat.
- **Distribution as an outcome.** The system reports per-crew draft counts and Gini concentration.
  Because drafting is premium-paid and allocated senior-first, these describe how **premium earnings**
  are distributed, not how a burden falls. A high concentration is the expected consequence of the
  agreement, not a defect the model should flag. Whether that distribution is desirable is a question
  for the parties to the agreement, not for a gate.
