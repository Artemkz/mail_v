from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
  pass


engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
  async with async_session() as session:
    yield session


async def init_db() -> None:
  async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
    await conn.run_sync(_migrate_schema)


def _migrate_schema(connection) -> None:
  from sqlalchemy import inspect, text

  inspector = inspect(connection)
  if "mailbox_accounts" in inspector.get_table_names():
    columns = {column["name"] for column in inspector.get_columns("mailbox_accounts")}
    if "is_consolidation_target" not in columns:
      connection.execute(
        text(
          "ALTER TABLE mailbox_accounts "
          "ADD COLUMN is_consolidation_target BOOLEAN NOT NULL DEFAULT 0"
        )
      )

  if "messages" in inspector.get_table_names():
    columns = {column["name"] for column in inspector.get_columns("messages")}
    for column_name in ("is_read", "is_starred", "is_archived"):
      if column_name not in columns:
        connection.execute(
          text(f"ALTER TABLE messages ADD COLUMN {column_name} BOOLEAN NOT NULL DEFAULT 0")
        )
