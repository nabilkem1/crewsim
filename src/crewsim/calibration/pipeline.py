import hashlib
import importlib.metadata
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from .. import config
from . import delays, nhpp, regime

#: The pipeline's phases, in order, as (label, what it produces). Exposed so a
#: caller can size a progress bar before starting rather than discovering the
#: number of steps as they arrive.
PHASES: tuple[tuple[str, str], ...] = (
    ("fitting severity regimes", "Markov transition matrix, pi0, intensity multipliers"),
    ("fitting sick-call arrivals", "Negative Binomial GLM + absence-duration lognormal"),
    ("fitting flight delays", "base delay probability + Gaussian mixture"),
    ("writing parameter store", "blake2b content hash + params_v<ver>_<season>.json"),
)


def run_pipeline(
    cfg: config.BaseConfig,
    season: str,
    window_name: str = "fitting",
    on_step: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    """Runs the full calibration pipeline and emits the parameter store.

    on_step(index, total, label), if given, is called immediately BEFORE each
    phase starts -- the three fitters are single long calls with no internal
    progress to report, so a caller can only say which one is running, not how
    far through it is. Reporting on entry is what makes that honest: the label
    names the phase in flight, not one already finished.
    """
    total = len(PHASES)
    phases = enumerate(PHASES, start=1)

    def step() -> None:
        """Announce the next phase. Self-advancing, so the call sites cannot
        drift out of order with PHASES or skip a number."""
        index, (label, _detail) = next(phases)
        if on_step is not None:
            on_step(index, total, label)

    # AUD-05 / §6.4: the window this store CLAIMS is the window the fitters
    # actually receive. Before this, the three fitters read the full corpus
    # (holdout included) while the store stamped `data_window: fitting` --
    # the fitting/holdout separation existed as metadata only, and V3/V6
    # validated the model on months the calibration had already seen.
    fit_window: tuple[Any, Any] | None = None
    if cfg.windows is not None:
        w = cfg.windows.get(window_name)
        fit_window = (w.start, w.end)

    # 1. Run all independent fitters
    step()
    regime_res = regime.fit_regime(cfg, season, window=fit_window)
    step()
    nhpp_res = nhpp.fit_sick_calls(cfg, window=fit_window)
    step()
    delays_res = delays.fit_delays(cfg, season, window=fit_window)
    step()

    # Get project version
    try:
        version = importlib.metadata.version("crewsim")
    except Exception:  # noqa: BLE001 - a version lookup must not abort calibration
        version = "unknown"
        
    # 2. Build the parameter store
    window: dict[str, Any] = {}
    if cfg.windows is not None:
        w = cfg.windows.get(window_name)
        window = {"start": w.start.isoformat(), "end": w.end.isoformat()}

    store = {
        "params_version": f"v{version}",
        "fitted_at": datetime.now(UTC).isoformat(),
        "data_window": window,
        "season": season,
        "markov_steady_state_pi0": regime_res["pi0"],
        "markov_transition_matrix_P": regime_res["matrix"],
        "intensity_multipliers": regime_res["multipliers"],
        "sick_call_nhpp": {
            "coefficients": nhpp_res["coefficients"],
            "dispersion": nhpp_res["dispersion"],
            "category_levels": nhpp_res["category_levels"],
            "duration_lognorm_shape": nhpp_res["duration_lognorm_shape"],
            "duration_lognorm_scale": nhpp_res["duration_lognorm_scale"],
            # AUD-28e: whether the NB MLE converged (after retry). A store
            # carrying unconverged coefficients must say so.
            "converged": nhpp_res.get("converged", False),
        },
        "flight_delay_mixture": {
            "base_delay_probability": delays_res["base_delay_probability"],
            # Per-regime probability/mean-flights-per-day -- what
            # scenarios/generator.py actually draws delayed flights from.
            # base_delay_probability above is kept only for the calibration
            # UI's existing "P(delayed | NORMAL-regime day)" display.
            "delay_by_regime": delays_res["delay_by_regime"],
            "components": delays_res["components"]
        },
        "diagnostics": {
            # AUD-18: agreement between the two regime-label sources (this
            # module's chaos-quantile day labels, which fit the transition
            # matrix, vs D9's station-day disruption_class, which the NHPP and
            # delay fits condition on). The generation-time coupling of the
            # two is only as valid as this number is high.
            "regime_label_agreement": regime.label_agreement(cfg, season, window=fit_window),
        },
        "validation_targets": {}
    }
    if not store["sick_call_nhpp"]["converged"]:
        print("[WARN] sick-call NHPP MLE did not converge (after retry); "
              "the store records converged=false -- treat fitted intensities as provisional.")
    
    # 3. Hash for determinism guarantee
    receipt_str = json.dumps(store, sort_keys=True)
    h = hashlib.blake2b(receipt_str.encode(), digest_size=20)
    store["content_hash"] = "blake2b:" + h.hexdigest()
    
    # 4. Save to JSON
    params_dir = config.ensure_dir(cfg, "params_dir")
    out_path = params_dir / f"params_v{version}_{season}.json"
    
    with open(out_path, "w") as f:
        json.dump(store, f, indent=2)
        
    store["_saved_path"] = str(out_path)
    return store
