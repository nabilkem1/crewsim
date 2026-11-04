# vvFMSInfo1  (View)  - AIMS "FMS info" parameter record: instructor/check capability labels and flight-check type table (1 row, 560 columns)

## 1. Purpose & business meaning
`TSC.dbo.vvFMSInfo1` is the view over an AIMS **system-parameter record** (not a per-crew or per-flight table). It exposes **one single row** (`RECDESC = 'CREWCODES2'`) whose 559 data columns are parallel arrays of configuration data set up once by the AIMS administrators:

1. **48 labels for instructor / check-pilot capabilities** (`FLTDUT_1..FLTDUT_48`): "A CHECK PILOT", "B CHECK PILOT", "LINE CHECK DROIT", "LINE CHECK GAUCH", "ENTRAINEUR SIMULATEUR", "LINE COACH PNC" ... (28 are defined, 20 are blank). Each label names one bit of the 48-bit capability block that is stored **per qualification row** in `CREWQUAL.DATA_BEGIN_END` (bytes 1-6). This is the dictionary that lets planner-assist turn those bits into readable "Instructor_Qualifications" and filter pilots by them.
2. **A table of 127 flight-check types** (`FLTCHECK_n_DESCR/_REQDOCS/_CODE/_QUAL`): ROUTE CHECK, LINE INDOC, PICUS, IFR, SIM TRAINING, TOUCH & GO, ETOPS, FAM FLIGHT ... (21 populated). Each check type carries a one-letter code and a bitmask of the instructor capabilities allowed to conduct it. This block is not used by planner-assist.
3. Two small bitmaps/arrays (`GALEYCATEG` - galley categories; `FLTCHECKTRAINEE` - trainee letter codes of the checks) and a reserved area (`FUT180`).

"FMS" in the name is probably the AIMS *Flight Management System* / flight-scheduling parameter family (as in `vvFMSCodes`, the sibling view with flight-type codes); "CREWCODES2" is the second crew-codes parameter block (inference). Writers: AIMS administrators (rare configuration edits). Readers: `R0_GetDraftList`, `rpt.get_crew_qualifications`, `rpt.list_instructor_qualifications`.

## 2. Physical facts
- `TSC.dbo.vvFMSInfo1`, **VIEW** (definition not retrievable: `view_defs.json` has `def = null`; no row count/index metadata). Measured **1 row** (`RECDESC` = `CREWCODES2` only; `COUNT(*) = 1`), **560 columns** (`cid` 1..560).
- No key (a single-row view). The procedures always add `WHERE RECDESC = 'CREWCODES2'` so that they keep working if AIMS ever exposes more record kinds.
- Column count: 4 header columns + 48 `FLTDUT_n` + 127 x 4 `FLTCHECK_n_*` = 4 + 48 + 508 = 560.
- Costs nothing to read, but **do not `SELECT *`** (560 columns, roughly 12 KB per row): select only `FLTDUT_1..FLTDUT_28` (labels) or the few `FLTCHECK` columns needed.
- Character widths below are `len/2` of columns.json (metadata is in bytes).

## 3. Column dictionary
All 560 columns are listed: 4 header columns, 48 `FLTDUT_n` rows, and for the 127 flight-check slots one inventory row per slot naming its four columns explicitly. Values were read from the single row (these are configuration labels, not personal data).

### 3.1 Header columns

| Column | Type | Null | Business meaning | Encoding / allowed values / units | Evidence |
|---|---|---|---|---|---|
| RECDESC | nchar(10) | Y | Record descriptor = the AIMS record kind stored in this row. The view exposes exactly **one row** whose `RECDESC = 'CREWCODES2'` (the 'crew codes #2' parameter record: instructor-capability labels and flight-check types) | single value `CREWCODES2`; filter `WHERE RECDESC = 'CREWCODES2'` | profiled; `R0_GetDraftList.sql` line 275, `rpt.get_crew_qualifications.sql` line 37, `rpt.list_instructor_qualifications.sql` |
| GALEYCATEG | varbinary(30) | Y | Bitmap over crew categories (240 bits = `CREWCAT` numbers) of the categories allowed to work in the galley position (inference from the name) | 30 bytes, all zero in this database | profiled; naming inference; not used by any procedure |
| FLTCHECKTRAINEE | varbinary(127) | Y | One byte per flight-check type n (1..127): the **lowercase letter code of the trainee variant** of check n. The first 21 bytes read `rlpistfeoxcdghqzjawmk`, i.e. the lowercase of `FLTCHECK_1_CODE .. FLTCHECK_21_CODE` (R L P I S T F E O X C D G H Q Z J A W M K); bytes 22-127 are zero | byte n = ASCII code of the letter (e.g. 0x72 = 'r' for check 1); 0 = none | profiled (byte-by-byte comparison with the CODE columns); not used by any procedure |
| FUT180 | varbinary(33) | Y | Reserved/future area of the AIMS record | 33 bytes, all zero | profiled; unknown - not used by any procedure |

### 3.2 Instructor / check-capability labels: FLTDUT_1 .. FLTDUT_48

Each `FLTDUT_n` (nchar(30), blank-padded) is the **name of the n-th instructor/check capability bit**. Capability n corresponds to bit `n` (1-based) of the 48-bit block stored in `CREWQUAL.DATA_BEGIN_END` bytes 1-6: byte `(n-1)/8 + 1`, mask `2^((n-1)%8)`. Labels are the French/English texts shown in AIMS ('LINE CHECK DROIT' = right-seat line check, 'LINE CHECK GAUCH' = left-seat line check, 'ENTRAINEUR' = trainer/instructor, 'PNC' = cabin crew, 'PNT' = pilots, 'DV' = flight director). Evidence for all 48 columns: `R0_GetDraftList.sql` lines 261-290 (reads FLTDUT_1..48 into `@info_FLTDUT_n` and builds `@QualMap`), `rpt.get_crew_qualifications.sql` lines 23-37 and 68-120, `rpt.list_instructor_qualifications.sql` (returns all 48).

