import React, { useEffect, useState } from 'react';
import { 
  fetchGantt, fetchWaterfall, fetchHeatmap, fetchTimeseries,
  fetchEligibility, fetchGrid, fetchGates, fetchDataQuality
} from './api';

export function Charts() {
  const [gantt, setGantt] = useState<any[]>([]);
  const [waterfall, setWaterfall] = useState<any[]>([]);
  const [heatmap, setHeatmap] = useState<any>(null);
  const [timeseries, setTimeseries] = useState<any>(null);
  const [eligibility, setEligibility] = useState<any>(null);
  const [grid, setGrid] = useState<any[]>([]);
  const [gates, setGates] = useState<any[]>([]);
  const [dataQuality, setDataQuality] = useState<any>(null);

  const [drillDown, setDrillDown] = useState<{ title: string; data: any } | null>(null);

  useEffect(() => {
    fetchGantt().then(setGantt).catch(console.error);
    fetchWaterfall().then(setWaterfall).catch(console.error);
    fetchHeatmap().then(setHeatmap).catch(console.error);
    fetchTimeseries().then(setTimeseries).catch(console.error);
    fetchEligibility().then(setEligibility).catch(console.error);
    fetchGrid().then(setGrid).catch(console.error);
    fetchGates().then(setGates).catch(console.error);
    fetchDataQuality().then(setDataQuality).catch(console.error);
  }, []);

  const handleDrillDown = (title: string, data: any) => {
    setDrillDown({ title, data });
  };

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-6)' }}>
        {/* Gantt */}
        <div className="card" onClick={() => handleDrillDown('Gantt Chart', gantt)} style={{ cursor: 'pointer' }}>
          <h3 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.125rem', fontWeight: 600 }}>Gantt Chart (Mock)</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
            {gantt.map((task, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center' }}>
                <div style={{ width: '120px', fontSize: '0.875rem', fontWeight: 500 }}>{task.task}</div>
                <div style={{ flex: 1, backgroundColor: 'var(--surface-muted)', height: '24px', position: 'relative', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ 
                    position: 'absolute', 
                    left: `${i * 20}%`, 
                    width: '30%', 
                    height: '100%', 
                    backgroundColor: 'var(--color-primary-500)', 
                    borderRadius: 'var(--radius-sm)'
                  }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Waterfall */}
        <div className="card" onClick={() => handleDrillDown('Waterfall Chart', waterfall)} style={{ cursor: 'pointer' }}>
          <h3 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.125rem', fontWeight: 600 }}>Waterfall Chart (Mock)</h3>
          <div style={{ display: 'flex', alignItems: 'flex-end', height: '150px', gap: 'var(--spacing-2)', borderBottom: '1px solid var(--border-default)' }}>
            {waterfall.map((item, i) => {
              const height = Math.abs(item.value) / 10;
              const color = item.type === 'total' ? 'var(--color-primary-700)' : item.type === 'positive' ? 'var(--color-success-text)' : 'var(--color-error-text)';
              return (
                <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end' }}>
                  <div style={{ fontSize: '0.75rem', marginBottom: '4px' }}>{item.value}</div>
                  <div style={{ width: '100%', height: `${height}px`, backgroundColor: color, borderRadius: 'var(--radius-sm) var(--radius-sm) 0 0' }} />
                  <div style={{ fontSize: '0.7rem', marginTop: '4px', textAlign: 'center' }}>{item.category.split(' ')[0]}</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Heatmap */}
        <div className="card" onClick={() => handleDrillDown('Heatmap Chart', heatmap)} style={{ cursor: 'pointer' }}>
          <h3 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.125rem', fontWeight: 600 }}>Heatmap Chart (Mock)</h3>
          {heatmap && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
              {heatmap.values.map((row: number[], i: number) => (
                <div key={i} style={{ display: 'flex', gap: '2px' }}>
                  <div style={{ width: '80px', fontSize: '0.75rem', alignSelf: 'center' }}>{heatmap.y_labels[i]}</div>
                  {row.map((val: number, j: number) => {
                    const intensity = Math.min(val * 2, 100);
                    return (
                      <div key={j} style={{ 
                        flex: 1, 
                        height: '40px', 
                        backgroundColor: `color-mix(in srgb, var(--color-primary-600) ${intensity}%, var(--surface-default))`,
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center',
                        fontSize: '0.75rem',
                        color: intensity > 50 ? 'white' : 'inherit'
                      }}>
                        {val}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Timeseries */}
        <div className="card" onClick={() => handleDrillDown('Timeseries Chart', timeseries)} style={{ cursor: 'pointer' }}>
          <h3 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.125rem', fontWeight: 600 }}>Timeseries Chart (Mock)</h3>
          {timeseries && (
            <div style={{ height: '150px', position: 'relative', borderLeft: '1px solid var(--border-default)', borderBottom: '1px solid var(--border-default)' }}>
               <svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none">
                 {timeseries.series.map((s: any, idx: number) => {
                    const max = 100;
                    const pts = s.data.map((d: number, i: number) => `${(i / (s.data.length - 1)) * 100},${100 - (d / max * 100)}`).join(' ');
                    return (
                      <polyline key={idx} points={pts} fill="none" stroke={idx === 0 ? 'var(--color-primary-600)' : 'var(--color-warning-text)'} strokeWidth="2" />
                    );
                 })}
               </svg>
               <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 'var(--spacing-2)', fontSize: '0.75rem' }}>
                 {timeseries.timestamps.map((t: string, i: number) => (
                   <span key={i}>{t}</span>
                 ))}
               </div>
            </div>
          )}
        </div>

        {/* Eligibility Analysis */}
        <div className="card" onClick={() => handleDrillDown('Eligibility Analysis', eligibility)} style={{ cursor: 'pointer' }}>
          <h3 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.125rem', fontWeight: 600 }}>Eligibility Analysis</h3>
          {eligibility && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem' }}>
                <span>Eligible: {eligibility.eligible}</span>
                <span>Ineligible: {eligibility.ineligible}</span>
              </div>
              <div style={{ display: 'flex', height: '24px', borderRadius: 'var(--radius-sm)', overflow: 'hidden' }}>
                <div style={{ width: `${(eligibility.eligible / (eligibility.eligible + eligibility.ineligible)) * 100}%`, backgroundColor: 'var(--color-success-text)' }} />
                <div style={{ width: `${(eligibility.ineligible / (eligibility.eligible + eligibility.ineligible)) * 100}%`, backgroundColor: 'var(--color-error-text)' }} />
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Click for reasons breakdown</div>
            </div>
          )}
        </div>

        {/* Grid Explorer */}
        <div className="card" onClick={() => handleDrillDown('Grid Explorer', grid)} style={{ cursor: 'pointer' }}>
          <h3 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.125rem', fontWeight: 600 }}>Grid Explorer</h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-default)', textAlign: 'left' }}>
                  <th style={{ padding: 'var(--spacing-2)' }}>ID</th>
                  <th style={{ padding: 'var(--spacing-2)' }}>Name</th>
                  <th style={{ padding: 'var(--spacing-2)' }}>Status</th>
                  <th style={{ padding: 'var(--spacing-2)' }}>Load</th>
                </tr>
              </thead>
              <tbody>
                {grid.map((row, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border-default)' }}>
                    <td style={{ padding: 'var(--spacing-2)' }}>{row.id}</td>
                    <td style={{ padding: 'var(--spacing-2)' }}>{row.name}</td>
                    <td style={{ padding: 'var(--spacing-2)', color: row.status === 'Active' ? 'var(--color-success-text)' : row.status === 'Warning' ? 'var(--color-warning-text)' : 'var(--text-secondary)' }}>{row.status}</td>
                    <td style={{ padding: 'var(--spacing-2)' }}>{row.load}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Gates Dashboard */}
        <div className="card" onClick={() => handleDrillDown('Gates Dashboard', gates)} style={{ cursor: 'pointer' }}>
          <h3 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.125rem', fontWeight: 600 }}>Gates Dashboard</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
            {gates.map((gate, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center' }}>
                <div style={{ width: '140px', fontSize: '0.875rem', fontWeight: 500 }}>{gate.gate}</div>
                <div style={{ flex: 1, backgroundColor: 'var(--surface-muted)', height: '24px', position: 'relative', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ 
                    position: 'absolute', 
                    left: 0, 
                    width: `${gate.rate * 100}%`, 
                    height: '100%', 
                    backgroundColor: 'var(--color-primary-500)', 
                    borderRadius: 'var(--radius-sm)'
                  }} />
                </div>
                <div style={{ width: '50px', textAlign: 'right', fontSize: '0.875rem' }}>{(gate.rate * 100).toFixed(0)}%</div>
              </div>
            ))}
          </div>
        </div>

        {/* Data Quality Viewer */}
        <div className="card" onClick={() => handleDrillDown('Data Quality Viewer', dataQuality)} style={{ cursor: 'pointer' }}>
          <h3 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.125rem', fontWeight: 600 }}>Data Quality Viewer</h3>
          {dataQuality && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
              {dataQuality.dimensions.map((dim: string, i: number) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center' }}>
                  <div style={{ width: '100px', fontSize: '0.875rem' }}>{dim}</div>
                  <div style={{ flex: 1, backgroundColor: 'var(--surface-muted)', height: '16px', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ width: `${dataQuality.scores[i]}%`, backgroundColor: 'var(--color-success-text)', height: '100%', borderRadius: 'var(--radius-sm)' }} />
                  </div>
                  <div style={{ width: '40px', textAlign: 'right', fontSize: '0.75rem' }}>{dataQuality.scores[i]}%</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Universal Drill-down Modal */}
      {drillDown && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div className="card" style={{ width: '80%', maxWidth: '600px', maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-4)' }}>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 600 }}>{drillDown.title}</h3>
              <button className="btn" onClick={() => setDrillDown(null)}>Close</button>
            </div>
            <div style={{ overflowY: 'auto', flex: 1 }}>
              <pre style={{ backgroundColor: 'var(--surface-muted)', padding: 'var(--spacing-4)', borderRadius: 'var(--radius-md)', margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontSize: '0.875rem' }}>
                {JSON.stringify(drillDown.data, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
