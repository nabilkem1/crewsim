import React, { useState, useEffect } from 'react';
import { Modal } from '../../components/Modal';

/**
 * Every formula and process description below is read directly from real
 * fitted output (see api/routers/calibration.py::run_calibration_job and
 * calibration/{nhpp,regime,delays}.py) -- no example numbers, no invented
 * intermediate steps. Where a field wasn't previously exposed to this
 * endpoint (category levels, dispersion, base_delay_probability, the real
 * regime-HMM settings and fit report actually used), it was added to the job
 * result rather than approximated here.
 */

interface TransitionMatrix {
  [from: string]: { [to: string]: number };
}

interface RegimeSettings {
  n_restarts: number;
  max_iter: number;
  tol: number;
  transition_pseudocount: number;
  delay_threshold_minutes: number;
  sick_call_exposure: string;
}

interface StateEmission {
  delay_probability: number;
  cancel_probability: number;
  sick_rate_per_exposure: number;
  expected_share_of_days: number;
  mean_run_days: number | null;
}

interface RegimeHmm {
  station?: string;
  emissions?: Record<string, StateEmission>;
  degenerate_states?: string[];
  model_selection?: {
    by_n_states: Record<string, { log_likelihood: number; bic: number; aic: number }>;
    bic_preferred_n_states: number | null;
  };
  holdout?: { n_days: number; loglik_per_day: number | null; loglik_per_day_one_state: number | null };
}

interface GoodnessOfFit {
  model: string;
  log_likelihood: number | null;
  bic: number | null;
  n_days: number | null;
  converged: boolean | null;
  restarts_reaching_best: number | null;
  restarts: number | null;
  holdout?: { n_days: number; loglik_per_day: number | null; loglik_per_day_one_state: number | null } | null;
  bic_preferred_n_states: number | null;
}

interface MixtureComponent {
  weight: number;
  mean_mins: number;
  std_dev: number;
}

interface FittedData {
  transition_matrix?: TransitionMatrix;
  regime_pi0?: Record<string, number>;
  intensity_multipliers?: Record<string, number>;
  regime_hmm?: RegimeHmm;
  nhpp_coefficients?: Record<string, number>;
  nhpp_dispersion?: number | null;
  nhpp_category_levels?: Record<string, string[]>;
  base_delay_probability?: number | null;
  mixture_components?: MixtureComponent[];
  duration_lognorm?: { shape: number | null; scale: number | null };
}

interface CalibrationResults {
  status: string;
  season?: string;
  fitted?: FittedData;
  calibration_settings?: {
    regime_hmm?: RegimeSettings;
    delay_gmm_components?: number;
  };
  goodness_of_fit?: GoodnessOfFit | null;
  goodness_of_fit_note?: string;
}

const STATE_ORDER = ['CALM', 'NORMAL', 'DISRUPTED', 'SEVERE'];

const fmt = (v: number | null | undefined, digits = 4): string =>
  v === null || v === undefined || Number.isNaN(v) ? '—' : v.toFixed(digits);

const fmtPct = (v: number | null | undefined, digits = 1): string =>
  v === null || v === undefined ? '—' : `${(v * 100).toFixed(digits)}%`;

const codeBlock: React.CSSProperties = {
  backgroundColor: 'var(--surface-muted)',
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-md)',
  padding: 'var(--spacing-4)',
  fontFamily: 'var(--font-mono)',
  fontSize: '0.85rem',
  overflowX: 'auto',
  whiteSpace: 'pre',
  lineHeight: 1.7,
};

const sectionHeading: React.CSSProperties = {
  fontSize: '0.95rem',
  fontWeight: 700,
  marginTop: 'var(--spacing-6)',
  marginBottom: 'var(--spacing-2)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  color: 'var(--color-neutral-600)',
};

const table: React.CSSProperties = {
  borderCollapse: 'collapse',
  width: '100%',
  fontSize: '0.85rem',
};
const th: React.CSSProperties = {
  textAlign: 'left',
  padding: '0.4rem 0.75rem',
  borderBottom: '2px solid var(--border-default)',
  color: 'var(--color-neutral-600)',
};
const td: React.CSSProperties = {
  textAlign: 'left',
  padding: '0.4rem 0.75rem',
  borderBottom: '1px solid var(--border-default)',
  fontFamily: 'var(--font-mono)',
};

/**
 * "How this was calibrated" is a procedure, so it reads as a numbered
 * procedure. Each step is one action on one input, and where a step needs a
 * caveat that caveat is a sub-bullet rather than another clause in a
 * seven-line sentence.
 */
const Steps: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <ol
    style={{
      margin: 0,
      paddingLeft: '1.35rem',
      display: 'flex',
      flexDirection: 'column',
      gap: 'var(--spacing-3)',
      fontSize: '0.875rem',
      lineHeight: 1.6,
    }}
  >
    {children}
  </ol>
);

const Step: React.FC<{ title: string; children?: React.ReactNode }> = ({ title, children }) => (
  <li>
    <strong>{title}</strong>
    {children && <div style={{ marginTop: '0.25rem' }}>{children}</div>}
  </li>
);

const Bullets: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <ul
    style={{
      margin: '0.4rem 0 0',
      paddingLeft: '1.1rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.3rem',
      color: 'var(--color-neutral-600)',
    }}
  >
    {children}
  </ul>
);

