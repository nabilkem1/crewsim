import { useEffect, useRef, useState } from 'react';
import { LogView, type LogEntry } from './LogView';

/**
 * The execution log, streamed over server-sent events while a job runs.
 *
 * Replaces a blind 2-second `setInterval` refetch of every job. `EventSource`
 * holds one connection and the backend emits an event whenever the job row
 * changes, so a step appears here within half a second of being recorded.
 *
 * Every value shown is measured by the run that produced it -- the real
 * parameter-store version and hash, real wall-clock durations, real policy and
 * scenario counts (see `api/runlog.py`). Nothing here is a template filled in
 * beside the run.
 */

export interface JobEvent {
  job_id: string;
  status: string;
  progress: number;
  log: LogEntry[];
  error_message: string | null;
}

export const ExecutionLog: React.FC<{
  jobId: string;
  /** API resource the job belongs to, e.g. 'processing' or 'calibration'. */
  resource?: string;
  onFinished?: () => void;
}> = ({ jobId, resource = 'processing', onFinished }) => {
  const [event, setEvent] = useState<JobEvent | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);

  // Held in a ref so a caller passing an inline arrow does not tear down and
  // re-open the stream on every render.
  const onFinishedRef = useRef(onFinished);
  onFinishedRef.current = onFinished;

  useEffect(() => {
    let finished = false;
    setEvent(null);
    setStreamError(null);

    const source = new EventSource(`/api/${resource}/${jobId}/stream`);

    source.onmessage = (e) => setEvent(JSON.parse(e.data) as JobEvent);

    source.addEventListener('end', () => {
      source.close();
      if (!finished) {
        finished = true;
        onFinishedRef.current?.();
      }
    });

    source.onerror = () => {
      // EventSource reconnects on its own; only surface it if the browser gave up.
      if (source.readyState === EventSource.CLOSED && !finished) {
        setStreamError('Lost the connection to the job stream.');
      }
    };

    return () => source.close();
  }, [jobId, resource]);

  return (
    <div>
      <LogView
        entries={event?.log ?? []}
        heading="Execution log"
        status={event ? `${event.status} · ${event.progress}%` : 'connecting…'}
      />

      {streamError && (
        <div
          style={{
            marginTop: 'var(--spacing-2)',
            fontSize: '0.8125rem',
            color: 'var(--color-error-text)',
          }}
        >
          {streamError}
        </div>
      )}
    </div>
  );
};
