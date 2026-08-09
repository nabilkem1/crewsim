import React, { useEffect, useState } from 'react';

interface TTestResponse {
    metric: string;
    t_statistic: number;
    p_value: number;
    significant: boolean;
}

export const StatisticalCompare: React.FC<{ runA: string; runB: string }> = ({ runA, runB }) => {
    const [data, setData] = useState<TTestResponse | null>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!runA || !runB) return;
        setLoading(true);
        fetch(`/api/comparison/t-test?run_a=${runA}&run_b=${runB}&metric=accuracy`)
            .then(res => res.json())
            .then(res => {
                setData(res);
                setLoading(false);
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });
    }, [runA, runB]);

    return (
        <div>
            <h3 style={{ marginBottom: 'var(--spacing-xs)' }}>Statistical T-Tests</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 'var(--spacing-md)' }}>
                Comparing <strong>{runA}</strong> and <strong>{runB}</strong>
            </p>
            
            {loading && <div>Loading statistics...</div>}
            
            {!loading && data && (
                <div className="card" style={{ 
                    padding: 'var(--spacing-md)', 
                    borderLeft: `4px solid ${data.significant ? 'var(--color-success)' : 'var(--color-warning)'}`
                }}>
                    <h4 style={{ margin: '0 0 var(--spacing-sm) 0', fontSize: '1.2em' }}>
                        Metric: {data.metric.charAt(0).toUpperCase() + data.metric.slice(1)}
                    </h4>
                    
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-md)', marginBottom: 'var(--spacing-md)' }}>
                        <div style={{ padding: 'var(--spacing-sm)', backgroundColor: 'var(--bg-secondary)', borderRadius: '4px' }}>
                            <div style={{ fontSize: '0.9em', color: 'var(--text-secondary)' }}>T-Statistic</div>
                            <div style={{ fontSize: '1.5em', fontWeight: 'bold' }}>{data.t_statistic.toFixed(4)}</div>
                        </div>
                        <div style={{ padding: 'var(--spacing-sm)', backgroundColor: 'var(--bg-secondary)', borderRadius: '4px' }}>
                            <div style={{ fontSize: '0.9em', color: 'var(--text-secondary)' }}>P-Value</div>
                            <div style={{ fontSize: '1.5em', fontWeight: 'bold' }}>{data.p_value.toFixed(4)}</div>
                        </div>
                    </div>
                    
                    <div style={{ 
                        padding: 'var(--spacing-sm)', 
                        backgroundColor: data.significant ? 'rgba(0, 255, 0, 0.1)' : 'rgba(255, 0, 0, 0.1)',
                        color: data.significant ? 'var(--color-success)' : 'var(--color-warning)',
                        borderRadius: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                    }}>
                        <span style={{ fontSize: '1.2em' }}>{data.significant ? '✓' : 'ℹ'}</span>
                        <strong>Result:</strong> 
                        The difference is {data.significant ? '' : 'not '}statistically significant (α = 0.05).
                    </div>
                </div>
            )}
        </div>
    );
};
