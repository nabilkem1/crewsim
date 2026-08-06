#!/usr/bin/env python3
"""Generate the per-section 'Terms you may not know' glossaries.

Single source of truth: TERMS below. Every section's glossary is emitted from
it, so a definition can never drift between files.

Rules encoded here:
  * Only non-software concepts (airline ops, labour/regulatory, statistics &
    OR, simulation methodology). SimPy/Parquet/mypy etc. are not glossary items.
  * A term earns a row only if its file uses it as though the reader knows it.
    Terms the body already explains at length are excluded per file.
  * No unverified Air Transat facts in definitions: define generically and
    point at the parameter registry or [CONFIRM] markers.
"""
import re
import pathlib

A, L, S, M = "Airline operations", "Labour & regulatory", "Statistics & operations research", "Simulation methodology"

# term -> (category, definition, example, regex used to prove it appears in the body)
TERMS: dict[str, tuple[str, str, str, str]] = {
# ---------------------------------------------------------------- airline ops
"IOC (Integrated Operations Centre)": (A,
 "The airline's 24/7 control room. When the operation breaks, the IOC decides what to re-plan — which flight to delay, which crew to move, what to cancel.",
 "A freezing-rain morning at YUL: the IOC decides which departures still go and which crews get reassigned.", r"IOC"),
"Bid period": (A,
 "The scheduling cycle crew bid their schedules for — typically about a month. Schedules are published before it starts and are hard to change afterwards.",
 "Crew submit preferences in week 3; the roster for the next bid period is published in week 4.", r"[Bb]id.?period"),
"Roster": (A,
 "One crew member's published schedule for a bid period: every trip, day off, vacation and training block.",
 "A roster might read: 3-day trip, 2 days off, 4-day trip, day off, reserve block.", r"[Rr]oster"),
"Line holder": (A,
 "A crew member holding a normal flying schedule (a 'line'), as opposed to a reserve. Line holders are the population that drafting draws from.",
 "110 of 120 pilots hold lines; the other 10 hold reserve lines.", r"[Ll]ine holder"),
"Pairing": (A,
 "A multi-day trip: a sequence of flights that starts and ends at the crew member's home base. The unit of work crew are assigned.",
 "YUL to CDG, overnight in Paris, CDG back to YUL — one 3-day pairing.", r"[Pp]airing"),
"Duty period": (A,
 "One continuous stretch of work inside a pairing, measured from report time to release time. Regulated maximum length.",
 "Report 07:00, release 17:30 = a 10.5-hour duty period, inside a 13-hour limit.", r"[Dd]uty period|duty block|MAX_DUTY"),
"Report / release time": (A,
 "The moment a crew member must be at the aircraft, and the moment they are free. Legality rules are evaluated against local report time.",
 "A 16:00 report for an 18:00 departure — the crew member must be there at 16:00, not 18:00.", r"[Rr]eport time|report/release|release time"),
"Leg": (A,
 "One flight: one takeoff and one landing. A pairing is made of duty periods, and a duty period is made of legs.",
 "YUL to CDG is one leg. A YUL-CDG-YUL round trip is two.", r"\bleg\b|\blegs\b"),
"Credit hours": (A,
 "The pay hours credited for a pairing. This need not equal the hours actually flown — the exact rule is contractual.",
 "A 3-day pairing with 14 flown hours might credit 18 hours. `[CONFIRM: Finance]` for the real rule.", r"[Cc]redit hours|credit_hours"),
"Crew base": (A,
 "The airport a crew member is contractually based at. Duty normally starts and ends there; working from elsewhere requires positioning them first.",
 "A YUL-based FO cannot simply pick up a trip departing YYZ — they have to be flown there first.", r"\bbase\b|crew base|[Bb]ases"),
"Fleet / type rating": (A,
 "The licence endorsement for one specific aircraft type. It does not transfer between types, which makes qualification a hard yes/no, not a cost.",
 "An A330-rated captain cannot fly an A321neo LR trip, however urgent it is.", r"type rating|fleet"),
"Position": (A,
 "The seat or role: Captain (CA) or First Officer (FO) for pilots; the cabin role for flight attendants.",
 "A trip missing its FO cannot be covered by a spare CA.", r"[Pp]osition"),
"Position complement": (A,
 "The set of crew positions a pairing requires in order to operate at all.",
 "An A321neo LR trip needs 1 CA + 1 FO + cabin crew. Missing any one of them means the flight cannot go.", r"complement"),
"Reserve (standby)": (A,
 "A crew member paid to be available rather than assigned a trip. Unused reserves are pure cost; used reserves are the cheapest way to fix a hole.",
 "Six reserves sit at home on Tuesday; two get called, four do not — all six are paid.", r"[Rr]eserve"),
"Short-call / long-call": (A,
 "The two reserve types, distinguished by how much notice they get before they must report. Short-call is more responsive and more expensive.",
 "This spec's surrogate values (rule L8, section 5.4) are 2 hours for short-call, 12 hours for long-call — placeholders, not contractual figures.", r"[Ss]hort-call|SHORT_CALL|short_call"),
"Reserve guarantee": (A,
 "The pay a reserve receives simply for being on call, whether or not they are used. This is the fixed cost the whole model trades against.",
 "At a placeholder $250/day, 10 reserves for 28 days costs $70,000 before anything happens.", r"guarantee"),
"Drafting": (A,
 "Assigning a crew member who was NOT on reserve — someone on a day off, a trip, training or vacation — to cover flying that has no crew, at premium pay. At Air Transat nothing is exempt and there is no cap on how often one person may be drafted.",
 "No reserve is eligible for a Tuesday trip, so the most senior available FO is called at home on their day off — and is paid a premium for it.", r"[Dd]raft"),
"Open time": (A,
 "Flying that currently has no crew assigned. Effectively the queue of broken flights, which will cancel if nothing covers them in time.",
 "A captain calls in sick at 06:00; their 16:00 departure is now open time with a 16:00 deadline.", r"[Oo]pen time|open-time|OpenTime|open item"),
"Deadhead": (A,
 "Flying a crew member as a passenger purely to reposition them where they are needed. Costs a seat and consumes duty time.",
 "Flying a YYZ-based FO to YUL as a passenger so they can operate a trip out of Montreal.", r"[Dd]eadhead|DEADHEAD"),
"Layover": (A,
 "The overnight rest a crew takes at a station away from their base, mid-pairing. Drives hotel and per-diem cost.",
 "A YUL-CDG pairing lays over in Paris before flying home the next day.", r"[Ll]ayover"),
"IROPS": (A,
 "Irregular operations — the umbrella term for anything that breaks the plan: weather, air-traffic control, maintenance, strikes.",
 "A January ice storm closing YUL for six hours is an IROPS event.", r"IROPS"),
"Sick call": (A,
 "A crew member notifying the airline that they cannot work. The most common single cause of open time, and the main random input to this model.",
 "An FO calls at 05:40 to report unfit for a 16:00 departure.", r"[Ss]ick call|SICK_CALL|sick_call"),
"Absence duration": (A,
 "How long a sick crew member stays unavailable. Multi-day absences break several pairings, not one.",
 "A four-day absence removes that crew member from every trip in the window, generating several open-time items.", r"absence duration|absence start"),
"Cascade": (A,
 "A NEW disruption caused by a recovery action. Fixing today's problem with someone who was needed tomorrow moves the problem rather than solving it.",
 "Drafting an FO off Thursday's trip covers Tuesday but leaves Thursday uncovered.", r"[Cc]ascade"),
"Simulator session (sim)": (A,
 "Mandatory recurrent training in a full-flight simulator. Slots are booked months ahead and are expensive to lose, which is why it is the highest draft tier.",
 "Cancelling a sim slot wastes the slot and can leave the crew member unqualified to fly until they re-train.", r"[Ss]imulator|SIMULATOR"),
"Requalification": (A,
 "Re-doing training after a qualification lapses. A missed training event can trigger it, costing far more than the session that was missed.",
 "Miss a scheduled check and the crew member may need full requalification before they can fly again.", r"[Rr]equal"),
"Station / station-day": (A,
 "An airport in the network; one airport on one calendar date. The natural grain for weather and delay data.",
 "'CDG on 14 January' is one station-day, which might be labelled DISRUPTED.", r"station"),
"OTP (on-time performance)": (A,
 "The dataset of scheduled versus actual flight times, with delay and cancellation reasons attached.",
 "Used here to fit the delay model and to label which historical days were bad.", r"OTP"),
"IATA delay codes": (A,
 "Standard two-character codes recording why a flight was late. The industry's shared vocabulary for blame.",
 "A weather code versus a crew code on the same delay means very different things for this model.", r"[Dd]elay code"),
"Per diem": (A,
 "A fixed daily allowance paid to crew for time spent away from base, covering meals and incidentals.",
 "Used here as a positioning cost when a draft requires an overnight away from home.", r"per-diem|per diem"),
"Premium pay code": (A,
 "The payroll code recording that an hour was paid at a premium rate rather than a normal one. Crucial here because drafts are usually not recorded anywhere else.",
 "A draft is reconstructed by finding a schedule change that coincides with a draft-premium pay code.", r"pay code|premium code|premium pay"),
"Establishment": (A,
 "The total number of reserves held — the size of the standby workforce for a bid period.",
 "'Reserve establishment of 10' means 10 crew members are on reserve lines.", r"establishment"),

# ------------------------------------------------------------ labour & reg.
"Seniority": (L,
 "Rank ordering of crew by service date, usually as a number where 1 is the most senior. It governs bidding, and here it also governs who gets drafted first.",
 "Air Transat drafts SENIOR FIRST: the order starts at seniority number 1 and works down. Because drafting is premium-paid, this is the ordinary seniority principle applied to desirable work — the same logic as bidding.", r"[Ss]eniority"),
"Collective agreement (CBA)": (L,
 "The negotiated contract between the airline and a union. It defines pay premiums, reserve guarantees, the drafting order and any cap on how often one person may be drafted.",
 "The draft premium and the senior-first drafting order both come from the agreement, not from the model.", r"[Cc]ollective agreement|CBA|agreement"),
"ALPA": (L,
 "Air Line Pilots Association — the union representing Air Transat's pilots.",
 "Pilot cost coefficients live in `costs_pilots.yaml`, derived from the ALPA agreement.", r"ALPA"),
"CUPE": (L,
 "Canadian Union of Public Employees — represents Air Transat's cabin crew, through separate locals per base.",
 "Cabin crew coefficients belong in a separate `costs_cabin.yaml`; pilot values must not be reused.", r"CUPE"),
"CARs Part VII": (L,
 "The Canadian Aviation Regulations covering commercial air services, including flight duty and rest limits. The legality surrogate approximates these — it does not implement them.",
 "The 13-hour duty cap in rule L1 is a deliberately conservative stand-in for the real CARs tables.", r"CARs"),
"FDP (flight duty period)": (L,
 "The regulated maximum working window for a crew member, which varies with start time and how many legs are flown.",
 "Simplified here to a flat 13-hour bound so it stays testable.", r"FDP|flight duty"),
"APPR": (L,
 "Canada's Air Passenger Protection Regulations — statutory compensation an airline owes passengers when a delay or cancellation is within its control.",
 "180 passengers arriving 7 hours late at $700 each is $126,000 — often larger than every crew cost combined.", r"APPR"),
"Law 25": (L,
 "Quebec's privacy legislation. Drives pseudonymisation of crew identifiers in the analytics corpus.",
 "Crew IDs become surrogate keys at ingestion; seniority is kept as a rank only, never as a name.", r"Law 25|Loi 25"),
"Pseudonymisation": (L,
 "Replacing identifying fields with surrogate keys so records stay linkable but individuals are not directly identifiable.",
 "`C0041` instead of an employee number and a name.", r"[Pp]seudonym"),
"SME (subject-matter expert)": (L,
 "Here, an IOC duty manager or crew planner — someone who does this job and can say whether the simulated behaviour is plausible.",
 "Gate V5 is an SME walking through a simulated disruption week hour by hour.", r"SME"),

# ------------------------------------------------- statistics & OR
"Stochastic": (S,
 "Driven by randomness. A stochastic model produces a distribution of outcomes rather than one answer.",
 "The same reserve plan costs $45,000 in one simulated month and $380,000 in another.", r"[Ss]tochastic"),
"Monte Carlo": (S,
 "Estimating an answer by simulating many random outcomes and averaging them, when no formula exists.",
 "Run 1,000 simulated Januaries, average the cost — that average is the estimate.", r"Monte Carlo"),
"Scenario": (S,
 "One complete simulated realisation of a whole bid period: every sick call, delay and bad-weather day, in order.",
 "Scenario 47 might contain 62 sick calls with a four-day storm in week two.", r"[Ss]cenario"),
"Two-stage stochastic program": (S,
 "An optimisation where you must commit to some decisions BEFORE the uncertainty is revealed, then adjust afterwards with what is left.",
 "Buy reserves in advance (stage 1), then react to whatever January actually does (stage 2).", r"[Tt]wo-[Ss]tage"),
"Here-and-now (first stage)": (S,
 "The decisions committed before anything is known. They cannot be revised once the period starts.",
 "The reserve vector: how many reserves, of which type, on which days.", r"here[- ]and[- ]now|first[- ]stage|First [Ss]tage"),
"Recourse (second stage)": (S,
 "The adjustment made AFTER the uncertainty is revealed — not 'recovery' in the airline sense, but the corrective decision the model is allowed to take later.",
 "Given a sick call that actually happened, assign a reserve or draft someone. Here the recourse is a fixed rule with parameters, not a free choice.", r"[Rr]ecourse"),
"Expected value E[.]": (S,
 "The probability-weighted average outcome — here, the mean cost across all simulated scenarios.",
 "E[C] = $50,557 means the average simulated bid period cost that much.", r"[Ee]xpected value|E\[C\]|E\[cost\]|\\mathbb\{E\}"),
"CVaR₀.₉₅ (conditional value at risk)": (S,
 "The MEAN of all scenarios beyond the 95th percentile — not the worst case, and not the 95th percentile itself. It measures how bad the bad months are on average.",
 "If the worst 5 of 100 simulated months cost 120k, 140k, 150k, 180k and 220k, CVaR is their mean: $162,000.", r"CVaR"),
"Tail risk": (S,
 "Exposure to the rare, expensive outcomes at the far end of the distribution. These are the days that actually determine how many reserves you need.",
 "An ice-storm week that costs eight times an average week is tail risk.", r"[Tt]ail[- ]risk|tail risk|tail"),
"Chance constraint": (S,
 "A requirement that must hold with at least a given probability, rather than always.",
 "'Uncovered legs exceed 3 in at most 5% of months' — not 'never exceed 3'.", r"[Cc]hance constraint"),
"Poisson process / NHPP": (S,
 "A standard model for random arrivals spread over time. Non-Homogeneous (NHPP) means the arrival rate itself changes with time of day, day of week or season.",
 "Sick calls arrive more often in January than in May, and more often on Mondays — an NHPP captures that.", r"NHPP|Poisson"),
"Thinning": (S,
 "A technique for generating a time-varying arrival process: simulate at the maximum rate, then randomly discard arrivals to match the real rate. It is not data filtering.",
 "Generate at the January rate everywhere, then discard most of the May arrivals.", r"thinn?ed|thinning"),
"GLM / Negative Binomial": (S,
 "Regression for count data. Negative Binomial is used instead of Poisson when the counts vary more than Poisson allows (overdispersion) — which absence counts always do.",
 "Fitting daily sick-call counts against season, day-of-week and base as predictors.", r"GLM|NegBin|Negative Binomial"),
"Markov chain / transition matrix": (S,
 "A state machine whose next state depends only on the current one, with fixed probabilities. The matrix holds those probabilities.",
 "A SEVERE day has a 40% chance of being followed by another SEVERE day — which is what produces bad WEEKS, not scattered bad days.", r"Markov|transition_matrix|transition matrix|severity regime|self-transition"),
"Latent state": (S,
 "A state that is not directly observed but is inferred from data, and which drives what you do observe.",
 "'Today's disruption severity' is never recorded anywhere; it is inferred from delays, cancellations and absences together.", r"[Ll]atent"),
"Lognormal": (S,
 "A right-skewed distribution used for durations: most values are small, a few are very large, and none are negative.",
 "Most sick absences are 1-2 days; a few last three weeks.", r"[Ll]ognormal"),
"Erlang-B / Erlang loss": (S,
 "A classical formula giving the probability that all servers are busy when a new request arrives. Used here as a sanity check on the simulation.",
 "With reserves as 'servers' and sick calls as 'arrivals', the simulation's shortfall rate must match the formula, or there is a bug.", r"Erlang"),
"Offered load": (S,
 "Arrival rate divided by service rate (λ/μ). A dimensionless number expressing how much work is presented per server — not a rate itself.",
 "Load 4.5 against 6 reserves means the pool is usually, but not always, sufficient.", r"offered load|lambda_\{?\\?text\{eff|λ_"),
"Bayesian optimisation (TPE / GP)": (S,
 "A search method for expensive, noisy functions: it builds a model of what it has learned so far and uses it to pick where to try next.",
 "Rather than testing all 60 reserve levels, it converges on the promising range in a fraction of the runs.", r"Bayesian optimi"),
"Ranking and selection (OCBA)": (S,
 "Statistical procedures for picking the best of a small set of noisy options, and for deciding how many more runs are needed to be confident.",
 "Choosing between four drafting rules whose cost differences are smaller than the run-to-run noise.", r"[Rr]anking.{0,4}(and|&).{0,4}selection|OCBA"),
"Sample-average approximation (SAA)": (S,
 "Replacing a true expectation you cannot compute with the average over a finite sample of scenarios.",
 "Using the mean of 1,000 simulated months in place of the true expected monthly cost.", r"[Ss]ample-average"),
"Common Random Numbers (CRN)": (S,
 "Evaluating every option against the SAME random scenarios, so a comparison is not contaminated by luck. The single most valuable technique in this system.",
 "Compare two reserve plans against identical simulated Januaries; the difference reflects the plans, not different weather.", r"CRN|Common Random"),
"Paired comparison": (S,
 "Comparing two options scenario by scenario and averaging the DIFFERENCES, rather than comparing two separate averages. Vastly less noisy.",
 "Per-policy spread is on the order of the mean, yet the paired difference resolves to plus or minus $4,139 at only 100 scenarios.", r"[Pp]aired"),
"Standard error / confidence interval / t-statistic": (S,
 "How precisely a mean is estimated; the range it plausibly lies in; and how many standard errors a difference sits from zero. A t of roughly 2 or more means the difference is unlikely to be noise.",
 "'-10,154 ± 4,139, t = -4.8' means the gap is real, not a fluke of sampling.", r"standard error|confidence interval|t-stat|t = |CI\)"),
"Variance reduction / stratified sampling": (S,
 "Techniques that get a more precise answer from the same number of runs. Stratification forces the sample to include the right proportion of rare bad days.",
 "Guaranteeing that 5% of simulated days are SEVERE instead of hoping they turn up.", r"[Vv]ariance reduction|[Ss]tratifi"),
"Gini coefficient": (S,
 "A concentration measure from 0 (perfectly even) to 1 (everything falls on one individual). Here it describes how PREMIUM EARNINGS from drafting are distributed, not how a burden falls.",
 "A high Gini is the expected result of senior-first allocation, not a warning sign — and when drafts are rare relative to headcount it is arithmetic rather than insight.", r"Gini"),
"Holdout": (S,
 "Data deliberately kept out of model fitting and used only to test the fitted model. Testing on data you fitted proves nothing.",
 "Fit on 2023-2025, then check the eligibility rate against 2025-2026, which the fit never saw.", r"[Hh]oldout"),
"Recall / precision": (S,
 "Recall: what fraction of the real cases you found. Precision: what fraction of what you found was real.",
 "The draft reconstruction must find at least 80% of actual drafts (recall) to be usable.", r"[Rr]ecall|[Pp]recision"),
"Sensitivity sweep": (S,
 "Re-running everything across a range of a parameter to see whether the recommendation changes. If it flips, the recommendation was never solid.",
 "Sweeping the terminal penalty from 1.0x to 3.0x cancellation cost and checking the answer stays at R = 6.", r"[Ss]ensitivity"),
"Integer lattice / relaxed-and-rounded": (S,
 "The decision is whole numbers of people, so the search space is a grid of integer points. 'Relax and round' means solving as if fractional, then rounding.",
 "You cannot staff 6.4 reserves; the optimiser searches over 6 and 7.", r"[Ii]nteger lattice|relaxed-and-rounded"),
"Pathwise": (S,
 "Holding inside each individual simulated month, rather than only on average across months.",
 "'No crew member is drafted more than twice' must hold in every simulated January, not merely on average over a thousand of them.", r"[Pp]athwise"),
"Newsvendor model": (S,
 "The classic single-decision stocking problem: commit to a quantity before demand is known, and pay for having too much or too little.",
 "Reserve sizing is a newsvendor problem with cascades and eligibility bolted on, which is what makes it hard.", r"newsvendor"),

# ------------------------------------------------- simulation methodology
"DES (discrete-event simulation)": (M,
 "A simulation where the clock jumps from one event to the next rather than ticking. Nothing is computed for the time in between, because nothing changes there.",
 "Jump from a 06:00 sick call straight to the 08:15 assignment decision — the 135 minutes between are never simulated.", r"DES|discrete[- ]event"),
"Event calendar / next-event time progression": (M,
 "The ordered queue of scheduled future events, and the rule that the clock advances to whichever is next. Here the calendar is self-extending: handling an event can add new future events.",
 "Executing a draft inserts a cascade disruption three days ahead, which the clock will eventually reach.", r"event calendar|next-event"),
"Terminating vs steady-state simulation": (M,
 "A terminating simulation runs over a fixed window and stops. A steady-state one runs until the system settles. Seasonality means this system never settles, so it is terminating by design.",
 "'Cost of one 28-day bid period' is a terminating question. 'Long-run average queue length' would be a steady-state one.", r"[Tt]erminating|steady state|steady-state"),
"Warm-up period": (M,
 "An initial stretch that is simulated but excluded from results, to wash out an unrealistic starting condition.",
 "At t=0 nothing is broken yet, which never happens in reality — so the first 7 days are discarded.", r"[Ww]arm-?up"),
"Welch's procedure": (M,
 "A standard method for choosing warm-up length: plot a smoothed metric across runs and see when it stops trending.",
 "Watch the moving average of open-item count until it flattens; that is where warm-up ends.", r"Welch"),
"Cool-down": (M,
 "Extra simulated time after the measurement window, so consequences triggered near the end still get to happen and be costed.",
 "A draft on day 27 breaks a trip on day 30 — without cool-down that cost silently disappears.", r"[Cc]ool-?down"),
"Replication": (M,
 "One independent run of the simulation. Results are averaged across replications; here, one replication is one scenario.",
 "1,000 replications means 1,000 simulated bid periods.", r"[Rr]eplication"),
"Terminal penalty / terminal value": (M,
 "A charge applied to whatever is still unresolved when the horizon ends, so a policy cannot look cheap by pushing problems past the finish line.",
 "Without it, leaving a trip uncovered on day 42 would be free, and the model would learn to do exactly that.", r"[Tt]erminal penalty|[Tt]erminal state-value|terminal_penalty"),
"Degeneracy test": (M,
 "Running the model with extreme inputs whose answer you can work out by hand, to prove the machinery is wired correctly.",
 "Zero reserves and zero sick calls must cost exactly zero. If it does not, stop.", r"[Dd]egeneracy"),
"Trace validation": (M,
 "Walking a domain expert through the simulation's event log step by step and asking whether the sequence is plausible.",
 "'The model drafted this FO at 14:20 — would you have done that?'", r"[Tt]race validation"),
"Backtest": (M,
 "Feeding real historical inputs through the model and comparing its output to what actually happened.",
 "Replay last January's real sick calls and check the simulated cost against actual payroll and invoices.", r"[Bb]acktest"),
"Verification vs validation": (M,
 "Verification asks 'did we build the thing right' (is the code a correct implementation). Validation asks 'did we build the right thing' (does the model describe reality).",
 "A reproducibility test is verification. Comparing the cascade rate to history is validation.", r"[Vv]erification|validation gate|validation band"),

# ------------------------------------------- added after reverse-coverage scan
"Rest (mandatory rest)": (A,
 "A legally required interval after a duty during which a crew member cannot be assigned anything at all. Not the same as a day off: rest is generated by the duty that precedes it.",
 "Land at 02:00 after a 10-hour duty and 11 hours of rest are owed — so a 09:00 trip the same morning is illegal, however willing the crew member is.", r"\brest\b|MIN_REST|REST"),
"Schedule block": (A,
 "One interval on a crew member's calendar with a type attached: pairing, reserve, day off, vacation, training, simulator or rest. The atom the whole model manipulates.",
 "'Vacation, 12-16 March' is one block. Drafting someone consumes or breaks blocks.", r"[Ss]chedule [Bb]lock|BlockType|duty block|\bblock\b"),
"Line & bidding": (A,
 "A 'line' is one awarded month of work. Crew bid for lines in seniority order — including reserve lines — so reserve slots and flying slots come out of the same pool of people. The same seniority principle governs who is offered a draft.",
 "Awarding 10 reserve lines means 10 fewer flying lines, which is why adding a reserve is not adding a person.", r"reserve lines|flying lines|\bbid\b|bidding"),
"Day off / WFY": (A,
 "A roster block with no duty assigned. Air Transat's roster code for it is WFY; the model calls the block type DAY_OFF. Crew in this state are the first-choice draft candidates (tier 1).",
 "A trip needs an FO on Tuesday; the most senior crew member showing WFY that day is called, and paid the draft premium.", r"day off|DAY_OFF|days off|WFY"),
"Premium pay": (A,
 "Pay above the normal rate, owed when the airline asks for work outside the normal deal — such as a draft.",
 "A draft premium of a placeholder $500 is paid on every draft regardless of what the crew member was doing.", r"premium"),
"Reserve utilisation": (A,
 "The share of held reserves that actually get used. Low utilisation means you are paying for standby you did not need.",
 "10 reserves, 3 called out over the month: utilisation is low and the establishment is probably too large.", r"utilisation|utilization|UTILIZATION"),
"Shortfall": (A,
 "The situation where no eligible reserve exists for an open item, so the choice narrows to drafting or cancelling.",
 "Six reserves, all either off-base, unrested or wrongly rated — that is a shortfall even though nobody is flying.", r"shortfall"),
"Service level": (A,
 "The operational quality promise, expressed here as how much uncovered flying is tolerable and how often.",
 "'At most 3 uncovered legs, in no more than 5% of months' is a service-level target.", r"service[- ]level"),
"Training (ground / recurrent)": (A,
 "Scheduled classroom or simulator training crew must complete to stay qualified. Booked well ahead, which is why disrupting it is expensive.",
 "Drafting someone out of ground training (tier 3) also incurs the cost of rescheduling the session.", r"ground training|[Tt]raining"),
"Aircraft rotation": (A,
 "The chain of consecutive flights one aircraft flies through a day. A delay early in the chain propagates to everything after it.",
 "Not modelled here (see the out-of-scope table), which is why simulated tail severity is understated.", r"rotation"),
"Alternate": (A,
 "A second airport a flight can divert to. Long-haul sun and transatlantic routes often have few nearby ones, which raises the cost of things going wrong.",
 "A Caribbean destination with no close alternate makes a cancellation more expensive than a short-haul one.", r"alternate"),
"ATC": (A,
 "Air traffic control. ATC restrictions — capacity, staffing, weather routing — are a common source of delay outside the airline's control.",
 "A European ATC disruption in the summer peak lengthens duties and can push crews out of legality.", r"\bATC\b|air-traffic"),
"Load factor": (A,
 "How full a flight is, as a percentage of seats sold. High load factors make a cancellation much more expensive, because more passengers need compensating and rebooking.",
 "A full wide-body cancellation triggers far more APPR compensation than a half-empty narrow-body one.", r"load factor"),
"No-show": (A,
 "A reserve who cannot be reached or does not report when called. A reserve is not a guaranteed resource.",
 "Recorded in the reserve utilisation log, and a candidate realism improvement for a later phase.", r"no-show"),
"Crew tracking system": (A,
 "The operational system of record for who is doing what right now, and where schedule changes get logged. It is the source for most datasets here.",
 "Notably, it usually has no field saying 'this was a draft' — which is why draft events must be reconstructed.", r"crew tracking"),
"Accreditation (of a model)": (M,
 "The formal sign-off that a simulation is fit for its stated purpose, backed by a documented evidence package.",
 "Phase 3 assembles trace validation, backtesting bands and rule comparisons into one accreditation package.", r"accreditation"),
}

