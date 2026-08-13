/**
 * The states a data view can be in other than "has data".
 *
 * These exist so that no component has to invent something to render when a
 * fetch fails. The previous pattern -- catch the error, substitute plausible
 * hardcoded values -- made the failure path indistinguishable from the success
 * path at the UI.
 */

const base: React.CSSProperties = {
  padding: 'var(--spacing-4)',
  borderRadius: 'var(--radius-md)',
  border: '1px solid var(--border-default)',
  fontSize: '0.875rem',
  lineHeight: 1.5,
};

export const Loading: React.FC<{ what?: string }> = ({ what = 'data' }) => (
  <div style={{ ...base, color: 'var(--color-neutral-500)' }}>Loading {what}…</div>
);

export const ErrorPanel: React.FC<{ message: string; onRetry?: () => void }> = ({
  message,
  onRetry,
}) => (
  <div
    role="alert"
    style={{
      ...base,
      backgroundColor: 'var(--color-error-bg)',
      color: 'var(--color-error-text)',
      borderColor: 'var(--color-error-text)',
    }}
  >
    <strong>Could not load this view.</strong>
    <div style={{ marginTop: 'var(--spacing-2)' }}>{message}</div>
    {onRetry && (
      <button
        onClick={onRetry}
        style={{
          marginTop: 'var(--spacing-3)',
          padding: '0.4rem 0.9rem',
          borderRadius: 'var(--radius-md)',
          border: '1px solid currentColor',
          background: 'transparent',
          color: 'inherit',
          cursor: 'pointer',
          fontWeight: 500,
        }}
      >
        Retry
      </button>
    )}
  </div>
);

/**
 * For an endpoint that answered successfully but has nothing real to report.
 * Deliberately shows no figures: the backend sends empty collections for these,
 * because a placeholder number on screen outlives any banner above it.
 */
export const NotImplementedPanel: React.FC<{ title: string; notice: string }> = ({
  title,
  notice,
}) => (
  <div
    style={{
      ...base,
      backgroundColor: 'var(--surface-muted)',
      color: 'var(--color-neutral-700)',
      borderStyle: 'dashed',
    }}
  >
    <strong>{title} is not implemented yet.</strong>
    <div style={{ marginTop: 'var(--spacing-2)' }}>{notice}</div>
    <div style={{ marginTop: 'var(--spacing-2)', fontStyle: 'italic' }}>
      No figures are shown here because none have been computed.
    </div>
  </div>
);
