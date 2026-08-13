import { useState } from 'react';
import type { CascadeChain } from './api';
import { clockOf, money } from './api';
import { Callout, CASCADE_COLOR, CASCADE_FG, UNCOVERED_COLOR, UNCOVERED_FG } from './CascadeCharts';

/**
 * The costliest real cascade chains, row by row (WD-002 / WD-003).
 *
 * Every row here is an actual `CostLedger` entry, and every chain is the set
 * of rows sharing one `root_event_uid` -- the mechanism that lets a Thursday
 * cancellation be attributed to the Tuesday sick call that caused it. Nothing
 * is reconstructed from a template or interpolated between events.
 *
 * Rendered as an indented list rather than the zoom/pan timeline WD-002
 * describes: the ledger records each row's ROOT, never its immediate parent,
 * so the true tree shape is not recoverable from this data. Drawing a
 * node-edge graph would mean inventing the edges. Chronological order plus
 * the item id each row belongs to is what the data actually supports.
 */

// Text colours, so these are the theme-aware -fg tokens rather than the fixed
// graphical fills (see CascadeCharts for why the two differ).
const CATEGORY_TONE: Record<string, string> = {
  CANCELLATION: UNCOVERED_FG,
  TERMINAL_PENALTY: UNCOVERED_FG,
  DRAFT_TIER2: CASCADE_FG,
  DRAFT_TIER3: CASCADE_FG,
  DRAFT_TIER4: CASCADE_FG,
  DRAFT_TIER5: CASCADE_FG,
};

