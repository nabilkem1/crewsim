"""Configuration and path resolution.

Every scope, horizon, population and **path** value comes from `configs/`.
Nothing in `src/` may hard-code one -- that is enforced by
`tests/test_config.py` (§4.4, §4.4.1b).

`load()` returns a validated `BaseConfig` (S1a-02): every section of
`configs/base.yaml` is a Pydantic model, so a missing or mistyped key fails
at load time with a readable error instead of surfacing three functions
downstream as a `KeyError` on a dict. No field on any model here carries a
numeric default -- every number this module knows about came from a YAML
file, never from code (§4.4).
"""
from __future__ import annotations

import datetime
import os
import pathlib
import re
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

# The one bootstrap literal in the codebase. See the module docstring.
_CONFIG_RELPATH = "configs/base.yaml"


def repo_root() -> pathlib.Path:
    """The project root: two levels above this file (src/crewsim/config.py)."""
    return pathlib.Path(__file__).resolve().parents[2]


# ============================================================== base models
class _Model(BaseModel):
    """Shared strictness: an unrecognised key is a typo, not silently ignored."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class PathsConfig(_Model):
    corpus_dir: pathlib.Path
    params_dir: pathlib.Path
    reports_dir: pathlib.Path
    seasons_file: pathlib.Path
    # D12 (the agreement rules) is a document, not an extract. A real corpus
    # folder that has none can name one here; null = `<corpus_dir>/d12_agreement_rules.yaml`.
    agreement_rules_file: pathlib.Path | None = None

    @model_validator(mode="before")
    @classmethod
    def _resolve_against_repo_root(cls, data: Any) -> Any:
        """Every path field is absolute the moment validation finishes.

        Resolution happens here, once, so every caller downstream (loaders,
        `ensure_dir`, `dataset_path`) receives a resolved path and never a
        literal it would have to resolve itself (§4.4.1b).
        """
        if not isinstance(data, dict):
            return data
        root = repo_root()
        out = dict(data)
        for key, value in data.items():
            if value is None:
                continue
            p = pathlib.Path(value)
            out[key] = p if p.is_absolute() else root / p
        return out


class Window(_Model):
    start: datetime.date
    end: datetime.date


class WindowsConfig(_Model):
    fitting: Window
    holdout: Window

    def get(self, name: str) -> Window:
        if name not in ("fitting", "holdout"):
            raise KeyError(f"unknown window {name!r}; known: fitting, holdout")
        window: Window = getattr(self, name)
        return window


class ScopeConfig(_Model):
    base: str
    fleet: str
    position: str
    crew_group: str
    season: str
    bid_period: str
    # Another fleet string to use INSTEAD when D1 holds more active pilots for it
    # than for `fleet` in this base/position (e.g. a real extract that only says
    # `A321` where the scope says `A321neoLR`). null = never substitute.
    fleet_fallback: str | None = None
    # Set by `load()` when the fallback was taken, never written in a YAML:
    # what was substituted and on what evidence. Reports quote it.
    fleet_resolution: str | None = None


class HorizonConfig(_Model):
    warmup_days: int
    measurement_days: int
    cooldown_days: int

    @property
    def horizon_days(self) -> int:
        """Total simulated days, computed and never stored.

        A literal `42` anywhere -- config or test -- would re-introduce the
        defect S1a-04 documents: assert the identity, never the number.
        """
        return self.warmup_days + self.measurement_days + self.cooldown_days


class PopulationConfig(_Model):
    roster_size: int
    displaced_flying: str      # S1b-02 AC2: "open_time" | "absorb"
    reserve_bid_rule: str      # S1b-02 AC3: "junior_first" | "senior_first"

    @field_validator("displaced_flying")
    @classmethod
    def _known_displaced_flying(cls, v: str) -> str:
        if v not in ("open_time", "absorb"):
            raise ValueError(f"displaced_flying must be 'open_time' or 'absorb', got {v!r}")
        return v

    @field_validator("reserve_bid_rule")
    @classmethod
    def _known_bid_rule(cls, v: str) -> str:
        if v not in ("junior_first", "senior_first"):
            raise ValueError(f"reserve_bid_rule must be 'junior_first' or 'senior_first', got {v!r}")
        return v


class DemandConfig(_Model):
    """Declared but not consumed until slice 1b (§4.4.1). See `load()`."""

    pairings_per_bid_period: int | None = None
    credit_hours_per_bid_period: int | None = None
    
    # Hours before departure to hold an open item before cancelling.
    # e.g., {"short_haul": 2.0, "long_haul": 4.0, "default": 2.0}
    uncovered_deadline_hours: dict[str, float] | float


class SensitivityConfig(_Model):
    roster_size: list[int]
    terminal_penalty: list[float]
    lambda_risk_dial: list[float]
    instability_threshold: int


class QualityGateThresholds(_Model):
    d4_link_pass: float
    d4_link_marginal: float
    d6_d7_join_pass: float
    # F-42: was d9_completeness_pass. D9 is no longer an input; the regime
    # model needs every day at each crew base to carry D8 flight data instead.
    station_day_coverage_pass: float
    # IMP-523: share of D3 legs with a positive block time and both clock times.
    d3_leg_complete_pass: float
    # IMP-523: share of D3 pairings whose fleet is a real fleet (not "UNKNOWN").
    d3_known_fleet_pass: float
    # IMP-524: most exact-duplicate rows a dataset may carry (share of its rows).
    duplicate_rate_max: float
    # IMP-524: most D2 blocks that may overlap another block of the same crew.
    overlap_rate_max: float
    # IMP-524: a column holding ONE value is only reported on datasets this big.
    constant_column_min_rows: int
    # IMP-525: most D10 invoice rows that may lack a crew_id (V6 filters on it).
    null_key_rate_max: float


class RegimeQuantiles(_Model):
    p_calm: float
    p_normal: float
    p_disrupted: float


class RegimeHmmConfig(_Model):
    """F-42 Option B: the hidden Markov model that infers the daily regime.

    See calibration/hmm.py and calibration/regime.py.
    """

    n_restarts: int                 # EM starts per fit; best log-likelihood kept
    max_iter: int                   # EM iteration cap per start
    tol: float                      # EM stops when the log-likelihood gain is below this
    seed: int                       # mixed into crn.stable_seed for the random starts
    init_self_transition: float     # diagonal of the starting transition matrix
    transition_pseudocount: float   # Dirichlet smoothing added to transition counts
    min_probability: float          # numerical floor on every emission probability/rate
    candidate_n_states: list[int]   # BIC model-selection report (the model itself uses 4)
    delay_threshold_minutes: int    # a departure counts as delayed at/after this delay
    sick_call_exposure: str         # crew_on_duty | constant
    restart_agreement_tol: float    # relative log-lik gap counted as "same optimum"
    min_state_share: float          # expected share of days below which a state is flagged
    # IMP-527: thin-data guards. A fit on fewer informative days than this is
    # refused rather than reported as a regime model.
    min_days: int
    # IMP-527: warn when fewer than this share of EM restarts reached the best optimum.
    min_restart_share: float

    @field_validator("sick_call_exposure")
    @classmethod
    def _known_exposure(cls, v: str) -> str:
        allowed = ("crew_on_duty", "constant")
        if v not in allowed:
            raise ValueError(f"sick_call_exposure must be one of {allowed}, got {v!r}")
        return v

    @field_validator("n_restarts", "max_iter")
    @classmethod
    def _positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("must be >= 1")
        return v

    @field_validator("init_self_transition")
    @classmethod
    def _probability(cls, v: float) -> float:
        if not 0.0 < v < 1.0:
            raise ValueError("init_self_transition must be in (0, 1)")
        return v


class CalibrationConfig(_Model):
    delay_gmm_components: int
    delay_gmm_random_state: int
    # Since F-42 these only seed ONE of the HMM's EM restarts (days bucketed
    # by severity quantile); they no longer define the regime.
    regime_quantiles: RegimeQuantiles
    regime_hmm: RegimeHmmConfig
    overdispersion_threshold: float
    sick_call_min_duration_days: float


class DraftReconstructionConfig(_Model):
    """S0-03, §6.3-1: the D6 x D7 join, spelled out as data.

    A NULL `initiator` always passes regardless of `initiator_filter` --
    that is enforced by the reconstruction code, not expressible as a config
    value, because "handle it, don't drop it silently" is the requirement.
    """

    premium_pay_codes: list[str]
    short_notice_reason_codes: list[str]
    initiator_filter: list[str]
    # IMP-514: a D6 change counts as a draft only when it was made no more than
    # this many hours before the pairing started. None = the rule is off (every
    # short-notice-coded change is a candidate). The right figure is a
    # [CONFIRM: Crew Planning] answer, so it is never defaulted to a number.
    max_notice_hours: float | None = None


class CascadeReconstructionConfig(_Model):
    """S0-05, §6.3-3: the 7-day follow-on scan."""

    window_days: int
    cascade_reason_codes: list[str]
    confidence_level: float

class LegalityConfig(_Model):
    max_duty_hours: float
    min_rest_hours_home: float
    min_rest_hours_away: float
    short_call_notice_hours: float
    long_call_notice_hours: float
    rolling_7d_duty_limit_hours: float
    rolling_7d_flight_limit_hours: float
    rolling_28d_duty_limit_hours: float
    # AUD-24: whether ON-CALL-BUT-NOT-FLYING hours accrue toward L3/L4's
    # rolling limits and L5's work streak. A [CONFIRM: Labour Relations]
    # question, so it is a swept flag rather than a hardcoded assumption.
    reserve_counts_as_duty: bool
    # IMP-104: minimum notice (call -> report) for drafting a crew member who
    # is NOT on reserve at the call. AUD-10 removed an invented 2 h floor; the
    # real figure is a [CONFIRM: Crew Planning] question. 0.0 means "no floor
    # beyond the call preceding the report", which is the behaviour since
    # AUD-10 -- a draft for a duty that has already reported stays illegal.
    # Required, like every other legality figure (no numeric defaults).
    line_holder_draft_notice_hours: float


class ReserveShift(_Model):
    """One standby shift: when it starts and how long it runs."""

    label: str
    start_hour: float
    hours: float

    def window_label(self) -> str:
        """The shift as a readable local clock range, e.g. "06:00-18:00 (12h)"."""
        end = (self.start_hour + self.hours) % 24

        def hhmm(h: float) -> str:
            return f"{int(h):02d}:{round(h % 1 * 60):02.0f}"

        return f"{hhmm(self.start_hour)}-{hhmm(end)} ({self.hours:g}h)"


class ReserveLinesConfig(_Model):
    """The standby SHIFTS the mock corpus's reserve lines are built from.

    **The engine never reads this.** `roster_loader` takes each D2 row's own
    start/end verbatim, so whatever a real Air Transat extract rosters --
    morning, afternoon, night, varying by crew and by day -- is honoured
    exactly as scheduled. The roster is the authority on when a reserve is on
    duty; this section only shapes the MOCK data the generator writes, so that
    the mock corpus has realistic variety instead of one hardcoded window.

    A reserve is on call for a shift and off duty outside it (spec §5.0.2's
    "on call until Tue 18:00", §5.5's "a reserve whose window ends at 18:00 is
    worth nothing after 18:00") -- never a continuous multi-day block.
    """

    shifts: list[ReserveShift]

    @field_validator("shifts")
    @classmethod
    def _at_least_one(cls, v: list[ReserveShift]) -> list[ReserveShift]:
        if not v:
            raise ValueError("reserve_lines.shifts must list at least one standby shift")
        return v

    def shift(self, label: str) -> ReserveShift:
        for s in self.shifts:
            if s.label == label:
                return s
        raise KeyError(f"unknown reserve shift {label!r}; known: {[s.label for s in self.shifts]}")


class ReducedModeConfig(_Model):
    p_elig: float
    # AUD-21 / §5.7: REDUCED-mode cascades are Bernoulli(p_cascade) spawning a
    # synthetic future open item. Screening only, like p_elig.
    p_cascade: float


class GatesConfig(_Model):
    v2_confidence_level: float
    # AUD-12 / §5.0.5 Welch check: how far (as a fraction of the tail mean)
    # the daily open-item mean may sit from its settled level and still count
    # as "stabilised". A verification tolerance, not a modelling input.
    welch_tolerance: float


class CascadeConfig(_Model):
    visibility_lag_hours: float


class PositioningConfig(_Model):
    """S1c-07: how cross-base reserve dispatch behaves. The PRICES live in
    costs_pilots.yaml -> positioning; this is the behaviour that decides when
    they are charged and how much duty time positioning consumes."""
    deadhead_duration_hours: float
    hotel_on_every_deadhead: bool
    transport_on_every_deadhead: bool

    @field_validator("deadhead_duration_hours")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("positioning.deadhead_duration_hours must be >= 0")
        return v


class ServiceLevelConfig(_Model):
    """WN-004, spec Sec7.5's chance constraint: P(UncoveredLegs > u_max) <= epsilon.

    No numeric default (test_no_config_model_field_has_a_numeric_default
    enforces this repo-wide) -- both fields must come from configs/base.yaml,
    where they carry a [CONFIRM: Crew Planning] marker. u_max/epsilon = 3/0.05
    is proposed there, not invented here: it is spec_sections/00_Intro.md's own
    glossary worked example of what a service-level target looks like ("At
    most 3 uncovered legs, in no more than 5% of months"), used as the most
    defensible starting point available pending a real Crew Planning number.
    """

    u_max: int
    epsilon: float


class PairingIdForm(_Model):
    """One spelling of a dated pairing id: `<code><separator><date>`.

    The corpus names a pairing by its rotation code AND its start date
    (`G0025_20260601`); some extracts quote only the code (`G0025`) or use
    another spelling (`TS18@2026-05-18`). The first form listed is canonical.
    """

    separator: str
    date_format: str


class PayCodeSpec(_Model):
    """IMP-525: what one D7 pay code means, as data."""

    meaning: str
    # RESERVE_STAFFING | RESERVE_UTILIZATION | DRAFT | IGNORE
    comparable_to: str

    @field_validator("comparable_to")
    @classmethod
    def _known_category(cls, v: str) -> str:
        allowed = ("RESERVE_STAFFING", "RESERVE_UTILIZATION", "DRAFT", "IGNORE")
        if v not in allowed:
            raise ValueError(f"comparable_to must be one of {allowed}, got {v!r}")
        return v


class CoverageConfig(_Model):
    """IMP-516: how each dataset's valid time interval is detected."""

    # A day is "covered" when the smoothed daily row count is at least
    # `min_share` of the dataset's typical busy level -- the way a dataset that
    # simply stops (D2 after mid-June) or starts late (D4 on 1 June) is told
    # apart from one that merely has a quiet day.
    min_share: float
    # The "typical busy level": this quantile of the smoothed daily counts.
    # A high quantile, not the median, so a long low tail after a dataset
    # collapses does not drag its own reference down with it.
    reference_quantile: float
    # Days in the centred moving average that smooths the daily counts.
    smooth_days: int
    # Dataset name -> interval, overriding detection (e.g. once the data
    # owner states the real extraction period).
    explicit: dict[str, Window] | None = None


class DataConfig(_Model):
    """Rules for reading a REAL extract, as opposed to the generated mock.

    Every value here only changes behaviour on data the mock never produces
    (post-cutoff scheduled-only flights, UTC dates, bare pairing codes, block
    types outside the spec), so the mock corpus reads exactly as before.
    """

    # D8 `date` is not always the local departure date. "date" = use the
    # column as supplied; "sched_dep_local" = the local calendar day of the
    # scheduled departure (what D2 and D4 use).
    flight_day: str
    # Last day with recorded movements. Later D8 rows are dropped. None =
    # detected from the data (the last day with any actual departure).
    cutoff: datetime.date | None = None
    # A non-cancelled flight with no actual departure never operated as far as
    # the data knows: it is scheduled-only, not an on-time flight.
    require_actuals: bool
    coverage: CoverageConfig
    # Overlapping D2 blocks of one crew: "reconcile" (trim soft blocks, drop
    # the later of two hard ones, count both) or "raise".
    overlap_policy: str
    # Block types a hard block may overlap by trimming THEM (a day off that
    # runs into a pairing).
    trimmable_block_types: list[str]
    # D2 block types outside the engine's BlockType -> the engine type they
    # stand in for. A type in neither place is refused, never skipped.
    block_type_map: dict[str, str]
    # Fleet group -> fleet strings that are the same family for qualification
    # (A321-200 and A321neoLR share a type rating).
    fleet_groups: dict[str, list[str]]
    pairing_id_forms: list[PairingIdForm]
    # When true the D4/D5/D6 linkage gates accept an id resolved from a bare
    # code plus a date; the result is flagged as resolved, not exact.
    allow_resolved_ids: bool
    pay_codes: dict[str, PayCodeSpec]
    # A column the file carries that the schema does not declare: "ignore" it
    # (reported by `crewsim data readiness`), or "refuse" the file. A MISSING
    # declared column, and any identifying (Law 25) column, is always refused.
    extra_columns: str = "ignore"
    # D4 rows with no `notification_ts`: "at_absence_start" assumes the absence
    # was reported at 00:00 on `absence_start` (every sick call kept; notice is
    # the conservative reading), "exclude" drops them from the replay and V3.
    null_notification_ts: str = "at_absence_start"
    # D8 rows whose origin equals their destination are not flights (a real
    # extract had 708). true = drop them before any count; false = keep.
    drop_self_loop_flights: bool = False
    # Where D9's labels came from: generator_truth | derived_rule | unknown.
    d9_source: str

    @field_validator("flight_day")
    @classmethod
    def _known_flight_day(cls, v: str) -> str:
        if v not in ("date", "sched_dep_local"):
            raise ValueError(f"flight_day must be 'date' or 'sched_dep_local', got {v!r}")
        return v

    @field_validator("extra_columns")
    @classmethod
    def _known_extra_columns(cls, v: str) -> str:
        if v not in ("ignore", "refuse"):
            raise ValueError(f"extra_columns must be 'ignore' or 'refuse', got {v!r}")
        return v

    @field_validator("null_notification_ts")
    @classmethod
    def _known_null_notification(cls, v: str) -> str:
        if v not in ("at_absence_start", "exclude"):
            raise ValueError(f"null_notification_ts must be 'at_absence_start' or 'exclude', got {v!r}")
        return v

    @field_validator("overlap_policy")
    @classmethod
    def _known_overlap_policy(cls, v: str) -> str:
        if v not in ("reconcile", "raise"):
            raise ValueError(f"overlap_policy must be 'reconcile' or 'raise', got {v!r}")
        return v

    @field_validator("d9_source")
    @classmethod
    def _known_d9_source(cls, v: str) -> str:
        allowed = ("generator_truth", "derived_rule", "unknown")
        if v not in allowed:
            raise ValueError(f"d9_source must be one of {allowed}, got {v!r}")
        return v

    @field_validator("pairing_id_forms")
    @classmethod
    def _at_least_one_form(cls, v: list[PairingIdForm]) -> list[PairingIdForm]:
        if not v:
            raise ValueError("pairing_id_forms must list at least one form")
        return v


class LimitationsConfig(_Model):
    """Thresholds for the limitations the data-load and calibration reports state
    (`data/limitations.py`). They decide what is WORTH saying, never a verdict."""

    # A "sick" absence longer than this is a leave recorded as one.
    long_absence_days: int
    # Fewer cancellations than this leaving the crew bases in the fitting window and
    # the regime model's cancellation stream carries no signal.
    min_base_cancellations: int
    # A day with at least this many D8 flights and more than `artefact_cancel_share`
    # of them cancelled is an extraction artefact, not a disruption.
    artefact_min_flights: int
    artefact_cancel_share: float
    # Complete seasons a window needs before a seasonal model can tell season from year.
    min_season_episodes: int
    # Share of D4 rows without a notification time worth reporting.
    null_notification_share: float
    # Below this share of D4 pairings found in the sick pilot's own D2 roster, the
    # V3 eligibility target cannot be rebuilt from history.
    min_roster_link_share: float
    # Holdout log-likelihood per day the regime model must gain over one state.
    holdout_gain_min: float
    # A fitted dispersion below this is, in effect, Poisson.
    poisson_dispersion_max: float


class BaseConfig(_Model):
    paths: PathsConfig
    scope: ScopeConfig
    horizon: HorizonConfig
    population: PopulationConfig
    quality_gates: QualityGateThresholds
    calibration: CalibrationConfig
    data: DataConfig
    draft_reconstruction: DraftReconstructionConfig
    cascade_reconstruction: CascadeReconstructionConfig
    legality: LegalityConfig | None = None
    reserve_lines: ReserveLinesConfig | None = None
    cascade: CascadeConfig | None = None
    positioning: PositioningConfig | None = None
    gates: GatesConfig | None = None
    reduced_mode: ReducedModeConfig | None = None
    mode: str
    costs_file: str
    windows: WindowsConfig | None = None
    demand: DemandConfig | None = None
    sensitivity: SensitivityConfig | None = None
    service_level: ServiceLevelConfig | None = None
    limitations: LimitationsConfig | None = None
    config_path: pathlib.Path | None = None


# =============================================================== cost models
class ReserveGuarantee(_Model):
    short_call: float
    long_call: float


class ReserveCosts(_Model):
    guarantee_per_day: ReserveGuarantee
    utilisation: float


class DraftCosts(_Model):
    base_premium: float
    tier: dict[int, float]
    train_reschedule: float


class PositioningCosts(_Model):
    deadhead: float
    hotel: float
    transport: float


class DisruptionCosts(_Model):
    cancellation: float
    delay_per_minute: float
    terminal_penalty_multiple: float
    
    @field_validator("terminal_penalty_multiple")
    @classmethod
    def check_terminal_penalty(cls, v):
        if v <= 1.0:
            raise ValueError(f"terminal_penalty_multiple must strictly exceed 1.0, got {v}")
        return v


class APPRCompensation(_Model):
    cancellation_band: str
    hours_3_to_6: float
    hours_6_to_9: float
    hours_9_plus: float

    @property
    def on_cancellation(self) -> float:
        """The APPR amount a cancellation attracts, per `cancellation_band`."""
        return float(getattr(self, self.cancellation_band))

    @field_validator("cancellation_band")
    @classmethod
    def _known_band(cls, v: str) -> str:
        if v not in ("hours_3_to_6", "hours_6_to_9", "hours_9_plus"):
            raise ValueError(f"unknown appr cancellation_band {v!r}")
        return v


class CostsConfig(_Model):
    version: str
    reserve: ReserveCosts
    draft: DraftCosts
    positioning: PositioningCosts
    disruption: DisruptionCosts
    appr_compensation: APPRCompensation
    config_path: pathlib.Path | None = None


# ==================================================================== loading
#: IMP-512: the environment variable that selects the configuration file for a
#: whole process (CLI, API server, notebooks) without editing the committed
#: configs/base.yaml. An explicit `config_path` argument still wins.
CONFIG_ENV_VAR = "CREWSIM_CONFIG"

#: A config file may name another to build on: `extends: base.yaml` (resolved
#: next to the file that says so). Only the keys it overrides need repeating.
_EXTENDS_KEY = "extends"


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursive mapping merge: `override` wins, nested mappings merge key by key."""
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def _read_raw(path: pathlib.Path, _seen: tuple[pathlib.Path, ...] = ()) -> dict[str, Any]:
    """The YAML at `path`, with its `extends:` chain folded in."""
    if not path.is_file():
        raise FileNotFoundError(
            f"configuration not found at {path}. "
            f"Every value this simulation uses lives in configs/ (§4.4)."
        )
    resolved = path.resolve()
    if resolved in _seen:
        raise ValueError(f"configuration `extends` cycle through {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    parent = raw.pop(_EXTENDS_KEY, None)
    if parent is None:
        return dict(raw)
    return _merge(_read_raw(path.parent / parent, (*_seen, resolved)), raw)


def selected_config_path(config_path: str | pathlib.Path | None = None) -> pathlib.Path:
    """The file `load()` will read: the argument, else $CREWSIM_CONFIG, else
    configs/base.yaml under the repo root."""
    if config_path:
        return pathlib.Path(config_path)
    env = os.environ.get(CONFIG_ENV_VAR)
    return pathlib.Path(env) if env else repo_root() / _CONFIG_RELPATH


def load(config_path: str | pathlib.Path | None = None, *, quiet: bool = False) -> BaseConfig:
    """Load and validate the base configuration.

    Raises rather than falling back to defaults: a run against an unknown or
    malformed configuration is worse than a run that refuses to start.
    `quiet` suppresses the notice/warning lines (for callers that only need
    the values, e.g. the CLI banner).
    """
    # Locate the config file, read it (folding in any `extends:` parent) ...
    path = selected_config_path(config_path)
    raw = _read_raw(path)
    # ... and validate it into a typed BaseConfig (unknown/invalid keys raise here).
    cfg = BaseConfig.model_validate({**raw, "config_path": path})
    cfg = resolve_scope_fleet(cfg)

    if quiet:
        return cfg

    # Print notices/warnings for declared-but-unused keys and still-open [CONFIRM] questions.
    if cfg.demand is not None:
        for notice in unconsumed_notices(cfg):
            print(f"[NOTICE] {notice}")

    for warning in open_question_warnings(cfg):
        print(f"[WARN] {warning}")

    return cfg


def fleet_members(cfg: BaseConfig, fleet: str) -> set[str]:
    """Every fleet string that qualifies as `fleet` (IMP-522).

    `fleet` may be a group's name or any one member of a group
    (`data.fleet_groups`): both give the whole group. A fleet in no group
    qualifies only itself, so an unconfigured run is unchanged.
    """
    for name, members in cfg.data.fleet_groups.items():
        if fleet == name or fleet in members:
            return {*members, fleet}
    return {fleet}


def _active_pilots(cfg: BaseConfig, fleet: str) -> int | None:
    """ACTIVE pilots in D1 at the scoped base and position whose fleet is `fleet`
    (or shares its type rating). None when D1 cannot be read."""
    import csv
    import gzip

    path = dataset_path(cfg, "d1_crew_master")
    if path is None:
        return None
    opener = gzip.open if path.name.endswith(".gz") else open
    members = fleet_members(cfg, fleet)
    try:
        with opener(path, "rt", encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
    except OSError:
        return None
    s = cfg.scope
    try:
        return sum(
            1 for r in rows
            if r["employment_status"] == "ACTIVE" and r["base"] == s.base
            and r["position"] == s.position and r["fleet"] in members
            and r.get("crew_group", "PILOT") == "PILOT"
        )
    except KeyError:
        return None


def resolve_scope_fleet(cfg: BaseConfig) -> BaseConfig:
    """Use `scope.fleet_fallback` when D1 holds more active pilots for it.

    A real extract may name a fleet more coarsely than the scope does (`A321`
    for what the scope calls `A321neoLR`), leaving the configured cell nearly
    empty. When `scope.fleet_fallback` is set and D1 holds strictly more ACTIVE
    pilots at this base/position for the fallback, the fallback becomes
    `scope.fleet` and `scope.fleet_resolution` says why. Otherwise nothing
    changes, so a config without a fallback (the mock's) reads exactly as before.
    """
    scope = cfg.scope
    if scope.fleet_fallback is None or scope.fleet_fallback == scope.fleet:
        return cfg
    configured = _active_pilots(cfg, scope.fleet)
    fallback = _active_pilots(cfg, scope.fleet_fallback)
    if configured is None or fallback is None or fallback <= configured:
        return cfg
    note = (
        f"scope fleet {scope.fleet} has {configured} ACTIVE pilot(s) at "
        f"{scope.base}/{scope.position} in D1, {scope.fleet_fallback} has {fallback}: "
        f"using {scope.fleet_fallback}"
    )
    return cfg.model_copy(update={
        "scope": scope.model_copy(update={"fleet": scope.fleet_fallback, "fleet_resolution": note})
    })


def corpus_kind(cfg: BaseConfig) -> str:
    """"MOCK" for the generated corpus, "REAL" for anything else (IMP-512).

    The mock ships a `_ground_truth.json` manifest (the generator's own answer
    key, what `score_recall` reads); a real extract cannot have one. A folder
    whose name starts `real_data` is REAL regardless.
    """
    corpus = cfg.paths.corpus_dir
    if any(part.startswith("real_data") for part in corpus.parts):
        return "REAL"
    return "MOCK" if (corpus / "_ground_truth.json").is_file() else "REAL"


def corpus_banner(cfg: BaseConfig) -> str:
    """One line naming the corpus a command is about to read."""
    try:
        shown = cfg.paths.corpus_dir.relative_to(repo_root())
    except ValueError:
        shown = cfg.paths.corpus_dir
    config_name = cfg.config_path.name if cfg.config_path else "?"
    return f"[{corpus_kind(cfg)} DATA] corpus={shown} config={config_name}"


def open_question_warnings(cfg: BaseConfig) -> list[str]:
    """Configured values that are internally contradictory and are waiting on
    a business answer, surfaced at load time rather than discovered as a
    baffling zero three layers down.

    Today there is one (IMP-117): a long-call reserve whose standby shift is
    no longer than L8's long-call notice can never be called out for a report
    later in the SAME shift -- the longest notice a shift can offer is less
    than its own length. Since OPEN-4 the eligibility pool only requires the
    RESERVE block to cover the REPORT time, and since IMP-116 a reserve called
    before that block starts is still held to its LC notice. So such a reserve
    CAN still be used, but only for an item known at least
    `long_call_notice_hours` before its report (displaced flying, a long-lead
    sick call, a cascade item past its visibility lag). Whether that happens
    is measured, not assumed: see kpis.reserve_usage_by_call_type.
    """
    warnings: list[str] = []
    if cfg.reserve_lines is not None and cfg.legality is not None:
        lc_notice = cfg.legality.long_call_notice_hours
        too_short = [s for s in cfg.reserve_lines.shifts if s.hours <= lc_notice]
        if too_short:
            names = ", ".join(f"{s.label} {s.window_label()}" for s in too_short)
            scope = ("every" if len(too_short) == len(cfg.reserve_lines.shifts) else "some")
            buying = policies_buying_long_call(cfg)
            who = (f" Policies buying long-call reserves: {', '.join(buying)}." if buying else "")
            warnings.append(
                f"{scope} standby shift is no longer than legality.long_call_notice_hours "
                f"({lc_notice:g}h) -- {names}. A long-call reserve on such a shift can never be "
                f"called out for a report later in the same shift; they can only cover items "
                f"known at least {lc_notice:g}h before report. Check the LC line of the "
                f"'reserve usage by call type' KPI: LC reserve-days paid with zero LC "
                f"assignments means they are bought and never used.{who} This is the open "
                f"[CONFIRM: Crew Planning] question recorded in configs/base.yaml -> "
                f"reserve_lines, not a simulation result."
            )
    return warnings


def policies_buying_long_call(cfg: BaseConfig) -> list[str]:
    """Policy files under configs/policies/ with any long_call > 0 (IMP-117).

    Read as raw YAML rather than through engine.policy.load_policy: config.py
    sits below the engine in the dependency order and must not import it.
    """
    if cfg.config_path is None:
        return []
    policies_dir = cfg.config_path.parent / "policies"
    if not policies_dir.is_dir():
        return []
    names: list[str] = []
    for path in sorted(policies_dir.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        reserves = (raw.get("stage1") or {}).get("reserves") or []
        if any((r or {}).get("long_call", 0) > 0 for r in reserves):
            names.append(path.stem)
    return names


def load_costs(cfg: BaseConfig) -> CostsConfig:
    """Load the cost-coefficient file `cfg.costs_file` references.

    Resolved relative to base.yaml's own directory -- `costs_file` is a bare
    filename (see C3, §2.3), not a second `paths.*` key. Inventing a
    `paths.costs_dir` entry would be a config key nobody asked for; the costs
    file lives next to the config that names it.
    """
    if cfg.config_path is None:
        raise ValueError("cfg.config_path is unset; load the config via config.load()")
    path = cfg.config_path.parent / cfg.costs_file
    if not path.is_file():
        raise FileNotFoundError(
            f"costs_file {cfg.costs_file!r} (from {cfg.config_path}) not found at {path}"
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return CostsConfig.model_validate({**raw, "config_path": path})


def verify_policy_costs(cfg: BaseConfig, policy: Any, costs: CostsConfig) -> None:
    """AUD-16: make a policy's `costs_file` pin a CHECK, not a label.

    C3 (§2.3) promises policies "hash-pinned to a cost-coefficient file
    version", but every run loads `cfg.costs_file` and the policy's own
    `costs_file` string only ever reached provenance displays -- a policy
    claiming v3.2.1 silently priced against whatever base.yaml pointed at.
    Called at the single chokepoint every simulation passes through
    (des.run_scenario / run_historical_replay).

    Accepts `name` or `name@version`. A bare name pins the file only.
    """
    pinned = getattr(policy, "costs_file", None)
    if not pinned:
        return
    name, _, version = pinned.partition("@")
    if name != cfg.costs_file:
        raise ValueError(
            f"policy {getattr(policy, 'policy_id', '?')!r} pins costs file {name!r} "
            f"but this run loads {cfg.costs_file!r} (configs/base.yaml -> costs_file)"
        )
    if version and version != costs.version:
        raise ValueError(
            f"policy {getattr(policy, 'policy_id', '?')!r} pins {name}@{version} "
            f"but the loaded file's version is {costs.version!r} -- update the "
            f"policy pin or load the pinned costs version"
        )


# Config fields that are deliberately declared ahead of the code that will read
# them. THE single source of truth: unconsumed_notices() surfaces these at
# runtime, and tests/test_config.py's consumption guard treats exactly this set
# as permitted. A field missing from both is a bug -- a documented knob that
# silently does nothing, which is how `mode` (S1c-01) and `appr_compensation`
# (S1b-06) each shipped unnoticed.
DECLARED_NOT_YET_CONSUMED: dict[str, str] = {
    "demand.pairings_per_bid_period":
        "flying is exogenous until slice 1b",
    "demand.credit_hours_per_bid_period":
        "flying is exogenous until slice 1b",
}


def unconsumed_notices(cfg: BaseConfig) -> list[str]:
    """Keys that are declared in config but not yet read by any code path.

    The `demand.pairings_per_bid_period` pattern (§4.4): flying is generated
    exogenously until slice 1b, when sick calls bind to real roster crew and
    pairings come from dataset D3. Declaring the key now and warning on it
    beats leaving it out (silent) or wiring it to a stub (silently wrong).
    """
    # IMP-213: built once, from the registry alone. A key is reported only if
    # it is actually set in this config -- an absent section or a None value
    # has nothing to warn about. (This used to skip every `demand.` key and
    # then re-add the same two notices by hand.)
    notices: list[str] = []
    for key, why in sorted(DECLARED_NOT_YET_CONSUMED.items()):
        value: Any = cfg
        for part in key.split("."):
            value = getattr(value, part, None)
            if value is None:
                break
        if value is not None:
            notices.append(f"{key} is declared but not yet consumed by any code path ({why})")
    return notices


# ========================================================== [CONFIRM] markers
class ConfirmMarker(BaseModel):
    file: pathlib.Path
    line: int
    owner: str
    text: str


_CONFIRM_RE = re.compile(r"\[CONFIRM:\s*([^\]]+)\]")


def find_confirm_markers(path: pathlib.Path) -> list[ConfirmMarker]:
    """Every `[CONFIRM: <owner>]` marker in a config file's raw text.

    YAML comments never survive `yaml.safe_load` -- a marker on a trailing
    comment, a block comment above a section, or a single file-level marker
    covering every value (costs_pilots.yaml's header) would all vanish if
    this scanned the parsed mapping instead of the file's own bytes. Never
    tie a placeholder to a default: the marker must stay visible, not be
    silently resolved into a plausible-looking number (§4.4).

    Deliberately does not try to distinguish a real marker from the
    `[CONFIRM: <owner>]` convention example in base.yaml's own header
    comment (§4.4): a value-based filter on the literal text `<owner>` would
    also hide a genuine, unfilled placeholder someone pastes from that same
    template -- exactly the "placeholder hardens into a fact" failure this
    function exists to prevent. Surfacing one harmless extra line is the
    safer failure mode.
    """
    markers = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for m in _CONFIRM_RE.finditer(line):
            markers.append(
                ConfirmMarker(file=path, line=n, owner=m.group(1).strip(), text=line.strip())
            )
    return markers


def all_confirm_markers(cfg: BaseConfig) -> list[ConfirmMarker]:
    """[CONFIRM] markers across every config file this run actually used."""
    markers = []
    if cfg.config_path is not None:
        markers += find_confirm_markers(cfg.config_path)
        costs_path = cfg.config_path.parent / cfg.costs_file
        if costs_path.is_file():
            markers += find_confirm_markers(costs_path)
    return markers


# Accepted on-disk encodings for a dataset. Polars reads both transparently,
# so callers should never care which one is present.
DATASET_SUFFIXES = (".csv", ".csv.gz")


def dataset_path(cfg: BaseConfig, name: str) -> pathlib.Path | None:
    """Locate dataset `name` inside the configured corpus, or None.

    The single place in the codebase that knows how a dataset is stored. Callers
    ask for `d2_rosters`; whether it is CSV or gzipped CSV is not their problem.
    """
    corpus = cfg.paths.corpus_dir
    for suffix in DATASET_SUFFIXES:
        candidate = corpus / f"{name}{suffix}"
        if candidate.is_file():
            return candidate
    return None


# Output locations. They are created on first write, not kept in the repository:
# a checkout carries inputs (the corpus) and code, never run output.
OUTPUT_PATH_KEYS = ("params_dir", "reports_dir")


def ensure_dir(cfg: BaseConfig, key: str) -> pathlib.Path:
    """Resolve an output `paths.*` key and create it if it does not exist.

    Writers call this instead of `resolve`; nothing else may create directories,
    so an empty output tree is always the result of a run, never of a checkout.
    """
    path = resolve(cfg, key)
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve(cfg: BaseConfig, key: str) -> pathlib.Path:
    """Look up a `paths.*` key by name.

    Already absolute: `PathsConfig` resolves every field at validation time,
    so this is an attribute lookup with a friendly error, not a second
    resolution step.

    >>> resolve(load(), "corpus_dir")   # -> <repo>/src/crewsim/data/corpus
    """
    try:
        return getattr(cfg.paths, key)  # type: ignore[no-any-return]
    except AttributeError as exc:
        known = sorted(cfg.paths.model_fields)
        raise KeyError(f"paths.{key} is not defined. Known keys: {known}") from exc


def policies_dir() -> pathlib.Path:
    """`configs/policies/` -- where named policies (R4, R10, ...) live."""
    return repo_root() / "configs" / "policies"


def policy_path(name_or_path: str | pathlib.Path) -> pathlib.Path:
    """Resolve a policy argument to a file: an existing path as given, else
    `configs/policies/<name>.yaml`.

    IMP-612: the one resolver. The CLI, the grid runner, the report, gate V9
    and the API each used to build this path themselves (two helpers plus
    a dozen inline f-strings), so a rule change -- such as IMP-301's
    allow-list -- had to be made in every one of them.
    """
    p = pathlib.Path(name_or_path)
    if p.is_file():
        return p
    return policies_dir() / f"{name_or_path}.yaml"


def params_store_path(cfg: BaseConfig, season: str) -> pathlib.Path:
    """`<params_dir>/params_v<version>_<season>.json` -- the one place this name is built.

    IMP-412: calibration (writer), scenario generation, the simulation and
    provenance (readers) used to build it separately, each with its own
    "unknown" version fallback. One helper, one version source
    (`crewsim.package_version`), so writer and readers can never disagree.
    """
    return resolve(cfg, "params_dir") / params_store_filename(season)


def params_store_filename(season: str) -> str:
    """`params_v<version>_<season>.json`. Split out so the writer can join it
    onto the directory `ensure_dir` returned (and created)."""
    from . import package_version

    return f"params_v{package_version()}_{season}.json"
