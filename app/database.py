import os
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base


def get_database_url() -> str:
    """Return the database URL.

    1. On Azure: use the DATABASE_URL environment variable.
    2. On your computer: build it from the values in your .env file.
    The driver is always psycopg (version 3), which is what requirements.txt installs.
    """
    url = os.getenv("DATABASE_URL")
    if url:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    from .config import settings
    return URL.create(
        drivername="postgresql+psycopg",
        username=settings.database_username,
        password=settings.database_password,
        host=settings.database_hostname,
        port=int(settings.database_port),
        database=settings.database_name,
    ).render_as_string(hide_password=False)


DATABASE_URL = get_database_url()

# pool_pre_ping avoids "connection closed" errors after Azure idles a connection
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
