import React, { useState, useEffect } from 'react';

export const DiagnosticsView: React.FC<{ initialJobId?: string }> = ({ initialJobId = '' }) => {
  const [jobId, setJobId] = useState(initialJobId);
  const [diagnostics, setDiagnostics] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fetchDiagnosticsForJob = async (id: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/calibration/${id}/diagnostics`);
      if (res.ok) {
        const data = await res.json();
        setDiagnostics(data);
      }
    } catch (err) {
      console.error('Failed to fetch diagnostics', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialJobId) {
      setJobId(initialJobId);
      fetchDiagnosticsForJob(initialJobId);
    }
  }, [initialJobId]);

  const [showExplanation, setShowExplanation] = useState(false);

  return (
    <div>
      <h2 style={{ marginBottom: 'var(--spacing-2)', fontSize: '1.25rem', fontWeight: 600 }}>Diagnostics View</h2>
      <div style={{ marginBottom: 'var(--spacing-4)', color: 'var(--color-neutral-500)', fontSize: '0.875rem', fontFamily: 'var(--font-mono)' }}>
        Job ID: {jobId || 'None'}
      </div>
      
      {loading && (
        <div style={{ color: 'var(--color-neutral-500)', fontSize: '0.875rem', marginBottom: 'var(--spacing-4)' }}>
          Loading diagnostics...
        </div>
      )}

      {diagnostics && diagnostics.chart_data && (
        <div style={{ backgroundColor: 'var(--surface-default)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', padding: 'var(--spacing-4)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-3)' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>Log-Likelihood Convergence</h3>
            <button 
              onClick={() => setShowExplanation(!showExplanation)}
              style={{
                background: 'var(--color-neutral-200)', border: 'none', borderRadius: '50%',
                width: '20px', height: '20px', fontSize: '0.75rem', fontWeight: 'bold',
                cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'var(--color-neutral-700)'
              }}
              title="What is this?"
            >
              ?
            </button>
          </div>
          
          {showExplanation && (
            <div style={{ backgroundColor: 'var(--surface-muted)', padding: 'var(--spacing-3)', borderRadius: 'var(--radius-md)', fontSize: '0.875rem', marginBottom: 'var(--spacing-4)', lineHeight: '1.5' }}>
              <strong>Log-Likelihood</strong> measures how well the simulated statistical models (Transition Matrices, NHPP arrival rates, and Mixture components) match the historical dataset. 
              Because probabilities are so small, taking the natural logarithm allows us to add them up without precision errors. The number is always negative, but <strong>closer to zero is better</strong>.<br/><br/>
              <strong>Convergence</strong> means the optimization algorithm has found the best possible parameters. A healthy calibration curve starts low (negative) and rapidly climbs before plateauing near the top.
            </div>
          )}
          
          <div style={{ display: 'flex', alignItems: 'flex-end', height: '200px', gap: '4px', marginTop: 'var(--spacing-4)' }}>
            {diagnostics.chart_data.map((point: any) => {
              // Normalize LL (e.g., from -2500 to 0) to a percentage (0% to 100%)
              const minLL = -3000;
              const maxLL = 0;
              const heightPercentage = Math.max(10, Math.min(100, ((point.log_likelihood - minLL) / (maxLL - minLL)) * 100));
              return (
                <div key={point.iteration} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', height: '100%' }}>
                  <div 
                    title={`Iteration ${point.iteration}: LL ${point.log_likelihood}`}
                    style={{ 
                      width: '100%', 
                      height: `${heightPercentage}%`, 
                      backgroundColor: 'var(--color-primary-500)',
                      borderRadius: 'var(--radius-sm) var(--radius-sm) 0 0',
                      transition: 'height 0.3s'
                    }} 
                  />
                </div>
              );
            })}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 'var(--spacing-2)', fontSize: '0.75rem', color: 'var(--color-neutral-500)' }}>
            <span>Iteration 1</span>
            <span>Iteration {diagnostics.chart_data.length}</span>
          </div>
        </div>
      )}
    </div>
  );
};