# Per-file curated selection. A term is listed only where the body uses it as
# though the reader already knows it (terms the body itself explains at length
# are deliberately omitted from that file).
SELECT: dict[str, list[str]] = {
"1_Problem_Statement.md": [
 "IOC (Integrated Operations Centre)", "Bid period", "Roster", "Line holder", "Pairing", "Crew base",
 "Fleet / type rating", "Position", "Reserve (standby)", "Short-call / long-call", "Reserve guarantee",
 "Drafting", "Open time", "Deadhead", "IROPS", "Sick call", "Cascade",
 "Simulator session (sim)", "Seniority", "Collective agreement (CBA)", "CARs Part VII", "APPR",
 "Stochastic", "Scenario", "Two-stage stochastic program", "Here-and-now (first stage)",
 "Recourse (second stage)", "Tail risk", "Common Random Numbers (CRN)", "Paired comparison",
 "Standard error / confidence interval / t-statistic",
],
"2_HighLevel_Architecture.md": [
 "IOC (Integrated Operations Centre)", "Bid period", "Roster", "Pairing", "Crew base", "Fleet / type rating",
 "Reserve (standby)", "Drafting", "Open time", "Sick call", "Cascade", "Premium pay code", "OTP (on-time performance)",
 "IATA delay codes", "Monte Carlo", "Scenario", "Poisson process / NHPP", "GLM / Negative Binomial",
 "Markov chain / transition matrix", "Latent state", "CVaR₀.₉₅ (conditional value at risk)",
 "Common Random Numbers (CRN)", "Bayesian optimisation (TPE / GP)", "Ranking and selection (OCBA)",
 "DES (discrete-event simulation)", "Warm-up period", "Verification vs validation",
],
"3_HighLevel_Phased_Approach.md": [
 "Bid period", "Roster", "Reserve (standby)", "Short-call / long-call", "Drafting", "Open time",
 "Fleet / type rating", "Seniority", "Premium pay code", "Cascade", "SME (subject-matter expert)",
 "Poisson process / NHPP", "Markov chain / transition matrix", "Holdout", "Recall / precision",
 "Erlang-B / Erlang loss", "CVaR₀.₉₅ (conditional value at risk)", "Chance constraint",
 "Bayesian optimisation (TPE / GP)", "Ranking and selection (OCBA)", "Common Random Numbers (CRN)",
 "Variance reduction / stratified sampling", "Trace validation", "Backtest", "Degeneracy test",
 "Terminal penalty / terminal value", "Warm-up period",
],
"4_Implementation_Framework__Library_Stack.md": [
 "Bid period", "Roster", "Pairing", "Crew base", "Fleet / type rating", "Position", "Reserve (standby)",
 "Short-call / long-call", "Reserve guarantee", "Drafting", "Deadhead", "Per diem", "Requalification",
 "Simulator session (sim)", "Seniority", "Collective agreement (CBA)", "ALPA", "CUPE",
 "CARs Part VII", "APPR", "Law 25", "Poisson process / NHPP", "GLM / Negative Binomial",
 "Markov chain / transition matrix", "Common Random Numbers (CRN)", "Holdout",
 "Warm-up period", "Cool-down", "Terminal penalty / terminal value", "Bayesian optimisation (TPE / GP)",
],
"5_Detailed_Implementation_Description.md": [
 "IOC (Integrated Operations Centre)", "Bid period", "Roster", "Line holder", "Pairing", "Duty period",
 "Report / release time", "Leg", "Credit hours", "Crew base", "Fleet / type rating", "Position",
 "Position complement", "Reserve (standby)", "Short-call / long-call", "Reserve guarantee", "Drafting",
 "Open time", "Deadhead", "Layover", "Sick call", "Absence duration", "Cascade",
 "Simulator session (sim)", "Station / station-day", "Seniority", "CARs Part VII", "FDP (flight duty period)",
 "APPR", "Scenario", "Poisson process / NHPP", "Thinning", "Markov chain / transition matrix", "Lognormal",
 "Gini coefficient", "Common Random Numbers (CRN)", "Holdout", "DES (discrete-event simulation)",
 "Event calendar / next-event time progression", "Terminating vs steady-state simulation", "Warm-up period",
 "Welch's procedure", "Cool-down", "Replication", "Terminal penalty / terminal value",
],
"6_Detailed_Data_Requirements.md": [
 "IOC (Integrated Operations Centre)", "Bid period", "Roster", "Pairing", "Duty period", "Report / release time",
 "Leg", "Credit hours", "Crew base", "Fleet / type rating", "Position", "Reserve (standby)",
 "Short-call / long-call", "Drafting", "Open time", "Deadhead", "Layover", "Sick call", "Cascade",
 "Simulator session (sim)", "Requalification", "Station / station-day",
 "OTP (on-time performance)", "IATA delay codes", "Per diem", "Premium pay code", "Seniority",
 "Collective agreement (CBA)", "ALPA", "CUPE", "Law 25", "Pseudonymisation", "SME (subject-matter expert)",
 "Poisson process / NHPP", "Markov chain / transition matrix", "Holdout", "Recall / precision", "IROPS",
],
"7_Formal_TwoStage_Stochastic_Program.md": [
 "Bid period", "Crew base", "Fleet / type rating", "Position", "Reserve (standby)", "Short-call / long-call",
 "Reserve guarantee", "Drafting", "Open time", "Deadhead", "Cascade", "Seniority",
 "Establishment", "APPR", "Stochastic", "Scenario", "Two-stage stochastic program", "Here-and-now (first stage)",
 "Recourse (second stage)", "Expected value E[.]", "Tail risk", "Chance constraint", "Pathwise",
 "Sample-average approximation (SAA)", "Common Random Numbers (CRN)", "Paired comparison",
 "Standard error / confidence interval / t-statistic", "Erlang-B / Erlang loss", "Offered load",
 "Poisson process / NHPP", "Bayesian optimisation (TPE / GP)", "Ranking and selection (OCBA)",
 "Integer lattice / relaxed-and-rounded", "Newsvendor model", "Terminal penalty / terminal value",
],
"8_SimPy_DES_Skeleton_with_CRN_Architecture.md": [
 "Roster", "Pairing", "Crew base", "Fleet / type rating", "Position", "Reserve (standby)",
 "Short-call / long-call", "Reserve guarantee", "Drafting", "Open time", "Cascade", "Seniority",
 "Sick call", "Scenario", "CVaR₀.₉₅ (conditional value at risk)", "Common Random Numbers (CRN)",
 "Paired comparison", "Standard error / confidence interval / t-statistic",
 "DES (discrete-event simulation)", "Warm-up period", "Terminal penalty / terminal value", "Erlang-B / Erlang loss",
],
"9_Verification__Validation_Plan_Gate_before_any_planning_use.md": [
 "IOC (Integrated Operations Centre)", "Roster", "Pairing", "Reserve (standby)", "Short-call / long-call",
 "Drafting", "Cascade", "Seniority", "Collective agreement (CBA)", "CARs Part VII",
 "SME (subject-matter expert)", "Scenario", "Erlang-B / Erlang loss", "Offered load",
 "Poisson process / NHPP", "Holdout", "Gini coefficient", "Sensitivity sweep",
 "Standard error / confidence interval / t-statistic", "Common Random Numbers (CRN)",
 "Degeneracy test", "Trace validation", "Backtest", "Terminal penalty / terminal value",
],
"10_Summary_of_Key_Design_Decisions_traceability.md": [
 "Bid period", "Roster", "Line holder", "Crew base", "Fleet / type rating", "Position", "Reserve (standby)",
 "Short-call / long-call", "Drafting", "Open time", "Cascade", "Seniority",
 "Collective agreement (CBA)", "ALPA", "CUPE", "CARs Part VII", "APPR", "Law 25",
 "Scenario", "Recourse (second stage)", "CVaR₀.₉₅ (conditional value at risk)", "Chance constraint",
 "Pathwise", "Markov chain / transition matrix", "Common Random Numbers (CRN)", "Holdout",
 "Terminal penalty / terminal value", "Warm-up period", "Cool-down",
],
}

