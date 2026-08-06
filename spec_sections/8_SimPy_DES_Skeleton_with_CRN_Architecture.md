# 8. SimPy DES Skeleton with CRN Architecture

**Version:** 3.0 (Air Transat instantiation, engineering edition) · **Date:** 2026-08-05

---
## What this section is

A runnable reference implementation, and an honest account of what it does and does not do.

**The file lives at `./crewsim_skeleton.py`**, driven by **`./configs/base.yaml`**. Dependencies are
`simpy>=4.1`, `numpy>=1.26` and optionally `pyyaml>=6` — without PyYAML or the config file it falls back
to built-in defaults and says so. It is the single source of truth: this section explains and excerpts
it rather than duplicating the whole listing, so the two cannot drift apart.

**Scope, horizon and population come from config, never from code.** A config key the current code does
not yet read — `demand.pairings_per_bid_period` today — is allowed, because it records an answer from the
business ahead of the slice that consumes it. But the loader prints a notice for every such key, so it
never looks as though it is having an effect:

```
[config] NOTE: demand.pairings_per_bid_period is set but not yet consumed
         -- it takes effect at slice 1b (flying comes from D3).
```

```bash
python crewsim_skeleton.py
```

The skeleton is **production-shaped**: its interfaces, CRN discipline, engine separation and evaluation
loop are the ones the full system keeps. Its *domain logic* is deliberately simplified. Extend it;
do not rewrite it.
## 8.1 What this Skeleton Code Does NOT Do (Yet)

The current skeleton code is a stripped-down foundation. It is deliberately missing some real-world complexities so that it remains easy to read and extend. **Do not mistake these omissions for completeness.** 

Because of these omissions, the output numbers in this skeleton will overstate how useful reserves are. 

| Missing Feature | What it means in plain English |
|---|---|
| **No Flight Delays** | The skeleton currently decides to cancel a flight instantly if it can't find a pilot. In reality, flights just delay until someone shows up. |
| **Sick Pilots Don't Disappear** | Currently, if a pilot calls in sick, the flight becomes "broken" (open time), but the pilot technically stays in the available pool. Slice 1b fixes this so sick pilots actually drop off the map. |
| **Reserves Don't Rotate** | The skeleton treats reserves as 24/7 robots. In reality, reserves have days off, and strict legal limits on how much notice you must give them (Rule L8). Because this is missing, the skeleton thinks ~90% of reserves are always available, when reality is closer to 30%. |
| **Headcount is Additive** | The skeleton just "adds 10 reserves" to the airline. In reality, adding 10 reserves means you have 10 fewer pilots flying regular trips. |

---

## 8.2 The Four Golden Rules of the Architecture

When you extend this Python code, you must respect these four architectural rules.

### 1. The Weather Control Rule (CRN Seeding)
To test if "10 Reserves" is a better policy than "6 Reserves", both policies must be tested against the **exact same simulated weather and sick calls**. We call this Common Random Numbers (CRN). If we don't do this, the "10 Reserve" policy might look worse simply because it randomly got hit by a blizzard. 
*   **The Code:** We use a `stable_seed()` function (using `blake2b`). We never use Python's built-in `hash()` because it randomly changes every time you restart your computer.

### 2. The No-Teleportation Rule (Rule L0)
A pilot cannot be assigned to two places at once. 
*   **The Code:** The most critical check in the code (`crew.blocks_in`) ensures that a pilot's new duty does not overlap with their current duty **OR** their mandatory rest period. A pilot's legally required sleep is treated as a hard, physical block on their calendar.

### 3. Split, Don't Delete 
When a reserve pilot is called to fly a short 4-hour morning trip, they don't disappear for the rest of the week. 
*   **The Code:** The `_assign` function does not delete a pilot's `RESERVE` block. It **splits** it. It inserts the flight and the mandatory rest, and puts the pilot right back on `RESERVE` status for the remainder of the day.

### 4. Daily Cost Bookkeeping
We must charge the airline for a reserve pilot *every single day* they sit at home. 
*   **The Code:** The accounting ledger runs a loop that accrues the `RESERVE_STAFFING` cost per reserve, per day. If we only charged the airline once at the start of the month, the math would assume reserves are basically free, and the AI would recommend an infinite number of them.

