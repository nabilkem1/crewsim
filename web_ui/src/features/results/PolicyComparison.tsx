import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { errorMessage } from '../../api/client';
import { ErrorPanel, Loading } from '../../components/StatusPanel';
import { Modal } from '../../components/Modal';
import { GateBadge } from './GateBadge';
import {
  fetchArtifacts,
  fetchDrilldownJob,
  fetchJobDetail,
  fetchSummaries,
  launchDrilldown,
  type ConfirmMarker,
  type DrilldownResults,
  type GateRow,
  type GateVerdict,
  type JobResults,
  type RunSummary,
  type ScoreboardRow,
} from './api';

/**
 * The IOC-facing decision surface: which reserve policy (R value) to run.
 *
 * Every number here comes from `run_processing_job`'s real batch-grid
 * scoreboard (crewsim.reporting.grid/kpis/paired/recommendation/gate_status)
 * -- nothing is computed client-side beyond sorting and display formatting.
 * The one thing this component refuses to soften is a failed validation
 * gate: when V3 or V4 fails, the warning is attached directly to the
 * recommendation, not filed separately, because a recommendation card is
 * exactly the number a planner acts on.
 */

const money = (v: number | null | undefined) =>
  v == null ? '—' : `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

const pct = (v: number | null | undefined, digits = 1) =>
  v == null ? '—' : `${(v * 100).toFixed(digits)}%`;

const cellStyle: React.CSSProperties = {
  padding: 'var(--spacing-3) var(--spacing-4)',
  borderBottom: '1px solid var(--border-default)',
};
const headStyle: React.CSSProperties = {
  ...cellStyle,
  fontWeight: 600,
  color: 'var(--color-neutral-600)',
  textAlign: 'left',
  backgroundColor: 'var(--surface-muted)',
};
const smallMuted: React.CSSProperties = {
  fontSize: '0.75rem',
  color: 'var(--color-neutral-500)',
};

// A stable colour per ledger category, so the same category reads the same
// colour in every stacked bar rather than shifting with insertion order.
const CATEGORY_COLORS: Record<string, string> = {
  RESERVE_STAFFING: '#60a5fa',
  RESERVE_UTILIZATION: '#3b82f6',
  DRAFT_TIER1: '#34d399',
  DRAFT_TIER2: '#22c55e',
  DRAFT_TIER3: '#16a34a',
  DRAFT_TIER4: '#15803d',
  DRAFT_TIER5: '#166534',
  DEADHEAD: '#a78bfa',
  HOTEL: '#8b5cf6',
  TRANSPORT: '#7c3aed',
  CANCELLATION: '#f87171',
  APPR_COMPENSATION: '#ef4444',
  TERMINAL_PENALTY: '#b91c1c',
  // Exogenous, not a Stage-1/recourse cost like everything else here --
  // deliberately a visually distinct warm grey rather than a shade in
  // either family, so it doesn't read as belonging to the staffing/recourse
  // split this chart is otherwise organised around.
  DELAY_AMBIENT: '#a8a29e',
};
const FALLBACK_COLOR = '#94a3b8';
const categoryColor = (cat: string) => CATEGORY_COLORS[cat] ?? FALLBACK_COLOR;

// ---------------------------------------------------------------- Scoreboard
function ScoreboardTable({
  rows,
  onDrilldown,
}: {
  rows: ScoreboardRow[];
  onDrilldown: (policy: string) => void;
}) {
  const bestCost = useMemo(
    () => Math.min(...rows.map((r) => r.expected_cost ?? Infinity)),
    [rows],
  );
  const bestCvar = useMemo(() => Math.min(...rows.map((r) => r.cvar95 ?? Infinity)), [rows]);
  const sorted = useMemo(
    () => [...rows].sort((a, b) => (a.cvar95 ?? Infinity) - (b.cvar95 ?? Infinity)),
    [rows],
  );

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
        <thead>
          <tr>
            <th style={headStyle}>Policy</th>
            <th style={headStyle}>E[cost]</th>
            <th style={headStyle}>CVaR95</th>
            <th style={headStyle}>Uncovered legs/scn</th>
            <th style={headStyle} title="Service level: P(uncovered legs > u_max) <= epsilon">
              Service level
            </th>
            <th style={headStyle}>Eligibility</th>
            <th style={headStyle}>Cascade rate</th>
            <th style={headStyle} title="Reserve-days actually dispatched / reserve-days bought">
              Utilization
            </th>
            <th style={headStyle} />
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const sl = r.service_level;
            return (
              <Fragment key={r.policy}>
                <tr>
                  <td style={{ ...cellStyle, fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                    {r.policy}
                  </td>
                  <td
                    style={{
                      ...cellStyle,
                      fontWeight: r.expected_cost === bestCost ? 700 : 400,
                      color: r.expected_cost === bestCost ? 'var(--color-success-text)' : undefined,
                    }}
                  >
                    {money(r.expected_cost)}
                  </td>
                  <td
                    style={{
                      ...cellStyle,
                      fontWeight: r.cvar95 === bestCvar ? 700 : 400,
                      color: r.cvar95 === bestCvar ? 'var(--color-success-text)' : undefined,
                    }}
                  >
                    {money(r.cvar95)}
                    {r.cvar95 === bestCvar && (
                      <span style={{ marginLeft: 'var(--spacing-2)', fontSize: '0.75rem', fontWeight: 600 }}>
                        lowest tail risk
                      </span>
                    )}
                  </td>
                  <td style={cellStyle}>{r.uncovered == null ? '—' : r.uncovered.toFixed(1)}</td>
                  <td style={cellStyle}>
                    {sl == null ? (
                      <span style={smallMuted} title="No u_max/epsilon configured yet">
                        not evaluated
                      </span>
                    ) : (
                      <span
                        title={`P(uncovered > ${sl.u_max}) = ${pct(sl.p_uncovered_exceeds_u_max, 1)}, threshold ${pct(sl.epsilon, 1)}`}
                        style={{
                          padding: '0.15rem 0.5rem',
                          borderRadius: 'var(--radius-full)',
                          fontSize: '0.75rem',
                          fontWeight: 700,
                          backgroundColor: sl.service_level_met ? 'var(--color-success-bg)' : 'var(--color-error-bg)',
                          color: sl.service_level_met ? 'var(--color-success-text)' : 'var(--color-error-text)',
                        }}
                      >
                        {sl.service_level_met ? 'MEETS' : 'INFEASIBLE'}
                      </span>
                    )}
                  </td>
                  <td style={cellStyle}>{pct(r.elig)}</td>
                  <td style={cellStyle}>{pct(r.casc)}</td>
                  <td style={cellStyle}>
                    {r.utilization_rate == null ? (
                      '—'
                    ) : (
                      <span title={`${r.reserve_dispatches_mean?.toFixed(1)} dispatches / ${r.reserve_staffing_days_mean?.toFixed(0)} reserve-days bought (mean per scenario)`}>
                        {pct(r.utilization_rate)}
                      </span>
                    )}
                  </td>
                  <td style={cellStyle}>
                    <button
                      onClick={() => onDrilldown(r.policy)}
                      style={{
                        padding: '0.25rem 0.6rem',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        backgroundColor: 'transparent',
                        color: 'var(--color-primary-600)',
                        border: '1px solid var(--color-primary-600)',
                        borderRadius: 'var(--radius-sm)',
                        cursor: 'pointer',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      Why this R?
                    </button>
                  </td>
                </tr>
                <tr>
                  <td colSpan={9} style={{ ...cellStyle, ...smallMuted, fontFamily: 'var(--font-mono)', paddingTop: 0, paddingBottom: 'var(--spacing-2)' }}>
                    {r.policy_hash ? `policy ${r.policy_hash}` : ''}
                    {r.policy_hash && r.costs_version ? ' · ' : ''}
                    {r.costs_version ?? ''}
                  </td>
                </tr>
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ------------------------------------------------------------ Decomposition
function CostDecomposition({ rows }: { rows: ScoreboardRow[] }) {
  const [asTable, setAsTable] = useState(false);
  const withBreakdown = rows.filter((r) => r.cost_by_category);
  const categories = useMemo(() => {
    const set = new Set<string>();
    withBreakdown.forEach((r) => Object.keys(r.cost_by_category ?? {}).forEach((c) => set.add(c)));
    // Staffing first (the Stage-1, guaranteed part), then everything else
    // alphabetically -- so the "guaranteed cost vs. recourse cost" split
    // spec Sec1.1 frames is visually the base of the bar, not scattered.
    return Array.from(set).sort((a, b) => {
      if (a === 'RESERVE_STAFFING') return -1;
      if (b === 'RESERVE_STAFFING') return 1;
      return a.localeCompare(b);
    });
  }, [withBreakdown]);

  if (withBreakdown.length === 0 || categories.length === 0) return null;

  const hasAmbientDelay = categories.includes('DELAY_AMBIENT');
  const maxTotal = Math.max(
    ...withBreakdown.map((r) => Object.values(r.cost_by_category ?? {}).reduce((a, b) => a + b, 0)),
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-2)' }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>
          Cost decomposition (guaranteed staffing vs. recourse)
        </h3>
        <button
          onClick={() => setAsTable((v) => !v)}
          style={{
            fontSize: '0.75rem', padding: '0.25rem 0.6rem', borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-default)', backgroundColor: 'transparent', cursor: 'pointer',
          }}
        >
          {asTable ? 'Show as chart' : 'Show as table'}
        </button>
      </div>

      {hasAmbientDelay && (
        <p style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)', margin: '0 0 var(--spacing-2)' }}>
          <code>DELAY_AMBIENT</code> is real, calibrated ambient flight delay — but it doesn't vary
          by policy, so it's shown here and deliberately left out of E[C]/CVaR95 in the scoreboard
          above. This bar's total will therefore run higher than that row's E[C].
        </p>
      )}

      {!asTable && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
          {withBreakdown.map((r) => {
            const byCat = r.cost_by_category ?? {};
            const total = Object.values(byCat).reduce((a, b) => a + b, 0);
            return (
              <div key={r.policy}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '0.25rem' }}>
                  <strong style={{ fontFamily: 'var(--font-mono)' }}>{r.policy}</strong>
                  <span style={smallMuted}>{money(total)}</span>
                </div>
                <div style={{ display: 'flex', width: '100%', height: '20px', borderRadius: 'var(--radius-sm)', overflow: 'hidden', border: '1px solid var(--border-default)' }}>
                  {categories.map((cat) => {
                    const amt = byCat[cat] ?? 0;
                    if (amt <= 0) return null;
                    const widthPct = (amt / maxTotal) * 100;
                    return (
                      <div
                        key={cat}
                        title={`${cat}: ${money(amt)}`}
                        style={{ width: `${widthPct}%`, backgroundColor: categoryColor(cat), minWidth: amt > 0 ? '2px' : 0 }}
                      />
                    );
                  })}
                </div>
              </div>
            );
          })}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--spacing-3)', marginTop: 'var(--spacing-1)' }}>
            {categories.map((cat) => (
              <div key={cat} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.7rem', color: 'var(--color-neutral-600)' }}>
                <span style={{ width: '10px', height: '10px', borderRadius: '2px', backgroundColor: categoryColor(cat), display: 'inline-block' }} />
                {cat}
              </div>
            ))}
          </div>
        </div>
      )}

      {asTable && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ borderCollapse: 'collapse', fontSize: '0.8rem', width: '100%' }}>
            <thead>
              <tr>
                <th style={headStyle}>Policy</th>
                {categories.map((cat) => (
                  <th key={cat} style={{ ...headStyle, textAlign: 'right' }}>{cat}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {withBreakdown.map((r) => (
                <tr key={r.policy}>
                  <td style={{ ...cellStyle, fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{r.policy}</td>
                  {categories.map((cat) => (
                    <td key={cat} style={{ ...cellStyle, textAlign: 'right' }}>
                      {money(r.cost_by_category?.[cat] ?? 0)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// -------------------------------------------------------------- Validation
function ValidationBanner({ gate, verdict }: { gate: string; verdict: GateVerdict | null }) {
  if (!verdict) {
    return (
      <div
        style={{
          padding: 'var(--spacing-3) var(--spacing-4)',
          borderRadius: 'var(--radius-md)',
          backgroundColor: 'var(--surface-muted)',
          border: '1px dashed var(--border-default)',
          fontSize: '0.875rem',
          color: 'var(--color-neutral-600)',
        }}
      >
        Gate <GateBadge gate={gate} />: no events occurred in this run, so nothing was checked against
        the historical band.
      </div>
    );
  }
  const pass = verdict.pass;
  return (
    <div
      role={pass ? undefined : 'alert'}
      style={{
        padding: 'var(--spacing-4)',
        borderRadius: 'var(--radius-md)',
        backgroundColor: pass ? 'var(--color-success-bg)' : 'var(--color-error-bg)',
        color: pass ? 'var(--color-success-text)' : 'var(--color-error-text)',
        border: `1px solid ${pass ? 'var(--color-success-text)' : 'var(--color-error-text)'}`,
        fontSize: '0.875rem',
      }}
    >
      <strong>
        Gate <GateBadge gate={gate} />:{' '}
        {pass ? 'PASS' : verdict.verdict === 'INCONCLUSIVE' ? 'INCONCLUSIVE' : 'FAIL — these figures are UNVALIDATED'}
      </strong>
      <div style={{ marginTop: 'var(--spacing-2)' }}>{verdict.message}</div>
    </div>
  );
}

// ---------------------------------------------------------- Recommendation
const LAMBDA_LEGEND: { at: (lam: number) => boolean; label: string }[] = [
  { at: (lam) => lam === 0, label: 'risk-neutral: minimise average cost, accept tail exposure' },
  { at: (lam) => lam > 0 && lam < 1, label: 'balanced' },
  { at: (lam) => lam >= 1, label: 'prioritise stability through bad months' },
];
const lambdaHint = (lam: number) => LAMBDA_LEGEND.find((l) => l.at(lam))?.label ?? '';

function RecommendationPanel({ results }: { results: JobResults }) {
  const rec = results.recommendation;
  const anyFailed = (results.v3 != null && !results.v3.pass) || (results.v4 != null && !results.v4.pass);

  if (!rec) {
    const excludedRows = results.scoreboard.filter((r) => r.service_level && !r.service_level.service_level_met);
    const allInfeasible = results.scoreboard.length >= 2 && excludedRows.length === results.scoreboard.length;
    return (
      <div
        style={{
          padding: 'var(--spacing-4)',
          borderRadius: 'var(--radius-md)',
          backgroundColor: 'var(--surface-muted)',
          border: '1px dashed var(--border-default)',
          fontSize: '0.875rem',
          color: 'var(--color-neutral-600)',
        }}
      >
        {allInfeasible ? (
          <>
            <strong>No feasible recommendation.</strong> Every compared policy (
            {excludedRows.map((r) => r.policy).join(', ')}) fails the service-level constraint (see the
            Service level column below) — spec §7.5 requires the optimiser never propose an infeasible R.
            Run a wider policy set, or revisit the u_max/epsilon threshold with Crew Planning.
          </>
        ) : (
          <>
            No R* recommendation: fewer than 2 reserve-level (R…) policies with a feasible service level
            were compared in this run. Launch a batch run over at least two policies (e.g. R6 and R10) to
            get one.
          </>
        )}
      </div>
    );
  }

  const distinctRs = new Set(rec.curve.map((c) => c.recommended_r));

  return (
    <div
      style={{
        padding: 'var(--spacing-4)',
        borderRadius: 'var(--radius-md)',
        border: `1px solid ${anyFailed ? 'var(--color-error-text)' : 'var(--border-default)'}`,
        backgroundColor: anyFailed ? 'var(--color-error-bg)' : 'var(--surface-muted)',
      }}
    >
      {anyFailed && (
        <div style={{ marginBottom: 'var(--spacing-3)', fontWeight: 700, color: 'var(--color-error-text)', fontSize: '0.875rem' }}>
          A validation gate failed for this run (see above) — treat the recommendation below as
          unvalidated, not a number to act on directly.
        </div>
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: 'var(--spacing-2)' }}>
        <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>
          Recommended reserve level (R*), by risk tolerance
        </h3>
        <span
          style={{
            fontSize: '0.75rem', fontWeight: 700, padding: '0.2rem 0.6rem', borderRadius: 'var(--radius-full)',
            backgroundColor: rec.stable ? 'var(--color-success-bg)' : 'var(--color-warning-bg)',
            color: rec.stable ? 'var(--color-success-text)' : 'var(--color-warning-text)',
          }}
        >
          {rec.stable ? 'STABLE' : `UNSTABLE (R* varies by more than ${rec.instability_threshold} across lambda)`}
        </span>
      </div>
      <p style={{ fontSize: '0.8rem', color: 'var(--color-neutral-600)', marginTop: 'var(--spacing-1)' }}>
        argmin<sub>R</sub>[E[cost] + &lambda;&times;CVaR95], at terminal_penalty={rec.terminal_penalty}. Compares{' '}
        {rec.r_values_compared.join(', ')}
        {!rec.full_r_sweep && ' (not the full R4/R6/R8/R10/R14 sweep — run all five for the canonical curve)'}.
        {rec.excluded_infeasible_r.length > 0 && (
          <> Excluded as infeasible (service level): {rec.excluded_infeasible_r.join(', ')}.</>
        )}
      </p>
      <div style={{ overflowX: 'auto', marginTop: 'var(--spacing-3)' }}>
        <table style={{ borderCollapse: 'collapse', fontSize: '0.875rem' }}>
          <thead>
            <tr>
              {rec.curve.map((c) => (
                <th key={c.lambda} style={{ ...headStyle, textAlign: 'center' }} title={lambdaHint(c.lambda)}>
                  &lambda;={c.lambda}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              {rec.curve.map((c) => (
                <td key={c.lambda} style={{ ...cellStyle, textAlign: 'center', fontWeight: 700, fontSize: '1.25rem' }}>
                  R{c.recommended_r}
                </td>
              ))}
            </tr>
            <tr>
              {rec.curve.map((c) => (
                <td key={`${c.lambda}-hint`} style={{ ...cellStyle, textAlign: 'center', fontSize: '0.7rem', color: 'var(--color-neutral-500)' }}>
                  {lambdaHint(c.lambda)}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      {distinctRs.size === 1 && (
        <p style={{ fontSize: '0.8rem', color: 'var(--color-neutral-600)', marginTop: 'var(--spacing-2)' }}>
          R{[...distinctRs][0]} wins at every swept &lambda; here — risk tolerance does not change the
          answer for this comparison.
        </p>
      )}
    </div>
  );
}

// --------------------------------------------------------------- Gate grid
function GateStatusGrid({ gates }: { gates: GateRow[] }) {
  if (gates.length === 0) return null;
  const style = (verdict: string): React.CSSProperties => {
    const ok = verdict === 'PASS' || verdict === 'STABLE';
    const bad = verdict === 'FAIL' || verdict === 'UNSTABLE';
    return {
      backgroundColor: ok ? 'var(--color-success-bg)' : bad ? 'var(--color-error-bg)' : 'var(--surface-muted)',
      color: ok ? 'var(--color-success-text)' : bad ? 'var(--color-error-text)' : 'var(--color-neutral-600)',
      border: `1px solid ${ok ? 'var(--color-success-text)' : bad ? 'var(--color-error-text)' : 'var(--border-default)'}`,
    };
  };
  return (
    <div>
      <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 'var(--spacing-1)' }}>
        Gate status (V1–V9)
      </h3>
      <p style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)', marginTop: 0, marginBottom: 'var(--spacing-2)' }}>
        Click any gate for its full definition and pass criterion.
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 'var(--spacing-3)' }}>
        {gates.map((g) => (
          <div key={g.gate} style={{ ...style(g.verdict), borderRadius: 'var(--radius-md)', padding: 'var(--spacing-3)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--spacing-2)', fontWeight: 700, fontSize: '0.8125rem' }}>
              <GateBadge gate={g.gate} />
              <span style={{ flexShrink: 0 }}>{g.verdict}</span>
            </div>
            <div style={{ fontSize: '0.75rem', marginTop: '0.25rem', lineHeight: 1.4 }}>{g.detail}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ------------------------------------------------------------ Confirm flags
function ConfirmFlagsList({ markers }: { markers: ConfirmMarker[] }) {
  if (markers.length === 0) return null;
  return (
    <div>
      <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 'var(--spacing-2)' }}>
        Outstanding [CONFIRM:] flags ({markers.length})
      </h3>
      <p style={{ ...smallMuted, marginTop: 0, marginBottom: 'var(--spacing-2)' }}>
        Every result above depends on these unconfirmed values, scanned live from configs/base.yaml and
        costs_pilots.yaml.
      </p>
      <div style={{ maxHeight: '220px', overflowY: 'auto', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
          <thead>
            <tr>
              <th style={headStyle}>Owner</th>
              <th style={headStyle}>File:line</th>
              <th style={headStyle}>Context</th>
            </tr>
          </thead>
          <tbody>
            {markers.map((m, i) => (
              <tr key={i}>
                <td style={cellStyle}>{m.owner}</td>
                <td style={{ ...cellStyle, fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>
                  {m.file}:{m.line}
                </td>
                <td style={{ ...cellStyle, fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--color-neutral-600)' }}>
                  {m.context}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// --------------------------------------------------------------- Comparisons
function ComparisonsTable({ results }: { results: JobResults }) {
  if (results.comparisons.length === 0) return null;
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
        <thead>
          <tr>
            <th style={headStyle}>Comparison</th>
            <th style={headStyle}>Paired CRN difference</th>
            <th style={headStyle}>95% CI</th>
            <th style={headStyle}>t-stat</th>
          </tr>
        </thead>
        <tbody>
          {results.comparisons.map((c) => (
            <tr key={`${c.policy_a}-${c.policy_b}`}>
              <td style={{ ...cellStyle, fontFamily: 'var(--font-mono)' }}>
                {c.policy_b} &minus; {c.policy_a}
              </td>
              {c.evaluated ? (
                <>
                  <td style={{ ...cellStyle, fontWeight: 600 }}>{money(c.mean_diff)}</td>
                  <td style={cellStyle}>
                    [{money(c.ci_lower)}, {money(c.ci_upper)}]
                  </td>
                  <td style={cellStyle}>{c.t_stat?.toFixed(1)}</td>
                </>
              ) : (
                <td style={{ ...cellStyle, color: 'var(--color-neutral-500)' }} colSpan={3}>
                  not evaluated — {c.reason}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------- Drilldown
/** `${label}-${scenario_id}`, not scenario_id alone -- the same scenario_id
 *  can legitimately appear in both the costliest and typical groups when
 *  n_scenarios is small, and scenario_id alone can't tell those two rows
 *  apart. */
const drilldownKey = (s: { label: string; scenario_id: number }) => `${s.label}-${s.scenario_id}`;

function DrilldownModalContent({ data }: { data: DrilldownResults }) {
  const [openKey, setOpenKey] = useState<string | null>(
    data.scenarios[0] ? drilldownKey(data.scenarios[0]) : null,
  );
  return (
    <div>
      <p style={{ fontSize: '0.875rem', color: 'var(--color-neutral-600)' }}>
        Policy {data.policy}, season {data.season}. The 5 costliest and 5 most-typical (closest to the
        median cost) scenarios from the same CRN scenario set this policy's scoreboard row was computed
        from — every uncovered leg's cost traced back through root_event_uid to the sick call that caused
        it.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
        {data.scenarios.map((s) => {
          const key = drilldownKey(s);
          const isOpen = openKey === key;
          return (
            <div key={key} style={{ border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)' }}>
              <button
                onClick={() => setOpenKey(isOpen ? null : key)}
                style={{
                  width: '100%', textAlign: 'left', padding: 'var(--spacing-3)', backgroundColor: 'var(--surface-muted)',
                  border: 'none', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem', fontWeight: 600,
                }}
              >
                <span>
                  <span style={{
                    fontSize: '0.7rem', fontWeight: 700, marginRight: 'var(--spacing-2)', padding: '0.1rem 0.5rem',
                    borderRadius: 'var(--radius-full)', backgroundColor: s.label === 'costliest' ? 'var(--color-error-bg)' : 'var(--color-info-bg, var(--surface-muted))',
                    color: s.label === 'costliest' ? 'var(--color-error-text)' : 'var(--color-neutral-700)',
                  }}>
                    {s.label}
                  </span>
                  Scenario {s.scenario_id}
                </span>
                <span>{money(s.cost)}</span>
              </button>
              {isOpen && (
                <div style={{ padding: 'var(--spacing-3)' }}>
                  {s.chains.length > 0 ? (
                    <details style={{ marginBottom: 'var(--spacing-3)' }}>
                      <summary style={{ cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600 }}>
                        {s.chains.length} uncovered-leg causal chain(s)
                      </summary>
                      {s.chains.map((chain) => (
                        <div key={chain.root_event_uid} style={{ marginTop: 'var(--spacing-2)' }}>
                          <div style={{ fontSize: '0.8rem', fontWeight: 600 }}>
                            Root event {chain.root_event_uid} — {chain.rows.length} cost row(s)
                          </div>
                          <div style={{ overflowX: 'auto' }}>
                            <table style={{ borderCollapse: 'collapse', fontSize: '0.75rem', width: '100%' }}>
                              <thead>
                                <tr>
                                  <th style={headStyle}>sim_time</th>
                                  <th style={headStyle}>category</th>
                                  <th style={headStyle}>crew_id</th>
                                  <th style={headStyle}>amount</th>
                                </tr>
                              </thead>
                              <tbody>
                                {chain.rows.map((r, i) => (
                                  <tr key={i}>
                                    <td style={cellStyle}>{r.sim_time.toFixed(0)}</td>
                                    <td style={cellStyle}>{r.category}</td>
                                    <td style={cellStyle}>{r.crew_id ?? '—'}</td>
                                    <td style={cellStyle}>{money(r.amount)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      ))}
                    </details>
                  ) : (
                    <p style={smallMuted}>No uncovered legs in this scenario.</p>
                  )}
                  <details>
                    <summary style={{ cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600 }}>
                      Full event timeline ({s.trace.length} lines)
                    </summary>
                    <div style={{
                      maxHeight: '260px', overflowY: 'auto', fontFamily: 'var(--font-mono)', fontSize: '0.75rem',
                      backgroundColor: 'var(--chrome-bg)', color: 'var(--chrome-text-strong)', padding: 'var(--spacing-3)', borderRadius: 'var(--radius-sm)', marginTop: 'var(--spacing-2)',
                    }}>
                      {s.trace.map((line, i) => (
                        <div key={i}>{line}</div>
                      ))}
                    </div>
                  </details>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

type DrilldownState =
  | { phase: 'idle' }
  | { phase: 'launching'; policy: string }
  | { phase: 'running'; policy: string; jobId: string; log: string | null }
  | { phase: 'done'; policy: string; data: DrilldownResults }
  | { phase: 'error'; policy: string; message: string };

// ======================================================================
export function PolicyComparison() {
  const [summaries, setSummaries] = useState<RunSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [results, setResults] = useState<JobResults | null>(null);
  const [reportUrl, setReportUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drilldown, setDrilldown] = useState<DrilldownState>({ phase: 'idle' });
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const eligible = useMemo(() => summaries.filter((s) => s.has_comparison), [summaries]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, artifacts] = await Promise.all([fetchSummaries(), fetchArtifacts()]);
      setSummaries(list);
      const report = artifacts.find((a) => a.filename === 'policy_report.html');
      setReportUrl(report ? report.url : null);
      const first = list.find((s) => s.has_comparison);
      setSelectedId(first ? first.id : null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!selectedId) {
      setResults(null);
      return;
    }
    let cancelled = false;
    fetchJobDetail(selectedId)
      .then((detail) => {
        if (!cancelled) setResults(detail.results);
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const startDrilldown = useCallback(
    async (policy: string) => {
      if (!selectedId) return;
      setDrilldown({ phase: 'launching', policy });
      try {
        const { job_id } = await launchDrilldown(selectedId, policy);
        setDrilldown({ phase: 'running', policy, jobId: job_id, log: null });
      } catch (err) {
        setDrilldown({ phase: 'error', policy, message: errorMessage(err) });
      }
    },
    [selectedId],
  );

  // Poll the drill-down job until it reaches a terminal state. A dedicated
  // small poll rather than SSE: this is a short-lived, one-off job, not a
  // long batch run worth a persistent stream connection.
  useEffect(() => {
    if (drilldown.phase !== 'running') return;
    let cancelled = false;

    const tick = async () => {
      try {
        const detail = await fetchDrilldownJob(drilldown.jobId);
        if (cancelled) return;
        if (detail.status === 'completed' && detail.results) {
          setDrilldown({ phase: 'done', policy: drilldown.policy, data: detail.results });
        } else if (detail.status === 'failed') {
          setDrilldown({
            phase: 'error',
            policy: drilldown.policy,
            message: detail.error_message ?? 'Drill-down job failed.',
          });
        } else {
          pollTimer.current = setTimeout(tick, 1500);
        }
      } catch (err) {
        if (!cancelled) setDrilldown({ phase: 'error', policy: drilldown.policy, message: errorMessage(err) });
      }
    };
    pollTimer.current = setTimeout(tick, 800);
    return () => {
      cancelled = true;
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drilldown.phase === 'running' ? drilldown.jobId : null]);

  if (loading) return <Loading what="policy comparisons" />;
  if (error) return <ErrorPanel message={error} onRetry={() => void load()} />;

  if (eligible.length === 0) {
    return (
      <div className="card">
        <h2 style={{ marginBottom: 'var(--spacing-2)', fontSize: '1.25rem', fontWeight: 600 }}>
          Policy Comparison
        </h2>
        <p style={{ color: 'var(--color-neutral-500)', fontSize: '0.875rem' }}>
          No batch run has compared multiple policies yet. Launch a batch run from the Processing tab
          with two or more reserve-level policies (e.g. R6, R8, R10) to see a comparison and
          recommendation here.
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--spacing-3)', marginBottom: 'var(--spacing-4)' }}>
        <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600 }}>Policy Comparison</h2>
        {eligible.length > 1 && (
          <select
            value={selectedId ?? ''}
            onChange={(e) => setSelectedId(e.target.value)}
            style={{ padding: 'var(--spacing-2)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)' }}
          >
            {eligible.map((s) => (
              <option key={s.id} value={s.id}>
                {new Date(s.created_at).toLocaleString()} ({s.id.slice(0, 8)})
              </option>
            ))}
          </select>
        )}
      </div>

      {results && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-5)' }}>
          <p style={{ fontSize: '0.8rem', color: 'var(--color-neutral-500)', margin: 0 }}>
            {results.num_scenarios} CRN-paired scenario(s) &middot; season {results.season} &middot; master_seed=
            {results.master_seed} &middot; params {results.params_version} ({results.params_hash.slice(0, 16)}…)
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
            <ValidationBanner gate="V3" verdict={results.v3} />
            <ValidationBanner gate="V4" verdict={results.v4} />
          </div>

          <RecommendationPanel results={results} />

          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 'var(--spacing-2)' }}>Scoreboard</h3>
            <ScoreboardTable rows={results.scoreboard} onDrilldown={(p) => void startDrilldown(p)} />
          </div>

          <CostDecomposition rows={results.scoreboard} />

          <GateStatusGrid gates={results.gates} />

          <ConfirmFlagsList markers={results.confirm_markers} />

          {results.comparisons.length > 0 && (
            <div>
              <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 'var(--spacing-2)' }}>
                Pairwise paired-CRN comparisons
              </h3>
              <ComparisonsTable results={results} />
            </div>
          )}

          {reportUrl && (
            <div>
              <a
                href={reportUrl}
                target="_blank"
                rel="noreferrer"
                style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-primary-600)' }}
              >
                Open the full policy report (cost distributions, trade-off curve, lambda curve, gate
                status, drill-down) &rarr;
              </a>
            </div>
          )}
        </div>
      )}

      {drilldown.phase !== 'idle' && (
        <Modal title={`Why ${drilldown.policy}?`} onClose={() => setDrilldown({ phase: 'idle' })}>
          {(drilldown.phase === 'launching' || drilldown.phase === 'running') && (
            <Loading what="the exemplar scenario drill-down (this re-simulates with full tracing, so it takes longer than the scoreboard did)" />
          )}
          {drilldown.phase === 'error' && (
            <ErrorPanel message={drilldown.message} onRetry={() => void startDrilldown(drilldown.policy)} />
          )}
          {drilldown.phase === 'done' && <DrilldownModalContent data={drilldown.data} />}
        </Modal>
      )}
    </div>
  );
}
