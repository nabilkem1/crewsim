import { useCallback, useEffect, useState } from 'react';
import { errorMessage } from '../../api/client';
import { ErrorPanel, Loading } from '../../components/StatusPanel';
import { fetchSummaries, type RunSummary } from './api';

/**
 * Two columns were removed from this table: "Events", which the backend always
 * reported as 0, and "Success Rate", which was not a rate at all -- it was
 * 100% for a completed job and 0% for anything else, i.e. the status column
 * rendered as a percentage.
 */
export function Summaries() {
  const [data, setData] = useState<RunSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchSummaries());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="card">
      <h2 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.25rem', fontWeight: 600 }}>
        Processing Run Summaries
      </h2>

      {loading && <Loading what="run summaries" />}
      {!loading && error && <ErrorPanel message={error} onRetry={() => void load()} />}
      {!loading && !error && data.length === 0 && (
        <p style={{ color: 'var(--color-neutral-500)', fontSize: '0.875rem' }}>
          No processing runs yet. Launch one from the Processing tab.
        </p>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
        {data.map((run) => (
          <div
            key={run.id}
            style={{
              border: '1px solid var(--border-default)',
              padding: 'var(--spacing-4)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <h3 style={{ marginBottom: 'var(--spacing-2)', fontWeight: 600 }}>{run.name}</h3>
            <div
              style={{
                display: 'flex',
                gap: 'var(--spacing-4)',
                flexWrap: 'wrap',
                color: 'var(--color-neutral-600)',
                fontSize: '0.875rem',
              }}
            >
              <span style={{ fontFamily: 'var(--font-mono)' }}>{run.id}</span>
              <span>Status: {run.status}</span>
              <span>Duration: {run.duration ?? '—'}</span>
              <span>Started: {new Date(run.created_at).toLocaleString()}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
