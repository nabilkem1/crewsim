# Glossary

## Terms you may not know

This specification mixes four vocabularies: airline operations, labour and regulatory language,
statistics and operations research, and simulation methodology. None of them is standard software
engineering, and the rest of this section assumes them. Skim the table, or skip it if the words are
already familiar. The same definitions appear in every section that uses the term.


### Airline operations

| Term | What it means | Example |
|---|---|---|
| **Bid period** | The scheduling cycle crew bid their schedules for — typically about a month. Schedules are published before it starts and are hard to change afterwards. | Crew submit preferences in week 3; the roster for the next bid period is published in week 4. |
| **Roster** | One crew member's published schedule for a bid period: every trip, day off, vacation and training block. | A roster might read: 3-day trip, 2 days off, 4-day trip, day off, reserve block. |
| **Line holder** | A crew member holding a normal flying schedule (a 'line'), as opposed to a reserve. Line holders are the population that drafting draws from. | 110 of 120 pilots hold lines; the other 10 hold reserve lines. |
| **Pairing** | A multi-day trip: a sequence of flights that starts and ends at the crew member's home base. The unit of work crew are assigned. | YUL to CDG, overnight in Paris, CDG back to YUL — one 3-day pairing. |
| **Duty period** | One continuous stretch of work inside a pairing, measured from report time to release time. Regulated maximum length. | Report 07:00, release 17:30 = a 10.5-hour duty period, inside a 13-hour limit. |
| **Report / release time** | The moment a crew member must be at the aircraft, and the moment they are free. Legality rules are evaluated against local report time. | A 16:00 report for an 18:00 departure — the crew member must be there at 16:00, not 18:00. |
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
| **Sick call** | A crew member notifying the airline that they cannot work. The most common single cause of open time, and the main random input to this model. | An FO calls at 05:40 to report unfit for a 16:00 departure. |
| **Absence duration** | How long a sick crew member stays unavailable. Multi-day absences break several pairings, not one. | A four-day absence removes that crew member from every trip in the window, generating several open-time items. |
| **Cascade** | A NEW disruption caused by a recovery action. Fixing today's problem with someone who was needed tomorrow moves the problem rather than solving it. | Drafting an FO off Thursday's trip covers Tuesday but leaves Thursday uncovered. |
| **Simulator session (sim)** | Mandatory recurrent training in a full-flight simulator. Slots are booked months ahead and are expensive to lose, which is why it is the highest draft tier. | Cancelling a sim slot wastes the slot and can leave the crew member unqualified to fly until they re-train. |
| **Station / station-day** | An airport in the network; one airport on one calendar date. The natural grain for weather and delay data. | 'CDG on 14 January' is one station-day, which might be labelled DISRUPTED. |
| **Rest (mandatory rest)** | A legally required interval after a duty during which a crew member cannot be assigned anything at all. Not the same as a day off: rest is generated by the duty that precedes it. | Land at 02:00 after a 10-hour duty and 11 hours of rest are owed — so a 09:00 trip the same morning is illegal, however willing the crew member is. |
| **Schedule block** | One interval on a crew member's calendar with a type attached: pairing, reserve, day off, vacation, training, simulator or rest. The atom the whole model manipulates. | 'Vacation, 12-16 March' is one block. Drafting someone consumes or breaks blocks. |
| **Line & bidding** | A 'line' is one awarded month of work. Crew bid for lines in seniority order — including reserve lines — so reserve slots and flying slots come out of the same pool of people. The same seniority principle governs who is offered a draft. | Awarding 10 reserve lines means 10 fewer flying lines, which is why adding a reserve is not adding a person. |
| **Day off / WFY** | A roster block with no duty assigned. Air Transat's roster code for it is WFY; the model calls the block type DAY_OFF. Crew in this state are the first-choice draft candidates (tier 1). | A trip needs an FO on Tuesday; the most senior crew member showing WFY that day is called, and paid the draft premium. |
| **Premium pay** | Pay above the normal rate, owed when the airline asks for work outside the normal deal — such as a draft. | A draft premium of a placeholder $500 is paid on every draft regardless of what the crew member was doing. |
| **Reserve utilisation** | The share of held reserves that actually get used. Low utilisation means you are paying for standby you did not need. | 10 reserves, 3 called out over the month: utilisation is low and the establishment is probably too large. |
| **Training (ground / recurrent)** | Scheduled classroom or simulator training crew must complete to stay qualified. Booked well ahead, which is why disrupting it is expensive. | Drafting someone out of ground training (tier 3) also incurs the cost of rescheduling the session. |

### Labour & regulatory

| Term | What it means | Example |
|---|---|---|
| **Seniority** | Rank ordering of crew by service date, usually as a number where 1 is the most senior. It governs bidding, and here it also governs who gets drafted first. | Air Transat drafts SENIOR FIRST: the order starts at seniority number 1 and works down. Because drafting is premium-paid, this is the ordinary seniority principle applied to desirable work — the same logic as bidding. |
| **CARs Part VII** | The Canadian Aviation Regulations covering commercial air services, including flight duty and rest limits. The legality surrogate approximates these — it does not implement them. | The 13-hour duty cap in rule L1 is a deliberately conservative stand-in for the real CARs tables. |
| **FDP (flight duty period)** | The regulated maximum working window for a crew member, which varies with start time and how many legs are flown. | Simplified here to a flat 13-hour bound so it stays testable. |
| **APPR** | Canada's Air Passenger Protection Regulations — statutory compensation an airline owes passengers when a delay or cancellation is within its control. | 180 passengers arriving 7 hours late at $700 each is $126,000 — often larger than every crew cost combined. |

### Statistics & operations research

| Term | What it means | Example |
|---|---|---|
| **Scenario** | One complete simulated realisation of a whole bid period: every sick call, delay and bad-weather day, in order. | Scenario 47 might contain 62 sick calls with a four-day storm in week two. |
| **Poisson process / NHPP** | A standard model for random arrivals spread over time. Non-Homogeneous (NHPP) means the arrival rate itself changes with time of day, day of week or season. | Sick calls arrive more often in January than in May, and more often on Mondays — an NHPP captures that. |
| **Thinning** | A technique for generating a time-varying arrival process: simulate at the maximum rate, then randomly discard arrivals to match the real rate. It is not data filtering. | Generate at the January rate everywhere, then discard most of the May arrivals. |
| **Markov chain / transition matrix** | A state machine whose next state depends only on the current one, with fixed probabilities. The matrix holds those probabilities. | A SEVERE day has a 40% chance of being followed by another SEVERE day — which is what produces bad WEEKS, not scattered bad days. |
| **Lognormal** | A right-skewed distribution used for durations: most values are small, a few are very large, and none are negative. | Most sick absences are 1-2 days; a few last three weeks. |
| **Common Random Numbers (CRN)** | Evaluating every option against the SAME random scenarios, so a comparison is not contaminated by luck. The single most valuable technique in this system. | Compare two reserve plans against identical simulated Januaries; the difference reflects the plans, not different weather. |
| **Gini coefficient** | A concentration measure from 0 (perfectly even) to 1 (everything falls on one individual). Here it describes how PREMIUM EARNINGS from drafting are distributed, not how a burden falls. | A high Gini is the expected result of senior-first allocation, not a warning sign — and when drafts are rare relative to headcount it is arithmetic rather than insight. |
| **Holdout** | Data deliberately kept out of model fitting and used only to test the fitted model. Testing on data you fitted proves nothing. | Fit on 2023-2025, then check the eligibility rate against 2025-2026, which the fit never saw. |

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

