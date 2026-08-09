import React, { useEffect, useState } from 'react';

export const ConfigValidation: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('http://localhost:8000/api/config/validate')
      .then(res => {
        if (!res.ok) throw new Error('Validation failed');
        return res.json();
      })
      .then(d => {
        setData(d);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Loading validation data...</div>;
  if (error) return <div style={{ color: 'var(--color-error-text)' }}>{error}</div>;

  return (
    <div className="card config-validation" style={{ height: '100%', overflowY: 'auto' }}>
      <h2 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.25rem', fontWeight: 600 }}>Pre-flight Validation</h2>
      <div style={{ marginBottom: 'var(--spacing-4)', padding: 'var(--spacing-3)', borderRadius: 'var(--radius-md)', backgroundColor: data.is_valid ? 'var(--color-success-50)' : 'var(--color-warning-50)', color: data.is_valid ? 'var(--color-success-700)' : 'var(--color-warning-700)', border: `1px solid ${data.is_valid ? 'var(--color-success-500)' : 'var(--color-warning-500)'}` }}>
        <strong>Status: </strong> {data.is_valid ? 'Config is ready' : 'Config has unconfirmed markers'}
      </div>
      {data.markers && data.markers.length > 0 && (() => {
        const groupedMarkers = data.markers.reduce((acc: any, m: any) => {
          const file = m.file.split('/').pop();
          if (!acc[file]) acc[file] = [];
          acc[file].push(m);
          return acc;
        }, {});
        
        const fileDescriptions: Record<string, string> = {
          'base.yaml': 'Core simulation configuration. Why we need it: Defines paths, horizons, and stochastic demands.',
          'costs_pilots.yaml': 'Pilot cost coefficients. Why we need it: Used for financial penalty modeling.',
          'costs_cabin.yaml': 'Cabin crew cost coefficients. Why we need it: Used for financial penalty modeling.'
        };

        return (
          <div>
            <h3 style={{ marginBottom: 'var(--spacing-4)' }}>CONFIRM Markers</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-6)' }}>
              {Object.entries(groupedMarkers).map(([fileName, markers]: [string, any]) => (
                <div key={fileName} style={{ backgroundColor: 'var(--surface-default)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-lg)', padding: 'var(--spacing-4)' }}>
                  <h4 style={{ fontSize: '1.125rem', color: 'var(--color-primary-700)', marginBottom: 'var(--spacing-1)' }}>{fileName}</h4>
                  <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-600)', marginBottom: 'var(--spacing-4)', fontStyle: 'italic' }}>
                    {fileDescriptions[fileName] || 'Configuration source file. Why we need it: Feeds the simulation engine.'}
                  </div>
                  
                  <ul style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)', padding: 0, listStyle: 'none' }}>
                    {markers.map((m: any, i: number) => {
                      // Attempt to extract the parameter name from the line text (e.g. "param_name: value # [CONFIRM: owner]")
                      const paramNameMatch = m.text.match(/^([^:]+):/);
                      const paramName = paramNameMatch ? paramNameMatch[1].trim() : 'Unknown Parameter';
                      
                      return (
                        <li key={i} style={{ padding: 'var(--spacing-3)', border: '1px solid var(--color-neutral-200)', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--color-neutral-50)' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', fontSize: '0.9rem' }}>
                              {paramName} <span style={{ color: 'var(--color-neutral-500)', fontSize: '0.75rem', marginLeft: '0.5rem' }}>(Line {m.line})</span>
                            </div>
                            <div style={{ color: 'var(--color-neutral-600)', fontSize: '0.75rem', backgroundColor: 'var(--color-neutral-200)', padding: '2px 8px', borderRadius: '12px' }}>
                              Owner: {m.owner}
                            </div>
                          </div>
                          
                          <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-600)', marginTop: 'var(--spacing-2)', marginBottom: 'var(--spacing-2)' }}>
                            Internal configuration setting. Why we need it: Currently flagged with a [CONFIRM] marker requiring sign-off before production runs.
                          </div>

                          <pre style={{ margin: '0', padding: 'var(--spacing-2)', backgroundColor: 'var(--color-bg-base)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', fontSize: '0.875rem', overflowX: 'auto' }}>
                            {m.text}
                          </pre>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        );
      })()}
    </div>
  );
};
