-- Drafted legs recorded by AIMS (PNC + PNT), one row per drafted flight leg (plus optional day-level markers below).
-- Tested read-only against TSC on 2026-11-03 (January 2026: 645 leg rows = 637 flights + 8 ground legs with LEG_FLT < 0, which have no LEGMAIN/LEGTIMES row so ACTUAL_DEPARTURE_UTC is NULL). See tables\ROSTERDT.md and drafts.md.
DECLARE @BEGIN DATE = '2026-01-01', @END DATE = '2026-01-31';
DECLARE @B INT = DATEDIFF(DAY, '1980-01-01', @BEGIN), @E INT = DATEDIFF(DAY, '1980-01-01', @END);  -- AIMS day numbers: sargable on LEG_DAY

SELECT  d.ID                                              AS CREW_ID,
        DATEADD(DAY, d.LEG_DAY, '1980-01-01')             AS LEG_DATE,
        r.POS,
        d.VALUE1                                          AS DRAFT_CODE,
        CASE d.VALUE1 WHEN 15 THEN 'PNC DRAFT A LA BASE'
                      WHEN 16 THEN 'PNC DRAFT OUT OF BASE/HORS BASE'
                      WHEN 19 THEN 'DRAFT PILOTE'
                      WHEN 20 THEN 'DRAFT PILOTE SUR VACANCES' END AS DRAFT_TYPE,
        cr.DESC_                                          AS PAIRING_NAME,
        r.DUTYDAY, r.DUTYNO,
        d.LEG_CARRIER, d.LEG_FLT, d.LEG_DEP, lm.ARR, d.LEG_LEGCD,
        -- actual departure, UTC: priority OPSATD -> BLOF -> ETD -> STD (same as R3/R4)
        DATEADD(MINUTE, COALESCE(lt.OPSATD, lt.BLOF, lt.ETD, lm.STD), DATEADD(DAY, d.LEG_DAY, '1980-01-01')) AS ACTUAL_DEPARTURE_UTC
FROM    TSC.dbo.ROSTERDT d
JOIN    TSC.dbo.ROSTER   r  ON  r.ID = d.ID AND r.LEG_DAY = d.LEG_DAY AND r.LEG_DEP = d.LEG_DEP
                           AND r.LEG_CARRIER = d.LEG_CARRIER AND r.LEG_FLT = d.LEG_FLT AND r.LEG_LEGCD = d.LEG_LEGCD
                           AND r.DUTYNO = d.DUTYNO AND r.DUTYDAY = d.DUTYDAY AND r.GRDDUTYBEG = d.GRDDUTYBEG   -- full roster key: no fan-out
LEFT JOIN TSC.dbo.CRROUTE   cr ON cr.CDATE = r.DUTYDAY AND cr.CROUTE = r.DUTYNO
LEFT JOIN TSC.dbo.LEGMAIN   lm ON lm.DAY = r.LEG_DAY AND lm.DEP = r.LEG_DEP AND lm.CARRIER = r.LEG_CARRIER AND lm.FLT = r.LEG_FLT AND lm.LEGCD = r.LEG_LEGCD
LEFT JOIN TSC.dbo.LEGTIMES  lt ON lt.DAY = r.LEG_DAY AND lt.DEP = r.LEG_DEP AND lt.CARRIER = r.LEG_CARRIER AND lt.FLT = r.LEG_FLT AND lt.LEGCD = r.LEG_LEGCD
WHERE   d.RECTYPE = 21 AND d.VALUE1 IN (15, 16, 19, 20)
  AND   d.LEG_FLT <> 0                       -- leg-level markers only; LEG_FLT = 0 rows are day-level (see below)
  AND   d.LEG_DAY BETWEEN @B AND @E
ORDER BY d.ID, d.LEG_DAY, ACTUAL_DEPARTURE_UTC;

-- Day-level markers (crew drafted "for the day", no pairing leg; DUTYNO = 0): kept separate because they have no leg/pairing.
-- SELECT d.ID, DATEADD(DAY, d.LEG_DAY, '1980-01-01') AS DAY_DATE, d.VALUE1 AS DRAFT_CODE
-- FROM TSC.dbo.ROSTERDT d WHERE d.RECTYPE = 21 AND d.VALUE1 IN (15,16,19,20) AND d.LEG_FLT = 0 AND d.LEG_DAY BETWEEN @B AND @E;

