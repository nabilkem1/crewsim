import React, { useState, useEffect } from 'react';

export const ComparisonView: React.FC<{ initialJobIds?: string[] }> = ({ initialJobIds = [] }) => {
  const [jobIds, setJobIds] = useState(initialJobIds.join(','));
  const [comparisons, setComparisons] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchComparisonsForJobs = async (ids: string) => {
    if (!ids.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/calibration/compare?job_ids=${encodeURIComponent(ids)}`);
      if (res.ok) {
        const data = await res.json();
        setComparisons(data.comparison || []);
      }
    } catch (err) {
      console.error('Failed to fetch comparisons', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialJobIds.length > 0) {
      const idsString = initialJobIds.join(',');
      setJobIds(idsString);
      fetchComparisonsForJobs(idsString);
    }
  }, [initialJobIds]);

  return (
    <div className="card">
      <h2 style={{ marginBottom: 'var(--spacing-2)', fontSize: '1.25rem', fontWeight: 600 }}>Compare Calibrations</h2>
      <div style={{ marginBottom: 'var(--spacing-4)', color: 'var(--color-neutral-500)', fontSize: '0.875rem', fontFamily: 'var(--font-mono)' }}>
        Job IDs: {jobIds || 'None'}
      </div>

      {loading && (
        <div style={{ color: 'var(--color-neutral-500)', fontSize: '0.875rem', marginBottom: 'var(--spacing-4)' }}>
          Comparing calibrations...
        </div>
      )}

      {comparisons.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ backgroundColor: 'var(--surface-muted)', borderBottom: '2px solid var(--border-default)' }}>
                <th style={{ padding: 'var(--spacing-3)', textAlign: 'left', fontWeight: 600 }}>Job ID</th>
                <th style={{ padding: 'var(--spacing-3)', textAlign: 'left', fontWeight: 600 }}>Transition Matrix Norm</th>
                <th style={{ padding: 'var(--spacing-3)', textAlign: 'left', fontWeight: 600 }}>NHPP Alpha</th>
                <th style={{ padding: 'var(--spacing-3)', textAlign: 'left', fontWeight: 600 }}>Log Likelihood</th>
              </tr>
            </thead>
            <tbody>
              {comparisons.map((c: any) => (
                <tr key={c.job_id} style={{ borderBottom: '1px solid var(--border-default)' }}>
                  <td style={{ padding: 'var(--spacing-3)', fontFamily: 'var(--font-mono)' }}>{c.job_id}</td>
                  <td style={{ padding: 'var(--spacing-3)' }}>{c.transition_matrix_norm}</td>
                  <td style={{ padding: 'var(--spacing-3)' }}>{c.nhpp_alpha}</td>
                  <td style={{ padding: 'var(--spacing-3)', fontWeight: 500, color: 'var(--color-primary-700)' }}>{c.log_likelihood}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