NEW_TERMS = ["Rest (mandatory rest)", "Schedule block", "Line & bidding", "Day off / WFY", "Premium pay",
             "Reserve utilisation", "Shortfall", "Service level", "Training (ground / recurrent)",
             "Aircraft rotation", "Alternate", "ATC", "Load factor", "No-show",
             "Crew tracking system", "Accreditation (of a model)"]
for _f in SELECT:
    SELECT[_f] = SELECT[_f] + [t for t in NEW_TERMS if t not in SELECT[_f]]

CAT_ORDER = [A, L, S, M]
_ORDER = {t: i for i, t in enumerate(TERMS)}

INTRO_BLURB = (
"This specification mixes four vocabularies: airline operations, labour and regulatory language,\n"
"statistics and operations research, and simulation methodology. None of them is standard software\n"
"engineering, and the rest of this section assumes them. Skim the table, or skip it if the words are\n"
"already familiar. The same definitions appear in every section that uses the term.\n"
)


def render(terms: list[str], heading: str = "## Terms you may not know") -> str:
    out = [heading, "", INTRO_BLURB]
    grouped: dict[str, list[str]] = {c: [] for c in CAT_ORDER}
    for t in sorted(terms, key=lambda x: _ORDER[x]):
        grouped[TERMS[t][0]].append(t)
    single_table = len(terms) <= 12
    for cat in CAT_ORDER:
        rows = grouped[cat]
        if not rows:
            continue
        if not single_table:
            out.append(f"### {cat}")
            out.append("")
        out.append("| Term | What it means | Example |")
        out.append("|---|---|---|")
        for t in rows:
            _, defn, ex, _ = TERMS[t]
            out.append(f"| **{t}** | {defn} | {ex} |")
        out.append("")
    out.append("---")
    out.append("")
    return "\n".join(out)


