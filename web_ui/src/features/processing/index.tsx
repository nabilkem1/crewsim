import { useCallback, useEffect, useRef, useState } from 'react';
import { apiDelete, apiFetch, apiPost, errorMessage } from '../../api/client';
import { ErrorPanel } from '../../components/StatusPanel';
import { ExecutionLog } from '../../components/ExecutionLog';
import { FinishedLog } from '../../components/FinishedLog';
import { Scoreboard, type JobResults } from './Scoreboard';
import { ScenarioFingerprints } from './ScenarioFingerprints';

/**
 * A read-only "scenario tables" preview used to live on this page, rendering
 * five hardcoded rows (CALM 0.8 / 4 calls, SEVERE 2.2 / 12 calls) under the
 * caption "sample snapshot of generated scenario variables". No generator ever
 * produced them. Removed rather than relabelled -- see CODE_REVIEW_API_WEBUI.md
 * on why a plausible number on screen outlives any caption above it.
 */

interface Job {
  id: string;
  type: string;
  status: string;
  progress: number;
  created_at: string;
  error_message?: string;
  results?: JobResults;
}

interface Policy {
  filename: string;
  // Every policy declares the season it was defined for (a required field on
  // the Policy model). Each season has its own independently fitted parameter
  // store, so running a policy against a different season mixes two
  // calibrations -- the API refuses it, and this list never offers it.
  policy: { policy_id: string; season: string };
}

const MAX_SCENARIOS = 1000;
const POLL_MS = 4000;
// A batch run is CPU-bound work sharing this process with the API server
// (see api/routers/processing.py's own note on that trade-off), so a poll
// landing during a busy stretch can time out or 502 without the backend
// actually being down. Surfacing that as a full error panel on every such
// blip made the panel flash in and out once per poll interval -- visible as
// the page flickering, not a real outage. Tolerate a couple of misses
// before saying anything; a genuine outage still gets reported within
// FAILURE_THRESHOLD * POLL_MS.
const FAILURE_THRESHOLD = 3;

/** A cheap signature of exactly the fields the job list renders (results is
 *  only ever set once, when a job first reaches a terminal state, so status
 *  changing already covers it), so a poll tick can skip the state update --
 *  and the re-render it would force on every job row -- when nothing
 *  actually changed. Same fix as calibration/RunMonitor.tsx's poll. */
function jobsSignature(jobs: Job[]): string {
  return jobs.map((j) => `${j.id}:${j.status}:${j.progress}:${j.error_message ?? ''}`).join('|');
}

