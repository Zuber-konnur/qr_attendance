import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from app.config import Config, BASE_DIR

logger = logging.getLogger(__name__)

engine_args = Config.SQLALCHEMY_ENGINE_OPTIONS.copy()
db_url = Config.DATABASE_URL

if db_url.startswith("sqlite"):
    engine_args["connect_args"] = {"check_same_thread": False}
    # If relative sqlite path, ensure it resolves to project root
    if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////") and not (len(db_url) > 11 and db_url[10] == ":"):
        sqlite_file = db_url.replace("sqlite:///", "")
        if not os.path.isabs(sqlite_file):
            abs_db_path = os.path.join(BASE_DIR, sqlite_file).replace("\\", "/")
            db_url = f"sqlite:///{abs_db_path}"

try:
    engine = create_engine(db_url, **engine_args)
except Exception as e:
    logger.error(f"Failed to create database engine for {db_url}: {e}")
    fallback_path = os.path.join(BASE_DIR, "attendance.db").replace("\\", "/")
    logger.info(f"Falling back to local SQLite database: sqlite:///{fallback_path}")
    engine = create_engine(f"sqlite:///{fallback_path}", connect_args={"check_same_thread": False})

db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

def init_db():
    import app.models  # Ensure models are imported so tables are created
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully.")

def get_db_info():
    """Return friendly name and dialect of the active database."""
    dialect_name = engine.dialect.name
    if "sqlite" in dialect_name:
        return {"type": "SQLite", "badge": "bg-secondary", "url": "Local SQLite Database"}
    elif "postgres" in dialect_name:
        return {"type": "PostgreSQL", "badge": "bg-primary", "url": f"{engine.url.host or 'Remote'}/{engine.url.database or ''}"}
    elif "mysql" in dialect_name:
        return {"type": "MySQL", "badge": "bg-warning text-dark", "url": f"{engine.url.host or 'Remote'}/{engine.url.database or ''}"}
    return {"type": dialect_name.capitalize(), "badge": "bg-info", "url": str(engine.url)}
