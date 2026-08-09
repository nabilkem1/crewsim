import { useState, useEffect } from 'react';

interface AuditLog {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string;
  details?: any;
}

export function AuditLogViewer() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/platform/audit-log')
      .then(res => res.json())
      .then(data => {
        setLogs(data);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Loading audit logs...</div>;

  return (
    <div className="card">
      <h2 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.25rem', fontWeight: 600, marginTop: 0 }}>System Audit Log</h2>
      {logs.length === 0 ? (
        <div style={{ color: 'var(--color-neutral-500)' }}>No audit logs found.</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ backgroundColor: 'var(--surface-muted)', borderBottom: '1px solid var(--border-default)' }}>
                <th style={{ padding: 'var(--spacing-3) var(--spacing-4)', fontWeight: 500, color: 'var(--color-neutral-600)' }}>Timestamp</th>
                <th style={{ padding: 'var(--spacing-3) var(--spacing-4)', fontWeight: 500, color: 'var(--color-neutral-600)' }}>Actor</th>
                <th style={{ padding: 'var(--spacing-3) var(--spacing-4)', fontWeight: 500, color: 'var(--color-neutral-600)' }}>Action</th>
                <th style={{ padding: 'var(--spacing-3) var(--spacing-4)', fontWeight: 500, color: 'var(--color-neutral-600)' }}>Entity</th>
                <th style={{ padding: 'var(--spacing-3) var(--spacing-4)', fontWeight: 500, color: 'var(--color-neutral-600)' }}>Details</th>
              </tr>
            </thead>
            <tbody>
              {logs.map(log => (
                <tr key={log.id} style={{ borderBottom: '1px solid var(--border-default)' }}>
                  <td style={{ padding: 'var(--spacing-3) var(--spacing-4)' }}>{new Date(log.timestamp).toLocaleString()}</td>
                  <td style={{ padding: 'var(--spacing-3) var(--spacing-4)' }}>{log.actor}</td>
                  <td style={{ padding: 'var(--spacing-3) var(--spacing-4)' }}>{log.action}</td>
                  <td style={{ padding: 'var(--spacing-3) var(--spacing-4)' }}>{log.entity_type} ({log.entity_id})</td>
                  <td style={{ padding: 'var(--spacing-3) var(--spacing-4)', color: 'var(--color-neutral-500)', fontFamily: 'var(--font-mono)' }}>
                    {log.details ? JSON.stringify(log.details) : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
