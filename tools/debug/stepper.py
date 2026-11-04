"""Shared machinery for the step-by-step debug drivers in tools/debug/.

Two kinds of stop, both installed at runtime (nothing in src/ is modified,
nothing changes unless a driver is the entry point):

LineStop  -- stops ON A REAL SOURCE LINE inside crewsim (e.g. nhpp.py, the line
             `model = smf.negativebinomial(...)`), just BEFORE it runs. The
             editor opens the crewsim file at that line and the Variables panel
             shows that function's own locals (df, pdf, counts, matrix, ...).
             The line is found by a text anchor, so it follows code edits; the
             resolved file:line table is printed at start-up.
             How: the target function is recompiled from its own source with a
             `breakpoint()` inserted before the anchor line, keeping the real
             file name and line numbers, and swapped in via `__code__`. Your own
             VS Code breakpoints in the same files keep working.
             A local `debug_step` (Variables panel) says which step you are on.

Step      -- wraps a function and stops in the wrapper just before the call
             (used by compare_steps.py). F11 twice steps into the function.

Keys at a stop (VS Code)
------------------------
  F10        run the highlighted line, see its result in Variables
  F11        step into the call on that line
  Shift+F11  finish the current function, back to its caller
  F5         run to the next step
  Debug Console: any expression, e.g. `df.head()`, `pdf.shape`, `res.summary()`

Environment variables (set in .vscode/launch.json)
--------------------------------------------------
CREWSIM_STEPS      "all" (default), or ids and ranges: "C05,C20-C26".
CREWSIM_STEP_MAX   default max stops per step (default 2). A step can set its own.
CREWSIM_STEP_MODE  "break" (default) stops; "trace" prints one line per hit.

Without a debugger attached, "break" falls back to Python's pdb.
"""
from __future__ import annotations
import __future__

import ast
import functools
import inspect
import os
import re
import sys
import textwrap
import types
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from crewsim import cli, config


@dataclass
class Step:
    """Stop in a wrapper just before `owner.attr(...)` is called."""
    id: str
    owner: Any            # module, class, or object instance holding the function
    attr: str             # function / method name on `owner`
    what: str             # one-line explanation shown at the stop
    max_stops: int | None = None                                   # overrides CREWSIM_STEP_MAX
    when: Callable[[tuple[Any, ...], dict[str, Any]], bool] | None = None  # extra filter

    @property
    def label(self) -> str:
        return self.attr


@dataclass
class LineStop:
    """Stop inside `func`, just before the first line containing `anchor`."""
    id: str
    func: Callable[..., Any]   # module-level function, e.g. nhpp.fit_sick_calls
    anchor: str                # text on the FIRST line of the target statement
    what: str                  # what to look at when stopped there
    occurrence: int = 1        # use the n-th line containing `anchor`
    max_stops: int | None = None
    when: Callable[[dict[str, Any]], bool] | None = None   # gets the frame's locals
    # filled by install():
    file: str = field(default="", init=False)
    line: int = field(default=0, init=False)

    @property
    def label(self) -> str:
        return f"{os.path.basename(self.file)}:{self.line}"


# --------------------------------------------------------------------------- selection

_SELECTED = os.environ.get("CREWSIM_STEPS", "all").strip()
_MAX_HITS = int(os.environ.get("CREWSIM_STEP_MAX", "2"))
_MODE = os.environ.get("CREWSIM_STEP_MODE", "break").strip().lower()
_hits: Counter[str] = Counter()
_stops: Counter[str] = Counter()


def _split_id(step_id: str) -> tuple[str, int]:
    m = re.fullmatch(r"([A-Za-z]+)(\d+)", step_id.strip())
    if not m:
        raise ValueError(f"bad step id {step_id!r} (expected e.g. C05)")
    return m.group(1).upper(), int(m.group(2))


