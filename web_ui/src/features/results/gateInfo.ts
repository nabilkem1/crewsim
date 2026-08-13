/**
 * The nine V&V gates, verbatim from spec_sections/9_Verification__Validation_Plan_Gate_before_any_planning_use.md
 * (§9.1 gate list, §9.2 how-to-run detail). This is the single source of
 * truth for gate titles/descriptions shown in the UI -- nothing here is
 * invented, so if the spec's gate list changes, this is the file to update
 * alongside it.
 */

export type GateId = 'V1' | 'V2' | 'V3' | 'V4' | 'V5' | 'V6' | 'V7' | 'V8' | 'V9';

export interface GateInfo {
  title: string;
  kind: 'Verification' | 'Validation';
  nickname: string;
  test: string;
  passCriterion: string;
  detail: string[];
}

export const GATE_INFO: Record<GateId, GateInfo> = {
  V1: {
    title: 'Degeneracy Check',
    kind: 'Verification',
    nickname: 'The Extremes',
    test: 'Run the math on three extreme configurations that are computable on paper: 0 sick calls / 0 reserves / 0 delays, everyone on reserve, and 0 reserves with normal sick calls.',
    passCriterion: 'The simulation outputs exactly $0 where expected (and pure staffing cost / zero staffing cost in the other two configurations).',
    detail: [
      '0 reserves, 0 sick calls, 0 delays -> total cost must be exactly $0.',
      'Everyone is on reserve -> zero drafts, zero cancellations; total cost = pure staffing.',
      '0 reserves, normal sick calls -> every broken flight is either drafted or cancelled; zero staffing costs.',
      'If the simulation disagrees with basic arithmetic on any of these, the engine is wrong before anything more complex is worth testing.',
    ],
  },
  V2: {
    title: 'Erlang-B Bound',
    kind: 'Verification',
    nickname: 'The Textbook Check',
    test: 'Strip the model to the basics -- single base, single fleet, cascades disabled -- and compare its answer against the classic Erlang-B queueing formula for the same offered load.',
    passCriterion: "The simulation's answer matches the closed-form textbook math exactly.",
    detail: [
      'Example: "If we have 5 reserves, and we average 3 sick calls a day, how often will we run out of pilots?" -- the simulation and the textbook formula must independently arrive at the same answer.',
      'If the textbook says 11% and the simulation says 3%, the core queueing logic is fundamentally broken -- e.g. hallucinating that reserves return from flights faster than they actually do.',
    ],
  },
  V3: {
    title: 'Usability Rate',
    kind: 'Validation',
    nickname: 'The 30% Usability Rule',
    test: 'Measure how often reserves were actually legal to fly on historical days, using real roster schedules held out in a Testing Vault the disruption models never trained on.',
    passCriterion: "The simulation's usability (eligibility) rate falls inside the historical confidence band.",
    detail: [
      'Golden rule: never fit inputs to hit the target. Tweaking the math until the rate magically lands on the historical figure is a fake pass, not a validated model.',
      'Honest procedure: train on the Training Vault only, measure eligibility on the completely unseen Testing Vault, and report the gap honestly.',
      'If it fails: find the missing legality mechanism first, widen the tolerance band only with explicit written business sign-off, or downgrade the whole simulation to advisory-only with a warning on every report.',
    ],
  },
  V4: {
    title: 'Domino Effect',
    kind: 'Validation',
    nickname: 'The Trap',
    test: 'Measure how often drafting a pilot causes a future flight to break (a cascading draft), against the same held-out Testing Vault used for V3.',
    passCriterion: "The simulation's cascade rate matches the historical band.",
    detail: [
      'Same golden rule as V3: never fit inputs to hit the target.',
      'Cascades must be emergent from crew state and calendar arithmetic, not a random dice roll -- that is exactly what this gate checks for.',
      'If it fails: find the missing mechanism, widen the tolerance band with business sign-off, or downgrade to advisory-only.',
    ],
  },
  V5: {
    title: 'Trace Validation',
    kind: 'Validation',
    nickname: 'The Expert Walkthrough',
    test: "Replay a real, memorable disruption week and walk real IOC Duty Managers through the simulation's hour-by-hour log.",
    passCriterion: 'The experts agree the choices make logical, real-world sense -- not that the final cost number happens to be right.',
    detail: [
      'The question to ask is never "is this number right?" -- it is "would you have actually done this in real life?"',
      'A model that gets the right final cost by making bizarre, illegal decisions is not validated; it got lucky.',
      'Learning about a real-world recovery trick the model does not know yet counts as a successful test, not a failed one.',
      'This repo has no real Air Transat history to replay, so V5 currently runs against the mock corpus\'s own worst week, labelled as such everywhere it is shown -- it cannot self-certify a PASS; only a real SME walkthrough can.',
    ],
  },
  V6: {
    title: 'Cost Backtest',
    kind: 'Validation',
    nickname: 'The Receipt Check',
    test: "Feed a real historical disruption period into the model and compare its total calculated cost against Air Transat's real payroll and invoice receipts for that same week.",
    passCriterion: 'The cost lands close to the real receipts, in the direction predicted by known excluded mechanisms -- not necessarily exactly on the dollar.',
    detail: [
      'Known biases to expect: excluded voluntary pickup overstates drafting cost; conservative legal rules overstate cost; no network delay propagation understates cost on bad-weather days.',
      'A backtest that lands perfectly on the dollar by accident -- because large errors cancelled out -- is worth less than one that misses in the exact predicted direction.',
      'This repo has no real payroll/invoice data, so V6 currently runs as a labelled mock-data dry run of the same mechanics, never presented as a real PASS.',
    ],
  },
  V7: {
    title: 'CRN Integrity',
    kind: 'Verification',
    nickname: 'The Weather Control Check',
    test: 'Run the exact same reserve policy with the exact same master seed twice, under real multiprocessing (joblib, not a single CPU thread), and compare the financial ledgers byte-for-byte.',
    passCriterion: 'The ledgers match down to the exact penny.',
    detail: [
      'If the random number generator is not strictly controlled across CPU cores, the simulation silently produces different results on every run -- destroying the common-random-numbers trick that makes policy comparisons meaningful.',
    ],
  },
  V8: {
    title: 'Legality Invariants',
    kind: 'Verification',
    nickname: 'The Laws of Physics Check',
    test: "Run thousands of automated property tests scanning every simulated pilot's calendar for physically impossible situations.",
    passCriterion: 'Zero instances of a pilot being assigned to two overlapping duties (Rule L0), and zero violations of mandatory rest (Rule L2).',
    detail: [
      'Physical feasibility is more fundamental than any union rule -- if the model hallucinates teleporting pilots, its cost savings are fake regardless of what else passes.',
    ],
  },
  V9: {
    title: 'Parameter Sensitivity',
    kind: 'Verification',
    nickname: 'The Judgement Call Check',
    test: 'Massively change terminal_penalty and roster_size -- two inputs currently set by judgement rather than measured from Air Transat data -- and see whether the recommendation panics.',
    passCriterion: "The recommended reserve count stays relatively stable across the sweep; it doesn't drastically flip because a judgement call was nudged.",
    detail: [
      'Example failure: recommending "5 reserves" at 1x terminal penalty but flipping to "40 reserves" at 2x means the recommendation rests on a flimsy assumption and cannot be trusted.',
      'A recommendation that flips when a judgement call is nudged is not a recommendation -- it is a coin toss with error bars.',
    ],
  },
};
