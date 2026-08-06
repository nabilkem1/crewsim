#!/usr/bin/env python3
"""
Backlog verification runner.

Two gates per story (see backlog/README.md):
  * automated  -- what Claude runs; must be deterministic and exit non-zero on failure
  * manual     -- what YOU run; one command, one screen, <= 60 seconds, with a stated
                  expected value and a stated failure mode

Usage
  python backlog/verify.py --status            board: counts by phase and status
  python backlog/verify.py --phase 1a          run every automated check in a slice
  python backlog/verify.py S1a-04              one story: run auto, print the manual recipe
  python backlog/verify.py --manual 1a         manual checklist only, to work through
  python backlog/verify.py --next              what is unblocked and ready to start
  python backlog/verify.py --graph             dependency order

Deps: pyyaml (falls back to a message if absent)
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent
STORIES = ROOT / "stories.yaml"

C = dict(g="\033[32m", r="\033[31m", y="\033[33m", b="\033[34m",
         d="\033[2m", B="\033[1m", x="\033[0m")
STATUS_ICON = {"done": "✅", "in_progress": "🔨", "todo": "  ", "blocked": "⛔"}


def load():
    try:
        import yaml
    except ImportError:
        sys.exit("pyyaml is required:  pip install pyyaml")
    doc = yaml.safe_load(STORIES.read_text())
    return doc, {s["id"]: s for s in doc["stories"]}


def runnable(cmd: str) -> bool:
    """Is the first token of the command actually on PATH / present?"""
    head = cmd.strip().split()[0]
    if head in ("python", "python3", "pytest", "for", "ruff", "mypy"):
        return True
    return shutil.which(head) is not None


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(cmd, shell=True, cwd=REPO, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)


# --------------------------------------------------------------------------- views
def show_status(doc, by_id):
    print(f"\n{C['B']}Backlog — {doc['meta']['project']}{C['x']}  "
          f"{C['d']}(spec {doc['meta']['spec']}){C['x']}\n")
    per_phase = defaultdict(Counter)
    for s in doc["stories"]:
        per_phase[s["phase"]][s["status"]] += 1
    print(f"  {'phase':<5} {'name':<34} {'done':>5} {'wip':>4} {'todo':>5} "
          f"{'blk':>4}   gate")
    print(f"  {'-'*5} {'-'*34} {'-'*5} {'-'*4} {'-'*5} {'-'*4}   {'-'*40}")
    for ph, meta in doc["phases"].items():
        c = per_phase[ph]
        tot = sum(c.values())
        bar = "done" if c["done"] == tot and tot else ""
        col = C["g"] if bar else ""
        print(f"  {col}{ph:<5} {meta['name'][:34]:<34} {c['done']:>5} "
              f"{c['in_progress']:>4} {c['todo']:>5} {c['blocked']:>4}{C['x']}   "
              f"{C['d']}{meta['gate']}{C['x']}")
    tot = Counter(s["status"] for s in doc["stories"])
    print(f"\n  total {sum(tot.values())} stories — "
          f"{tot['done']} done, {tot['in_progress']} in progress, "
          f"{tot['todo']} todo, {tot['blocked']} blocked")
    crit = [s for s in doc["stories"] if s.get("critical_path")]
    if crit:
        print(f"\n  {C['y']}⚠ critical path:{C['x']} " +
              ", ".join(f"{s['id']} {s['title']}" for s in crit))
    print()


def show_next(doc, by_id):
    done = {s["id"] for s in doc["stories"] if s["status"] == "done"}
    ready = [s for s in doc["stories"]
             if s["status"] == "todo"
             and all(d in done for d in s.get("depends_on", []))]
    print(f"\n{C['B']}Ready to start{C['x']} — all dependencies satisfied\n")
    if not ready:
        print("  nothing unblocked\n")
        return
    for s in ready:
        star = f" {C['y']}★ CRITICAL PATH{C['x']}" if s.get("critical_path") else ""
        print(f"  {C['b']}{s['id']:<8}{C['x']} [{s['size']}] {s['title']}{star}")
        print(f"           {C['d']}phase {s['phase']} · {s['epic']} · "
              f"spec §{', §'.join(s.get('spec', []))}{C['x']}")
    print()


def show_manual(doc, phase):
    rows = [s for s in doc["stories"] if s["phase"] == phase]
    print(f"\n{C['B']}Manual checklist — phase {phase}{C['x']}"
          f"  {C['d']}({len(rows)} stories, ~{len(rows)} minutes){C['x']}\n")
    for s in rows:
        ch = s.get("check", {})
        print(f"{STATUS_ICON[s['status']]} {C['b']}{s['id']}{C['x']} {s['title']}")
        print(f"     {C['d']}$ {ch.get('manual','TBD')}{C['x']}")
        print(f"     expect   {ch.get('expect','TBD')}")
        print(f"     {C['r']}fails if{C['x']} {ch.get('fails_if','TBD')}\n")


def show_graph(doc):
    done = {s["id"] for s in doc["stories"] if s["status"] == "done"}
    print(f"\n{C['B']}Dependency order{C['x']}\n")
    for s in doc["stories"]:
        deps = s.get("depends_on", [])
        mark = "".join("✓" if d in done else "·" for d in deps) or "—"
        print(f"  {STATUS_ICON[s['status']]} {s['id']:<8} {mark:<6} "
              f"{s['title'][:52]:<52} {C['d']}{'<- ' + ', '.join(deps) if deps else ''}{C['x']}")
    print()


def check_story(s, execute=True) -> bool:
    ch = s.get("check", {})
    auto, manual = ch.get("auto", "TBD"), ch.get("manual", "TBD")
    print(f"\n{C['B']}{s['id']} — {s['title']}{C['x']}")
    print(f"  {C['d']}{s['epic']} · phase {s['phase']} · size {s['size']} · "
          f"spec §{', §'.join(s.get('spec', []))}"
          f"{' · fixes ' + s['fixes'] if s.get('fixes') else ''}"
          f"{' · gate ' + s['gate'] if s.get('gate') else ''}{C['x']}")
    if s["status"] == "blocked":
        print(f"  {C['r']}⛔ BLOCKED{C['x']} — {s.get('blocked_by','')}")
        return False

    ok = True
    print(f"\n  🤖 {C['B']}Claude verifies{C['x']}")
    if auto == "TBD":
        print(f"     {C['d']}not defined yet (refine when: "
              f"{s.get('refine_when','TBD')}){C['x']}")
    elif not execute:
        print(f"     $ {auto}")
    elif not runnable(auto):
        print(f"     $ {auto}\n     {C['y']}NOT IMPLEMENTED{C['x']} — "
              f"command not available yet")
    else:
        code, out = run(auto)
        tail = "\n".join(out.strip().splitlines()[-4:])
        # A story that has not been built yet is NOT IMPLEMENTED, not FAILED.
        # Only real assertion failures should show red, or --phase becomes noise.
        missing = (code == 4 or "file or directory not found" in out
                   or "no tests ran" in out or "ModuleNotFoundError" in out
                   or "No such file" in out)
        if code == 0:
            print(f"     $ {auto}\n     {C['g']}PASS{C['x']}")
        elif missing:
            print(f"     $ {auto}\n     {C['y']}NOT IMPLEMENTED{C['x']} — "
                  f"nothing to run yet")
        else:
            ok = False
            print(f"     $ {auto}\n     {C['r']}FAIL{C['x']} (exit {code})")
            if tail:
                print("     " + tail.replace("\n", "\n     "))

    print(f"\n  🙋 {C['B']}You verify{C['x']}  {C['d']}(≤60s){C['x']}")
    print(f"     $ {manual}")
    print(f"     expect   {ch.get('expect','TBD')}")
    print(f"     {C['r']}fails if{C['x']} {ch.get('fails_if','TBD')}")
    if s.get("note"):
        print(f"     {C['d']}note: {s['note']}{C['x']}")
    return ok


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("story", nargs="?", help="story id, e.g. S1a-04")
    ap.add_argument("--phase", help="run every automated check in a phase")
    ap.add_argument("--manual", help="print the manual checklist for a phase")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--next", action="store_true", dest="next_")
    ap.add_argument("--graph", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="print commands without running them")
    a = ap.parse_args()

    doc, by_id = load()
    if a.status:
        return show_status(doc, by_id)
    if a.next_:
        return show_next(doc, by_id)
    if a.graph:
        return show_graph(doc)
    if a.manual:
        return show_manual(doc, a.manual)
    if a.phase:
        rows = [s for s in doc["stories"] if s["phase"] == a.phase]
        if not rows:
            sys.exit(f"no stories in phase {a.phase}")
        results = [check_story(s, execute=not a.dry_run) for s in rows]
        print(f"\n{C['B']}phase {a.phase}: "
              f"{sum(results)}/{len(results)} automated checks passing{C['x']}\n")
        return
    if a.story:
        s = by_id.get(a.story)
        if not s:
            sys.exit(f"unknown story {a.story}")
        check_story(s, execute=not a.dry_run)
        print()
        return
    show_status(doc, by_id)


if __name__ == "__main__":
    main()
