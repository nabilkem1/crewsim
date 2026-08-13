import { useCallback, useEffect, useState } from 'react';
import { apiFetch, errorMessage } from '../../api/client';
import { ErrorPanel, Loading } from '../../components/StatusPanel';

/**
 * A paged view of one corpus table.
 *
 * Paging is server-side: d3_pairing_legs is 511,664 rows, so "fetch it and
 * slice in the browser" would move 53 MB to render 50 lines.
 */

export interface DatasetPage {
  name: string;
  columns: string[];
  dtypes: string[];
  total: number;
  offset: number;
  limit: number;
  rows: Record<string, unknown>[];
}

const PAGE_SIZE = 50;

/** Right-align the columns polars typed as numeric, like a spreadsheet. */
function isNumeric(dtype: string): boolean {
  return /^(Int|UInt|Float|Decimal)/.test(dtype);
}

function renderCell(value: unknown): string {
  if (value === null || value === undefined) return '—';
  return String(value);
}

const th: React.CSSProperties = {
  padding: '0.4rem 0.65rem',
  fontSize: '0.7rem',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  color: 'var(--color-neutral-500)',
  borderBottom: '1px solid var(--border-default)',
  whiteSpace: 'nowrap',
  position: 'sticky',
  top: 0,
  backgroundColor: 'var(--surface-default, #fff)',
  textAlign: 'left',
};

const td: React.CSSProperties = {
  padding: '0.35rem 0.65rem',
  fontSize: '0.8125rem',
  fontFamily: 'var(--font-mono, ui-monospace, monospace)',
  borderBottom: '1px solid var(--border-subtle, rgba(0,0,0,0.06))',
  whiteSpace: 'nowrap',
};

export const DataGrid: React.FC<{ name: string }> = ({ name }) => {
  const [page, setPage] = useState<DatasetPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Reset paging when the selected table changes, or page 7 of one table
  // would silently become page 7 of the next.
  useEffect(() => {
    setOffset(0);
  }, [name]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPage(
        await apiFetch<DatasetPage>(
          `/data/datasets/${name}/rows?offset=${offset}&limit=${PAGE_SIZE}`,
        ),
      );
    } catch (e) {
      setError(errorMessage(e));
      setPage(null);
    } finally {
      setLoading(false);
    }
  }, [name, offset]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading && !page) return <Loading what={name} />;
  if (error) return <ErrorPanel message={error} onRetry={() => void load()} />;
  if (!page) return null;

  const from = page.total === 0 ? 0 : page.offset + 1;
  const to = Math.min(page.offset + page.limit, page.total);
  const atStart = page.offset === 0;
  const atEnd = to >= page.total;

  const navBtn = (disabled: boolean): React.CSSProperties => ({
    padding: '0.3rem 0.7rem',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border-default)',
    background: 'transparent',
    color: 'inherit',
    cursor: disabled ? 'default' : 'pointer',
    opacity: disabled ? 0.4 : 1,
    fontSize: '0.8125rem',
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)', minWidth: 0 }}>
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
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0 }}>{page.name}</h2>
          <div style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)' }}>
            {page.total.toLocaleString()} rows × {page.columns.length} columns
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
          <span style={{ fontSize: '0.8125rem', color: 'var(--color-neutral-500)' }}>
            {from.toLocaleString()}–{to.toLocaleString()} of {page.total.toLocaleString()}
          </span>
          <button
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            disabled={atStart}
            style={navBtn(atStart)}
          >
            ← Prev
          </button>
          <button
            onClick={() => setOffset(offset + PAGE_SIZE)}
            disabled={atEnd}
            style={navBtn(atEnd)}
          >
            Next →
          </button>
        </div>
      </div>

      <div
        style={{
          overflow: 'auto',
          maxHeight: '60vh',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-md)',
        }}
      >
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr>
              {page.columns.map((col, i) => (
                <th key={col} style={{ ...th, textAlign: isNumeric(page.dtypes[i]) ? 'right' : 'left' }}>
                  {col}
                  <div
                    style={{
                      fontWeight: 400,
                      textTransform: 'none',
                      letterSpacing: 0,
                      fontSize: '0.65rem',
                      color: 'var(--color-neutral-400, #9ca3af)',
                    }}
                  >
                    {page.dtypes[i]}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {page.rows.map((row, r) => (
              <tr key={page.offset + r}>
                {page.columns.map((col, i) => (
                  <td
                    key={col}
                    style={{ ...td, textAlign: isNumeric(page.dtypes[i]) ? 'right' : 'left' }}
                  >
                    {renderCell(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>

        {page.rows.length === 0 && (
          <div
            style={{
              padding: 'var(--spacing-4)',
              color: 'var(--color-neutral-500)',
              fontSize: '0.875rem',
            }}
          >
            No rows on this page.
          </div>
        )}
      </div>
    </div>
  );
};
