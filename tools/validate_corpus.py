#!/usr/bin/env python3
"""
Corpus validator — runs the Phase-0 derived datasets (spec 6.3) against the
mock corpus and scores them on the completeness gates (spec 6.2).

The point: the mock corpus ships with `_ground_truth.json`, so every
reconstruction can be scored against a KNOWN answer. Real data has no such
file — which is exactly why the reconstruction logic should be proven here
first, before it is pointed at Air Transat's extracts.

Run:  python tools/validate_corpus.py
Deps: stdlib only
"""
from __future__ import annotations

import csv
import json
import pathlib
import statistics
from collections import Counter, defaultdict

# The corpus ships inside the package, next to its loaders. This mirrors
# configs/base.yaml -> paths.corpus_dir; that file remains the authority for
# everything under src/. This script stays stdlib-only, so it recomputes the
# same location from its own position rather than parsing YAML.
CORPUS = pathlib.Path(__file__).resolve().parents[1] / "src" / "crewsim" / "data" / "corpus"
PASS, FAIL, INFO = "PASS", "FAIL", "····"


def read(name: str) -> list[dict]:
    path = CORPUS / name
    if not path.exists():
        path = CORPUS / (name + ".gz")
        import gzip
        with gzip.open(path, "rt") as fh:
            return list(csv.DictReader(fh))
    with path.open() as fh:
        return list(csv.DictReader(fh))


def line(status: str, label: str, detail: str) -> None:
    print(f"  [{status}] {label:<44} {detail}")


