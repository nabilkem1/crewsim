from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class Job(Base):
    """Async background jobs for long-running simulation/calibration tasks."""
    __tablename__ = "jobs"
    
    id = Column(String, primary_key=True)
    type = Column(String)  # 'simulation', 'calibration'
    status = Column(String)  # 'queued', 'running', 'completed', 'failed', 'cancelled'
    progress = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    error_message = Column(String, nullable=True)
    results = Column(JSON, nullable=True)
    diagnostics = Column(JSON, nullable=True)

class Run(Base):
    """Historical simulation runs."""
    __tablename__ = "runs"
    
    id = Column(String, primary_key=True)  # Usually UUID
    job_id = Column(String, ForeignKey("jobs.id"), nullable=True)
    config_hash = Column(String)  # blake2b hash of the configuration
    status = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    results_url = Column(String, nullable=True)  # Path to generated artifacts
    metrics = Column(JSON, nullable=True)  # High-level KPIs (cost, etc.)

class AuditLog(Base):
    """System audit log for tracking actions."""
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    actor = Column(String)
    action = Column(String)
    entity_type = Column(String)
    entity_id = Column(String)
    details = Column(JSON, nullable=True)

# SQLite setup for local MVP
DATABASE_URL = "sqlite:///./crewsim_metadata.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
