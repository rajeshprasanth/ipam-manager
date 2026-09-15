"""SQLAlchemy engine and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


_engine_kwargs: dict = {"pool_pre_ping": True}

if settings.DATABASE_URL.startswith("sqlite"):
    from sqlalchemy.pool import StaticPool

    _engine_kwargs.update(
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
else:
    _engine_kwargs.update(pool_size=10, max_overflow=20)

engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()