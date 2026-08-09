import React, { useState } from 'react';
import { LineageView } from './LineageView';
import { ConfigDiff } from './ConfigDiff';
import { StatisticalCompare } from './StatisticalCompare';

export const ProvenanceDashboard: React.FC = () => {
    const [activeTab, setActiveTab] = useState<'lineage' | 'diff' | 'stats'>('lineage');
    const [runId] = useState('run-123');
    const [runA, setRunA] = useState('run-a-123');
    const [runB, setRunB] = useState('run-b-456');

    return (
        <div className="card" style={{ padding: 'var(--spacing-md)' }}>
            <h2 style={{ color: 'var(--color-primary)', marginBottom: 'var(--spacing-md)' }}>Provenance & Comparison Dashboard</h2>
            
            <div style={{ display: 'flex', gap: 'var(--spacing-sm)', marginBottom: 'var(--spacing-md)' }}>
                <button 
                    className="btn"
                    role="button"
                    tabIndex={0}
                    aria-label="Navigate to Run Lineage and Details"
                    style={{ 
                        opacity: activeTab === 'lineage' ? 1 : 0.7,
                        backgroundColor: activeTab === 'lineage' ? 'var(--color-primary)' : 'var(--bg-secondary)',
                        color: activeTab === 'lineage' ? 'white' : 'var(--text-color)'
                    }}
                    onClick={() => setActiveTab('lineage')}
                >
                    Run Lineage & Details
                </button>
                <button 
                    className="btn"
                    role="button"
                    tabIndex={0}
                    aria-label="Navigate to Config Diff"
                    style={{ 
                        opacity: activeTab === 'diff' ? 1 : 0.7,
                        backgroundColor: activeTab === 'diff' ? 'var(--color-primary)' : 'var(--bg-secondary)',
                        color: activeTab === 'diff' ? 'white' : 'var(--text-color)'
                    }}
                    onClick={() => setActiveTab('diff')}
                >
                    Config Diff
                </button>
                <button 
                    className="btn"
                    role="button"
                    tabIndex={0}
                    aria-label="Navigate to Statistical T-Tests"
                    style={{ 
                        opacity: activeTab === 'stats' ? 1 : 0.7,
                        backgroundColor: activeTab === 'stats' ? 'var(--color-primary)' : 'var(--bg-secondary)',
                        color: activeTab === 'stats' ? 'white' : 'var(--text-color)'
                    }}
                    onClick={() => setActiveTab('stats')}
                >
                    Statistical T-Tests
                </button>
            </div>

            <div className="card" style={{ padding: 'var(--spacing-md)', backgroundColor: 'var(--bg-surface)' }}>
                {activeTab === 'lineage' && <LineageView runId={runId} />}
                {activeTab === 'diff' && <ConfigDiff runA={runA} runB={runB} onRunAChange={setRunA} onRunBChange={setRunB} />}
                {activeTab === 'stats' && <StatisticalCompare runA={runA} runB={runB} />}
            </div>
        </div>
    );
};
