# Crew Reserve & Drafting Policy Optimization System
## Stochastic Simulation for IOC Recovery Policy Design — Air Transat

**Document type:** Technical Specification & Implementation Plan
**Version:** 3.0 (Air Transat instantiation, engineering edition)
**Date:** 2026-08-05
**Status:** Draft for review

**Scope note:** This system is an **offline policy-simulation and optimization tool**. It is *not* a
real-time decision-support system. Its outputs inform monthly/bid-period reserve planning and
drafting-policy design, not day-of-operation recovery actions.

---

## What this system does, in one paragraph

Air Transat must decide, weeks before each bid period opens, how many crew members to pay to sit at
home on standby. Too many is wasted payroll; too few means drafting crew off their days off, their
trips, their training, and occasionally their vacations — which is paid at a premium, and which breaks
*other* parts of the schedule downstream. This system simulates a bid
period thousands of times under realistic disruption, prices every recovery action, and reports what
each candidate staffing plan would actually have cost. It is a measuring instrument for a decision that
is currently made on judgement.

---

## Glossary — every non-software term used in this specification

This is the complete list, gathered in one place. **You do not need to read it** — every section
repeats the subset it uses, right at the top, so the words are explained where you meet them.
Come back here only when you want to look something up. 
Four vocabularies are in play: airline operations, labour and regulatory language, statistics
and operations research, and simulation methodology.

### Airline operations

