import React, { useState, useEffect } from 'react';

export const DataProfileView: React.FC = () => {
  const [htmlContent, setHtmlContent] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProfile = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/data/profile-report');
      if (res.ok) {
        const text = await res.text();
        setHtmlContent(text);
      } else {
        setError('Failed to fetch data profile report.');
      }
    } catch (err) {
      setError('An error occurred while fetching the profile.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 200px)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-4)' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Descriptive Data Profile</h2>
        <button 
          onClick={fetchProfile}
          disabled={loading}
          style={{
            padding: 'var(--spacing-2) var(--spacing-4)',
            backgroundColor: 'var(--color-primary-600)',
            color: 'white',
            border: 'none',
            borderRadius: 'var(--radius-md)',
            fontWeight: 500,
            cursor: loading ? 'not-allowed' : 'pointer'
          }}
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>
      
      {error && <div style={{ color: 'var(--color-error-text)', marginBottom: 'var(--spacing-4)' }}>{error}</div>}
      
      {!error && (
        <div style={{ flex: 1, border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
          {htmlContent ? (
            <iframe 
              srcDoc={htmlContent} 
              style={{ width: '100%', height: '100%', border: 'none' }}
              title="Data Profile Report"
            />
          ) : (
            <div style={{ padding: 'var(--spacing-4)', color: 'var(--color-neutral-500)' }}>
              Loading profile report...
            </div>
          )}
        </div>
      )}
    </div>
  );
};
