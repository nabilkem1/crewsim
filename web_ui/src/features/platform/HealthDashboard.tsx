import { useState, useEffect } from 'react';

interface HealthData {
  status: string;
  cpu: { usage_percent: number };
  memory: { total_gb: number; used_gb: number; usage_percent: number };
  database: { status: string; latency_ms?: number };
  uptime_seconds: number;
}

export function HealthDashboard() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/platform/health')
      .then(res => res.json())
      .then(data => {
        setHealth(data);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Loading health dashboard...</div>;
  if (!health) return <div>Failed to load health data.</div>;

  return (
    <div className="card">
      <h2 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.25rem', fontWeight: 600, marginTop: 0 }}>Platform Health Dashboard</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--spacing-4)' }}>
        <div style={{ padding: 'var(--spacing-4)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--surface-muted)' }}>
          <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-500)', marginBottom: 'var(--spacing-1)' }}>Status</div>
          <div style={{ fontWeight: 500, color: health.status === 'healthy' ? 'var(--color-success-text)' : 'var(--color-neutral-800)' }}>{health.status}</div>
        </div>
        <div style={{ padding: 'var(--spacing-4)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--surface-muted)' }}>
          <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-500)', marginBottom: 'var(--spacing-1)' }}>CPU</div>
          <div style={{ fontWeight: 500 }}>{health.cpu.usage_percent}%</div>
        </div>
        <div style={{ padding: 'var(--spacing-4)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--surface-muted)' }}>
          <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-500)', marginBottom: 'var(--spacing-1)' }}>Memory</div>
          <div style={{ fontWeight: 500 }}>{health.memory.used_gb} GB / {health.memory.total_gb} GB ({health.memory.usage_percent}%)</div>
        </div>
        <div style={{ padding: 'var(--spacing-4)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--surface-muted)' }}>
          <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-500)', marginBottom: 'var(--spacing-1)' }}>Database</div>
          <div style={{ fontWeight: 500 }}>{health.database.status} (latency: {health.database.latency_ms || 0}ms)</div>
        </div>
        <div style={{ padding: 'var(--spacing-4)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--surface-muted)' }}>
          <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-500)', marginBottom: 'var(--spacing-1)' }}>Uptime</div>
          <div style={{ fontWeight: 500 }}>{health.uptime_seconds}s</div>
        </div>
      </div>
    </div>
  );
}
