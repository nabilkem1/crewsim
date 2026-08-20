import React, { useState, useEffect } from 'react';

export const AnalyticsDashboard: React.FC = () => {
    const [activeTab, setActiveTab] = useState('summaries');
    const [summaries, setSummaries] = useState<any[]>([]);
    const [comparisons, setComparisons] = useState<any[]>([]);
    const [drills, setDrills] = useState<any[]>([]);

    useEffect(() => {
        // Fetch summaries
        fetch('/cascade-summaries')
            .then(res => res.json())
            .then(data => setSummaries(data.summaries || []))
            .catch(e => {
                console.error("Failed to fetch cascade summaries, using mock data", e);
                setSummaries([
                    { id: 'casc_mock_1', name: 'Mock Recovery', status: 'completed', total_drills: 10, success_rate: 0.9, cost_impact: 10000 },
                    { id: 'casc_mock_2', name: 'Mock Escalation', status: 'running', total_drills: 4, success_rate: 0.5, cost_impact: 4500 }
                ]);
            });

        // Fetch comparisons
        fetch('/cascade-policy-comparisons')
            .then(res => res.json())
            .then(data => setComparisons(data.comparisons || []))
            .catch(e => {
                console.error("Failed to fetch policy comparisons, using mock data", e);
                setComparisons([
                    { policy_name: 'Mock Policy A', avg_resolution_time: 40, cost_efficiency: 0.8, fatigue_impact: 'High' },
                    { policy_name: 'Mock Policy B', avg_resolution_time: 60, cost_efficiency: 0.95, fatigue_impact: 'Low' }
                ]);
            });

        // Fetch drills
        fetch('/exemplar-drills')
            .then(res => res.json())
            .then(data => setDrills(data.drills || []))
            .catch(e => {
                console.error("Failed to fetch exemplar drills, using mock data", e);
                setDrills([
                    { id: 'drill_mock_1', name: 'Mock Drill A', efficiency_score: 90, time_to_fill_mins: 15 }
                ]);
            });
    }, []);

    return (
        <div className="card">
            <h2 style={{ marginBottom: '1.5rem', color: 'var(--color-neutral-900)' }}>Cascade Analytics Dashboard</h2>
            
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '2rem', borderBottom: '1px solid var(--border-default)', paddingBottom: '1rem' }}>
                {['summaries', 'drills', 'comparisons'].map(tab => (
                    <button 
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        role="button"
                        tabIndex={0}
                        aria-label={`Navigate to ${tab.replace('-', ' ')}`}
                        style={{ 
                            padding: '0.5rem 1rem', 
                            borderRadius: 'var(--radius-md)',
                            border: 'none',
                            backgroundColor: activeTab === tab ? 'var(--color-primary-100)' : 'transparent',
                            color: activeTab === tab ? 'var(--color-primary-700)' : 'var(--color-neutral-600)',
                            cursor: 'pointer',
                            fontWeight: 500,
                            textTransform: 'capitalize'
                        }}>
                        {tab.replace('-', ' ')}
                    </button>
                ))}
            </div>

            {activeTab === 'summaries' && (
                <div>
                    <h3 style={{ marginBottom: '1rem', color: 'var(--color-neutral-800)' }}>Cascade Summaries & Timelines</h3>
                    <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))' }}>
                        {summaries.map(s => (
                            <div key={s.id} style={{ 
                                padding: '1.5rem', 
                                border: '1px solid var(--border-default)', 
                                borderRadius: 'var(--radius-md)',
                                backgroundColor: 'var(--surface-default)',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '0.75rem'
                            }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                    <div style={{ fontWeight: 600, fontSize: '1.125rem' }}>{s.name}</div>
                                    <div style={{ 
                                        padding: '0.25rem 0.75rem', 
                                        borderRadius: '1rem',
                                        fontSize: '0.75rem',
                                        fontWeight: 600,
                                        backgroundColor: s.status === 'completed' ? 'var(--color-success-bg)' : 'var(--color-info-bg)',
                                        color: s.status === 'completed' ? 'var(--color-success-text)' : 'var(--color-info-text)'
                                    }}>
                                        {s.status.toUpperCase()}
                                    </div>
                                </div>
                                <div style={{ color: 'var(--color-neutral-500)', fontSize: '0.875rem' }}>ID: {s.id}</div>
                                
                                <div style={{ 
                                    display: 'grid', 
                                    gridTemplateColumns: '1fr 1fr', 
                                    gap: '1rem', 
                                    marginTop: '0.5rem',
                                    paddingTop: '0.75rem',
                                    borderTop: '1px solid var(--border-default)'
                                }}>
                                    <div>
                                        <div style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)', textTransform: 'uppercase' }}>Total Drills</div>
                                        <div style={{ fontWeight: 500 }}>{s.total_drills}</div>
                                    </div>
                                    <div>
                                        <div style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)', textTransform: 'uppercase' }}>Success Rate</div>
                                        <div style={{ fontWeight: 500, color: s.success_rate >= 0.8 ? 'var(--color-success-text)' : 'var(--color-warning-text)' }}>
                                            {(s.success_rate * 100).toFixed(0)}%
                                        </div>
                                    </div>
                                    <div>
                                        <div style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)', textTransform: 'uppercase' }}>Cost Impact</div>
                                        <div style={{ fontWeight: 500 }}>${s.cost_impact.toLocaleString()}</div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {activeTab === 'drills' && (
                <div>
                    <h3 style={{ marginBottom: '1rem', color: 'var(--color-neutral-800)' }}>Exemplar Drills</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        {drills.map(drill => (
                            <div key={drill.id} style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                padding: '1rem 1.5rem',
                                backgroundColor: 'var(--surface-default)',
                                border: '1px solid var(--border-default)',
                                borderRadius: 'var(--radius-md)'
                            }}>
                                <div>
                                    <div style={{ fontWeight: 600 }}>{drill.name}</div>
                                    <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-500)' }}>ID: {drill.id}</div>
                                </div>
                                <div style={{ display: 'flex', gap: '2rem', textAlign: 'right' }}>
                                    <div>
                                        <div style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)' }}>Efficiency</div>
                                        <div style={{ fontWeight: 600 }}>{drill.efficiency_score} / 100</div>
                                    </div>
                                    <div>
                                        <div style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)' }}>Fill Time</div>
                                        <div style={{ fontWeight: 600 }}>{drill.time_to_fill_mins} mins</div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {activeTab === 'comparisons' && (
                <div>
                    <h3 style={{ marginBottom: '1rem', color: 'var(--color-neutral-800)' }}>Cascade Policy Comparisons</h3>
                    <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
                            <thead>
                                <tr style={{ borderBottom: '2px solid var(--border-default)' }}>
                                    <th style={{ padding: '0.75rem 1rem', color: 'var(--color-neutral-600)' }}>Policy Name</th>
                                    <th style={{ padding: '0.75rem 1rem', color: 'var(--color-neutral-600)' }}>Avg Resolution Time</th>
                                    <th style={{ padding: '0.75rem 1rem', color: 'var(--color-neutral-600)' }}>Cost Efficiency</th>
                                    <th style={{ padding: '0.75rem 1rem', color: 'var(--color-neutral-600)' }}>Fatigue Impact</th>
                                </tr>
                            </thead>
                            <tbody>
                                {comparisons.map((comp, idx) => (
                                    <tr key={idx} style={{ borderBottom: '1px solid var(--border-default)' }}>
                                        <td style={{ padding: '1rem', fontWeight: 500 }}>{comp.policy_name}</td>
                                        <td style={{ padding: '1rem' }}>{comp.avg_resolution_time} mins</td>
                                        <td style={{ padding: '1rem' }}>{(comp.cost_efficiency * 100).toFixed(0)}%</td>
                                        <td style={{ 
                                            padding: '1rem',
                                            color: comp.fatigue_impact === 'High' ? 'var(--color-error-text)' : 
                                                   comp.fatigue_impact === 'Medium' ? 'var(--color-warning-text)' : 
                                                   'var(--color-success-text)'
                                        }}>
                                            {comp.fatigue_impact}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
};
