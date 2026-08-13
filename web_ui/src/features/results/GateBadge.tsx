import { useState } from 'react';
import { Modal } from '../../components/Modal';
import { GATE_INFO, type GateId } from './gateInfo';

/**
 * Every place a gate ID (V1..V9) is shown to a planner, it should read as
 * "V3 (Usability Rate — Validation)", not a bare code, and clicking it should
 * open the real spec definition (§9) rather than leave the planner to go
 * find spec_sections/9_... themselves.
 */
export function GateBadge({ gate }: { gate: string }) {
  const [open, setOpen] = useState(false);
  const info = GATE_INFO[gate as GateId];

  if (!info) return <span>{gate}</span>;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title={`${info.nickname} — click for the full gate definition`}
        style={{
          background: 'none',
          border: 'none',
          padding: 0,
          margin: 0,
          font: 'inherit',
          fontWeight: 'inherit',
          color: 'inherit',
          cursor: 'pointer',
          textDecoration: 'underline',
          textDecorationStyle: 'dotted',
          textUnderlineOffset: '3px',
        }}
      >
        {gate} ({info.title} — {info.kind})
      </button>
      {open && (
        <Modal title={`Gate ${gate} — ${info.title}`} onClose={() => setOpen(false)}>
          <div style={{ display: 'flex', gap: 'var(--spacing-3)', flexWrap: 'wrap', marginBottom: 'var(--spacing-4)' }}>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 700,
                padding: '0.25rem 0.6rem',
                borderRadius: 'var(--radius-full, 999px)',
                backgroundColor: info.kind === 'Verification' ? 'var(--color-primary-100, #dbeafe)' : 'var(--color-warning-bg, #fef3c7)',
                color: info.kind === 'Verification' ? 'var(--color-primary-700, #1d4ed8)' : 'var(--color-warning-text, #92400e)',
              }}
            >
              {info.kind}
            </span>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 700,
                padding: '0.25rem 0.6rem',
                borderRadius: 'var(--radius-full, 999px)',
                backgroundColor: 'var(--surface-muted)',
                color: 'var(--color-neutral-600)',
              }}
            >
              nicknamed "{info.nickname}"
            </span>
          </div>

          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: 'var(--spacing-1)' }}>The test</h3>
          <p style={{ fontSize: '0.875rem', lineHeight: 1.6, marginTop: 0 }}>{info.test}</p>

          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: 'var(--spacing-1)' }}>Pass criterion</h3>
          <p style={{ fontSize: '0.875rem', lineHeight: 1.6, marginTop: 0 }}>{info.passCriterion}</p>

          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: 'var(--spacing-1)' }}>How it actually works</h3>
          <ul style={{ fontSize: '0.875rem', lineHeight: 1.6, marginTop: 0, paddingLeft: '1.25rem' }}>
            {info.detail.map((line, i) => (
              <li key={i} style={{ marginBottom: 'var(--spacing-2)' }}>
                {line}
              </li>
            ))}
          </ul>
        </Modal>
      )}
    </>
  );
}
