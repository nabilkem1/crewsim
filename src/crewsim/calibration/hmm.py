"""Hidden Markov model of the daily disruption regime (F-42, Option B).

Why an HMM, and why hmmlearn
----------------------------
The severity regime (CALM / NORMAL / DISRUPTED / SEVERE) is never observed.
What IS observed, every day at a base, is what the regime causes: flights
delayed, flights cancelled, crew calling in sick. A hidden Markov model infers
both the hidden day-states and how each state behaves, in one maximum-
likelihood fit (Baum-Welch EM), from those observations alone -- no externally
supplied label (the old D9 `disruption_class`) and no arbitrary quantile cut.

`hmmlearn` (scikit-learn family) is the library: it supplies a tested,
log-space forward-backward / Viterbi / EM engine (`BaseHMM`), multi-sequence
fitting (`lengths`), BIC/AIC and the stationary distribution, and is designed
to be subclassed with a custom emission model -- which is exactly what this
problem needs (one day = a mixed vector of binomial-type flight counts and a
Poisson sick-call count with an exposure offset). pomegranate v1 would work
too but drags in PyTorch; nltk's HMM is a discrete-symbol tagger for NLP and
cannot express count emissions at all.

Emission model (conditionally independent given the day's state k)
--------------------------------------------------------------------
Columns of the observation matrix X (see OBS_COLUMNS):

    n_flights    departures from the base that day
    n_delayed    of those, not cancelled and delayed >= threshold
    n_cancelled  of those, cancelled
    sick_calls   absences starting that day at the base
    exposure     crew on duty at the base that day (Poisson offset)

    (n_ontime, n_delayed, n_cancelled) ~ Multinomial(n_flights; 1-q_k-r_k, q_k, r_k)
    sick_calls                         ~ Poisson(exposure * lam_k)

A day with no flight data (n_flights = 0) or no exposure (exposure = 0)
contributes log-likelihood exactly 0 for that stream in every state: it is
*uninformative*, not "a calm day", and the chain carries on through it.

The M-step is closed form (posterior-weighted rates), so EM is fast and exact.
"""
from __future__ import annotations

import contextlib
import logging
import warnings
from collections.abc import Iterator
from typing import Any

import numpy as np
from hmmlearn.base import BaseHMM
from scipy.special import gammaln, xlogy

#: Column order of the observation matrix every function here expects.
OBS_COLUMNS: tuple[str, ...] = ("n_flights", "n_delayed", "n_cancelled", "sick_calls", "exposure")
_F, _D, _C, _S, _E = range(len(OBS_COLUMNS))


