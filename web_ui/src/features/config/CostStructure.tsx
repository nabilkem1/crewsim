import React, { useEffect, useState } from 'react';

export const CostStructure: React.FC = () => {
  const [costs, setCosts] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('http://localhost:8000/api/config/costs')
      .then(res => {
        if (!res.ok) throw new Error('Failed to load cost structure');
        return res.json();
      })
      .then(d => {
        setCosts(d);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Loading cost structure...</div>;
  if (error) return <div style={{ color: 'var(--color-error-text)' }}>{error}</div>;

  return (
    <div className="card cost-structure" style={{ height: '100%', overflowY: 'auto' }}>
      <h2 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.25rem', fontWeight: 600 }}>Cost Structure</h2>
      <pre style={{ margin: 0, padding: 'var(--spacing-4)', backgroundColor: 'var(--color-neutral-50)', borderRadius: 'var(--radius-md)', fontSize: '0.875rem', overflowX: 'auto' }}>
        {JSON.stringify(costs, null, 2)}
      </pre>
    </div>
  );
};