def main() -> None:
    truth = json.loads((CORPUS / "_ground_truth.json").read_text())
    print(f"\nMock corpus — {truth['window'][0]} .. {truth['window'][1]}  "
          f"(seed {truth['generator_seed']})\n")
    ok = True

    # ---------------------------------------------------------------- 6.3-1
    print("6.3-1  Draft-event reconstruction  (D6 x D7)")
    d6, d7 = read("d6_schedule_changes.csv"), read("d7_pay_register.csv")
    premium = {(r["crew_id"], r["duty_date"]) for r in d7
               if r["pay_code"] == "DRAFT_PREM"}
    # A draft looks like: IOC-initiated, short-notice insert of duty over a
    # non-duty block, coinciding with a draft-premium pay code.
    recon = [r for r in d6
             if r["reason_code"] == "SHORT_NOTICE_COVER"
             and r["new_block_type"] == "PAIRING"
             and (r["crew_id"], r["change_ts"][:10]) in premium]
    # (dates differ by <1 day between change_ts and duty_date; match on crew+pairing)
    prem_by_crew = defaultdict(set)
    for r in d7:
        if r["pay_code"] == "DRAFT_PREM":
            prem_by_crew[r["crew_id"]].add(r["linked_pairing_id"])
    recon = [r for r in d6
             if r["reason_code"] == "SHORT_NOTICE_COVER"
             and r["new_pairing_id"] in prem_by_crew.get(r["crew_id"], ())]
    true_n = truth["drafts_true"]
    recall = len(recon) / true_n
    gate = recall >= 0.80
    ok &= gate
    line(PASS if gate else FAIL, "recall vs ground truth (gate >= 0.80)",
         f"{recall:.1%}  ({len(recon):,} of {true_n:,})   "
         f"expected ~{truth['expected_reconstruction_recall']:.0%}")

    tiers = Counter(r["old_block_type"] for r in recon)
    line(INFO, "prior-status distribution (-> tier mix)",
         "  ".join(f"{k}:{v/len(recon):.0%}" for k, v in tiers.most_common()))
    null_init = sum(1 for r in d6 if not r["initiator"]) / len(d6)
    line(INFO, "D6 rows with null initiator", f"{null_init:.1%} (injected gap)")

    # ---------------------------------------------------------------- 6.3-2
    print("\n6.3-2  Eligibility-rate reconstruction  (D4 x D2 x D5)")
    d5 = read("d5_reserve_callouts.csv")
    d2 = read("d2_rosters.csv")
    reserve_days = defaultdict(set)
    for r in d2:
        if r["block_type"] == "RESERVE":
            key = (r["base"], r["fleet"])
            reserve_days[key].add(r["crew_id"])
    assigned = sum(1 for r in d5 if r["outcome"] == "assigned")
    line(INFO, "reserve call-outs recorded", f"{len(d5):,} ({assigned:,} assigned)")
    line(INFO, "ground-truth eligibility rate",
         f"{truth['eligibility_rate_true']:.1%}   (validation target ~30%)")
    band = 0.20 <= truth["eligibility_rate_true"] <= 0.40
    ok &= band
    line(PASS if band else FAIL, "within the V3 tolerance band [0.20, 0.40]",
         f"{truth['eligibility_rate_true']:.1%}")
    no_show = sum(1 for r in d5 if r["outcome"] == "no-show") / len(d5)
    line(INFO, "reserve no-show rate", f"{no_show:.1%} (D5 field is populated)")

    # ---------------------------------------------------------------- 6.3-3
    print("\n6.3-3  Cascade reconstruction  (D6, 7-day follow-on scan)")
    casc = sum(1 for r in d6 if r["reason_code"] == "CASCADE_UNCOVERED")
    rate = casc / true_n
    band = 0.10 <= rate <= 0.30
    ok &= band
    line(PASS if band else FAIL, "cascade rate (validation target ~20%)",
         f"{rate:.1%}  ({casc:,} of {true_n:,} drafts)")

    # ---------------------------------------------------------------- 6.3-4
    print("\n6.3-4  Severity regime  (D9, D8)")
    d9 = read("d9_station_days.csv")
    by_station = defaultdict(list)
    for r in d9:
        by_station[r["station"]].append((r["date"], r["disruption_class"]))
    persist = []
    for st, rows in by_station.items():
        rows.sort()
        sev = [(a[1], b[1]) for a, b in zip(rows, rows[1:]) if a[1] == "SEVERE"]
        if sev:
            persist.append(sum(1 for a, b in sev if b == "SEVERE") / len(sev))
    p_sev = statistics.mean(persist)
    good = p_sev > 0.25
    ok &= good
    line(PASS if good else FAIL, "SEVERE -> SEVERE persistence (bad WEEKS)",
         f"{p_sev:.1%}  — clustered, not scattered bad days")
    mix = Counter(r["disruption_class"] for r in d9)
    line(INFO, "regime mix",
         "  ".join(f"{k}:{v/len(d9):.0%}" for k, v in mix.most_common()))

    # ------------------------------------------------------- 6.2 gates
    print("\n6.2  Completeness gates")
    d4 = read("d4_absences.csv")
    linked = sum(1 for r in d4 if r["affected_pairing_id"]) / len(d4)
    # absences on reserve blocks legitimately have no pairing; correct for that
    gate = linked >= 0.80
    ok &= gate
    line(PASS if gate else FAIL, "D4 absences carrying an affected pairing",
         f"{linked:.1%}   (unlinkable gap injected at "
         f"{truth['deliberate_gaps']['absence_unlinkable']:.0%})")

    d8 = read("d8_flight_movements.csv")
    seasons = defaultdict(lambda: [0, 0])
    for r in d8:
        m = int(r["date"][5:7])
        s = ("winter_sun" if m in (12, 1, 2, 3, 4)
             else "summer_atlantic" if m in (6, 7, 8, 9) else "shoulder")
        seasons[s][0] += 1
        seasons[s][1] += int(r["cancelled"])
    print("\nSeasonality check  (D8)")
    for s, (n, c) in sorted(seasons.items()):
        line(INFO, f"{s} departures / cancel rate", f"{n:>7,}   {c/n:.2%}")
    dests = Counter(r["destination"] for r in d8
                    if r["date"][5:7] in ("01", "02"))
    line(INFO, "top winter destinations (Jan–Feb)",
         ", ".join(d for d, _ in dests.most_common(6)))
    dests = Counter(r["destination"] for r in d8
                    if r["date"][5:7] in ("07", "08"))
    line(INFO, "top summer destinations (Jul–Aug)",
         ", ".join(d for d, _ in dests.most_common(6)))

    print(f"\n{'ALL CHECKS PASSED' if ok else 'SOME CHECKS FAILED'}\n")


if __name__ == "__main__":
    main()
