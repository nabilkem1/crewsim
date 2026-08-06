# 3. Phased Approach & Delivery Plan

**Version:** 3.0 (Air Transat instantiation, engineering edition) · **Date:** 2026-08-05

---
## What this section is

The delivery plan, expressed as **slices with exit tests** rather than phases with dates. The
organising principle:

> Every slice ends with a test that can *fail*. If a slice has no way to fail, it is not a slice — it
> is a wish.

v2 planned Phase 1 as a single 6–8 week block ending in one big validation gate. That is a two-month
bet on a foundation nobody has checked. This version splits it into five slices, each of which either
passes its gate or tells you something you needed to know earlier.

---

## Phase 0 — Data foundation & calibration

**Duration:** 2–4 weeks, overlapping Phase 1. **Deliverable:** versioned parameter store + data-quality
report.

| Task | Output |
|---|---|
| Land the twelve source extracts (§6.1) into the Parquet/Delta corpus | Corpus + schema tests |
| Reconstruct draft-event history (join schedule changes × premium pay codes, §6.3-1) | Draft-event table + **recall metric** |
| Fit the sick-call NHPP with covariates, **per season** | `sick_call_nhpp` block of the parameter store |
| Fit the severity-regime Markov chain, **per season** | `severity_regime` block |
| Extract validation targets: eligibility rate, cascade rate, crew-status-at-draft distribution | `validation_targets` block, each with a confidence interval |
| Split the data window into a **fitting period and a holdout period** | Two parameter stores; the holdout one is never used for fitting |

> **What is the "crew-status-at-draft distribution"?**
> When someone gets drafted to cover a flight, what were they doing right before their phone rang? Were they sitting at home on a day off (Tier 1), or were they pulled off a future trip (Tier 2), or even interrupted during their vacation (Tier 4)? 
> 
> The *distribution* is simply the historical percentage breakdown of these statuses (e.g., 85% from days off, 13% from future trips, 2% from vacation). 
> 
> **Why is it a Validation Target?** We use this historical breakdown to test if the simulation is telling the truth. If the simulation claims that 40% of our drafts will come from people on vacation, we instantly know the model is broken because it doesn't match the historical reality of 2%. If the simulation hits this target closely, the planners can trust that the model understands the real-world constraints.

### ⚠️ The Critical Data Schedule Risk

The biggest hidden risk in the project timeline is figuring out *when drafts actually happened in the past*. This is called **draft-event reconstruction**, and the later stages of the project cannot proceed without it.

Here is the problem: Airline tracking systems rarely have a simple checkbox that says "This was a draft." Instead, engineers have to play detective. They must cross-reference "schedule change" logs (dataset D6) with "premium pay" logs (dataset D7) to guess when a draft occurred. 

Our goal is to successfully identify at least **80% of all historical drafts**. If we fail to hit this 80% mark, we cannot accurately calculate our "Validation Targets" (like the crew-status distribution mentioned above). If we can't calculate our validation targets, we cannot mathematically prove to the airline that our simulation works.

**Recommendation: Run a one-week "Data Spike" immediately.**
Before committing to any long-term project deadlines, a data engineer should spend one week trying to match D6 and D7 for a single month of historical data. 
*   If they hit the 80% success rate, the project timeline is safe. 
*   If they fail, it means we need a much harder, manual way to identify drafts (like reading through old operations logs). 

You want to discover this problem in Week 1, not Week 7. Because some early development work (Slice 1a) can be done without this data, running this one-week test immediately won't slow down the rest of the team.

---

## Phase 1 — MVP, Delivered as Five Gated Slices

**Overall goal:** Build a working simulation pipeline that can test and compare different backup (reserve) strategies using highly realistic, simulated months.

**MVP Scope:** Keep it simple to start. We will only model First Officers (FO) flying the A321neo LR out of Montreal (YUL).

Instead of building the entire simulation in a dark room and hoping it works at the end, we will build it in **five strict steps (Slices 1a through 1e)**. 
Each step has an "Exit Gate"—a test it *must* pass before the team is allowed to move to the next step. If a step fails its test, development stops until the code is fixed.

### The 5 Steps and Why They Must Happen in This Order

**Step 1a: The Physics Engine & Ledgers (Starts immediately)**
*   **What we build:** The core math, the cost tracking, and the random number generators. We use completely fake, synthetic data here.
*   **Why it's first:** This requires absolutely no real data from the airline, so the engineers can start on Day 1 while the data team is still gathering history (Phase 0). It also forces us to fix foundational bugs early.
*   **The Exit Gate:** If we run the same fake month twice, do we get the *exact* same dollar amount down to the penny? If not, our math is broken.

