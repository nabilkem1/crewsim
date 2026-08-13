import { useEffect, useRef, useState } from 'react';

/**
 * Terminal-style renderer for the execution log.
 *
 * Shared by the live (SSE) and finished (fetched) views so a step looks
 * identical whether you watched it happen or opened the job afterwards.
 */

export interface LogEntry {
  step: number | null;
  total: number;
  message: string;
  detail: string | null;
  status: 'running' | 'done' | 'failed' | 'info' | 'warning' | 'error';
  duration_ms: number | null;
  /** Scenario counters for the step in flight; null when not applicable. */
  progress_done?: number | null;
  progress_total?: number | null;
  /** Bare filename of a file this step produced, if any -- rendered as a
   *  download link. The URL is built here rather than sent by the API, so the
   *  log stays a record of what happened rather than of how to fetch it. */
  artifact?: string | null;
}

/** Files land in the configured reports/params directories; this endpoint
 *  serves either, and refuses anything that is not a direct child of one. */
const artifactHref = (filename: string) =>
  `/api/results/artifacts/download/${encodeURIComponent(filename)}?raw=1`;

/** Braille spinner: fixed-width in a monospace column, so the line does not
 *  jitter as it animates. */
const SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
const SPINNER_INTERVAL_MS = 80;

function useSpinner(active: boolean): string {
  const [frame, setFrame] = useState(0);
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setFrame((f) => (f + 1) % SPINNER_FRAMES.length), SPINNER_INTERVAL_MS);
    return () => clearInterval(id);
  }, [active]);
  return SPINNER_FRAMES[frame];
}

const BAR_WIDTH = 28;

/** An in-terminal bar for the step in flight. */
const StepProgress: React.FC<{ done: number; total: number }> = ({ done, total }) => {
  const pct = total > 0 ? Math.min(1, done / total) : 0;
  const filled = Math.round(pct * BAR_WIDTH);
  return (
    <div style={{ paddingLeft: '6ch', whiteSpace: 'pre', color: '#38bdf8' }}>
      <span>{'█'.repeat(filled)}</span>
      <span style={{ color: '#334155' }}>{'░'.repeat(BAR_WIDTH - filled)}</span>
      <span style={{ color: '#94a3b8' }}>
        {'  '}
        {Math.round(pct * 100)}% ({done.toLocaleString()}/{total.toLocaleString()})
      </span>
    </div>
  );
};

const MS_PER_SECOND = 1000;
/** Column the measured durations line up on, as in the CLI's own output. */
const LEADER_WIDTH = 58;

const STATUS_COLOR: Record<LogEntry['status'], string> = {
  running: '#38bdf8',
  done: '#4ade80',
  failed: '#f87171',
  error: '#f87171',
  warning: '#fbbf24',
  info: '#94a3b8',
};

function formatDuration(ms: number | null): string {
  if (ms === null) return '';
  return ms < MS_PER_SECOND ? `${ms} ms` : `${(ms / MS_PER_SECOND).toFixed(1)} s`;
}

function gutter(entry: LogEntry): string {
  if (entry.step === null) return entry.status === 'warning' || entry.status === 'error' ? ' ⚠ ' : '   ';
  return `[${entry.step}/${entry.total}]`;
}

function leader(text: string): string {
  return ' ' + '.'.repeat(Math.max(1, LEADER_WIDTH - text.length)) + ' ';
}

const LogLine: React.FC<{ entry: LogEntry }> = ({ entry }) => {
  const running = entry.status === 'running';
  const spinner = useSpinner(running);
  const hasBar =
    running && typeof entry.progress_done === 'number' && typeof entry.progress_total === 'number';

  return (
    <div>
      <div style={{ whiteSpace: 'pre' }}>
        <span style={{ color: STATUS_COLOR[entry.status] ?? '#e2e8f0' }}>{gutter(entry)}</span>
        <span> {entry.message}</span>
        {entry.duration_ms !== null && (
          <>
            <span style={{ color: '#475569' }}>{leader(entry.message)}</span>
            <span style={{ color: '#94a3b8' }}>{formatDuration(entry.duration_ms)}</span>
          </>
        )}
        {running && <span style={{ color: '#38bdf8' }}> {spinner}</span>}
      </div>

      {entry.detail && (
        <div
          style={{
            color: '#94a3b8',
            paddingLeft: '6ch',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          → {entry.detail}
        </div>
      )}

      {entry.artifact && (
        <div style={{ paddingLeft: '6ch' }}>
          <a
            href={artifactHref(entry.artifact)}
            download={entry.artifact}
            title={`Download ${entry.artifact}`}
            style={{ color: '#7dd3fc', textDecoration: 'underline' }}
          >
            ⭳ {entry.artifact}
          </a>
        </div>
      )}

      {hasBar && <StepProgress done={entry.progress_done!} total={entry.progress_total!} />}
    </div>
  );
};

export const LogView: React.FC<{
  entries: LogEntry[];
  heading: string;
  status: string;
}> = ({ entries, heading, status }) => {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'nearest' });
  }, [entries]);

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 'var(--spacing-2)',
        }}
      >
        <strong style={{ fontSize: '0.875rem' }}>{heading}</strong>
        <span style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)' }}>{status}</span>
      </div>

      <div
        style={{
          backgroundColor: 'var(--chrome-bg)',
          color: 'var(--chrome-text-strong)',
          borderRadius: 'var(--radius-md)',
          padding: 'var(--spacing-3)',
          fontFamily: 'var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace)',
          fontSize: '0.8125rem',
          lineHeight: 1.6,
          maxHeight: '340px',
          overflowY: 'auto',
          overflowX: 'auto',
        }}
      >
        {entries.length === 0 && <div style={{ color: '#94a3b8' }}>waiting for the job to start…</div>}

        {entries.map((entry, i) => (
          <LogLine key={i} entry={entry} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};
