"""Allow `python -m crewsim …` without installing the package."""
import sys

from .cli import main

sys.exit(main())
