# 6. Detailed Data Requirements

**Version:** 3.0 (Air Transat instantiation, engineering edition) · **Date:** 2026-08-05

---
## What this section is

The data contract with Air Transat's operational systems: what has to be extracted, at what grain, how
far back, and what has to be *derived* from it before the simulation can be calibrated.

**The one thing to take away:** two of the three validation gates depend on a dataset that does not
exist yet and has to be reconstructed by a join (§6.3-1). That reconstruction is the schedule risk on
this project. Everything else is ordinary ETL.

---

## 6.1 Source extracts


Grain, required fields, use, and minimum history. "Min history" is driven by what the fit needs, not by
what is convenient — three seasonal cycles is the floor for anything with a season covariate.

| # | Dataset | Grain | Required fields | Used for (Why we need it) | Min history |
|---|---|---|---|---|---|
| **D1** | Crew master | crew member | `crew_id` (pseudonymised), base, position, type ratings + validity dates, seniority number, employment status, hire/termination dates | **Who's Who:** Knowing who is legally allowed to fly which plane, and who gets drafted first (seniority). | current + 24 mo of changes |
| **D2** | Published rosters | crew × block | `crew_id`, block type (pairing / reserve / off / vacation / training / sim), start & end (UTC **and** station local), `pairing_id`, **reserve call type (SC/LC)** | **The Baseline:** Knowing what everyone is scheduled to do today, so we know exactly whose schedule we are breaking when we draft them. | 24–36 mo |
| **D3** | Pairing definitions | pairing × duty × leg | `pairing_id`, base, fleet, position complement, duty periods (report/release), legs with stations & times, credit hours, layover stations | **The Mission:** Knowing the exact schedule of a broken flight so the computer can check if a reserve pilot has enough legal time on their clock to fly it. | 24–36 mo |
| **D4** | Sick-call / absence log | absence event | `crew_id`, notification timestamp, absence start/end, absence type code, affected `pairing_id`(s), base, fleet, category | **The Catalyst:** Teaching the AI when people get sick (e.g., more often in January, or on Mondays) and how long they usually stay sick. | **36 mo minimum** — need ≥3 seasonal cycles |
| **D5** | Reserve utilisation log | call-out event | reserve `crew_id`, call timestamp, report time, assigned `pairing_id`, outcome (assigned / released / no-show) | **Reality Check:** Checking if historical planners actually used the reserves they had, and how much notice they actually gave them. | 24 mo |
| **D6** | Schedule-change / reassignment log | change event | `crew_id`, change timestamp, old block, new block, reason code, initiator (system / planner / IOC) | **The Domino Effect:** Reconstructing history to see how past drafts broke future schedules, so we can prove our simulation isn't cheating. | 24–36 mo |
| **D7** | Pay register / premium codes | pay item | `crew_id`, pay period, pay code, hours or amount, linked duty date | **The Receipts:** Reading real payroll receipts to prove exactly how much a draft costs in real life, rather than guessing. | 24 mo |
| **D8** | OTP / flight movement | flight leg | flight, date, scheduled vs. actual times, IATA delay codes, cancellation flag & reason | **Delay Physics:** Teaching the AI the physics of delays (e.g., how often flights cancel and how delays cascade). | 36 mo |
| **D9** | Weather / IROPS day labels | station-day | station, date, disruption class (or derivable from D8 delay-code density) | **Streaks of Bad Luck:** Teaching the AI that bad weather comes in streaks (a blizzard lasts 3 days, it's not just one random bad day). | 36 mo |
| **D10** | Hotel / deadhead invoices | booking | date, station, cost, linked crew/pairing | **Pricing:** Figuring out the exact dollar cost of a hotel night or a deadhead passenger ticket. | 12–24 mo |
| **D11** | Training & simulator schedule | session | `crew_id`, session type, start/end, requalification deadline | **The Danger Zone:** Knowing exactly when to charge a massive penalty for accidentally pulling a pilot out of their mandatory simulator training. | 12–24 mo |
| **D12** | Collective agreement *(document)* | — | Draft premium %, reserve guarantees, minimum-day rules, **the drafting order**, cap on drafts | **Union Rules:** Getting the official union laws that dictate how much things cost and the legal order we must call people in. | current agreements |

### Air Transat specifics for D12

Two agreements, two cost files. **Do not share coefficients between them.**

| Group | Agreement | Cost file |
|---|---|---|
| Pilots | ALPA — five-year term, 1 May 2025 to 30 April 2030 | `configs/costs_pilots.yaml` |
| Cabin crew | CUPE — Local 4041 (Montréal), 4047 (Toronto), 4078 (Vancouver) | `configs/costs_cabin.yaml` (Phase 2) |

The MVP uses pilots only (§1.5). When cabin crew arrive in Phase 2, note that the three CUPE locals
correspond to the three crew bases — base is not merely a location field for that group, it is also an
agreement boundary.

### A note on D2 that is easy to miss

`reserve call type (SC/LC)` is listed as required, and it is genuinely required, not nice-to-have.
Without it you cannot implement rule L8 (2 h notice for short-call, 12 h for long-call), and without L8
the eligibility rate is structurally near 100% instead of near 30% — because every reserve looks
reachable for every trip. If D2 does not carry call type, find it in D5 or reconstruct it, and flag it
as a Phase-0 blocker rather than proceeding without it.

---

## 6.2 Data Quality & Strict Governance Rules

Because this data contains sensitive employee information and dictates millions of dollars, we must follow strict governance rules.

### 1. Privacy (Québec Law 25 Compliance)
By law, the simulation cannot know who anyone is.
*   **Anonymized Data:** The system must scrub names and employee numbers before it even looks at the data. **Example:** Instead of seeing *"John Doe (Employee #1234)"*, the AI only sees *"Pilot A"*. 
*   **Seniority:** We keep the seniority *rank* (e.g., Pilot A is #12 on the list), but never the name attached to it.
*   **The Union Warning:** Because drafting pays premium money, this tool will accidentally predict exactly who will make the most extra cash this year. **Example:** The dashboard might show that the top 20 most senior pilots take 80% of the premium draft money. It is highly recommended to brief the unions (ALPA and CUPE) on this *before* they see the dashboard, so they understand it's an "earnings distribution" and not a "forced labor burden."

### 2. Timezone Discipline (No Pure UTC)
Aviation happens across timezones, and the Canadian legal rest rules (CARs) are based on the **local time** of the airport the pilot is standing in.
*   **Example:** If a pilot flies from Montreal (YUL) to Paris (CDG), a 10:00 PM departure in Montreal is a 4:00 AM departure in Paris. The legal limits for how long a pilot can stay awake are completely different if their day starts at 10 PM versus 4 AM. 
*   **The Rule:** If the database only saves pure UTC time, the simulation's legal math will break. The data extraction must save the UTC time **plus** the local station time.

### 3. Minimum Passing Grades for Data (The Phase 0 Gates)
Before we are even allowed to start building the simulation, the raw historical data must pass two strict completeness tests:

| The Test | Minimum Passing Grade | Clear Explanation (Why this matters) |
|---|---|---|
| **The Sick Call Link Test** | **95%** | At least 95% of historical sick calls (D4) must successfully link to a real pilot's schedule (D2). **Example:** If 20% of sick calls are just floating in the database attached to nobody, the AI can't learn how sick calls actually break schedules. |
| **The Payroll Link Test (Critical Path)** | **80%** | We must be able to join the schedule-change database (D6) with the payroll receipts (D7) to mathematically prove a draft actually happened 80% of the time. **Example:** If someone's schedule changed, but we can't find the receipt proving they got paid draft premium, we are just guessing. If this fails, the entire project is blocked. |

### 4. The "No Black Boxes" Rule (Versioned Storage)
If an executive asks, *"Why did the AI recommend 15 reserves last Tuesday, but 12 reserves today?"*, an engineer must be able to answer exactly why. 
*   **The Rule:** Every time the AI calculates a result, it must save a digital receipt (a cryptographic hash) of exactly which data, math formulas, and policies it used. 
*   **The Chain of Evidence:** `Exact Data Used` → `Exact Math Formulas` → `Exact Weather Scenario` → `Exact Business Policy` = **Final Result**. There are no untraceable answers.

### Drift monitoring — Phase 3

Monthly refit; alert when sick-call intensity or the regime transition matrix shifts beyond tolerance.
For a leisure carrier this matters more than for a scheduled network carrier: route structure changes
seasonally, so a model fitted on last winter's sun programme may not describe this winter's.

---

## 6.3 Derived Datasets (The Phase 0 Engineering Work)

These four datasets do not exist anywhere in Air Transat's systems. The engineers have to build them from scratch by mixing other datasets together. If these aren't built perfectly, the simulation cannot be trusted.

### 6.3-1 Draft-Event Table (The Hardest Task)

**The Problem:** Airline computer systems rarely have a giant button that says "THIS WAS A DRAFT." There is no `was_drafted` column in the database. Instead, the computer just records that a schedule was changed (Dataset D6), and payroll records that someone got paid a premium (Dataset D7). A "draft" is the hidden intersection between the two.

**The Reconstruction (How to find them):**
To prove a draft happened, the code has to look for a specific recipe:
1. The Operations Center (IOC) changed a schedule at the last minute.
2. The pilot was originally supposed to be on a Day Off, Vacation, or Training.
3. The pilot was suddenly placed on a flight.
4. The payroll system shows they were paid a draft premium for that exact day.

**Example of why this is risky:** If the payroll system doesn't use a unique code for "draft premium" and just lumps it in with "overtime," we will accidentally count regular overtime as drafts. If we can't reliably reconstruct these events, we fail the 80% Reality Check gate from Section 6.2, and we must prominently warn the business that our numbers are just "indicative guesses."

### 6.3-2 Eligibility-Rate Table (The 30% Usability Rule)

**The Problem:** We need to prove our legal math works.
**The Reconstruction:** For every historical sick call in the database, the code must pause time, look at every reserve pilot sitting at home on that exact day, run them through our legal math (L0-L8), and spit out what percentage were actually legal to fly the broken trip. 
**Output:** This shouldn't just be one average number; it must be a full distribution (e.g., "Usually it's 30%, but on Tuesdays it drops to 15%").

### 6.3-3 Cascade Table (The Domino Effect)

**The Problem:** We need to prove the AI understands that fixing a problem today breaks something tomorrow.
**The Reconstruction:** For every draft we found in step 6.3-1, the code must scan that exact pilot's schedule for the next 7 days to see if drawing them caused a future flight to break. 
**Example:** If we draft Pilot A on Monday, did they legally time-out and miss their scheduled flight on Thursday? We must prove this happens roughly 20% of the time, just like real life.

### 6.3-4 Daily Severity Labels (Bad Weather Streaks)

**The Problem:** We need to teach the AI that bad days come in streaks.
**The Reconstruction:** The code groups historical days into four categories (e.g., Normal, Bad, Severe, Nightmare) based on how many flights cancelled and how many people called in sick. It must calculate this **per season**. 
**Example:** A `SEVERE` day in the July Atlantic programme (mostly long delays) behaves completely differently than a `SEVERE` day in the January Sun programme (blizzards causing mass cancellations). You cannot mix them together.

---

## 6.4 The "Holdout" Discipline (No Cheating on the Tests)

> **CRITICAL RULE:** Tweaking the AI's inputs until it magically matches the 30% Usability Rule and the 20% Domino Effect rule proves absolutely nothing. That is just "calibration wearing validation's clothes"—also known as cheating on the test.

**The Concept:**
If you give a student the answers to the final exam before they take it, passing the exam doesn't prove they are smart; it just proves they memorized the answers. The exact same logic applies to AI. If you train the simulation on 2024 data, and then *grade* its accuracy using that exact same 2024 data, of course it will score perfectly! But it will fail miserably when asked to predict 2025. 

**The Rule for this Project:**
To prevent this, you must split your historical data into two strictly separated vaults:
1.  **The Training Vault (e.g., 2023-2024):** You use this data to teach the AI how often people get sick, how much things cost, and how weather works. 
2.  **The Testing Vault (e.g., 2025):** You use this data *only* to grade the AI. The AI has never seen this data before. If the AI predicts a 24% Domino Effect, but the real 2025 data shows 30%, **you must report the 6% gap**. 

**If the AI fails a test, you have three options:**
1.  Find the missing legal rule in the codebase (e.g., did we forget to code the 12-hour rest rule? Are reserves illegally teleporting between bases?).
2.  Widen the acceptable passing grade, but only with explicit written permission from the business.
3.  Downgrade the entire simulation to "advisory only" and print a massive warning on every dashboard so users know it failed validation.

**What you are NEVER allowed to do:**
You are never allowed to silently tweak the math inputs until the AI gets a passing grade. A model that fails a test and honestly admits it is infinitely more valuable to Air Transat than a model that was secretly manipulated to look perfect.