/**
 * A worked example, computed from this run's own fitted values.
 *
 * Not illustrative round numbers: every figure shown here is arithmetic on
 * output already displayed above it, so the reader can check it against the
 * tables. An example with invented inputs would be indistinguishable from a
 * real one at a glance, which is the failure mode this whole panel exists to
 * avoid (see the module docstring).
 */
const WorkedExample: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div
    style={{
      marginTop: 'var(--spacing-4)',
      borderLeft: '3px solid var(--color-primary-500)',
      backgroundColor: 'var(--surface-muted)',
      borderRadius: '0 var(--radius-md) var(--radius-md) 0',
      padding: 'var(--spacing-3) var(--spacing-4)',
      fontSize: '0.875rem',
      lineHeight: 1.65,
    }}
  >
    <div
      style={{
        fontSize: '0.7rem',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        color: 'var(--color-primary-700, #1d4ed8)',
        marginBottom: '0.4rem',
      }}
    >
      Worked example — from this run's own numbers
    </div>
    {children}
  </div>
);

/** Inline monospace for a value quoted mid-sentence. */
const V: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <code style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{children}</code>
);

// ------------------------------------------------------------- result tables
// The summary panel used to render four of these as `JSON.stringify(..., 2)`
// inside a <pre>. That is a debug view: it shows the transport shape rather
// than the quantity, buries the numbers in punctuation, and gives a reader no
// way to compare a column down the page.

const cell: React.CSSProperties = {
  padding: '0.3rem 0.7rem',
  fontSize: '0.8125rem',
  fontFamily: 'var(--font-mono)',
  borderBottom: '1px solid var(--border-default)',
  whiteSpace: 'nowrap',
};

const headCell: React.CSSProperties = {
  padding: '0.3rem 0.7rem',
  fontSize: '0.7rem',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  color: 'var(--color-neutral-500)',
  borderBottom: '2px solid var(--border-default)',
  textAlign: 'left',
  whiteSpace: 'nowrap',
};

const num: React.CSSProperties = { ...cell, textAlign: 'right' };

const Scroller: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{ overflowX: 'auto' }}>{children}</div>
);

const Empty: React.FC<{ what: string }> = ({ what }) => (
  <div style={{ fontSize: '0.8125rem', color: 'var(--color-neutral-500)' }}>
    No {what} in this fit.
  </div>
);

