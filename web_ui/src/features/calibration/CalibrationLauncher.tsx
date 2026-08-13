import React, { useState, useEffect } from 'react';
import { apiFetch, apiPost, errorMessage } from '../../api/client';
import { ErrorPanel } from '../../components/StatusPanel';

/**
 * `<season>_<yyyymmddhhmmss>_<short id>` -- e.g. winter_sun_20260810143012_4f2a91.
 *
 * Replaces a free-text "Calibration Run Identifier" the user had to fill in.
 * A name typed by hand sorts arbitrarily, collides with the next one, and says
 * nothing the run does not already know: the season is the single input that
 * distinguishes two fits, and the timestamp orders them. The short random
 * suffix keeps two runs of the same season in the same second apart.
 */
function runName(season: string): string {
  const d = new Date();
  const p = (n: number, width = 2) => String(n).padStart(width, '0');
  const stamp =
    `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}` +
    `${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
  // crypto.randomUUID is available in every browser this app targets; its
  // first block is 8 hex chars, of which 6 is plenty to disambiguate.
  const short = crypto.randomUUID().replace(/-/g, '').slice(0, 6);
  return `${season || 'unset'}_${stamp}_${short}`;
}

export const CalibrationLauncher: React.FC = () => {
  // Each season gets its own independent fit: its own regime/NHPP/delay model
  // and its own params_v<version>_<season>.json.
  //
  // Preselected from configs/base.yaml -> scope.season rather than offered as
  // a "use the configured default" entry. That option was a name for a value
  // it did not show, so the form could be submitted without the reader ever
  // learning which season the fit would run against -- and the answer only
  // appeared afterwards, in the result.
  const [season, setSeason] = useState('');
  const [seasons, setSeasons] = useState<string[]>([]);
  const [launching, setLaunching] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);


  useEffect(() => {
    apiFetch<{ seasons: string[]; current: string }>('/config/seasons')
      .then((d) => {
        setSeasons(d.seasons);
        // Only if the user has not already picked one -- this resolves after
        // first paint, and clobbering a deliberate choice would be worse than
        // an empty select.
        setSeason((cur) => cur || d.current);
      })
      .catch((e) => setError(errorMessage(e)));
  }, []);

  // What each fit is FOR, in the simulation's terms -- these labels named the
  // statistical technique and left the reader to guess what it drives.
  const availableModels = [
    {
      id: 'transition_matrix',
      label: 'Transition Matrix (Markov States)',
      purpose: 'Makes disruption cluster into bad weeks instead of scattered bad days.',
    },
    {
      id: 'intensity_multipliers',
      label: 'Intensity Multipliers',
      purpose: 'Measures how much worse each severity regime is than a normal day.',
    },
    {
      id: 'nhpp_covariates',
      label: 'NHPP Covariates (MLE Fit)',
      purpose: 'Sets how many crew call in sick, by season, weekday, base, fleet and regime.',
    },
    {
      id: 'mixture_dist',
      label: 'Mixture Dist Params',
      purpose: 'Sets how often a flight is delayed and how long the delay runs.',
    },
    {
      id: 'lognormal_dist',
      label: 'Lognormal Dist Params',
      purpose: 'Sets how many days an absence lasts once it starts.',
    },
  ];

  const handleLaunch = async (e: React.FormEvent) => {
    e.preventDefault();
    setLaunching(true);
    setError(null);
    setJobId(null);
    try {
      // `dataset: 'all_corpus_files'` used to be sent here and silently
      // discarded by the backend, along with the model selection. The API now
      // rejects anything it cannot honour, so this sends only real inputs.
      const data = await apiPost<{ id: string }>('/calibration/jobs', {
        name: runName(season),
        season,
        models_to_fit: availableModels.map(m => m.id),
      });
      setJobId(data.id);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLaunching(false);
    }
  };

  return (
    <div className="card">
      <h2 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.25rem', fontWeight: 600 }}>Launch Statistical Calibration Layer</h2>
      <form onSubmit={handleLaunch} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-1)' }}>
          <label style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--color-neutral-700)' }}>
            Run name
          </label>
          <div
            style={{
              padding: 'var(--spacing-2)',
              borderRadius: 'var(--radius-md)',
              border: '1px dashed var(--border-default)',
              backgroundColor: 'var(--surface-muted)',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.8125rem',
              color: 'var(--color-neutral-600)',
              maxWidth: '600px',
            }}
          >
            {season || 'unset'}_&lt;timestamp&gt;_&lt;id&gt;
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)' }}>
            Generated at launch from the season and the clock -- runs sort chronologically and
            cannot collide.
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-1)' }}>
          <label style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--color-neutral-700)' }}>Season</label>
          <select
            value={season}
            onChange={e => setSeason(e.target.value)}
            style={{
              padding: 'var(--spacing-2)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)', width: '100%', maxWidth: '600px'
            }}
          >
            {seasons.length === 0 && <option value="">Loading seasons…</option>}
            {seasons.map(sn => (
              <option key={sn} value={sn}>{sn}</option>
            ))}
          </select>
          <span style={{ fontSize: '0.75rem', color: 'var(--color-neutral-500)' }}>
            Each season is fit independently -- its own regime, arrival-intensity and delay
            models, and its own parameter store. Defaults to <code>scope.season</code> from
            configs/base.yaml.
          </span>
        </div>

        <div>
          <label style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--color-neutral-700)', display: 'block', marginBottom: 'var(--spacing-2)' }}>
            Statistical Models to Calibrate (Full Pipeline Enforced)
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 'var(--spacing-3)', backgroundColor: 'var(--surface-muted)', padding: 'var(--spacing-4)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-default)' }}>
            {availableModels.map(m => (
              <label key={m.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--spacing-2)', fontSize: '0.875rem', color: 'var(--color-neutral-700)', cursor: 'not-allowed' }}>
                <input 
                  type="checkbox" 
                  checked={true}
                  disabled={true}
                  style={{ width: '1rem', height: '1rem', accentColor: 'var(--color-primary-600)', opacity: 0.6, marginTop: '2px', flexShrink: 0 }}
                />
                <span>
                  <span style={{ display: 'block' }}>{m.label}</span>
                  <span
                    style={{
                      display: 'block',
                      fontSize: '0.75rem',
                      color: 'var(--color-neutral-500)',
                      lineHeight: 1.4,
                    }}
                  >
                    {m.purpose}
                  </span>
                </span>
              </label>
            ))}
          </div>
        </div>

        <button 
          type="submit" 
          disabled={launching}
          style={{
            alignSelf: 'flex-start',
            padding: 'var(--spacing-2) var(--spacing-4)',
            backgroundColor: 'var(--color-primary-600)',
            color: 'white',
            border: 'none',
            borderRadius: 'var(--radius-md)',
            fontWeight: 500,
            cursor: launching ? 'not-allowed' : 'pointer',
            opacity: launching ? 0.7 : 1
          }}
        >
          {launching ? 'Queueing…' : 'Run Statistical Fitting'}
        </button>
      </form>

      {error && <div style={{ marginTop: 'var(--spacing-4)' }}><ErrorPanel message={error} /></div>}

      {jobId && (
        <div style={{ 
          marginTop: 'var(--spacing-4)', padding: 'var(--spacing-3)', backgroundColor: 'var(--color-success-bg)', color: 'var(--color-success-text)', borderRadius: 'var(--radius-md)', fontSize: '0.875rem'
        }}>
          Queued. Track the four fitting phases in the Run Monitor. Job ID: {jobId}
        </div>
      )}
    </div>
  );
};
