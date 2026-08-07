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
import pathlib
import re
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

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


class DemandConfig(_Model):
    """Declared but not consumed until slice 1b (§4.4.1). See `load()`."""

    pairings_per_bid_period: int | None = None
    credit_hours_per_bid_period: int | None = None
    
    # Hours before departure to hold an open item before cancelling.
    # e.g., {"short_haul": 2.0, "long_haul": 4.0, "default": 2.0}
    uncovered_deadline_hours: dict[str, float] | float = 0.0


class SensitivityConfig(_Model):
    roster_size: list[int]
    terminal_penalty: list[float]
    lambda_risk_dial: list[float]


class QualityGateThresholds(_Model):
    d4_link_pass: float
    d4_link_marginal: float
    d6_d7_join_pass: float
    d9_completeness_pass: float


class RegimeQuantiles(_Model):
    p_calm: float
    p_normal: float
    p_disrupted: float


class CalibrationConfig(_Model):
    delay_gmm_components: int
    delay_gmm_random_state: int
    regime_quantiles: RegimeQuantiles
    overdispersion_threshold: float


class DraftReconstructionConfig(_Model):
    """S0-03, §6.3-1: the D6 x D7 join, spelled out as data.

    A NULL `initiator` always passes regardless of `initiator_filter` --
    that is enforced by the reconstruction code, not expressible as a config
    value, because "handle it, don't drop it silently" is the requirement.
    """

    premium_pay_codes: list[str]
    short_notice_reason_codes: list[str]
    initiator_filter: list[str]


class CascadeReconstructionConfig(_Model):
    """S0-05, §6.3-3: the 7-day follow-on scan."""

    window_days: int
    cascade_reason_codes: list[str]
    confidence_level: float


class BaseConfig(_Model):
    paths: PathsConfig
    scope: ScopeConfig
    horizon: HorizonConfig
    population: PopulationConfig
    quality_gates: QualityGateThresholds
    calibration: CalibrationConfig
    draft_reconstruction: DraftReconstructionConfig
    cascade_reconstruction: CascadeReconstructionConfig
    mode: str
    costs_file: str
    windows: WindowsConfig | None = None
    demand: DemandConfig | None = None
    sensitivity: SensitivityConfig | None = None
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


class DisruptionCosts(_Model):
    cancellation: float
    delay_per_minute: float
    terminal_penalty_multiple: float


class APPRCompensation(_Model):
    hours_3_to_6: float
    hours_6_to_9: float
    hours_9_plus: float


class CostsConfig(_Model):
    version: str
    reserve: ReserveCosts
    draft: DraftCosts
    positioning: PositioningCosts
    disruption: DisruptionCosts
    appr_compensation: APPRCompensation
    config_path: pathlib.Path | None = None


# ==================================================================== loading
def load(config_path: str | pathlib.Path | None = None) -> BaseConfig:
    """Load and validate the base configuration.

    Raises rather than falling back to defaults: a run against an unknown or
    malformed configuration is worse than a run that refuses to start.
    """
    path = pathlib.Path(config_path) if config_path else repo_root() / _CONFIG_RELPATH
    if not path.is_file():
        raise FileNotFoundError(
            f"configuration not found at {path}. "
            f"Every value this simulation uses lives in configs/ (§4.4)."
        )
    raw = yaml.safe_load(path.read_text()) or {}
    cfg = BaseConfig.model_validate({**raw, "config_path": path})

    if cfg.demand is not None:
        for notice in unconsumed_notices(cfg):
            print(f"[NOTICE] {notice}")

    return cfg


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
    raw = yaml.safe_load(path.read_text()) or {}
    return CostsConfig.model_validate({**raw, "config_path": path})


def unconsumed_notices(cfg: BaseConfig) -> list[str]:
    """Keys that are declared in config but not yet read by any code path.

    The `demand.pairings_per_bid_period` pattern (§4.4): flying is generated
    exogenously until slice 1b, when sick calls bind to real roster crew and
    pairings come from dataset D3. Declaring the key now and warning on it
    beats leaving it out (silent) or wiring it to a stub (silently wrong).
    """
    notices = []
    if cfg.demand is not None:
        if cfg.demand.pairings_per_bid_period is not None:
            notices.append(
                "demand.pairings_per_bid_period is declared but not yet consumed by any "
                "code path (flying is exogenous until slice 1b)"
            )
        if cfg.demand.credit_hours_per_bid_period is not None:
            notices.append(
                "demand.credit_hours_per_bid_period is declared but not yet consumed by any "
                "code path (flying is exogenous until slice 1b)"
            )
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
    for n, line in enumerate(path.read_text().splitlines(), 1):
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