def _enabled(step_id: str) -> bool:
    if _SELECTED.lower() == "all":
        return True
    prefix, num = _split_id(step_id)
    for token in filter(None, (t.strip() for t in _SELECTED.split(","))):
        if "-" in token:
            lo, hi = (_split_id(t) for t in token.split("-", 1))
            if lo[0] == prefix and lo[1] <= num <= hi[1]:
                return True
        elif _split_id(token) == (prefix, num):
            return True
    return False


def _decide(step_id: str, label: str, what: str, max_stops: int | None) -> bool:
    _hits[step_id] += 1
    if not _enabled(step_id):
        return False
    if _MODE == "trace":
        print(f"[{step_id}] {label} hit {_hits[step_id]}", file=sys.stderr)
        return False
    limit = max_stops if max_stops is not None else _MAX_HITS
    if _stops[step_id] >= limit:
        return False
    _stops[step_id] += 1
    print(f"\n[{step_id}] {label} -- stop {_stops[step_id]}/{limit} (hit {_hits[step_id]})\n"
          f"      {what}", file=sys.stderr)
    return True


# --------------------------------------------------------------------------- wrapper steps

def _wrap(step: Step, original: Any) -> Any:
    name = getattr(original, "__qualname__", step.attr)

    def should_stop(args: tuple[Any, ...], kwargs: dict[str, Any]) -> bool:
        if step.when is not None and not step.when(args, kwargs):
            return False
        return _decide(step.id, step.attr, step.what, step.max_stops)

    if inspect.isgeneratorfunction(original):
        @functools.wraps(original)
        def gen_wrapper(*args: Any, **kwargs: Any) -> Any:
            if should_stop(args, kwargs):
                step_id, description, function = step.id, step.what, name  # noqa: F841 - shown in Variables
                breakpoint()  # <- STOP. See Variables. F11 x2 = step into, Shift+F11 = back to caller.
            result = yield from original(*args, **kwargs)
            return result
        return gen_wrapper

    @functools.wraps(original)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if should_stop(args, kwargs):
            step_id, description, function = step.id, step.what, name  # noqa: F841 - shown in Variables
            breakpoint()  # <- STOP. See Variables. F11 x2 = step into, Shift+F11 = back to caller.
        result = original(*args, **kwargs)
        return result  # <- after F10 on the line above, inspect `result` here
    return wrapper


def _install_wrapper(step: Step, crewsim_modules: list[types.ModuleType]) -> None:
    owner = step.owner
    if inspect.isclass(owner) or isinstance(owner, types.ModuleType):
        original = inspect.getattr_static(owner, step.attr)
    else:
        original = getattr(owner, step.attr)  # bound method of an instance (e.g. scipy's lognorm)
    wrapped = _wrap(step, original)
    setattr(owner, step.attr, wrapped)
    if isinstance(owner, types.ModuleType):
        # The same function is often imported by name elsewhere
        # (`from .loaders import load_dataset`); rebind those too.
        for mod in crewsim_modules:
            if getattr(mod, step.attr, None) is original:
                setattr(mod, step.attr, wrapped)


# --------------------------------------------------------------------------- line stops

_LINE_STOPS: dict[str, LineStop] = {}
_HOOK = "_crewsim_debug_step"   # global injected into each patched module
_LOCAL = "debug_step"           # local visible in the Variables panel at a stop


def _line_hook(step_id: str, frame_locals: dict[str, Any]) -> str:
    """Called by the injected code. Returns a non-empty string to stop."""
    s = _LINE_STOPS[step_id]
    if s.when is not None and not s.when(frame_locals):
        return ""
    if _decide(s.id, s.label, s.what, s.max_stops):
        return f"{s.id} {s.label}: {s.what}"
    return ""


def _injected(step_id: str, lineno: int) -> list[ast.stmt]:
    # debug_step = _crewsim_debug_step("C05", locals())
    # if debug_step: breakpoint()
    src = f"{_LOCAL} = {_HOOK}({step_id!r}, locals())\nif {_LOCAL}: breakpoint()\n"
    stmts = ast.parse(src).body
    for node in stmts:
        for sub in ast.walk(node):
            if hasattr(sub, "lineno"):
                # One line BEFORE the target: after breakpoint() returns, the
                # target line starts and the debugger/pdb stops there.
                sub.lineno = sub.end_lineno = lineno - 1
    return stmts


