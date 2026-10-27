from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import DateTime, Integer, String, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

UTC = timezone.utc


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    video_url: Mapped[str] = mapped_column(String(2048))
    webhook_url: Mapped[str] = mapped_column(String(2048))
    template: Mapped[str] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    output_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    process_attempts: Mapped[int] = mapped_column(Integer, default=0)
    webhook_status: Mapped[str] = mapped_column(String(32), default="pending")
    webhook_attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_webhook_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def sqlite_url(db_path: Path) -> str:
    return "sqlite:///" + db_path.resolve().as_posix()


def create_db_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        sqlite_url(db_path),
        future=True,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, future=True)
