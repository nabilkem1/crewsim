import { useCallback, useEffect, useState } from 'react';
import { apiFetch, errorMessage } from '../../api/client';
import { ErrorPanel, Loading } from '../../components/StatusPanel';
import { DataGrid } from './DataGrid';
import { DataQualityDashboard } from './DataQualityDashboard';

export { DataGrid } from './DataGrid';
export { DataQualityDashboard } from './DataQualityDashboard';

/**
 * The D1-D12 corpus.
 *
 * Tables on the left, the selected one in a grid on the right. The list comes
 * from `loaders.DATASET_SCHEMAS` via the API rather than a directory listing,
 * so a dataset that has not been extracted yet shows as **missing** instead of
 * simply not appearing -- the difference between "there is no such table" and
 * "this table has no data" is one a planner needs to see.
 */

interface DatasetInfo {
  name: string;
  columns: string[];
  present: boolean;
  tabular: boolean;
  note?: string;
}

type Tab = 'tables' | 'quality';

export const DataDashboard: React.FC = () => {
  const [tab, setTab] = useState<Tab>('tables');
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<{ datasets: DatasetInfo[] }>('/data/datasets');
      setDatasets(data.datasets);
      const first = data.datasets.find((d) => d.tabular && d.present);
      setSelected((cur) => cur ?? first?.name ?? null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const active = datasets.find((d) => d.name === selected) ?? null;

  const tabBtn = (id: Tab, label: string) => (
    <button
      key={id}
      onClick={() => setTab(id)}
      style={{
        padding: 'var(--spacing-2) var(--spacing-4)',
        backgroundColor: tab === id ? 'var(--color-primary-600)' : 'transparent',
        color: tab === id ? 'white' : 'var(--color-text-base)',
        border: tab === id ? 'none' : '1px solid var(--border-default)',
        borderRadius: 'var(--radius-md)',
        fontWeight: 500,
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
      <div
        style={{
          display: 'flex',
          gap: 'var(--spacing-4)',
          borderBottom: '1px solid var(--border-default)',
          paddingBottom: 'var(--spacing-2)',
        }}
      >
        {tabBtn('tables', 'Corpus Tables')}
        {tabBtn('quality', 'Data Quality')}
      </div>

      {tab === 'quality' && <DataQualityDashboard />}

      {tab === 'tables' && (
        <>
          {loading && <Loading what="the corpus" />}
          {error && <ErrorPanel message={error} onRetry={() => void load()} />}

          {!loading && !error && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(200px, 240px) minmax(0, 1fr)',
                gap: 'var(--spacing-4)',
                alignItems: 'start',
              }}
            >
              <nav
                className="card"
                aria-label="Corpus tables"
                style={{ padding: 'var(--spacing-2)', display: 'flex', flexDirection: 'column', gap: '2px' }}
              >
                {datasets.map((d) => {
                  const selectable = d.tabular && d.present;
                  const isActive = d.name === selected;
                  return (
                    <button
                      key={d.name}
                      onClick={() => selectable && setSelected(d.name)}
                      disabled={!selectable}
                      aria-current={isActive}
                      title={d.present ? undefined : 'Not present in the configured corpus'}
                      style={{
                        textAlign: 'left',
                        padding: '0.45rem 0.6rem',
                        borderRadius: 'var(--radius-sm)',
                        border: 'none',
                        background: isActive ? 'var(--color-primary-50, #eff6ff)' : 'transparent',
                        color: selectable
                          ? isActive
                            ? 'var(--color-primary-700, #1d4ed8)'
                            : 'var(--color-text-base)'
                          : 'var(--color-neutral-400, #9ca3af)',
                        fontWeight: isActive ? 600 : 400,
                        cursor: selectable ? 'pointer' : 'not-allowed',
                        fontFamily: 'var(--font-mono, ui-monospace, monospace)',
                        fontSize: '0.8125rem',
                      }}
                    >
                      {d.name}
                      {!d.present && (
                        <span style={{ display: 'block', fontSize: '0.7rem' }}>missing</span>
                      )}
                      {d.present && !d.tabular && (
                        <span style={{ display: 'block', fontSize: '0.7rem' }}>YAML</span>
                      )}
                    </button>
                  );
                })}
              </nav>

              <div className="card" style={{ minWidth: 0 }}>
                {active && !active.present && (
                  <ErrorPanel
                    message={`${active.name} is declared in the schema registry but is not present in the configured corpus.`}
                  />
                )}
                {active && active.present && !active.tabular && (
                  <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-600)' }}>
                    <strong>{active.name}</strong>
                    <p style={{ marginTop: 'var(--spacing-2)' }}>{active.note}</p>
                  </div>
                )}
                {active && active.present && active.tabular && <DataGrid name={active.name} />}
                {!active && (
                  <div style={{ color: 'var(--color-neutral-500)', fontSize: '0.875rem' }}>
                    Select a table.
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