**Step 1b: Injecting Real People and Rosters**
*   **What we build:** We load real pilot schedules into the simulation. We make sure backup pilots actually need to sleep and take days off, rather than acting like available robots 24/7.
*   **Why it's second:** You can't test if a backup pilot is "eligible" to fly until you prove they are acting like a real human with a real schedule.
*   **The Exit Gate:** Does the rate at which we run out of backup pilots match basic mathematical probability (the Erlang-B formula)?

**Step 1c: The Eligibility Engine**
*   **What we build:** The strict legal rules. When a flight breaks, can *this specific* backup pilot legally take the flight without violating union or safety limits?
*   **Why it's third:** You must know who is legally allowed to fly (1c) *before* you can figure out what happens when you run out of legal pilots (1d).
*   **The Exit Gate:** Does the simulation find legal backup pilots at the same rate the airline historically did? (If the simulation finds a legal pilot 90% of the time, but the real airline only finds one 30% of the time, our rules are too loose).

**Step 1d: The Cascade Engine**
*   **What we build:** The disaster physics. If we draft a pilot to save Tuesday's flight, does that cause them to miss their scheduled Thursday flight? (This is a "cascade").
*   **Why it's fourth:** Cascades only happen when we run out of eligible reserves and have to draft people. So 1c must be perfect first.
*   **The Exit Gate:** Does the rate of these cascading disasters in the simulation match the historical rate of disasters?

**Step 1e: The Dashboard and The Human Test**
*   **What we build:** The final HTML report (like the one shown in Section 2.4). We run 24 different strategy combinations and output the costs.
*   **Why it's last:** You should only bring a finished, polished report to the airline's Duty Managers. You only get one hour of their time; don't waste it showing them a half-finished tool.
*   **The Exit Gate:** Does a veteran airline manager look at a specific simulated disaster and say, *"Yes, that is exactly how this would play out in real life"*? And does the total cost match the airline's actual historical invoices?

### What is the "Hand-Picked Policy Grid"? (Step 1e)

In the MVP (Phase 1), we do not use a complex AI or math robot (optimizer) to guess the best strategy. Instead, we give the simulation a fixed, hand-picked list of realistic options to test. 

We ask the system to test every possible combination of these three choices:

1. **How many reserves?** 4, 6, 8, 10, 12, or 14 backup pilots.
2. **Who gets called first?** When a flight breaks, which backup pilot gets the call? We test five plausible real-world strategies:
    *   **Shortest Remaining Window ("Use it or lose it"):** Call the pilot whose shift ends soonest, so they don't go to waste.
    *   **Seniority ("The Union Ladder"):** Always call the most junior (or senior) pilot first, as dictated by union contracts.
    *   **Lowest Hours Flown ("Equitability"):** Call the pilot who has flown the least this month to prevent burnout.
    *   **First-In, First-Out (FIFO):** A simple queue. Whoever has been sitting on standby the longest gets the call.
    *   **Best Fit ("Least Buffer Waste"):** Call the pilot whose remaining legal flying hours most closely match the length of the broken flight.
3. **Cross-base help?** If Montreal runs out of backups, are they allowed to borrow a backup pilot from Toronto? (True or False).

**(6 reserve levels) × (5 callout rules) × (2 cross-base rules) = 60 total strategies.**

We run all 60 strategies through the exact same 1,000 simulated months. Because the code is highly optimized, this takes a few minutes on a standard laptop—you don't need a supercomputer.

**Notice what is missing from that list: Drafting Rules.**
The grid only tests how to handle *backup* pilots. It does not test how to *draft* regular pilots, because the airline's drafting rules are currently locked in by their union contract (they must draft by Impact Tier, and then Senior-First).

**The "What-If" Counterfactuals**
Even though the drafting rules are locked by the union contract, we still force the simulation to test two "illegal" strategies just to see what happens:
1. **Junior-First:** What if we drafted junior pilots first instead of senior pilots?
2. **Pure Cost-Ranked:** What if we ignored the union's "Impact Tiers" completely, and just drafted whoever was the absolute cheapest?

These are called **counterfactuals**. We don't run these to recommend that the airline break their contract. We run them to put an exact price tag on the contract. If the airline knows that the "Senior-First" rule is costing them $500,000 a year compared to "Junior-First," they have powerful data for their next union negotiation. That is exactly what this tool is built for.

---

