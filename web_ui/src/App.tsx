import { useState, useEffect } from 'react'
import { ConfigDashboard } from './features/config'
import { DataDashboard } from './features/data'
import { CalibrationDashboard } from './features/calibration'
import { ProcessingDashboard } from './features/processing'
import { ResultsDashboard } from './features/results'
import { AnalyticsDashboard } from './features/analytics'
import { GlobalErrorBoundary, NotificationProvider } from './features/jobs'
import { HealthDashboard } from './features/platform'
import airTransatLogo from './assets/air-transat-logo.svg'

/** The sidebar's items. `glyph` is what shows when the rail is collapsed --
 *  deliberately monochrome geometry rather than emoji, which render at
 *  inconsistent sizes and colours across platforms. */
const NAV_ITEMS: { id: string; label: string; glyph: string }[] = [
  { id: 'dashboard', label: 'Dashboard', glyph: '▣' },
  { id: 'config', label: 'Configuration', glyph: '⚙' },
  { id: 'data', label: 'Data', glyph: '▤' },
  { id: 'calibration', label: 'Calibration', glyph: '∿' },
  { id: 'processing', label: 'Processing', glyph: '▶' },
  { id: 'results', label: 'Results & Reports', glyph: '▦' },
  { id: 'analytics', label: 'Cascade Analytics', glyph: '⋔' },
];

const SIDEBAR_STORAGE_KEY = 'crewsim.sidebarCollapsed';

type Theme = 'light' | 'dark';
// Kept in sync with the inline script in index.html, which stamps
// `data-theme` on <html> BEFORE this file (or React) ever runs -- that is
// what prevents a flash of the wrong theme on load. Same storage key here.
const THEME_STORAGE_KEY = 'crewsim.theme';

