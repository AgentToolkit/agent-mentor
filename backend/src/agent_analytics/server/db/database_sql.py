import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path

def is_localhost():
    """Check if we're running on localhost based on DATABASE_URL or hostname"""
    if os.getenv('DATABASE_URL'):
        return 'localhost' in os.getenv('DATABASE_URL')
    return True  # Default to localhost if no DATABASE_URL is set

# Create SQLite database in a 'data' directory for local development
if is_localhost():
    data_dir = Path(__file__).parent / 'data'
    data_dir.mkdir(exist_ok=True)
    DATABASE_URL = f"sqlite:///{data_dir}/dev.db"
else:
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is required in production")

# Create engine with appropriate settings for SQLite vs Production
if is_localhost():
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}  # Needed for SQLite
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency for database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()