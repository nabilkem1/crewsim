"""Crew Reserve & Drafting Policy Optimisation System.

An offline policy-simulation tool for sizing reserve crew establishment.
See spec_sections/ for the specification; backlog/ for the delivery plan.
"""
__version__ = "0.1.0"


def package_version() -> str:
    """The crewsim version, the same whether or not the package is installed.

    IMP-412: installed metadata first, then `__version__` -- never "unknown".
    Running from source (`PYTHONPATH=src`) used to fall back to "unknown", so
    calibration wrote `params_vunknown_<season>.json` while an installed run
    looked for `params_v0.1.0_<season>.json` (and vice versa).
    `tests/test_project_structure.py` keeps `__version__` equal to
    pyproject.toml's `version`, so both sources agree.
    """
    import importlib.metadata

    try:
        return importlib.metadata.version("crewsim")
    except importlib.metadata.PackageNotFoundError:
        return __version__
