import { useState } from 'react';
import { Modal } from '../../components/Modal';

/**
 * The policy scoreboard: the five figures a planner compares policies on,
 * the paired CRN difference between them, and gate V3's verdict on whether any
 * of it is validated.
 *
 * The V3 line is not decoration. S1c-05's acceptance criterion is that "a
 * number failing V3 must never reach a planner silently", and `crewsim run`
 * prints the same verdict for the same reason. It fails by design against the
 * mock corpus, so it will usually be showing -- that is the correct behaviour,
 * not a bug to suppress.
 */

export interface ScoreboardRow {
  policy: string;
  policy_id: string | null;
  policy_hash: string | null;
  expected_cost: number | null;
  cvar95: number | null;
  elig: number | null;
  casc: number | null;
  uncovered: number | null;
}

export interface Comparison {
  policy_a: string;
  policy_b: string;
  summary: string;
  evaluated: boolean;
}

export interface V3Verdict {
  pass: boolean;
  sim_mean: number;
  ci_lower: number;
  ci_upper: number;
  n_events: number;
  message: string;
}

export interface JobResults {
  scoreboard: ScoreboardRow[];
  comparisons: Comparison[];
  v3: V3Verdict | null;
  num_scenarios: number;
  season: string;
  master_seed: string;
  params_version: string;
  params_hash: string;
}

const DASH = '—';

/**
 * What each scoreboard column means, in the terms a planner decides on.
 *
 * Every definition here describes what `reporting/kpis.py::compute_kpis`
 * actually computes -- the measurement window, the CVaR tail fraction and the
 * "n/a rather than 0" rule are properties of that code, not of this panel.
 */
const METRICS: { key: string; title: string; body: React.ReactNode }[] = [
  {
    key: 'expected_cost',
    title: 'E[C] — Expected Cost',
    body: (
      <>
        The <strong>mean</strong> total cost per scenario over the measurement window: reserve
        staffing, draft premiums, cancellations and terminal penalties, averaged across every CRN
        scenario in the run.
        <br />
        This is the "typical month" figure. It is the number to compare policies on when you care
        about the long-run bill — and the one that hides the bad months, which is what CVaR95 is
        for.
      </>
    ),
  },
  {
    key: 'cvar95',
    title: 'CVaR95 — Worst-Case Cost',
    body: (
      <>
        The mean cost of the <strong>worst 5%</strong> of scenarios — not the 95th percentile
        itself, but the average of everything beyond it.
        <br />
        A policy can have an attractive E[C] and a punishing CVaR95: cheap most months, ruinous in
        the bad ones. If the operation cannot absorb the tail, this is the column that decides.
      </>
    ),
  },
  {
    key: 'elig',
    title: 'elig — Eligibility Rate',
    body: (
      <>
        The mean fraction of the reserve pool that is <strong>legally available</strong> at the
        moment cover is needed — after duty limits, rest, and notice rules (L0–L8) have removed
        everyone who cannot legally take the assignment.
        <br />
        A low value means reserves exist on paper but not in practice. Gate V3 validates this
        against the historical band; the banner below the table tells you whether it passed.
      </>
    ),
  },
  {
    key: 'casc',
    title: 'casc — Cascading Draft Rate',
    body: (
      <>
        The fraction of drafts that <strong>caused a further draft</strong> — covering one hole
        opened another.
        <br />
        Cascades are how a small shortfall becomes a large one. A policy with a similar cost but a
        lower cascade rate is the more stable operation.
      </>
    ),
  },
  {
    key: 'uncovered',
    title: 'uncovered — Uncovered Legs per Scenario',
    body: (
      <>
        The mean number of legs per scenario that were <strong>never covered</strong>: an item that
        hit its own deadline (a cancellation) or was still open when the horizon ended.
        <br />
        This is the service-failure count. Cost figures already price these through the
        cancellation and terminal-penalty terms, so read it alongside E[C] rather than instead of
        it.
      </>
    ),
  },
];

const MetricsHelpModal: React.FC<{ onClose: () => void }> = ({ onClose }) => (
  <Modal title="Reading the scoreboard" onClose={onClose}>
    <p style={{ marginTop: 0 }}>
      Each row is one policy, run over the <em>same</em> CRN scenario set, so differences between
      rows reflect the policy rather than draw luck. Every figure is measured over the measurement
      window only — warm-up is excluded.
    </p>
    {METRICS.map((m) => (
      <div key={m.key} style={{ marginTop: 'var(--spacing-5, 1.25rem)' }}>
        <h3
          style={{
            fontSize: '0.95rem',
            fontWeight: 700,
            marginBottom: 'var(--spacing-1)',
            color: 'var(--color-primary-700, #1d4ed8)',
          }}
        >
          {m.title}
        </h3>
        <div style={{ fontSize: '0.875rem', lineHeight: 1.6 }}>{m.body}</div>
      </div>
    ))}
    <p
      style={{
        marginTop: 'var(--spacing-5, 1.25rem)',
        fontSize: '0.8125rem',
        color: 'var(--color-neutral-600)',
      }}
    >
      <strong>n/a</strong> is not zero. Eligibility and cascade rate are reported as n/a when a run
      produced no such events at all — no eligibility decisions, or no drafts to cascade from.
    </p>
  </Modal>
);

