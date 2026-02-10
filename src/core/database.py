from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool
from src.core.config import settings

# Configure engine for SQLite
connect_args = {"check_same_thread": False}

# Check if using in-memory database
_is_memory = settings.DB_PATH == ":memory:" or settings.DB_PATH == ""

if _is_memory:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args=connect_args,
        poolclass=StaticPool,
        echo=settings.DEBUG
    )
else:
    # Ensure data directory exists before creating engine
    db_path = Path(settings.DB_PATH)
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError):
        # If we can't create the directory (e.g., during tests), continue anyway
        # The engine will fail later if the directory is actually needed
        pass
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args=connect_args,
        echo=settings.DEBUG
    )


def init_db():
    """Initialize database tables."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Get database session."""
    with Session(engine) as session:
        yield session
