# Drafts in AIMS - how a "drafted pairing" is recorded and how to retrieve it

Source: `c:\dev\crewsim\backlog\DRAFTPNCPNT.sql` (original kept in `queries\DRAFTPNCPNT.original.sql`; its header says the same logic is applied in Snowflake `PRD_DVL.DMT_CREW.DMT_DRAFTS_PNT_PNC`, ordered by `CREW_CODE, ACTUAL_DEPARTURE_DATE_UTC`). Object documentation: [tables/ROSTERDT.md](tables/ROSTERDT.md). Verified against the live TSC database on 2026-11-03 (read-only).

## 1. Business concept
A **draft** is when crew (pilots = PNT, cabin crew = PNC) are assigned to a flight/pairing outside the normal bid/roster process (typically from a day off, reserve, vacation or another base) to cover a need. AIMS does **not** keep drafts in a dedicated table; it stamps the roster element with an attribute in the EAV table `ROSTERDT`:

| `ROSTERDT.RECTYPE` | `VALUE1` | Meaning (label used by the query) | Crew |
|---|---|---|---|
| 21 | 15 | PNC DRAFT A LA BASE | cabin |
| 21 | 16 | PNC DRAFT OUT OF BASE / HORS BASE | cabin |
| 21 | 19 | DRAFT PILOTE | pilot |
| 21 | 20 | DRAFT PILOTE SUR VACANCES (drafted while on vacation) | pilot |

`RECTYPE 21` has other `VALUE1` codes (1-14, 17, 18, 21-24, 27) that are **not decoded anywhere**; they are not "not drafted" - they are unknown.

## 2. Two kinds of draft marker
* **Element level** (`ROSTERDT.LEG_FLT <> 0`): the draft is on one roster element (a flight leg, or occasionally a ground activity). Identified by the full ROSTER key. This is the normal case (645 rows in 2026-01, 637 flights).
* **Day level** (`ROSTERDT.LEG_FLT = 0`, `DUTYNO = 0`): the draft is on the crew-day (480 rows in 2026 for 390 crew). No ROSTER row has that key; only `ID + LEG_DAY` links to ROSTER.

## 3. What the backlog query does (annotated)
```
RO     = ROSTER rows with LEG_DATE in [@BEGIN,@END]          (ID, POS, DUTYDAY, DUTYNO, leg key, GRDDUTYBEG)
RDT1   = ROSTERDT rows in the window with LEG_FLT <> 0       (element level; negative LEG_FLT included)
RDT2   = ROSTERDT rows in the window with LEG_FLT  = 0       (day level)
RF_1   = RO LEFT JOIN RDT1 on ID + the 5-column leg key      (DUTYNO, DUTYDAY, GRDDUTYBEG are NOT in the join)
RF_2   = RO LEFT JOIN RDT2 on ID + LEG_DAY                   (day marker copied to EVERY roster row of the crew-day)
RF     = RF_1 UNION ALL RF_2
final  = RF where RECTYPE = 21 AND VALUE1 IN (15,16,19,20), DRAFT_TYPE decoded with a CASE, ORDER BY ID, LEG_DATE
```
Output columns: `LEG_DATE, ID, POS, DUTYDAY, DUTYNO, LEG_DAY, LEG_CARRIER, LEG_FLT, LEG_LEGCD, RECTYPE, VALUE1, VALUE2, DRAFT_TYPE`.