| Column | Type | Null | Meaning (label value, measured 2026-11-03) | CREWQUAL.DATA_BEGIN_END bit (byte, mask) |
|---|---|---|---|---|
| FLTDUT_1 | nchar(30) | Y | A CHECK PILOT | byte 1, mask 1 |
| FLTDUT_2 | nchar(30) | Y | B CHECK PILOT | byte 1, mask 2 |
| FLTDUT_3 | nchar(30) | Y | LINE CHECK DROIT | byte 1, mask 4 |
| FLTDUT_4 | nchar(30) | Y | LINE CHECK GAUCH | byte 1, mask 8 |
| FLTDUT_5 | nchar(30) | Y | MECANICIEN VERIF | byte 1, mask 16 |
| FLTDUT_6 | nchar(30) | Y | RC ETOPS CHECK | byte 1, mask 32 |
| FLTDUT_7 | nchar(30) | Y | ENTRAINEUR PRLI | byte 1, mask 64 |
| FLTDUT_8 | nchar(30) | Y | ENTRAINEUR SOP | byte 1, mask 128 |
| FLTDUT_9 | nchar(30) | Y | ENTRAINEUR SIMULATEUR | byte 2, mask 1 |
| FLTDUT_10 | nchar(30) | Y | ENTRAINEUR PERFORMANCE | byte 2, mask 2 |
| FLTDUT_11 | nchar(30) | Y | ENTRAINEUR EPT | byte 2, mask 4 |
| FLTDUT_12 | nchar(30) | Y | ENTRAINEUR PNT FORMATION SOL | byte 2, mask 8 |
| FLTDUT_13 | nchar(30) | Y | CRM JET TRANSITION INITIAL B | byte 2, mask 16 |
| FLTDUT_14 | nchar(30) | Y | PILOTE STANDARDISATEUR | byte 2, mask 32 |
| FLTDUT_15 | nchar(30) | Y | TRAINING DEVELOPPER | byte 2, mask 64 |
| FLTDUT_16 | nchar(30) | Y | REQUALIFICATION | byte 2, mask 128 |
| FLTDUT_17 | nchar(30) | Y | EET | byte 3, mask 1 |
| FLTDUT_18 | nchar(30) | Y | LINE INSPECTION | byte 3, mask 2 |
| FLTDUT_19 | nchar(30) | Y | AIRCRAFT INSPECTION | byte 3, mask 4 |
| FLTDUT_20 | nchar(30) | Y | ENTRAINEUR INITIAL | byte 3, mask 8 |
| FLTDUT_21 | nchar(30) | Y | ENTRAINEUR FIRST AID | byte 3, mask 16 |
| FLTDUT_22 | nchar(30) | Y | ENTRAINEUR ANNUELLE | byte 3, mask 32 |
| FLTDUT_23 | nchar(30) | Y | ENTRAINEUR DV | byte 3, mask 64 |
| FLTDUT_24 | nchar(30) | Y | LINE COACH PNC | byte 3, mask 128 |
| FLTDUT_25 | nchar(30) | Y | INITIAL-B APS-MCC INSTRUCTEUR | byte 4, mask 1 |
| FLTDUT_26 | nchar(30) | Y | JET TRANSITION INITIAL B | byte 4, mask 2 |
| FLTDUT_27 | nchar(30) | Y | FD MEETING Leadership | byte 4, mask 4 |
| FLTDUT_28 | nchar(30) | Y | Formation Commandant | byte 4, mask 8 |
| FLTDUT_29 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 4, mask 16 |
| FLTDUT_30 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 4, mask 32 |
| FLTDUT_31 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 4, mask 64 |
| FLTDUT_32 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 4, mask 128 |
| FLTDUT_33 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 5, mask 1 |
| FLTDUT_34 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 5, mask 2 |
| FLTDUT_35 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 5, mask 4 |
| FLTDUT_36 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 5, mask 8 |
| FLTDUT_37 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 5, mask 16 |
| FLTDUT_38 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 5, mask 32 |
| FLTDUT_39 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 5, mask 64 |
| FLTDUT_40 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 5, mask 128 |
| FLTDUT_41 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 6, mask 1 |
| FLTDUT_42 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 6, mask 2 |
| FLTDUT_43 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 6, mask 4 |
| FLTDUT_44 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 6, mask 8 |
| FLTDUT_45 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 6, mask 16 |
| FLTDUT_46 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 6, mask 32 |
| FLTDUT_47 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 6, mask 64 |
| FLTDUT_48 | nchar(30) | Y | (blank - unused slot, bit never set) | byte 6, mask 128 |

### 3.3 Flight-check types: FLTCHECK_1 .. FLTCHECK_127 (4 columns each = 508 columns)

A table of **127 flight-check / line-training check types** (slot n = check type n). Every slot has four columns:

- `FLTCHECK_n_DESCR` (nchar(29)): description of the check type (blank = slot unused);
- `FLTCHECK_n_REQDOCS` (tinyint): required-documents flag/count (0 in every populated slot - purpose unknown);
- `FLTCHECK_n_CODE` (nchar(2)): one-letter code of the check, blank-padded (R, L, P, I ...); the trainee variant of the letter is byte n of `FLTCHECKTRAINEE` (lowercase);
- `FLTCHECK_n_QUAL` (bigint): **bitmask of the instructor capabilities (FLTDUT_k, bit k-1) that are allowed to conduct/sign check n** (inference, strongly supported: 'ROUTE CHECK' = 3 = A CHECK PILOT + B CHECK PILOT; 'ETOPS' = 35 = A CHECK + B CHECK + RC ETOPS CHECK; 'coachings flights' = 8388608 = bit 24 = LINE COACH PNC; 'LINE INDOC' = 15 = A/B CHECK PILOT + LINE CHECK DROIT/GAUCH).

