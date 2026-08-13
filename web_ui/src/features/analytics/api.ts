/**
 * The cascade-analytics response contract.
 *
 * Mirrors `reporting/cascade_analytics.py`. Two rules carried over from the
 * backend, because they change how these fields must be READ:
 *
 * 1. **Two populations, never averaged together.** `cascadeRate*` comes from
 *    whole-simulation counters (the basis kpis.py and gate V4 use -- they
 *    carry no root_event_uid, so they cannot be attributed to a window).
 *    Everything chain- and dollar-shaped is measurement-window attributed, so
 *    it reconciles with E[C]. Each is labelled where it is displayed.
 *
 * 2. **`null` means "not observed", never zero.** An amplification of 1.0x
 *    would read as "cascades are free"; `null` is "no cascading chain was
 *    seen". The UI must render those differently.
 */

export interface ChainRow {
  sim_time: number;
  event_uid: number;
  category: string;
  crew_id: string | null;
  amount: number;
}

export interface CascadeChain {
  scenario_id: number;
  root_event_uid: number;
  /** Distinct open items sharing this root. 1 = absorbed where it landed. */
  n_items: number;
  cost: number;
  start_minute: number;
  end_minute: number;
  uncovered: boolean;
  categories: string[];
  rows: ChainRow[];
}

export interface PerScenarioRate {
  scenario_id: number;
  n_drafts: number;
  n_cascading_drafts: number;
  /** null when the scenario drafted nobody -- not a rate of zero. */
  rate: number | null;
}

export interface CascadeAnalytics {
  n_scenarios: number;
  // -- rate: whole-simulation population --
  drafts_total: number;
  cascading_drafts_total: number;
  cascade_rate_mean: number | null;
  cascade_rate_max: number | null;
  n_scenarios_with_drafts: number;
  n_scenarios_with_cascade: number;
  share_of_scenarios_with_cascade: number | null;
  per_scenario: PerScenarioRate[];
  // -- economics: measurement-window population --
  n_chains: number;
  n_cascading_chains: number;
  mean_cost_simple_chain: number | null;
  mean_cost_cascading_chain: number | null;
  amplification_ratio: number | null;
  cascading_chain_cost_total: number;
  share_of_chain_cost_from_cascades: number | null;
  chain_size_histogram: Record<string, number>;
  max_chain_size: number;
  tier_mix: Record<string, number>;
  n_uncovered_chains: number;
  // -- reserve-loss mechanism: counted, never priced --
  reserve_loss_cascades: number;
  reserve_blocks_lost: number;
  reserve_loss_note: string;
  exemplar_chains: CascadeChain[];
  depth_note: string;
}

export interface JobEnvelope {
  job_id: string;
  season: string | null;
  num_scenarios: number | null;
  created_at: string;
}

export interface PolicySummary {
  policy: string;
  policy_id: string | null;
  expected_cost: number | null;
  cvar95: number | null;
  /** null when the run predates cascade analytics -- NOT "no cascades". */
  analytics: CascadeAnalytics | null;
}

export interface SummariesResponse extends JobEnvelope {
  summaries: PolicySummary[];
  stale_policies: string[];
  notice: string | null;
}

export interface DrillsResponse extends JobEnvelope {
  drills: (CascadeChain & { policy: string })[];
  /** Chains found across every policy, before the response cap. */
  total_chains: number;
  truncated: boolean;
  depth_note: string | null;
}

export interface ComparisonsResponse extends JobEnvelope {
  comparisons: PolicySummary[];
  paired: boolean;
  pairing_basis: string;
}

export const money = (v: number): string =>
  `$${Math.round(v).toLocaleString()}`;

export const pct = (v: number, digits = 1): string => `${(v * 100).toFixed(digits)}%`;

/** Simulated minutes -> "day N HH:MM", the same clock EventTape prints. */
export const clockOf = (minutes: number): string => {
  const day = Math.floor(minutes / (24 * 60));
  const rem = Math.floor(minutes - day * 24 * 60);
  const hh = String(Math.floor(rem / 60)).padStart(2, '0');
  const mm = String(rem % 60).padStart(2, '0');
  return `day ${day} ${hh}:${mm}`;
};
