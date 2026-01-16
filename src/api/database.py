"""Database models and session management for job tracking."""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from typing import Optional
import json

Base = declarative_base()


class TaxonomyJob(Base):
    """Database model for tracking taxonomy jobs."""
    __tablename__ = "taxonomy_jobs"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(String, unique=True, index=True, nullable=False)
    filename = Column(String, nullable=False)
    status = Column(String, nullable=False, default="uploaded")
    column_mapping = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    error_message = Column(Text, nullable=True)


class MatchSession(Base):
    """Database model for tracking match sessions with validation state."""
    __tablename__ = "match_sessions"

    id = Column(Integer, primary_key=True, index=True)
    our_target_id = Column(String, nullable=False)
    client_target_id = Column(String, nullable=False)
    threshold = Column(String, nullable=True)
    results = Column(JSON, nullable=False)  # Store MatchResult list as JSON
    validation_states = Column(JSON, nullable=False, default={})  # {target_l3: 'pending'|'validated'|'rejected'}
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# SQLite database for job tracking (separate from main Postgres for vectors)
DATABASE_URL = "sqlite:///./taxonomy_jobs.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize the database tables."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
