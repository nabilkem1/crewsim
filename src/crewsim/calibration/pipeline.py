import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from .. import config, package_version
from ..data import clean, coverage, limitations, loaders
from . import delays, nhpp, regime

#: The pipeline's phases, in order, as (label, what it produces). Exposed so a
#: caller can size a progress bar before starting rather than discovering the
#: number of steps as they arrive.
PHASES: tuple[tuple[str, str], ...] = (
    (
        "fitting severity regimes (hidden Markov model)",
        "HMM per crew base x season: transition matrix, pi0, emissions, day labels",
    ),
    ("fitting sick-call arrivals", "Negative Binomial GLM + absence-duration lognormal"),
    ("fitting flight delays", "base delay probability + Gaussian mixture"),
    ("writing parameter store", "blake2b content hash + params_v<ver>_<season>.json"),
)


#: Keys that describe a RUN, not the fitted parameters. Excluded from the
#: content hash so recalibrating unchanged data reproduces the same hash.
RUN_METADATA_KEYS: frozenset[str] = frozenset({"fitted_at", "content_hash", "_saved_path"})

#: Keys that are not parameters at all. `diagnostics` holds cross-checks
#: (e.g. agreement with an optional D9) that nothing downstream reads; hashing
#: them would let an edit to a diagnostic invalidate every cached scenario set.
NON_PARAMETER_KEYS: frozenset[str] = RUN_METADATA_KEYS | {"diagnostics"}