| Term | What it means | Example |
|---|---|---|
| **IOC (Integrated Operations Centre)** | The airline's 24/7 control room. When the operation breaks, the IOC decides what to re-plan — which flight to delay, which crew to move, what to cancel. | A freezing-rain morning at YUL: the IOC decides which departures still go and which crews get reassigned. |
| **Bid period** | The scheduling cycle crew bid their schedules for — typically about a month. Schedules are published before it starts and are hard to change afterwards. | Crew submit preferences in week 3; the roster for the next bid period is published in week 4. |
| **Roster** | One crew member's published schedule for a bid period: every trip, day off, vacation and training block. | A roster might read: 3-day trip, 2 days off, 4-day trip, day off, reserve block. |
| **Line holder** | A crew member holding a normal flying schedule (a 'line'), as opposed to a reserve. Line holders are the population that drafting draws from. | 110 of 120 pilots hold lines; the other 10 hold reserve lines. |
| **Pairing** | A multi-day trip: a sequence of flights that starts and ends at the crew member's home base. The unit of work crew are assigned. | YUL to CDG, overnight in Paris, CDG back to YUL — one 3-day pairing. |
| **Duty period** | One continuous stretch of work inside a pairing, measured from report time to release time. Regulated maximum length. | Report 07:00, release 17:30 = a 10.5-hour duty period, inside a 13-hour limit. |
| **Report / release time** | The moment a crew member must be at the aircraft, and the moment they are free. Legality rules are evaluated against local report time. | A 16:00 report for an 18:00 departure — the crew member must be there at 16:00, not 18:00. |
| **Leg** | One flight: one takeoff and one landing. A pairing is made of duty periods, and a duty period is made of legs. | YUL to CDG is one leg. A YUL-CDG-YUL round trip is two. |
| **Credit hours** | The pay hours credited for a pairing. This need not equal the hours actually flown — the exact rule is contractual. | A 3-day pairing with 14 flown hours might credit 18 hours. `[CONFIRM: Finance]` for the real rule. |
| **Crew base** | The airport a crew member is contractually based at. Duty normally starts and ends there; working from elsewhere requires positioning them first. | A YUL-based FO cannot simply pick up a trip departing YYZ — they have to be flown there first. |
| **Fleet / type rating** | The licence endorsement for one specific aircraft type. It does not transfer between types, which makes qualification a hard yes/no, not a cost. | An A330-rated captain cannot fly an A321neo LR trip, however urgent it is. |
| **Position** | The seat or role: Captain (CA) or First Officer (FO) for pilots; the cabin role for flight attendants. | A trip missing its FO cannot be covered by a spare CA. |
| **Position complement** | The set of crew positions a pairing requires in order to operate at all. | An A321neo LR trip needs 1 CA + 1 FO + cabin crew. Missing any one of them means the flight cannot go. |
| **Reserve (standby)** | A crew member paid to be available rather than assigned a trip. Unused reserves are pure cost; used reserves are the cheapest way to fix a hole. | Six reserves sit at home on Tuesday; two get called, four do not — all six are paid. |
| **Short-call / long-call** | The two reserve types, distinguished by how much notice they get before they must report. Short-call is more responsive and more expensive. | This spec's surrogate values (rule L8, section 5.4) are 2 hours for short-call, 12 hours for long-call — placeholders, not contractual figures. |
| **Reserve guarantee** | The pay a reserve receives simply for being on call, whether or not they are used. This is the fixed cost the whole model trades against. | At a placeholder $250/day, 10 reserves for 28 days costs $70,000 before anything happens. |
| **Drafting** | Assigning a crew member who was NOT on reserve — someone on a day off, a trip, training or vacation — to cover flying that has no crew, at premium pay. At Air Transat nothing is exempt and there is no cap on how often one person may be drafted. | No reserve is eligible for a Tuesday trip, so the most senior available FO is called at home on their day off — and is paid a premium for it. |
| **Open time** | Flying that currently has no crew assigned. Effectively the queue of broken flights, which will cancel if nothing covers them in time. | A captain calls in sick at 06:00; their 16:00 departure is now open time with a 16:00 deadline. |
| **Deadhead** | Flying a crew member as a passenger purely to reposition them where they are needed. Costs a seat and consumes duty time. | Flying a YYZ-based FO to YUL as a passenger so they can operate a trip out of Montreal. |
| **Layover** | The overnight rest a crew takes at a station away from their base, mid-pairing. Drives hotel and per-diem cost. | A YUL-CDG pairing lays over in Paris before flying home the next day. |
| **IROPS** | Irregular operations — the umbrella term for anything that breaks the plan: weather, air-traffic control, maintenance, strikes. | A January ice storm closing YUL for six hours is an IROPS event. |
| **Sick call** | A crew member notifying the airline that they cannot work. The most common single cause of open time, and the main random input to this model. | An FO calls at 05:40 to report unfit for a 16:00 departure. |
| **Absence duration** | How long a sick crew member stays unavailable. Multi-day absences break several pairings, not one. | A four-day absence removes that crew member from every trip in the window, generating several open-time items. |
| **Cascade** | A NEW disruption caused by a recovery action. Fixing today's problem with someone who was needed tomorrow moves the problem rather than solving it. | Drafting an FO off Thursday's trip covers Tuesday but leaves Thursday uncovered. |
| **Simulator session (sim)** | Mandatory recurrent training in a full-flight simulator. Slots are booked months ahead and are expensive to lose, which is why it is the highest draft tier. | Cancelling a sim slot wastes the slot and can leave the crew member unqualified to fly until they re-train. |
| **Requalification** | Re-doing training after a qualification lapses. A missed training event can trigger it, costing far more than the session that was missed. | Miss a scheduled check and the crew member may need full requalification before they can fly again. |
| **Station / station-day** | An airport in the network; one airport on one calendar date. The natural grain for weather and delay data. | 'CDG on 14 January' is one station-day, which might be labelled DISRUPTED. |
| **OTP (on-time performance)** | The dataset of scheduled versus actual flight times, with delay and cancellation reasons attached. | Used here to fit the delay model and to label which historical days were bad. |
| **IATA delay codes** | Standard two-character codes recording why a flight was late. The industry's shared vocabulary for blame. | A weather code versus a crew code on the same delay means very different things for this model. |
| **Per diem** | A fixed daily allowance paid to crew for time spent away from base, covering meals and incidentals. | Used here as a positioning cost when a draft requires an overnight away from home. |
| **Premium pay code** | The payroll code recording that an hour was paid at a premium rate rather than a normal one. Crucial here because drafts are usually not recorded anywhere else. | A draft is reconstructed by finding a schedule change that coincides with a draft-premium pay code. |
| **Establishment** | The total number of reserves held — the size of the standby workforce for a bid period. | 'Reserve establishment of 10' means 10 crew members are on reserve lines. |
| **Rest (mandatory rest)** | A legally required interval after a duty during which a crew member cannot be assigned anything at all. Not the same as a day off: rest is generated by the duty that precedes it. | Land at 02:00 after a 10-hour duty and 11 hours of rest are owed — so a 09:00 trip the same morning is illegal, however willing the crew member is. |
| **Schedule block** | One interval on a crew member's calendar with a type attached: pairing, reserve, day off, vacation, training, simulator or rest. The atom the whole model manipulates. | 'Vacation, 12-16 March' is one block. Drafting someone consumes or breaks blocks. |
| **Line & bidding** | A 'line' is one awarded month of work. Crew bid for lines in seniority order — including reserve lines — so reserve slots and flying slots come out of the same pool of people. The same seniority principle governs who is offered a draft. | Awarding 10 reserve lines means 10 fewer flying lines, which is why adding a reserve is not adding a person. |
| **Day off / WFY** | A roster block with no duty assigned. Air Transat's roster code for it is WFY; the model calls the block type DAY_OFF. Crew in this state are the first-choice draft candidates (tier 1). | A trip needs an FO on Tuesday; the most senior crew member showing WFY that day is called, and paid the draft premium. |
| **Premium pay** | Pay above the normal rate, owed when the airline asks for work outside the normal deal — such as a draft. | A draft premium of a placeholder $500 is paid on every draft regardless of what the crew member was doing. |
| **Reserve utilisation** | The share of held reserves that actually get used. Low utilisation means you are paying for standby you did not need. | 10 reserves, 3 called out over the month: utilisation is low and the establishment is probably too large. |
| **Shortfall** | The situation where no eligible reserve exists for an open item, so the choice narrows to drafting or cancelling. | Six reserves, all either off-base, unrested or wrongly rated — that is a shortfall even though nobody is flying. |
| **Service level** | The operational quality promise, expressed here as how much uncovered flying is tolerable and how often. | 'At most 3 uncovered legs, in no more than 5% of months' is a service-level target. |
| **Training (ground / recurrent)** | Scheduled classroom or simulator training crew must complete to stay qualified. Booked well ahead, which is why disrupting it is expensive. | Drafting someone out of ground training (tier 3) also incurs the cost of rescheduling the session. |
| **Aircraft rotation** | The chain of consecutive flights one aircraft flies through a day. A delay early in the chain propagates to everything after it. | Not modelled here (see the out-of-scope table), which is why simulated tail severity is understated. |
| **Alternate** | A second airport a flight can divert to. Long-haul sun and transatlantic routes often have few nearby ones, which raises the cost of things going wrong. | A Caribbean destination with no close alternate makes a cancellation more expensive than a short-haul one. |
| **ATC** | Air traffic control. ATC restrictions — capacity, staffing, weather routing — are a common source of delay outside the airline's control. | A European ATC disruption in the summer peak lengthens duties and can push crews out of legality. |
| **Load factor** | How full a flight is, as a percentage of seats sold. High load factors make a cancellation much more expensive, because more passengers need compensating and rebooking. | A full wide-body cancellation triggers far more APPR compensation than a half-empty narrow-body one. |
| **No-show** | A reserve who cannot be reached or does not report when called. A reserve is not a guaranteed resource. | Recorded in the reserve utilisation log, and a candidate realism improvement for a later phase. |
| **Crew tracking system** | The operational system of record for who is doing what right now, and where schedule changes get logged. It is the source for most datasets here. | Notably, it usually has no field saying 'this was a draft' — which is why draft events must be reconstructed. |

