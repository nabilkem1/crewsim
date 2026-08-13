import type { CascadeAnalytics, PolicySummary } from './api';
import { money, pct } from './api';
import { AmplificationBars, BarRow, Callout, CASCADE_COLOR, KpiCard, ScenarioRateStrip } from './CascadeCharts';

/**
 * The cascade summary for one policy (WD-001).
 *
 * The order of this page is the argument it makes, so it is deliberate:
 * amplification first (what a cascade costs once it happens), then frequency
 * (how often that is), then the mechanism (which draft tier produces it).
 * Reversing that -- rate first -- is what makes a rare, expensive tail look
 * like a rounding error.
 */

const TIER_HINT: Record<string, string> = {
  DRAFT_TIER1: 'day off — no future trip to break',
  DRAFT_TIER2: 'holds a conflicting future pairing — the cascade tier',
  DRAFT_TIER3: 'on a scheduled trip',
  DRAFT_TIER4: 'vacation',
  DRAFT_TIER5: 'simulator / training',
};

export const CascadeSummary: React.FC<{ summary: PolicySummary }> = ({ summary }) => {
  const a: CascadeAnalytics | null = summary.analytics;

  if (!a) {
    return (
      <Callout tone="warn" title="No cascade data on this run">
        This run completed before cascade analytics existed, so it carries no chain data. Re-run the
        policy grid from Processing to populate it. This is <em>not</em> the same as a run in which no
        cascades occurred — that case shows measured zeros below instead.
      </Callout>
    );
  }

  const noCascades = a.n_cascading_chains === 0 && a.cascading_drafts_total === 0;
  const sizeEntries = Object.entries(a.chain_size_histogram);
  const sizeMax = Math.max(...sizeEntries.map(([, v]) => v), 1);
  const tierEntries = Object.entries(a.tier_mix).sort(([x], [y]) => x.localeCompare(y));
  const tierMax = Math.max(...tierEntries.map(([, v]) => v), 1);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-6)' }}>
      {noCascades ? (
        <Callout tone="info" title="No cascade fired in this run — a measured result, not missing data">
          Across {a.n_scenarios} scenario{a.n_scenarios === 1 ? '' : 's'} and{' '}
          {a.drafts_total.toLocaleString()} draft{a.drafts_total === 1 ? '' : 's'}, none broke a future
          pairing. At this roster scale a tier-1 candidate (someone on a day off, with no future trip to
          ruin) is almost always available, so drafting rarely has to reach the tier that cascades. The
          draft-tier mix below is the leading indicator: cascades stay near zero for as long as
          <code> DRAFT_TIER2</code> does.
        </Callout>
      ) : (
        <section aria-label="Cascade amplification">
          <h3 style={{ fontSize: '0.95rem', marginBottom: 'var(--spacing-1)' }}>
            What a cascade costs
          </h3>
          <p style={{ fontSize: '0.8rem', color: 'var(--color-neutral-600)', marginBottom: 'var(--spacing-3)', lineHeight: 1.5 }}>
            A disruption that is absorbed where it lands against one that breaks something else. This is
            the whole argument for an event-level ledger: the second is not visible at all in a model
            that prices a draft and stops there.
          </p>
          <AmplificationBars
            simple={a.mean_cost_simple_chain}
            cascading={a.mean_cost_cascading_chain}
            format={money}
          />
        </section>
      )}

      <section aria-label="Key cascade indicators">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))',
            gap: 'var(--spacing-3)',
          }}
        >
          <KpiCard
            label="Amplification"
            value={a.amplification_ratio === null ? 'not observed' : `${a.amplification_ratio.toFixed(1)}×`}
            basis="measurement window"
            emphasis={a.amplification_ratio !== null}
            hint="Mean cost of a chain that cascaded, over one that did not."
          />
          <KpiCard
            label="Cascade rate"
            value={a.cascade_rate_mean === null ? 'no drafts' : pct(a.cascade_rate_mean, 2)}
            basis="whole simulation"
            hint={`Share of drafts that broke a future pairing. Peak scenario ${
              a.cascade_rate_max === null ? 'n/a' : pct(a.cascade_rate_max, 2)
            }.`}
          />
          <KpiCard
            label="Scenarios affected"
            value={`${a.n_scenarios_with_cascade} / ${a.n_scenarios}`}
            basis="whole simulation"
            hint={
              a.share_of_scenarios_with_cascade === null
                ? undefined
                : `${pct(a.share_of_scenarios_with_cascade, 0)} of scenarios saw any cascade at all.`
            }
          />
          <KpiCard
            label="Cascading chains"
            value={`${a.n_cascading_chains.toLocaleString()} / ${a.n_chains.toLocaleString()}`}
            basis="measurement window"
            hint={
              a.share_of_chain_cost_from_cascades === null
                ? undefined
                : `${pct(a.share_of_chain_cost_from_cascades, 1)} of all chain cost (${money(
                    a.cascading_chain_cost_total,
                  )}).`
            }
          />
        </div>
      </section>

      <section aria-label="Cascade rate by scenario">
        <h3 style={{ fontSize: '0.95rem', marginBottom: 'var(--spacing-1)' }}>
          Where the cascades actually happened
        </h3>
        <p style={{ fontSize: '0.8rem', color: 'var(--color-neutral-600)', marginBottom: 'var(--spacing-3)', lineHeight: 1.5 }}>
          One bar per scenario.{' '}
          {a.n_scenarios_with_cascade === 0
            ? 'No scenario in this run produced one.'
            : `In this run they fell in ${a.n_scenarios_with_cascade} of ${a.n_scenarios} scenario${
                a.n_scenarios === 1 ? '' : 's'
              }, so the mean above describes almost no individual month.`}{' '}
          Whether that concentration is a property of the mechanism or of this seed takes more runs to
          say — the shape is shown rather than summarised so the question stays visible.
        </p>
        <ScenarioRateStrip rows={a.per_scenario} />
      </section>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: 'var(--spacing-6)',
        }}
      >
        <section aria-label="Chain size distribution">
          <h3 style={{ fontSize: '0.95rem', marginBottom: 'var(--spacing-1)' }}>Chain size</h3>
          <p style={{ fontSize: '0.78rem', color: 'var(--color-neutral-600)', marginBottom: 'var(--spacing-3)', lineHeight: 1.5 }}>
            Open items sharing one root cause. Size 1 means the absence was covered where it landed.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
            {sizeEntries.map(([size, count]) => (
              <BarRow
                key={size}
                label={`${size} item${size === '1' ? '' : 's'}`}
                value={count}
                max={sizeMax}
                color={size === '1' ? 'var(--color-neutral-400)' : CASCADE_COLOR}
                title={
                  size === '1'
                    ? 'Absorbed where it landed — no cascade'
                    : `A chain that grew to ${size} open items`
                }
              />
            ))}
          </div>
          <p style={{ fontSize: '0.72rem', color: 'var(--color-neutral-500)', marginTop: 'var(--spacing-3)', lineHeight: 1.5 }}>
            {a.depth_note}
          </p>
        </section>

        <section aria-label="Draft tier mix">
          <h3 style={{ fontSize: '0.95rem', marginBottom: 'var(--spacing-1)' }}>
            Draft tier mix — the lever
          </h3>
          <p style={{ fontSize: '0.78rem', color: 'var(--color-neutral-600)', marginBottom: 'var(--spacing-3)', lineHeight: 1.5 }}>
            Tier 2 is defined as “holds a conflicting future pairing”, so it is the tier whose own
            definition makes it a cascade candidate. Its share is the leading indicator for the rate
            above.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
            {tierEntries.length === 0 ? (
              <span style={{ fontSize: '0.8rem', color: 'var(--color-neutral-500)' }}>
                No draft was booked inside the measurement window.
              </span>
            ) : (
              tierEntries.map(([tier, count]) => (
                <BarRow
                  key={tier}
                  label={tier.replace('DRAFT_', '')}
                  value={count}
                  max={tierMax}
                  color={tier === 'DRAFT_TIER2' ? CASCADE_COLOR : 'var(--color-primary-600)'}
                  title={TIER_HINT[tier] ?? tier}
                />
              ))
            )}
          </div>
        </section>
      </div>

      <section aria-label="Reserve-loss cascades">
        <Callout tone="info" title={`Reserve-loss cascades: ${a.reserve_loss_cascades} (${a.reserve_blocks_lost} blocks lost)`}>
          {a.reserve_loss_note}
        </Callout>
      </section>

      {a.n_uncovered_chains > 0 && (
        <Callout tone="warn" title={`${a.n_uncovered_chains} chain(s) ended uncovered`}>
          These reached a cancellation or a terminal penalty rather than being covered. They are the
          costliest outcome in the ledger and are listed first under Exemplar Chains.
        </Callout>
      )}
    </div>
  );
};