/** `compute_kpis` returns null for eligibility and cascade rate when the run
 *  produced no such events. Render that as "n/a", never as 0. */
const money = (v: number | null) => (v === null ? DASH : `$${Math.round(v).toLocaleString()}`);
const ratio = (v: number | null) => (v === null ? 'n/a' : v.toFixed(2));
const count = (v: number | null) => (v === null ? DASH : v.toFixed(1));

const th: React.CSSProperties = {
  textAlign: 'right',
  padding: '0.5rem 0.75rem',
  fontSize: '0.75rem',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  color: 'var(--color-neutral-500)',
  borderBottom: '1px solid var(--border-default)',
  whiteSpace: 'nowrap',
};

const td: React.CSSProperties = {
  textAlign: 'right',
  padding: '0.5rem 0.75rem',
  fontFamily: 'var(--font-mono, ui-monospace, monospace)',
  fontSize: '0.875rem',
  borderBottom: '1px solid var(--border-subtle, rgba(0,0,0,0.06))',
  whiteSpace: 'nowrap',
};

export const Scoreboard: React.FC<{ results: JobResults }> = ({ results }) => {
  const [helpOpen, setHelpOpen] = useState(false);

  return (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
    <div
      style={{
        display: 'flex',
        gap: 'var(--spacing-4)',
        flexWrap: 'wrap',
        fontSize: '0.75rem',
        color: 'var(--color-neutral-500)',
      }}
    >
      <span>{results.num_scenarios} CRN scenarios</span>
      <span>season {results.season}</span>
      <span>seed {results.master_seed}</span>
      <span>
        params {results.params_version}
        {results.params_version !== 'MISSING' && results.params_hash
          ? ` (${results.params_hash.slice(0, 16)}…)`
          : ''}
      </span>
    </div>

    <div style={{ overflowX: 'auto' }}>
      <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: '640px' }}>
        <thead>
          <tr>
            <th style={{ ...th, textAlign: 'left' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                Policy
                <button
                  type="button"
                  onClick={() => setHelpOpen(true)}
                  aria-label="What do these columns mean?"
                  title="What do these columns mean?"
                  style={{
                    background: 'var(--color-neutral-200)',
                    border: 'none',
                    borderRadius: '50%',
                    width: '16px',
                    height: '16px',
                    fontSize: '0.65rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    color: 'var(--color-neutral-700)',
                    lineHeight: 1,
                  }}
                >
                  ?
                </button>
              </span>
            </th>
            <th style={th} title="Expected cost over the measurement window">
              E[C]
            </th>
            <th style={th} title="Worst-case cost: mean of the worst 5% of scenarios">
              CVaR95
            </th>
            <th style={th} title="Mean eligibility rate">
              elig
            </th>
            <th style={th} title="Cascading draft rate">
              casc
            </th>
            <th style={th} title="Uncovered legs per scenario">
              uncovered
            </th>
          </tr>
        </thead>
        <tbody>
          {results.scoreboard.map((row) => (
            <tr key={row.policy}>
              <td
                style={{ ...td, textAlign: 'left' }}
                title={row.policy_hash ? `policy hash ${row.policy_hash}` : undefined}
              >
                {row.policy_id ?? row.policy}
              </td>
              <td style={td}>{money(row.expected_cost)}</td>
              <td style={td}>{money(row.cvar95)}</td>
              <td style={td}>{ratio(row.elig)}</td>
              <td style={td}>{ratio(row.casc)}</td>
              <td style={td}>{count(row.uncovered)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>

    {results.comparisons.length > 0 && (
      <div
        style={{
          fontFamily: 'var(--font-mono, ui-monospace, monospace)',
          fontSize: '0.8125rem',
          color: 'var(--color-neutral-700)',
        }}
      >
        {results.comparisons.map((c) => (
          <div key={`${c.policy_a}-${c.policy_b}`}>{c.summary}</div>
        ))}
      </div>
    )}

    {results.v3 && (
      <div
        role={results.v3.pass ? undefined : 'alert'}
        style={{
          fontSize: '0.8125rem',
          padding: 'var(--spacing-2) var(--spacing-3)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid',
          borderColor: results.v3.pass ? 'var(--color-success-text)' : 'var(--color-error-text)',
          backgroundColor: results.v3.pass ? 'var(--color-success-bg)' : 'var(--color-error-bg)',
          color: results.v3.pass ? 'var(--color-success-text)' : 'var(--color-error-text)',
        }}
      >
        {results.v3.pass ? '' : '⚠ '}
        {results.v3.message}
      </div>
    )}

    {helpOpen && <MetricsHelpModal onClose={() => setHelpOpen(false)} />}
  </div>
  );
};
