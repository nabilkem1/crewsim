# Brief: can CrewSim's corpus (D1..D12) be read directly from AIMS (TSC database)?

## Context
CrewSim (C:\dev\crewsim) is a crew reserve/drafting simulator for Air Transat. It is calibrated and validated from a "corpus" of 12 datasets (CSV files, schema = DATASET_SCHEMAS in
C:\dev\crewsim\src\crewsim\data\loaders.py lines 73-215 + OPTIONAL_COLUMNS; business dictionary C:\dev\crewsim\spec_sections\data_schema\data_dictionary.md; spec section 6:
C:\dev\crewsim\spec_sections\6_Detailed_Data_Requirements.md; real-extract config C:\dev\crewsim\configs\real.yaml and base.yaml (see `data:` section)).
Today the corpus is delivered by an Air Transat contact ("Pierre") as extracts (real files: C:\dev\crewsim\src\crewsim\data\corpus\real_datav2\v3\*.csv; his notes and CrewSim's open
problems: C:\dev\crewsim\Pierre3.md, pierre2.md, PierreEmail.md, backlog\verify\pierre2_export_drafts_aims.md, backlog\verify\pierre_analyse_donnees_reelles.md,
backlog\improvements\findings2\finding_after_pierre_dtata.md). Rules in the real corpus: crew_id is an opaque surrogate (P######), no personal data columns (banned columns list in loaders.py),
pairing_id = AIMS pairing code + start date (e.g. C0001_20260501), *_local times of D3/D8 are airport-local recomputed from UTC with DST, D2 *_local is base-local, all dates/times UTC otherwise.
QUESTION TO ANSWER: for each dataset assigned to you - is it possible to produce it DIRECTLY from the AIMS database TSC (and CrewSchedAI procs) with SQL, column by column,
what is derivable, what is only approximated, what is missing/unavailable, and what the history depth is.

## Evidence already available (READ FIRST)
The semantic layer built so far: C:\dev\crewsim\docs\aims_semantic\README.md, drafts.md and tables\*.md (ROSTER, ROSTERDT, ROSTERID, CRCODES, CRROUTE, CREWLEG, CRLEGGROUND, LEGMAIN, LEGTIMES,
HOTAC, HOTEL, vvCREWDB, CREWQUAL, CREWCATEG, CREWCAT, EXPI, vvCREXPREC, vvPositions, vvAirports, vvZONEIDX, vvCarriers, AIRCTYPE, vvAIRCTYPE, GENCAT, TABLES, vvFMSCodes, vvFMSInfo1, SPEFREC*, fn_*...).
Key encodings: AIMS dates = day number since 1980-01-01 (2026-11-03 = 17108); times = UTC minutes after 00:00 of the row's day column; ROSTER key (ID, LEG_DAY, LEG_DEP, LEG_CARRIER, LEG_FLT, LEG_LEGCD, DUTYNO, DUTYDAY, GRDDUTYBEG);
pairing instance (CDATE=DUTYDAY, CROUTE=DUTYNO), name CRROUTE.DESC_; flight key (DAY, DEP, CARRIER, FLT, LEGCD); activities = CRCODES via -LEG_FLT; drafts = ROSTERDT RECTYPE 21 VALUE1 15/16/19/20.
NEW objects found in the TSC catalog that are NOT yet documented and look essential (history / change logs / published rosters / pay): LOG_ROSTER (12M), LOG_ROSTERDT (17.5M), PROSTER (3.4M), PROSTERDT (5.4M), PROSTERID,
PUBLCROU, PUBLLEGS, PUBLVER, HISTCROU, HISTLEGS, HISTVER, ORGCROU, CRWCHNGS (1.3M), MSTLOGCRW (260M!), MSTLOGLEAVE, MSTLOGMISC, MSTLOGTRN, LOG (3M), LOG_CRROUTE, LOG_CREWLEG, LOG_LEGMAIN, LOG_LEGTIMES,
LOG_LEGDELAYS, LEGDELAYS (768k), DLYCD, DLYCAT, LEGTRDELAYS, CNGRSN, TIMEPNCPNT (355k, timesheet PNC/PNT), TSCPAYID, ALLWRDC, TRIPSWAP, TRIPIDX, MCREW3, Crewmsg (7M), CRWCMPL, LEAVE, LEAVEDESC, DEADHEAD (204k),
CREWBASES, CREWPOS, COMPLEMENT, CREXPREC (145k; the view vvCREXPREC), CREXPLOG (1.8 BILLION rows - never scan), IRREGROSTER, IRREGALERT, ALERTCRW, DutyReq, TRN* (TRNBOOKING, TRNSESS2, TRNCOURSE..., TRNMEMBS2, TRNFAILURE),
TSCBIDS, UNCREWED_ROUTES, SLOTS, PUBLCROU... Use sys.columns to inspect any table (read-only). A full table list with row counts is in C:\dev\crewsim\docs\aims_semantic\_raw\all_tables.txt.
You must discover the meaning of the new objects yourself from column names, data profiling and any hints in the repo SQL / CrewSim docs. Label inference as inference.

## Tools / rules
* Read-only SQL via: pwsh -NoProfile -File C:\dev\crewsim\docs\aims_semantic\_raw\q.ps1 -Database TSC -Sql "SELECT ..." [-Max 60]   (SELECT/WITH only, 60 s timeout, READ UNCOMMITTED).
  The server is a PRODUCTION AIMS database: always TOP / narrow date or ID filters / aggregates on indexed columns (check sys.indexes first for big tables); MSTLOGCRW (260M), CREXPLOG (1.8B), LOG_LEGPAX (14M), MSGQ (19M), WEBLOGNG (38M) must only be touched with an indexed, narrow predicate.
  <= ~40 queries per dataset.
* PRIVACY (strict): never write names, birth dates, addresses, contacts, passport/employee numbers, free-text messages or any individual's values. Aggregates and code/lookup values only. Free-text memo/message columns: do not read content, only describe/count.
* Do not modify the databases or any repo source file. Write only into C:\dev\crewsim\docs\aims_semantic\corpus\.

## Required output (one markdown file per assigned group, path given in your task)
For EACH dataset (and each OPTIONAL column) in scope:
1. A mapping table, ONE ROW PER CORPUS COLUMN: `corpus column | status | AIMS source (table.column / expression) | transformation (encoding, time-zone, filter, join) | evidence | gap / risk`.
   status is exactly one of: DIRECT (1:1 column), DERIVABLE (needs a join/decode/computation that you verified on data), PARTIAL (only for part of the population/period, or approximate), MISSING (not in AIMS/TSC at all), UNKNOWN (cannot determine).
2. A tested (read-only) SQL sketch producing a few rows/counts for a small window (e.g. January 2026 = LEG_DAY 16802..16832), or an explanation why it cannot be built. Show counts, not personal values.
3. History depth: min/max date available in the relevant AIMS tables, and whether past states are recoverable (the real corpus needs 2024-04-24 .. 2026-08-31 at least; CrewSim asks for ideally 36 months from 2023-08).
4. Comparison with what the real Pierre v3 CSV contains for the same dataset where relevant (read the CSV header and use aggregate counts only, e.g. rows per month; do NOT print crew ids/personal data), to reveal differences (e.g. fields Pierre computed outside AIMS such as Snowflake mart logic).
5. Verdict for the dataset: FULL / MOSTLY / PARTIAL / NOT POSSIBLE direct-from-AIMS, one-paragraph justification, and the ordered list of what is missing + what business input is needed.
6. Concise notes (not full docs) on every newly discovered AIMS object you relied on: what it is, key, grain, row count, date range, how it is written (inference).
Finish your reply with ONLY: the file path, and a <=12-bullet summary of verdicts and the most important blockers.