## Phase 2 — Optimization & Scale

**Duration:** 6–10 weeks (starts only after Phase 1 passes all tests).

In Phase 1, we built a working engine and gave it a small, hand-picked list of 60 strategies to test. In Phase 2, we take off the training wheels, scale the tool to the whole airline, and add an AI to find the perfect strategy.

*   **Adding the "AI Optimizer":** Instead of humans guessing which strategies to test, we plug in an advanced AI search algorithm (Bayesian Optimization). It can automatically explore thousands of combinations of reserve levels and callout rules to find the absolute mathematically "best" answer.
*   **The Management "Risk Dial":** The AI won't just blindly search for the "cheapest average" strategy, because the cheapest average usually causes disasters when things go wrong. We give management a "Risk Dial" (λ). They can tune the AI to either maximize everyday savings (risk-neutral) or protect against nightmare disaster months (risk-averse).
*   **Expanding to the Whole Airline:** We expand the simulation from just one aircraft type in Montreal to *all* aircraft (A330, A321) across all bases (YUL, YYZ). Importantly, because an A321 pilot cannot legally fly an A330, the AI treats these as separate, parallel problems so the math doesn't get confused.
*   **Adding Cabin Crew:** Flight attendants are added to the simulation. Because they have an entirely different union contract (CUPE) than the pilots (ALPA), they get their own dedicated cost rules and impact tiers. 
*   **Adding "Volunteers":** Phase 1 only modeled forced drafts. Phase 2 adds the logic for pilots who voluntarily pick up open flights for extra premium pay.
*   **Cloud Computing:** We move the simulation from running on a single engineer's laptop to running on the airline's cloud servers (Ray on AKS) so the AI can test thousands of scenarios in minutes.

---

## Phase 3 — Enterprise Hardening

**Duration:** Ongoing, after Phase 2 is actually being used by planners.

This phase is about turning a powerful engineering tool into a bulletproof, user-friendly software product that the airline relies on every month.

*   **Self-Updating Data:** The real world changes constantly (e.g., a new COVID wave causes sick calls to spike). The system will automatically pull fresh historical data every month. If it notices that the rate of sick calls has drastically changed in the real world, it will automatically alert the engineers and adjust its own physics.
*   **Domino-Effect Delays:** We add the physics of "delay propagation." If a morning flight to Cancun is delayed by 3 hours, how does that cascade and break the crew schedules for the rest of the day? 
*   **Plugging into the Real Legal Engine:** In earlier phases, the simulation uses simplified math to guess if a pilot is legally allowed to fly. In Phase 3, we plug the simulation directly into the airline's actual legal rules engine to guarantee perfect accuracy.
*   **Official Dashboards:** We move away from text files and build a polished web dashboard (like Power BI) that crew planners can log into and use as part of their official monthly workflow.
*   **Live "Day-Of" Tool (Optional Future Goal):** Currently, the tool is for long-term monthly planning. Eventually, the Operations Center could use a "live" version of this tool on a Tuesday afternoon to ask, *"Our flight to Paris just broke, what is the cheapest way to fix it right now?"*

---

## 3.1 The "Done" Checklist (How to know a step is actually finished)

An engineering step (or "slice") is only considered **done** when it passes its Exit Gate test *and* every item on this checklist is true. This is a strict rule, not a suggestion:

1. **The test is fully automated.** The Exit Gate test must be written into the code's automated testing pipeline (CI). It cannot just be a script that one engineer ran once on their laptop.
2. **No hidden "magic numbers".** Every single cost, probability, or rule must be pulled from the official data files. An engineer is never allowed to hardcode a number (like `cost = 500`) directly into the code.
3. **The code is strictly typed.** The core simulation engine must pass strict automated code-quality checks (`mypy --strict`) with zero errors.
4. **We know the test's blind spots.** The team must document exactly what their Exit Gate test is good at catching, and what it might accidentally miss.
5. **Managing Placeholders.** We cannot always wait for the airline to confirm exact numbers before building. If a piece of data is unconfirmed (like the exact cost of a hotel room), it must be loaded from a designated config file or dataset—*never* hardcoded—and it must be visibly flagged with `[CONFIRM: SME]` so the Subject Matter Experts know they need to verify it. A step is not fully "done" for production until all SME flags in that step are resolved.

**Rule #5 is the most important one to watch out for.** It is very easy to build a perfectly functioning simulation, feed it placeholder costs from a config file, forget to ask the SME to verify them, and end up with a beautifully mathematically-perfect wrong answer.