## 4. Behaviour you must know (measured)
1. **A day-level marker is multiplied** onto every ROSTER row of that crew-day (flights, ground, anything): in 2026-01, 11 distinct day markers produce 59 joined rows. Those rows are labelled drafted although only the crew-day carries the marker. Rows for crew-days with a marker but no ROSTER row do not appear at all (none occurred in the sample).
2. **Element-level join omits `DUTYNO, DUTYDAY, GRDDUTYBEG`.** Safe for flights (24,476 flight rows = 24,476 distinct `ID + leg key` in 2026-01), but ground activities (negative `LEG_FLT`) can duplicate. Use the full ROSTER key.
3. **No pairing name, no airports, no time in the output.** `DUTYDAY, DUTYNO` is the pairing instance (`CRROUTE.CDATE, CROUTE`; name `CRROUTE.DESC_`); the "actual departure UTC" of the Snowflake mart needs LEGTIMES/LEGMAIN (priority `OPSATD -> BLOF -> ETD -> STD`, UTC minutes after midnight of `LEG_DAY`).
4. **Sargability:** the `CAST(DATEADD(DAY, LEG_DAY, ...) AS DATE)` filters hide `LEG_DAY` from the indexes; compare to day numbers instead (`ROSTERDT_INDEX_2/3` start with `RECTYPE` / `LEG_DAY`).
5. **RECTYPE 21 is filtered only at the end** of the pipeline in the original; the CTEs build all attributes first (RDT1/RDT2 contain every RECTYPE, 26.9M-row table). Filter `RECTYPE = 21` inside the CTE.
6. **Draft is per leg, not per pairing**: 561 PNT draft legs fall in 320 pairings (202 crew) in 2026-01.
7. **Day number** = days since 1980-01-01; 2026-01-01 = 16802.
8. **PNC/PNT consistency** verified: 15/16 only on non-PNT positions, 19/20 only on positions 1, 2, 4.

## 5. Recommended retrieval
Use `queries\drafted_legs.sql` (tested: 645 rows, 245 crew, 341 pairings for 2026-01). It keeps the original filters and decoding, joins ROSTER on the full key, adds `CRROUTE.DESC_` (pairing), LEGMAIN (`ARR`) and a computed `ACTUAL_DEPARTURE_UTC`, and leaves day-level markers as a separate optional query.

Pairing-level view of drafts (a pairing is "drafted" if any of its legs carries a draft marker for a given crew):
```sql
SELECT d.ID, r.DUTYDAY, r.DUTYNO, cr.DESC_, MAX(d.VALUE1) AS draft_code, COUNT(*) AS drafted_legs
FROM TSC.dbo.ROSTERDT d
JOIN TSC.dbo.ROSTER r ON r.ID=d.ID AND r.LEG_DAY=d.LEG_DAY AND r.LEG_DEP=d.LEG_DEP AND r.LEG_CARRIER=d.LEG_CARRIER AND r.LEG_FLT=d.LEG_FLT
                     AND r.LEG_LEGCD=d.LEG_LEGCD AND r.DUTYNO=d.DUTYNO AND r.DUTYDAY=d.DUTYDAY AND r.GRDDUTYBEG=d.GRDDUTYBEG
LEFT JOIN TSC.dbo.CRROUTE cr ON cr.CDATE=r.DUTYDAY AND cr.CROUTE=r.DUTYNO
WHERE d.RECTYPE=21 AND d.VALUE1 IN (15,16,19,20) AND d.LEG_FLT>0 AND d.LEG_DAY BETWEEN 16802 AND 16832
GROUP BY d.ID, r.DUTYDAY, r.DUTYNO, cr.DESC_;
```
(If a crew has mixed codes inside one pairing, group by `d.VALUE1` instead of `MAX`.)

## 6. Relation to the planner-assist procedures
`dbo.R0_GetDraftList` **forecasts** draft candidates (PNT draft order, 13 steps) and flags rule risks; it never reads `ROSTERDT`. `ROSTERDT RECTYPE 21` is the **recorded outcome**. The two can be compared to back-test R0, e.g. take pairings from `drafted_legs.sql`, run R0 for the same pairing/date, and check whether the actually drafted crew were among the top-ranked candidates and whether R3/R4/R5 violations existed on the drafted pairing.

## 7. Yearly volume (rows, element + day level; RECTYPE 21)
2022: 15=1,915 / 16=282 / 19=2,376 / 20=2; 2023: 719 / 215 / 3,072 / 1; 2024: 528 / 219 / 4,020 / 4; 2025: 466 / 153 / 3,719 / 52; 2026 (to 2026-11-03 and planned): 445 / 238 / 6,500 / 85.
Rising PNT drafts (19) and the first non-trivial "on vacation" drafts (20) since 2025 are visible; the cause is not in the data.

## 8. Open points
Meaning of the remaining RECTYPE 21 codes; exact AIMS semantics of "A LA BASE / HORS BASE" (crew base vs pairing base); whether the marker is deleted when a draft is cancelled; mapping of Snowflake `CREW_CODE` to the AIMS crew id; `VALUE2` is always 0 for RECTYPE 21.