### Labour & regulatory

| Term | What it means | Example |
|---|---|---|
| **Seniority** | Rank ordering of crew by service date, usually as a number where 1 is the most senior. It governs bidding, and here it also governs who gets drafted first. | Air Transat drafts SENIOR FIRST: the order starts at seniority number 1 and works down. Because drafting is premium-paid, this is the ordinary seniority principle applied to desirable work — the same logic as bidding. |
| **Collective agreement (CBA)** | The negotiated contract between the airline and a union. It defines pay premiums, reserve guarantees, the drafting order and any cap on how often one person may be drafted. | The draft premium and the senior-first drafting order both come from the agreement, not from the model. |
| **ALPA** | Air Line Pilots Association — the union representing Air Transat's pilots. | Pilot cost coefficients live in `costs_pilots.yaml`, derived from the ALPA agreement. |
| **CUPE** | Canadian Union of Public Employees — represents Air Transat's cabin crew, through separate locals per base. | Cabin crew coefficients belong in a separate `costs_cabin.yaml`; pilot values must not be reused. |
| **CARs Part VII** | The Canadian Aviation Regulations covering commercial air services, including flight duty and rest limits. The legality surrogate approximates these — it does not implement them. | The 13-hour duty cap in rule L1 is a deliberately conservative stand-in for the real CARs tables. |
| **FDP (flight duty period)** | The regulated maximum working window for a crew member, which varies with start time and how many legs are flown. | Simplified here to a flat 13-hour bound so it stays testable. |
| **APPR** | Canada's Air Passenger Protection Regulations — statutory compensation an airline owes passengers when a delay or cancellation is within its control. | 180 passengers arriving 7 hours late at $700 each is $126,000 — often larger than every crew cost combined. |
| **Law 25** | Quebec's privacy legislation. Drives pseudonymisation of crew identifiers in the analytics corpus. | Crew IDs become surrogate keys at ingestion; seniority is kept as a rank only, never as a name. |
| **Pseudonymisation** | Replacing identifying fields with surrogate keys so records stay linkable but individuals are not directly identifiable. | `C0041` instead of an employee number and a name. |
| **SME (subject-matter expert)** | Here, an IOC duty manager or crew planner — someone who does this job and can say whether the simulated behaviour is plausible. | Gate V5 is an SME walking through a simulated disruption week hour by hour. |

