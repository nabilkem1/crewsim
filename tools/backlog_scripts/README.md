# One-shot backlog scripts

These seven scripts were written to bulk-edit `backlog/` during authoring
(formatting epics, injecting user-story narratives, finding stories missing a
field). They ran once, against a state of the backlog that no longer exists, and
nothing imports them.

They lived at the repository root until 2026-08-09, where they read as part of
the package. They are kept — not deleted — because they document how the backlog
was generated, but they are not maintained and are not expected to run against
the current `backlog/`.

`crewsim_skeleton.py` is deliberately **not** here. It is the reference
implementation the spec and `src/crewsim/engine/des.py` both cite, and 12 files
across the repo point at it by path.
