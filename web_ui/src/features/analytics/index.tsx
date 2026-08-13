import { useCallback, useEffect, useState } from 'react';
import { apiFetch, errorMessage } from '../../api/client';
import { ErrorPanel, Loading } from '../../components/StatusPanel';
import type { ComparisonsResponse, DrillsResponse, SummariesResponse } from './api';
import { CascadeSummary } from './CascadeSummary';
import { Callout } from './CascadeCharts';
import { ExemplarChains } from './ExemplarChains';
import { PolicyCascadeComparison } from './PolicyCascadeComparison';

/**
 * Cascade analytics.
 *
 * This view used to call three endpoints at the wrong paths, get a 404 from
 * each, and then render hardcoded "Mock Recovery" / "Mock Policy A" rows from
 * a catch block -- so a tab whose every request failed still looked like a
 * working dashboard. The endpoints were then emptied rather than filled in,
 * because the figures behind them had never come from the cascade engine.
 *
 * They are real now. Everything on this page is computed by
 * `reporting/cascade_analytics.py` from actual `CostLedger` rows during a
 * policy-grid run, and read back from that job -- no figure here is produced
 * by this component, and none is produced on request.
 *
 * The page reads a COMPLETED grid job. That is not a limitation to work
 * around: it is what keeps the cascade figures and the E[C] shown beside them
 * drawn from the same CRN scenario set, rather than two independent samples
 * that would disagree for reasons nobody could see.
 */

type Tab = 'summaries' | 'drills' | 'comparisons';

const TABS: { id: Tab; label: string; path: string }[] = [
  { id: 'summaries', label: 'Summary', path: '/analytics/cascade-summaries' },
  { id: 'drills', label: 'Exemplar Chains', path: '/analytics/exemplar-drills' },
  { id: 'comparisons', label: 'Policy Comparison', path: '/analytics/cascade-policy-comparisons' },
];

type Payload = SummariesResponse | DrillsResponse | ComparisonsResponse;

export const AnalyticsDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('summaries');
  const [payload, setPayload] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [policyIndex, setPolicyIndex] = useState(0);

  const active = TABS.find((t) => t.id === activeTab)!;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setPayload(null);
    try {
      setPayload(await apiFetch<Payload>(active.path));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [active.path]);

  useEffect(() => {
    void load();
  }, [load]);

  const summaries = payload && 'summaries' in payload ? payload.summaries : null;
  const selected = summaries?.[Math.min(policyIndex, summaries.length - 1)] ?? null;

  return (
    <div className="card">
      <div style={{ marginBottom: 'var(--spacing-4)' }}>
        <h2 style={{ marginBottom: '0.25rem' }}>Cascade Analytics</h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--color-neutral-600)', lineHeight: 1.55, margin: 0, maxWidth: '68ch' }}>
          A draft does not end when it is paid for. If the crew member drafted today held a trip
          tomorrow, that trip breaks, re-enters as open time, and has to be covered again. This page
          prices that chain from the ledger — the difference between what a disruption costs and what a
          draft costs.
        </p>
      </div>

      {payload && (
        <div
          style={{
            fontSize: '0.72rem',
            fontFamily: 'var(--font-mono)',
            color: 'var(--color-neutral-500)',
            marginBottom: 'var(--spacing-4)',
          }}
        >
          run {payload.job_id.slice(0, 8)} · {payload.num_scenarios ?? '?'} scenarios ·{' '}
          {payload.season ?? 'season n/a'} · {new Date(payload.created_at).toLocaleString()}
        </div>
      )}

      <div
        role="tablist"
        aria-label="Cascade analytics sections"
        style={{
          display: 'flex',
          gap: '0.5rem',
          marginBottom: 'var(--spacing-5)',
          borderBottom: '1px solid var(--border-default)',
          paddingBottom: 'var(--spacing-3)',
          flexWrap: 'wrap',
        }}
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            onClick={() => setActiveTab(tab.id)}
            aria-selected={activeTab === tab.id}
            style={{
              padding: '0.5rem 1rem',
              borderRadius: 'var(--radius-md)',
              cursor: 'pointer',
              fontWeight: 500,
              fontSize: '0.85rem',
              border: activeTab === tab.id ? 'none' : '1px solid var(--border-default)',
              backgroundColor: activeTab === tab.id ? 'var(--color-primary-600)' : 'transparent',
              color: activeTab === tab.id ? 'white' : 'var(--color-text-base)',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading && <Loading what="cascade analytics" />}
      {!loading && error && <ErrorPanel message={error} onRetry={() => void load()} />}

      {!loading && !error && payload && (
        <>
          {'notice' in payload && payload.notice && (
            <div style={{ marginBottom: 'var(--spacing-4)' }}>
              <Callout tone="warn" title="Some policies carry no cascade data">
                {payload.notice}
              </Callout>
            </div>
          )}

          {activeTab === 'summaries' && summaries && (
            <>
              {summaries.length > 1 && (
                <div
                  style={{
                    display: 'flex',
                    gap: '0.4rem',
                    marginBottom: 'var(--spacing-4)',
                    flexWrap: 'wrap',
                    alignItems: 'center',
                  }}
                >
                  <span style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)' }}>Policy:</span>
                  {summaries.map((s, i) => (
                    <button
                      key={s.policy}
                      type="button"
                      onClick={() => setPolicyIndex(i)}
                      aria-pressed={i === policyIndex}
                      style={{
                        padding: '0.25rem 0.7rem',
                        borderRadius: 'var(--radius-full)',
                        fontSize: '0.78rem',
                        cursor: 'pointer',
                        border: '1px solid var(--border-default)',
                        backgroundColor:
                          i === policyIndex ? 'var(--color-primary-600)' : 'transparent',
                        color: i === policyIndex ? 'white' : 'var(--color-text-base)',
                      }}
                    >
                      {s.policy}
                    </button>
                  ))}
                </div>
              )}
              {selected ? (
                <CascadeSummary summary={selected} />
              ) : (
                <Callout tone="info" title="No policies in this run">
                  This grid job produced no scoreboard rows.
                </Callout>
              )}
            </>
          )}

          {activeTab === 'drills' && 'drills' in payload && (
            <ExemplarChains
              drills={payload.drills}
              depthNote={payload.depth_note}
              totalChains={payload.total_chains}
              truncated={payload.truncated}
            />
          )}

          {activeTab === 'comparisons' && 'comparisons' in payload && (
            <PolicyCascadeComparison data={payload} />
          )}
        </>
      )}
    </div>
  );
};