### Statistics & operations research

| Term | What it means | Example |
|---|---|---|
| **Stochastic** | Driven by randomness. A stochastic model produces a distribution of outcomes rather than one answer. | The same reserve plan costs $45,000 in one simulated month and $380,000 in another. |
| **Monte Carlo** | Estimating an answer by simulating many random outcomes and averaging them, when no formula exists. | Run 1,000 simulated Januaries, average the cost — that average is the estimate. |
| **Scenario** | One complete simulated realisation of a whole bid period: every sick call, delay and bad-weather day, in order. | Scenario 47 might contain 62 sick calls with a four-day storm in week two. |
| **Two-stage stochastic program** | An optimisation where you must commit to some decisions BEFORE the uncertainty is revealed, then adjust afterwards with what is left. | Buy reserves in advance (stage 1), then react to whatever January actually does (stage 2). |
| **Here-and-now (first stage)** | The decisions committed before anything is known. They cannot be revised once the period starts. | The reserve vector: how many reserves, of which type, on which days. |
| **Recourse (second stage)** | The adjustment made AFTER the uncertainty is revealed — not 'recovery' in the airline sense, but the corrective decision the model is allowed to take later. | Given a sick call that actually happened, assign a reserve or draft someone. Here the recourse is a fixed rule with parameters, not a free choice. |
| **Expected value E[.]** | The probability-weighted average outcome — here, the mean cost across all simulated scenarios. | E[C] = $50,557 means the average simulated bid period cost that much. |
| **CVaR₀.₉₅ (conditional value at risk)** | The MEAN of all scenarios beyond the 95th percentile — not the worst case, and not the 95th percentile itself. It measures how bad the bad months are on average. | If the worst 5 of 100 simulated months cost 120k, 140k, 150k, 180k and 220k, CVaR is their mean: $162,000. |
| **Tail risk** | Exposure to the rare, expensive outcomes at the far end of the distribution. These are the days that actually determine how many reserves you need. | An ice-storm week that costs eight times an average week is tail risk. |
| **Chance constraint** | A requirement that must hold with at least a given probability, rather than always. | 'Uncovered legs exceed 3 in at most 5% of months' — not 'never exceed 3'. |
| **Poisson process / NHPP** | A standard model for random arrivals spread over time. Non-Homogeneous (NHPP) means the arrival rate itself changes with time of day, day of week or season. | Sick calls arrive more often in January than in May, and more often on Mondays — an NHPP captures that. |
| **Thinning** | A technique for generating a time-varying arrival process: simulate at the maximum rate, then randomly discard arrivals to match the real rate. It is not data filtering. | Generate at the January rate everywhere, then discard most of the May arrivals. |
| **GLM / Negative Binomial** | Regression for count data. Negative Binomial is used instead of Poisson when the counts vary more than Poisson allows (overdispersion) — which absence counts always do. | Fitting daily sick-call counts against season, day-of-week and base as predictors. |
| **Markov chain / transition matrix** | A state machine whose next state depends only on the current one, with fixed probabilities. The matrix holds those probabilities. | A SEVERE day has a 40% chance of being followed by another SEVERE day — which is what produces bad WEEKS, not scattered bad days. |
| **Latent state** | A state that is not directly observed but is inferred from data, and which drives what you do observe. | 'Today's disruption severity' is never recorded anywhere; it is inferred from delays, cancellations and absences together. |
| **Hidden Markov model (HMM)** | A Markov chain whose states are never observed directly; each state instead produces observable data with its own probabilities. Fitting it (Baum-Welch EM) learns the transition matrix and what each state looks like at once; decoding it (Viterbi) gives the most likely state of each day. | The daily regime is fitted this way from flights delayed/cancelled, sick calls and crew on duty: a SEVERE day is one where ~40% of departures run late and sick calls run ~3x a NORMAL day. No D9 label is needed. |
| **Lognormal** | A right-skewed distribution used for durations: most values are small, a few are very large, and none are negative. | Most sick absences are 1-2 days; a few last three weeks. |
| **Erlang-B / Erlang loss** | A classical formula giving the probability that all servers are busy when a new request arrives. Used here as a sanity check on the simulation. | With reserves as 'servers' and sick calls as 'arrivals', the simulation's shortfall rate must match the formula, or there is a bug. |
| **Offered load** | Arrival rate divided by service rate (λ/μ). A dimensionless number expressing how much work is presented per server — not a rate itself. | Load 4.5 against 6 reserves means the pool is usually, but not always, sufficient. |
| **Bayesian optimisation (TPE / GP)** | A search method for expensive, noisy functions: it builds a model of what it has learned so far and uses it to pick where to try next. | Rather than testing all 60 reserve levels, it converges on the promising range in a fraction of the runs. |
| **Ranking and selection (OCBA)** | Statistical procedures for picking the best of a small set of noisy options, and for deciding how many more runs are needed to be confident. | Choosing between four drafting rules whose cost differences are smaller than the run-to-run noise. |
| **Sample-average approximation (SAA)** | Replacing a true expectation you cannot compute with the average over a finite sample of scenarios. | Using the mean of 1,000 simulated months in place of the true expected monthly cost. |
| **Common Random Numbers (CRN)** | Evaluating every option against the SAME random scenarios, so a comparison is not contaminated by luck. The single most valuable technique in this system. | Compare two reserve plans against identical simulated Januaries; the difference reflects the plans, not different weather. |
| **Paired comparison** | Comparing two options scenario by scenario and averaging the DIFFERENCES, rather than comparing two separate averages. Vastly less noisy. | Per-policy spread is on the order of the mean, yet the paired difference resolves to plus or minus $4,139 at only 100 scenarios. |
| **Standard error / confidence interval / t-statistic** | How precisely a mean is estimated; the range it plausibly lies in; and how many standard errors a difference sits from zero. A t of roughly 2 or more means the difference is unlikely to be noise. | '-10,154 ± 4,139, t = -4.8' means the gap is real, not a fluke of sampling. |
| **Variance reduction / stratified sampling** | Techniques that get a more precise answer from the same number of runs. Stratification forces the sample to include the right proportion of rare bad days. | Guaranteeing that 5% of simulated days are SEVERE instead of hoping they turn up. |
| **Gini coefficient** | A concentration measure from 0 (perfectly even) to 1 (everything falls on one individual). Here it describes how PREMIUM EARNINGS from drafting are distributed, not how a burden falls. | A high Gini is the expected result of senior-first allocation, not a warning sign — and when drafts are rare relative to headcount it is arithmetic rather than insight. |
| **Holdout** | Data deliberately kept out of model fitting and used only to test the fitted model. Testing on data you fitted proves nothing. | Fit on 2023-2025, then check the eligibility rate against 2025-2026, which the fit never saw. |
| **Recall / precision** | Recall: what fraction of the real cases you found. Precision: what fraction of what you found was real. | The draft reconstruction must find at least 80% of actual drafts (recall) to be usable. |
| **Sensitivity sweep** | Re-running everything across a range of a parameter to see whether the recommendation changes. If it flips, the recommendation was never solid. | Sweeping the terminal penalty from 1.0x to 3.0x cancellation cost and checking the answer stays at R = 6. |
| **Integer lattice / relaxed-and-rounded** | The decision is whole numbers of people, so the search space is a grid of integer points. 'Relax and round' means solving as if fractional, then rounding. | You cannot staff 6.4 reserves; the optimiser searches over 6 and 7. |
| **Pathwise** | Holding inside each individual simulated month, rather than only on average across months. | 'No crew member is drafted more than twice' must hold in every simulated January, not merely on average over a thousand of them. |
| **Newsvendor model** | The classic single-decision stocking problem: commit to a quantity before demand is known, and pay for having too much or too little. | Reserve sizing is a newsvendor problem with cascades and eligibility bolted on, which is what makes it hard. |

