import type { ComparisonsResponse, PolicySummary } from './api';
import { money, pct } from './api';
import { Callout, CASCADE_FG } from './CascadeCharts';

/**
 * Cascade behaviour across the policies in one grid run (WD-004).
 *
 * WD-004 asks for a warning when two runs used different seeds. That warning
 * is deliberately absent rather than faked: every row here comes from a single
 * grid job, and `run_grid` passes one master seed to every policy in it, so
 * the comparison is CRN-paired by construction. The basis is stated instead,
 * so a reader can see why the guarantee holds rather than inferring it from a
 * warning that never appears.
 */

const HEADERS: { key: string; label: string; hint: string; numeric: true }[] = [
  { key: 'expected_cost', label: 'E[cost]', hint: 'Mean measurement-window cost', numeric: true },
  { key: 'cvar95', label: 'CVaR95', hint: 'Mean of the worst 5% of scenarios', numeric: true },
  { key: 'rate', label: 'Cascade rate', hint: 'Share of drafts breaking a future pairing (whole simulation)', numeric: true },
  { key: 'affected', label: 'Scenarios hit', hint: 'Scenarios with at least one cascade', numeric: true },
  { key: 'amp', label: 'Amplification', hint: 'Cascaded chain cost / simple chain cost (measurement window)', numeric: true },
  { key: 'tier2', label: 'Tier-2 drafts', hint: 'The draft tier whose definition makes it a cascade candidate', numeric: true },
  { key: 'share', label: 'Cascade $ share', hint: 'Share of chain cost sitting in cascading chains', numeric: true },
];

const cell = (v: string, emphasis = false): React.ReactNode => (
  <span
    style={{
      fontVariantNumeric: 'tabular-nums',
      fontFamily: 'var(--font-mono)',
      fontSize: '0.8rem',
      color: emphasis ? CASCADE_FG : 'var(--color-text-base)',
      fontWeight: emphasis ? 600 : 400,
    }}
  >
    {v}
  </span>
);

const rowValues = (s: PolicySummary): Record<string, React.ReactNode> => {
  const a = s.analytics;
  if (!a) {
    const dash = cell('—');
    return { expected_cost: dash, cvar95: dash, rate: dash, affected: dash, amp: dash, tier2: dash, share: dash };
  }
  return {
    expected_cost: cell(s.expected_cost === null ? '—' : money(s.expected_cost)),
    cvar95: cell(s.cvar95 === null ? '—' : money(s.cvar95)),
    rate: cell(a.cascade_rate_mean === null ? 'no drafts' : pct(a.cascade_rate_mean, 2), (a.cascade_rate_mean ?? 0) > 0),
    affected: cell(`${a.n_scenarios_with_cascade}/${a.n_scenarios}`),
    amp: cell(a.amplification_ratio === null ? '—' : `${a.amplification_ratio.toFixed(1)}×`, a.amplification_ratio !== null),
    tier2: cell(String(a.tier_mix['DRAFT_TIER2'] ?? 0), (a.tier_mix['DRAFT_TIER2'] ?? 0) > 0),
    share: cell(
      a.share_of_chain_cost_from_cascades === null ? '—' : pct(a.share_of_chain_cost_from_cascades, 2),
    ),
  };
};

export const PolicyCascadeComparison: React.FC<{ data: ComparisonsResponse }> = ({ data }) => {
  const rows = data.comparisons;
  if (rows.length === 0) {
    return (
      <Callout tone="info" title="No policies in this run">
        This grid job produced no scoreboard rows to compare.
      </Callout>
    );
  }
  const anyCascade = rows.some((r) => (r.analytics?.cascading_drafts_total ?? 0) > 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
      <Callout tone="info" title="Paired comparison">
        {data.pairing_basis}
      </Callout>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '760px' }}>
          <thead>
            <tr>
              <th
                style={{
                  textAlign: 'left',
                  padding: 'var(--spacing-2) var(--spacing-3)',
                  borderBottom: '1px solid var(--border-default)',
                  fontSize: '0.72rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  color: 'var(--color-neutral-500)',
                  position: 'sticky',
                  left: 0,
                  backgroundColor: 'var(--surface-default)',
                }}
              >
                Policy
              </th>
              {HEADERS.map((h) => (
                <th
                  key={h.key}
                  title={h.hint}
                  style={{
                    textAlign: 'right',
                    padding: 'var(--spacing-2) var(--spacing-3)',
                    borderBottom: '1px solid var(--border-default)',
                    fontSize: '0.72rem',
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    color: 'var(--color-neutral-500)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {h.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => {
              const values = rowValues(s);
              return (
                <tr key={s.policy}>
                  <td
                    style={{
                      padding: 'var(--spacing-2) var(--spacing-3)',
                      borderBottom: '1px solid var(--border-subtle)',
                      fontWeight: 600,
                      fontSize: '0.85rem',
                      position: 'sticky',
                      left: 0,
                      backgroundColor: 'var(--surface-default)',
                    }}
                  >
                    {s.policy}
                    {!s.analytics && (
                      <div style={{ fontSize: '0.68rem', fontWeight: 400, color: 'var(--color-warning-text)' }}>
                        no cascade data — re-run
                      </div>
                    )}
                  </td>
                  {HEADERS.map((h) => (
                    <td
                      key={h.key}
                      style={{
                        padding: 'var(--spacing-2) var(--spacing-3)',
                        borderBottom: '1px solid var(--border-subtle)',
                        textAlign: 'right',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {values[h.key]}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {!anyCascade && (
        <Callout tone="info" title="No policy in this run produced a cascade">
          The reserve level does not change this on its own: cascades depend on whether drafting has to
          reach a crew member who holds a conflicting future pairing, and at this roster scale a
          day-off candidate is almost always available first. Compare the tier-2 column — it stays at
          zero alongside the cascade rate.
        </Callout>
      )}
    </div>
  );
};