GLOSSARY_HEADS = ("## Terms you may not know",
                  "## Glossary — every non-software term used in this specification")


def strip_existing(body: str, anchor: str) -> str:
    """Make regeneration idempotent: drop a previously inserted glossary."""
    for head in GLOSSARY_HEADS:
        i = body.find(head)
        if i != -1:
            j = body.find(anchor, i)
            assert j != -1, "anchor missing after glossary head"
            body = body[:i] + body[j:]
    return body


def main() -> None:
    root = pathlib.Path("/Users/nabil/Documents/dev/_TS/draft-sim/spec_sections")
    problems: list[str] = []

    # --- per-section files -------------------------------------------------
    for fname, terms in SELECT.items():
        path = root / fname
        anchor = "## What this section is"
        body = strip_existing(path.read_text(), anchor)
        assert body.count(anchor) == 1, f"{fname}: anchor not unique"
        # validation: every glossary term must actually occur in the body
        kept, dropped = [], []
        for t in terms:
            (kept if re.search(TERMS[t][3], body) else dropped).append(t)
        if dropped:
            problems.append(f"{fname}: pruned (not used in body) -> {', '.join(dropped)}")
        path.write_text(body.replace(anchor, render(kept) + anchor, 1))
        print(f"{fname:<62} {len(kept):>3} terms  (pruned {len(dropped)})")

    # --- 00_Intro gets the complete master list ----------------------------
    path = root / "00_Intro.md"
    anchor = "## Reading guide"   # sits just below the one-paragraph summary
    body = strip_existing(path.read_text(), anchor)
    assert body.count(anchor) == 1
    heading = "## Glossary — every non-software term used in this specification"
    corpus = "\n".join(strip_existing((root / f).read_text(),
                                       "## What this section is") for f in SELECT)
    master = [t for t in TERMS if re.search(TERMS[t][3], corpus)]
    unused = [t for t in TERMS if t not in master]
    if unused:
        problems.append("master list: dropped unused -> " + ", ".join(unused))
    block = render(master, heading)
    block = block.replace(INTRO_BLURB,
        "This is the complete list, gathered in one place. **You do not need to read it** — every section\n"
        "repeats the subset it uses, right at the top, so the words are explained where you meet them.\n"
        "Come back here only when you want to look something up. \n"
        "Four vocabularies are in play: airline operations, labour and regulatory language, statistics\n"
        "and operations research, and simulation methodology.\n")
    path.write_text(body.replace(anchor, block + anchor, 1))
    print(f"{'00_Intro.md':<62} {len(master):>3} terms (master list)")

    print("\n--- pruning report ---")
    for p in problems:
        print("  " + p)
    print("\nEvery remaining glossary term is verified present in its file body.")


if __name__ == "__main__":
    main()