### Simulation methodology

| Term | What it means | Example |
|---|---|---|
| **DES (discrete-event simulation)** | A simulation where the clock jumps from one event to the next rather than ticking. Nothing is computed for the time in between, because nothing changes there. | Jump from a 06:00 sick call straight to the 08:15 assignment decision — the 135 minutes between are never simulated. |
| **Event calendar / next-event time progression** | The ordered queue of scheduled future events, and the rule that the clock advances to whichever is next. Here the calendar is self-extending: handling an event can add new future events. | Executing a draft inserts a cascade disruption three days ahead, which the clock will eventually reach. |
| **Terminating vs steady-state simulation** | A terminating simulation runs over a fixed window and stops. A steady-state one runs until the system settles. Seasonality means this system never settles, so it is terminating by design. | 'Cost of one 28-day bid period' is a terminating question. 'Long-run average queue length' would be a steady-state one. |
| **Warm-up period** | An initial stretch that is simulated but excluded from results, to wash out an unrealistic starting condition. | At t=0 nothing is broken yet, which never happens in reality — so the first 7 days are discarded. |
| **Welch's procedure** | A standard method for choosing warm-up length: plot a smoothed metric across runs and see when it stops trending. | Watch the moving average of open-item count until it flattens; that is where warm-up ends. |
| **Cool-down** | Extra simulated time after the measurement window, so consequences triggered near the end still get to happen and be costed. | A draft on day 27 breaks a trip on day 30 — without cool-down that cost silently disappears. |
| **Replication** | One independent run of the simulation. Results are averaged across replications; here, one replication is one scenario. | 1,000 replications means 1,000 simulated bid periods. |
| **Terminal penalty / terminal value** | A charge applied to whatever is still unresolved when the horizon ends, so a policy cannot look cheap by pushing problems past the finish line. | Without it, leaving a trip uncovered on day 42 would be free, and the model would learn to do exactly that. |
| **Degeneracy test** | Running the model with extreme inputs whose answer you can work out by hand, to prove the machinery is wired correctly. | Zero reserves and zero sick calls must cost exactly zero. If it does not, stop. |
| **Trace validation** | Walking a domain expert through the simulation's event log step by step and asking whether the sequence is plausible. | 'The model drafted this FO at 14:20 — would you have done that?' |
| **Backtest** | Feeding real historical inputs through the model and comparing its output to what actually happened. | Replay last January's real sick calls and check the simulated cost against actual payroll and invoices. |
| **Verification vs validation** | Verification asks 'did we build the thing right' (is the code a correct implementation). Validation asks 'did we build the right thing' (does the model describe reality). | A reproducibility test is verification. Comparing the cascade rate to history is validation. |
| **Accreditation (of a model)** | The formal sign-off that a simulation is fit for its stated purpose, backed by a documented evidence package. | Phase 3 assembles trace validation, backtesting bands and rule comparisons into one accreditation package. |

