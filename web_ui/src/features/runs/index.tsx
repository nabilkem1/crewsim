import React, { useState, useEffect } from 'react';

// Types
interface Run {
  id: string;
  name: string;
  status: string;
  created_at: string;
  updated_at: string;
  duration: number | null;
}

interface RunsResponse {
  data: Run[];
  meta: {
    total: number;
    page: number;
    limit: number;
    pages: number;
  };
}

export const RunManagementDashboard: React.FC = () => {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);

  const fetchRuns = async () => {
    setLoading(true);
    try {
      const queryParams = new URLSearchParams({
        page: page.toString(),
        limit: '10',
      });
      if (search) queryParams.append('search', search);
      if (statusFilter) queryParams.append('status', statusFilter);

      const response = await fetch(`/api/runs?${queryParams.toString()}`);
      if (response.ok) {
        const data: RunsResponse = await response.json();
        setRuns(data.data);
        setTotalPages(data.meta.pages);
      }
    } catch (error) {
      console.error("Failed to fetch runs", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, [page, search, statusFilter]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(e.target.value);
    setPage(1);
  };

  const handleStatusChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setStatusFilter(e.target.value);
    setPage(1);
  };

  const getStatusColor = (status: string) => {
    switch (status.toUpperCase()) {
      case 'COMPLETED': return { bg: 'var(--color-success-bg)', text: 'var(--color-success-text)' };
      case 'FAILED': return { bg: 'var(--color-error-bg)', text: 'var(--color-error-text)' };
      case 'RUNNING': return { bg: 'var(--color-info-bg)', text: 'var(--color-info-text)' };
      default: return { bg: 'var(--color-neutral-100)', text: 'var(--color-neutral-700)' };
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-6)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 600 }}>Run Management Dashboard</h1>
        
        <div style={{ display: 'flex', gap: 'var(--spacing-3)' }}>
          <input 
            type="text" 
            placeholder="Search runs..." 
            value={search}
            onChange={handleSearchChange}
            style={{
              padding: 'var(--spacing-2) var(--spacing-3)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-default)',
              fontFamily: 'var(--font-sans)'
            }}
          />
          <select 
            value={statusFilter} 
            onChange={handleStatusChange}
            style={{
              padding: 'var(--spacing-2) var(--spacing-3)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-default)',
              fontFamily: 'var(--font-sans)',
              backgroundColor: 'var(--surface-default)'
            }}
          >
            <option value="">All Statuses</option>
            <option value="COMPLETED">Completed</option>
            <option value="RUNNING">Running</option>
            <option value="FAILED">Failed</option>
          </select>
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 'var(--spacing-6)', textAlign: 'center', color: 'var(--color-neutral-500)' }}>
            Loading runs...
          </div>
        ) : runs.length === 0 ? (
          <div style={{ padding: 'var(--spacing-6)', textAlign: 'center', color: 'var(--color-neutral-500)' }}>
            No runs found matching your criteria.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead style={{ backgroundColor: 'var(--surface-muted)', borderBottom: '1px solid var(--border-default)' }}>
              <tr>
                <th style={{ padding: 'var(--spacing-3) var(--spacing-4)', fontWeight: 500, color: 'var(--color-neutral-600)' }}>Run ID</th>
                <th style={{ padding: 'var(--spacing-3) var(--spacing-4)', fontWeight: 500, color: 'var(--color-neutral-600)' }}>Name</th>
                <th style={{ padding: 'var(--spacing-3) var(--spacing-4)', fontWeight: 500, color: 'var(--color-neutral-600)' }}>Status</th>
                <th style={{ padding: 'var(--spacing-3) var(--spacing-4)', fontWeight: 500, color: 'var(--color-neutral-600)' }}>Date</th>
                <th style={{ padding: 'var(--spacing-3) var(--spacing-4)', fontWeight: 500, color: 'var(--color-neutral-600)' }}>Duration</th>
                <th style={{ padding: 'var(--spacing-3) var(--spacing-4)', fontWeight: 500, color: 'var(--color-neutral-600)', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {runs.map(run => {
                const statusStyle = getStatusColor(run.status);
                return (
                  <tr key={run.id} style={{ borderBottom: '1px solid var(--border-default)' }}>
                    <td style={{ padding: 'var(--spacing-3) var(--spacing-4)', fontFamily: 'var(--font-mono)', fontSize: '0.875rem' }}>{run.id}</td>
                    <td style={{ padding: 'var(--spacing-3) var(--spacing-4)', fontWeight: 500 }}>{run.name}</td>
                    <td style={{ padding: 'var(--spacing-3) var(--spacing-4)' }}>
                      <span style={{ 
                        backgroundColor: statusStyle.bg, 
                        color: statusStyle.text,
                        padding: '2px 8px',
                        borderRadius: '9999px',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        display: 'inline-block'
                      }}>
                        {run.status}
                      </span>
                    </td>
                    <td style={{ padding: 'var(--spacing-3) var(--spacing-4)', color: 'var(--color-neutral-600)', fontSize: '0.875rem' }}>
                      {new Date(run.created_at).toLocaleString()}
                    </td>
                    <td style={{ padding: 'var(--spacing-3) var(--spacing-4)', color: 'var(--color-neutral-600)', fontSize: '0.875rem' }}>
                      {run.duration ? `${Math.floor(run.duration / 60)}m ${run.duration % 60}s` : '-'}
                    </td>
                    <td style={{ padding: 'var(--spacing-3) var(--spacing-4)', textAlign: 'right' }}>
                      <button style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--color-primary-600)',
                        cursor: 'pointer',
                        fontWeight: 500,
                        fontSize: '0.875rem'
                      }}>
                        View Details
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        
        {/* Pagination */}
        {!loading && totalPages > 1 && (
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            padding: 'var(--spacing-4)',
            borderTop: '1px solid var(--border-default)'
          }}>
            <button 
              disabled={page === 1}
              onClick={() => setPage(p => Math.max(1, p - 1))}
              style={{
                padding: 'var(--spacing-2) var(--spacing-4)',
                border: '1px solid var(--border-default)',
                borderRadius: 'var(--radius-md)',
                backgroundColor: page === 1 ? 'var(--surface-muted)' : 'var(--surface-default)',
                color: page === 1 ? 'var(--color-neutral-400)' : 'var(--color-neutral-700)',
                cursor: page === 1 ? 'not-allowed' : 'pointer'
              }}
            >
              Previous
            </button>
            <span style={{ fontSize: '0.875rem', color: 'var(--color-neutral-600)' }}>
              Page {page} of {totalPages}
            </span>
            <button 
              disabled={page === totalPages}
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              style={{
                padding: 'var(--spacing-2) var(--spacing-4)',
                border: '1px solid var(--border-default)',
                borderRadius: 'var(--radius-md)',
                backgroundColor: page === totalPages ? 'var(--surface-muted)' : 'var(--surface-default)',
                color: page === totalPages ? 'var(--color-neutral-400)' : 'var(--color-neutral-700)',
                cursor: page === totalPages ? 'not-allowed' : 'pointer'
              }}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
