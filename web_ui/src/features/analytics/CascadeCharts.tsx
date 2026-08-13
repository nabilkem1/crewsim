import type { PerScenarioRate } from './api';
import { pct } from './api';

/**
 * The small SVG pieces the cascade dashboard is built from.
 *
 * Hand-rolled rather than pulled from a chart library, matching
 * ScenarioFingerprints/EventTape -- this project has no charting dependency,
 * and these are simple enough that adding one would cost more than it saves.
 *
 * Everything structural (axes, gridlines, text, empty bars) is painted from
 * theme tokens so both themes work. The only fixed colours are semantic:
 * "this bar is the cascading one" carries meaning that must not swap when the
 * theme does, the same convention PolicyComparison's CATEGORY_COLORS follows.
 */

/**
 * Semantic fills for GRAPHICAL elements (bars, borders, rules) -- fixed in
 * both themes so "amber = this one cascaded" survives a theme switch.
 *
 * TEXT must not use these: #d29922 is only 2.5:1 on white and fails as a
 * text colour in the light theme. Text uses the --cascade-fg / --uncovered-fg
 * tokens, which hold the same hue at a lightness legible on each theme's own
 * surface (see index.css for the measured ratios).
 */
export const CASCADE_COLOR = '#d29922';
export const UNCOVERED_COLOR = '#f85149';
export const CASCADE_FG = 'var(--cascade-fg)';
export const UNCOVERED_FG = 'var(--uncovered-fg)';

export const KpiCard: React.FC<{
  label: string;
  value: string;
  /** The population this figure is measured over. Shown, not implied. */
  basis?: string;
  hint?: string;
  emphasis?: boolean;
}> = ({ label, value, basis, hint, emphasis = false }) => (
  <div
    style={{
      border: `1px solid ${emphasis ? CASCADE_COLOR : 'var(--border-default)'}`,
      borderRadius: 'var(--radius-md)',
      padding: 'var(--spacing-3) var(--spacing-4)',
      backgroundColor: 'var(--surface-default)',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.15rem',
      minWidth: 0,
    }}
  >
    <div
      style={{
        fontSize: '0.7rem',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        color: 'var(--color-neutral-500)',
      }}
    >
      {label}
    </div>
    <div
      style={{
        fontSize: '1.5rem',
        fontWeight: 600,
        fontVariantNumeric: 'tabular-nums',
        color: emphasis ? CASCADE_FG : 'var(--color-text-base)',
      }}
    >
      {value}
    </div>
    {basis && (
      <div style={{ fontSize: '0.68rem', color: 'var(--color-neutral-500)', fontFamily: 'var(--font-mono)' }}>
        {basis}
      </div>
    )}
    {hint && (
      <div style={{ fontSize: '0.72rem', color: 'var(--color-neutral-600)', lineHeight: 1.4 }}>
        {hint}
      </div>
    )}
  </div>
);

/**
 * Per-scenario cascade rate, one bar per scenario.
 *
 * This chart exists because the mean is misleading on its own. In the runs
 * measured so far most scenarios sit at zero and a single scenario carries
 * the whole rate, so a planner reading only "0.5%" would price a steady
 * trickle when the ledger shows something closer to a tail. Whether that
 * concentration generalises is not established -- the observations to date
 * share a master seed -- so the shape is drawn rather than asserted in copy.
 */
export const ScenarioRateStrip: React.FC<{ rows: PerScenarioRate[] }> = ({ rows }) => {
  const rated = rows.filter((r) => r.rate !== null);
  const max = Math.max(...rated.map((r) => r.rate ?? 0), 0);
  if (rated.length === 0) {
    return (
      <div style={{ fontSize: '0.8rem', color: 'var(--color-neutral-500)' }}>
        No scenario in this run produced a draft, so no cascade rate is defined.
      </div>
    );
  }
  const H = 90;
  const barW = 100 / rated.length;
  return (
    <div>
      <svg
        viewBox={`0 0 100 ${H}`}
        preserveAspectRatio="none"
        style={{ width: '100%', height: `${H}px`, display: 'block' }}
        role="img"
        aria-label={`Cascade rate for each of ${rated.length} scenarios. Mean ${pct(
          rated.reduce((a, r) => a + (r.rate ?? 0), 0) / rated.length,
        )}, peak ${pct(max)}.`}
      >
        {/* Baseline: without it, an all-zero run renders as blank space and
            reads as "no data" rather than "no cascades". */}
        <line x1="0" y1={H - 1} x2="100" y2={H - 1} stroke="var(--border-default)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        {rated.map((r, i) => {
          const h = max > 0 ? ((r.rate ?? 0) / max) * (H - 12) : 0;
          // A zero scenario still gets a visible stub. Drawing it at ~0 leaves
          // bare baseline, which reads as "no data" -- the opposite of the
          // point, since a run where nine of ten scenarios cascaded NOTHING is
          // exactly what this chart is here to show.
          const drawn = h > 0 ? Math.max(h, 3) : 3;
          return (
            <rect
              key={r.scenario_id}
              x={i * barW + barW * 0.15}
              y={H - 1 - drawn}
              width={barW * 0.7}
              height={drawn}
              fill={h > 0 ? CASCADE_COLOR : 'var(--color-neutral-300)'}
            >
              <title>
                {`scenario ${r.scenario_id}: ${r.n_cascading_drafts} of ${r.n_drafts} drafts cascaded (${pct(r.rate ?? 0, 2)})`}
              </title>
            </rect>
          );
        })}
      </svg>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '0.68rem',
          color: 'var(--color-neutral-500)',
          fontFamily: 'var(--font-mono)',
          marginTop: '0.2rem',
        }}
      >
        <span>scenario 0</span>
        <span>peak {pct(max, 2)}</span>
        <span>scenario {rated[rated.length - 1].scenario_id}</span>
      </div>
    </div>
  );
};

