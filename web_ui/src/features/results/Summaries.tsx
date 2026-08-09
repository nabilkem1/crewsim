import React, { useEffect, useState } from 'react';
import { fetchSummaries } from './api';

export function Summaries() {
  const [data, setData] = useState<any[]>([]);

  useEffect(() => {
    fetchSummaries().then(setData).catch(console.error);
  }, []);

  return (
    <div className="card">
      <h2 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.25rem', fontWeight: 600 }}>Final Run Summaries</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
        {data.map(run => (
          <div key={run.id} style={{ border: '1px solid var(--border-default)', padding: 'var(--spacing-4)', borderRadius: 'var(--radius-md)' }}>
            <h3 style={{ marginBottom: 'var(--spacing-2)', fontWeight: 600 }}>{run.name} ({run.id})</h3>
            <div style={{ display: 'flex', gap: 'var(--spacing-4)', color: 'var(--color-neutral-600)', fontSize: '0.875rem' }}>
              <span>Status: {run.status}</span>
              <span>Duration: {run.duration}</span>
              <span>Events: {run.total_events}</span>
              <span>Success Rate: {(run.success_rate * 100).toFixed(0)}%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