def content_hash(store: dict[str, Any]) -> str:
    """blake2b over the store's parameters (IMP-201): run metadata and
    diagnostics excluded."""
    # Drop non-parameters, serialise with sorted keys (stable text), then hash it.
    content = {k: v for k, v in store.items() if k not in NON_PARAMETER_KEYS}
    receipt_str = json.dumps(content, sort_keys=True)
    return "blake2b:" + hashlib.blake2b(receipt_str.encode(), digest_size=20).hexdigest()


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
    # Progress reporting: step() announces each phase of PHASES, in order, to on_step.
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
    holdout_window: tuple[Any, Any] | None = None
    if cfg.windows is not None:
        w = cfg.windows.get(window_name)
        fit_window = (w.start, w.end)
        if window_name != "holdout":
            h = cfg.windows.get("holdout")
            holdout_window = (h.start, h.end)

    # IMP-516: a fit over days nobody recorded does not fail, it quietly fits zeros.
    # Refuse a window the flight and sick-call data do not overlap, naming the
    # spans that ARE recorded.
    if fit_window is not None:
        coverage.require_window_supported(
            cfg, fit_window, datasets=("d8_flight_movements", "d4_absences"), what=window_name,
        )

    # 1. Run the fitters
    # Phase 1 (F-42): the severity regime is INFERRED, not loaded. One hidden
    # Markov model per crew base x season gives the day labels the next two
    # fitters condition on; the scoped base's model gives P, pi0, emissions.
    step()
    regime_inputs = regime.load_inputs(cfg)
    regime_fits = regime.fit_station_regimes(cfg, fit_window, inputs=regime_inputs)
    regime_days = regime.labels_frame(regime_fits)
    regime_res = regime.fit_regime(
        cfg, season, window=fit_window, fits=regime_fits, inputs=regime_inputs,
        holdout_window=holdout_window,
    )
    # Phase 2: sick calls -> Negative Binomial GLM (daily counts) + lognormal (absence duration).
    step()
    nhpp_res = nhpp.fit_sick_calls(cfg, window=fit_window, regime_days=regime_days)
    # Phase 3: flight delays -> P(delayed) per regime + Gaussian mixture (delay minutes).
    step()
    delays_res = delays.fit_delays(cfg, season, window=fit_window, regime_days=regime_days)
    # Phase 4: assemble, hash and write the parameter store (below).
    step()

    # IMP-412: one version source, shared with every reader of the store.
    version = package_version()

    # 2. Build the parameter store
    # The store records the window it was fitted on, then gathers the three fitters'
    # results under one dict: what scenario generation and the simulation read.
    window: dict[str, Any] = {}
    if cfg.windows is not None:
        w = cfg.windows.get(window_name)
        window = {"start": w.start.isoformat(), "end": w.end.isoformat()}

    store = {
        "params_version": f"v{version}",
        "data_window": window,
        "season": season,
        "markov_steady_state_pi0": regime_res["pi0"],
        "markov_transition_matrix_P": regime_res["matrix"],
        # F-42: sick-call rate per crew on duty in each state / NORMAL's, from
        # the HMM's emissions (metadata: generation uses the GLM's C(regime)).
        "intensity_multipliers": regime_res["multipliers"],
        # F-42: the full regime model -- per-state emissions, fit report
        # (log-likelihood, BIC, restarts), BIC model selection, holdout score.
        "regime_hmm": {
            k: regime_res[k]
            for k in (
                "station", "method", "startprob", "emissions", "fit", "degenerate_states",
                "settings", "model_selection", "holdout",
            )
            if k in regime_res
        },
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
            # IMP-515/516: what the data was cut down to before fitting, and the span
            # each dataset is recorded over. Excluded from the hash like every diagnostic.
            "data_coverage": {
                name: (interval.label() if interval else None)
                for name, interval in (
                    (n, coverage.dataset_interval(cfg, n))
                    for n in ("d2_rosters", "d4_absences", "d8_flight_movements")
                )
            },
            "operated_flights": clean.operated_flights_report(
                cfg, loaders.load_dataset(cfg, "d8_flight_movements")
            )[1],
            # F-42: D9 is no longer an input. If one is present (the mock
            # corpus keeps the generator's true regime there), this reports
            # how often the HMM's labels match it. Excluded from the hash.
            "regime_label_agreement": regime.label_agreement(
                cfg, season, window=fit_window, labels=regime_days
            ),
        },
        "validation_targets": {}
    }
    # What this fit could NOT do properly (one season in the window, a flat
    # cancellation stream, columns assumed away, ...). Shown by the CLI, the API
    # and the data-profile page; part of `diagnostics`, so outside the hash.
    try:
        found = limitations.collect(cfg) + limitations.from_store(cfg, store)
        store["diagnostics"]["limitations"] = [x.as_dict() for x in limitations.sort_limitations(found)]
    except Exception as exc:  # noqa: BLE001 - a report must never stop a fit that succeeded
        store["diagnostics"]["limitations"] = [limitations.Limitation(
            "limitations_failed", limitations.INFO, "Limitations could not be computed", str(exc)
        ).as_dict()]
    # Warn loudly if the sick-call GLM did not converge (the store records it too).
    if not store["sick_call_nhpp"]["converged"]:
        print("[WARN] sick-call NHPP MLE did not converge (after retry); "
              "the store records converged=false -- treat fitted intensities as provisional.")
    degenerate = store["regime_hmm"].get("degenerate_states") or []
    if degenerate:
        print(f"[WARN] regime HMM: state(s) {degenerate} hold almost no days in the fitting "
              "window -- the data may support fewer than 4 regimes (see regime_hmm.model_selection).")
    
    # 3. Hash for determinism guarantee: the same inputs and config must give
    # the same hash. IMP-201: so the hash covers CONTENT only. `fitted_at` used
    # to be inside the hashed dict, so every recalibration of unchanged data
    # produced a new hash and invalidated the scenario cache
    # (scenarios/generator.py keys on it). Run metadata is added after.
    store["content_hash"] = content_hash(store)
    store["fitted_at"] = datetime.now(UTC).isoformat()

    # 4. Save to JSON
    # Joined onto the directory ensure_dir returns (which tests redirect to a
    # temp dir), not re-resolved: same file name as every reader uses.
    out_path = config.ensure_dir(cfg, "params_dir") / config.params_store_filename(season)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)
        
    store["_saved_path"] = str(out_path)
    return store
