import React, { useEffect, useState } from 'react';

interface LineageNode {
    id: string;
    type: string;
    timestamp: string;
    status: string;
}

interface LineageResponse {
    run_id: string;
    lineage: LineageNode[];
}

export const LineageView: React.FC<{ runId: string }> = ({ runId }) => {
    const [data, setData] = useState<LineageResponse | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setLoading(true);
        fetch(`/api/provenance/${runId}/lineage`)
            .then(res => res.json())
            .then(res => {
                setData(res);
                setLoading(false);
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });
    }, [runId]);

    if (loading) return <div>Loading lineage...</div>;
    if (!data) return <div>Error loading lineage.</div>;

    return (
        <div>
            <h3 style={{ marginBottom: 'var(--spacing-sm)' }}>Run Lineage for {data.run_id}</h3>
            <ul style={{ listStyleType: 'none', paddingLeft: 0, margin: 0 }}>
                {data.lineage.map((node) => (
                    <li key={node.id} style={{ 
                        borderLeft: '2px solid var(--color-primary)', 
                        paddingLeft: 'var(--spacing-sm)',
                        marginBottom: 'var(--spacing-md)',
                        position: 'relative'
                    }}>
                        <div style={{
                            position: 'absolute',
                            left: '-6px',
                            top: '4px',
                            width: '10px',
                            height: '10px',
                            borderRadius: '50%',
                            backgroundColor: 'var(--color-primary)'
                        }} />
                        <div style={{ fontWeight: 'bold', fontSize: '1.1em', marginBottom: '4px' }}>{node.id}</div>
                        <div style={{ display: 'flex', gap: 'var(--spacing-sm)', fontSize: '0.9em', color: 'var(--text-secondary)' }}>
                            <span><strong>Type:</strong> {node.type}</span>
                            <span>&bull;</span>
                            <span><strong>Time:</strong> {new Date(node.timestamp).toLocaleString()}</span>
                            <span>&bull;</span>
                            <span>
                                <strong>Status:</strong> 
                                <span style={{ 
                                    marginLeft: '4px',
                                    color: node.status === 'completed' ? 'var(--color-success)' : 'var(--color-warning)' 
                                }}>
                                    {node.status}
                                </span>
                            </span>
                        </div>
                    </li>
                ))}
            </ul>
        </div>
    );
};
