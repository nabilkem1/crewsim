import React, { useEffect, useState } from 'react';

interface ParameterInspectionProps {
  category: string;
}

interface ConfigSchemaData {
  schema: any;
  current_values: any;
}

export const ParameterInspection: React.FC<ParameterInspectionProps> = ({ category }) => {
  const [data, setData] = useState<ConfigSchemaData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const richDescriptions: Record<string, Record<string, string>> = {
    paths: {
      corpus_dir: "Directory containing all input datasets. Why we need it: Required to load exogenous flying data and rosters.",
      params_dir: "Output directory for simulation parameters. Why we need it: Ensures run lineage is saved.",
      reports_dir: "Output directory for generated results. Why we need it: Stores charts and KPIs.",
      seasons_file: "Path to the season mapping. Why we need it: Used to determine peak vs off-peak rules."
    },
    horizon: {
      warmup_days: "Number of days before measurement starts. Why we need it: Stabilizes the simulation state before tracking.",
      measurement_days: "Core duration of the simulation. Why we need it: Determines the actual scope of the KPIs.",
      cooldown_days: "Trailing days after measurement. Why we need it: Clears out active pairings gracefully."
    },
    demand: {
      pairings_per_bid_period: "Total flight pairings per month. Why we need it: Drives the stochastic demand generation.",
      credit_hours_per_bid_period: "Total flying credit hours. Why we need it: Used to balance crew schedules.",
      uncovered_deadline_hours: "Threshold hours before cancellation. Why we need it: Prevents infinite assignment loops."
    },
    legality: {
      max_duty_hours: "Maximum continuous duty hours. Why we need it: Strictly required by FAA/EASA regulations.",
      min_rest_hours_home: "Minimum rest period at home base. Why we need it: Fatigue management compliance.",
      min_rest_hours_away: "Minimum rest period at outstations. Why we need it: Fatigue management compliance.",
      short_call_notice_hours: "Notice hours for short calls. Why we need it: Defines reserve deployment rules."
    },
    calibration: {
      delay_gmm_components: "Number of components in the delay GMM. Why we need it: Controls the precision of delay curve fitting.",
      overdispersion_threshold: "Threshold for marking a delay as overdispersed. Why we need it: Flags bad calibration data."
    }
  };

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`http://localhost:8000/api/config/schema/${category}`)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to fetch schema');
        return res.json();
      })
      .then((resData) => {
        setData(resData);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setError(err.message);
        setLoading(false);
      });
  }, [category]);

  if (loading) return <div className="card" style={{ color: 'var(--color-neutral-600)' }}>Loading details for {category}...</div>;
  if (error) return <div className="card" style={{ color: 'var(--color-error-text)' }}>Error: {error}</div>;
  if (!data) return null;

  const { schema, current_values } = data;
  const properties = schema?.properties || {};

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-6)' }}>
      <div>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 600, color: 'var(--color-neutral-900)', marginBottom: 'var(--spacing-2)' }}>
          {schema?.title || category}
        </h2>
        {schema?.description && (
          <p style={{ color: 'var(--color-neutral-600)' }}>{schema.description}</p>
        )}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
        {Object.entries(properties).map(([key, propSchema]: [string, any]) => {
          const val = current_values ? current_values[key] : undefined;
          
          return (
            <div key={key} style={{ 
              border: '1px solid var(--border-default)', 
              borderRadius: 'var(--radius-md)', 
              padding: 'var(--spacing-4)',
              backgroundColor: 'var(--surface-muted)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-2)' }}>
                <div style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', fontSize: '0.9rem', color: 'var(--color-primary-700)' }}>
                  {key}
                </div>
                <div style={{ 
                  fontSize: '0.75rem', 
                  backgroundColor: 'var(--color-neutral-200)', 
                  padding: 'var(--spacing-1) var(--spacing-2)', 
                  borderRadius: 'var(--radius-lg)',
                  color: 'var(--color-neutral-700)',
                  fontWeight: 500
                }}>
                  {propSchema.type || 'object'}
                </div>
              </div>
              
              { (richDescriptions[category]?.[key] || propSchema.description) ? (
                <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-600)', marginBottom: 'var(--spacing-3)', lineHeight: 1.5 }}>
                  {richDescriptions[category]?.[key] || propSchema.description}
                </div>
              ) : (
                <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-600)', marginBottom: 'var(--spacing-3)', fontStyle: 'italic' }}>
                  Controls internal engine logic for {key.replace(/_/g, ' ')}. Why we need it: Required for the stochastic simulation models to execute properly.
                </div>
              )}
              
              <div style={{ 
                backgroundColor: 'var(--surface-default)', 
                padding: 'var(--spacing-3)', 
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-default)',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.875rem'
              }}>
                <span style={{ color: 'var(--color-neutral-500)' }}>Current value: </span>
                <span style={{ fontWeight: 600, color: 'var(--color-neutral-900)' }}>
                  {val !== undefined ? (typeof val === 'object' ? JSON.stringify(val) : String(val)) : 'null'}
                </span>
              </div>
            </div>
          );
        })}
        {Object.keys(properties).length === 0 && (
          <div style={{ color: 'var(--color-neutral-500)', fontStyle: 'italic', fontSize: '0.875rem' }}>
            No detailed schema properties found for this category.
            <div style={{ marginTop: 'var(--spacing-2)', fontFamily: 'var(--font-mono)', fontSize: '0.875rem', fontStyle: 'normal' }}>
              <span style={{ color: 'var(--color-neutral-500)' }}>Value: </span>
              <span style={{ fontWeight: 600, color: 'var(--color-neutral-900)' }}>
                {JSON.stringify(current_values)}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ParameterInspection;
