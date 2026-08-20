import React, { useState, useEffect } from 'react';

// Types
interface Job {
  id: string;
  type: string;
  status: string;
  progress: number;
  created_at: string;
  error_message?: string;
}

interface ProfilingData {
  bottlenecks: Array<{
    component: string;
    time_spent_percent: number;
    status: string;
  }>;
}

interface Prediction {
  estimated_time_seconds: number;
  estimated_cost_dollars: number;
}

export const ProcessingDashboard: React.FC = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [logs, setLogs] = useState<Record<string, string[]>>({});
  const [outputDest, setOutputDest] = useState('/data/outputs/run1');
  const [workers, setWorkers] = useState(4);
  const [memory, setMemory] = useState(16);
  const [profiling, setProfiling] = useState<ProfilingData | null>(null);
  const [prediction, setPrediction] = useState<Prediction | null>(null);

  const fetchJobs = async () => {
    try {
      const res = await fetch('/api/processing/status');
      if (res.ok) setJobs(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 2000);
    return () => clearInterval(interval);
  }, []);

  const launchRun = async (isBatch: boolean) => {
    const endpoint = isBatch ? '/api/processing/batch' : '/api/processing/run';
    const payload = isBatch 
      ? { config_id: 'cfg-1', scenarios: ['scen-1', 'scen-2'] }
      : { config_id: 'cfg-1', scenario: 'scen-1' };
      
    try {
      await fetch(`${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      fetchJobs();
    } catch (e) {
      console.error(e);
    }
  };

  const fetchLogs = async (jobId: string) => {
    try {
      const res = await fetch(`/api/processing/${jobId}/logs`);
      if (res.ok) {
        const data = await res.json();
        setLogs(prev => ({ ...prev, [jobId]: data.logs }));
      }
    } catch (e) {
      console.error(e);
    }
  };

  const saveConfig = async () => {
    try {
      await fetch('/api/processing/config/output', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ destination_path: outputDest })
      });
      await fetch('/api/processing/config/hardware', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ worker_count: workers, memory_gb: memory })
      });
      alert('Configuration saved!');
    } catch (e) {
      console.error(e);
    }
  };

  const loadProfiling = async () => {
    try {
      const res = await fetch('/api/processing/profiling');
      if (res.ok) setProfiling(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  const loadPrediction = async () => {
    try {
      const res = await fetch('/api/processing/prediction');
      if (res.ok) setPrediction(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  const renderStatus = (status: string) => {
    const colorMap: Record<string, string> = {
      completed: 'var(--color-success-text)',
      failed: 'var(--color-error-text)',
      running: 'var(--color-info-text)',
      queued: 'var(--color-warning-text)'
    };
    return <span style={{ color: colorMap[status] || 'inherit', fontWeight: 600 }}>{status.toUpperCase()}</span>;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-6)' }}>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>Processing Pipeline</h1>
      
      <div style={{ display: 'flex', gap: 'var(--spacing-6)' }}>
        <div className="card" style={{ flex: 1 }}>
          <h2 style={{ fontSize: '1.25rem', marginBottom: 'var(--spacing-4)' }}>Launch Controls</h2>
          <div style={{ display: 'flex', gap: 'var(--spacing-4)', marginBottom: 'var(--spacing-4)' }}>
            <button 
              onClick={() => launchRun(false)}
              style={{ padding: 'var(--spacing-2) var(--spacing-4)', backgroundColor: 'var(--color-primary-600)', color: 'white', border: 'none', borderRadius: 'var(--radius-md)', cursor: 'pointer' }}>
              Launch Single Run
            </button>
            <button 
              onClick={() => launchRun(true)}
              style={{ padding: 'var(--spacing-2) var(--spacing-4)', backgroundColor: 'var(--color-neutral-800)', color: 'white', border: 'none', borderRadius: 'var(--radius-md)', cursor: 'pointer' }}>
              Launch Batch Run
            </button>
            <button 
              onClick={loadPrediction}
              style={{ padding: 'var(--spacing-2) var(--spacing-4)', backgroundColor: 'var(--surface-default)', color: 'var(--color-neutral-900)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', cursor: 'pointer' }}>
              Get Prediction
            </button>
          </div>
          
          {prediction && (
            <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--color-info-bg)', borderRadius: 'var(--radius-md)' }}>
              <strong>Prediction:</strong> Estimated Time: {prediction.estimated_time_seconds}s | Estimated Cost: ${prediction.estimated_cost_dollars}
            </div>
          )}
        </div>

        <div className="card" style={{ flex: 1 }}>
          <h2 style={{ fontSize: '1.25rem', marginBottom: 'var(--spacing-4)' }}>Configuration</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
            <div>
              <label style={{ display: 'block', marginBottom: 'var(--spacing-1)', fontSize: '0.875rem' }}>Output Destination</label>
              <input 
                type="text" 
                value={outputDest} 
                onChange={e => setOutputDest(e.target.value)}
                style={{ width: '100%', padding: 'var(--spacing-2)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)' }}
              />
            </div>
            <div style={{ display: 'flex', gap: 'var(--spacing-4)' }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', marginBottom: 'var(--spacing-1)', fontSize: '0.875rem' }}>Workers</label>
                <input 
                  type="number" 
                  value={workers} 
                  onChange={e => setWorkers(parseInt(e.target.value))}
                  style={{ width: '100%', padding: 'var(--spacing-2)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)' }}
                />
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', marginBottom: 'var(--spacing-1)', fontSize: '0.875rem' }}>Memory (GB)</label>
                <input 
                  type="number" 
                  value={memory} 
                  onChange={e => setMemory(parseInt(e.target.value))}
                  style={{ width: '100%', padding: 'var(--spacing-2)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)' }}
                />
              </div>
            </div>
            <button 
              onClick={saveConfig}
              style={{ padding: 'var(--spacing-2) var(--spacing-4)', backgroundColor: 'var(--surface-default)', color: 'var(--color-neutral-900)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', cursor: 'pointer', alignSelf: 'flex-start' }}>
              Save Config
            </button>
          </div>
        </div>
      </div>

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-4)' }}>
          <h2 style={{ fontSize: '1.25rem' }}>Job Monitor</h2>
          <button 
            onClick={loadProfiling}
            style={{ padding: 'var(--spacing-2) var(--spacing-4)', backgroundColor: 'var(--surface-default)', color: 'var(--color-neutral-900)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', cursor: 'pointer' }}>
            Run Profiler
          </button>
        </div>

        {profiling && (
          <div style={{ marginBottom: 'var(--spacing-6)', padding: 'var(--spacing-4)', backgroundColor: 'var(--surface-muted)', borderRadius: 'var(--radius-md)' }}>
            <h3 style={{ fontSize: '1rem', marginBottom: 'var(--spacing-2)' }}>Bottleneck Profiling</h3>
            <div style={{ display: 'flex', gap: 'var(--spacing-4)' }}>
              {profiling.bottlenecks.map((b, i) => (
                <div key={i} style={{ flex: 1, padding: 'var(--spacing-3)', backgroundColor: 'var(--surface-default)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)' }}>
                  <div style={{ fontWeight: 600 }}>{b.component}</div>
                  <div style={{ fontSize: '1.25rem', color: b.status === 'critical' ? 'var(--color-error-text)' : 'inherit' }}>
                    {b.time_spent_percent}%
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
          {jobs.length === 0 && <div style={{ color: 'var(--color-neutral-500)' }}>No active jobs.</div>}
          {jobs.map(job => (
            <div key={job.id} style={{ border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', padding: 'var(--spacing-4)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--spacing-2)' }}>
                <strong>{job.type}</strong>
                {renderStatus(job.status)}
              </div>
              <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-500)', marginBottom: 'var(--spacing-2)' }}>ID: {job.id}</div>
              
              <div style={{ width: '100%', height: '8px', backgroundColor: 'var(--color-neutral-200)', borderRadius: '4px', marginBottom: 'var(--spacing-2)', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${job.progress}%`, backgroundColor: job.status === 'failed' ? 'var(--color-error-text)' : 'var(--color-primary-500)', transition: 'width 0.3s ease' }}></div>
              </div>
              
              {job.error_message && (
                <div style={{ padding: 'var(--spacing-2)', backgroundColor: 'var(--color-error-bg)', color: 'var(--color-error-text)', borderRadius: 'var(--radius-sm)', fontSize: '0.875rem', marginBottom: 'var(--spacing-2)' }}>
                  {job.error_message}
                </div>
              )}

              <button 
                onClick={() => fetchLogs(job.id)}
                style={{ fontSize: '0.875rem', padding: 'var(--spacing-1) var(--spacing-2)', backgroundColor: 'transparent', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', cursor: 'pointer' }}>
                View Logs
              </button>

              {logs[job.id] && (
                <div style={{ marginTop: 'var(--spacing-2)', padding: 'var(--spacing-3)', backgroundColor: 'var(--color-neutral-900)', color: 'var(--color-success-bg)', fontFamily: 'var(--font-mono)', fontSize: '0.875rem', borderRadius: 'var(--radius-md)', maxHeight: '150px', overflowY: 'auto' }}>
                  {logs[job.id].map((log, i) => (
                    <div key={i}>{log}</div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