function App() {
  const [activeTab, setActiveTab] = useState<string>('dashboard')
  const [isHelpOpen, setIsHelpOpen] = useState(false)
  // Read synchronously on first render: resolving it in an effect would paint
  // the expanded sidebar first and visibly snap shut on every page load.
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(
    () => localStorage.getItem(SIDEBAR_STORAGE_KEY) === 'true',
  )
  // Read from the DOM, not from localStorage a second time: the inline head
  // script already resolved stored-preference-or-OS-default and stamped it
  // on <html> before this component ever mounted, so re-deriving the same
  // answer here would just be a second, independent implementation of that
  // same fallback logic that could quietly drift from the first one.
  const [theme, setTheme] = useState<Theme>(
    () => (document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'),
  )

  useEffect(() => {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, String(isSidebarCollapsed))
  }, [isSidebarCollapsed])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem(THEME_STORAGE_KEY, theme)
  }, [theme])

  const helpContent: Record<string, { title: string, description: string, features: string[] }> = {
    dashboard: {
      title: 'Platform Overview',
      description: 'This page shows high-level metrics and system health. Check this page to verify backend connectivity.',
      features: [
        'Active runs and queued-job wait time: live from the jobs database.',
        'CPU/memory: reported only when the host metrics library is installed, never guessed.'
      ]
    },
    config: {
      title: 'Configuration Management',
      description: 'Inspect CrewSim policies and parameters. This page is read-only: values are changed in the files under configs/, never here.',
      features: [
        'Select a category to inspect its full JSON schema.',
        'Search across all parameters to find where a value is set.',
        'Validate: lists every [CONFIRM] placeholder still waiting on a business owner before a run.'
      ]
    },
    data: {
      title: 'Corpus Data',
      description: 'Browse the D1-D12 source tables and their quality gates.',
      features: [
        'Select a table on the left to page through its rows.',
        'Column types are the ones the loaders validate and cast to.',
        'Data Quality runs the real Sec6.2 gates against the configured corpus.'
      ]
    },
    calibration: {
      title: 'Calibration Pipeline',
      description: 'Fit the statistical models (severity regimes, sick-call arrivals, flight delays) to the historical corpus for one season.',
      features: [
        'Run Statistical Fitting: always runs the full pipeline and writes that season\'s parameter store.',
        'Run monitor: track active and past calibration runs, with their logs.',
        'Results: inspect the fitted parameters and their diagnostics.'
      ]
    },
    processing: {
      title: 'Simulation Processing',
      description: 'Simulate candidate reserve policies against the same set of random scenarios (common random numbers).',
      features: [
        'Single Run: the first selected policy over the chosen number of scenarios.',
        'Batch Run: every selected policy over the same scenarios, ready for a paired comparison.',
        'Choose the season and the scenario count before launching.'
      ]
    },

    results: {
      title: 'Simulation Results & Reporting',
      description: 'Compare candidate reserve policies on real simulated cost, risk and validity, to decide which one to run.',
      features: [
        'Scoreboard: E[cost], CVaR95, uncovered legs, eligibility and cascade rate per policy.',
        'Recommended reserve level (R*) by risk tolerance (lambda), from the same argmin used by gate V9.',
        'Gate V3 eligibility-validity banner: a recommendation is flagged, never hidden, when unvalidated.',
        'Pairwise paired-CRN comparisons with a 95% confidence interval and t-statistic.',
        'Every completed processing run, plus generated reports and parameter artifacts.'
      ]
    },
    analytics: {
      title: 'Deep Cascade Analytics',
      description:
        'What a draft costs after it is paid for. Drafting a crew member who holds a trip tomorrow breaks that trip, which re-enters as open time and has to be covered again. This page prices that whole chain from the cost ledger, reading a completed policy-grid run from Processing.',
      features: [
        'Summary: amplification — what a disruption costs once it cascades against one absorbed where it landed — plus cascade rate, chain sizes and the draft-tier mix that drives them. Switch policy with the chips at the top.',
        'Exemplar Chains: the costliest real chains, expandable to every ledger row traced back through root_event_uid to the disruption that started it.',
        'Policy Comparison: cascade rate, amplification and tier-2 draft counts side by side. All policies come from one CRN scenario set, so differences are policy effects, not sampling noise.',
        'Two populations, labelled on every figure: cascade RATE is whole-simulation (matching gate V4), chain ECONOMICS are measurement-window attributed so the dollars reconcile with E[cost].',
        'Chain size, not depth: the ledger records each row\'s root, never its immediate parent, so a deep chain and a wide one cannot be told apart in it. Size is what the data supports.',
        'A run with no cascades reports a measured zero and explains it. A run predating this feature says so instead — the two look identical in a chart and mean opposite things.',
        'No gate V4 verdict is shown on this page: check the gate status on Results & Reports before treating a cascade rate as validated.'
      ]
    },
  }

  return (
    <GlobalErrorBoundary>
      <NotificationProvider>
        <div className="app-container">
          <aside className={`app-sidebar${isSidebarCollapsed ? ' is-collapsed' : ''}`}>
            <div className="app-sidebar-header">
              <span className="app-sidebar-brand">
                <span className="app-logo-plate" title="Air Transat">
                  <img src={airTransatLogo} alt="Air Transat" />
                </span>
                <span className="app-sidebar-brand-label">CrewSim</span>
              </span>
              <button
                type="button"
                className="app-sidebar-toggle"
                onClick={() => setIsSidebarCollapsed(v => !v)}
                aria-expanded={!isSidebarCollapsed}
                aria-label={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                title={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              >
                {isSidebarCollapsed ? '»' : '«'}
              </button>
            </div>
            <nav className="app-nav" aria-label="Main Navigation">
              {NAV_ITEMS.map(item => (
                <a
                  key={item.id}
                  href="#"
                  className={`app-nav-item${activeTab === item.id ? ' is-active' : ''}`}
                  role="button"
                  tabIndex={0}
                  aria-current={activeTab === item.id ? 'page' : undefined}
                  aria-label={`Navigate to ${item.label}`}
                  // The label is hidden when collapsed, so the tooltip is the
                  // only way to identify a glyph without expanding.
                  title={isSidebarCollapsed ? item.label : undefined}
                  onClick={(e) => { e.preventDefault(); setActiveTab(item.id); }}
                >
                  <span className="app-nav-glyph" aria-hidden="true">{item.glyph}</span>
                  <span className="app-nav-label">{item.label}</span>
                </a>
              ))}
            </nav>
          </aside>

          <main className="app-main">
            <header className="app-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div>{activeTab === 'config' ? 'Configuration Management' : activeTab === 'data' ? 'Corpus Data' : activeTab === 'calibration' ? 'Calibration Pipeline' : activeTab === 'processing' ? 'Simulation Processing' : activeTab === 'results' ? 'Simulation Results & Reporting' : activeTab === 'analytics' ? 'Deep Cascade Analytics' : 'Platform Overview'}</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <button
                  type="button"
                  className="app-theme-toggle"
                  onClick={() => setTheme(t => (t === 'light' ? 'dark' : 'light'))}
                  aria-label={theme === 'light' ? 'Switch to Ops Console dark theme' : 'Switch to Light theme'}
                  title={theme === 'light' ? 'Switch to Ops Console dark theme' : 'Switch to Light theme'}
                >
                  <span aria-hidden="true">{theme === 'light' ? '☾' : '☀'}</span>
                  {theme === 'light' ? 'Dark' : 'Light'}
                </button>
                <button
                  onClick={() => setIsHelpOpen(true)}
                  aria-label="Help"
                  title="Page Help"
                  style={{
                    width: '24px', height: '24px', borderRadius: '50%', backgroundColor: 'var(--color-primary-500)',
                    color: 'var(--color-on-primary)', border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    cursor: 'pointer', fontWeight: 'bold', fontSize: '14px', padding: 0
                  }}
                >
                  ?
                </button>
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
                    backgroundColor: 'var(--surface-default)', padding: '2.5rem',
                    borderRadius: 'var(--radius-lg)', width: '100%', maxWidth: '550px',
                    boxShadow: 'var(--shadow-md)', border: '1px solid var(--border-default)',
                    // Pages with a long feature list (Cascade Analytics) ran
                    // taller than the viewport, cutting off the heading and
                    // the dismiss button with no way to reach either.
                    maxHeight: 'calc(100vh - 4rem)', overflowY: 'auto'
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
                          {helpContent[activeTab]?.features.map((feat, idx) => {
                            // Split at the FIRST colon only: everything after it
                            // is the description, colons included.
                            const colon = feat.indexOf(':')
                            return (
                              <li key={idx} style={{ marginBottom: '0.5rem', color: 'var(--color-neutral-700)' }}>
                                {colon >= 0 ? (
                                  <>
                                    <strong style={{ color: 'var(--color-neutral-900)' }}>{feat.slice(0, colon)}:</strong>{feat.slice(colon + 1)}
                                  </>
                                ) : feat}
                              </li>
                            )
                          })}
                        </ul>
                      </div>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                      <button 
                        onClick={() => setIsHelpOpen(false)} 
                        style={{ 
                          padding: '0.6rem 1.5rem', borderRadius: 'var(--radius-button)', border: 'none', 
                          backgroundColor: 'var(--action-bg)', color: 'var(--action-fg)', fontWeight: 500, cursor: 'pointer',
                          boxShadow: 'var(--shadow-sm)'
                        }}
                      >
                        Got it
                      </button>
                    </div>
                  </div>
                </div>
              )}
              {/* IMP-612: no global search (GET /api/platform/search is not
                  implemented) and no audit log view (nothing writes AuditLog
                  rows yet, see IMP-401) -- a permanently empty or "coming
                  soon" panel reads as a broken feature. */}
              {activeTab === 'dashboard' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
                  <HealthDashboard />
                </div>
              )}
              {activeTab === 'config' && <ConfigDashboard />}
              {activeTab === 'data' && <DataDashboard />}
              {activeTab === 'calibration' && <CalibrationDashboard />}
              {activeTab === 'processing' && <ProcessingDashboard />}
              {activeTab === 'results' && <ResultsDashboard />}
              {activeTab === 'analytics' && <AnalyticsDashboard />}
            </div>
          </main>
        </div>
      </NotificationProvider>
    </GlobalErrorBoundary>
  )
}

export default App
