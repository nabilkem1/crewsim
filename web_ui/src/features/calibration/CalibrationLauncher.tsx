import React, { useState, useEffect } from 'react';

export const CalibrationLauncher: React.FC = () => {
  const [name, setName] = useState('');
  const [launching, setLaunching] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);

  useEffect(() => {
    const now = new Date();
    const timestamp = now.toISOString().replace(/T/, ' ').replace(/\..+/, '');
    setName(`Phase 0: Statistical Fit [${timestamp}]`);
  }, []);

  const availableModels = [
    { id: 'transition_matrix', label: 'Transition Matrix (Markov States)' },
    { id: 'intensity_multipliers', label: 'Intensity Multipliers' },
    { id: 'nhpp_covariates', label: 'NHPP Covariates (MLE Fit)' },
    { id: 'mixture_dist', label: 'Mixture Dist Params' },
    { id: 'lognormal_dist', label: 'Lognormal Dist Params' }
  ];

  const handleLaunch = async (e: React.FormEvent) => {
    e.preventDefault();
    setLaunching(true);
    try {
      const res = await fetch('http://localhost:8000/api/calibration/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          name, 
          dataset: 'all_corpus_files', 
          models_to_fit: availableModels.map(m => m.id) 
        })
      });
      if (res.ok) {
        const data = await res.json();
        setJobId(data.id);
      }
    } catch (err) {
      console.error('Failed to launch calibration', err);
    } finally {
      setLaunching(false);
    }
  };

  return (
    <div className="card">
      <h2 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.25rem', fontWeight: 600 }}>Launch Statistical Calibration Layer</h2>
      <form onSubmit={handleLaunch} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-1)' }}>
          <label style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--color-neutral-700)' }}>Calibration Run Identifier</label>
          <input 
            type="text" 
            value={name}
            onChange={e => setName(e.target.value)}
            style={{ 
              padding: 'var(--spacing-2)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)', fontFamily: 'var(--font-mono)', width: '100%', maxWidth: '600px'
            }} 
            required 
          />
        </div>

        <div>
          <label style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--color-neutral-700)', display: 'block', marginBottom: 'var(--spacing-2)' }}>
            Statistical Models to Calibrate (Full Pipeline Enforced)
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)', backgroundColor: 'var(--surface-muted)', padding: 'var(--spacing-4)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-default)' }}>
            {availableModels.map(m => (
              <label key={m.id} style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', fontSize: '0.875rem', color: 'var(--color-neutral-600)', cursor: 'not-allowed' }}>
                <input 
                  type="checkbox" 
                  checked={true}
                  disabled={true}
                  style={{ width: '1rem', height: '1rem', accentColor: 'var(--color-primary-600)', opacity: 0.6 }}
                />
                {m.label}
              </label>
            ))}
          </div>
        </div>

        <button 
          type="submit" 
          disabled={launching}
          style={{
            alignSelf: 'flex-start',
            padding: 'var(--spacing-2) var(--spacing-4)',
            backgroundColor: 'var(--color-primary-600)',
            color: 'white',
            border: 'none',
            borderRadius: 'var(--radius-md)',
            fontWeight: 500,
            cursor: launching ? 'not-allowed' : 'pointer',
            opacity: launching ? 0.7 : 1
          }}
        >
          {launching ? 'Reading Historical Data...' : 'Run Statistical Fitting'}
        </button>
      </form>

      {jobId && (
        <div style={{ 
          marginTop: 'var(--spacing-4)', padding: 'var(--spacing-3)', backgroundColor: 'var(--color-success-bg)', color: 'var(--color-success-text)', borderRadius: 'var(--radius-md)', fontSize: '0.875rem'
        }}>
          Calibration pipeline launched! Reading and fitting data. Job ID: {jobId}
        </div>
      )}
    </div>
  );
};