class DisruptionHMM(BaseHMM):
    """K-state HMM with a multinomial flight-outcome emission and a Poisson
    sick-call emission with exposure offset.

    Emission parameters (one entry per state):
        delay_prob_   q_k  P(a departure is delayed)
        cancel_prob_  r_k  P(a departure is cancelled)
        sick_rate_    lam_k  expected sick calls per unit of exposure per day

    `params` / `init_params` codes: 's' startprob, 't' transmat,
    'f' flight-outcome probabilities, 'l' sick-call rates.
    """

    def __init__(
        self,
        n_components: int = 1,
        *,
        min_probability: float,
        n_iter: int,
        tol: float,
        startprob_prior: float = 1.0,
        transmat_prior: float = 1.0,
        algorithm: str = "viterbi",
        random_state: Any = None,
        verbose: bool = False,
        params: str = "stfl",
        init_params: str = "",
    ) -> None:
        super().__init__(
            n_components=n_components,
            startprob_prior=startprob_prior,
            transmat_prior=transmat_prior,
            algorithm=algorithm,
            random_state=random_state,
            n_iter=n_iter,
            tol=tol,
            verbose=verbose,
            params=params,
            init_params=init_params,
            implementation="log",
        )
        self.min_probability = min_probability

    # ------------------------------------------------------------ bookkeeping
    def _get_n_fit_scalars_per_param(self) -> dict[str, int]:
        nc = self.n_components
        return {"s": nc - 1, "t": nc * (nc - 1), "f": 2 * nc, "l": nc}

    def _init(self, X: np.ndarray, lengths: Any = None) -> None:
        super()._init(X, lengths)
        if not all(hasattr(self, a) for a in ("delay_prob_", "cancel_prob_", "sick_rate_")):
            raise ValueError(
                "DisruptionHMM has no automatic emission initialisation: set "
                "delay_prob_, cancel_prob_ and sick_rate_ before fit() "
                "(see calibration.hmm.initial_parameters)."
            )

    def _check(self) -> None:
        super()._check()
        nc = self.n_components
        for name in ("delay_prob_", "cancel_prob_", "sick_rate_"):
            arr = np.asarray(getattr(self, name), dtype=float)
            if arr.shape != (nc,):
                raise ValueError(f"{name} must have shape (n_components,)")
            setattr(self, name, arr)
        if np.any(self.delay_prob_ + self.cancel_prob_ >= 1.0):
            raise ValueError("delay_prob_ + cancel_prob_ must be < 1 in every state")

    # -------------------------------------------------------------- emissions
    def _compute_log_likelihood(self, X: np.ndarray) -> np.ndarray:
        return emission_log_likelihood(
            X, self.delay_prob_, self.cancel_prob_, self.sick_rate_, self.min_probability
        )

    def _generate_sample_from_state(self, state: int, random_state: Any) -> np.ndarray:
        # Sampling needs a day's size (flights, exposure). The fitted typical
        # day is used -- enough for hmmlearn's sample() and for tests.
        n = round(getattr(self, "typical_flights_", 0.0))
        exposure = float(getattr(self, "typical_exposure_", 0.0))
        q, r = self.delay_prob_[state], self.cancel_prob_[state]
        ontime_delay_cancel = random_state.multinomial(n, [1.0 - q - r, q, r]) if n else [0, 0, 0]
        sick = random_state.poisson(exposure * self.sick_rate_[state])
        return np.array([n, ontime_delay_cancel[1], ontime_delay_cancel[2], sick, exposure], dtype=float)

    # ---------------------------------------------------------------- M-step
    def _initialize_sufficient_statistics(self) -> dict[str, Any]:
        stats = super()._initialize_sufficient_statistics()
        nc = self.n_components
        for key in ("flights", "delayed", "cancelled", "sick", "exposure"):
            stats[key] = np.zeros(nc)
        return stats

    def _accumulate_sufficient_statistics(
        self, stats: dict[str, Any], X: np.ndarray, lattice: np.ndarray,
        posteriors: np.ndarray, fwdlattice: np.ndarray, bwdlattice: np.ndarray,
    ) -> None:
        super()._accumulate_sufficient_statistics(
            stats, X, lattice, posteriors, fwdlattice, bwdlattice
        )
        stats["flights"] += posteriors.T @ X[:, _F]
        stats["delayed"] += posteriors.T @ X[:, _D]
        stats["cancelled"] += posteriors.T @ X[:, _C]
        stats["sick"] += posteriors.T @ X[:, _S]
        stats["exposure"] += posteriors.T @ X[:, _E]

    def _do_mstep(self, stats: dict[str, Any]) -> None:
        super()._do_mstep(stats)
        eps = self.min_probability
        if "f" in self.params:
            has = stats["flights"] > 0
            q = np.where(has, stats["delayed"] / np.where(has, stats["flights"], 1.0), self.delay_prob_)
            r = np.where(has, stats["cancelled"] / np.where(has, stats["flights"], 1.0), self.cancel_prob_)
            self.delay_prob_, self.cancel_prob_ = _clip_probabilities(q, r, eps)
        if "l" in self.params:
            has = stats["exposure"] > 0
            lam = np.where(has, stats["sick"] / np.where(has, stats["exposure"], 1.0), self.sick_rate_)
            self.sick_rate_ = np.maximum(lam, eps)


