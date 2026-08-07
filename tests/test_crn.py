"""Tests for CRN stream management (S1a-05)."""

from pathlib import Path

from crewsim.engine import crn


def test_stable_seed_is_reproducible() -> None:
    """Ensure stable_seed produces identical output across calls."""
    seed1 = crn.stable_seed({"some": "key", "array": [1, 2, 3]})
    seed2 = crn.stable_seed({"array": [1, 2, 3], "some": "key"})
    assert seed1 == seed2


def test_streams_are_independent() -> None:
    """Ensure spawn produces independent sequences."""
    streams = crn.generate_streams("master_seed", 2)
    rng1 = crn.event_rng(streams[0], "event_1")
    rng2 = crn.event_rng(streams[1], "event_1")

    assert rng1.random() != rng2.random()


def test_event_rng_is_aligned() -> None:
    """Ensure two streams initialized identically yield the same event RNGs."""
    streams1 = crn.generate_streams("master_seed", 1)
    streams2 = crn.generate_streams("master_seed", 1)

    rng1 = crn.event_rng(streams1[0], "event_A")
    rng2 = crn.event_rng(streams2[0], "event_A")

    assert rng1.random() == rng2.random()


def test_no_builtin_hash_usage() -> None:
    """Ensure hash() is not used in the codebase for seeding."""
    repo_root = Path(__file__).parent.parent
    src_dir = repo_root / "src" / "crewsim"

    bad_files = []
    for filepath in src_dir.rglob("*.py"):
        text = filepath.read_text(encoding="utf-8")
        if "hash(" in text:
            # We want to exclude hashlib or content_hash, just raw hash(
            # A simple heuristic: check for ` hash(` or `(hash(` or `[hash(` or `hash(` at start of line
            import re

            if re.search(r"\bhash\(", text):
                bad_files.append(filepath.name)

    assert not bad_files, f"Built-in hash() is banned for seeding, found in: {bad_files}"
