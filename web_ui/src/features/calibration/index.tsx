export { CalibrationLauncher } from './CalibrationLauncher';
export { RunMonitor } from './RunMonitor';
export { ResultsInspector } from './ResultsInspector';
export { DiagnosticsView } from './DiagnosticsView';
export { ComparisonView } from './ComparisonView';
export { LogExplorer } from './LogExplorer';
export { DataProfileView } from './DataProfileView';

import React, { useState, useEffect } from 'react';
import { CalibrationLauncher } from './CalibrationLauncher';
import { RunMonitor } from './RunMonitor';
import { ComparisonView } from './ComparisonView';
import { DataProfileView } from './DataProfileView';

export const CalibrationDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'pipeline' | 'profile'>('pipeline');
  const [modalView, setModalView] = useState<'none' | 'compare'>('none');
  const [modalCompareIds, setModalCompareIds] = useState<string[]>([]);

  useEffect(() => {
    const handleCompare = (e: any) => {
      setModalCompareIds(e.detail.jobIds);
      setModalView('compare');
    };
    
    window.addEventListener('CALIBRATION_COMPARE', handleCompare);
    return () => {
      window.removeEventListener('CALIBRATION_COMPARE', handleCompare);
    };
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
      <div style={{ display: 'flex', gap: 'var(--spacing-4)', borderBottom: '1px solid var(--border-default)', paddingBottom: 'var(--spacing-2)' }}>
        <button 
          onClick={() => setActiveTab('pipeline')}
          style={{
            padding: 'var(--spacing-2) var(--spacing-4)',
            backgroundColor: activeTab === 'pipeline' ? 'var(--color-primary-600)' : 'transparent',
            color: activeTab === 'pipeline' ? 'white' : 'var(--color-text-base)',
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
            color: activeTab === 'profile' ? 'white' : 'var(--color-text-base)',
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

      {/* Modal Overlay for Compare */}
      {modalView !== 'none' && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 50, padding: 'var(--spacing-6)'
        }}>
          <div style={{
            backgroundColor: 'var(--surface-default)',
            borderRadius: 'var(--radius-lg)',
            width: '100%', maxWidth: '800px',
            maxHeight: '90vh', overflowY: 'auto',
            position: 'relative',
            boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)'
          }}>
            <button 
              onClick={() => setModalView('none')}
              style={{
                position: 'absolute', top: '24px', right: '24px',
                background: 'none', border: 'none', cursor: 'pointer',
                fontSize: '1.5rem', lineHeight: '1', color: 'var(--color-neutral-500)',
                zIndex: 10
              }}
              title="Close"
            >
              &times;
            </button>
            <div style={{ padding: '0' }}>
              {modalView === 'compare' && <ComparisonView initialJobIds={modalCompareIds} />}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
