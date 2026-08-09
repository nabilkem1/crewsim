import React, { useEffect, useState } from 'react';
import { fetchMetrics } from './api';

export function Metrics() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    fetchMetrics().then(setData).catch(console.error);
  }, []);

  if (!data) return <div>Loading...</div>;

  return (
    <div className="card">
      <h2 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.25rem', fontWeight: 600 }}>Metric Comparisons</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border-default)', textAlign: 'left' }}>
            <th style={{ padding: 'var(--spacing-2)' }}>Metric</th>
            {data.runs.map((run: string) => (
              <th key={run} style={{ padding: 'var(--spacing-2)' }}>{run}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.metrics.map((metric: string) => (
            <tr key={metric} style={{ borderBottom: '1px solid var(--border-default)' }}>
              <td style={{ padding: 'var(--spacing-2)', textTransform: 'capitalize' }}>{metric.replace('_', ' ')}</td>
              {data.runs.map((run: string) => (
                <td key={run} style={{ padding: 'var(--spacing-2)' }}>{data.data[metric][run]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
