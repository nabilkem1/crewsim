import React, { useEffect, useState } from 'react';

interface DiffItem {
    key: string;
    run_a: any;
    run_b: any;
}

interface DiffResponse {
    diff: DiffItem[];
}

export const ConfigDiff: React.FC<{ 
    runA: string; 
    runB: string; 
    onRunAChange: (v: string) => void; 
    onRunBChange: (v: string) => void 
}> = ({ runA, runB, onRunAChange, onRunBChange }) => {
    const [data, setData] = useState<DiffResponse | null>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!runA || !runB) return;
        setLoading(true);
        fetch(`/api/comparison/diff?run_a=${runA}&run_b=${runB}`)
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
            <h3 style={{ marginBottom: 'var(--spacing-sm)' }}>Config Diff</h3>
            
            <div style={{ display: 'flex', gap: 'var(--spacing-md)', marginBottom: 'var(--spacing-lg)' }}>
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <label style={{ fontSize: '0.9em', fontWeight: 'bold' }}>Run A</label>
                    <input 
                        type="text" 
                        value={runA} 
                        onChange={e => onRunAChange(e.target.value)} 
                        placeholder="Run A ID"
                        style={{ padding: 'var(--spacing-xs)', border: '1px solid var(--border-color)', borderRadius: '4px' }}
                    />
                </div>
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <label style={{ fontSize: '0.9em', fontWeight: 'bold' }}>Run B</label>
                    <input 
                        type="text" 
                        value={runB} 
                        onChange={e => onRunBChange(e.target.value)} 
                        placeholder="Run B ID"
                        style={{ padding: 'var(--spacing-xs)', border: '1px solid var(--border-color)', borderRadius: '4px' }}
                    />
                </div>
            </div>
            
            {loading && <div>Loading diff...</div>}
            
            {!loading && data && (
                <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                        <thead>
                            <tr style={{ backgroundColor: 'var(--bg-secondary)', borderBottom: '2px solid var(--border-color)' }}>
                                <th style={{ padding: 'var(--spacing-sm)' }}>Configuration Key</th>
                                <th style={{ padding: 'var(--spacing-sm)' }}>{runA} (Run A)</th>
                                <th style={{ padding: 'var(--spacing-sm)' }}>{runB} (Run B)</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.diff.map((item, index) => (
                                <tr key={item.key} style={{ 
                                    borderBottom: '1px solid var(--border-color)',
                                    backgroundColor: index % 2 === 0 ? 'transparent' : 'var(--bg-secondary)'
                                }}>
                                    <td style={{ padding: 'var(--spacing-sm)', fontWeight: 'bold' }}>{item.key}</td>
                                    <td style={{ 
                                        padding: 'var(--spacing-sm)', 
                                        backgroundColor: 'rgba(255, 0, 0, 0.05)',
                                        fontFamily: 'monospace'
                                    }}>
                                        {JSON.stringify(item.run_a)}
                                    </td>
                                    <td style={{ 
                                        padding: 'var(--spacing-sm)', 
                                        backgroundColor: 'rgba(0, 255, 0, 0.05)',
                                        fontFamily: 'monospace'
                                    }}>
                                        {JSON.stringify(item.run_b)}
                                    </td>
                                </tr>
                            ))}
                            {data.diff.length === 0 && (
                                <tr>
                                    <td colSpan={3} style={{ padding: 'var(--spacing-md)', textAlign: 'center' }}>
                                        No differences found.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};
