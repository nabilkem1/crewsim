import { useCallback, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { apiFetch, errorMessage } from '../../api/client';
import { ErrorPanel, Loading } from '../../components/StatusPanel';
import { EventTape } from './EventTape';

/**
 * The demand behind the scoreboard, one row per scenario.
 *
 * E[C] and CVaR95 are two numbers summarising fifty outcomes, and from them a
 * planner cannot tell a uniformly mediocre policy from one that is usually
 * fine with a brutal tail. This shows the distribution those two numbers came
 * from: each scenario's severity regime day by day, its sick-call load, and
 * what each policy cost on it.
 *
 * Everything rendered here is measured. The regimes and counts are the
 * `scenarios/generator.py` parquet the engine actually ran against; the costs
 * are the per-scenario vector the paired comparison is computed from.
 */

interface DailyOutcomes {
  drafts: number[];
  cascading_drafts: number[];
  uncovered: number[];
}

interface ScenarioRow {
  scenario: number;
  regimes: string[];
  sick_calls: number[];
  total_sick_calls: number;
  /** Ambient flight delay: real, exogenous, and shared across every policy
   *  (like sick_calls above) -- calibrated from historical flight movements
   *  for this base+fleet, not caused by any reserve/draft decision. Null on
   *  scenario sets cached before this field existed. */
  delayed_flights: number[] | null;
  delay_minutes: number[] | null;
  total_delayed_flights: number | null;
  total_delay_minutes: number | null;
  costs: Record<string, number | null>;
  /** What each policy DID with the shared demand, day by day. Aggregated
   *  during the run, so it is per-day and not a scenario total repeated on
   *  every cell. Null for jobs run before this field existed. */
  outcomes: Record<string, DailyOutcomes | null>;
}

interface Fingerprints {
  job_id: string;
  season: string;
  master_seed: string;
  horizon_days: number;
  n_scenarios: number;
  policies: string[];
  regime_order: string[];
  scenarios: ScenarioRow[];
}

/** Severity ramp. Ordered, not categorical — the regimes are a scale. */
const REGIME_COLOR: Record<string, string> = {
  CALM: '#3f8f6b',
  NORMAL: '#4a7fd4',
  DISRUPTED: '#c98a2b',
  SEVERE: '#c0392b',
};
const UNKNOWN_REGIME = '#94a3b8';

/** CVaR95 averages the worst 5% of scenarios; marking exactly that set is what
 *  turns the column into something you can point at. */
const TAIL_FRACTION = 0.05;

/** Width of the right-hand block: sick-call total, cost bar, cost. The header
 *  control cluster is pinned to the same width, so the policy selector sits
 *  directly above the column it selects for rather than floating free. One
 *  constant, because two independently-tuned values drift the moment either
 *  side changes. */
const RIGHT_COLUMN = '272px';

type SortKey = 'scenario' | 'cost' | 'load';

const num: React.CSSProperties = {
  fontFamily: 'var(--font-mono, ui-monospace, monospace)',
  fontVariantNumeric: 'tabular-nums',
  fontSize: '0.75rem',
};

/** CSV field quoting: only wrap in quotes (and escape embedded quotes) when
 *  the field actually needs it, so the common case stays readable raw. */
function csvField(value: string | number): string {
  const s = String(value);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function downloadScenariosCsv(data: Fingerprints) {
  const policies = data.policies;
  const header = [
    'scenario',
    'day',
    'regime',
    'sick_calls',
    'total_sick_calls',
    // Exogenous and shared across every policy, same as sick_calls -- one
    // column each, not repeated per policy.
    'delayed_flights',
    'delay_minutes',
    // Scenario-level, repeated on every day row of that scenario -- the
    // denormalised-join convention.
    ...policies.map((p) => `cost_${p}`),
    // Genuinely per-day now that grid.py aggregates outcomes by horizon day.
    ...policies.map((p) => `drafts_${p}`),
    ...policies.map((p) => `cascading_drafts_${p}`),
    ...policies.map((p) => `uncovered_${p}`),
  ];
  const lines = [header.map(csvField).join(',')];

  for (const s of data.scenarios) {
    for (let day = 0; day < s.regimes.length; day++) {
      const row = [
        s.scenario,
        day,
        s.regimes[day],
        s.sick_calls[day] ?? 0,
        s.total_sick_calls,
        s.delayed_flights?.[day] ?? '',
        s.delay_minutes?.[day] ?? '',
        ...policies.map((p) => s.costs[p] ?? ''),
        ...policies.map((p) => s.outcomes?.[p]?.drafts?.[day] ?? ''),
        ...policies.map((p) => s.outcomes?.[p]?.cascading_drafts?.[day] ?? ''),
        ...policies.map((p) => s.outcomes?.[p]?.uncovered?.[day] ?? ''),
      ];
      lines.push(row.map(csvField).join(','));
    }
  }

  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `scenarios_${data.job_id}_${data.season}_${data.master_seed}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** A speech-balloon tooltip anchored to a hovered/focused day cell -- a fixed
 *  native `title` attribute is slow to appear, cannot be styled, and clips
 *  inside scrolling containers, all of which matter here since the grid can
 *  be dozens of scenarios wide and this is the only way to read a single
 *  day's numbers.
 *
 *  Rendered through a portal at a viewport-fixed position computed from the
 *  hovered cell's own bounding rect, rather than CSS-anchored inside the row.
 *  The grid used to be a horizontal scroll container, and `overflowX: 'auto'`
 *  implicitly computes `overflow-y: auto` too (an explicit scrolling value on
 *  one axis forces the other off `visible`), which silently clipped a balloon
 *  positioned via `bottom: 100%`. That container is gone -- the strip flexes
 *  to fit now -- but the portal stays: it is immune to clipping by ANY
 *  ancestor, and the panel it sits in is itself inside a scrollable job
 *  card. */
/** The balloon shell: portal, viewport-fixed placement, arrow. Shared so a
 *  second tooltip is a second CALLER, not a second copy of the styling. */
const Balloon: React.FC<{ anchor: DOMRect; children: React.ReactNode }> = ({ anchor, children }) =>
  createPortal(
    <div
      role="tooltip"
      style={{
        position: 'fixed',
        left: anchor.left + anchor.width / 2,
        top: anchor.top - 8,
        transform: 'translate(-50%, -100%)',
        // Chrome, not the neutral ramp: this chip is always dark, in both
        // themes -- see the --chrome-* token comment in index.css.
        background: 'var(--chrome-bg)',
        color: 'var(--chrome-text-strong)',
        padding: '0.35rem 0.6rem',
        borderRadius: 'var(--radius-md)',
        fontSize: '0.72rem',
        whiteSpace: 'nowrap',
        boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
        zIndex: 2000,
        pointerEvents: 'none',
      }}
    >
      {children}
      <div
        style={{
          position: 'absolute',
          top: '100%',
          left: '50%',
          transform: 'translateX(-50%)',
          borderWidth: '5px',
          borderStyle: 'solid',
          borderColor: 'var(--chrome-bg) transparent transparent transparent',
        }}
      />
    </div>,
    document.body,
  );

const sectionLabel: React.CSSProperties = {
  color: 'var(--chrome-text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  fontSize: '0.62rem',
  whiteSpace: 'nowrap',
  alignSelf: 'center',
};

const DayBalloon: React.FC<{
  day: number;
  regime: string;
  calls: number;
  /** Ambient flight delay, exogenous -- same for every policy, so shown
   *  alongside sick_calls rather than in the per-policy line below. */
  delayedFlights: number | null;
  delayMinutes: number | null;
  policy: string;
  /** THIS day's counts for the selected policy -- not scenario totals. Showing
   *  a whole-scenario figure on every one of 42 cells read as if the day
   *  itself had produced it. */
  drafts: number | null;
  cascadingDrafts: number | null;
  uncoveredLegs: number | null;
  anchor: DOMRect;
}> = ({ day, regime, calls, delayedFlights, delayMinutes, policy, drafts, cascadingDrafts, uncoveredLegs, anchor }) => (
    <Balloon anchor={anchor}>
      <div style={{ marginBottom: '0.3rem' }}>
        <strong>day {day}</strong> · {regime}
      </div>

      {/* Two labelled sections, because the figures are different populations
          and stacking them unlabelled read as cause and effect. Measured on a
          real scenario: one sick call opens 2.0 legs on average, and only 69
          of 154 outcomes are booked on the day their leg opened. */}
      <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '0.15rem 0.55rem' }}>
        <span style={sectionLabel}>demand arriving</span>
        <span>
          {calls} sick call{calls === 1 ? '' : 's'}
          {delayedFlights != null && (
            <>
              {' · '}
              {delayedFlights} delayed flight{delayedFlights === 1 ? '' : 's'}
              {delayMinutes != null && delayedFlights > 0
                ? ` (${Math.round(delayMinutes)} min)`
                : ''}
            </>
          )}
        </span>

        <span style={sectionLabel}>work {policy} completed</span>
        <span>
          {drafts ?? '—'} draft{drafts === 1 ? '' : 's'} · {cascadingDrafts ?? '—'} cascading ·{' '}
          {uncoveredLegs ?? '—'} uncovered
        </span>
      </div>

      <div
        style={{
          color: 'var(--chrome-text-muted)',
          marginTop: '0.35rem',
          fontStyle: 'italic',
          maxWidth: '30ch',
          whiteSpace: 'normal',
        }}
      >
        Work settles legs opened this day <em>or earlier</em> — it is not the answer to this day's
        sick calls. One absence also opens several legs.
      </div>
    </Balloon>
  );

export const ScenarioFingerprints: React.FC<{ jobId: string }> = ({ jobId }) => {
  // Which row is expanded into its event tape. One at a time: each open tape
  // is a scenario re-run on the server.
  const [openScenario, setOpenScenario] = useState<number | null>(null);
  const [data, setData] = useState<Fingerprints | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState<SortKey>('scenario');
  const [policy, setPolicy] = useState<string | null>(null);
  const [hoverCell, setHoverCell] = useState<{ scenario: number; day: number; rect: DOMRect } | null>(null);
  const [hoverTotal, setHoverTotal] = useState<{ scenario: number; rect: DOMRect } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await apiFetch<Fingerprints>(`/processing/${jobId}/scenarios`);
      setData(d);
      setPolicy((cur) => cur ?? d.policies[0] ?? null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    void load();
  }, [load]);

  const view = useMemo(() => {
    if (!data || !policy) return null;

    const costOf = (s: ScenarioRow) => s.costs[policy] ?? null;
    const costs = data.scenarios
      .map(costOf)
      .filter((c): c is number => c !== null);
    const maxCost = costs.length ? Math.max(...costs) : 0;
    const maxLoad = Math.max(1, ...data.scenarios.map((s) => Math.max(...s.sick_calls, 0)));

    // The worst 5%, rounded up so a small run still marks at least one.
    const tailSize = costs.length ? Math.max(1, Math.ceil(costs.length * TAIL_FRACTION)) : 0;
    const tailThreshold = [...costs].sort((a, b) => b - a)[tailSize - 1] ?? Infinity;

    const rows = [...data.scenarios].sort((a, b) => {
      if (sortKey === 'cost') return (costOf(b) ?? -1) - (costOf(a) ?? -1);
      if (sortKey === 'load') return b.total_sick_calls - a.total_sick_calls;
      return a.scenario - b.scenario;
    });

    return { rows, maxCost, maxLoad, tailThreshold, tailSize, costOf };
  }, [data, policy, sortKey]);

  if (loading) return <Loading what="scenario fingerprints" />;
  if (error) return <ErrorPanel message={error} onRetry={() => void load()} />;
  if (!data || !view || !policy) return null;

  const sortBtn = (key: SortKey, label: string) => (
    <button
      key={key}
      onClick={() => setSortKey(key)}
      style={{
        padding: '0.2rem 0.6rem',
        fontSize: '0.75rem',
        borderRadius: 'var(--radius-sm)',
        cursor: 'pointer',
        border: '1px solid var(--border-default)',
        background: sortKey === key ? 'var(--color-primary-600)' : 'transparent',
        color: sortKey === key ? 'var(--color-on-primary)' : 'var(--color-text-base)',
      }}
    >
      {label}
    </button>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 'var(--spacing-3)',
          flexWrap: 'wrap',
        }}
      >
        <div>
          <strong style={{ fontSize: '0.9rem' }}>Scenario distribution</strong>
          <div style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)' }}>
            The {data.n_scenarios} scenarios <em>this run</em> used · {data.horizon_days}-day
            horizon · {data.season} · seed {data.master_seed}
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: 'var(--spacing-2)',
            flexWrap: 'wrap',
            flex: `0 0 ${RIGHT_COLUMN}`,
          }}
        >
          {data.policies.length > 1 && (
            <select
              value={policy}
              onChange={(e) => setPolicy(e.target.value)}
              aria-label="Policy whose cost is shown"
              style={{
                padding: '0.2rem 0.4rem',
                fontSize: '0.75rem',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-default)',
              }}
            >
              {data.policies.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          )}
          <span style={{ fontSize: '0.72rem', color: 'var(--color-neutral-500)' }}>sort</span>
          {sortBtn('scenario', '#')}
          {sortBtn('cost', 'cost')}
          {sortBtn('load', 'sick calls')}
          <button
            onClick={() => downloadScenariosCsv(data)}
            title="Download every scenario's full day-by-day content (regime, sick calls, per-policy cost) as CSV"
            style={{
              padding: '0.2rem 0.6rem',
              fontSize: '0.75rem',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
              border: '1px solid var(--border-default)',
              background: 'transparent',
              color: 'var(--color-text-base)',
            }}
          >
            Download CSV
          </button>
        </div>
      </div>

      {/* Legend — the regimes are a severity scale, so they read left to right. */}
      <div
        style={{
          display: 'flex',
          gap: 'var(--spacing-3)',
          flexWrap: 'wrap',
          fontSize: '0.72rem',
          color: 'var(--color-neutral-500)',
          alignItems: 'center',
        }}
      >
        {data.regime_order.map((r) => (
          <span key={r} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
            <span
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '2px',
                background: REGIME_COLOR[r] ?? UNKNOWN_REGIME,
              }}
            />
            {r}
          </span>
        ))}
        <span style={{ marginLeft: 'auto' }}>Colour = that day's severity regime</span>
      </div>

      {/* No horizontal scroll. The strip is the row's identity -- scrolling it
          out of view left only a sick-call total and a bar, with nothing to
          say which scenario they belonged to. The day cells flex instead, so
          42 days always span whatever width is available. */}
      <div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', minWidth: 0 }}>
          {view.rows.map((s) => {
            const cost = view.costOf(s);
            const inTail = cost !== null && cost >= view.tailThreshold;
            return (
              <div key={s.scenario}>
              <div
                onClick={() => setOpenScenario((cur) => (cur === s.scenario ? null : s.scenario))}
                role="button"
                tabIndex={0}
                aria-expanded={openScenario === s.scenario}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setOpenScenario((cur) => (cur === s.scenario ? null : s.scenario));
                  }
                }}
                title={
                  openScenario === s.scenario
                    ? 'Close the replay'
                    : 'Replay this scenario event by event'
                }
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--spacing-2)',
                  cursor: 'pointer',
                  borderRadius: 'var(--radius-sm)',
                  background:
                    openScenario === s.scenario ? 'var(--color-primary-50, #eff6ff)' : 'transparent',
                }}
              >
                {/* The affordance. Decorative rather than a nested button:
                    the whole row is already the control and carries
                    aria-expanded, so a second focusable element here would
                    announce the same action twice. */}
                <span
                  aria-hidden="true"
                  style={{
                    width: '15px',
                    height: '15px',
                    flexShrink: 0,
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    borderRadius: '3px',
                    border: '1px solid',
                    borderColor:
                      openScenario === s.scenario
                        ? 'var(--color-primary-600)'
                        : 'var(--border-default)',
                    background:
                      openScenario === s.scenario ? 'var(--color-primary-600)' : 'transparent',
                    color:
                      openScenario === s.scenario ? 'var(--color-on-primary)' : 'var(--color-neutral-500)',
                    fontSize: '0.7rem',
                    lineHeight: 1,
                    fontWeight: 700,
                  }}
                >
                  {openScenario === s.scenario ? '−' : '+'}
                </span>

                <span
                  style={{ ...num, width: '2.2rem', textAlign: 'right', color: 'var(--color-neutral-500)' }}
                >
                  {s.scenario}
                </span>

                {/* One cell per horizon day. */}
                <div style={{ display: 'flex', gap: '1px', flex: '1 1 auto', minWidth: 0 }}>
                  {s.regimes.map((regime, day) => {
                    const calls = s.sick_calls[day] ?? 0;
                    const hovered = hoverCell?.scenario === s.scenario && hoverCell.day === day;
                    return (
                      <span
                        key={day}
                        aria-label={`day ${day}, ${regime}, ${calls} sick call${calls === 1 ? '' : 's'}`}
                        onMouseEnter={(e) =>
                          setHoverCell({ scenario: s.scenario, day, rect: e.currentTarget.getBoundingClientRect() })
                        }
                        onMouseLeave={() => setHoverCell(null)}
                        style={{
                          position: 'relative',
                          // Flexes to fit rather than a fixed 9px: 42 fixed
                          // cells forced the row wider than most panels.
                          flex: '1 1 0',
                          minWidth: '4px',
                          height: '16px',
                          borderRadius: '1px',
                          background: REGIME_COLOR[regime] ?? UNKNOWN_REGIME,
                          // Floor keeps a zero-call day visible as a regime,
                          // rather than reading as a gap in the horizon.
                          opacity: 0.22 + 0.78 * (calls / view.maxLoad),
                          outline: hovered ? '1px solid var(--color-neutral-900, #111827)' : undefined,
                        }}
                      >
                        {hovered && (
                          <DayBalloon
                            day={day}
                            regime={regime}
                            calls={calls}
                            delayedFlights={s.delayed_flights?.[day] ?? null}
                            delayMinutes={s.delay_minutes?.[day] ?? null}
                            policy={policy}
                            drafts={s.outcomes?.[policy]?.drafts?.[day] ?? null}
                            cascadingDrafts={s.outcomes?.[policy]?.cascading_drafts?.[day] ?? null}
                            uncoveredLegs={s.outcomes?.[policy]?.uncovered?.[day] ?? null}
                            anchor={hoverCell.rect}
                          />
                        )}
                      </span>
                    );
                  })}
                </div>

                {/* Right block: total, bar, cost. Fixed to RIGHT_COLUMN so it
                    lines up under the header controls. */}
                <div
                  style={{
                    flex: `0 0 ${RIGHT_COLUMN}`,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                  }}
                >
                <span
                  onMouseEnter={(e) =>
                    setHoverTotal({ scenario: s.scenario, rect: e.currentTarget.getBoundingClientRect() })
                  }
                  onMouseLeave={() => setHoverTotal(null)}
                  style={{
                    ...num,
                    position: 'relative',
                    width: '2.4rem',
                    textAlign: 'right',
                    color: 'var(--color-neutral-500)',
                    cursor: 'help',
                  }}
                >
                  {s.total_sick_calls}
                  {hoverTotal?.scenario === s.scenario && (
                    <Balloon anchor={hoverTotal.rect}>
                      <div>
                        <strong>{s.total_sick_calls} sick calls</strong> in scenario {s.scenario}
                      </div>
                      <div style={{ color: 'var(--chrome-text-muted)', marginTop: '0.15rem' }}>
                        summed over its {s.regimes.length} days · busiest day{' '}
                        {Math.max(...s.sick_calls, 0)}
                      </div>
                    </Balloon>
                  )}
                </span>

                {/* Cost bar, shared scale across scenarios. */}
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
                  <div
                    style={{
                      flex: 1,
                      height: '10px',
                      background: 'var(--color-neutral-200)',
                      borderRadius: '2px',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: cost !== null && view.maxCost > 0 ? `${(cost / view.maxCost) * 100}%` : '0%',
                        background: inTail ? 'var(--color-error-text)' : 'var(--color-primary-500)',
                      }}
                    />
                  </div>
                  <span
                    style={{
                      ...num,
                      width: '5.5rem',
                      textAlign: 'right',
                      color: inTail ? 'var(--color-error-text)' : 'var(--color-text-base)',
                      fontWeight: inTail ? 600 : 400,
                    }}
                  >
                    {cost === null ? '—' : `$${Math.round(cost).toLocaleString()}`}
                  </span>
                </div>
                </div>
              </div>

              {openScenario === s.scenario && (
                <div
                  style={{
                    // Left edge lines up with the day strip above it: the
                    // toggle glyph, the scenario number, and the two gaps
                    // between them. Derived rather than a guessed rem value,
                    // so adding the "+" did not silently knock it out of line.
                    margin:
                      'var(--spacing-2) 0 var(--spacing-4) calc(15px + 2.2rem + 2 * var(--spacing-2))',
                    padding: 'var(--spacing-3)',
                    border: '1px solid var(--border-default)',
                    borderRadius: 'var(--radius-md)',
                  }}
                >
                  <EventTape jobId={jobId} scenario={s.scenario} policy={policy} />
                </div>
              )}
              </div>
            );
          })}
        </div>
      </div>

      <div
        style={{
          fontSize: '0.78rem',
          color: 'var(--color-neutral-600)',
          borderTop: '1px solid var(--border-default)',
          paddingTop: 'var(--spacing-3)',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.45rem',
        }}
      >
        <div>
          <strong>How to read a row.</strong> Each row is one simulated 6-week period. The{' '}
          {data.horizon_days} small squares are its days, left to right: the colour is how
          disrupted that day was, and a <em>darker</em> square means more crew called in sick that
          day. Then the day's total sick calls, and what this policy cost over the whole period.
          Hover a square for <em>that day's</em> figures: sick calls and ambient flight delay
          (exogenous, real, shared by every policy), plus what the selected policy did about
          the sick calls — drafts, how many of those cascaded into a further draft, and legs
          left uncovered.
        </div>
        <div>
          <strong>Ambient flight delay is real but excluded from E[C]/CVaR95.</strong> It is
          historical flight-lateness for this base+fleet (D8-calibrated), not caused by any
          reserve/draft decision — it happens the same way regardless of policy, so it is shown
          here and in the cost breakdown as <code>DELAY_AMBIENT</code>, but deliberately left out
          of the cost the R* recommendation optimises.
        </div>
        <div>
          <strong>The red bars are the expensive ones</strong> — the worst{' '}
          {Math.round(TAIL_FRACTION * 100)}% of periods. Those are exactly the periods CVaR95
          averages, so this is the &ldquo;bad month&rdquo; figure made visible: a policy can look
          affordable on E[C] and still own the reddest rows here.
        </div>
        <div>
          <strong>Uncovered legs are spread across the horizon, not stacked at the end.</strong>{' '}
          A leg is counted uncovered when it reaches <em>its own</em> deadline still unfilled —
          hours or days after it opened. The separate &ldquo;still open when the horizon ends&rdquo;
          case exists (<code>TERMINAL_PENALTY</code>) but does not fire at this corpus size.
        </div>
        <div>
          <strong>Click a row (or its <span aria-hidden="true">+</span>)</strong> to replay that
          scenario event by event — every arrival, dispatch, draft and cancellation in order.
        </div>
        <div>
          Every policy runs against <em>this same demand</em> — that is what makes the comparison
          paired. Switching policy changes only the cost column, never the squares.
        </div>
      </div>
    </div>
  );
};