---

## 8.3 How to Read the Output

When you run the skeleton code, it tests different reserve levels (R=0, R=2, R=4, etc.) over 100 simulated months. 

Here is what the dashboard spits out:

```text
  R      E[C]    CVaR95  elig  casc  uncov   staffing / draft / cancel / util
  0   174,224   359,920  0.00  0.10    6.3         0 / 40,224 / 134,000 /     0
  2    98,977   254,750  0.54  0.11    3.2    10,500 / 18,424 /  66,000 / 4,053
  6    49,571   109,860  0.76  0.09    0.4    31,500 /  2,888 /   8,250 / 6,933
 10    60,961    78,730  0.86  0.01    0.0    52,500 /    608 /     500 / 7,353
 30   165,364   173,340  0.96  0.00    0.0   157,500 /    488 /       0 / 7,376

argmin E[C]      at R = 6   (Best on Average)
argmin CVaR95    at R = 10  (Best for Disasters)
```

### The Glossary of the Output Table
*   **`R`**: The number of Reserve Pilots we are testing.
*   **`E[C]` (Expected Cost):** The total average cost across all 100 simulated months. 
*   **`CVaR95` (The "Disaster" Cost):** The average cost of the *worst 5% of months* (e.g., a week-long blizzard). 
*   **`elig`**: The percentage of reserves who were actually legally allowed to fly when called.
*   **`casc`**: The percentage of drafts that caused a "domino effect" later in the week.
*   **`uncov`**: The average number of flights that cancelled because nobody was available.
*   **`staffing / draft / cancel / util`**: The exact breakdown of where the money went:
    *   **staffing**: The fixed base payroll just to have reserves sit at home.
    *   **draft**: The premium overtime paid to regular pilots to save a flight.
    *   **cancel**: The massive penalties paid to passengers when a flight is cancelled.
    *   **util (Utilization)**: The small extra hourly bump paid to a reserve pilot when they are actually called in to fly.

### Three Key Takeaways from this Data:

**1. The "U-Curve" of Costs:**
Look at the `E[C]` (Average Cost) column. It forms a U-shape. 
*   **At R=0 (Too Few):** The cost is massive ($174,224) because the airline is bleeding money on flight cancellations ($134,000).
*   **At R=30 (Too Many):** The cost is massive again ($165,364) because the airline is bleeding money on pure payroll ($157,500) for pilots sitting at home.
*   **At R=6 (Just Right):** The sweet spot is in the middle at $49,571. Finding this exact bottom of the U-curve is the entire reason this software exists.

**2. Risk vs Average (R=6 vs R=10):**
The simulation shows that R=6 is the cheapest option on a *normal* month. However, if you look at the `CVaR95` column (the disaster scenario), R=10 is much safer. Buying four extra reserves costs the airline about $10,000 extra on a normal month, but saves them $30,000 during a bad one. **The AI's job is to show the math; management's job is to pick the risk level.**

**3. The Mix of Costs (The Sanity Check):**
Always look at the far right column breakdown (`staffing / draft / cancel`). 
*   At R=0, the costs are entirely dominated by cancellations. 
*   By R=10, cancellations are almost completely gone, and base payroll dominates. 
*   The middle of the table (R=6) is where premium drafting handles the overflow. 
If you ever see this mix shift in a way that doesn't make logical sense, you have a bug in your code.

---

## 8.4 Verification Checks (The Automated Tests)

Before any new code is added to the simulator, it must pass a strict suite of automated verification checks. These tests prove that the foundational math isn't secretly broken.

Here are the four tests that the skeleton code passes today:

### 1. The Weather Control Check (CRN Integrity)
*   **The Test:** If we run the simulation on two completely different computers with the exact same master "seed", do they generate the exact same sequence of sick calls?
*   **The Result:** Identical to the 12th decimal place. ✓
*   **Why it matters:** If the code isn't deterministic, it's impossible to prove if "Policy A" is actually better than "Policy B", or if it just got lucky with good weather. 