None of the FLTCHECK_* columns is read by any planner-assist procedure; they are documented from the data. Only slots 1-21 are populated; slots 22-127 are empty (blank description/code, `REQDOCS` = 0, `QUAL` = 0). Populated slots:

| n | FLTCHECK_n_DESCR | FLTCHECK_n_CODE | FLTCHECK_n_REQDOCS | FLTCHECK_n_QUAL (decoded) |
|---|---|---|---|---|
| 1 | ROUTE CHECK | R | 0 | 3 = A CHECK PILOT + B CHECK PILOT |
| 2 | LINE INDOC | L | 0 | 15 = A CHECK PILOT + B CHECK PILOT + LINE CHECK DROIT + LINE CHECK GAUCH |
| 3 | PICUS | P | 0 | 7 = A CHECK PILOT + B CHECK PILOT + LINE CHECK DROIT |
| 4 | IFR | I | 0 | 1 = A CHECK PILOT |
| 5 | SIM TRAINING | S | 0 | 3 = A CHECK PILOT + B CHECK PILOT |
| 6 | TOUCH & GO | T | 0 | 1 = A CHECK PILOT |
| 7 | FIRST FLIGHT LI FO | F | 0 | 15 = A CHECK PILOT + B CHECK PILOT + LINE CHECK DROIT + LINE CHECK GAUCH |
| 8 | ETOPS | E | 0 | 35 = A CHECK PILOT + B CHECK PILOT + RC ETOPS CHECK |
| 9 | LIETOPS | O | 0 | 15 = A CHECK PILOT + B CHECK PILOT + LINE CHECK DROIT + LINE CHECK GAUCH |
| 10 | FAM FLIGHT | X | 0 | 0 (no capability required / none recorded) |
| 11 | R-RE TURN | C | 0 | 3 = A CHECK PILOT + B CHECK PILOT |
| 12 | CONSOLIDATION | D | 0 | 0 (no capability required / none recorded) |
| 13 | MONITORING | G | 0 | 0 (no capability required / none recorded) |
| 14 | LI ETOPS TYPE RATED | H | 0 | 15 = A CHECK PILOT + B CHECK PILOT + LINE CHECK DROIT + LINE CHECK GAUCH |
| 15 | RC ETOPS TYPE RATED | Q | 0 | 3 = A CHECK PILOT + B CHECK PILOT |
| 16 | coachings flights | Z | 0 | 8388608 = LINE COACH PNC |
| 17 | Observation flight | J | 0 | 15 = A CHECK PILOT + B CHECK PILOT + LINE CHECK DROIT + LINE CHECK GAUCH |
| 18 | Progress Check | A | 0 | 15 = A CHECK PILOT + B CHECK PILOT + LINE CHECK DROIT + LINE CHECK GAUCH |
| 19 | Recommendation Flight | W | 0 | 7 = A CHECK PILOT + B CHECK PILOT + LINE CHECK DROIT |
| 20 | Line Monitoring | M | 0 | 15 = A CHECK PILOT + B CHECK PILOT + LINE CHECK DROIT + LINE CHECK GAUCH |
| 21 | Final Assessment | K | 0 | 3 = A CHECK PILOT + B CHECK PILOT |

Complete column inventory of this block (every column is named below; type/null as in columns.json: DESCR nchar(29), REQDOCS tinyint, CODE nchar(2), QUAL bigint; all nullable):

