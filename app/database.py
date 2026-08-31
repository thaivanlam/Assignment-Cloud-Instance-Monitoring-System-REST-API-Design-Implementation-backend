from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if IS_SQLITE else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


if IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):
        """Put every SQLite connection in WAL mode with a relaxed sync setting.

        SQLite's default rollback journal locks the *whole database file* for the
        duration of a write, so a monitoring scan recording an alert blocks every
        concurrent reader until its commit has fsynced. WAL lets readers carry on
        against the last committed snapshot while a writer works, and
        `synchronous=NORMAL` drops the fsync-per-commit that made the stall long.
        Both are per-connection settings, so they are set on connect rather than once.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
