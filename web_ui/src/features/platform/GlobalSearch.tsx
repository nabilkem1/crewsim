import { useState } from 'react';

interface SearchResult {
  id: string;
  type: string;
  title: string;
}

export function GlobalSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query) return;
    
    setLoading(true);
    try {
      const res = await fetch(`/api/platform/search?q=${encodeURIComponent(query)}`);
      const data = await res.json();
      setResults(data.results || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h2 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.25rem', fontWeight: 600, marginTop: 0 }}>Global Cross-Entity Search</h2>
      <form onSubmit={handleSearch} style={{ display: 'flex', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-6)' }}>
        <input 
          type="text" 
          value={query} 
          onChange={(e) => setQuery(e.target.value)} 
          placeholder="Search jobs, runs, agents..." 
          style={{ flexGrow: 1, padding: 'var(--spacing-2) var(--spacing-3)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', fontSize: '0.875rem' }}
        />
        <button type="submit" disabled={loading} style={{ padding: 'var(--spacing-2) var(--spacing-4)', backgroundColor: 'var(--color-primary-600)', color: 'white', border: 'none', borderRadius: 'var(--radius-md)', cursor: 'pointer', fontWeight: 500, fontSize: '0.875rem' }}>
          Search
        </button>
      </form>
      
      {loading && <div style={{ color: 'var(--color-neutral-500)', fontSize: '0.875rem' }}>Searching...</div>}
      
      {!loading && results.length > 0 && (
        <ul style={{ listStyleType: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
          {results.map(r => (
            <li key={r.id} style={{ padding: 'var(--spacing-3)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--surface-muted)', display: 'flex', gap: 'var(--spacing-2)' }}>
              <span style={{ fontWeight: 600, color: 'var(--color-primary-600)', fontSize: '0.75rem' }}>[{r.type.toUpperCase()}]</span> 
              <span style={{ fontSize: '0.875rem' }}>{r.title}</span>
            </li>
          ))}
        </ul>
      )}
      {!loading && query && results.length === 0 && (
        <div style={{ color: 'var(--color-neutral-500)', fontSize: '0.875rem' }}>No results found for "{query}".</div>
      )}
    </div>
  );
}
