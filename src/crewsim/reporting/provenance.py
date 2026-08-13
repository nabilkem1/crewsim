"""Provenance of the frozen parameter store a run reads.

Lifted out of `cli.py` (where it was `_params_provenance`) so the web API can
report the same thing on the same terms. The rule it encodes is the one that
matters: **a missing store is reported as missing, never defaulted.** A
provenance chain that invents a version is worse than one that admits a gap,
because regenerating the result a year from now is the entire point.
"""

from __future__ import annotations

import json

from .. import config


def params_provenance(cfg: config.BaseConfig) -> tuple[str, str]:
    """`(params_version, content_hash)` for this run's parameter store.

    Real values off the store that calibration emitted --
    `calibration/pipeline.py` writes `params_version` and a blake2b
    `content_hash` receipt into `output/params/params_v<ver>_<season>.json`.

    Returns `("MISSING", <explanation>)` when there is no store for the
    configured season, which is a normal state, not an error: it is what a
    fresh checkout looks like before `crewsim calibrate --emit` has run.
    """
    from ..engine import des

    params_dir = config.resolve(cfg, "params_dir")
    path = params_dir / f"params_v{des._package_version()}_{cfg.scope.season}.json"
    if not path.is_file():
        return "MISSING", f"no parameter store at {path.name} -- run `crewsim calibrate --emit`"
    store = json.loads(path.read_text())
    return store.get("params_version", "unknown"), store.get("content_hash", "unknown")


# The store already carries its own prefixes -- `params_version` is "v0.1.0",
# not "0.1.0", and `content_hash` is "blake2b:87de6f4a...", not a bare digest.
# Re-adding them at the call site produced "params_vv0.1.0 (blake2b:blake2b:...)",
# which is why this formatting lives here rather than in an f-string per caller.
_HASH_PREFIX_SEPARATOR = ":"
_DIGEST_DISPLAY_CHARS = 8


def format_params_provenance(version: str, content_hash: str) -> str:
    """`params_v0.1.0 (blake2b:87de6f4a...)` -- a one-line display form.

    The digest is truncated for reading; the full value stays in the API
    payload and in the CLI's provenance footer, which are what a reproduction
    would actually use.
    """
    if version == "MISSING":
        return f"MISSING -- {content_hash}"

    algo, sep, digest = content_hash.partition(_HASH_PREFIX_SEPARATOR)
    if sep:
        shown = f"{algo}{sep}{digest[:_DIGEST_DISPLAY_CHARS]}..."
    else:
        shown = f"{content_hash[:_DIGEST_DISPLAY_CHARS]}..."
    return f"params_{version} ({shown})"