---
## Reading guide

Read in this order if you are new. Read §4.4 first if you are looking for a number.

| § | File | What it gives you | Read it if you are… |
|---|---|---|---|
| 1 | `1_Problem_Statement.md` | The problem, the two-stage structure, the six modelling principles, what is out of scope and which way each omission biases the answer | …anyone. Start here. |
| 2 | `2_HighLevel_Architecture.md` | Six-layer pipeline, per-layer interfaces, and the four architectural commitments that everything obeys | …writing code |
| 3 | `3_HighLevel_Phased_Approach.md` | Delivery plan as five gated slices; the Phase-0 schedule risk | …planning the work |
| 4 | `4_Implementation_Framework__Library_Stack.md` | Stack, repo layout, engineering standards, and **the parameter registry — the single source of truth for every number** | …looking for a constant, or setting up the repo |
| 5 | `5_Detailed_Implementation_Description.md` | The implementation contract: DES five-component spec, entities, engines, legality rules L0–L8, cost engine | …building the simulation core |
| 6 | `6_Detailed_Data_Requirements.md` | The twelve source extracts, governance, and the four derived datasets that have to be reconstructed | …doing the ETL or Phase-0 calibration |
| 7 | `7_Formal_TwoStage_Stochastic_Program.md` | The mathematics the optimiser minimises, each formula with code and worked arithmetic | …implementing the objective, or reviewing the maths |
| 8 | `8_SimPy_DES_Skeleton_with_CRN_Architecture.md` | The runnable reference implementation, its real output, and an honest list of what it does not do | …about to write the first line of code |
| 9 | `9_Verification__Validation_Plan_Gate_before_any_planning_use.md` | The nine gates that must pass before any output informs a decision | …reviewing, or claiming something is done |
| 10 | `10_Summary_of_Key_Design_Decisions_traceability.md` | Decision register: every non-obvious choice, why, and where it lives | …asking "why does it do it *that* way?" |

**Companion artefacts at the repository root:**

| File | What it is |
|---|---|
| `crewsim_skeleton.py` | The runnable reference implementation (629 lines; `simpy`, `numpy`). `python crewsim_skeleton.py` |
| `SPEC_REVIEW.md` | The review of v2 that drove this revision. Contains the measurement evidence behind every correction listed below. |
| `QUESTIONS_TO_ASK.md` | Every outstanding `[CONFIRM: …]` and open assumption, turned into a question with an owner, a priority and where the answer lands. Start with §1 (IOC) and §6.1 (the data spike). |
| `configs/base.yaml` | Scope, horizon, population and the V9 sensitivity sweeps. The only place these values are set. |
| `spec_sections/_v2_original/` | The v2 documents, unmodified, for comparison. |

---

## Conventions used throughout

| Convention | Meaning |
|---|---|
| `[CONFIRM: <owner>]` | A placeholder value — plausible in magnitude, **not** an Air Transat number. Must be replaced by the named owner before any result informs a decision. |
| **Worked example** | Concrete, arithmetically checkable. Every formula has one. Change a formula, change its example. |
| `→ code` | The preceding mathematics restated as Python-shaped pseudocode. The maths is the contract; the code is the explanation. |
| **D#** | A defect from `SPEC_REVIEW.md`, corrected in this version. |
| ⚠️ | A correction to something v2 stated incorrectly, flagged so reviewers who read v2 notice the change. |

