import React, { useState } from 'react';

export const ConfigSearch: React.FC = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/config/search?q=${encodeURIComponent(query)}`);
      if (!res.ok) throw new Error('Search failed');
      const data = await res.json();
      setResults(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card config-search" style={{ height: '100%', overflowY: 'auto' }}>
      <h2 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.25rem', fontWeight: 600 }}>Parameter Search</h2>
      <form onSubmit={handleSearch} style={{ display: 'flex', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-4)' }}>
        <input 
          type="text" 
          value={query} 
          onChange={e => setQuery(e.target.value)} 
          placeholder="Search config paths or values..."
          style={{ flex: 1, padding: 'var(--spacing-2)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)' }}
        />
        <button type="submit" disabled={loading} style={{ padding: 'var(--spacing-2) var(--spacing-4)', backgroundColor: 'var(--color-primary-600)', color: 'white', borderRadius: 'var(--radius-md)', border: 'none', cursor: 'pointer' }}>
          Search
        </button>
      </form>
      {error && <div style={{ color: 'var(--color-error-text)' }}>{error}</div>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
        {results.map((r, i) => (
          <div key={i} style={{ padding: 'var(--spacing-3)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--surface-default)' }}>
            <div style={{ fontWeight: 600, color: 'var(--color-primary-700)', marginBottom: 'var(--spacing-1)' }}>{r.path}</div>
            <pre style={{ margin: 0, padding: 'var(--spacing-2)', backgroundColor: 'var(--color-neutral-50)', borderRadius: 'var(--radius-sm)', fontSize: '0.875rem' }}>
              {JSON.stringify(r.value, null, 2)}
            </pre>
          </div>
        ))}
        {!loading && query && results.length === 0 && <div>No results found.</div>}
      </div>
    </div>
  );
};