/** A labelled horizontal bar row -- used for chain sizes and draft tiers. */
export const BarRow: React.FC<{
  label: string;
  value: number;
  max: number;
  color?: string;
  suffix?: string;
  title?: string;
  /** Overrides the printed figure when the bar is money rather than a count. */
  display?: string;
}> = ({ label, value, max, color, suffix, title, display }) => (
  <div
    style={{ display: 'grid', gridTemplateColumns: '7rem 1fr 5rem', alignItems: 'center', gap: 'var(--spacing-2)' }}
    title={title}
  >
    <span style={{ fontSize: '0.78rem', color: 'var(--color-neutral-600)', fontFamily: 'var(--font-mono)' }}>
      {label}
    </span>
    <div
      style={{
        height: '14px',
        backgroundColor: 'var(--color-neutral-100)',
        borderRadius: 'var(--radius-sm)',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          width: max > 0 ? `${Math.max((value / max) * 100, value > 0 ? 1.5 : 0)}%` : '0%',
          height: '100%',
          backgroundColor: color ?? 'var(--color-primary-600)',
        }}
      />
    </div>
    <span
      style={{
        fontSize: '0.78rem',
        fontVariantNumeric: 'tabular-nums',
        textAlign: 'right',
        color: 'var(--color-text-base)',
        fontFamily: 'var(--font-mono)',
      }}
    >
      {display ?? value.toLocaleString()}
      {suffix}
    </span>
  </div>
);

/**
 * The amplification comparison: two bars, one baseline, one cascading.
 *
 * Deliberately not a ratio-only readout. The ratio is the headline, but a
 * 7x amplification on chains that are rare and cheap is a different planning
 * problem from 7x on common expensive ones, and only the absolute bars show
 * which one this is.
 */
export const AmplificationBars: React.FC<{
  simple: number | null;
  cascading: number | null;
  format: (v: number) => string;
}> = ({ simple, cascading, format }) => {
  if (simple === null || cascading === null) return null;
  const max = Math.max(simple, cascading);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
      <BarRow
        label="resolved"
        value={Math.round(simple)}
        display={format(simple)}
        max={max}
        color="var(--color-neutral-400)"
        title="Mean cost of a chain that was absorbed where it landed (one open item)"
      />
      <BarRow
        label="cascaded"
        value={Math.round(cascading)}
        display={format(cascading)}
        max={max}
        color={CASCADE_COLOR}
        title="Mean cost of a chain that grew to more than one open item"
      />
      <div style={{ fontSize: '0.72rem', color: 'var(--color-neutral-600)', lineHeight: 1.45 }}>
        Mean attributable cost per chain, {format(simple)} against {format(cascading)}. Every dollar is
        traced through <code>root_event_uid</code>, so a cascade's cost is the recovery cost of the item
        it created — never a separate added term (§5.7's anti-double-counting rule).
      </div>
    </div>
  );
};

export const Callout: React.FC<{
  tone: 'info' | 'warn';
  title: string;
  children: React.ReactNode;
}> = ({ tone, title, children }) => (
  <div
    style={{
      border: '1px solid var(--border-default)',
      borderLeft: `3px solid ${tone === 'warn' ? 'var(--color-warning-500)' : 'var(--color-primary-500)'}`,
      borderRadius: 'var(--radius-md)',
      padding: 'var(--spacing-3) var(--spacing-4)',
      backgroundColor: tone === 'warn' ? 'var(--color-warning-bg)' : 'var(--surface-muted)',
      fontSize: '0.8rem',
      lineHeight: 1.5,
      color: 'var(--color-text-base)',
    }}
  >
    <strong style={{ display: 'block', marginBottom: '0.25rem' }}>{title}</strong>
    <span style={{ color: 'var(--color-neutral-700)' }}>{children}</span>
  </div>
);