export const ProcessingDashboard: React.FC = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [selectedPolicies, setSelectedPolicies] = useState<string[]>([]);
  const [numScenarios, setNumScenarios] = useState<number>(100);
  // The backend used to infer a season by substring-matching a filename
  // (`if "W26" in calibration_file`), so any other name silently kept whatever
  // the config already had. It is an explicit, validated season now,
  // preselected from configs/base.yaml -> scope.season so the form always
  // shows which one a run will use rather than naming a value it hides.
  const [season, setSeason] = useState<string>('');
  const [seasons, setSeasons] = useState<string[]>([]);
  // joblib's own convention: 1 = sequential, -1 = every core. Default 1 because
  // the workers run inside the API process.
  // joblib's convention: 1 = sequential, -1 = every core. Only meaningful for
  // more than one policy -- run_grid parallelises ACROSS policies, so a single
  // policy is one joblib task that pays process-spawn and pickling overhead for
  // no concurrency (measured: 8.4s sequential vs 8.8s at n_jobs=-1) and loses
  // per-scenario progress, which cannot cross the process boundary.
  const [nJobs, setNJobs] = useState<number>(1);
  const [error, setError] = useState<string | null>(null);
  const consecutivePollFailures = useRef(0);
  const lastSignature = useRef<string>('');

  const policiesForSeason = policies.filter((p) => !season || p.policy.season === season);

  // Hidden AND forced back to sequential below one policy: leaving a stale
  // n_jobs=-1 applied while the control is off screen would silently cost the
  // progress bar and buy nothing.
  const parallelismApplies = selectedPolicies.length > 1;
  const effectiveJobs = parallelismApplies ? nJobs : 1;

  // Changing season must not leave a policy from the previous one selected --
  // the API would reject the launch, and the checkbox would still look ticked.
  useEffect(() => {
    setSelectedPolicies((prev) => {
      const allowed = new Set(policiesForSeason.map((p) => p.filename.replace('.yaml', '')));
      const kept = prev.filter((id) => allowed.has(id));
      if (kept.length > 0) return kept.length === prev.length ? prev : kept;
      const first = policiesForSeason[0];
      return first ? [first.filename.replace('.yaml', '')] : [];
    });
    // policiesForSeason is derived from these two; depending on the array
    // itself would re-run on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season, policies]);

  const fetchJobs = useCallback(async () => {
    try {
      const data = await apiFetch<Job[]>('/processing/status');
      consecutivePollFailures.current = 0;
      const signature = jobsSignature(data);
      if (signature !== lastSignature.current) {
        lastSignature.current = signature;
        setJobs(data);
      }
      setError(null);
    } catch (e) {
      consecutivePollFailures.current += 1;
      // Stale data stays on screen through a blip -- silently reusing what
      // was already there is more honest than replacing it with an error
      // banner that will likely be gone again by the next tick.
      if (consecutivePollFailures.current >= FAILURE_THRESHOLD) {
        setError(errorMessage(e));
      }
    }
  }, []);

  useEffect(() => {
    apiFetch<Policy[]>('/config/policies')
      .then((data) => setPolicies(data))
      .catch((e) => setError(errorMessage(e)));

    // Seasons come from configs/seasons.yaml, not a hardcoded list. The options
    // here used to be "params_v0.1_W26.json"/"params_v0.1_S26.json" -- parameter
    // filenames, neither of which is a valid scope.season.
    apiFetch<{ seasons: string[]; current: string }>('/config/seasons')
      .then((d) => {
        setSeasons(d.seasons);
        setSeason((cur) => cur || d.current);
      })
      .catch((e) => setError(errorMessage(e)));
  }, []);

  useEffect(() => {
    void fetchJobs();
    // Per-job progress arrives over SSE (ExecutionLog); this slow poll only
    // picks up jobs started elsewhere, so it no longer needs a 2s cadence.
    const interval = setInterval(() => void fetchJobs(), POLL_MS);
    return () => clearInterval(interval);
  }, [fetchJobs]);

  const launchRun = async (isBatch: boolean) => {
    const endpoint = isBatch ? '/processing/batch' : '/processing/run';
    const payload = isBatch
      ? { config_ids: selectedPolicies, num_scenarios: numScenarios, season: season || null, jobs: effectiveJobs }
      : { config_id: selectedPolicies[0], num_scenarios: numScenarios, season: season || null, jobs: 1 };
    try {
      await apiPost(endpoint, payload);
      await fetchJobs();
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const cancelJob = async (jobId: string) => {
    try {
      await apiPost(`/processing/${jobId}/cancel`, {});
      await fetchJobs();
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const deleteJob = async (jobId: string) => {
    try {
      await apiDelete(`/processing/${jobId}`);
      await fetchJobs();
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const renderStatus = (status: string) => {
    const colorMap: Record<string, string> = {
      completed: 'var(--color-success-text)',
      failed: 'var(--color-error-text)',
      running: 'var(--color-info-text)',
      queued: 'var(--color-warning-text)',
    };
    return (
      <span style={{ color: colorMap[status] || 'inherit', fontWeight: 600 }}>
        {status.toUpperCase()}
      </span>
    );
  };

  const btn: React.CSSProperties = {
    padding: 'var(--spacing-2) var(--spacing-4)',
    color: 'white',
    border: 'none',
    borderRadius: 'var(--radius-md)',
    cursor: 'pointer',
    fontSize: '0.875rem',
  };

  const field: React.CSSProperties = {
    padding: 'var(--spacing-2)',
    borderRadius: 'var(--radius-md)',
    border: '1px solid var(--border-default)',
    fontSize: '0.875rem',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-6)' }}>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>Processing Pipeline</h1>

      {error && <ErrorPanel message={error} onRetry={() => void fetchJobs()} />}

      <div
        className="card"
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--spacing-4)',
          padding: 'var(--spacing-4)',
        }}
      >
        <h2
          style={{
            fontSize: '1.1rem',
            margin: 0,
            borderBottom: '1px solid var(--border-default)',
            paddingBottom: 'var(--spacing-2)',
          }}
        >
          Launch Controls
        </h2>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: 'var(--spacing-4)',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
            <strong style={{ fontSize: '0.875rem' }}>
              Select Policies{' '}
              <span style={{ fontWeight: 400, color: 'var(--color-neutral-500)' }}>
                ({season || 'all seasons'})
              </span>
            </strong>
            <div
              style={{
                padding: 'var(--spacing-2)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-default)',
                maxHeight: '120px',
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--spacing-1)',
              }}
            >
              {policiesForSeason.length === 0 && (
                <span style={{ fontSize: '0.8125rem', color: 'var(--color-neutral-500)' }}>
                  No policies defined for <strong>{season}</strong>. Policies live in{' '}
                  <code>configs/policies/</code> and each declares its own season.
                </span>
              )}
              {policiesForSeason.map((p) => {
                const id = p.filename.replace('.yaml', '');
                return (
                  <label
                    key={p.policy.policy_id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--spacing-2)',
                      fontSize: '0.875rem',
                      cursor: 'pointer',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedPolicies.includes(id)}
                      onChange={(e) =>
                        setSelectedPolicies(
                          e.target.checked
                            ? [...selectedPolicies, id]
                            : selectedPolicies.filter((pid) => pid !== id),
                        )
                      }
                    />
                    {p.policy.policy_id} — {p.filename}
                  </label>
                );
              })}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-1)' }}>
              <strong style={{ fontSize: '0.875rem' }}>Number of Scenarios</strong>
              <input
                type="number"
                min={1}
                max={MAX_SCENARIOS}
                value={numScenarios}
                onChange={(e) =>
                  setNumScenarios(
                    Math.min(MAX_SCENARIOS, Math.max(1, parseInt(e.target.value) || 1)),
                  )
                }
                style={field}
              />
            </div>

            {parallelismApplies && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-1)' }}>
                <strong style={{ fontSize: '0.875rem' }}>Parallelism</strong>
                <select
                  value={nJobs}
                  onChange={(e) => setNJobs(Number(e.target.value))}
                  style={field}
                >
                  <option value={1}>Sequential (n_jobs=1)</option>
                  <option value={-1}>All cores (n_jobs=-1)</option>
                  <option value={-2}>All but one core (n_jobs=-2)</option>
                </select>
                <span style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)' }}>
                  Runs policies concurrently. Faster for a grid, but per-scenario progress is
                  unavailable — the bar jumps once to 100%.
                </span>
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-1)' }}>
              <strong style={{ fontSize: '0.875rem' }}>Season</strong>
              <select value={season} onChange={(e) => setSeason(e.target.value)} style={field}>
                {seasons.length === 0 && <option value="">Loading seasons…</option>}
                {seasons.map((sn) => (
                  <option key={sn} value={sn}>
                    {sn}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
            <strong style={{ fontSize: '0.875rem' }}>Execute</strong>
            <button
              onClick={() => void launchRun(false)}
              disabled={selectedPolicies.length === 0}
              style={{
                ...btn,
                backgroundColor: 'var(--color-primary-600)',
                opacity: selectedPolicies.length === 0 ? 0.5 : 1,
              }}
            >
              Single Run (first policy)
            </button>
            <button
              onClick={() => void launchRun(true)}
              disabled={selectedPolicies.length === 0}
              style={{
                ...btn,
                // Chrome, not the neutral ramp: `btn` fixes this button's text
                // to white, and --color-neutral-800 inverts to a near-white
                // fill in dark mode -- white-on-near-white. --chrome-bg is a
                // solid dark fill in both themes (and reuses the same navy the
                // sidebar/primary dark surfaces already use).
                backgroundColor: 'var(--chrome-bg)',
                opacity: selectedPolicies.length === 0 ? 0.5 : 1,
              }}
            >
              Batch Run (grid)
            </button>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 style={{ fontSize: '1.25rem', marginBottom: 'var(--spacing-4)' }}>Job Monitor</h2>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
          {jobs.length === 0 && (
            <div style={{ color: 'var(--color-neutral-500)' }}>No jobs yet.</div>
          )}

          {jobs.map((job) => {
            const active = job.status === 'queued' || job.status === 'running';
            return (
              <div
                key={job.id}
                style={{
                  border: '1px solid var(--border-default)',
                  borderRadius: 'var(--radius-md)',
                  padding: 'var(--spacing-4)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    marginBottom: 'var(--spacing-2)',
                  }}
                >
                  <strong>
                    {job.type} ({job.results?.num_scenarios ?? '?'} scenarios)
                  </strong>
                  {renderStatus(job.status)}
                </div>
                <div
                  style={{
                    fontSize: '0.75rem',
                    color: 'var(--color-neutral-500)',
                    fontFamily: 'var(--font-mono)',
                    marginBottom: 'var(--spacing-2)',
                  }}
                >
                  {job.id}
                </div>

                <div
                  style={{
                    width: '100%',
                    height: '8px',
                    backgroundColor: 'var(--color-neutral-200)',
                    borderRadius: '4px',
                    marginBottom: 'var(--spacing-3)',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      width: `${job.progress}%`,
                      backgroundColor:
                        job.status === 'failed'
                          ? 'var(--color-error-text)'
                          : 'var(--color-primary-500)',
                      transition: 'width 0.3s ease',
                    }}
                  />
                </div>

                {/* Streamed live while the job runs; the recorded log once it ends. */}
                {active ? (
                  <ExecutionLog jobId={job.id} onFinished={fetchJobs} />
                ) : (
                  <FinishedLog jobId={job.id} />
                )}

                {job.results?.scoreboard && (
                  <div style={{ marginTop: 'var(--spacing-4)' }}>
                    <Scoreboard results={job.results} />
                  </div>
                )}

                {/* The distribution behind E[C] and CVaR95. Fetched on demand
                    rather than with the job list: it is one request per job
                    opened, not per poll. */}
                {job.results?.scoreboard && (
                  <details style={{ marginTop: 'var(--spacing-4)' }}>
                    <summary
                      style={{
                        cursor: 'pointer',
                        fontSize: '0.875rem',
                        fontWeight: 600,
                        padding: 'var(--spacing-1) 0',
                      }}
                    >
                      Scenario distribution
                    </summary>
                    <div style={{ marginTop: 'var(--spacing-3)' }}>
                      <ScenarioFingerprints jobId={job.id} />
                    </div>
                  </details>
                )}

                {job.error_message && (
                  <div
                    style={{
                      marginTop: 'var(--spacing-3)',
                      padding: 'var(--spacing-2)',
                      backgroundColor: 'var(--color-error-bg)',
                      color: 'var(--color-error-text)',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.875rem',
                    }}
                  >
                    {job.error_message}
                  </div>
                )}

                <div
                  style={{ display: 'flex', gap: 'var(--spacing-2)', marginTop: 'var(--spacing-3)' }}
                >
                  {active && (
                    <button
                      onClick={() => void cancelJob(job.id)}
                      title="Stop this run at the next scenario boundary"
                      style={{
                        fontSize: '0.875rem',
                        padding: 'var(--spacing-1) var(--spacing-2)',
                        backgroundColor: 'transparent',
                        color: 'var(--color-warning-text)',
                        border: '1px solid var(--color-warning-text)',
                        borderRadius: 'var(--radius-sm)',
                        cursor: 'pointer',
                      }}
                    >
                      Cancel run
                    </button>
                  )}
                  <button
                    onClick={() => void deleteJob(job.id)}
                    style={{
                      fontSize: '0.875rem',
                      padding: 'var(--spacing-1) var(--spacing-2)',
                      backgroundColor: 'transparent',
                      color: 'var(--color-error-text)',
                      border: '1px solid var(--color-error-text)',
                      borderRadius: 'var(--radius-sm)',
                      cursor: 'pointer',
                    }}
                  >
                    Delete
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
