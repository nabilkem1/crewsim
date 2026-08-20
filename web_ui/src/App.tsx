import { useState, useEffect } from 'react'
import { ConfigDashboard } from './features/config'
import { CalibrationDashboard } from './features/calibration'
import { ProcessingDashboard } from './features/processing'
import { ResultsDashboard } from './features/results'
import { RunManagementDashboard } from './features/runs'
import { AnalyticsDashboard } from './features/analytics'
import { ProvenanceDashboard } from './features/provenance'
import { JobQueue, GlobalErrorBoundary, NotificationProvider } from './features/jobs'

function App() {
  const [healthStatus, setHealthStatus] = useState<string>('Checking...')
  const [healthData, setHealthData] = useState<any>(null)
  const [activeTab, setActiveTab] = useState<string>('dashboard')
  const [isSearchOpen, setIsSearchOpen] = useState(false)
  const [isHelpOpen, setIsHelpOpen] = useState(false)

  const helpContent: Record<string, { title: string, description: string, features: string[] }> = {
    dashboard: { 
      title: 'Platform Overview', 
      description: 'This page shows high-level metrics and system health. Check this page to verify backend connectivity.',
      features: [
        'Total Active Runs: Tracks simulations currently executing.',
        'Average Queue Wait Time: Monitor processing bottlenecks.',
        'System Memory Usage: Resource utilization metrics.',
        'API Connection Status: Real-time backend liveness.'
      ]
    },
    config: { 
      title: 'Configuration Management', 
      description: 'Manage CrewSim policies and parameters.',
      features: [
        'Select a category to inspect its full JSON schema.',
        'Search across all parameters for specific values to edit.',
        'Validate configuration markers before executing runs.'
      ]
    },
    calibration: { 
      title: 'Calibration Pipeline', 
      description: 'Run historical data fitting.',
      features: [
        'Tune underlying engine parameters automatically.',
        'Click "Launch Calibration Job" to define target metrics.',
        'Track active and past calibration runs.'
      ]
    },
    processing: { 
      title: 'Simulation Processing', 
      description: 'Launch new simulation scenarios.',
      features: [
        'Run single deterministic scenarios.',
        'Launch batch simulations for stochastic modeling.',
        'Configure policy overrides prior to execution.'
      ]
    },
    runs: { 
      title: 'Run Management History', 
      description: 'Browse all historical runs.',
      features: [
        'View a searchable table of all past executions.',
        'Filter runs by status (Completed, Failed, Running).',
        'Quickly jump to results or logs for a specific run ID.'
      ]
    },
    jobs: { 
      title: 'Job Execution Queue', 
      description: 'Monitor active and queued background tasks.',
      features: [
        'Track live progress of simulations and calibrations.',
        'Cancel long-running or stuck background jobs.',
        'Retry previously failed executions.'
      ]
    },
    results: { 
      title: 'Simulation Results & Reporting', 
      description: 'View detailed outcome charts.',
      features: [
        'Analyze dynamic Gantt and Waterfall charts.',
        'Click on any chart to trigger Universal Drill-down.',
        'Download bulk raw JSON/CSV artifacts.'
      ]
    },
    analytics: { 
      title: 'Deep Cascade Analytics', 
      description: 'Analyze the ripple effects of drafting policies.',
      features: [
        'Compare multi-policy fatigue vs cost tradeoffs.',
        'View complex cascade summaries and analytical grids.',
        'Dive into shift timelines and schedule changes.'
      ]
    },
    provenance: { 
      title: 'Run Comparison & Provenance', 
      description: 'Track the lineage of results back to their configuration snapshot.',
      features: [
        'Diff two configurations side-by-side.',
        'Ensure reproducible runs through artifact tracking.',
        'Statistically compare two runs via T-Test.'
      ]
    }
  }

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setIsSearchOpen(prev => !prev)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  useEffect(() => {
    fetch('/api/health')
      .then(res => res.json())
      .then(data => {
        setHealthStatus(`API Status: ${data.status.toUpperCase()}`)
        setHealthData(data)
      })
      .catch(() => {
        setHealthStatus('API Status: DISCONNECTED')
        setHealthData(null)
      })
  }, [])

  return (
    <GlobalErrorBoundary>
      <NotificationProvider>
        <div className="app-container">
          <aside className="app-sidebar">
            <div className="app-sidebar-header">
              CrewSim
            </div>
            <nav className="app-nav" aria-label="Main Navigation">
              <a href="#" className="app-nav-item" role="button" tabIndex={0} aria-label="Navigate to Dashboard" onClick={(e) => { e.preventDefault(); setActiveTab('dashboard'); }}>Dashboard</a>
              <a href="#" className="app-nav-item" role="button" tabIndex={0} aria-label="Navigate to Configuration" onClick={(e) => { e.preventDefault(); setActiveTab('config'); }}>Configuration</a>
              <a href="#" className="app-nav-item" role="button" tabIndex={0} aria-label="Navigate to Calibration" onClick={(e) => { e.preventDefault(); setActiveTab('calibration'); }}>Calibration</a>
              <a href="#" className="app-nav-item" role="button" tabIndex={0} aria-label="Navigate to Processing" onClick={(e) => { e.preventDefault(); setActiveTab('processing'); }}>Processing</a>
              <a href="#" className="app-nav-item" role="button" tabIndex={0} aria-label="Navigate to Run Management" onClick={(e) => { e.preventDefault(); setActiveTab('runs'); }}>Run Management</a>
              <a href="#" className="app-nav-item" role="button" tabIndex={0} aria-label="Navigate to Runs and Jobs" onClick={(e) => { e.preventDefault(); setActiveTab('jobs'); }}>Runs & Jobs</a>
              <a href="#" className="app-nav-item" role="button" tabIndex={0} aria-label="Navigate to Results and Reports" onClick={(e) => { e.preventDefault(); setActiveTab('results'); }}>Results & Reports</a>
              <a href="#" className="app-nav-item" role="button" tabIndex={0} aria-label="Navigate to Cascade Analytics" onClick={(e) => { e.preventDefault(); setActiveTab('analytics'); }}>Cascade Analytics</a>
              <a href="#" className="app-nav-item" role="button" tabIndex={0} aria-label="Navigate to Comparison and Provenance" onClick={(e) => { e.preventDefault(); setActiveTab('provenance'); }}>Comparison & Provenance</a>
            </nav>
          </aside>
          
          <main className="app-main">
            <header className="app-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>{activeTab === 'config' ? 'Configuration Management' : activeTab === 'calibration' ? 'Calibration Pipeline' : activeTab === 'processing' ? 'Simulation Processing' : activeTab === 'runs' ? 'Run Management History' : activeTab === 'results' ? 'Simulation Results & Reporting' : activeTab === 'analytics' ? 'Deep Cascade Analytics' : activeTab === 'provenance' ? 'Run Comparison & Provenance' : activeTab === 'jobs' ? 'Job Execution Queue' : 'Platform Overview'}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <button 
                  onClick={() => setIsHelpOpen(true)}
                  aria-label="Help"
                  title="Page Help"
                  style={{
                    width: '24px', height: '24px', borderRadius: '50%', backgroundColor: 'var(--color-primary-500)', 
                    color: 'white', border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', 
                    cursor: 'pointer', fontWeight: 'bold', fontSize: '14px', padding: 0
                  }}
                >
                  ?
                </button>
                <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-500)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ padding: '0.25rem 0.5rem', backgroundColor: 'var(--color-neutral-100)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)' }}>Ctrl K</span> to search
                </div>
              </div>
            </header>
            <div className="app-content">
              {isHelpOpen && (
                <div style={{
                  position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                  backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 2000,
                  display: 'flex', justifyContent: 'center', alignItems: 'center'
                }} onClick={() => setIsHelpOpen(false)}>
                  <div style={{
                    backgroundColor: '#ffffff', padding: '2.5rem',
                    borderRadius: 'var(--radius-lg)', width: '100%', maxWidth: '550px',
                    boxShadow: '0 20px 40px rgba(0,0,0,0.15)', border: '1px solid var(--border-default)'
                  }} onClick={e => e.stopPropagation()}>
                    <h2 style={{ marginBottom: '1rem', color: 'var(--color-primary-600)', fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ backgroundColor: 'var(--color-primary-50)', color: 'var(--color-primary-700)', padding: '0.2rem 0.6rem', borderRadius: 'var(--radius-full)', fontSize: '1rem' }}>?</span>
                      {helpContent[activeTab]?.title} Help
                    </h2>
                    
                    <div style={{ color: 'var(--color-text-base)', lineHeight: 1.5, marginBottom: '2rem' }}>
                      <p style={{ marginBottom: '1.25rem', fontSize: '0.95rem' }}>
                        {helpContent[activeTab]?.description}
                      </p>
                      
                      <div style={{ backgroundColor: 'var(--color-neutral-50)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-neutral-200)' }}>
                        <h3 style={{ fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-neutral-500)', marginBottom: '0.75rem' }}>Key Features</h3>
                        <ul style={{ paddingLeft: '1.25rem', listStyleType: 'disc', margin: 0, fontSize: '0.9rem' }}>
                          {helpContent[activeTab]?.features.map((feat, idx) => (
                            <li key={idx} style={{ marginBottom: '0.5rem', color: 'var(--color-neutral-700)' }}>
                              {feat.includes(':') ? (
                                <>
                                  <strong style={{ color: 'var(--color-neutral-900)' }}>{feat.split(':')[0]}:</strong>{feat.split(':')[1]}
                                </>
                              ) : feat}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                      <button 
                        onClick={() => setIsHelpOpen(false)} 
                        style={{ 
                          padding: '0.6rem 1.5rem', borderRadius: 'var(--radius-md)', border: 'none', 
                          backgroundColor: 'var(--color-primary-600)', color: 'white', fontWeight: 500, cursor: 'pointer',
                          boxShadow: '0 2px 4px rgba(37, 99, 235, 0.2)'
                        }}
                      >
                        Got it
                      </button>
                    </div>
                  </div>
                </div>
              )}
              {isSearchOpen && (
                <div style={{
                  position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                  backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1000,
                  display: 'flex', justifyContent: 'center', alignItems: 'flex-start', paddingTop: '10vh'
                }} onClick={() => setIsSearchOpen(false)}>
                  <div style={{
                    backgroundColor: '#ffffff', padding: '1rem',
                    borderRadius: 'var(--radius-lg)', width: '100%', maxWidth: '600px',
                    boxShadow: '0 10px 25px rgba(0,0,0,0.1)'
                  }} onClick={e => e.stopPropagation()}>
                    <input 
                      autoFocus
                      type="text" 
                      placeholder="Search jobs, runs, configurations... (Placeholder)" 
                      style={{ 
                        width: '100%', padding: '0.75rem', fontSize: '1rem', 
                        border: '1px solid var(--color-primary-500)', borderRadius: 'var(--radius-md)',
                        outline: 'none', backgroundColor: 'var(--color-bg-subtle)', color: 'var(--color-text-base)'
                      }}
                    />
                    <div style={{ marginTop: '1rem', fontSize: '0.875rem', color: 'var(--color-neutral-500)', textAlign: 'center' }}>
                      Search functionality coming soon. Press Esc to close.
                    </div>
                  </div>
                </div>
              )}
              {activeTab === 'dashboard' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
                  <div className="card">
                    <h2>Welcome to CrewSim Platform</h2>
                    <p style={{ marginTop: '0.5rem', color: 'var(--color-neutral-500)' }}>
                      The backend API connection is active and ready.
                    </p>
                    <div style={{
                      marginTop: '1.5rem',
                      display: 'inline-block',
                      padding: '0.5rem 1rem',
                      backgroundColor: healthStatus.includes('HEALTHY') || healthStatus.includes('OK') ? 'var(--color-success-bg)' : 'var(--color-error-bg)',
                      color: healthStatus.includes('HEALTHY') || healthStatus.includes('OK') ? 'var(--color-success-text)' : 'var(--color-error-text)',
                      borderRadius: 'var(--radius-md)',
                      fontWeight: 500,
                      fontSize: '0.875rem'
                    }}>
                      {healthStatus}
                    </div>
                  </div>
                  
                  {healthData && (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 'var(--spacing-4)' }}>
                      <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '2rem' }}>
                        <div style={{ fontSize: '3rem', fontWeight: 700, color: 'var(--color-primary-600)', marginBottom: '0.5rem' }}>{healthData.kpis?.active_runs || 0}</div>
                        <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-600)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>Total Active Runs</div>
                      </div>
                      <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '2rem' }}>
                        <div style={{ fontSize: '3rem', fontWeight: 700, color: 'var(--color-primary-600)', marginBottom: '0.5rem' }}>{healthData.kpis?.avg_queue_wait_seconds || 0}s</div>
                        <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-600)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>Avg Queue Wait Time</div>
                      </div>
                      <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '2rem' }}>
                        <div style={{ fontSize: '3rem', fontWeight: 700, color: 'var(--color-primary-600)', marginBottom: '0.5rem' }}>{healthData.memory?.usage_percent || 0}%</div>
                        <div style={{ fontSize: '0.875rem', color: 'var(--color-neutral-600)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>System Memory Usage</div>
                      </div>
                    </div>
                  )}
                </div>
              )}
              {activeTab === 'config' && <ConfigDashboard />}
              {activeTab === 'calibration' && <CalibrationDashboard />}
              {activeTab === 'processing' && <ProcessingDashboard />}
              {activeTab === 'runs' && <RunManagementDashboard />}
              {activeTab === 'results' && <ResultsDashboard />}
              {activeTab === 'analytics' && <AnalyticsDashboard />}
              {activeTab === 'provenance' && <ProvenanceDashboard />}
              {activeTab === 'jobs' && <JobQueue />}
            </div>
          </main>
        </div>
      </NotificationProvider>
    </GlobalErrorBoundary>
  )
}

export default App