| n | DESCR column | REQDOCS column | CODE column | QUAL column |
|---|---|---|---|---|
| 1 | FLTCHECK_1_DESCR | FLTCHECK_1_REQDOCS | FLTCHECK_1_CODE | FLTCHECK_1_QUAL |
| 2 | FLTCHECK_2_DESCR | FLTCHECK_2_REQDOCS | FLTCHECK_2_CODE | FLTCHECK_2_QUAL |
| 3 | FLTCHECK_3_DESCR | FLTCHECK_3_REQDOCS | FLTCHECK_3_CODE | FLTCHECK_3_QUAL |
| 4 | FLTCHECK_4_DESCR | FLTCHECK_4_REQDOCS | FLTCHECK_4_CODE | FLTCHECK_4_QUAL |
| 5 | FLTCHECK_5_DESCR | FLTCHECK_5_REQDOCS | FLTCHECK_5_CODE | FLTCHECK_5_QUAL |
| 6 | FLTCHECK_6_DESCR | FLTCHECK_6_REQDOCS | FLTCHECK_6_CODE | FLTCHECK_6_QUAL |
| 7 | FLTCHECK_7_DESCR | FLTCHECK_7_REQDOCS | FLTCHECK_7_CODE | FLTCHECK_7_QUAL |
| 8 | FLTCHECK_8_DESCR | FLTCHECK_8_REQDOCS | FLTCHECK_8_CODE | FLTCHECK_8_QUAL |
| 9 | FLTCHECK_9_DESCR | FLTCHECK_9_REQDOCS | FLTCHECK_9_CODE | FLTCHECK_9_QUAL |
| 10 | FLTCHECK_10_DESCR | FLTCHECK_10_REQDOCS | FLTCHECK_10_CODE | FLTCHECK_10_QUAL |
| 11 | FLTCHECK_11_DESCR | FLTCHECK_11_REQDOCS | FLTCHECK_11_CODE | FLTCHECK_11_QUAL |
| 12 | FLTCHECK_12_DESCR | FLTCHECK_12_REQDOCS | FLTCHECK_12_CODE | FLTCHECK_12_QUAL |
| 13 | FLTCHECK_13_DESCR | FLTCHECK_13_REQDOCS | FLTCHECK_13_CODE | FLTCHECK_13_QUAL |
| 14 | FLTCHECK_14_DESCR | FLTCHECK_14_REQDOCS | FLTCHECK_14_CODE | FLTCHECK_14_QUAL |
| 15 | FLTCHECK_15_DESCR | FLTCHECK_15_REQDOCS | FLTCHECK_15_CODE | FLTCHECK_15_QUAL |
| 16 | FLTCHECK_16_DESCR | FLTCHECK_16_REQDOCS | FLTCHECK_16_CODE | FLTCHECK_16_QUAL |
| 17 | FLTCHECK_17_DESCR | FLTCHECK_17_REQDOCS | FLTCHECK_17_CODE | FLTCHECK_17_QUAL |
| 18 | FLTCHECK_18_DESCR | FLTCHECK_18_REQDOCS | FLTCHECK_18_CODE | FLTCHECK_18_QUAL |
| 19 | FLTCHECK_19_DESCR | FLTCHECK_19_REQDOCS | FLTCHECK_19_CODE | FLTCHECK_19_QUAL |
| 20 | FLTCHECK_20_DESCR | FLTCHECK_20_REQDOCS | FLTCHECK_20_CODE | FLTCHECK_20_QUAL |
| 21 | FLTCHECK_21_DESCR | FLTCHECK_21_REQDOCS | FLTCHECK_21_CODE | FLTCHECK_21_QUAL |
| 22 | FLTCHECK_22_DESCR | FLTCHECK_22_REQDOCS | FLTCHECK_22_CODE | FLTCHECK_22_QUAL |
| 23 | FLTCHECK_23_DESCR | FLTCHECK_23_REQDOCS | FLTCHECK_23_CODE | FLTCHECK_23_QUAL |
| 24 | FLTCHECK_24_DESCR | FLTCHECK_24_REQDOCS | FLTCHECK_24_CODE | FLTCHECK_24_QUAL |
| 25 | FLTCHECK_25_DESCR | FLTCHECK_25_REQDOCS | FLTCHECK_25_CODE | FLTCHECK_25_QUAL |
| 26 | FLTCHECK_26_DESCR | FLTCHECK_26_REQDOCS | FLTCHECK_26_CODE | FLTCHECK_26_QUAL |
| 27 | FLTCHECK_27_DESCR | FLTCHECK_27_REQDOCS | FLTCHECK_27_CODE | FLTCHECK_27_QUAL |
| 28 | FLTCHECK_28_DESCR | FLTCHECK_28_REQDOCS | FLTCHECK_28_CODE | FLTCHECK_28_QUAL |
| 29 | FLTCHECK_29_DESCR | FLTCHECK_29_REQDOCS | FLTCHECK_29_CODE | FLTCHECK_29_QUAL |
| 30 | FLTCHECK_30_DESCR | FLTCHECK_30_REQDOCS | FLTCHECK_30_CODE | FLTCHECK_30_QUAL |
| 31 | FLTCHECK_31_DESCR | FLTCHECK_31_REQDOCS | FLTCHECK_31_CODE | FLTCHECK_31_QUAL |
| 32 | FLTCHECK_32_DESCR | FLTCHECK_32_REQDOCS | FLTCHECK_32_CODE | FLTCHECK_32_QUAL |
| 33 | FLTCHECK_33_DESCR | FLTCHECK_33_REQDOCS | FLTCHECK_33_CODE | FLTCHECK_33_QUAL |
| 34 | FLTCHECK_34_DESCR | FLTCHECK_34_REQDOCS | FLTCHECK_34_CODE | FLTCHECK_34_QUAL |
| 35 | FLTCHECK_35_DESCR | FLTCHECK_35_REQDOCS | FLTCHECK_35_CODE | FLTCHECK_35_QUAL |
| 36 | FLTCHECK_36_DESCR | FLTCHECK_36_REQDOCS | FLTCHECK_36_CODE | FLTCHECK_36_QUAL |
| 37 | FLTCHECK_37_DESCR | FLTCHECK_37_REQDOCS | FLTCHECK_37_CODE | FLTCHECK_37_QUAL |
| 38 | FLTCHECK_38_DESCR | FLTCHECK_38_REQDOCS | FLTCHECK_38_CODE | FLTCHECK_38_QUAL |
| 39 | FLTCHECK_39_DESCR | FLTCHECK_39_REQDOCS | FLTCHECK_39_CODE | FLTCHECK_39_QUAL |
| 40 | FLTCHECK_40_DESCR | FLTCHECK_40_REQDOCS | FLTCHECK_40_CODE | FLTCHECK_40_QUAL |
| 41 | FLTCHECK_41_DESCR | FLTCHECK_41_REQDOCS | FLTCHECK_41_CODE | FLTCHECK_41_QUAL |
| 42 | FLTCHECK_42_DESCR | FLTCHECK_42_REQDOCS | FLTCHECK_42_CODE | FLTCHECK_42_QUAL |
| 43 | FLTCHECK_43_DESCR | FLTCHECK_43_REQDOCS | FLTCHECK_43_CODE | FLTCHECK_43_QUAL |
| 44 | FLTCHECK_44_DESCR | FLTCHECK_44_REQDOCS | FLTCHECK_44_CODE | FLTCHECK_44_QUAL |
| 45 | FLTCHECK_45_DESCR | FLTCHECK_45_REQDOCS | FLTCHECK_45_CODE | FLTCHECK_45_QUAL |
| 46 | FLTCHECK_46_DESCR | FLTCHECK_46_REQDOCS | FLTCHECK_46_CODE | FLTCHECK_46_QUAL |
| 47 | FLTCHECK_47_DESCR | FLTCHECK_47_REQDOCS | FLTCHECK_47_CODE | FLTCHECK_47_QUAL |
| 48 | FLTCHECK_48_DESCR | FLTCHECK_48_REQDOCS | FLTCHECK_48_CODE | FLTCHECK_48_QUAL |
| 49 | FLTCHECK_49_DESCR | FLTCHECK_49_REQDOCS | FLTCHECK_49_CODE | FLTCHECK_49_QUAL |
| 50 | FLTCHECK_50_DESCR | FLTCHECK_50_REQDOCS | FLTCHECK_50_CODE | FLTCHECK_50_QUAL |
| 51 | FLTCHECK_51_DESCR | FLTCHECK_51_REQDOCS | FLTCHECK_51_CODE | FLTCHECK_51_QUAL |
| 52 | FLTCHECK_52_DESCR | FLTCHECK_52_REQDOCS | FLTCHECK_52_CODE | FLTCHECK_52_QUAL |
| 53 | FLTCHECK_53_DESCR | FLTCHECK_53_REQDOCS | FLTCHECK_53_CODE | FLTCHECK_53_QUAL |
| 54 | FLTCHECK_54_DESCR | FLTCHECK_54_REQDOCS | FLTCHECK_54_CODE | FLTCHECK_54_QUAL |
| 55 | FLTCHECK_55_DESCR | FLTCHECK_55_REQDOCS | FLTCHECK_55_CODE | FLTCHECK_55_QUAL |
| 56 | FLTCHECK_56_DESCR | FLTCHECK_56_REQDOCS | FLTCHECK_56_CODE | FLTCHECK_56_QUAL |
| 57 | FLTCHECK_57_DESCR | FLTCHECK_57_REQDOCS | FLTCHECK_57_CODE | FLTCHECK_57_QUAL |
| 58 | FLTCHECK_58_DESCR | FLTCHECK_58_REQDOCS | FLTCHECK_58_CODE | FLTCHECK_58_QUAL |
| 59 | FLTCHECK_59_DESCR | FLTCHECK_59_REQDOCS | FLTCHECK_59_CODE | FLTCHECK_59_QUAL |
| 60 | FLTCHECK_60_DESCR | FLTCHECK_60_REQDOCS | FLTCHECK_60_CODE | FLTCHECK_60_QUAL |
| 61 | FLTCHECK_61_DESCR | FLTCHECK_61_REQDOCS | FLTCHECK_61_CODE | FLTCHECK_61_QUAL |
| 62 | FLTCHECK_62_DESCR | FLTCHECK_62_REQDOCS | FLTCHECK_62_CODE | FLTCHECK_62_QUAL |
| 63 | FLTCHECK_63_DESCR | FLTCHECK_63_REQDOCS | FLTCHECK_63_CODE | FLTCHECK_63_QUAL |
| 64 | FLTCHECK_64_DESCR | FLTCHECK_64_REQDOCS | FLTCHECK_64_CODE | FLTCHECK_64_QUAL |
| 65 | FLTCHECK_65_DESCR | FLTCHECK_65_REQDOCS | FLTCHECK_65_CODE | FLTCHECK_65_QUAL |
| 66 | FLTCHECK_66_DESCR | FLTCHECK_66_REQDOCS | FLTCHECK_66_CODE | FLTCHECK_66_QUAL |
| 67 | FLTCHECK_67_DESCR | FLTCHECK_67_REQDOCS | FLTCHECK_67_CODE | FLTCHECK_67_QUAL |
| 68 | FLTCHECK_68_DESCR | FLTCHECK_68_REQDOCS | FLTCHECK_68_CODE | FLTCHECK_68_QUAL |
| 69 | FLTCHECK_69_DESCR | FLTCHECK_69_REQDOCS | FLTCHECK_69_CODE | FLTCHECK_69_QUAL |
| 70 | FLTCHECK_70_DESCR | FLTCHECK_70_REQDOCS | FLTCHECK_70_CODE | FLTCHECK_70_QUAL |
| 71 | FLTCHECK_71_DESCR | FLTCHECK_71_REQDOCS | FLTCHECK_71_CODE | FLTCHECK_71_QUAL |
| 72 | FLTCHECK_72_DESCR | FLTCHECK_72_REQDOCS | FLTCHECK_72_CODE | FLTCHECK_72_QUAL |
| 73 | FLTCHECK_73_DESCR | FLTCHECK_73_REQDOCS | FLTCHECK_73_CODE | FLTCHECK_73_QUAL |
| 74 | FLTCHECK_74_DESCR | FLTCHECK_74_REQDOCS | FLTCHECK_74_CODE | FLTCHECK_74_QUAL |
| 75 | FLTCHECK_75_DESCR | FLTCHECK_75_REQDOCS | FLTCHECK_75_CODE | FLTCHECK_75_QUAL |
| 76 | FLTCHECK_76_DESCR | FLTCHECK_76_REQDOCS | FLTCHECK_76_CODE | FLTCHECK_76_QUAL |
| 77 | FLTCHECK_77_DESCR | FLTCHECK_77_REQDOCS | FLTCHECK_77_CODE | FLTCHECK_77_QUAL |
| 78 | FLTCHECK_78_DESCR | FLTCHECK_78_REQDOCS | FLTCHECK_78_CODE | FLTCHECK_78_QUAL |
| 79 | FLTCHECK_79_DESCR | FLTCHECK_79_REQDOCS | FLTCHECK_79_CODE | FLTCHECK_79_QUAL |
| 80 | FLTCHECK_80_DESCR | FLTCHECK_80_REQDOCS | FLTCHECK_80_CODE | FLTCHECK_80_QUAL |
| 81 | FLTCHECK_81_DESCR | FLTCHECK_81_REQDOCS | FLTCHECK_81_CODE | FLTCHECK_81_QUAL |
| 82 | FLTCHECK_82_DESCR | FLTCHECK_82_REQDOCS | FLTCHECK_82_CODE | FLTCHECK_82_QUAL |
| 83 | FLTCHECK_83_DESCR | FLTCHECK_83_REQDOCS | FLTCHECK_83_CODE | FLTCHECK_83_QUAL |
| 84 | FLTCHECK_84_DESCR | FLTCHECK_84_REQDOCS | FLTCHECK_84_CODE | FLTCHECK_84_QUAL |
| 85 | FLTCHECK_85_DESCR | FLTCHECK_85_REQDOCS | FLTCHECK_85_CODE | FLTCHECK_85_QUAL |
| 86 | FLTCHECK_86_DESCR | FLTCHECK_86_REQDOCS | FLTCHECK_86_CODE | FLTCHECK_86_QUAL |
| 87 | FLTCHECK_87_DESCR | FLTCHECK_87_REQDOCS | FLTCHECK_87_CODE | FLTCHECK_87_QUAL |
| 88 | FLTCHECK_88_DESCR | FLTCHECK_88_REQDOCS | FLTCHECK_88_CODE | FLTCHECK_88_QUAL |
| 89 | FLTCHECK_89_DESCR | FLTCHECK_89_REQDOCS | FLTCHECK_89_CODE | FLTCHECK_89_QUAL |
| 90 | FLTCHECK_90_DESCR | FLTCHECK_90_REQDOCS | FLTCHECK_90_CODE | FLTCHECK_90_QUAL |
| 91 | FLTCHECK_91_DESCR | FLTCHECK_91_REQDOCS | FLTCHECK_91_CODE | FLTCHECK_91_QUAL |
| 92 | FLTCHECK_92_DESCR | FLTCHECK_92_REQDOCS | FLTCHECK_92_CODE | FLTCHECK_92_QUAL |
| 93 | FLTCHECK_93_DESCR | FLTCHECK_93_REQDOCS | FLTCHECK_93_CODE | FLTCHECK_93_QUAL |
| 94 | FLTCHECK_94_DESCR | FLTCHECK_94_REQDOCS | FLTCHECK_94_CODE | FLTCHECK_94_QUAL |
| 95 | FLTCHECK_95_DESCR | FLTCHECK_95_REQDOCS | FLTCHECK_95_CODE | FLTCHECK_95_QUAL |
| 96 | FLTCHECK_96_DESCR | FLTCHECK_96_REQDOCS | FLTCHECK_96_CODE | FLTCHECK_96_QUAL |
| 97 | FLTCHECK_97_DESCR | FLTCHECK_97_REQDOCS | FLTCHECK_97_CODE | FLTCHECK_97_QUAL |
| 98 | FLTCHECK_98_DESCR | FLTCHECK_98_REQDOCS | FLTCHECK_98_CODE | FLTCHECK_98_QUAL |
| 99 | FLTCHECK_99_DESCR | FLTCHECK_99_REQDOCS | FLTCHECK_99_CODE | FLTCHECK_99_QUAL |
| 100 | FLTCHECK_100_DESCR | FLTCHECK_100_REQDOCS | FLTCHECK_100_CODE | FLTCHECK_100_QUAL |
| 101 | FLTCHECK_101_DESCR | FLTCHECK_101_REQDOCS | FLTCHECK_101_CODE | FLTCHECK_101_QUAL |
| 102 | FLTCHECK_102_DESCR | FLTCHECK_102_REQDOCS | FLTCHECK_102_CODE | FLTCHECK_102_QUAL |
| 103 | FLTCHECK_103_DESCR | FLTCHECK_103_REQDOCS | FLTCHECK_103_CODE | FLTCHECK_103_QUAL |
| 104 | FLTCHECK_104_DESCR | FLTCHECK_104_REQDOCS | FLTCHECK_104_CODE | FLTCHECK_104_QUAL |
| 105 | FLTCHECK_105_DESCR | FLTCHECK_105_REQDOCS | FLTCHECK_105_CODE | FLTCHECK_105_QUAL |
| 106 | FLTCHECK_106_DESCR | FLTCHECK_106_REQDOCS | FLTCHECK_106_CODE | FLTCHECK_106_QUAL |
| 107 | FLTCHECK_107_DESCR | FLTCHECK_107_REQDOCS | FLTCHECK_107_CODE | FLTCHECK_107_QUAL |
| 108 | FLTCHECK_108_DESCR | FLTCHECK_108_REQDOCS | FLTCHECK_108_CODE | FLTCHECK_108_QUAL |
| 109 | FLTCHECK_109_DESCR | FLTCHECK_109_REQDOCS | FLTCHECK_109_CODE | FLTCHECK_109_QUAL |
| 110 | FLTCHECK_110_DESCR | FLTCHECK_110_REQDOCS | FLTCHECK_110_CODE | FLTCHECK_110_QUAL |
| 111 | FLTCHECK_111_DESCR | FLTCHECK_111_REQDOCS | FLTCHECK_111_CODE | FLTCHECK_111_QUAL |
| 112 | FLTCHECK_112_DESCR | FLTCHECK_112_REQDOCS | FLTCHECK_112_CODE | FLTCHECK_112_QUAL |
| 113 | FLTCHECK_113_DESCR | FLTCHECK_113_REQDOCS | FLTCHECK_113_CODE | FLTCHECK_113_QUAL |
| 114 | FLTCHECK_114_DESCR | FLTCHECK_114_REQDOCS | FLTCHECK_114_CODE | FLTCHECK_114_QUAL |
| 115 | FLTCHECK_115_DESCR | FLTCHECK_115_REQDOCS | FLTCHECK_115_CODE | FLTCHECK_115_QUAL |
| 116 | FLTCHECK_116_DESCR | FLTCHECK_116_REQDOCS | FLTCHECK_116_CODE | FLTCHECK_116_QUAL |
| 117 | FLTCHECK_117_DESCR | FLTCHECK_117_REQDOCS | FLTCHECK_117_CODE | FLTCHECK_117_QUAL |
| 118 | FLTCHECK_118_DESCR | FLTCHECK_118_REQDOCS | FLTCHECK_118_CODE | FLTCHECK_118_QUAL |
| 119 | FLTCHECK_119_DESCR | FLTCHECK_119_REQDOCS | FLTCHECK_119_CODE | FLTCHECK_119_QUAL |
| 120 | FLTCHECK_120_DESCR | FLTCHECK_120_REQDOCS | FLTCHECK_120_CODE | FLTCHECK_120_QUAL |
| 121 | FLTCHECK_121_DESCR | FLTCHECK_121_REQDOCS | FLTCHECK_121_CODE | FLTCHECK_121_QUAL |
| 122 | FLTCHECK_122_DESCR | FLTCHECK_122_REQDOCS | FLTCHECK_122_CODE | FLTCHECK_122_QUAL |
| 123 | FLTCHECK_123_DESCR | FLTCHECK_123_REQDOCS | FLTCHECK_123_CODE | FLTCHECK_123_QUAL |
| 124 | FLTCHECK_124_DESCR | FLTCHECK_124_REQDOCS | FLTCHECK_124_CODE | FLTCHECK_124_QUAL |
| 125 | FLTCHECK_125_DESCR | FLTCHECK_125_REQDOCS | FLTCHECK_125_CODE | FLTCHECK_125_QUAL |
| 126 | FLTCHECK_126_DESCR | FLTCHECK_126_REQDOCS | FLTCHECK_126_CODE | FLTCHECK_126_QUAL |
| 127 | FLTCHECK_127_DESCR | FLTCHECK_127_REQDOCS | FLTCHECK_127_CODE | FLTCHECK_127_QUAL |

