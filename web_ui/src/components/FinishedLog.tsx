import { useCallback, useEffect, useState } from 'react';
import { apiFetch, errorMessage } from '../api/client';
import { LogView, type LogEntry } from './LogView';

/**
 * The recorded execution log for a job that has already finished.
 *
 * A completed job has nothing left to stream, so this fetches the stored log
 * once instead of opening an `EventSource` that would connect, receive one
 * event and immediately close.
 */
export const FinishedLog: React.FC<{ jobId: string; resource?: string }> = ({
  jobId,
  resource = 'processing',
}) => {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<{ log: LogEntry[] }>(`/${resource}/${jobId}/logs`);
      setEntries(data.log ?? []);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoaded(true);
    }
  }, [jobId, resource]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <div style={{ fontSize: '0.8125rem', color: 'var(--color-error-text)' }}>{error}</div>
    );
  }
  if (loaded && entries.length === 0) {
    // Jobs created before the execution log existed have no entries. Say that
    // rather than rendering an empty terminal that looks like a failure.
    return (
      <div style={{ fontSize: '0.8125rem', color: 'var(--color-neutral-500)' }}>
        No execution log was recorded for this job.
      </div>
    );
  }

  return <LogView entries={entries} heading="Execution log" status="finished" />;
};
