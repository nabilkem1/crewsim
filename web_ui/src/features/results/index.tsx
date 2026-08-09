import React from 'react';
import { Summaries } from './Summaries';
import { Artifacts } from './Artifacts';
import { Metrics } from './Metrics';
import { Charts } from './Charts';

export function ResultsDashboard() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-6)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 600 }}>Results & Visualization Dashboard</h1>
      </div>
      <Summaries />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-6)' }}>
        <Artifacts />
        <Metrics />
      </div>
      <Charts />
    </div>
  );
}