## 4. Keys & relationships
- No key. Treat as a constant lookup: `SELECT ... FROM TSC.dbo.vvFMSInfo1 WHERE RECDESC = 'CREWCODES2'`.
- **`FLTDUT_n` <-> `CREWQUAL.DATA_BEGIN_END`** (N:M through bit position, no join column): bit n (1-based) of the first 6 bytes of `CREWQUAL.DATA_BEGIN_END` is set when the qualification row carries capability n. Decode: byte `(n-1)/8 + 1`, mask `2^((n-1)%8)`. In R0 the mapping is materialised as table variable `@QualMap(ByteIdx, BitMask, DescText)` (`R0_GetDraftList.sql` lines 277-290) and applied with `(CONVERT(TINYINT, SUBSTRING(q.DATA_BEGIN_END, QM.ByteIdx, 1)) & QM.BitMask) > 0` (lines 459-468 and 521-526); `rpt.get_crew_qualifications` does the same with six parsed bytes `byte1..byte6` and 48 `SELECT @info_FLTDUT_n, byteN, mask UNION ALL` branches (lines 46-51, 68-120).
- `FLTCHECK_n_QUAL` bit k-1 <-> `FLTDUT_k` (check n may be conducted by holders of capability k) - inference.
- `FLTCHECKTRAINEE` byte n <-> `FLTCHECK_n_CODE` (lowercase variant) - verified for n = 1..21.
- Sibling views: `vvFMSCodes` (flight-service-type, aircraft-category codes etc., used by `rpt.Get_Detailed_Pairing`) is a different record of the same AIMS parameter family.