const ChainCard: React.FC<{ chain: CascadeChain & { policy?: string } }> = ({ chain }) => {
  const [open, setOpen] = useState(false);
  // The first item in the chain is its root cause; every other uid joined it
  // because a draft broke something. Numbering them by first appearance keeps
  // the "item N" labels short without implying a depth the ledger can't show.
  const itemOrder: number[] = [];
  for (const r of chain.rows) if (!itemOrder.includes(r.event_uid)) itemOrder.push(r.event_uid);

  return (
    <div
      style={{
        border: '1px solid var(--border-default)',
        borderLeft: `3px solid ${chain.uncovered ? UNCOVERED_COLOR : CASCADE_COLOR}`,
        borderRadius: 'var(--radius-md)',
        backgroundColor: 'var(--surface-default)',
        overflow: 'hidden',
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 'var(--spacing-3)',
          padding: 'var(--spacing-3) var(--spacing-4)',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
          color: 'var(--color-text-base)',
          font: 'inherit',
        }}
      >
        <span style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem', minWidth: 0 }}>
          <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>
            {money(chain.cost)}
            <span style={{ fontWeight: 400, color: 'var(--color-neutral-600)' }}>
              {' '}
              across {chain.n_items} open item{chain.n_items === 1 ? '' : 's'}
            </span>
          </span>
          <span
            style={{
              fontSize: '0.72rem',
              color: 'var(--color-neutral-500)',
              fontFamily: 'var(--font-mono)',
            }}
          >
            {chain.policy ? `${chain.policy} · ` : ''}scenario {chain.scenario_id} · root{' '}
            {chain.root_event_uid} · {clockOf(chain.start_minute)} → {clockOf(chain.end_minute)}
          </span>
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', flexShrink: 0 }}>
          {chain.uncovered && (
            <span
              style={{
                fontSize: '0.68rem',
                fontWeight: 600,
                padding: '0.15rem 0.45rem',
                borderRadius: 'var(--radius-full)',
                color: UNCOVERED_FG,
                border: `1px solid ${UNCOVERED_COLOR}`,
              }}
            >
              UNCOVERED
            </span>
          )}
          <span aria-hidden="true" style={{ color: 'var(--color-neutral-500)' }}>
            {open ? '▾' : '▸'}
          </span>
        </span>
      </button>

      {open && (
        <div style={{ borderTop: '1px solid var(--border-default)', padding: 'var(--spacing-3) var(--spacing-4)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.76rem', fontFamily: 'var(--font-mono)' }}>
            <thead>
              <tr style={{ color: 'var(--color-neutral-500)', textAlign: 'left' }}>
                <th style={{ padding: '0.25rem 0.5rem 0.4rem 0', fontWeight: 500 }}>when</th>
                <th style={{ padding: '0.25rem 0.5rem 0.4rem 0', fontWeight: 500 }}>item</th>
                <th style={{ padding: '0.25rem 0.5rem 0.4rem 0', fontWeight: 500 }}>what</th>
                <th style={{ padding: '0.25rem 0.5rem 0.4rem 0', fontWeight: 500 }}>crew</th>
                <th style={{ padding: '0.25rem 0 0.4rem 0.5rem', fontWeight: 500, textAlign: 'right' }}>
                  cost
                </th>
              </tr>
            </thead>
            <tbody>
              {chain.rows.map((r, i) => {
                // Indent anything that is not the chain's own root item: it
                // exists only because an earlier draft broke something.
                const isRoot = r.event_uid === chain.root_event_uid;
                return (
                  <tr key={`${r.event_uid}-${r.category}-${i}`} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '0.3rem 0.5rem 0.3rem 0', color: 'var(--color-neutral-600)', whiteSpace: 'nowrap' }}>
                      {clockOf(r.sim_time)}
                    </td>
                    <td style={{ padding: '0.3rem 0.5rem 0.3rem 0', color: 'var(--color-neutral-500)' }}>
                      {isRoot ? '' : '└ '}
                      {r.event_uid}
                    </td>
                    <td
                      style={{
                        padding: '0.3rem 0.5rem 0.3rem 0',
                        color: CATEGORY_TONE[r.category] ?? 'var(--color-text-base)',
                        fontWeight: CATEGORY_TONE[r.category] ? 600 : 400,
                      }}
                    >
                      {r.category}
                    </td>
                    <td style={{ padding: '0.3rem 0.5rem 0.3rem 0', color: 'var(--color-neutral-600)' }}>
                      {r.crew_id ?? '—'}
                    </td>
                    <td
                      style={{
                        padding: '0.3rem 0 0.3rem 0.5rem',
                        textAlign: 'right',
                        fontVariantNumeric: 'tabular-nums',
                        color: r.amount > 0 ? 'var(--color-text-base)' : 'var(--color-neutral-500)',
                      }}
                    >
                      {r.amount > 0 ? money(r.amount) : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p style={{ fontSize: '0.72rem', color: 'var(--color-neutral-500)', marginTop: 'var(--spacing-3)', lineHeight: 1.5 }}>
            {itemOrder.length} distinct open item{itemOrder.length === 1 ? '' : 's'} share this root.
            A <code>$0</code> row is an <code>OPEN_ITEM</code> marker — the item entering the queue,
            recorded so the chain has a visible start, not a cost.
          </p>
        </div>
      )}
    </div>
  );
};

export const ExemplarChains: React.FC<{
  drills: (CascadeChain & { policy: string })[];
  depthNote: string | null;
  totalChains?: number;
  truncated?: boolean;
}> = ({ drills, depthNote, totalChains, truncated }) => {
  if (drills.length === 0) {
    return (
      <Callout tone="info" title="No cascading chain in this run">
        Every disruption was absorbed where it landed — no draft broke a future pairing, so no chain
        grew past a single open item. There is nothing to drill into, which is a finding about the run
        rather than missing data. The Summaries tab shows the draft-tier mix that explains it.
      </Callout>
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
      <p style={{ fontSize: '0.82rem', color: 'var(--color-neutral-600)', lineHeight: 1.55, margin: 0 }}>
        The costliest chains in this run, most expensive first. Each is a real set of ledger rows
        sharing one <code>root_event_uid</code>; expand one to see every booking traced back to the
        disruption that started it.
      </p>
      {drills.map((d) => (
        <ChainCard key={`${d.policy}-${d.scenario_id}-${d.root_event_uid}`} chain={d} />
      ))}
      {truncated && (
        <p style={{ fontSize: '0.75rem', color: 'var(--color-neutral-600)', margin: 0 }}>
          Showing the {drills.length} costliest of {totalChains?.toLocaleString()} chains across every
          policy in this run. Use the per-policy Summary tab to see one policy's own chains.
        </p>
      )}
      {depthNote && (
        <p style={{ fontSize: '0.72rem', color: 'var(--color-neutral-500)', lineHeight: 1.5, marginTop: 'var(--spacing-2)' }}>
          {depthNote}
        </p>
      )}
    </div>
  );
};
