from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Folder, Message
from app.schemas.mail import BulkMessageResponse, MessageStatsResponse, MessageUpdate


async def get_message_stats(db: AsyncSession) -> MessageStatsResponse:
  inbox_filter = Message.is_archived.is_(False)

  total_inbox = await db.scalar(select(func.count(Message.id)).where(inbox_filter))
  unread = await db.scalar(
    select(func.count(Message.id)).where(inbox_filter, Message.is_read.is_(False))
  )
  starred = await db.scalar(
    select(func.count(Message.id)).where(inbox_filter, Message.is_starred.is_(True))
  )
  archived = await db.scalar(
    select(func.count(Message.id)).where(Message.is_archived.is_(True))
  )

  return MessageStatsResponse(
    total_inbox=total_inbox or 0,
    unread=unread or 0,
    starred=starred or 0,
    archived=archived or 0,
  )


async def update_message_fields(
  db: AsyncSession,
  message: Message,
  payload: MessageUpdate,
) -> Message:
  if payload.is_read is not None:
    message.is_read = payload.is_read
  if payload.is_starred is not None:
    message.is_starred = payload.is_starred
  if payload.is_archived is not None:
    message.is_archived = payload.is_archived
  if payload.folder_id is not None:
    if payload.folder_id == 0:
      message.folder_id = None
    else:
      folder_exists = await db.execute(select(Folder).where(Folder.id == payload.folder_id))
      if not folder_exists.scalar_one_or_none():
        raise ValueError("Папка не найдена")
      message.folder_id = payload.folder_id

  await db.commit()
  await db.refresh(message)
  return message


async def mark_all_read(
  db: AsyncSession,
  *,
  folder_id: int | None = None,
  archived: bool = False,
) -> int:
  stmt = update(Message).where(Message.is_read.is_(False))
  if archived:
    stmt = stmt.where(Message.is_archived.is_(True))
  else:
    stmt = stmt.where(Message.is_archived.is_(False))
  if folder_id is not None:
    stmt = stmt.where(Message.folder_id == folder_id)

  stmt = stmt.values(is_read=True)
  result = await db.execute(stmt)
  await db.commit()
  return result.rowcount or 0


async def apply_bulk_action(
  db: AsyncSession,
  message_ids: list[int],
  action: str,
  folder_id: int | None = None,
) -> BulkMessageResponse:
  result = await db.execute(select(Message).where(Message.id.in_(message_ids)))
  messages = result.scalars().all()
  if not messages:
    return BulkMessageResponse(action=action, affected=0)

  if action == "move":
    if folder_id is None:
      raise ValueError("Для перемещения укажите folder_id")
    if folder_id == 0:
      target_folder_id = None
    else:
      folder_exists = await db.execute(select(Folder).where(Folder.id == folder_id))
      if not folder_exists.scalar_one_or_none():
        raise ValueError("Папка не найдена")
      target_folder_id = folder_id
    for message in messages:
      message.folder_id = target_folder_id
  elif action == "read":
    for message in messages:
      message.is_read = True
  elif action == "unread":
    for message in messages:
      message.is_read = False
  elif action == "star":
    for message in messages:
      message.is_starred = True
  elif action == "unstar":
    for message in messages:
      message.is_starred = False
  elif action == "archive":
    for message in messages:
      message.is_archived = True
  elif action == "unarchive":
    for message in messages:
      message.is_archived = False
  else:
    raise ValueError(f"Неизвестное действие: {action}")

  await db.commit()
  return BulkMessageResponse(action=action, affected=len(messages))