# =============================================================== pure helpers

@contextlib.contextmanager
def quiet_hmmlearn() -> Iterator[None]:
    """Silence two known, harmless hmmlearn messages around its calls.

    * "Model is not converging" log lines: with a Dirichlet prior on the
      transitions EM maximises the posterior, not the likelihood, so
      sub-tolerance dips are expected, not a fault. Convergence is reported
      in the fit report instead.
    * numpy's DeprecationWarning about setting an array's shape, raised
      inside hmmlearn.utils.normalize on numpy >= 2.5 -- a library-internal
      idiom, not something this code does. Left alone it floods the
      calibration job's warning log, burying warnings that matter.
    """
    logger = logging.getLogger("hmmlearn.base")
    previous = logger.level
    logger.setLevel(logging.ERROR)
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message="Setting the shape on a NumPy array", category=DeprecationWarning
            )
            yield
    finally:
        logger.setLevel(previous)


def emission_log_likelihood(
    X: np.ndarray, q: np.ndarray, r: np.ndarray, lam: np.ndarray, min_probability: float
) -> np.ndarray:
    """log P(day t | state k) for every day and state, shape (n_days, K).

    xlogy makes 0 * log(anything) == 0, so a day with no flights / no
    exposure contributes exactly 0 for that stream -- uninformative, as the
    module docstring promises.
    """
    X = np.asarray(X, dtype=float)
    n, nd, nc, s, e = X[:, _F], X[:, _D], X[:, _C], X[:, _S], X[:, _E]
    no = n - nd - nc
    q = np.maximum(np.asarray(q, dtype=float), min_probability)
    r = np.maximum(np.asarray(r, dtype=float), min_probability)
    p_ok = np.maximum(1.0 - q - r, min_probability)
    lam = np.maximum(np.asarray(lam, dtype=float), min_probability)

    log_coef = gammaln(n + 1) - gammaln(nd + 1) - gammaln(nc + 1) - gammaln(no + 1)
    flights = (
        log_coef[:, None]
        + xlogy(nd[:, None], q[None, :])
        + xlogy(nc[:, None], r[None, :])
        + xlogy(no[:, None], p_ok[None, :])
    )
    mu = e[:, None] * lam[None, :]
    sick = xlogy(s[:, None], mu) - mu - gammaln(s + 1)[:, None]
    # exposure == 0 days: Poisson(0) has P(0) = 1; a recorded sick call on a
    # zero-exposure day cannot be explained -- callers zero those out first.
    return np.asarray(flights + sick)


def _clip_probabilities(q: np.ndarray, r: np.ndarray, eps: float) -> tuple[np.ndarray, np.ndarray]:
    q = np.clip(q, eps, 1.0 - eps)
    r = np.clip(r, eps, 1.0 - eps)
    total = q + r
    too_big = total >= 1.0 - eps
    scale = np.where(too_big, (1.0 - eps) / np.where(too_big, total, 1.0), 1.0)
    return q * scale, r * scale


