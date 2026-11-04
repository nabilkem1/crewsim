-- =============================================================================
-- PROPOSED DDL - NOT EXECUTED.  Database: CrewSchedAI   Schema: sim  (new; do not use dbo)
-- Decision 2026-11-03: the crew pseudonym map (Pierre's v3 key, option A) is HOSTED inside CrewSchedAI (option C),
-- so extraction SQL (kept in the CrewSim repo, option a) joins to it and CrewSim never receives a raw AIMS crew id.
-- Review with the DBA, then run in QAS first.  Idempotent.
-- =============================================================================
IF SCHEMA_ID('sim') IS NULL EXEC('CREATE SCHEMA sim AUTHORIZATION dbo');
GO

-- ---------------------------------------------------------------------------
-- sim.crew_key_map : AIMS crew id -> pseudonym used in every CrewSim file (v3 P###### key).  SENSITIVE.
-- Loaded once from Pierre's h01_crew_key_map.csv (pilots AND cabin crew: cabin-ready by design).
-- ---------------------------------------------------------------------------
IF OBJECT_ID('sim.crew_key_map', 'U') IS NULL
CREATE TABLE sim.crew_key_map (
    aims_crew_id  INT          NOT NULL,                 -- TSC.dbo.ROSTER.ID / ROSTERID.ID
    crew_id       VARCHAR(12)  NOT NULL,                 -- 'P000123'
    crew_group    VARCHAR(5)   NULL,                     -- PILOT | CABIN (filled from position at load time, optional)
    source_batch  VARCHAR(60)  NOT NULL,                 -- e.g. 'h01_crew_key_map_20261110.csv'
    loaded_at     DATETIME2(0) NOT NULL CONSTRAINT DF_sim_crew_key_map_loaded DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_sim_crew_key_map PRIMARY KEY CLUSTERED (aims_crew_id),
    CONSTRAINT UQ_sim_crew_key_map_crew_id UNIQUE (crew_id),
    CONSTRAINT CK_sim_crew_key_map_fmt CHECK (crew_id LIKE 'P%' AND (crew_group IS NULL OR crew_group IN ('PILOT', 'CABIN')))
);
GO

-- ---------------------------------------------------------------------------
-- sim.activity_code_map : M01 (classification of TSC.dbo.CRCODES), versioned by validity dates.
-- ---------------------------------------------------------------------------
IF OBJECT_ID('sim.activity_code_map', 'U') IS NULL
CREATE TABLE sim.activity_code_map (
    aims_code_id          INT          NOT NULL,         -- CRCODES.ID (<= 0)
    crew_code             VARCHAR(8)   NOT NULL,         -- CRCODES.CC
    description           NVARCHAR(100) NOT NULL,
    block_type            VARCHAR(12)  NOT NULL,         -- PAIRING DAY_OFF VACATION RESERVE TRAINING SIMULATOR ABSENCE OFFICE OTHER REST
    absence_type          VARCHAR(12)  NULL,             -- SICK FAMILY INJURY LONG_TERM PARENTAL OTHER
    session_type          VARCHAR(16)  NULL,             -- SIM GROUND PPC CRM RECURRENT INITIAL_GROUND EXAM OTHER
    reserve_call_type     CHAR(2)      NULL,             -- SC | LC
    counts_as_unavailable BIT          NOT NULL,
    valid_from            DATE         NOT NULL CONSTRAINT DF_sim_acm_from DEFAULT '1999-01-01',
    valid_to              DATE         NULL,
    validated_by          VARCHAR(60)  NULL,             -- department, not a person
    comment               NVARCHAR(200) NULL,
    CONSTRAINT PK_sim_activity_code_map PRIMARY KEY CLUSTERED (aims_code_id, valid_from)
);
GO

-- ---------------------------------------------------------------------------
-- sim.user_group_map : M02 (AIMS user / program -> organisational group, for D6 initiator).
-- ---------------------------------------------------------------------------
IF OBJECT_ID('sim.user_group_map', 'U') IS NULL
CREATE TABLE sim.user_group_map (
    kind                  VARCHAR(7)   NOT NULL,         -- USER | PROGRAM
    aims_user_or_program  VARCHAR(40)  NOT NULL,         -- LOG_ROSTER.AIMSUSER / EXTERNALAPPL
    group_name            VARCHAR(20)  NOT NULL,         -- IOC CREW_CONTROL CREW_PLANNING CREW_SELF_SERVICE SYSTEM_AUTOMATIC OTHER
    active_from           DATE         NOT NULL CONSTRAINT DF_sim_ugm_from DEFAULT '1999-01-01',
    active_to             DATE         NULL,
    CONSTRAINT PK_sim_user_group_map PRIMARY KEY CLUSTERED (kind, aims_user_or_program, active_from)
);
GO

-- ---------------------------------------------------------------------------
-- sim.aircraft_subfleet : H03 (registration -> sub-fleet, e.g. A321neoLR).
-- ---------------------------------------------------------------------------
IF OBJECT_ID('sim.aircraft_subfleet', 'U') IS NULL
CREATE TABLE sim.aircraft_subfleet (
    registration     VARCHAR(10) NOT NULL,               -- AIRCRAFT.REG / LEGMAIN.REG
    aims_ac_type     VARCHAR(5)  NOT NULL,               -- AIRCTYPE.IATACODE (321, 32Q, ...)
    subfleet         VARCHAR(20) NOT NULL,
    in_service_from  DATE        NOT NULL,
    in_service_to    DATE        NULL,
    long_range_tank  BIT         NULL,
    CONSTRAINT PK_sim_aircraft_subfleet PRIMARY KEY CLUSTERED (registration, in_service_from)
);
GO

-- ---------------------------------------------------------------------------
-- Least privilege: a role the CrewSim service account joins.  No access to the key map for anybody else.
-- NOTE: database chaining is OFF on TSC and CrewSchedAI, so the role also needs explicit SELECT on the TSC objects
-- the extraction reads (granted in TSC, listed in the extraction SQL header), not blanket db_datareader.
-- ---------------------------------------------------------------------------
IF DATABASE_PRINCIPAL_ID('sim_extract_reader') IS NULL CREATE ROLE sim_extract_reader;
GRANT SELECT ON SCHEMA::sim TO sim_extract_reader;
DENY  INSERT, UPDATE, DELETE ON SCHEMA::sim TO sim_extract_reader;
-- ALTER ROLE sim_extract_reader ADD MEMBER [<service account>];   -- when the account exists
GO