### 2. The No-Teleportation Check (Rule L0)
*   **The Test:** The code simulates 100 months of chaos. At the end, it scans every single pilot's calendar to see if anyone was assigned to two flights at once, or if a flight overlapped with their legally mandatory rest period.
*   **The Result:** 0 violations found. ✓
*   **Why it matters:** If the AI is allowed to cheat by ignoring the laws of physics or transport regulations, its cost savings are completely fake.

### 3. The Payroll Math Check
*   **The Test:** If we simulate a month with 2 reserves, and then simulate a month with 20 reserves, does the base payroll cost exactly 10 times as much?
*   **The Result:** Linear math confirmed. ✓
*   **Why it matters:** Earlier versions of the code accidentally charged the airline for reserves *once* per month instead of daily. This simple math check ensures the financial ledger is actually booking costs correctly over time.

### 4. The Seniority Check
*   **The Test:** When a flight breaks and the AI has to draft someone, does the "Senior First" policy always pick the available pilot with the most seniority?
*   **The Result:** Confirmed. ✓
*   **Why it matters:** Drafting follows strict union rules. If the AI drafts out of order, the union will file a grievance and the company will pay massive penalties. The code must prove it can follow these rules flawlessly.

---

### Checks that must be added next (Phase 1a)
- **The Degeneracy Check (The Extremes):** If we run a scenario with 0 sick calls and 0 reserves, the extra cost must be exactly $0. Conversely, if we have *infinite* reserves, the cancellation cost must be exactly $0. Testing these extremes proves the core logic doesn't have any bizarre baseline biases.
- **End-to-End Determinism:** It's not enough for the random sick calls to match; we must prove the final financial ledger matches down to the penny across multiple identical runs.

---

## 8.5 Extending It: The Roadmap (Phase 1a-1e)

The skeleton code is designed to be built upon in five distinct "slices". Here is exactly what needs to be built next, and where the engineers need to write the code:

### Slice 1a: The Housekeeping Slice
*   **The Goal:** Clean up the codebase and add the final automated tests before the real work begins.
*   **Where to code:** 
    *   Break apart the giant `crewsim_skeleton.py` script into smaller, modular files inside an `engine/` folder.
    *   Move all the hard-coded costs (like payroll rates) into a clean `costs_pilots.yaml` configuration file.
    *   Add the Degeneracy and Determinism verification tests (from Section 8.4).

### Slice 1b: The Reality Injection Slice
*   **The Goal:** Stop using fake, synthetic schedules and plug the AI into Air Transat's real historical data.
*   **Where to code:** 
    *   Update `build_roster` to load real historical schedules (Dataset D2). 
    *   Update `build_reserves` to ensure reserves are carved *out of* the total pilot headcount, not just magically added on top.
    *   Update `generate_scenario` so that when a pilot calls in sick, they are actually removed from the available pool.

### Slice 1c: The Strict Legal Rules Slice
*   **The Goal:** Teach the AI the remaining transport regulations and union rules.
*   **Where to code:** 
    *   Update `LegalitySurrogate.check` to enforce rules L3, L4, L5, and L8 (like maximum monthly flying hours and reserve notification limits).

### Slice 1d: The Domino Effect Slice
*   **The Goal:** Teach the AI that drafting a pilot on Monday might cause their Thursday flight to cancel.
*   **Where to code:** 
    *   Build the `CascadeEngine` to calculate the 7-day ripple effect of every draft.
    *   Add the massive "Terminal Penalty" for flights that are still broken at the end of the simulated month.

### Slice 1e: The Management Dashboard Slice
*   **The Goal:** Build the interface so the business can actually use this tool.
*   **Where to code:** 
    *   Build a reporting module that allows management to click on a specific disastrous simulation, drill down into it, and see exactly *why* the AI made a specific draft choice.

---

### The Two Commandments of Extending the Code

If you are an engineer writing new code for this project, you must follow these two rules without exception:

1.  **No `simpy` in the Engine:** The core business logic (inside the `engine/` folder) must **never** import the `simpy` simulation library. The business rules (like "how does a pilot get paid") must remain plain, simple Python classes that can be tested entirely on their own, outside of the simulation clock.
2.  **No "Ghost" Costs:** You can never just add $500 to a "total cost" variable. Every single time the AI spends money, it must write a brand new row to the financial ledger, and it must attach a `root_event_uid` (a receipt ID) explaining *exactly* which event caused that expense.
