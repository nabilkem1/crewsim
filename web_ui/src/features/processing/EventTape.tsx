import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch, errorMessage } from '../../api/client';
import { ErrorPanel, Loading } from '../../components/StatusPanel';

/**
 * One scenario replayed as a time-ordered tape, with a scrubber.
 *
 * A scrubber rather than an autoplaying timeline: the interesting moment is
 * usually a specific one — where a cascade started, where the reserve pool ran
 * out — and an animation makes you wait for it and then lose it. Play is
 * offered as a secondary control for demonstrating the run to someone else.
 *
 * Everything here is a record of something the engine did. The rows are ledger
 * entries and trace lines from a re-run of this exact scenario; nothing is
 * interpolated between them.
 */

interface TapeEvent {
  t: number;
  day: number;
  clock: string;
  kind: string;
  category: string;
  crew: string | null;
  item: number;
  items: number[];
  root: number;
  amount: number | null;
  depth: number;
  in_window: boolean;
  text: string;
}

interface Tape {
  scenario: number;
  policy: string;
  master_seed: string;
  horizon_minutes: number;
  horizon_days: number;
  events: TapeEvent[];
  window: { warmup_end: number; measurement_end: number; note: string };
  totals: {
    cost: number;
    measured_cost: number;
    drafts: number;
    reserve_dispatches: number;
    uncovered: number;
  };
  background: { category: string; total: number; rows: number; note: string };
}

const COLOR: Record<string, string> = {
  SICK_CALL: '#ffb454',
  DISPLACED_LINE: '#7f8ea3',
  RESERVE_UTILIZATION: '#79d3a5',
  CANCELLATION: '#ff8a7a',
  APPR_COMPENSATION: '#ff8a7a',
  TERMINAL_PENALTY: '#ff8a7a',
  DEADHEAD: '#7fb4ff',
  HOTEL: '#7fb4ff',
  TRANSPORT: '#7fb4ff',
};
const DRAFT_COLOR = '#f0a8ff';
const DEFAULT_COLOR = '#cfd6df';

const colorFor = (kind: string) =>
  kind.startsWith('DRAFT_TIER') ? DRAFT_COLOR : (COLOR[kind] ?? DEFAULT_COLOR);

const money = (v: number) => `$${Math.round(v).toLocaleString()}`;

/** Play advances by a share of the horizon per tick — so a 42-day scenario and
 *  a 7-day one take the same wall-clock time to watch. */
const PLAY_TICK_MS = 120;
const PLAY_STEPS = 160;

