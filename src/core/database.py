from sqlmodel import SQLModel, create_engine, Session
from src.core.config import settings
from src.models import Decision, Blacklist

engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG)


def init_db():
    """Initialize database tables."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Get database session."""
    with Session(engine) as session:
        yield session
