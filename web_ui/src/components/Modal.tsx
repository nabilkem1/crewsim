import { useEffect } from 'react';
import type { ReactNode } from 'react';

/**
 * A large, scrollable modal for content too long for an inline expansion --
 * e.g. a calibrated model's full formula plus how it was fit. Closes on
 * Escape, on backdrop click, or the close button; body scroll is locked
 * while open so the page behind it doesn't scroll along with it.
 */
export const Modal: React.FC<{ title: string; onClose: () => void; children: ReactNode }> = ({
  title,
  onClose,
  children,
}) => {
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={onClose}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0,0,0,0.5)',
        zIndex: 3000,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        padding: 'var(--spacing-6)',
        // Not a portal: this renders wherever it was triggered from in the
        // DOM tree, so without an explicit reset it inherits `color` from
        // whatever ambient text color surrounds the trigger (e.g. a
        // pass/fail-colored gate badge), tinting the whole modal green/red.
        color: 'var(--text-default, var(--color-neutral-900, #111827))',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          backgroundColor: 'var(--surface-default, #ffffff)',
          borderRadius: 'var(--radius-lg)',
          width: '100%',
          maxWidth: '900px',
          height: '85vh',
          maxHeight: '900px',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 25px 50px rgba(0,0,0,0.25)',
          border: '1px solid var(--border-default)',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: 'var(--spacing-4) var(--spacing-6)',
            borderBottom: '1px solid var(--border-default)',
            flexShrink: 0,
          }}
        >
          <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600 }}>{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              border: 'none',
              backgroundColor: 'var(--surface-muted)',
              color: 'var(--color-neutral-700)',
              fontSize: '1.1rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            &times;
          </button>
        </div>
        <div
          style={{
            padding: 'var(--spacing-6)',
            overflowY: 'auto',
            flex: 1,
            lineHeight: 1.6,
          }}
        >
          {children}
        </div>
      </div>
    </div>
  );
};
