import React, { useState, useEffect, useRef } from 'react';
import { ResultsInspector } from './ResultsInspector';
import { ExecutionLog } from '../../components/ExecutionLog';
import { FinishedLog } from '../../components/FinishedLog';

interface Job {
  id: string;
  type: string;
  status: string;
  progress: number;
  created_at: string;
  /** Resolved at launch, so it is present for queued and failed runs too. */
  season: string | null;
}

/** A cheap signature of exactly the fields this component renders, so a poll
 *  tick can tell "nothing changed" apart from "something changed" before
 *  touching state. */
function jobsSignature(jobs: Job[]): string {
  return jobs.map((j) => `${j.id}:${j.status}:${j.progress}:${j.season ?? ''}`).join('|');
}

export const RunMonitor: React.FC = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedJobs, setSelectedJobs] = useState<Set<string>>(new Set());

  // Accordion state
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'results' | 'logs'>('results');

  // `fetch('/api/jobs')` returns a brand-new array/objects every poll even
  // when nothing on screen should change. Calling setJobs with that every
  // 2 seconds forced a full re-render of the whole list on every tick,
  // forever -- including every job row's checkbox, which is what made the
  // page visibly flicker even at rest (an idle instrument would show this
  // was the case: React DOM was re-touching every <input>'s attributes
  // every 2s with 0 actual data changes). Skip the state update entirely
  // when the fetched data is equivalent to what's already rendered.
  //
  // `null`, not `''`: an EMPTY job list also has the signature `''`, so a
  // string sentinel made "no jobs" indistinguishable from "nothing fetched
  // yet". Deleting the LAST run therefore compared '' !== '' , skipped
  // setJobs, and left the deleted row on screen until something else changed
  // -- and `deleteJobs` resetting the sentinel to '' to force a refresh was
  // the very thing that guaranteed the comparison would match. null can never
  // be a real signature, so it always forces the update.
  const lastSignature = useRef<string | null>(null);

  const fetchJobs = async () => {
    try {
      const res = await fetch('/api/jobs');
      if (res.ok) {
        const data = await res.json();
        const calibrationJobs: Job[] = data.filter((j: Job) => j.type === 'calibration');
        const signature = jobsSignature(calibrationJobs);
        if (signature !== lastSignature.current) {
          lastSignature.current = signature;
          setJobs(calibrationJobs);
        }
      }
    } catch (err) {
      console.error('Failed to fetch jobs', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 2000);
    return () => clearInterval(interval);
  }, []);

  const toggleSelection = (jobId: string) => {
    const newSet = new Set(selectedJobs);
    if (newSet.has(jobId)) {
      newSet.delete(jobId);
    } else {
      newSet.add(jobId);
    }
    setSelectedJobs(newSet);
  };

  const handleCompare = () => {
    window.dispatchEvent(new CustomEvent('CALIBRATION_COMPARE', { detail: { jobIds: Array.from(selectedJobs) } }));
  };

  const deleteJobs = async (jobIds: string[]) => {
    await Promise.all(
      jobIds.map((id) =>
        fetch(`/api/jobs/${id}`, { method: 'DELETE' }).catch((err) =>
          console.error(`Failed to delete job ${id}`, err),
        ),
      ),
    );
    setSelectedJobs((prev) => {
      const next = new Set(prev);
      jobIds.forEach((id) => next.delete(id));
      return next;
    });
    if (expandedJobId && jobIds.includes(expandedJobId)) setExpandedJobId(null);
    // Bypass the "skip if unchanged" signature check: a delete always
    // changes the id set, but force a fetch regardless of poll timing so
    // the row disappears immediately rather than up to 2s later.
    lastSignature.current = null;
    await fetchJobs();
  };

  const deleteJob = (jobId: string) => {
    if (!window.confirm('Delete this calibration run? This cannot be undone.')) return;
    void deleteJobs([jobId]);
  };

  const deleteSelected = () => {
    const ids = Array.from(selectedJobs);
    if (ids.length === 0) return;
    if (!window.confirm(`Delete ${ids.length} calibration run(s)? This cannot be undone.`)) return;
    void deleteJobs(ids);
  };

  const getTabStyle = (tab: string) => ({
    padding: 'var(--spacing-1) var(--spacing-3)',
    backgroundColor: activeTab === tab ? 'var(--color-primary-100)' : 'transparent',
    color: activeTab === tab ? 'var(--color-primary-700)' : 'var(--color-neutral-600)',
    border: 'none',
    borderRadius: 'var(--radius-md)',
    cursor: 'pointer',
    fontSize: '0.875rem',
    fontWeight: activeTab === tab ? 600 : 400
  });

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-4)' }}>
        <div style={{ display: 'flex', gap: 'var(--spacing-3)', alignItems: 'center' }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Run Monitor</h2>
          {selectedJobs.size > 1 && (
            <button
              onClick={handleCompare}
              style={{
                padding: 'var(--spacing-1) var(--spacing-3)',
                backgroundColor: 'var(--action-bg)',
                color: 'var(--action-fg)',
                border: 'none',
                borderRadius: 'var(--radius-button)',
                cursor: 'pointer',
                fontSize: '0.875rem'
              }}
            >
              Compare ({selectedJobs.size})
            </button>
          )}
          {selectedJobs.size > 0 && (
            <button
              onClick={deleteSelected}
              style={{
                padding: 'var(--spacing-1) var(--spacing-3)',
                backgroundColor: 'transparent',
                color: 'var(--color-error-text)',
                border: '1px solid var(--color-error-text)',
                borderRadius: 'var(--radius-md)',
                cursor: 'pointer',
                fontSize: '0.875rem'
              }}
            >
              Delete ({selectedJobs.size})
            </button>
          )}
        </div>
        <button 
          onClick={fetchJobs}
          style={{
            padding: 'var(--spacing-1) var(--spacing-3)',
            backgroundColor: 'var(--surface-muted)',
            border: '1px solid var(--border-default)',
            borderRadius: 'var(--radius-md)',
            cursor: 'pointer',
            fontSize: '0.875rem'
          }}
        >
          Refresh
        </button>
      </div>

      {loading ? (
        <div style={{ color: 'var(--color-neutral-500)', fontSize: '0.875rem' }}>Loading jobs...</div>
      ) : jobs.length === 0 ? (
        <div style={{ color: 'var(--color-neutral-500)', fontSize: '0.875rem' }}>No calibration jobs found.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
          {jobs.map(job => (
            <div key={job.id} style={{ 
              border: '1px solid var(--border-default)', 
              borderRadius: 'var(--radius-md)', 
              display: 'flex',
              flexDirection: 'column',
              backgroundColor: expandedJobId === job.id ? 'var(--surface-muted)' : 'var(--surface-default)',
              transition: 'background-color 0.2s'
            }}>
              {/* Header / Summary row */}
              <div 
                style={{ display: 'flex', gap: 'var(--spacing-3)', padding: 'var(--spacing-3)', cursor: 'pointer' }}
                onClick={() => setExpandedJobId(expandedJobId === job.id ? null : job.id)}
              >
                <div style={{ paddingTop: '2px' }} onClick={e => e.stopPropagation()}>
                  <input 
                    type="checkbox" 
                    checked={selectedJobs.has(job.id)}
                    onChange={() => toggleSelection(job.id)}
                    style={{ cursor: 'pointer' }}
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--spacing-2)', alignItems: 'center' }}>
                    <span style={{ fontWeight: 500, fontFamily: 'var(--font-mono)', fontSize: '0.875rem' }}>{job.id}</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
                      {job.season && (
                        <span
                          title="Season this run was fitted against"
                          style={{
                            fontSize: '0.75rem',
                            padding: '2px 8px',
                            borderRadius: '999px',
                            backgroundColor: 'var(--surface-muted)',
                            border: '1px solid var(--border-default)',
                            color: 'var(--color-neutral-700)',
                            fontFamily: 'var(--font-mono)',
                          }}
                        >
                          {job.season}
                        </span>
                      )}
                      <span style={{ 
                        fontSize: '0.75rem', 
                        padding: '2px 8px', 
                        borderRadius: '999px',
                        backgroundColor: job.status === 'completed' ? 'var(--color-success-bg)' : job.status === 'failed' ? 'var(--color-error-bg)' : 'var(--color-info-bg)',
                        color: job.status === 'completed' ? 'var(--color-success-text)' : job.status === 'failed' ? 'var(--color-error-text)' : 'var(--color-info-text)',
                        textTransform: 'uppercase',
                        fontWeight: 600
                      }}>
                        {job.status}
                      </span>
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteJob(job.id); }}
                        title="Delete this calibration run"
                        aria-label="Delete this calibration run"
                        style={{
                          padding: '2px 8px',
                          fontSize: '0.75rem',
                          backgroundColor: 'transparent',
                          color: 'var(--color-neutral-500)',
                          border: '1px solid var(--border-default)',
                          borderRadius: 'var(--radius-sm)',
                          cursor: 'pointer',
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                  <div style={{ width: '100%', backgroundColor: 'var(--color-neutral-200)', borderRadius: '999px', height: '8px', overflow: 'hidden' }}>
                    <div style={{ 
                      width: `${job.progress}%`, 
                      backgroundColor: job.status === 'failed' ? 'var(--color-error-text)' : 'var(--color-primary-500)', 
                      height: '100%',
                      transition: 'width 0.3s ease'
                    }} />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 'var(--spacing-1)', fontSize: '0.75rem', color: 'var(--color-neutral-500)' }}>
                    <span>Progress: {job.progress}%</span>
                    <span>{new Date(job.created_at).toLocaleString()}</span>
                  </div>

                  {/* The four fitting phases, streamed. A calibration run is
                      minutes of silence otherwise -- the bar alone cannot say
                      which fitter is working. */}
                  {(job.status === 'running' || job.status === 'queued') && (
                    <div style={{ marginTop: 'var(--spacing-3)' }} onClick={(e) => e.stopPropagation()}>
                      <ExecutionLog jobId={job.id} resource="calibration" onFinished={fetchJobs} />
                    </div>
                  )}
                </div>
              </div>

              {/* Accordion Content */}
              {expandedJobId === job.id && (
                <div style={{ 
                  borderTop: '1px solid var(--border-default)', 
                  padding: 'var(--spacing-3)',
                  backgroundColor: 'var(--surface-default)',
                  borderBottomLeftRadius: 'var(--radius-md)',
                  borderBottomRightRadius: 'var(--radius-md)'
                }} onClick={e => e.stopPropagation()}>
                  <div style={{ display: 'flex', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-3)', borderBottom: '1px solid var(--border-default)', paddingBottom: 'var(--spacing-2)' }}>
                    <button onClick={() => setActiveTab('results')} style={getTabStyle('results')}>Results</button>
                    <button onClick={() => setActiveTab('logs')} style={getTabStyle('logs')}>Logs</button>
                  </div>
                  <div style={{ padding: 'var(--spacing-2) 0' }}>
                    {activeTab === 'results' && <ResultsInspector initialJobId={job.id} />}
                    {activeTab === 'logs' &&
                      (job.status === 'running' || job.status === 'queued' ? (
                        <ExecutionLog jobId={job.id} resource="calibration" onFinished={fetchJobs} />
                      ) : (
                        <FinishedLog jobId={job.id} resource="calibration" />
                      ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
