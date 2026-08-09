#!/usr/bin/env python3
"""
Mock corpus generator — datasets D1..D12 of spec section 6.1.

WHAT THIS IS
    A deterministic, synthetic stand-in for Air Transat's operational extracts,
    so the ETL, the calibration jobs and the Phase-0 derived datasets (6.3) can
    be built and tested before any real data lands.

WHAT THIS IS NOT
    Real data, and not a forecast. Volumes, the route network and every cost are
    plausible-shaped inventions. Nothing here should be quoted as an Air Transat
    figure. See src/crewsim/data/corpus/README.md.

WHY IT IS BUILT THE WAY IT IS
    The corpus deliberately embeds:
      * seasonality      -- summer transatlantic vs winter sun (spec 4.5.2)
      * a severity regime -- correlated sick calls / delays / cancellations,
                             persistent across days (spec 5.2)
      * KNOWN ground truth for the validation targets (eligibility, cascade
        rate, true draft count) written to _ground_truth.json, so gates V3/V4
        and the 6.3 reconstructions can be scored against a known answer
      * DELIBERATE data-quality gaps, so the Phase-0 completeness gates in
        spec 6.2 are actually exercised rather than trivially passed

Run:  python tools/generate_mock_corpus.py [--out DIR] [--seed N] [--months N]

    Writes to src/crewsim/data/corpus/ by default — the corpus ships inside the
    package, next to its loaders, so a checkout runs without a generation step.
    The default mirrors configs/base.yaml -> paths.corpus_dir, which stays the
    authority for anything under src/; this script is stdlib+numpy only, so it
    recomputes the same location rather than parsing YAML.

Deps: numpy (stdlib csv/json used for output)
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import pathlib
from collections import defaultdict
from datetime import date, datetime, timedelta

import numpy as np

# ---------------------------------------------------------------------------
# 1. AIR TRANSAT SHAPE  (representative, not authoritative)
# ---------------------------------------------------------------------------

BASES = ["YUL", "YYZ", "YVR"]

# No common type rating across the A321 and A330 families, so qualification is
# hard-binding and the two are separate problem instances (spec 4.5.1).
FLEETS = ["A321neoLR", "A321-200", "A330-200", "A330-300"]
FLEET_FAMILY = {"A321neoLR": "A321", "A321-200": "A321",
                "A330-200": "A330", "A330-300": "A330"}

# Pilot establishment per (base, fleet, position). Cabin crew appear in the crew
# master for completeness but are not rostered here -- Phase 2 (spec 1.5).
PILOT_ESTABLISHMENT = {
    ("YUL", "A321neoLR", "CA"): 108, ("YUL", "A321neoLR", "FO"): 120,
    ("YUL", "A321-200",  "CA"): 34,  ("YUL", "A321-200",  "FO"): 36,
    ("YUL", "A330-200",  "CA"): 62,  ("YUL", "A330-200",  "FO"): 66,
    ("YUL", "A330-300",  "CA"): 16,  ("YUL", "A330-300",  "FO"): 18,
    ("YYZ", "A321neoLR", "CA"): 44,  ("YYZ", "A321neoLR", "FO"): 48,
    ("YYZ", "A330-200",  "CA"): 22,  ("YYZ", "A330-200",  "FO"): 24,
    ("YVR", "A321neoLR", "CA"): 17,  ("YVR", "A321neoLR", "FO"): 19,
}
CABIN_ESTABLISHMENT = {"YUL": 940, "YYZ": 330, "YVR": 115}

# Seasonal network. Summer runs transatlantic; winter runs the sun programme.
SUMMER_ATLANTIC = ["CDG", "ORY", "LYS", "MRS", "NTE", "BOD", "TLS", "BCN",
                   "MAD", "LIS", "OPO", "FCO", "VCE", "ATH", "LGW", "MAN",
                   "DUB", "BRU", "AMS", "ZRH", "BSL", "PRG", "ZAG", "TLV"]
WINTER_SUN = ["PUJ", "POP", "SDQ", "CUN", "VRA", "HAV", "MBJ", "KIN", "AUA",
              "CUR", "SJU", "SJO", "LIR", "PTY", "CTG", "CZM", "HOG", "FDF",
              "PTP", "BGI", "UVF", "ANU", "GCM", "NAS"]
DOMESTIC = ["YQB", "YHZ", "YOW", "YWG", "YYC", "YEG", "YHM"]

LONG_HAUL = set(SUMMER_ATLANTIC)          # A330 / A321neoLR territory
SHORT_HAUL = set(WINTER_SUN) | set(DOMESTIC)


def season_of(d: date) -> str:
    """Spec 4.5.2 -- three operating seasons, modelled separately."""
    if d.month in (12, 1, 2, 3, 4):
        return "winter_sun"
    if d.month in (6, 7, 8, 9):
        return "summer_atlantic"
    return "shoulder"


SEASON_DESTS = {
    "winter_sun":      (WINTER_SUN, 0.78, SUMMER_ATLANTIC, 0.14, DOMESTIC, 0.08),
    "summer_atlantic": (SUMMER_ATLANTIC, 0.80, WINTER_SUN, 0.12, DOMESTIC, 0.08),
    "shoulder":        (SUMMER_ATLANTIC, 0.45, WINTER_SUN, 0.42, DOMESTIC, 0.13),
}
# Daily departures by season -- a leisure carrier's volume swings hard.
SEASON_DEPARTURES = {"winter_sun": 62, "summer_atlantic": 74, "shoulder": 44}

# ---------------------------------------------------------------------------
# 2. SEVERITY REGIME  (spec 5.2 -- the correlation that sizes tail risk)
# ---------------------------------------------------------------------------

REGIMES = ["CALM", "NORMAL", "DISRUPTED", "SEVERE"]
# Fitted per season in the real system. The SEVERE self-transition is what
# produces bad WEEKS rather than scattered bad days.
REGIME_P = {
    "winter_sun":      [[.62, .30, .06, .02], [.18, .58, .18, .06],
                        [.05, .28, .48, .19], [.02, .14, .38, .46]],
    "summer_atlantic": [[.68, .27, .04, .01], [.22, .60, .14, .04],
                        [.06, .34, .47, .13], [.03, .22, .40, .35]],
    "shoulder":        [[.74, .22, .03, .01], [.26, .60, .11, .03],
                        [.08, .38, .43, .11], [.04, .26, .40, .30]],
}
REGIME_MULT = {"CALM": 0.5, "NORMAL": 1.0, "DISRUPTED": 2.0, "SEVERE": 3.5}

IATA_DELAY_CODES = {
    "CALM":      [("93", .4), ("15", .3), ("41", .2), ("89", .1)],
    "NORMAL":    [("93", .3), ("15", .25), ("41", .2), ("71", .15), ("89", .1)],
    "DISRUPTED": [("71", .35), ("81", .25), ("93", .15), ("41", .15), ("15", .10)],
    "SEVERE":    [("71", .45), ("75", .2), ("81", .2), ("93", .1), ("41", .05)],
}

# ---------------------------------------------------------------------------
# 3. DATA-QUALITY GAPS  (so spec 6.2's Phase-0 gates are really tested)
# ---------------------------------------------------------------------------

P_DRAFT_PAYCODE_MISSING = 0.12   # -> D6xD7 reconstruction recall approx 88%
P_D6_INITIATOR_NULL     = 0.08   # older records lack the initiator field
P_ABSENCE_UNLINKABLE    = 0.03   # -> D4 linkage approx 97% (gate is >= 95%)
P_D9_STATION_DAY_MISSING = 0.02

# Costs are placeholders. Real values are [CONFIRM: Finance] -- spec 4.4.2.
PAY_CODES = {
    "DRAFT_PREM": 500.0, "RESERVE_GTE": 250.0, "RESERVE_UTIL": 150.0,
    "OT": 95.0, "PER_DIEM": 68.0, "TRAINING": 0.0,
}


# ---------------------------------------------------------------------------
# 4. GENERATOR
# ---------------------------------------------------------------------------

class MockCorpus:
    def __init__(self, out: pathlib.Path, seed: int, months: int,
                 compress: bool = False):
        self.out = out
        self.compress = compress
        self.rng = np.random.default_rng(seed)
        self.end = date(2026, 7, 31)
        self.start = self.end - timedelta(days=int(months * 30.44))
        self.days = [(self.start + timedelta(days=i))
                     for i in range((self.end - self.start).days + 1)]
        self.seed = seed
        self.months = months
        self.truth: dict = {}

    # -- helpers -----------------------------------------------------------
    def pick(self, seq, p=None):
        return seq[int(self.rng.choice(len(seq), p=p))]

    def write(self, name: str, header: list[str], rows: list) -> None:
        # Plain CSV by default so the corpus is browsable; --compress writes
        # .csv.gz (~10:1), which Polars and pandas both read transparently.
        if self.compress:
            name += ".gz"
            fh = gzip.open(self.out / name, "wt", newline="")
        else:
            fh = (self.out / name).open("w", newline="")
        with fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows)
        size = (self.out / name).stat().st_size / 1e6
        print(f"  {name:<37} {len(rows):>8,} rows  {size:>6.1f} MB")

    # -- D9: station-day disruption labels ---------------------------------
    def gen_d9(self):
        stations = sorted(set(BASES) | set(SUMMER_ATLANTIC) | set(WINTER_SUN)
                          | set(DOMESTIC))
        rows, self.regime = [], {}
        for st in stations:
            z = 1
            for d in self.days:
                season = season_of(d)
                z = int(self.rng.choice(4, p=REGIME_P[season][z]))
                # Northern winter bites hardest at the Canadian bases.
                if st in BASES and d.month in (1, 2, 12) and self.rng.random() < .12:
                    z = min(3, z + 1)
                self.regime[(st, d)] = REGIMES[z]
                if self.rng.random() < P_D9_STATION_DAY_MISSING:
                    continue                      # deliberate gap
                rows.append([st, d.isoformat(), REGIMES[z], season,
                             round(REGIME_MULT[REGIMES[z]], 2)])
        self.write("d9_station_days.csv",
                   ["station", "date", "disruption_class", "season",
                    "intensity_multiplier"], rows)

    # -- D8: flight movements ----------------------------------------------
    def gen_d8(self):
        rows = []
        self.flights_by_day = defaultdict(list)
        fno = 100
        for d in self.days:
            season = season_of(d)
            prim, wp, sec, ws, dom, wd = SEASON_DESTS[season]
            n = int(self.rng.poisson(SEASON_DEPARTURES[season]))
            for _ in range(n):
                r = self.rng.random()
                dest = (self.pick(prim) if r < wp
                        else self.pick(sec) if r < wp + ws else self.pick(dom))
                base = self.pick(BASES, p=[.62, .27, .11])
                fleet = self._fleet_for(dest)
                fno = 100 + int(self.rng.integers(0, 800))
                dep_h = float(self.rng.uniform(5.5, 22.0))
                blk = self._block_hours(dest)
                z = self.regime.get((base, d), "NORMAL")
                lam = REGIME_MULT[z]
                delayed = self.rng.random() < min(.62, .13 * lam)
                delay = int(self.rng.gamma(2.0, 18 * lam)) if delayed else 0
                cancelled = self.rng.random() < min(.05, .0035 * lam * lam)
                code = ""
                if delay > 0 or cancelled:
                    codes, ws_ = zip(*IATA_DELAY_CODES[z])
                    code = self.pick(list(codes), p=list(ws_))
                sched = datetime.combine(d, datetime.min.time()) + timedelta(hours=dep_h)
                rows.append([
                    f"TS{fno}", d.isoformat(), base, dest, fleet,
                    sched.strftime("%Y-%m-%dT%H:%M"),
                    (sched + timedelta(hours=blk)).strftime("%Y-%m-%dT%H:%M"),
                    "" if cancelled else (sched + timedelta(minutes=delay)).strftime("%Y-%m-%dT%H:%M"),
                    "" if cancelled else (sched + timedelta(hours=blk, minutes=delay)).strftime("%Y-%m-%dT%H:%M"),
                    delay, code, int(cancelled),
                    "CREW" if cancelled and self.rng.random() < .18 else
                    ("WEATHER" if cancelled else ""),
                ])
                self.flights_by_day[d].append((base, dest, fleet, dep_h, blk))
        self.write("d8_flight_movements.csv",
                   ["flight_no", "date", "origin", "destination", "fleet",
                    "sched_dep_local", "sched_arr_local", "actual_dep_local",
                    "actual_arr_local", "delay_minutes", "iata_delay_code",
                    "cancelled", "cancel_reason"], rows)

    def _fleet_for(self, dest: str) -> str:
        if dest in LONG_HAUL:
            return self.pick(["A330-200", "A330-300", "A321neoLR"], p=[.45, .12, .43])
        return self.pick(["A321neoLR", "A321-200", "A330-200"], p=[.62, .28, .10])

    def _block_hours(self, dest: str) -> float:
        if dest in LONG_HAUL:
            return float(self.rng.uniform(6.5, 9.2))
        if dest in DOMESTIC:
            return float(self.rng.uniform(1.0, 5.0))
        return float(self.rng.uniform(3.4, 6.2))

    # -- D1: crew master ----------------------------------------------------
    def gen_d1(self):
        rows, self.pilots = [], []
        sen = 1
        # Seniority is a single company-wide ordinal (spec 6.2: rank only).
        order = sorted(PILOT_ESTABLISHMENT.items(),
                       key=lambda kv: (kv[0][2] != "CA", kv[0][1]))
        for (base, fleet, pos), n in order:
            for _ in range(n):
                cid = f"P{sen:05d}"
                hire = self.end - timedelta(days=int(self.rng.uniform(400, 11000)))
                status = "ACTIVE"
                term = ""
                r = self.rng.random()
                if r < .015:
                    status, term = "TERMINATED", (self.end - timedelta(
                        days=int(self.rng.uniform(30, 900)))).isoformat()
                elif r < .045:
                    status = "LONG_TERM_ABSENCE"        # LTD / parental / unpaid
                elif r < .06:
                    status = "INITIAL_TRAINING"         # not yet on a line
                elif r < .075:
                    status = "FLEET_TRANSITION"
                elif r < .09:
                    status = "MANAGEMENT_OR_INSTRUCTOR"  # partial availability
                rows.append([cid, base, "PILOT", pos, fleet,
                             FLEET_FAMILY[fleet],
                             (hire + timedelta(days=200)).isoformat(),
                             (self.end + timedelta(days=int(self.rng.uniform(30, 700)))).isoformat(),
                             sen, status, hire.isoformat(), term])
                if status == "ACTIVE":
                    self.pilots.append(dict(crew_id=cid, base=base, fleet=fleet,
                                            position=pos, seniority=sen))
                sen += 1
        for base, n in CABIN_ESTABLISHMENT.items():          # not rostered here
            local = {"YUL": "CUPE-4041", "YYZ": "CUPE-4047", "YVR": "CUPE-4078"}[base]
            for _ in range(n):
                cid = f"C{sen:05d}"
                hire = self.end - timedelta(days=int(self.rng.uniform(200, 9000)))
                rows.append([cid, base, f"CABIN::{local}", "FA", "ALL", "ALL",
                             "", "", sen, "ACTIVE", hire.isoformat(), ""])
                sen += 1
        self.write("d1_crew_master.csv",
                   ["crew_id", "base", "crew_group", "position", "fleet",
                    "fleet_family", "qual_valid_from", "qual_valid_to",
                    "seniority_number", "employment_status", "hire_date",
                    "termination_date"], rows)

    # -- D3: pairings + legs, and D2: rosters -------------------------------
    def gen_d3_d2(self):
        pairing_rows, leg_rows, roster_rows = [], [], []
        self.pairings = {}
        self.blocks = defaultdict(list)          # crew_id -> [(start,end,type,pid)]
        pid_n = 0

        groups = defaultdict(list)
        for p in self.pilots:
            groups[(p["base"], p["fleet"])].append(p)

        for (base, fleet), crews in groups.items():
            crews.sort(key=lambda c: c["seniority"])
            # Roughly one line in twelve is a reserve line, awarded by bid.
            n_res = max(1, round(len(crews) * 0.085))
            reserve_ids = {c["crew_id"] for c in crews[-n_res:]}   # junior end bids reserve
            for c in crews:
                d = self.start
                while d <= self.end:
                    if c["crew_id"] in reserve_ids and self.rng.random() < .55:
                        # Reserve block: 5 on / 3 off rotation, SC or LC.
                        span = int(self.rng.integers(3, 7))
                        call = "SC" if self.rng.random() < .62 else "LC"
                        self._block(roster_rows, c, d, span, "RESERVE", "", call)
                        d += timedelta(days=span + int(self.rng.integers(2, 4)))
                        continue
                    r = self.rng.random()
                    if r < .30:
                        span = int(self.rng.integers(1, 4))
                        self._block(roster_rows, c, d, span, "DAY_OFF")
                    elif r < .335:
                        span = int(self.rng.integers(7, 15))
                        self._block(roster_rows, c, d, span, "VACATION")
                    elif r < .355:
                        span = 1
                        self._block(roster_rows, c, d, span, "TRAINING")
                    elif r < .365:
                        span = 1
                        self._block(roster_rows, c, d, span, "SIMULATOR")
                    else:
                        pid_n += 1
                        pid = f"{base}{fleet[:4]}-{pid_n:06d}"
                        span = int(self.rng.integers(2, 6))
                        legs, last_release = self._make_pairing(
                            pid, base, fleet, d, span, pairing_rows, leg_rows)
                        self.pairings[pid] = dict(base=base, fleet=fleet,
                                                  start=d, days=span, legs=legs)
                        # D2's PAIRING block (day-granular) must fully contain
                        # D3's real duty-period timing (report/release, which
                        # can run past midnight of the pairing's last nominal
                        # day) -- otherwise the next block scheduled for this
                        # crew member starts before the pairing actually
                        # releases them. Pad the block's day-span (not the
                        # pairing's real duty_periods count, which stays
                        # `span`) up to whatever covers the true last release.
                        block_span = max(span, math.ceil(
                            (last_release - datetime.combine(d, datetime.min.time()))
                            .total_seconds() / 86400))
                        self._block(roster_rows, c, d, block_span, "PAIRING", pid)
                        d += timedelta(days=block_span)
                        continue
                    d += timedelta(days=span)
        self.write("d3_pairings.csv",
                   ["pairing_id", "base", "fleet", "position_complement",
                    "duty_periods", "credit_hours", "layover_stations",
                    "start_date", "days"], pairing_rows)
        self.write("d3_pairing_legs.csv",
                   ["pairing_id", "duty_period", "leg_seq", "flight_no",
                    "origin", "destination", "report_local", "dep_local",
                    "arr_local", "release_local", "block_hours"], leg_rows)
        self.write("d2_rosters.csv",
                   ["crew_id", "base", "fleet", "position", "block_type",
                    "start_utc", "end_utc", "start_local", "end_local",
                    "pairing_id", "reserve_call_type"], roster_rows)

    def _block(self, rows, c, d, span, btype, pid="", call=""):
        s = datetime.combine(d, datetime.min.time())
        e = s + timedelta(days=span)
        # UTC vs station local matters: legality runs on local (spec 6.2).
        off = {"YUL": 4, "YYZ": 4, "YVR": 7}[c["base"]]
        rows.append([c["crew_id"], c["base"], c["fleet"], c["position"], btype,
                     (s + timedelta(hours=off)).strftime("%Y-%m-%dT%H:%M"),
                     (e + timedelta(hours=off)).strftime("%Y-%m-%dT%H:%M"),
                     s.strftime("%Y-%m-%dT%H:%M"), e.strftime("%Y-%m-%dT%H:%M"),
                     pid, call])
        self.blocks[c["crew_id"]].append((d, d + timedelta(days=span), btype, pid))

    def _make_pairing(self, pid, base, fleet, d0, days, prows, lrows):
        season = season_of(d0)
        prim, wp, sec, ws, dom, _ = SEASON_DESTS[season]
        legs, layovers, credit = [], [], 0.0
        last_release = datetime.combine(d0, datetime.min.time())
        for dp in range(days):
            r = self.rng.random()
            dest = (self.pick(prim) if r < wp
                    else self.pick(sec) if r < wp + ws else self.pick(dom))
            rep = float(self.rng.uniform(5.0, 18.0))
            # An overnight duty (previous dp) can release after this day's
            # start; report can't precede that. Reuses the same 0.5h buffer
            # already used below for release (dep+block+0.5), rather than
            # inventing a new rest constant.
            day_start = datetime.combine(d0, datetime.min.time()) + timedelta(days=dp)
            if last_release > day_start:
                rep = max(rep, (last_release - day_start).total_seconds() / 3600.0 + 0.5)
            blk = self._block_hours(dest)
            n_legs = 1 if dest in LONG_HAUL else int(self.rng.integers(1, 3))
            t = rep + 1.0
            for k in range(n_legs):
                o = base if (dp == 0 and k == 0) else (dest if k else base)
                lrows.append([pid, dp + 1, k + 1,
                              f"TS{int(self.rng.integers(100, 900))}",
                              o, dest,
                              self._hm(d0, dp, rep), self._hm(d0, dp, t),
                              self._hm(d0, dp, t + blk),
                              self._hm(d0, dp, t + blk + 0.5), round(blk, 2)])
                credit += blk
                last_release = (datetime.combine(d0, datetime.min.time())
                                 + timedelta(days=dp, hours=t + blk + 0.5))
                t += blk + 1.2
            legs.append(dest)
            if dp < days - 1:
                layovers.append(dest)
        comp = "CA:1,FO:1,FA:5" if FLEET_FAMILY[fleet] == "A321" else "CA:1,FO:2,FA:8"
        prows.append([pid, base, fleet, comp, days, round(credit * 1.18, 2),
                      "|".join(layovers), d0.isoformat(), days])
        return legs, last_release

    @staticmethod
    def _hm(d0, dayoff, hours):
        return (datetime.combine(d0, datetime.min.time())
                + timedelta(days=dayoff, hours=hours)).strftime("%Y-%m-%dT%H:%M")

    # -- D4/D5/D6/D7/D10: disruption and its recovery -----------------------
    def gen_events(self):
        d4, d5, d6, d7, d10 = [], [], [], [], []
        by_crew = {p["crew_id"]: p for p in self.pilots}
        idx = defaultdict(list)                 # (crew) -> blocks, for lookup
        for cid, bl in self.blocks.items():
            idx[cid] = sorted(bl)

        reserve_pool = defaultdict(list)        # (base,fleet,date) -> [crew_id]
        for cid, bl in self.blocks.items():
            for s, e, t, _ in bl:
                if t == "RESERVE":
                    p = by_crew.get(cid)
                    if not p:
                        continue
                    dd = s
                    while dd < e:
                        reserve_pool[(p["base"], p["fleet"], dd)].append(cid)
                        dd += timedelta(days=1)

        n_abs = n_draft = n_cascade = 0
        elig_samples: list[float] = []
        abs_id = call_id = chg_id = 0

        for cid, bl in idx.items():
            p = by_crew.get(cid)
            if not p:
                continue
            for (s, e, t, pid) in bl:
                if t not in ("PAIRING", "RESERVE"):
                    continue
                z = self.regime.get((p["base"], s), "NORMAL")
                # Sick-call hazard per crew-day, modulated by the regime and
                # inflated in the northern winter (spec 5.2 covariates).
                lam = 0.0125 * REGIME_MULT[z] * (1.25 if s.month in (1, 2, 12) else 1.0)
                if self.rng.random() > 1 - math.exp(-lam * (e - s).days):
                    continue
                n_abs += 1
                abs_id += 1
                notif = datetime.combine(s, datetime.min.time()) - timedelta(
                    hours=float(self.rng.uniform(2, 26)))
                dur = max(1, int(self.rng.lognormal(0.55, 0.75)))
                linkable = self.rng.random() > P_ABSENCE_UNLINKABLE
                d4.append([f"A{abs_id:06d}", cid, notif.strftime("%Y-%m-%dT%H:%M"),
                           s.isoformat(), (s + timedelta(days=dur)).isoformat(),
                           dur, self.pick(["SICK", "SICK", "SICK", "FAMILY", "INJURY"]),
                           pid if linkable else "", p["base"], p["fleet"],
                           p["position"]])
                if t != "PAIRING" or not pid:
                    continue

                # --- recovery: reserve first, then draft, then cancel -------
                pool = reserve_pool.get((p["base"], p["fleet"], s), [])
                # Eligibility is emergent in the model; here it is generated
                # with a known rate so V3 has a ground truth to score against.
                elig = [r for r in pool if self.rng.random() < 0.30]
                if pool:
                    elig_samples.append(len(elig) / len(pool))
                if elig:
                    r = elig[0]
                    call_id += 1
                    outcome = ("no-show" if self.rng.random() < .04
                               else "released" if self.rng.random() < .07 else "assigned")
                    d5.append([f"R{call_id:06d}", r,
                               (notif + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M"),
                               (notif + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M"),
                               pid, outcome, p["base"], p["fleet"]])
                    if outcome == "assigned":
                        d7.append([r, s.strftime("%Y-%m"), "RESERVE_UTIL",
                                   PAY_CODES["RESERVE_UTIL"], s.isoformat(), pid])
                        continue

                # Draft: impact tier first, SENIOR first within tier.
                cands = self._draft_candidates(by_crew, idx, p, s)
                if not cands:
                    continue
                tier, victim = cands[0]
                n_draft += 1
                chg_id += 1
                init = "" if self.rng.random() < P_D6_INITIATOR_NULL else "IOC"
                d6.append([f"S{chg_id:06d}", victim,
                           (notif + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
                           {1: "DAY_OFF", 2: "PAIRING", 3: "TRAINING",
                            4: "VACATION", 5: "SIMULATOR"}[tier],
                           "PAIRING", pid, "SHORT_NOTICE_COVER", init])
                if self.rng.random() > P_DRAFT_PAYCODE_MISSING:
                    d7.append([victim, s.strftime("%Y-%m"), "DRAFT_PREM",
                               PAY_CODES["DRAFT_PREM"], s.isoformat(), pid])
                if self.rng.random() < .28:            # positioning was needed
                    st = self.pick(list(WINTER_SUN) + list(SUMMER_ATLANTIC))
                    d10.append([s.isoformat(), st,
                                self.pick(["HOTEL", "DEADHEAD", "TRANSPORT"]),
                                round(float(self.rng.uniform(120, 640)), 2),
                                victim, pid])
                # Cascade: the draft breaks something downstream (target ~20%).
                if self.rng.random() < 0.20:
                    n_cascade += 1
                    chg_id += 1
                    fd = s + timedelta(days=int(self.rng.integers(1, 8)))
                    d6.append([f"S{chg_id:06d}", victim,
                               (datetime.combine(fd, datetime.min.time())
                                ).strftime("%Y-%m-%dT%H:%M"),
                               "PAIRING", "OPEN", "", "CASCADE_UNCOVERED",
                               "" if self.rng.random() < P_D6_INITIATOR_NULL else "IOC"])

        # reserve guarantee accrues per reserve-day, whether used or not
        for (base, fleet, dd), crews in reserve_pool.items():
            if dd.day == 1:
                for c in crews:
                    d7.append([c, dd.strftime("%Y-%m"), "RESERVE_GTE",
                               PAY_CODES["RESERVE_GTE"] * 20, dd.isoformat(), ""])

        self.write("d4_absences.csv",
                   ["absence_id", "crew_id", "notification_ts", "absence_start",
                    "absence_end", "duration_days", "absence_type",
                    "affected_pairing_id", "base", "fleet", "position"], d4)
        self.write("d5_reserve_callouts.csv",
                   ["callout_id", "crew_id", "call_ts", "report_ts",
                    "assigned_pairing_id", "outcome", "base", "fleet"], d5)
        self.write("d6_schedule_changes.csv",
                   ["change_id", "crew_id", "change_ts", "old_block_type",
                    "new_block_type", "new_pairing_id", "reason_code",
                    "initiator"], d6)
        self.write("d7_pay_register.csv",
                   ["crew_id", "pay_period", "pay_code", "amount_cad",
                    "duty_date", "linked_pairing_id"], d7)
        self.write("d10_positioning_invoices.csv",
                   ["date", "station", "cost_type", "amount_cad", "crew_id",
                    "pairing_id"], d10)

        self.truth.update(
            absences=n_abs, drafts_true=n_draft, cascades_true=n_cascade,
            cascade_rate_true=round(n_cascade / n_draft, 4) if n_draft else 0.0,
            eligibility_rate_true=round(float(np.mean(elig_samples)), 4)
            if elig_samples else None,
            draft_paycode_missing_rate=P_DRAFT_PAYCODE_MISSING,
            expected_reconstruction_recall=round(1 - P_DRAFT_PAYCODE_MISSING, 4),
        )

    def _draft_candidates(self, by_crew, idx, p, day):
        """Tier first, then SENIOR first within tier (spec 5.6). No cap, no
        protected blocks -- neither exists at Air Transat."""
        tiers = {"DAY_OFF": 1, "PAIRING": 2, "TRAINING": 3,
                 "VACATION": 4, "SIMULATOR": 5}
        found = []
        for cid, bl in idx.items():
            q = by_crew.get(cid)
            if not q or q["base"] != p["base"] or q["fleet"] != p["fleet"] \
                    or q["position"] != p["position"] or cid == p["crew_id"]:
                continue
            for (s, e, t, _) in bl:
                if s <= day < e and t in tiers:
                    found.append((tiers[t], q["seniority"], cid))
                    break
            if len(found) > 400:
                break
        found.sort()                        # tier asc, then seniority asc
        return [(t, c) for t, _, c in found[:1]]

    # -- D11 / D12 ----------------------------------------------------------
    def gen_d11_d12(self):
        rows = []
        for cid, bl in self.blocks.items():
            for (s, e, t, _) in bl:
                if t in ("TRAINING", "SIMULATOR"):
                    rows.append([cid, "SIM" if t == "SIMULATOR" else "GROUND",
                                 s.isoformat(), e.isoformat(),
                                 (e + timedelta(days=int(self.rng.uniform(30, 200)))).isoformat(),
                                 round(float(self.rng.uniform(900, 2600)), 2)])
        self.write("d11_training_sessions.csv",
                   ["crew_id", "session_type", "start_date", "end_date",
                    "requalification_deadline", "reschedule_cost_cad_estimate"],
                   rows)
        (self.out / "d12_agreement_rules.yaml").write_text(
            "# D12 — collective agreement cost rules (document, not data).\n"
            "# MOCK. Every value is [CONFIRM: Labour Relations + Finance].\n"
            "# Confirmed facts (business, 2026-08-05) are marked CONFIRMED.\n"
            "pilots:\n"
            "  agreement: ALPA\n"
            "  term: 2025-05-01..2030-04-30\n"
            "  drafting:\n"
            "    order: tier_then_senior_first     # CONFIRMED\n"
            "    protected_blocks: none            # CONFIRMED — no such concept\n"
            "    max_drafts_per_crew_month: null   # CONFIRMED — no cap exists\n"
            "    premium_pct: 200                  # [CONFIRM: Finance]\n"
            "  reserve:\n"
            "    guarantee_per_day_cad: {short_call: 250, long_call: 180}\n"
            "    notice_hours:          {short_call: 2,   long_call: 12}\n"
            "cabin_crew:\n"
            "  agreement: CUPE\n"
            "  locals: {YUL: 4041, YYZ: 4047, YVR: 4078}\n"
            "  note: Phase 2 — do not reuse pilot coefficients.\n")
        print(f"  {'d12_agreement_rules.yaml':<34}   (document)")

    # -- ground truth -------------------------------------------------------
    def gen_truth(self):
        self.truth.update(
            generator_seed=self.seed, months=self.months,
            window=[self.start.isoformat(), self.end.isoformat()],
            fitting_window=[self.start.isoformat(), "2025-07-31"],
            holdout_window=["2025-08-01", self.end.isoformat()],
            deliberate_gaps=dict(
                draft_paycode_missing=P_DRAFT_PAYCODE_MISSING,
                d6_initiator_null=P_D6_INITIATOR_NULL,
                absence_unlinkable=P_ABSENCE_UNLINKABLE,
                d9_station_day_missing=P_D9_STATION_DAY_MISSING),
            note=("Ground truth for scoring the spec 6.3 reconstructions and "
                  "gates V3/V4. Real data has no such file — that is the "
                  "point of the mock corpus."),
        )
        (self.out / "_ground_truth.json").write_text(
            json.dumps(self.truth, indent=2) + "\n")
        print(f"  {'_ground_truth.json':<34}   {self.truth}")

    def run(self):
        self.out.mkdir(parents=True, exist_ok=True)
        print(f"Generating mock corpus -> {self.out}")
        print(f"  window {self.start} .. {self.end}  seed={self.seed}\n")
        self.gen_d9()
        self.gen_d8()
        self.gen_d1()
        self.gen_d3_d2()
        self.gen_events()
        self.gen_d11_d12()
        self.gen_truth()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    _default_out = (
        pathlib.Path(__file__).resolve().parents[1] / "src" / "crewsim" / "data" / "corpus"
    )
    ap.add_argument("--out", default=str(_default_out))
    ap.add_argument("--seed", type=int, default=20260805)
    ap.add_argument("--months", type=int, default=36)
    ap.add_argument("--compress", action="store_true",
                    help="write .csv.gz instead of .csv (~10x smaller)")
    a = ap.parse_args()
    MockCorpus(pathlib.Path(a.out), a.seed, a.months, a.compress).run()
