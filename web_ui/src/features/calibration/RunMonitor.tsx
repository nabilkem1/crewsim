import React, { useState, useEffect } from 'react';
import { ResultsInspector } from './ResultsInspector';
import { DiagnosticsView } from './DiagnosticsView';
import { LogExplorer } from './LogExplorer';

interface Job {
  id: string;
  type: string;
  status: string;
  progress: number;
  created_at: string;
}

export const RunMonitor: React.FC = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedJobs, setSelectedJobs] = useState<Set<string>>(new Set());
  
  // Accordion state
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'results' | 'diagnostics' | 'logs'>('results');

  const fetchJobs = async () => {
    try {
      const res = await fetch('/api/jobs');
      if (res.ok) {
        const data = await res.json();
        setJobs(data.filter((j: Job) => j.type === 'calibration'));
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
                backgroundColor: 'var(--color-primary-600)',
                color: 'white',
                border: 'none',
                borderRadius: 'var(--radius-md)',
                cursor: 'pointer',
                fontSize: '0.875rem'
              }}
            >
              Compare ({selectedJobs.size})
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
                    <button onClick={() => setActiveTab('diagnostics')} style={getTabStyle('diagnostics')}>Diagnostics</button>
                    <button onClick={() => setActiveTab('logs')} style={getTabStyle('logs')}>Logs</button>
                  </div>
                  <div style={{ padding: 'var(--spacing-2) 0' }}>
                    {activeTab === 'results' && <ResultsInspector initialJobId={job.id} />}
                    {activeTab === 'diagnostics' && <DiagnosticsView initialJobId={job.id} />}
                    {activeTab === 'logs' && <LogExplorer initialJobId={job.id} />}
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
