# Shared brief for semantic documentation of the TSC (AIMS) database

Goal: for each object assigned to you, write ONE markdown file in
C:\dev\crewsim\docs\aims_semantic\tables\<OBJECT>.md describing it in VERY detailed, business-meaningful terms
(AIMS = airline crew scheduling / operations system; TSC = the AIMS database; this repo = "planner-assist" crew-planning MCP that reads it).

## Evidence you must use
1. Column metadata (names, types, nullability, PK/indexes, row counts), already extracted:
   C:\dev\crewsim\docs\aims_semantic\_raw\columns.json  (fields obj,otype,cid,col,typ,len,prec,sc,nul,idn,comp)
   ...\_raw\indexes.json, ...\_raw\rowcounts.json (for tables). Views have NO definitions available (encrypted/no permission) and no row counts.
   CrewSchedAI custom tables: ...\_raw\crewschedai_columns.json, crewschedai_rowcounts.json.
   There are NO declared foreign keys and NO MS_Description properties, so semantics must be inferred.
2. The SQL source that uses them: C:\dev\flint\planner-assist-mcp\database\dbo\*.sql and \rpt\*.sql. Grep for the object name AND for its aliases and
   its columns; read the surrounding code (joins, filters, CASE decoding, comments, magic numbers/codes, time-zone handling, how dates/times are encoded).
   Files are big (up to 90KB): use grep with context and read the relevant ranges, do not skip evidence.
3. Live data profiling, READ-ONLY, via the helper:
   pwsh -NoProfile -File C:\dev\crewsim\docs\aims_semantic\_raw\q.ps1 -Database TSC -Sql "SELECT ..." [-Max 60]
   (use -Database CrewSchedAI for the custom tables). Only SELECT is accepted. Big tables: ROSTER 14M rows, HOTAC 8M, CREWLEG 1.8M, LEGMAIN 1.2M, CRROUTE 0.5M:
   ALWAYS use TOP, a narrow date/ID filter, or aggregate on indexed columns; never SELECT * unbounded; keep each query cheap. Do not run more than ~25 queries per object.
   Use profiling to: confirm data types/encodings (e.g. is DAY a yyyymmdd int? minutes since midnight? UTC vs local?), list DISTINCT values + counts for low-cardinality
   code columns, min/max dates, null rates of key columns, uniqueness of candidate keys, and to verify join keys by counting matches between tables.
## PRIVACY RULES (strict)
Crew data is personal data. NEVER write real crew names, birth dates, addresses, phone numbers, e-mails, passport/ID numbers, employee numbers or any
individual-identifying values into the markdown. Describe such columns by meaning only ("crew member's surname"), and do not profile their values.
Lookup/code values (activity codes, categories, airports, aircraft types, rule names, position codes) ARE fine to list. Pseudonymous operational keys such as flight numbers
are fine as aggregates but do not paste individual rows of crew assignments.

## Required structure of every <OBJECT>.md (keep these headings, in this order)
# <OBJECT>  (Table|View)  - <one-line business title>
## 1. Purpose & business meaning   (what real-world thing a row represents; grain; lifecycle; who writes/reads it; relation to AIMS modules)
## 2. Physical facts   (database.schema, type, row count at extraction time, primary key, other indexes and what they imply about access patterns, notes on partitions/size)
## 3. Column dictionary   (a markdown table: Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence)
   Cover EVERY column in columns.json for the object (views with hundreds of columns: group them logically under sub-headings, but still name every column; a column you cannot
   interpret must be listed as "unknown - not used by any procedure" rather than omitted or guessed). The Evidence column cites the proc/file that uses it or "profiled" or "naming inference".
## 4. Keys & relationships   (natural key; join keys to other TSC objects, cardinality 1:1/1:N/N:M, and the exact join predicate used in the code, with file reference)
## 5. Encoding conventions & gotchas   (date/time encodings, UTC vs local, sentinel values like 0/1900-01-01/NULL, soft deletes, active-period ranges ACTIVEBEG/ACTIVEEND, case/trim issues, performance traps)
## 6. How the planner-assist procedures use it   (per procedure: which columns, what filters, why; mention the rule/regulation being checked if any)
## 7. Typical query patterns   (2-4 correct, minimal example SELECTs using exact column names, safe for an LLM text-to-SQL agent; include the mandatory filters)
## 8. Data profile   (only aggregate facts you actually measured: ranges, distinct counts, top code values with counts; state the date you measured: today is 2026-11-03)
## 9. Open questions / confidence   (what remains uncertain; label inferences as such; never present a guess as a fact)

Quality bar: no filler, no generic advice. Every claim about meaning must be traceable to code, data or naming; mark inference honestly. Prefer precise facts
(e.g. "DAY is the AIMS day-number/date of the flight's scheduled departure, stored as ...") over vague text. Write in English. Do not modify any .sql source file. Do not write
outside _semantic\tables. When finished reply with ONLY: the list of files written, and a short list (max 10 bullets) of the most important cross-table facts you discovered
(join keys, encodings, status codes) so they can be merged into an overview.
