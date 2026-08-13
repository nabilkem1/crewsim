import React, { useEffect, useState } from 'react';

export const PolicyBrowser: React.FC = () => {
  const [policies, setPolicies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/config/policies')
      .then(res => {
        if (!res.ok) throw new Error('Failed to load policies');
        return res.json();
      })
      .then(d => {
        setPolicies(d);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Loading policies...</div>;
  if (error) return <div style={{ color: 'var(--color-error-text)' }}>{error}</div>;

  return (
    <div className="card policy-browser" style={{ height: '100%', overflowY: 'auto' }}>
      <h2 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.25rem', fontWeight: 600 }}>Policy Browser</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 'var(--spacing-4)' }}>
        {policies.map((p, i) => (
          <div key={i} style={{ padding: 'var(--spacing-4)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--surface-default)' }}>
            <h3 style={{ marginTop: 0, marginBottom: 'var(--spacing-2)', color: 'var(--color-primary-700)' }}>{p.filename}</h3>
            <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-600)', marginBottom: 'var(--spacing-2)' }}>
              <strong>Hash:</strong> {p.hash}
            </div>
            <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-600)', marginBottom: 'var(--spacing-1)' }}>
              <strong>ID:</strong> {p.policy.policy_id}
            </div>
            <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-600)', marginBottom: 'var(--spacing-1)' }}>
              <strong>Costs File:</strong> {p.policy.costs_file}
            </div>
            <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-600)', marginBottom: 'var(--spacing-1)' }}>
              <strong>Season:</strong> {p.policy.season}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
