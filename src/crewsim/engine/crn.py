"""Common Random Numbers (CRN) stream management.

Provides process-stable, cross-platform reproducible seeding using blake2b,
never Python's process-salted built-in hash function.
"""

import hashlib
import json
from typing import Any

from numpy.random import PCG64, Generator, SeedSequence


def stable_seed(key: Any) -> int:
    """
    Generate a stable 128-bit integer seed from any JSON-serializable key using blake2b.
    Must never use Python's built-in hash function.
    """
    if isinstance(key, int):
        return key

    serialized = json.dumps(key, sort_keys=True).encode("utf-8")
    digest = hashlib.blake2b(serialized, digest_size=16).digest()
    return int.from_bytes(digest, byteorder="little")


def generate_streams(master_key: Any, n_scenarios: int) -> list[SeedSequence]:
    """Derive `n_scenarios` independent streams from a master key."""
    seed = stable_seed(master_key)
    sq = SeedSequence(seed)
    return sq.spawn(n_scenarios)


def event_rng(scenario_stream: SeedSequence, event_uid: str) -> Generator:
    """Derive an isolated PRNG for a single event to maintain CRN alignment."""
    event_seed = stable_seed(event_uid)
    seq = SeedSequence(
        entropy=scenario_stream.entropy, spawn_key=scenario_stream.spawn_key + (event_seed,)
    )
    return Generator(PCG64(seq))
