import React, { useState, useEffect } from 'react';

export const LogExplorer: React.FC<{ initialJobId?: string }> = ({ initialJobId = '' }) => {
  const [jobId, setJobId] = useState(initialJobId);
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchLogsForJob = async (id: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/calibration/${id}/logs`);
      if (res.ok) {
        const data = await res.json();
        setLogs(data.logs || []);
      }
    } catch (err) {
      console.error('Failed to fetch logs', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialJobId) {
      setJobId(initialJobId);
      fetchLogsForJob(initialJobId);
    }
  }, [initialJobId]);

  return (
    <div>
      <h2 style={{ marginBottom: 'var(--spacing-2)', fontSize: '1.25rem', fontWeight: 600 }}>Log Explorer</h2>
      <div style={{ marginBottom: 'var(--spacing-4)', color: 'var(--color-neutral-500)', fontSize: '0.875rem', fontFamily: 'var(--font-mono)' }}>
        Job ID: {jobId || 'None'}
      </div>

      {loading && (
        <div style={{ color: 'var(--color-neutral-500)', fontSize: '0.875rem', marginBottom: 'var(--spacing-4)' }}>
          Loading logs...
        </div>
      )}

      {logs.length > 0 && (
        <div style={{
          // Chrome tokens, not the neutral ramp: this is a fixed-dark terminal
          // panel (same convention as EventTape/LogView), so it must not
          // invert when the neutral ramp does for dark mode -- --color-neutral-900
          // becomes near-white there, which would turn this into a
          // light-background panel with light-on-light text.
          backgroundColor: 'var(--chrome-bg)',
          color: 'var(--chrome-text-strong)',
          padding: 'var(--spacing-4)', 
          borderRadius: 'var(--radius-md)',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.875rem',
          maxHeight: '300px',
          overflowY: 'auto',
          whiteSpace: 'pre-wrap'
        }}>
          {logs.map((log, i) => (
            <div key={i} style={{ marginBottom: '4px' }}>
              <span style={{ 
                color: log.includes('[ERROR]') ? '#ef4444' : 
                       log.includes('[DEBUG]') ? '#8b5cf6' : 
                       log.includes('[INFO]') ? '#3b82f6' : 'inherit'
              }}>
                {log}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
