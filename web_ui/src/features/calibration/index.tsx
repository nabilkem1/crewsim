export { CalibrationLauncher } from './CalibrationLauncher';
export { RunMonitor } from './RunMonitor';
export { ResultsInspector } from './ResultsInspector';
export { LogExplorer } from './LogExplorer';
export { DataProfileView } from './DataProfileView';

import { useState } from 'react';
import { CalibrationLauncher } from './CalibrationLauncher';
import { RunMonitor } from './RunMonitor';
import { DataProfileView } from './DataProfileView';

export const CalibrationDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'pipeline' | 'profile'>('pipeline');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
      <div style={{ display: 'flex', gap: 'var(--spacing-4)', borderBottom: '1px solid var(--border-default)', paddingBottom: 'var(--spacing-2)' }}>
        <button 
          onClick={() => setActiveTab('pipeline')}
          style={{
            padding: 'var(--spacing-2) var(--spacing-4)',
            backgroundColor: activeTab === 'pipeline' ? 'var(--color-primary-600)' : 'transparent',
            color: activeTab === 'pipeline' ? 'var(--color-on-primary)' : 'var(--color-text-base)',
            border: activeTab === 'pipeline' ? 'none' : '1px solid var(--border-default)',
            borderRadius: 'var(--radius-md)',
            fontWeight: 500,
            cursor: 'pointer'
          }}
        >
          Calibration Pipeline
        </button>
        <button 
          onClick={() => setActiveTab('profile')}
          style={{
            padding: 'var(--spacing-2) var(--spacing-4)',
            backgroundColor: activeTab === 'profile' ? 'var(--color-primary-600)' : 'transparent',
            color: activeTab === 'profile' ? 'var(--color-on-primary)' : 'var(--color-text-base)',
            border: activeTab === 'profile' ? 'none' : '1px solid var(--border-default)',
            borderRadius: 'var(--radius-md)',
            fontWeight: 500,
            cursor: 'pointer'
          }}
        >
          Descriptive Data Profile
        </button>
      </div>

      {activeTab === 'pipeline' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-6)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 'var(--spacing-6)' }}>
            <CalibrationLauncher />
            <RunMonitor />
          </div>
        </div>
      )}

      {activeTab === 'profile' && (
        <DataProfileView />
      )}

    </div>
  );
};
