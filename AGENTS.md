# CrewSim project memory (kept by the assistant; update it whenever the user answers or decides something)

## Who is who
- **NK = Nabil Kemerchou (the user).** He owns the CrewSim side and also controls the AIMS/QAS environment.
- **Pierre** = Air Transat data owner. Emails to him are in French, signed "Nabil" (`pierre2.md`, `Pierre3.md`).

## Current direction (Nov 2026)
Reading **AIMS directly** (server `PPR-MTLSQLAIMS1\AIMS`, QAS copy) replaces Pierre's v3 CSVs for D2-D6, D8.
v3 files (`src/crewsim/data/corpus/real_datav2/v3`) stay only as a **regression/validation set**.
Pierre's v3 still supplies: D7 pay, D10 invoices, D1 HR fields, D11, pseudonym table, his emails/notes.
Questionnaire: `P:\Public\NAB\CrewSim_Courriel_et_Questions_Pierre_FR.docx` (30 questions, NK answered Q1-Q4).
Renumbered questions for Pierre (22 now; NK also removed old Q29 'Fichiers minimum et dates' and old Q30 'Fichiers v3 de reference' on 2026-11-04, and the 'Calendrier' section; the v3-as-regression-set decision is NK's, not asked of Pierre. Earlier: 24: old Q1-Q4 answered, old Q27-Q28 (draft mart / WFLY) removed because NK asked someone else by email): `P:\Public\NAB\CrewSim_Courriel_et_Questions_Pierre_FR_v2.docx`.
v2 also has a 6th column "Pourquoi on en a besoin" in Table 3 (the 21 complementary files). Old->new numbering: new = old - 4 for old Q5..Q26 (old Q5 = new Q1 ... old Q26 = new Q22); old Q29/Q30 = new Q23/Q24; sections renumbered 1-3 (the Drafts-mart section is gone).
NK (2026-11-04) asked someone else (by email) about: old Q27 (DRAFTPNCPNT.sql / ROSTERDT VALUE1 codes, CREW_CODE) and old Q28 (WFLY vs DAY_OFF before a draft). Do not re-ask Pierre; the answers will come from that person.

## NK's answers (source: the .docx, "NK :" notes)
| Old Q | Topic | NK's answer | Decision recorded |
|---|---|---|---|
| 1 | How QAS is fed from production | "It's a snapshot of the production" | QAS = production snapshot; what we validate in QAS holds for prod. Removed from Pierre's list. |
| 2 | Service account / prod access | "We will just use QAS, as it's a safe copy of the Prod" | No prod access and no reporting replica needed. Read-only on QAS only. Removed. |
| 3 | Pseudonym table (AIMS id -> crew_id) | "Yes for sim schema and store the data in CrewSchedAI under sim schema" | Hosted in DB `CrewSchedAI`, schema `sim`, never in the repo. Law 25 / security accepted by NK. **NK confirmed (2026-11-04) Q3 is FULLY answered**: the channel / coverage / new-id sub-questions are dropped too. Removed. |
| 4 | What happened on 2024-05-14; archives of the journal | "I will provide you with access to a backup DB named AIMS2 that has all the history before 2024" | History before 2024 exists in backup DB **AIMS2**. NK (2026-11-04): "I will give you access to AIMS2 soon" -- **access NOT yet granted**. Removed. See open points below. |

Q5-Q30 (old numbering) had **no answer** in the file. Q8 (D4 absence types) has a yellow highlight on "types d'absence"
and no text; meaning unknown (not asked). Ask NK if it matters.

## Open points created by these answers (not yet decided by NK)
- AIMS2 covers "before 2024"; the journal is dense from 2024-03-14 and exists from 2024-05-14. The gap 2024-01..2024-05-14
  and whether AIMS2 journals carry notification timestamps are unknown. Pre-2024-05-14 D8 has ~48% of flights with no actual times.
- The questionnaire still says "on démarre l'historique au 2024-05-14" (Table 1 note), "rien avant n'est nécessaire" (old Q29 / new Q26)
  and lists `m04_event_journal_archive` (P3) as "seulement si une archive existe". AIMS2 contradicts all three; NK has not asked to change them.
- Questionnaire text NOT changed for AIMS2 (NK did not ask); v2's Table 3 row M04 only says AIMS2 "pourrait en tenir lieu".
- More history would give a second complete winter_sun season, the main limitation of the v3 calibration.

## Code state (see also `configs/real.yaml`, `readme.md`)
- Real data runs only through `CREWSIM_CONFIG=configs/real.yaml`; mock corpus stays the default and the tests expect it.
- Accommodations made for v3: extra columns ignored, `scope.fleet_fallback: A321`, windows 2024-05-01..2025-07-31 / 2025-08-01..2026-08-31,
  draft codes DRAFT_THX + DRAFT_T2 (D6: DRAFT + SHORT_NOTICE_COVER), ABSENCE accepted, null notification_ts assumed at 00:00 of absence_start,
  D8 self-loops dropped, V6 uses `data.pay_codes`. Limitations are reported by `src/crewsim/data/limitations.py`.
- D12 comes from the mock file (all values `[CONFIRM]`): premium_pct, guarantee_per_day_cad, notice_hours, term still to be informed.
- Known pre-existing failing tests: `tests/engine/test_audit_fixes.py::test_a_rarely_seen_state_never_becomes_absorbing`,
  `tests/engine/test_events.py::test_open_time_item_deadline_is_report_time_minus_the_configured_lead`; ruff SIM105 at `cli.py:458`.