## 5. Encoding conventions & gotchas
- **One row only.** If the row is missing (`RECDESC` renamed) the procedures silently get NULL labels: R0's `@QualMap` would contain only NULLs and no instructor filter can match; `rpt.get_crew_qualifications` returns empty `Instructor_Qualifications`.
- **Labels are blank-padded `nchar(30)`** and are compared after `LTRIM(RTRIM())`. Callers must supply the **exact label text** (French/English mix, mixed case, e.g. `LINE CHECK DROIT`, `ENTRAINEUR SIMULATEUR`, `Formation Commandant`); `rpt.list_instructor_qualifications` returns the 48 labels (including 20 blanks) as columns, so the MCP layer has to drop blanks.
- The label order **is the bit order**: never sort or filter the labels before mapping to bits (R0 keeps `ByteIdx`/`BitMask` with each label).
- Only bits 1-28 are meaningful; bits 29-48 have blank labels and are never set in `CREWQUAL`.
- R0 stores labels in `VARCHAR(100)` variables: non-ASCII characters would be degraded (current labels are ASCII).
- The capability block is only 6 bytes of the 90-byte `DATA_BEGIN_END`; R0 guards with `DATALENGTH(q.DATA_BEGIN_END) >= QM.ByteIdx`.
- `FLTCHECK_n_QUAL` is a `bigint` bitmask over the 48 `FLTDUT_k` capabilities (values up to 2^23 observed): decode with `& POWER(CAST(2 AS bigint), k-1)`, not with `int` arithmetic.
- `FLTCHECK_*` and `GALEYCATEG`, `FLTCHECKTRAINEE`, `FUT180` are not read by any planner-assist procedure - do not rely on them for business rules without confirming semantics with AIMS administrators.