def _insert_before(tree: ast.AST, lineno: int, new: list[ast.stmt]) -> bool:
    for node in ast.walk(tree):
        for attr in ("body", "orelse", "finalbody", "handlers"):
            block = getattr(node, attr, None)
            if not isinstance(block, list):
                continue
            for i, stmt in enumerate(block):
                if isinstance(stmt, ast.stmt) and stmt.lineno == lineno:
                    block[i:i] = new
                    return True
    return False


def _install_lines(stops: list[LineStop]) -> None:
    by_func: dict[Any, list[LineStop]] = {}
    for s in stops:
        by_func.setdefault(s.func, []).append(s)
        _LINE_STOPS[s.id] = s

    for func, func_stops in by_func.items():
        code = func.__code__
        if code.co_freevars:
            raise TypeError(f"{func.__qualname__}: closures are not supported, use a Step")
        lines, first = inspect.getsourcelines(func)
        tree = ast.parse(textwrap.dedent("".join(lines)))
        ast.increment_lineno(tree, first - 1)
        if _LOCAL in code.co_varnames:
            raise NameError(f"{func.__qualname__} already has a local named {_LOCAL!r}")

        for s in func_stops:
            matches = [first + i for i, text in enumerate(lines) if i > 0 and s.anchor in text]
            if len(matches) < s.occurrence:
                raise LookupError(
                    f"[{s.id}] anchor {s.anchor!r} not found in {func.__qualname__} "
                    f"({code.co_filename}) -- the code changed, update the step table")
            s.file, s.line = code.co_filename, matches[s.occurrence - 1]
            if not _insert_before(tree, s.line, _injected(s.id, s.line)):
                raise LookupError(f"[{s.id}] {s.label}: anchor is not at the start of a statement")

        module = sys.modules[func.__module__]
        flags = 0
        if getattr(module, "annotations", None) is __future__.annotations:
            flags |= __future__.annotations.compiler_flag
        compiled = compile(tree, code.co_filename, "exec", flags=flags, dont_inherit=True)
        new_code = next(c for c in compiled.co_consts
                        if isinstance(c, types.CodeType) and c.co_name == code.co_name)
        func.__globals__[_HOOK] = _line_hook
        func.__code__ = new_code   # in place: every existing reference sees the stops


# --------------------------------------------------------------------------- driver entry

def install(steps: list[Step | LineStop]) -> None:
    crewsim_modules = [m for n, m in sys.modules.items() if n == "crewsim" or n.startswith("crewsim.")]
    for s in steps:
        if isinstance(s, Step):
            _install_wrapper(s, crewsim_modules)
    _install_lines([s for s in steps if isinstance(s, LineStop)])


def _print_table(steps: list[Step | LineStop]) -> None:
    root = str(config.repo_root())
    print("[debug] stops (* = enabled):", file=sys.stderr)
    for s in steps:
        where = s.label
        if isinstance(s, LineStop):
            where = f"{os.path.relpath(s.file, root)}:{s.line}"
        mark = "*" if _enabled(s.id) else " "
        print(f"  {mark} {s.id}  {where}", file=sys.stderr)


def run(steps: list[Step | LineStop], default_argv: list[str]) -> int:
    argv = sys.argv[1:] or default_argv
    install(steps)
    print(f"[debug] crewsim {' '.join(argv)}  | steps={_SELECTED} mode={_MODE} max={_MAX_HITS}",
          file=sys.stderr)
    if any(isinstance(s, LineStop) for s in steps):
        _print_table(steps)
    try:
        return cli.main(argv)
    finally:
        print("\n[debug] step hits:", file=sys.stderr)
        for s in steps:
            print(f"  {s.id} {s.label:34} hits={_hits[s.id]:>7}  stops={_stops[s.id]}", file=sys.stderr)
