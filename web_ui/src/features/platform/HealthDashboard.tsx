import { useCallback, useEffect, useState } from 'react';
import { apiFetch, errorMessage } from '../../api/client';
import { ErrorPanel, Loading } from '../../components/StatusPanel';

/**
 * Host and queue health.
 *
 * Two fixes here. The path was `/platform/health`, which is not where the
 * router is mounted -- it 404'd (and in dev, being outside the proxy's `/api`
 * prefix, it hit the Vite server and returned HTML). And host metrics are now
 * nullable: the backend used to invent CPU/memory figures when psutil was
 * missing, which is always, so this rendered a fictional 26.2% as fact.
 */

interface HealthData {
  status: string;
  database: { status: string };
  kpis: { active_runs: number; avg_queue_wait_seconds: number; queued_jobs: number };
  metrics_available: boolean;
  metrics_unavailable_reason?: string;
  cpu: { usage_percent: number } | null;
  memory: { total_gb: number; used_gb: number; usage_percent: number } | null;
  uptime_seconds: number | null;
}

const tile: React.CSSProperties = {
  padding: 'var(--spacing-4)',
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-md)',
  backgroundColor: 'var(--surface-muted)',
};

const label: React.CSSProperties = {
  fontSize: '0.875rem',
  color: 'var(--color-neutral-500)',
  marginBottom: 'var(--spacing-1)',
};

const Tile: React.FC<{ name: string; children: React.ReactNode }> = ({ name, children }) => (
  <div style={tile}>
    <div style={label}>{name}</div>
    <div style={{ fontWeight: 500 }}>{children}</div>
  </div>
);

export function HealthDashboard() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setHealth(await apiFetch<HealthData>('/platform/health'));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <Loading what="platform health" />;
  if (error || !health) return <ErrorPanel message={error ?? 'No data'} onRetry={() => void load()} />;

  return (
    <div className="card">
      <h2 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.25rem', fontWeight: 600, marginTop: 0 }}>
        Platform Health Dashboard
      </h2>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 'var(--spacing-4)',
        }}
      >
        <Tile name="Status">{health.status}</Tile>
        <Tile name="Database">{health.database.status}</Tile>
        <Tile name="Active runs">{health.kpis.active_runs}</Tile>
        <Tile name="Queued jobs">{health.kpis.queued_jobs}</Tile>
        <Tile name="Avg queue wait">{health.kpis.avg_queue_wait_seconds}s</Tile>
        <Tile name="CPU">
          {health.metrics_available && health.cpu ? `${health.cpu.usage_percent}%` : 'Unavailable'}
        </Tile>
        <Tile name="Memory">
          {health.metrics_available && health.memory
            ? `${health.memory.used_gb} / ${health.memory.total_gb} GB (${health.memory.usage_percent}%)`
            : 'Unavailable'}
        </Tile>
      </div>

      {!health.metrics_available && (
        <p
          style={{
            marginTop: 'var(--spacing-4)',
            fontSize: '0.875rem',
            color: 'var(--color-neutral-600)',
          }}
        >
          {health.metrics_unavailable_reason ?? 'Host metrics are unavailable.'}
        </p>
      )}
    </div>
  );
}