export const EventTape: React.FC<{ jobId: string; scenario: number; policy: string }> = ({
  jobId,
  scenario,
  policy,
}) => {
  const [tape, setTape] = useState<Tape | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [cursor, setCursor] = useState(0); // simulated minutes
  const [playing, setPlaying] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setPlaying(false);
    try {
      const t = await apiFetch<Tape>(
        `/processing/${jobId}/scenario/${scenario}/events?policy=${encodeURIComponent(policy)}`,
      );
      setTape(t);
      // Open fully scrubbed to the end: the completed run is the default
      // question ("what happened?"), not an empty tape.
      setCursor(t.horizon_minutes);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [jobId, scenario, policy]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!playing || !tape) return;
    const step = tape.horizon_minutes / PLAY_STEPS;
    const id = setInterval(() => {
      setCursor((c) => {
        if (c >= tape.horizon_minutes) {
          setPlaying(false);
          return c;
        }
        return Math.min(tape.horizon_minutes, c + step);
      });
    }, PLAY_TICK_MS);
    return () => clearInterval(id);
  }, [playing, tape]);

  const shown = useMemo(
    () => (tape ? tape.events.filter((e) => e.t <= cursor) : []),
    [tape, cursor],
  );

  // Running state at the cursor, accumulated from the events themselves rather
  // than interpolated — so the figures always equal the lines above them.
  const running = useMemo(() => {
    let cost = 0;
    let measured = 0;
    let drafts = 0;
    let dispatches = 0;
    let uncovered = 0;
    for (const e of shown) {
      if (e.amount !== null) {
        cost += e.amount;
        if (e.in_window) measured += e.amount;
      }
      if (e.kind.startsWith('DRAFT_TIER')) drafts += 1;
      else if (e.kind === 'RESERVE_UTILIZATION') dispatches += 1;
      else if (e.kind === 'CANCELLATION' || e.kind === 'TERMINAL_PENALTY') uncovered += 1;
    }
    return { cost, measured, drafts, dispatches, uncovered };
  }, [shown]);

  useEffect(() => {
    if (playing) bottomRef.current?.scrollIntoView({ block: 'nearest' });
  }, [shown.length, playing]);

  if (loading) return <Loading what={`scenario ${scenario} events`} />;
  if (error) return <ErrorPanel message={error} onRetry={() => void load()} />;
  if (!tape) return null;

  const day = Math.floor(cursor / (tape.horizon_minutes / tape.horizon_days));
  const atEnd = cursor >= tape.horizon_minutes;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
      {/* Scrubber */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-3)', flexWrap: 'wrap' }}>
        <button
          onClick={() => {
            if (atEnd) setCursor(0);
            setPlaying((p) => !p);
          }}
          aria-label={playing ? 'Pause' : 'Play'}
          style={{
            width: '30px',
            height: '30px',
            borderRadius: '50%',
            border: '1px solid var(--border-default)',
            background: 'transparent',
            cursor: 'pointer',
            flexShrink: 0,
          }}
        >
          {playing ? '❙❙' : '▶'}
        </button>

        <input
          type="range"
          min={0}
          max={tape.horizon_minutes}
          value={cursor}
          onChange={(e) => {
            setPlaying(false);
            setCursor(Number(e.target.value));
          }}
          aria-label="Simulated time"
          style={{ flex: 1, minWidth: '200px', cursor: 'pointer' }}
        />

        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.8125rem',
            fontVariantNumeric: 'tabular-nums',
            whiteSpace: 'nowrap',
          }}
        >
          day {day} / {tape.horizon_days}
        </span>
      </div>

      {/* Running state at the cursor */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
          gap: 'var(--spacing-2)',
          fontSize: '0.8125rem',
          fontFamily: 'var(--font-mono)',
        }}
      >
        {[
          ['events', `${shown.length} / ${tape.events.length}`],
          ['dispatches', running.dispatches],
          ['drafts', running.drafts],
          ['uncovered', running.uncovered],
          ['measured cost', money(running.measured)],
        ].map(([label, value]) => (
          <div
            key={String(label)}
            style={{
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-sm)',
              padding: '0.35rem 0.6rem',
            }}
          >
            <div style={{ fontSize: '0.65rem', color: 'var(--color-neutral-500)', fontFamily: 'inherit' }}>
              {label}
            </div>
            <div>{value}</div>
          </div>
        ))}
      </div>

      {/* The tape */}
      <div
        style={{
          // Chrome tokens for the panel itself (always dark, both themes);
          // the muted grays below it are terminal-specific dimming levels,
          // deliberately left as their own literals rather than collapsed
          // into one token.
          backgroundColor: 'var(--chrome-bg)',
          color: 'var(--chrome-text-strong)',
          borderRadius: 'var(--radius-md)',
          padding: 'var(--spacing-3)',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.78rem',
          lineHeight: 1.65,
          maxHeight: '380px',
          overflow: 'auto',
        }}
      >
        {shown.length === 0 && <div style={{ color: '#6b7787' }}>nothing has happened yet</div>}

        {shown.map((e, i) => (
          <div
            key={`${e.t}-${e.item}-${e.kind}-${i}`}
            style={{ whiteSpace: 'pre', opacity: e.in_window ? 1 : 0.45 }}
            title={
              e.in_window
                ? undefined
                : 'Outside the measurement window — shown because it happened, not counted in E[C]'
            }
          >
            <span style={{ color: '#6b7787' }}>
              {`day ${String(e.day).padStart(2)} ${e.clock}  `}
            </span>
            <span style={{ color: '#475569' }}>{'  '.repeat(e.depth)}</span>
            {e.depth > 0 && <span style={{ color: '#475569' }}>└ </span>}
            <span style={{ color: colorFor(e.kind) }}>{e.kind}</span>
            <span>{`  ${e.crew ?? ''}`}</span>
            <span style={{ color: '#94a3b8' }}>{`  ${e.text}`}</span>
            {e.amount !== null && (
              <span style={{ color: '#ffb454' }}>{`  ${money(e.amount)}`}</span>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div style={{ fontSize: '0.75rem', color: 'var(--color-neutral-600)', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
        <div>
          <strong>Indented lines are consequences.</strong> A draft that broke someone else's
          pairing appears under the absence that caused it — the same causal chain the{' '}
          <code>casc</code> column counts in aggregate.
        </div>
        <div>
          <strong>Dimmed lines fall outside the measurement window.</strong> They happened, but
          E[C] does not count them: warm-up is excluded, and cool-down counts only where the chain
          started inside. That is why <em>measured cost</em> above ends at{' '}
          {money(tape.totals.measured_cost)} while the full ledger is {money(tape.totals.cost)}.
        </div>
        <div>
          {tape.background.rows.toLocaleString()} {tape.background.category} rows totalling{' '}
          {money(tape.background.total)} are not shown — {tape.background.note.toLowerCase()}
        </div>
      </div>
    </div>
  );
};
