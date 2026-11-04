import { useCallback, useEffect, useState } from 'react';
import { apiFetch, errorMessage, isNotImplemented } from '../../api/client';
import { ErrorPanel, Loading, NotImplementedPanel } from '../../components/StatusPanel';

/**
 * Data quality report.
 *
 * This component used to answer a failed fetch with a hardcoded report: an
 * overall score of 95 and four passing checks, rendered identically to a real
 * result. Reporting an unearned pass on data quality is about the most
 * misleading thing this UI could do, so the fallback is gone -- and the backend
 * no longer fabricates one either. It reports `implemented: false` until it is
 * wired to `crewsim.data.quality`.
 */

interface QualityCheck {
  name: string;
  status: 'passed' | 'warning' | 'failed';
  details: string;
}

interface QualityReport {
  overall_score: number;
  checks: QualityCheck[];
}

interface QualityResponse {
  report: QualityReport | null;
  implemented?: boolean;
  notice?: string;
}

export const DataQualityDashboard: React.FC = () => {
  const [report, setReport] = useState<QualityReport | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotice(null);
    setReport(null);
    try {
      const data = await apiFetch<QualityResponse>('/data/quality-report');
      if (isNotImplemented(data)) {
        setNotice(data.notice);
      } else {
        setReport(data.report);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <Loading what="data quality report" />;
  if (error) return <ErrorPanel message={error} onRetry={() => void load()} />;
  if (notice) return <NotImplementedPanel title="The data quality report" notice={notice} />;

  if (!report) {
    return (
      <div className="card" style={{ padding: 'var(--spacing-8)', color: 'var(--color-error-text)', margin: 'var(--spacing-8) auto', maxWidth: '56rem' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: 'var(--spacing-2)', margin: 0 }}>Error</h2>
        <p style={{ margin: 0 }}>{error || 'Failed to load report.'}</p>
      </div>
    );
  }

  const getStatusStyle = (status: string): React.CSSProperties => {
    switch (status) {
      case 'passed': return { backgroundColor: 'var(--color-success-bg)', color: 'var(--color-success-text)', borderColor: 'var(--color-success-text)' };
      case 'warning': return { backgroundColor: 'var(--color-warning-bg)', color: 'var(--color-warning-text)', borderColor: 'var(--color-warning-text)' };
      case 'failed': return { backgroundColor: 'var(--color-error-bg)', color: 'var(--color-error-text)', borderColor: 'var(--color-error-text)' };
      default: return { backgroundColor: 'var(--color-neutral-100)', color: 'var(--color-neutral-800)', borderColor: 'var(--border-default)' };
    }
  };

  return (
    <div className="card" style={{ maxWidth: '56rem', margin: 'var(--spacing-8) auto 0', padding: 'var(--spacing-6)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-6)' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-neutral-800)', margin: 0 }}>Data Quality Dashboard</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-3)' }}>
          <span style={{ color: 'var(--color-neutral-600)', fontWeight: 500 }}>Overall Score:</span>
          <span style={{
            fontSize: '1.5rem', fontWeight: 700, padding: 'var(--spacing-1) var(--spacing-3)', borderRadius: 'var(--radius-lg)',
            backgroundColor: report.overall_score >= 90 ? 'var(--color-success-bg)' : report.overall_score >= 70 ? 'var(--color-warning-bg)' : 'var(--color-error-bg)',
            color: report.overall_score >= 90 ? 'var(--color-success-text)' : report.overall_score >= 70 ? 'var(--color-warning-text)' : 'var(--color-error-text)'
          }}>
            {report.overall_score}/100
          </span>
        </div>
      </div>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
        <h3 style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--color-neutral-700)', margin: 0, marginBottom: 'var(--spacing-3)', borderBottom: '1px solid var(--border-default)', paddingBottom: 'var(--spacing-2)' }}>Pre-Simulation Checks</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
          {report.checks.map((check, idx) => (
            <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--spacing-4)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-lg)', backgroundColor: 'var(--surface-muted)' }}>
              <div style={{ marginBottom: 0 }}>
                <h4 style={{ fontWeight: 600, color: 'var(--color-neutral-800)', margin: 0 }}>{check.name}</h4>
                <p style={{ fontSize: '0.875rem', color: 'var(--color-neutral-600)', margin: 0, marginTop: 'var(--spacing-1)' }}>{check.details}</p>
              </div>
              <span style={{
                padding: 'var(--spacing-1) var(--spacing-3)', borderRadius: '9999px', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', border: '1px solid',
                ...getStatusStyle(check.status)
              }}>
                {check.status}
              </span>
            </div>
          ))}
        </div>
      </div>
      
      <div style={{ marginTop: 'var(--spacing-8)', paddingTop: 'var(--spacing-4)', borderTop: '1px solid var(--border-default)', display: 'flex', justifyContent: 'flex-end' }}>
        <button style={{ padding: 'var(--spacing-2) var(--spacing-4)', backgroundColor: 'var(--action-bg)', color: 'var(--action-fg)', borderRadius: 'var(--radius-button)', fontWeight: 500, fontSize: '0.875rem', border: 'none', cursor: 'pointer' }}>
          Refresh Report
        </button>
      </div>
    </div>
  );
};

export default DataQualityDashboard;