def emission_parameters_from_weights(
    X: np.ndarray, weights: np.ndarray, min_probability: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Closed-form (q, r, lam) per state from a (n_days, K) responsibility
    matrix -- the M-step formula, reused for initialisation."""
    X = np.asarray(X, dtype=float)
    flights = weights.T @ X[:, _F]
    delayed = weights.T @ X[:, _D]
    cancelled = weights.T @ X[:, _C]
    sick = weights.T @ X[:, _S]
    exposure = weights.T @ X[:, _E]
    overall_q = X[:, _D].sum() / max(X[:, _F].sum(), 1.0)
    overall_r = X[:, _C].sum() / max(X[:, _F].sum(), 1.0)
    overall_lam = X[:, _S].sum() / max(X[:, _E].sum(), 1.0)
    q = np.where(flights > 0, delayed / np.where(flights > 0, flights, 1.0), overall_q)
    r = np.where(flights > 0, cancelled / np.where(flights > 0, flights, 1.0), overall_r)
    lam = np.where(exposure > 0, sick / np.where(exposure > 0, exposure, 1.0), overall_lam)
    q, r = _clip_probabilities(q, r, min_probability)
    return q, r, np.maximum(lam, min_probability)


def severity_index(X: np.ndarray) -> np.ndarray:
    """A per-day disruption score used ONLY to seed one EM restart and to
    order states: mean of the three per-day rates, each scaled by its own
    overall mean so no stream dominates by units. Days with no data score NaN."""
    X = np.asarray(X, dtype=float)
    parts = []
    for num, den in ((_D, _F), (_C, _F), (_S, _E)):
        with np.errstate(invalid="ignore", divide="ignore"):
            rate = np.where(X[:, den] > 0, X[:, num] / np.where(X[:, den] > 0, X[:, den], 1.0), np.nan)
        overall = np.nanmean(rate) if np.isfinite(rate).any() else np.nan
        if np.isfinite(overall) and overall > 0:
            parts.append(rate / overall)
    if not parts:
        return np.full(X.shape[0], np.nan)
    stacked = np.vstack(parts)
    with np.errstate(invalid="ignore"):
        return np.nanmean(stacked, axis=0)


def state_severity(q: np.ndarray, r: np.ndarray, lam: np.ndarray) -> np.ndarray:
    """One severity number per state, same construction as severity_index:
    each emission rate relative to its mean across states, averaged."""
    parts = []
    for values in (q, r, lam):
        v = np.asarray(values, dtype=float)
        m = v.mean()
        if m > 0:
            parts.append(v / m)
    return np.mean(np.vstack(parts), axis=0) if parts else np.zeros(len(q))


def initial_parameters(
    X: np.ndarray,
    n_states: int,
    rng: np.random.Generator,
    *,
    quantile_seed: list[float] | None,
    init_self_transition: float,
    min_probability: float,
) -> dict[str, np.ndarray]:
    """Starting point for one EM restart.

    quantile_seed given -> deterministic "Option A" start: days bucketed by
    the quantiles of severity_index (days with no data spread uniformly).
    quantile_seed None  -> random start: Dirichlet responsibilities per day.
    The transition matrix starts sticky (init_self_transition on the
    diagonal) because regimes persist -- strictly positive everywhere, as
    hmmlearn never revives a transition that starts at exactly zero.
    """
    n_days = X.shape[0]
    if quantile_seed is not None:
        score = severity_index(X)
        weights = np.full((n_days, n_states), 1.0 / n_states)
        finite = np.isfinite(score)
        if finite.any():
            cuts = np.quantile(score[finite], quantile_seed)
            labels = np.searchsorted(cuts, score[finite], side="left")
            weights[finite] = np.eye(n_states)[np.minimum(labels, n_states - 1)]
    else:
        weights = rng.dirichlet(np.ones(n_states), size=n_days)

    q, r, lam = emission_parameters_from_weights(X, weights, min_probability)
    if n_states == 1:
        trans = np.ones((1, 1))
    else:
        off = (1.0 - init_self_transition) / (n_states - 1)
        trans = np.full((n_states, n_states), off)
        np.fill_diagonal(trans, init_self_transition)
    start = np.full(n_states, 1.0 / n_states)
    return {"startprob": start, "transmat": trans, "q": q, "r": r, "lam": lam}


def build_model(
    n_states: int,
    init: dict[str, np.ndarray],
    *,
    max_iter: int,
    tol: float,
    transition_pseudocount: float,
    min_probability: float,
) -> DisruptionHMM:
    """A DisruptionHMM pre-loaded with `init`. hmmlearn's Dirichlet prior is
    expressed as (pseudo-count + 1): transmat = max(prior - 1 + counts, 0)."""
    model = DisruptionHMM(
        n_components=n_states,
        min_probability=min_probability,
        startprob_prior=1.0 + transition_pseudocount,
        transmat_prior=1.0 + transition_pseudocount,
        n_iter=max_iter,
        tol=tol,
        init_params="",
    )
    model.startprob_ = init["startprob"]
    model.transmat_ = init["transmat"]
    model.delay_prob_ = init["q"]
    model.cancel_prob_ = init["r"]
    model.sick_rate_ = init["lam"]
    return model


def reorder_states(model: DisruptionHMM, order: np.ndarray) -> DisruptionHMM:
    """Permute every state-indexed parameter in place (label switching): the
    EM output's state numbering is arbitrary, the business names are not."""
    order = np.asarray(order)
    model.startprob_ = model.startprob_[order]
    model.transmat_ = model.transmat_[np.ix_(order, order)]
    model.delay_prob_ = model.delay_prob_[order]
    model.cancel_prob_ = model.cancel_prob_[order]
    model.sick_rate_ = model.sick_rate_[order]
    return model


def fit_best(
    X: np.ndarray,
    lengths: list[int],
    n_states: int,
    *,
    seed_sequence: np.random.SeedSequence,
    n_restarts: int,
    max_iter: int,
    tol: float,
    init_self_transition: float,
    transition_pseudocount: float,
    min_probability: float,
    quantile_seed: list[float] | None,
    restart_agreement_tol: float,
) -> tuple[DisruptionHMM, dict[str, Any]]:
    """EM from several starts, keep the highest log-likelihood, then order
    the states from least to most severe.

    Restart 0 is the deterministic quantile start; the others are random,
    each from its own child of `seed_sequence` (reproducible, order-free).
    Returns the model and a fit report (log-likelihood, BIC, convergence,
    how many restarts reached the best optimum).
    """
    if X.shape[0] < 2:
        raise ValueError("an HMM needs at least two days of observations")

    children = seed_sequence.spawn(n_restarts)
    results: list[tuple[float, DisruptionHMM]] = []
    for i, child in enumerate(children):
        rng = np.random.default_rng(child)
        init = initial_parameters(
            X, n_states, rng,
            quantile_seed=quantile_seed if i == 0 else None,
            init_self_transition=init_self_transition,
            min_probability=min_probability,
        )
        model = build_model(
            n_states, init, max_iter=max_iter, tol=tol,
            transition_pseudocount=transition_pseudocount, min_probability=min_probability,
        )
        with quiet_hmmlearn():
            model.fit(X, lengths)
            results.append((float(model.score(X, lengths)), model))

    best_ll, best = max(results, key=lambda t: t[0])
    reached = sum(1 for ll, _ in results if abs(ll - best_ll) <= restart_agreement_tol * abs(best_ll))

    order = np.argsort(state_severity(best.delay_prob_, best.cancel_prob_, best.sick_rate_), kind="stable")
    reorder_states(best, order)
    best.typical_flights_ = float(np.mean(X[:, _F][X[:, _F] > 0])) if (X[:, _F] > 0).any() else 0.0
    best.typical_exposure_ = float(np.mean(X[:, _E][X[:, _E] > 0])) if (X[:, _E] > 0).any() else 0.0

    with quiet_hmmlearn():
        bic, aic = float(best.bic(X, lengths)), float(best.aic(X, lengths))
    report = {
        "n_states": n_states,
        "log_likelihood": best_ll,
        "bic": bic,
        "aic": aic,
        "n_days": int(X.shape[0]),
        "n_sequences": len(lengths),
        # hmmlearn's monitor also reports "converged" when the iteration cap
        # is hit; only a stop BEFORE the cap is a real convergence.
        "converged": bool(best.monitor_.converged and best.monitor_.iter < max_iter),
        "iterations": int(best.monitor_.iter),
        "restarts": n_restarts,
        "restarts_reaching_best": reached,
    }
    return best, report