All costs are **CAD**. All timestamps are stored UTC plus station local; legality is evaluated in local
time.

---

## Air Transat instantiation at a glance

| | |
|---|---|
| Crew bases | YUL (Montréal) · YYZ (Toronto) · YVR (Vancouver) `[CONFIRM: Crew Planning]` — inferred from the CUPE cabin-crew locals; the **pilot** base list is unverified. MVP uses YUL. |
| Fleet families | A321 family (A321neo LR, A321-200) · A330 family (A330-200, A330-300) |
| Why that matters | No common type rating across families ⇒ qualification is hard-binding ⇒ **two separate problem instances**, not one bigger search space (§4.5.1) |
| Crew groups | Pilots (ALPA, 2025–2030 agreement) · Cabin crew (CUPE Locals 4041 / 4047 / 4078) — separate cost files, never shared coefficients |
| Seasons | Winter sun (Dec–Apr) · Summer Atlantic (Jun–Sep) · Shoulder — modelled per season, **not** annually averaged (§4.5.2) |
| Regulation | CARs Part VII Subpart 700 (approximated by the legality surrogate) · APPR passenger compensation · Québec Law 25 for crew data |
| Drafting rule | Impact tier first, then **senior first** — mandated, not a decision variable. **Drafting is premium-paid**, so it is sought-after work allocated by seniority, exactly like bidding. No protected blocks and no per-crew cap: the only limits are the legality rules and schedule feasibility. |
| MVP slice | YUL · A321neo LR · First Officer · pilots |

---

## What changed from v2, and why

Version 3.0 does three things: retargets the specification to Air Transat, rewrites it for a software
engineering audience with worked examples throughout, and folds in the corrections from
`SPEC_REVIEW.md`.

### Corrections (each verified by running v2's own reference implementation)