## 6. How the planner-assist procedures use it
- `dbo.R0_GetDraftList` (candidate list for a pairing): reads `FLTDUT_1..FLTDUT_48` into `@info_FLTDUT_n` (lines 261-275), builds `@QualMap`; then (a) filters the candidate pool by `@InstructorQualList` (comma-separated labels): a candidate qualifies if any of his `CREWQUAL.DATA_BEGIN_END` bits whose label is in the list is set (lines 459-468); (b) fills `Instructor_Qualifications` (` | `-separated labels of all set bits, ordered by byte/bit) in the output (lines 521-526). Business meaning: "find me check pilots / simulator trainers / line coaches" or show a candidate's instructor roles next to the draft ranking.
- `rpt.get_crew_qualifications` (per crew member): same decode for one crew member's open-ended qualification rows -> `Instructor_Qualifications`.
- `rpt.list_instructor_qualifications`: returns `FLTDUT_1..FLTDUT_48` of the `CREWCODES2` row so the client can offer the valid instructor-qualification names.
- No other procedure reads this view; `FLTCHECK_*` are never used.

## 7. Typical query patterns
```sql
-- labels of the instructor/check capabilities, one row per bit (unpivot the 28 defined labels; bit n = FLTDUT_n)
SELECT v.Bit_No, LTRIM(RTRIM(v.Label)) AS Label
FROM TSC.dbo.vvFMSInfo1 AS f
CROSS APPLY (VALUES (1, f.FLTDUT_1), (2, f.FLTDUT_2), (3, f.FLTDUT_3), (4, f.FLTDUT_4), (5, f.FLTDUT_5), (6, f.FLTDUT_6), (7, f.FLTDUT_7),
                    (8, f.FLTDUT_8), (9, f.FLTDUT_9), (10, f.FLTDUT_10), (11, f.FLTDUT_11), (12, f.FLTDUT_12), (13, f.FLTDUT_13),
                    (14, f.FLTDUT_14), (15, f.FLTDUT_15), (16, f.FLTDUT_16), (17, f.FLTDUT_17), (18, f.FLTDUT_18), (19, f.FLTDUT_19),
                    (20, f.FLTDUT_20), (21, f.FLTDUT_21), (22, f.FLTDUT_22), (23, f.FLTDUT_23), (24, f.FLTDUT_24), (25, f.FLTDUT_25),
                    (26, f.FLTDUT_26), (27, f.FLTDUT_27), (28, f.FLTDUT_28)) AS v(Bit_No, Label)
WHERE f.RECDESC = 'CREWCODES2' AND LTRIM(RTRIM(v.Label)) <> N''
ORDER BY v.Bit_No;

-- qualification rows valid today that carry the capability labelled 'LINE CHECK DROIT' (bit 3 = byte 1, mask 4) - count only
SELECT COUNT(*) AS Qual_Rows
FROM TSC.dbo.CREWQUAL AS q
WHERE (CONVERT(tinyint, SUBSTRING(q.DATA_BEGIN_END, 1, 1)) & 4) > 0
  AND DATEDIFF(DAY, '1980-01-01', GETDATE()) BETWEEN q.ACTIVBEG AND q.ACTIVEND;

-- generic: label -> (byte, mask) for any bit n, then count qualification rows holding the label
DECLARE @n INT = 9;   -- 9 = ENTRAINEUR SIMULATEUR
SELECT COUNT(*) AS Qual_Rows
FROM TSC.dbo.CREWQUAL AS q
WHERE (CONVERT(tinyint, SUBSTRING(q.DATA_BEGIN_END, (@n - 1) / 8 + 1, 1)) & POWER(2, (@n - 1) % 8)) > 0
  AND DATEDIFF(DAY, '1980-01-01', GETDATE()) BETWEEN q.ACTIVBEG AND q.ACTIVEND;
```

