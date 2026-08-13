import { PolicyComparison } from './PolicyComparison';
import { Summaries } from './Summaries';

/**
 * The chart grid that used to sit below this (Gantt, waterfall, heatmap,
 * timeseries, eligibility, grid, gates, data-quality) was driven entirely by
 * hardcoded API literals and has been removed with them.
 *
 * What replaced it: `PolicyComparison` reads the real scoreboard, paired
 * comparisons, gate V3 verdict and R* recommendation a batch processing run
 * already computes (crewsim.reporting.grid/kpis/paired/recommendation) and
 * that nothing previously surfaced -- the decision-support content an IOC
 * planner needs to pick a reserve policy, not another chart.
 */
export function ResultsDashboard() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-6)' }}>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 600 }}>Simulation Results &amp; Reporting</h1>
      <PolicyComparison />
      <Summaries />
    </div>
  );
}
