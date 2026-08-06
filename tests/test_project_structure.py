"""S0-00 — the project structure enforces its own rules.

These tests exist because both rules are trivial to violate and expensive to
retrofit:

  1. The corpus ships with the package. src/crewsim/data/ holds the loaders AND
     the datasets they read, so a fresh checkout runs with no generation step.
     generated/ is for run output only (params, reports) and stays ignored.
  2. No path is ever hard-coded. Everything comes from configs/base.yaml.

If either is broken, the failure message says what to do about it.
"""
from __future__ import annotations

import importlib
import re

import pytest

from crewsim import config
from crewsim.cli import EXPECTED_DATASETS, EXPECTED_MODULES

ROOT = config.repo_root()
SRC = ROOT / "src" / "crewsim"


# --------------------------------------------------------------------- layout
@pytest.mark.parametrize("module", EXPECTED_MODULES)
def test_every_specified_module_exists(module: str) -> None:
    """§4.2's layout is the contract. Empty modules are fine; missing ones are not."""
    importlib.import_module(module)


def test_expected_package_directories_exist() -> None:
    for pkg in ("data", "calibration", "scenarios", "engine", "optimize", "reporting"):
        assert (SRC / pkg / "__init__.py").is_file(), f"src/crewsim/{pkg} is not a package"


def test_entry_point_is_declared() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert 'crewsim = "crewsim.cli:main"' in pyproject, (
        "pyproject.toml must declare the crewsim entry point, or `crewsim doctor` "
        "will not exist after `uv sync`"
    )


# ------------------------------------------- rule 1: the corpus ships with the code
def test_corpus_lives_inside_the_package() -> None:
    """The datasets sit next to their loaders, under src/crewsim/data/.

    A checkout is runnable immediately: no generation step, no external fetch,
    and the exact bytes the loaders were written against are the bytes on disk.
    """
    corpus = SRC / "data" / "corpus"
    assert corpus.is_dir(), (
        f"{corpus.relative_to(ROOT)} is missing. The corpus ships with the "
        f"package; regenerate it with: python generated/data/generate_mock_corpus.py"
    )


def test_corpus_is_not_git_ignored() -> None:
    """The corpus is committed. Nothing in .gitignore may quietly exclude it."""
    patterns = [
        line.strip()
        for line in (ROOT / ".gitignore").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    offenders = [
        p for p in patterns
        if not p.startswith("!") and p.rstrip("/") in {"src", "src/crewsim/data",
                                                       "src/crewsim/data/corpus",
                                                       "corpus", "*.csv", "*.json"}
    ]
    assert not offenders, (
        f".gitignore excludes the committed corpus: {offenders}. "
        f"src/crewsim/data/corpus/ must reach the repository."
    )


def test_corpus_ships_in_the_wheel() -> None:
    """Package data must not fall out of the build.

    hatchling includes every file under the packaged directory, so the corpus
    ships as long as src/crewsim is the wheel package root.
    """
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert 'packages = ["src/crewsim"]' in pyproject, (
        "the wheel must package src/crewsim as a whole, or the corpus under "
        "src/crewsim/data/corpus/ is silently dropped from the distribution"
    )


# ------------------------------------------------ rule 2: no hard-coded paths
# The one permitted literal: something has to know where the config file lives.
BOOTSTRAP = SRC / "config.py"

# A path literal names a DATA LOCATION — it points at the corpus or at generated
# output. Two things are deliberately *not* caught:
#   * bare file suffixes  — config.DATASET_SUFFIXES is their single authority,
#                           guarded by test_dataset_suffixes_have_one_authority
#   * "configs/base.yaml" — the bootstrap, guarded by its own test, and harmless
#                           when it appears in help text rather than in an open()
FORBIDDEN = re.compile(
    r"""["'][^"']*(generated/|corpus/|/corpus|\w+/\w+\.(csv|parquet|json))[^"']*["']"""
)


def test_no_hard_coded_paths_in_src() -> None:
    """Every path comes from configs/base.yaml -> paths (§4.4.1b).

    Pointing the loaders at Air Transat's real extracts must be a one-line
    config change, not a search-and-replace through the package.
    """
    offenders: list[str] = []
    for py in SRC.rglob("*.py"):
        if py == BOOTSTRAP:
            continue
        for n, line in enumerate(py.read_text().splitlines(), 1):
            code = line.split("#", 1)[0]
            if FORBIDDEN.search(code):
                offenders.append(f"{py.relative_to(ROOT)}:{n}: {line.strip()}")
    assert not offenders, (
        "hard-coded data paths found:\n  " + "\n  ".join(offenders)
        + "\nUse config.resolve(cfg, 'corpus_dir') instead — the corpus shipping "
          "inside the package is exactly why reaching for it by literal is tempting, "
          "and exactly why it must not happen: the real extracts live elsewhere."
    )


def test_bootstrap_literal_is_the_only_exception() -> None:
    """Guard the guard: if config.py stops being the bootstrap, this test tells us."""
    assert '_CONFIG_RELPATH = "configs/base.yaml"' in BOOTSTRAP.read_text()


def test_dataset_suffixes_have_one_authority() -> None:
    """Only config.py may know how a dataset is stored on disk.

    Otherwise every caller grows its own .csv / .csv.gz fallback, and moving the
    corpus to Parquet becomes a search-and-replace instead of a one-line change.
    """
    from crewsim import config as cfgmod

    assert cfgmod.DATASET_SUFFIXES, "config.DATASET_SUFFIXES must exist"
    suffix_literal = re.compile(r"""["']\.csv(\.gz)?["']""")
    offenders = [
        str(py.relative_to(ROOT))
        for py in SRC.rglob("*.py")
        if py != BOOTSTRAP and suffix_literal.search(py.read_text())
    ]
    assert not offenders, (
        f"dataset suffixes hard-coded outside config.py: {offenders}. "
        f"Use config.dataset_path() instead."
    )


# ------------------------------------------------------------------- wiring
def test_configured_paths_resolve() -> None:
    cfg = config.load()
    for key in ("corpus_dir", "params_dir", "reports_dir"):
        assert config.resolve(cfg, key).is_dir(), f"paths.{key} does not exist"


def test_corpus_dir_points_at_package_data() -> None:
    cfg = config.load()
    corpus = config.resolve(cfg, "corpus_dir").relative_to(ROOT)
    assert corpus.as_posix() == "src/crewsim/data/corpus", (
        f"the data source is src/crewsim/data/corpus, not {corpus}"
    )


def test_all_twelve_datasets_are_present() -> None:
    cfg = config.load()
    missing = [n for n in EXPECTED_DATASETS if config.dataset_path(cfg, n) is None]
    assert not missing, (
        f"missing datasets: {missing}. "
        f"Regenerate with: python generated/data/generate_mock_corpus.py"
    )


def test_generated_is_git_ignored() -> None:
    """generated/ now holds run output only — params and reports, never inputs."""
    ignore = (ROOT / ".gitignore").read_text().splitlines()
    assert any(line.strip().rstrip("/") == "generated" for line in ignore), (
        ".gitignore must exclude generated/ — calibration output and HTML reports "
        "are rebuilt on every run and must not reach the repository"
    )