## 8. Data profile (measured 2026-11-03)
- 1 row; `RECDESC` = `CREWCODES2`.
- `FLTDUT_1..28` defined (A CHECK PILOT, B CHECK PILOT, LINE CHECK DROIT, LINE CHECK GAUCH, MECANICIEN VERIF, RC ETOPS CHECK, ENTRAINEUR PRLI, ENTRAINEUR SOP, ENTRAINEUR SIMULATEUR, ENTRAINEUR PERFORMANCE, ENTRAINEUR EPT, ENTRAINEUR PNT FORMATION SOL, CRM JET TRANSITION INITIAL B, PILOTE STANDARDISATEUR, TRAINING DEVELOPPER, REQUALIFICATION, EET, LINE INSPECTION, AIRCRAFT INSPECTION, ENTRAINEUR INITIAL, ENTRAINEUR FIRST AID, ENTRAINEUR ANNUELLE, ENTRAINEUR DV, LINE COACH PNC, INITIAL-B APS-MCC INSTRUCTEUR, JET TRANSITION INITIAL B, FD MEETING Leadership, Formation Commandant); `FLTDUT_29..48` blank.
- Number of `CREWQUAL` rows (all periods / valid today) per capability bit: see `CREWQUAL.md` section 3.2 (e.g. A CHECK PILOT 694/71, LINE CHECK DROIT 800/73, ENTRAINEUR SIMULATEUR 176/157, LINE COACH PNC 225/140).
- `FLTCHECK_1..21` populated (ROUTE CHECK R, LINE INDOC L, PICUS P, IFR I, SIM TRAINING S, TOUCH & GO T, FIRST FLIGHT LI FO F, ETOPS E, LIETOPS O, FAM FLIGHT X, R-RE TURN C, CONSOLIDATION D, MONITORING G, LI ETOPS TYPE RATED H, RC ETOPS TYPE RATED Q, coachings flights Z, Observation flight J, Progress Check A, Recommendation Flight W, Line Monitoring M, Final Assessment K); `FLTCHECK_22..127` empty; `REQDOCS` = 0 everywhere.
- `GALEYCATEG` (30 bytes) and `FUT180` (33 bytes): all zero. `FLTCHECKTRAINEE`: 21 lowercase letters then zeros.

## 9. Open questions / confidence
- High: structure; `FLTDUT_n` labels <-> `CREWQUAL.DATA_BEGIN_END` bits (taken directly from working procedures and verified: only bits 1-28 occur in data and exactly 28 labels are non-blank); single-row nature.
- Medium-high (inference verified against data): `FLTCHECK_n_QUAL` as a bitmask over the `FLTDUT_k` capabilities; `FLTCHECKTRAINEE` as lowercase code letters.
- Low / unknown: meaning of the "FMS" abbreviation, of `FLTCHECK_n_REQDOCS` (always 0), of `GALEYCATEG` (all zero; inferred from the name) and of `FUT180`.
- Open: nothing in the code distinguishes pilot from cabin-crew capabilities (R0 filters by label text only, e.g. 'ENTRAINEUR DV' and 'LINE COACH PNC' are cabin-crew roles, 'LINE CHECK DROIT' is a pilot role); the split is inferred from the label wording.
