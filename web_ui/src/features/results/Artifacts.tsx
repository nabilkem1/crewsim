import React, { useEffect, useState } from 'react';
import { fetchArtifacts } from './api';

export function Artifacts() {
  const [data, setData] = useState<any[]>([]);

  useEffect(() => {
    fetchArtifacts().then(setData).catch(console.error);
  }, []);

  return (
    <div className="card">
      <h2 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.25rem', fontWeight: 600 }}>Simulation Artifacts</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border-default)', textAlign: 'left' }}>
            <th style={{ padding: 'var(--spacing-2)' }}>Filename</th>
            <th style={{ padding: 'var(--spacing-2)' }}>Run ID</th>
            <th style={{ padding: 'var(--spacing-2)' }}>Type</th>
            <th style={{ padding: 'var(--spacing-2)' }}>Size</th>
            <th style={{ padding: 'var(--spacing-2)' }}>Action</th>
          </tr>
        </thead>
        <tbody>
          {data.map(art => (
            <tr key={art.id} style={{ borderBottom: '1px solid var(--border-default)' }}>
              <td style={{ padding: 'var(--spacing-2)' }}>{art.filename}</td>
              <td style={{ padding: 'var(--spacing-2)' }}>{art.run_id}</td>
              <td style={{ padding: 'var(--spacing-2)' }}>{art.type}</td>
              <td style={{ padding: 'var(--spacing-2)' }}>{art.size_mb} MB</td>
              <td style={{ padding: 'var(--spacing-2)' }}>
                <a href={art.url} style={{ color: 'var(--color-primary-600)', textDecoration: 'none', fontWeight: 500 }}>Download</a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