| ID | What was wrong | Effect that was measured | Fixed in |
|---|---|---|---|
| **D1** | Reserve staffing cost booked as one row at `t = 0`, which the warm-up filter discarded | The entire Stage-1 cost was absent from every reported number; E[C] fell monotonically in reserve count (R=40 reported $23,928 vs R=6's $180,464). The model would have recommended the maximum establishment. | §5.8, §7.2, §8 |
| **D2** | Seeding via Python's `hash()`, salted per process | Not reproducible under `joblib` multiprocessing; gate V7 failed by construction | §4.3, §5.2, §8.2 |
| **D3** | **No single-assignment rule existed** — not in the code, not in L1–L9, not in V8 | 1,030 physically impossible assignments across 20 scenarios, plus 80–130 reserve double-bookings | New rule **L0** in §5.4; V8 extended in §9 |
| **D4** | Reserves never consumed; assignment did not remove them from the pool | Reserve productivity overstated | §5.0.4 E3, §8.2 |
| **D5** | Sick calls not bound to roster crew | The sick crew member stayed draftable; demand was exogenous, undercutting the emergence claim | §5.0.4 E1, §5.2 |
| **D6** | `seniority_order` sorted twice, inverted | Both settings returned the most *junior* candidate, and produced bit-identical results. See the v3.1 note below: this means Air Transat's mandated senior-first order was implemented backwards and could not be detected from the output. | §5.6, §8.2 |
| **D7** | Cascade cost double-counted: a separate `Σ q^casc` term on top of cascade items re-entering the queue | Corrupted objective function | §5.7, §7.3 |
| **D8** | Phase 0 proposed tuning inputs until emergent rates matched the 30%/20% targets | Calibration wearing validation's clothes — hitting the target would have proved nothing | §6.4, §9.2 |
| **D9** | Only 4 of 9 specified events implemented in the skeleton | Gap not budgeted despite Phase 1 claiming "the full event set" | §8.1 |
| **D10** | Horizon stated as both 35 and 42 days; terminal penalty set by fiat; fairness constraint written as an expectation but implemented pathwise | Inconsistent spec; unpinned CVaR lever | §4.4.1, §5.0.5, §7.5 |

### Realism improvements

| Improvement | Why |
|---|---|
| **Headcount conservation** (§5.10) | Reserves are bid from the same seniority list as flying lines, so +1 reserve = −1 line holder whose flying someone else must cover. This fixes the recommended *level*, not the shape of the curve: without it, each candidate `R` is evaluated against a different, larger workforce, so a reserve's true opportunity cost is missing and the model will recommend more reserves than it should. |
| **Voluntary pickup exclusion stated plainly** (§1.4) | v2 claimed excluding it was policy-neutral. It is not. It is now recorded as an open limitation with its bias direction named, and **not** approximated by an invented dial — if the layer exists, Crew Planning should describe it and it should be modelled as it works. |
| **Reserves as individuals with rotating lines** (§5.0.2, §5.5) | A scalar count cannot express SC/LC notification windows, reserve days off, or the shortest-remaining-window rule — and produces an eligibility rate near 100%. |
| **Season as an experiment dimension** (§4.5.2) | A leisure carrier's February and July are different problems. The deliverable is a per-bid-period vector, not one number. |
| **Fleet families as separate instances** (§4.5.1) | No common type rating ⇒ cross-fleet terms are infeasible ⇒ two coupled sub-problems, not one doubled search space. |
| **A cost-ranked draft variant in the comparison grid** (§3) | The mandated tier-first rule stays the baseline, but quantifying what it costs relative to a cost-ranked alternative is exactly what this tool is for. |
| **Delivery re-sequenced into five gated slices** (§3) | v2's Phase 1 was one 6–8 week block ending in a single gate. Slice 1a needs no data and starts immediately. |
| **New gate V9: parameter sensitivity** (§9) | Two parameters are set by judgement and both move the answer. A recommendation that flips when a judgement call is nudged is not a recommendation. |

### v3.1 corrections — supplied by the business, 2026-08-05

Two domain assumptions inherited from v2 were wrong. Both were listed as open Labour Relations
questions in §10.5; both are now answered.

| Correction | What v2 assumed | What is actually true | Consequence |
|---|---|---|---|
| **Drafting order** | `seniority_order` was a selectable Stage-2 policy lever with `junior_first` as the default | Air Transat drafts **senior first, always**. It is not selectable. | `seniority_order` becomes a constant. `junior_first` is demoted to a labelled counterfactual that may never appear in a recommendation. Sharpens **D6**: v2's inverted sort meant the *only* order the airline uses was implemented backwards, and the bit-identical output made it undetectable. |
| **Protected blocks** | Rule L9 made `VACATION` and `SIMULATOR` blocks draft-prohibited under `θ.respect_protected` | **No protected-block concept exists** in drafting. No block is contractually exempt. | L9 deleted (not defaulted off), along with `respect_protected` and the `Block.protected` flag and the §7.5 hard constraint. Tiers 4 and 5 are reachable — which makes `tier_cost[4]` a live cost driver rather than a corner case, since senior-first drafting reaches the crew holding the best vacation. |

| **Draft cap** | `max_drafts_per_crew_month` capped drafts at 2 and the selector enforced it | **No cap exists.** A crew member may be drafted as often as legality and their schedule permit. | Constraint removed from the formulation and the code; `n_c` survives as a KPI. Not free: uncapped drafting concentrates on senior crew, and the reference run shows this raising cascades and cost at low reserve levels. |
| **What drafting *is*** | An involuntary imposition, carrying "employee-relations damage" | **Premium-paid work that crew want** — which is precisely why it is allocated senior-first, the same seniority principle as bidding | Retires the "senior-first is the inverse of the industry norm" concern: it isn't inverse, it's the ordinary principle applied to desirable work. Fairness KPIs now read as *distribution of premium earnings*, not distribution of a burden — a reversal that matters in anything shared with ALPA. |

**The structural consequence, which is the important part:** every drafting parameter is now a constant.
θ holds only `reserve_selection` and `allow_cross_base_reserve`, both of which govern *reserve dispatch*.
The problem is a **Stage-1 reserve-sizing problem with a fixed recourse rule**.

This means the system is not a drafting-policy optimiser — there is no drafting policy to optimise. It
is a **reserve-sizing tool that models drafting faithfully as the cost consequence of under-staffing**.
That is arguably a stronger position, since the recourse rule is now a documented fact rather than a
modelled guess. §1.2, §3 and §7.7 have been rewritten to stop promising a search that does not exist.

### Presentation

Rewritten for a software engineering audience. Every formula is followed by a code-shaped restatement
and a worked example with checkable arithmetic. The plain-language analogies from v2 have been replaced
by mechanism-level explanations. All numeric constants now live in one registry (§4.4) rather than
being restated — and drifting — across sections.

---

## The one-week action before Phase 1 dates are committed

Two of the three validation gates depend on a dataset that does not exist yet: Air Transat's crew
tracking system almost certainly has no `was_drafted` column, so draft events must be reconstructed by
joining schedule-change records against premium pay codes (§6.3-1). §6.2 sets the completeness gate at
**≥80% recall**; below that, both the tier distribution and the cascade validation target degrade to
"indicative".

**Run a one-week data spike on D6/D7 first.** Pull one month, attempt the join, measure recall against
a sample labelled by an IOC duty manager. Slice 1a needs no data and runs in parallel, so this spike
costs nothing on the critical path — and if recall comes in low, you want to know in week 1, not
week 7.
