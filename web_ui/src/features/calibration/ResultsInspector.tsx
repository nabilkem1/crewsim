import React, { useState, useEffect } from 'react';

export const ResultsInspector: React.FC<{ initialJobId?: string }> = ({ initialJobId = '' }) => {
  const [jobId, setJobId] = useState(initialJobId);
  const [results, setResults] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchResultsForJob = async (id: string) => {
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const res = await fetch(`/api/calibration/${id}/results`);
      if (res.ok) {
        const data = await res.json();
        setResults(data);
      } else {
        setError('Results not found or job incomplete.');
      }
    } catch (err) {
      setError('Failed to fetch results.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialJobId) {
      setJobId(initialJobId);
      fetchResultsForJob(initialJobId);
    }
  }, [initialJobId]);

  return (
    <div>
      <h2 style={{ marginBottom: 'var(--spacing-2)', fontSize: '1.25rem', fontWeight: 600 }}>Results Inspector</h2>
      <div style={{ marginBottom: 'var(--spacing-4)', color: 'var(--color-neutral-500)', fontSize: '0.875rem', fontFamily: 'var(--font-mono)' }}>
        Job ID: {jobId || 'None'}
      </div>
      
      {loading && (
        <div style={{ color: 'var(--color-neutral-500)', fontSize: '0.875rem', marginBottom: 'var(--spacing-4)' }}>
          Loading results...
        </div>
      )}

      {error && (
        <div style={{ color: 'var(--color-error-text)', fontSize: '0.875rem', marginBottom: 'var(--spacing-4)' }}>
          {error}
        </div>
      )}

      {results && (
        <div style={{ backgroundColor: 'var(--surface-muted)', padding: 'var(--spacing-4)', borderRadius: 'var(--radius-md)' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 'var(--spacing-3)' }}>Calibration Output</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-4)', marginBottom: 'var(--spacing-4)' }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)', textTransform: 'uppercase' }}>Status</div>
              <div style={{ fontWeight: 500 }}>{results.status}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)', textTransform: 'uppercase' }}>Log Likelihood</div>
              <div style={{ fontWeight: 500 }}>{results.final_log_likelihood}</div>
            </div>
          </div>
          
          {results.detailed_results && (
            <div style={{ maxHeight: '400px', overflowY: 'auto', borderTop: '1px solid var(--border-default)', paddingTop: 'var(--spacing-4)', display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
              
              {/* Transition Matrix */}
              <div>
                <div style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: 'var(--spacing-2)' }}>Transition Matrix</div>
                <div style={{ backgroundColor: 'var(--surface-default)', padding: 'var(--spacing-3)', borderRadius: 'var(--radius-sm)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                  {results.detailed_results.transition_matrix.map((row: number[], i: number) => (
                    <div key={i} style={{ display: 'flex', gap: 'var(--spacing-3)' }}>
                      {row.map((val: number, j: number) => (
                        <span key={j} style={{ width: '40px', textAlign: 'right' }}>{val.toFixed(2)}</span>
                      ))}
                    </div>
                  ))}
                </div>
              </div>

              {/* Intensity Multipliers */}
              <div>
                <div style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: 'var(--spacing-2)' }}>Intensity Multipliers</div>
                <div style={{ backgroundColor: 'var(--surface-default)', padding: 'var(--spacing-3)', borderRadius: 'var(--radius-sm)', fontSize: '0.875rem' }}>
                  <ul style={{ margin: 0, paddingLeft: 'var(--spacing-4)' }}>
                    {Object.entries(results.detailed_results.intensity_multipliers).map(([key, val]) => (
                      <li key={key}><strong>{key}:</strong> {val as number}</li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* NHPP Equation */}
              <div>
                <div style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: 'var(--spacing-2)' }}>NHPP Equation</div>
                <div style={{ backgroundColor: 'var(--surface-default)', padding: 'var(--spacing-3)', borderRadius: 'var(--radius-sm)', fontFamily: 'var(--font-mono)', fontSize: '0.875rem', marginBottom: 'var(--spacing-2)' }}>
                  {results.detailed_results.nhpp_equation}
                </div>
                <div style={{ backgroundColor: 'var(--surface-default)', padding: 'var(--spacing-3)', borderRadius: 'var(--radius-sm)', fontSize: '0.875rem' }}>
                  <ul style={{ margin: 0, paddingLeft: 'var(--spacing-4)' }}>
                    {Object.entries(results.detailed_results.nhpp_variables).map(([key, val]) => (
                      <li key={key}><strong>{key}</strong> = {val as number}</li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Mixture Dist Params */}
              <div>
                <div style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: 'var(--spacing-2)' }}>Mixture Distribution Parameters</div>
                <div style={{ backgroundColor: 'var(--surface-default)', padding: 'var(--spacing-3)', borderRadius: 'var(--radius-sm)', fontSize: '0.875rem' }}>
                  <div style={{ display: 'flex', gap: 'var(--spacing-4)' }}>
                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)', textTransform: 'uppercase' }}>Components</div>
                      <div>{results.detailed_results.mixture_dist_params.components.join(', ')}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)', textTransform: 'uppercase' }}>Weights</div>
                      <div>{results.detailed_results.mixture_dist_params.weights.join(', ')}</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Log Normal Dist */}
              <div>
                <div style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: 'var(--spacing-2)' }}>Lognormal Distribution</div>
                <div style={{ backgroundColor: 'var(--surface-default)', padding: 'var(--spacing-3)', borderRadius: 'var(--radius-sm)', fontSize: '0.875rem' }}>
                  <span style={{ marginRight: 'var(--spacing-4)' }}><strong>μ:</strong> {results.detailed_results.log_normal_dist.mu}</span>
                  <span><strong>σ:</strong> {results.detailed_results.log_normal_dist.sigma}</span>
                </div>
              </div>

            </div>
          )}
        </div>
      )}
    </div>
  );
};
