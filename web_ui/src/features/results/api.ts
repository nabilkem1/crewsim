import { apiFetch, apiPost } from '../../api/client';

/**
 * The chart fetchers that used to live here (`fetchGantt`, `fetchWaterfall`,
 * `fetchHeatmap`, `fetchTimeseries`, `fetchEligibility`, `fetchGrid`,
 * `fetchGates`, `fetchDataQuality`, `fetchMetrics`) are gone along with the
 * endpoints behind them, all of which returned hardcoded literals describing a
 * different product. See the API/web-UI review in git history:
 * `git show 7b34d3b:CODE_REVIEW_API_WEBUI.md`.
 */

export interface RunSummary {
  id: string;
  name: string;
  type: string;
  status: string;
  duration: string | null;
  created_at: string;
  has_comparison: boolean;
}

export interface Artifact {
  id: string;
  filename: string;
  type: string;
  size_mb: number;
  url: string;
}

export interface ServiceLevel {
  u_max: number;
  epsilon: number;
  p_uncovered_exceeds_u_max: number;
  service_level_met: boolean;
}

export interface ScoreboardRow {
  policy: string;
  policy_id: string | null;
  policy_hash: string | null;
  costs_version: string | null;
  expected_cost: number | null;
  cvar95: number | null;
  elig: number | null;
  casc: number | null;
  uncovered: number | null;
  cost_by_category: Record<string, number> | null;
  reserve_dispatches_mean: number | null;
  reserve_staffing_days_mean: number | null;
  utilization_rate: number | null;
  service_level: ServiceLevel | null;
}

export interface PairedComparison {
  policy_a: string;
  policy_b: string;
  summary: string;
  evaluated: boolean;
  n_scenarios: number;
  mean_diff: number;
  half_width?: number;
  ci_lower?: number;
  ci_upper?: number;
  t_stat?: number;
  p_value?: number;
  confidence_label?: string;
  reason?: string;
}

/** Shared shape for gate V3 (eligibility) and V4 (cascade) reality-check
 *  verdicts -- see api/routers/processing.py's _v3_verdict/_v4_verdict. */
export interface GateVerdict {
  pass: boolean;
  verdict?: string;
  sim_mean: number;
  ci_lower: number;
  ci_upper: number;
  gap: number;
  n_events: number;
  message: string;
}

export interface RecommendationPoint {
  lambda: number;
  recommended_r: number;
}

export interface Recommendation {
  terminal_penalty: number;
  curve: RecommendationPoint[];
  r_values_compared: number[];
  full_r_sweep: boolean;
  stable: boolean;
  instability_threshold: number;
  excluded_infeasible_r: number[];
}

export interface GateRow {
  gate: string;
  verdict: string;
  detail: string;
}

export interface ConfirmMarker {
  file: string;
  line: number;
  owner: string;
  context: string;
  scope: 'key' | 'section';
}

export interface JobResults {
  scoreboard: ScoreboardRow[];
  comparisons: PairedComparison[];
  v3: GateVerdict | null;
  v4: GateVerdict | null;
  recommendation: Recommendation | null;
  gates: GateRow[];
  confirm_markers: ConfirmMarker[];
  num_scenarios: number;
  season: string;
  master_seed: string;
  params_version: string;
  params_hash: string;
}

export interface JobDetail {
  id: string;
  type: string;
  status: string;
  progress: number;
  created_at: string;
  updated_at: string | null;
  error_message: string | null;
  results: JobResults | null;
}

// ---------------------------------------------------------------- WN-008
export interface LedgerRowJSON {
  scenario_id: number;
  policy_id: string;
  sim_time: number;
  event_uid: number;
  root_event_uid: number;
  crew_id: string | null;
  category: string;
  amount: number;
}

export interface DrilldownChain {
  root_event_uid: number;
  rows: LedgerRowJSON[];
  trace_lines: string[];
}

export interface DrilldownScenario {
  label: 'costliest' | 'typical';
  scenario_id: number;
  cost: number;
  trace: string[];
  chains: DrilldownChain[];
}

export interface DrilldownResults {
  policy: string;
  season: string;
  scenarios: DrilldownScenario[];
}

export interface DrilldownJobDetail {
  id: string;
  status: string;
  progress: number;
  error_message: string | null;
  results: DrilldownResults | null;
}

export const fetchSummaries = () => apiFetch<RunSummary[]>('/results/summaries');
export const fetchArtifacts = () => apiFetch<Artifact[]>('/results/artifacts');
export const fetchJobDetail = (jobId: string) => apiFetch<JobDetail>(`/results/${jobId}`);

export const launchDrilldown = (batchJobId: string, policy: string) =>
  apiPost<{ job_id: string; status: string }>(`/processing/${batchJobId}/drilldown/${policy}`, {});

export const fetchDrilldownJob = (jobId: string) => apiFetch<DrilldownJobDetail>(`/results/${jobId}`);