/** Square from-state x to-state grid, with pi0 as a trailing column. */
const MatrixTable: React.FC<{
  matrix?: TransitionMatrix;
  pi0?: Record<string, number>;
}> = ({ matrix, pi0 }) => {
  if (!matrix || Object.keys(matrix).length === 0) return <Empty what="transition matrix" />;
  const states = Object.keys(matrix);
  return (
    <Scroller>
      <table style={table}>
        <thead>
          <tr>
            <th style={headCell}>from \ to</th>
            {states.map((s) => (
              <th key={s} style={{ ...headCell, textAlign: 'right' }}>{s}</th>
            ))}
            {pi0 && <th style={{ ...headCell, textAlign: 'right' }}>π₀</th>}
          </tr>
        </thead>
        <tbody>
          {states.map((from) => (
            <tr key={from}>
              <td style={{ ...cell, fontWeight: 700 }}>{from}</td>
              {states.map((to) => {
                const v = matrix[from]?.[to] ?? 0;
                return (
                  <td
                    key={to}
                    style={{
                      ...num,
                      // The diagonal is the persistence term -- the thing that
                      // makes runs of bad days cluster -- so it is worth
                      // finding at a glance.
                      fontWeight: from === to ? 700 : 400,
                      color: from === to ? 'var(--color-primary-700, #1d4ed8)' : undefined,
                    }}
                  >
                    {fmt(v, 3)}
                  </td>
                );
              })}
              {pi0 && <td style={{ ...num, color: 'var(--color-neutral-500)' }}>{fmtPct(pi0[from])}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </Scroller>
  );
};

const KeyValueTable: React.FC<{
  rows: { label: string; value: string; note?: string }[];
  columns: [string, string, string];
}> = ({ rows, columns }) => {
  if (rows.length === 0) return <Empty what="values" />;
  return (
    <Scroller>
      <table style={table}>
        <thead>
          <tr>
            <th style={headCell}>{columns[0]}</th>
            <th style={{ ...headCell, textAlign: 'right' }}>{columns[1]}</th>
            <th style={headCell}>{columns[2]}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <td style={cell}>{r.label}</td>
              <td style={num}>{r.value}</td>
              <td style={{ ...cell, color: 'var(--color-neutral-500)', fontFamily: 'inherit' }}>
                {r.note}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Scroller>
  );
};

/** GLM coefficients, intercept first, then largest effect downwards. */
const CoefficientTable: React.FC<{ coefficients?: Record<string, number> }> = ({
  coefficients,
}) => {
  const all = Object.entries(coefficients ?? {}).filter(([k]) => k !== 'alpha');
  if (all.length === 0) return <Empty what="coefficients" />;

  const intercept = all.filter(([k]) => k === 'Intercept');
  const rest = all
    .filter(([k]) => k !== 'Intercept')
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));

  return (
    <Scroller>
      <table style={table}>
        <thead>
          <tr>
            <th style={headCell}>Term</th>
            <th style={{ ...headCell, textAlign: 'right' }}>β</th>
            <th style={{ ...headCell, textAlign: 'right' }}>exp(β)</th>
            <th style={headCell}>Effect on rate</th>
          </tr>
        </thead>
        <tbody>
          {[...intercept, ...rest].map(([name, value]) => {
            const ratio = Math.exp(value);
            const isIntercept = name === 'Intercept';
            return (
              <tr key={name}>
                <td style={{ ...cell, fontWeight: isIntercept ? 700 : 400 }}>{name}</td>
                <td style={num}>
                  {value >= 0 && !isIntercept ? '+' : ''}
                  {fmt(value)}
                </td>
                <td style={num}>{fmt(ratio, 3)}</td>
                <td style={{ ...cell, fontFamily: 'inherit', color: 'var(--color-neutral-500)' }}>
                  {isIntercept
                    ? `baseline ${fmt(ratio, 3)} /day at every reference level`
                    : `x${fmt(ratio, 2)} vs reference`}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Scroller>
  );
};

const MixtureTable: React.FC<{
  components?: MixtureComponent[];
  baseProbability?: number | null;
}> = ({ components, baseProbability }) => {
  if (!components || components.length === 0) return <Empty what="mixture components" />;
  const expected = components.reduce((acc, c) => acc + c.weight * c.mean_mins, 0);
  return (
    <>
      <Scroller>
        <table style={table}>
          <thead>
            <tr>
              <th style={headCell}>Component</th>
              <th style={{ ...headCell, textAlign: 'right' }}>Weight</th>
              <th style={{ ...headCell, textAlign: 'right' }}>Mean (min)</th>
              <th style={{ ...headCell, textAlign: 'right' }}>Std dev (min)</th>
            </tr>
          </thead>
          <tbody>
            {components.map((c, i) => (
              <tr key={i}>
                <td style={cell}>{i + 1}</td>
                <td style={num}>{fmtPct(c.weight, 1)}</td>
                <td style={num}>{fmt(c.mean_mins, 1)}</td>
                <td style={num}>{fmt(c.std_dev, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Scroller>
      <div style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)', marginTop: '0.4rem' }}>
        P(delayed | NORMAL day) = {fmtPct(baseProbability, 2)} · weighted mean delay ={' '}
        {fmt(expected, 1)} min
      </div>
    </>
  );
};

const LognormalTable: React.FC<{ duration?: { shape: number | null; scale: number | null } }> = ({
  duration,
}) => {
  const shape = duration?.shape ?? null;
  const scale = duration?.scale ?? null;
  if (shape === null || scale === null) return <Empty what="duration fit" />;
  const mean = scale * Math.exp((shape * shape) / 2);
  return (
    <KeyValueTable
      columns={['Parameter', 'Value', '']}
      rows={[
        { label: 'σ (shape)', value: fmt(shape), note: 'spread on the log scale' },
        { label: 'scale', value: fmt(scale), note: `median = ${fmt(scale, 2)} days` },
        { label: 'mean', value: fmt(mean), note: `scale · exp(σ²/2) = ${fmt(mean, 2)} days` },
      ]}
    />
  );
};

// ---------------------------------------------------------------- Transition Matrix
const TransitionMatrixModal: React.FC<{ data: FittedData; settings?: RegimeSettings }> = ({
  data,
  settings,
}) => {
  const states = data.transition_matrix ? Object.keys(data.transition_matrix) : STATE_ORDER;

  // Derived from the fitted matrix, never assumed: prefer NORMAL as the row to
  // walk through, but fall back to whatever states this fit actually produced.
  const example = (() => {
    const m = data.transition_matrix;
    if (!m) return null;
    const state = states.includes('NORMAL') ? 'NORMAL' : states[0];
    const row = m[state];
    if (!row) return null;
    const entries = Object.entries(row);
    if (entries.length === 0) return null;
    const [likeliestNext, likeliestP] = entries.reduce((a, b) => (b[1] > a[1] ? b : a));
    const selfP = row[state] ?? 0;
    // Expected run length of a geometric holding time. Guard p=1, which would
    // divide by zero and render "Infinity days".
    const expectedRun = selfP >= 1 ? null : 1 / (1 - selfP);
    return { state, likeliestNext, likeliestP, selfP, expectedRun };
  })();

  return (
    <>
      <p>
        A 4-state Markov chain over daily severity, so a run generates <em>bad weeks</em>, not
        scattered bad days: yesterday's state directly shapes today's.
      </p>

      <h3 style={sectionHeading}>Formula</h3>
      <p>
        P(S<sub>t+1</sub> = j | S<sub>t</sub> = i): the probability of transitioning to state{' '}
        <code>j</code> tomorrow, given today's state is <code>i</code>. Fitted transition matrix
        (rows sum to 1):
      </p>
      <div style={{ overflowX: 'auto' }}>
        <table style={table}>
          <thead>
            <tr>
              <th style={th}>from \ to</th>
              {states.map((s) => (
                <th style={th} key={s}>{s}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {states.map((from) => (
              <tr key={from}>
                <td style={{ ...td, fontWeight: 700 }}>{from}</td>
                {states.map((to) => (
                  <td style={td} key={to}>{fmt(data.transition_matrix?.[from]?.[to], 3)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.regime_pi0 && (
        <>
          <p style={{ marginTop: 'var(--spacing-4)' }}>
            &pi;<sub>0</sub> -- the stationary distribution of the fitted chain, i.e. the long-run
            share of days in each state (used as day-0's starting distribution when a simulation
            has no "yesterday"):
          </p>
          <div style={codeBlock}>
            {states.map((s) => `${s.padEnd(11)} = ${fmtPct(data.regime_pi0?.[s])}`).join('\n')}
          </div>
        </>
      )}

      <h3 style={sectionHeading}>How this was calibrated (hidden Markov model)</h3>
      <Steps>
        <Step title="Build one row of observations per day at the base.">
          <V>
            flights, flights delayed{settings ? ` ≥ ${settings.delay_threshold_minutes} min` : ''},
            flights cancelled (D8) · sick calls (D4) · crew on duty (D2)
          </V>
          <Bullets>
            <li>
              The regime itself is never observed — no label is supplied (D9 is not an input).
            </li>
            <li>A day with no data is kept but carries no information; the chain runs through it.</li>
          </Bullets>
        </Step>

        <Step title="Assume each hidden state produces the day's observations.">
          <Bullets>
            <li>flight outcomes ~ Multinomial(flights; on-time, delayed q<sub>k</sub>, cancelled r<sub>k</sub>)</li>
            <li>sick calls ~ Poisson(crew on duty × λ<sub>k</sub>)</li>
            <li>tomorrow's state depends only on today's: P(S<sub>t+1</sub>=j | S<sub>t</sub>=i)</li>
          </Bullets>
        </Step>

        <Step title="Fit everything at once by maximum likelihood (Baum–Welch EM).">
          <Bullets>
            <li>
              E-step: forward–backward gives, for each day, the probability of each state given
              all days before and after it.
            </li>
            <li>M-step: re-estimate P, q, r, λ as posterior-weighted counts and rates.</li>
            {settings && (
              <li>
                {settings.n_restarts} starting points, best log-likelihood kept; transition counts
                smoothed with a pseudo-count of {settings.transition_pseudocount} so no row is
                ever empty or absorbing.
              </li>
            )}
          </Bullets>
        </Step>

        <Step title="Name the states and label every day.">
          States are ordered by severity (delay, cancellation and sick rates) and named CALM →
          SEVERE. The most likely state path (Viterbi) labels each day; the sick-call GLM and the
          delay model are then fitted on those labels.
        </Step>
      </Steps>

      {example && (
        <WorkedExample>
          <p style={{ margin: 0 }}>
            Read the matrix one row at a time. Today is <V>{example.state}</V>, so tomorrow is{' '}
            <V>{example.likeliestNext}</V> with probability{' '}
            <V>{fmt(example.likeliestP, 3)}</V> — the largest entry in that row.
          </p>
          <p style={{ marginBottom: 0 }}>
            The diagonal is what controls how much days cluster. <V>{example.state}</V> repeats
            with <V>{fmt(example.selfP, 3)}</V>
            {example.expectedRun !== null ? (
              <>
                , so a spell in it lasts{' '}
                <V>
                  1 / (1 − {fmt(example.selfP, 3)}) ≈ {fmt(example.expectedRun, 1)} days
                </V>{' '}
                on average
              </>
            ) : (
              ' — once entered, this fit never leaves it'
            )}
            . Independent daily draws would give no such persistence.
          </p>
        </WorkedExample>
      )}
    </>
  );
};

// ---------------------------------------------------------------- Intensity Multipliers
const IntensityMultipliersModal: React.FC<{ data: FittedData }> = ({ data }) => {
  const states = data.intensity_multipliers ? Object.keys(data.intensity_multipliers) : STATE_ORDER;

  // The most extreme state this fit actually produced, not an assumed SEVERE.
  const worked = (() => {
    const m = data.intensity_multipliers;
    if (!m) return null;
    const entries = Object.entries(m).filter(([, v]) => typeof v === 'number');
    if (entries.length === 0) return null;
    const [state, value] = entries.reduce((a, b) => (b[1] > a[1] ? b : a));
    const delta = (value - 1) * 100;
    const pctMore =
      Math.abs(delta) < 0.05
        ? 'indistinguishable from a NORMAL day in this fit'
        : `${Math.abs(delta).toFixed(0)}% ${delta > 0 ? 'more' : 'less'} disruption`;
    return { state, value, pctMore };
  })();

  return (
    <>
      <p>
        How much more often crew call in sick in each regime, relative to a typical NORMAL day.
      </p>

      <h3 style={sectionHeading}>Formula</h3>
      <div style={codeBlock}>
        {'multiplier[state] = λ[state] / λ[NORMAL]   (λ = sick calls per crew on duty per day)\n\n'}
        {states.map((s) => `multiplier[${s.padEnd(10)}] = ${fmt(data.intensity_multipliers?.[s], 3)}`).join('\n')}
      </div>
      <p>
        A SEVERE multiplier of {fmt(data.intensity_multipliers?.SEVERE, 2)} means a SEVERE day
        carries {fmt(data.intensity_multipliers?.SEVERE, 1)}&times; the sick-call rate of a
        typical NORMAL day.
      </p>

      <h3 style={sectionHeading}>How this was calibrated</h3>
      <Steps>
        <Step title="Read λ for each state from the regime hidden Markov model.">
          λ is the HMM's own sick-call emission rate, estimated jointly with the transition
          matrix — no separate re-clustering of days.
        </Step>
        <Step title="Express it per state.">
          One rate per state, weighted by each day's posterior probability of being in it.
        </Step>
        <Step title="Divide each by the NORMAL mean.">
          That makes <V>NORMAL = 1.000</V> by construction, so every other state reads directly
          as "this many times a normal day".
        </Step>
      </Steps>

      <div
        style={{
          marginTop: 'var(--spacing-4)',
          fontSize: '0.875rem',
          lineHeight: 1.6,
        }}
      >
        <strong>What this is not used for.</strong>
        <Bullets>
          <li>
            It is a <em>descriptive</em> summary of how the four states differ in severity.
          </li>
          <li>
            It does <strong>not</strong> feed sick-call generation. That uses the NHPP GLM's own{' '}
            <V>regime</V> coefficient instead — applying both would count the same regime effect
            twice, through two separate channels.
          </li>
        </Bullets>
      </div>

      {worked && (
        <WorkedExample>
          <p style={{ margin: 0 }}>
            <V>{worked.state}</V> has a multiplier of <V>{fmt(worked.value, 3)}</V>, so a{' '}
            <V>{worked.state}</V> day carries <V>{fmt(worked.value, 1)}×</V> the sick-call rate
            of a typical NORMAL day — {worked.pctMore}.
          </p>
        </WorkedExample>
      )}
    </>
  );
};

// ---------------------------------------------------------------- NHPP Coefficients
const NhppModal: React.FC<{ data: FittedData }> = ({ data }) => {
  const coefs = data.nhpp_coefficients ?? {};
  const entries = Object.entries(coefs).filter(([k]) => k !== 'alpha');
  const intercept = coefs.Intercept ?? 0;
  const dispersion = data.nhpp_dispersion;
  const alpha = dispersion !== null && dispersion !== undefined ? dispersion - 1 : null;
  const levels = data.nhpp_category_levels ?? {};

  // Arithmetic on the fitted coefficients above -- the reader can check both
  // lines against the code block. `swing` is whichever level moves the rate
  // most in this fit, so the example does not assume a covariate exists.
  const worked = (() => {
    if (coefs.Intercept === undefined) return null;
    const baseline = Math.exp(intercept);
    const others = entries.filter(([k]) => k !== 'Intercept');
    const swing =
      others.length > 0
        ? others.reduce((a, b) => (Math.abs(b[1]) > Math.abs(a[1]) ? b : a))
        : null;
    return {
      intercept,
      baseline,
      swing: swing ? { name: swing[0], value: swing[1] } : null,
      swingLambda: swing ? Math.exp(intercept + swing[1]) : null,
    };
  })();

  return (
    <>
      <p>
        The daily sick-call arrival rate for a given day / base / fleet / position combination.
      </p>

      <h3 style={sectionHeading}>Formula</h3>
      <p>
        &lambda; = exp(&beta;<sub>0</sub> + &sum; &beta;<sub>i</sub>&middot;1[covariate = i]), a
        Negative Binomial GLM. Fitted coefficients (every non-reference dummy level; the
        reference level for each covariate contributes 0 and is listed below):
      </p>
      <div style={codeBlock}>
        {`Intercept (β₀) = ${fmt(intercept)}\n\n`}
        {entries
          .filter(([k]) => k !== 'Intercept')
          .map(([k, v]) => `${k.padEnd(28)} = ${v >= 0 ? '+' : ''}${fmt(v)}`)
          .join('\n')}
      </div>

      {Object.keys(levels).length > 0 && (
        <>
          <p style={{ marginTop: 'var(--spacing-4)' }}>
            Reference (dropped, contributes 0) level per covariate -- the alphabetically-first
            level observed while fitting:
          </p>
          <div style={codeBlock}>
            {Object.entries(levels)
              .map(([k, v]) => `${k.padEnd(14)} reference = ${v[0]}   (all levels: ${v.join(', ')})`)
              .join('\n')}
          </div>
        </>
      )}

      <p style={{ marginTop: 'var(--spacing-4)' }}>
        Variance (Negative Binomial, NB2): Var = &lambda; + &alpha;&middot;&lambda;&sup2;, with
        this fit's dispersion &alpha; = {alpha === null ? '—' : fmt(alpha, 6)}{' '}
        {alpha !== null && (alpha <= 1e-6 ? '(≈ 0 → effectively Poisson here)' : '(overdispersed relative to Poisson)')}
      </p>

      <h3 style={sectionHeading}>How this was calibrated</h3>
      <Steps>
        <Step title="Build one observation per (day × base × fleet × position).">
          The response is that cell's observed sick-call count for that day.
        </Step>
        <Step title="Regress it on 6 covariates.">
          <Bullets>
            <li>season</li>
            <li>day-of-week</li>
            <li>base</li>
            <li>fleet</li>
            <li>position</li>
            <li>the severity-regime state fitted above</li>
          </Bullets>
        </Step>
        <Step title="Fit by maximum likelihood with statsmodels.">
          Each categorical covariate becomes dummy variables; one level per covariate is dropped
          as the reference and is folded into the intercept.
        </Step>
        <Step title="Use Negative Binomial, not Poisson.">
          Sick-call counts are <em>overdispersed</em> in the historical data — variance exceeds
          the mean.
          <Bullets>
            <li>
              Poisson forces <V>variance = mean</V>, which would understate real day-to-day
              volatility and make reserve cover look safer than it is.
            </li>
            <li>
              Absence <em>duration</em> is fit separately (see the lognormal section), on the
              same underlying absence records.
            </li>
          </Bullets>
        </Step>
      </Steps>

      {worked && (
        <WorkedExample>
          <p style={{ margin: 0 }}>
            With every covariate at its reference level, all dummies are 0 and only the intercept
            survives:
          </p>
          <div style={{ ...codeBlock, marginTop: '0.5rem', marginBottom: '0.5rem' }}>
            {`λ = exp(β₀) = exp(${fmt(worked.intercept)}) = ${fmt(worked.baseline, 3)} sick calls/day`}
          </div>
          {worked.swing && (
            <>
              <p style={{ margin: 0 }}>
                Add the largest fitted coefficient, <V>{worked.swing.name}</V> ={' '}
                <V>
                  {worked.swing.value >= 0 ? '+' : ''}
                  {fmt(worked.swing.value)}
                </V>
                :
              </p>
              <div style={{ ...codeBlock, marginTop: '0.5rem', marginBottom: '0.5rem' }}>
                {`λ = exp(${fmt(worked.intercept)} ${worked.swing.value >= 0 ? '+' : '−'} ${fmt(Math.abs(worked.swing.value))}) = ${fmt(worked.swingLambda!, 3)} sick calls/day`}
              </div>
              <p style={{ margin: 0 }}>
                Because the link is exponential, coefficients multiply rather than add: that one
                level scales the rate by <V>×{fmt(Math.exp(worked.swing.value), 2)}</V>.
              </p>
            </>
          )}
        </WorkedExample>
      )}
    </>
  );
};

// ---------------------------------------------------------------- Flight Delay Mixture
const DelayMixtureModal: React.FC<{ data: FittedData; nComponents?: number }> = ({
  data,
  nComponents,
}) => {
  const components = data.mixture_components ?? [];

  const worked = (() => {
    if (components.length === 0) return null;
    const expectedDelay = components.reduce((acc, c) => acc + c.weight * c.mean_mins, 0);
    const terms = components
      .map((c) => `${fmt(c.weight, 2)}×${fmt(c.mean_mins, 0)}`)
      .join(' + ');
    const longestIdx = components.reduce(
      (best, c, i) => (c.mean_mins > components[best].mean_mins ? i : best),
      0,
    );
    const p = data.base_delay_probability;
    return {
      expectedDelay,
      terms,
      per100: p === null || p === undefined ? '—' : (p * 100).toFixed(0),
      longest:
        components.length > 1 ? { ...components[longestIdx], index: longestIdx + 1 } : null,
    };
  })();

  return (
    <>
      <p>Whether a flight is delayed on a normal day, and how long the delay runs if it is.</p>

      <h3 style={sectionHeading}>Formula</h3>
      <div style={codeBlock}>
        {`P(delayed | NORMAL-regime day) = ${fmtPct(data.base_delay_probability, 2)}\n\n`}
        {'f(duration | delayed) = Σₖ wₖ · N(duration ; μₖ, σₖ²)\n\n'}
        {components
          .map(
            (c, i) =>
              `component ${i + 1}: w=${fmt(c.weight, 3)}  μ=${fmt(c.mean_mins, 1)} min  σ=${fmt(c.std_dev, 1)} min`,
          )
          .join('\n')}
      </div>

      <h3 style={sectionHeading}>How this was calibrated</h3>
      <Steps>
        <Step title="Measure how often a flight is delayed at all.">
          <V>base_delay_probability</V> is the empirical fraction of flights with a positive delay
          on <strong>NORMAL-regime days</strong> in the fitting window.
          <Bullets>
            <li>
              NORMAL-only, so the baseline is not inflated by the disrupted days the regime model
              already accounts for separately.
            </li>
          </Bullets>
        </Step>
        <Step title="Fit how long a delay runs, given that it happened.">
          A {nComponents ?? components.length}-component Gaussian Mixture Model over{' '}
          <strong>every delayed flight in the season, any regime</strong>, via
          Expectation-Maximization (<V>sklearn.GaussianMixture</V>).
          <Bullets>
            <li>
              A mixture rather than one bell curve because delays are multi-modal in practice: a
              short turnaround slip and a long IROPS cascade are different processes, and a single
              Normal would average them into a shape matching neither.
            </li>
          </Bullets>
        </Step>
        <Step title="Sort components by mean.">
          Component 1 is always the shortest-delay mode and the last is always the longest, so
          the ordering is stable across refits and two runs stay comparable.
        </Step>
      </Steps>

      {worked && (
        <WorkedExample>
          <p style={{ margin: 0 }}>
            Two independent questions, answered by the two halves above.
          </p>
          <Bullets>
            <li>
              <strong>Does it slip?</strong> On a NORMAL day, about{' '}
              <V>{worked.per100}</V> of every 100 flights are delayed.
            </li>
            <li>
              <strong>By how much?</strong> Averaging the components by weight —{' '}
              <V>
                {worked.terms} = {fmt(worked.expectedDelay, 1)} min
              </V>{' '}
              — is the mean delay <em>given</em> one occurred.
            </li>
            {worked.longest && (
              <li>
                The heavy tail lives in component {worked.longest.index}:{' '}
                <V>μ = {fmt(worked.longest.mean_mins, 0)} min</V> carrying{' '}
                <V>{fmtPct(worked.longest.weight, 0)}</V> of the weight.
              </li>
            )}
          </Bullets>
        </WorkedExample>
      )}
    </>
  );
};

// ---------------------------------------------------------------- Absence Duration
const DurationLognormalModal: React.FC<{ data: FittedData }> = ({ data }) => {
  const shape = data.duration_lognorm?.shape ?? null;
  const scale = data.duration_lognorm?.scale ?? null;
  const mean = shape !== null && scale !== null ? scale * Math.exp((shape * shape) / 2) : null;
  return (
    <>
      <p>How long a sick-call absence runs, once it starts.</p>

      <h3 style={sectionHeading}>Formula</h3>
      <div style={codeBlock}>
        {'f(x; σ, scale) = 1 / (x·σ·√(2π)) · exp( -(ln x - ln scale)² / (2σ²) )\n\n'}
        {`σ (shape) = ${fmt(shape)}\n`}
        {`scale     = ${fmt(scale)}  (this is also the median, in days)\n`}
        {mean !== null && `mean      = scale · exp(σ²/2) = ${fmt(mean, 2)} days`}
      </div>

      <h3 style={sectionHeading}>How this was calibrated</h3>
      <Steps>
        <Step title="Take the real D4 absence durations, in days.">
          Only absences with a <strong>positive</strong> duration — a zero-day absence carries no
          duration to fit.
        </Step>
        <Step title="Fit by maximum likelihood with scipy.stats.lognorm.fit.">
          Two free parameters: <V>σ</V> (shape) and <V>scale</V>.
        </Step>
        <Step title="Pin the location parameter at 0.">
          A duration cannot be negative.
          <Bullets>
            <li>
              Left free, the fit could slide the whole distribution off zero to compensate for a
              poor fit elsewhere, buying likelihood with a physically impossible shape.
            </li>
          </Bullets>
        </Step>
        <Step title="Why lognormal, and not Normal.">
          Absence durations are strongly right-skewed — most are short, a few run very long.
          <Bullets>
            <li>
              A symmetric family would miss that tail, and the tail is the part that actually
              strands a pairing.
            </li>
          </Bullets>
        </Step>
      </Steps>

      {shape !== null && scale !== null && (
        <WorkedExample>
          <Bullets>
            <li>
              <strong>Median = scale = <V>{fmt(scale, 2)} days</V>.</strong> Half of all absences
              finish at or below this.
            </li>
            {mean !== null && (
              <li>
                <strong>
                  Mean = scale · exp(σ²/2) = <V>{fmt(mean, 2)} days</V>.
                </strong>{' '}
                {mean > scale
                  ? 'The mean sits above the median — that gap is the long tail, and it is exactly why planning to the average understates cover.'
                  : 'Mean and median are close in this fit, so the tail is mild.'}
              </li>
            )}
          </Bullets>
        </WorkedExample>
      )}
    </>
  );
};

const HelpButton: React.FC<{ onClick: () => void }> = ({ onClick }) => (
  <button
    onClick={onClick}
    style={{
      background: 'var(--color-neutral-200)', border: 'none', borderRadius: '50%',
      width: '18px', height: '18px', fontSize: '0.7rem', fontWeight: 'bold',
      cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: 'var(--color-neutral-700)', flexShrink: 0,
    }}
    title="Formula and calibration process"
  >
    ?
  </button>
);

const SectionHeader: React.FC<{ title: string; onHelp: () => void }> = ({ title, onHelp }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-2)' }}>
    <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>{title}</div>
    <HelpButton onClick={onHelp} />
  </div>
);

type ModalKey = 'transition' | 'multipliers' | 'nhpp' | 'mixture' | 'duration' | null;

export const ResultsInspector: React.FC<{ initialJobId?: string }> = ({ initialJobId = '' }) => {
  const [jobId, setJobId] = useState(initialJobId);
  const [results, setResults] = useState<CalibrationResults | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openModal, setOpenModal] = useState<ModalKey>(null);

  const fetchResultsForJob = async (id: string) => {
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const res = await fetch(`/api/calibration/${id}/results`);
      if (res.ok) {
        const data = await res.json();
        setResults(data);
      } else {
        setError('Results not found or job incomplete.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch results.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialJobId) {
      setJobId(initialJobId);
      fetchResultsForJob(initialJobId);
    }
  }, [initialJobId]);

  const fitted = results?.fitted;
  const settings = results?.calibration_settings;

  const modalTitles: Record<Exclude<ModalKey, null>, string> = {
    transition: 'Transition Matrix (Markov States)',
    multipliers: 'Intensity Multipliers',
    nhpp: 'NHPP Coefficients (sick-call arrival intensity)',
    mixture: 'Flight Delay Mixture',
    duration: 'Absence Duration (Lognormal)',
  };

  return (
    <div>
      <h2 style={{ marginBottom: 'var(--spacing-2)', fontSize: '1.25rem', fontWeight: 600 }}>Results Inspector</h2>
      <div style={{ marginBottom: 'var(--spacing-4)', color: 'var(--color-neutral-500)', fontSize: '0.875rem', fontFamily: 'var(--font-mono)' }}>
        Job ID: {jobId || 'None'}
      </div>

      {loading && (
        <div style={{ color: 'var(--color-neutral-500)', fontSize: '0.875rem', marginBottom: 'var(--spacing-4)' }}>
          Loading results...
        </div>
      )}

      {error && (
        <div style={{ color: 'var(--color-error-text)', fontSize: '0.875rem', marginBottom: 'var(--spacing-4)' }}>
          {error}
        </div>
      )}

      {results && (
        <div style={{ backgroundColor: 'var(--surface-muted)', padding: 'var(--spacing-4)', borderRadius: 'var(--radius-md)' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 'var(--spacing-3)' }}>Calibration Output</h3>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-4)', marginBottom: 'var(--spacing-4)' }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)', textTransform: 'uppercase' }}>Status</div>
              <div style={{ fontWeight: 500 }}>{results.status}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)', textTransform: 'uppercase' }}>Season</div>
              <div style={{ fontWeight: 500 }}>{results.season ?? '—'}</div>
            </div>
          </div>

          {/*
            Goodness of fit is reported as absent rather than invented. This panel
            used to show a "Log Likelihood" of -1204.45 that the pipeline never
            produced, next to a convergence chart generated by an arithmetic
            recurrence. Both are gone; run_pipeline reports no likelihood or
            iteration history, so this says so.
          */}
          {results.goodness_of_fit == null && results.goodness_of_fit_note && (
            <div style={{ fontSize: '0.8125rem', color: 'var(--color-neutral-600)', borderLeft: '3px solid var(--border-default)', paddingLeft: 'var(--spacing-3)', marginBottom: 'var(--spacing-4)' }}>
              <strong>Goodness of fit: not reported.</strong> {results.goodness_of_fit_note}
            </div>
          )}
          {results.goodness_of_fit && (
            <div style={{ fontSize: '0.8125rem', color: 'var(--color-neutral-600)', borderLeft: '3px solid var(--border-default)', paddingLeft: 'var(--spacing-3)', marginBottom: 'var(--spacing-4)' }}>
              <strong>Goodness of fit ({results.goodness_of_fit.model}):</strong>{' '}
              log-likelihood {fmt(results.goodness_of_fit.log_likelihood, 1)}, BIC{' '}
              {fmt(results.goodness_of_fit.bic, 1)} over {results.goodness_of_fit.n_days ?? '—'} days;{' '}
              {results.goodness_of_fit.restarts_reaching_best ?? '—'}/{results.goodness_of_fit.restarts ?? '—'}{' '}
              restarts reached the best optimum
              {results.goodness_of_fit.converged === false ? ' (iteration cap hit — not converged)' : ''}.
              {results.goodness_of_fit.holdout?.loglik_per_day != null && (
                <>
                  {' '}Holdout log-likelihood per day {fmt(results.goodness_of_fit.holdout.loglik_per_day, 2)} vs{' '}
                  {fmt(results.goodness_of_fit.holdout.loglik_per_day_one_state, 2)} for a model with no regimes.
                </>
              )}
              {results.goodness_of_fit.bic_preferred_n_states != null && (
                <> BIC prefers {results.goodness_of_fit.bic_preferred_n_states} state(s).</>
              )}{' '}
              {results.goodness_of_fit_note}
            </div>
          )}

          {fitted && (
            <div style={{ maxHeight: '400px', overflowY: 'auto', borderTop: '1px solid var(--border-default)', paddingTop: 'var(--spacing-4)', display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>

              <div>
                <SectionHeader title="Transition Matrix (Markov States)" onHelp={() => setOpenModal('transition')} />
                <MatrixTable matrix={fitted.transition_matrix} pi0={fitted.regime_pi0} />
              </div>

              {fitted.regime_hmm?.emissions && (
                <div>
                  <SectionHeader title="Regime HMM — what each state looks like" onHelp={() => setOpenModal('transition')} />
                  <KeyValueTable
                    columns={['State', 'P(delayed) · P(cancelled) · sick/crew-day', 'share of days']}
                    rows={STATE_ORDER.filter((s) => fitted.regime_hmm?.emissions?.[s]).map((s) => {
                      const e = fitted.regime_hmm!.emissions![s];
                      return {
                        label: s,
                        value: `${fmt(e.delay_probability, 3)} · ${fmt(e.cancel_probability, 4)} · ${fmt(e.sick_rate_per_exposure, 4)}`,
                        note: `${fmtPct(e.expected_share_of_days)}${fitted.regime_hmm?.degenerate_states?.includes(s) ? ' (near-empty)' : ''}`,
                      };
                    })}
                  />
                </div>
              )}

              <div>
                <SectionHeader title="Intensity Multipliers" onHelp={() => setOpenModal('multipliers')} />
                <KeyValueTable
                  rows={Object.entries(fitted.intensity_multipliers ?? {}).map(([k, v]) => ({
                    label: k,
                    value: fmt(v, 3),
                    // NORMAL is the denominator, so it is 1.000 by construction
                    // rather than a fitted result.
                    note: k === 'NORMAL' ? 'reference' : `${fmt(v, 2)}x a NORMAL day`,
                  }))}
                  columns={['State', 'Multiplier', '']}
                />
              </div>

              <div>
                <SectionHeader title="NHPP Coefficients" onHelp={() => setOpenModal('nhpp')} />
                <CoefficientTable coefficients={fitted.nhpp_coefficients} />
              </div>

              <div>
                <SectionHeader title="Flight Delay Mixture" onHelp={() => setOpenModal('mixture')} />
                <MixtureTable
                  components={fitted.mixture_components}
                  baseProbability={fitted.base_delay_probability}
                />
              </div>

              <div>
                <SectionHeader title="Absence Duration (Lognormal)" onHelp={() => setOpenModal('duration')} />
                <LognormalTable duration={fitted.duration_lognorm} />
              </div>
            </div>
          )}
        </div>
      )}

      {openModal && fitted && (
        <Modal title={modalTitles[openModal]} onClose={() => setOpenModal(null)}>
          {openModal === 'transition' && (
            <TransitionMatrixModal data={fitted} settings={settings?.regime_hmm} />
          )}
          {openModal === 'multipliers' && <IntensityMultipliersModal data={fitted} />}
          {openModal === 'nhpp' && <NhppModal data={fitted} />}
          {openModal === 'mixture' && (
            <DelayMixtureModal data={fitted} nComponents={settings?.delay_gmm_components} />
          )}
          {openModal === 'duration' && <DurationLognormalModal data={fitted} />}
        </Modal>
      )}
    </div>
  );
};
