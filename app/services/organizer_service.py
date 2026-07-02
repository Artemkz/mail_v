from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Folder, Message
from app.schemas.mail import OrganizerResponse
from app.services.imap_service import sanitize_folder_name


async def organize_by_sender(db: AsyncSession) -> OrganizerResponse:
  """
  Для каждого отправителя с более чем одним письмом:
  - создаёт папку (если ещё нет)
  - перемещает все его письма в эту папку
  """
  sender_counts = await db.execute(
    select(Message.sender_email, func.count(Message.id))
    .group_by(Message.sender_email)
    .having(func.count(Message.id) > 1)
  )
  senders = sender_counts.all()

  folders_created = 0
  messages_moved = 0

  for sender_email, _ in senders:
    existing = await db.execute(
      select(Folder).where(Folder.sender_email == sender_email)
    )
    folder_existed = existing.scalar_one_or_none() is not None

    folder = await _get_or_create_sender_folder(db, sender_email)
    if folder is None:
      continue

    if not folder_existed:
      folders_created += 1

    result = await db.execute(
      select(Message).where(
        Message.sender_email == sender_email,
        (Message.folder_id.is_(None)) | (Message.folder_id != folder.id),
      )
    )
    for message in result.scalars().all():
      message.folder_id = folder.id
      messages_moved += 1

  await db.commit()

  return OrganizerResponse(
    folders_created=folders_created,
    messages_moved=messages_moved,
    senders_processed=len(senders),
  )


async def _get_or_create_sender_folder(
  db: AsyncSession, sender_email: str
) -> Folder | None:
  result = await db.execute(
    select(Folder).where(Folder.sender_email == sender_email)
  )
  folder = result.scalar_one_or_none()
  if folder:
    return folder

  folder_name = sanitize_folder_name(sender_email)
  existing_by_name = await db.execute(
    select(Folder).where(Folder.name == folder_name)
  )
  if existing_by_name.scalar_one_or_none():
    domain = sender_email.split("@", 1)[1].replace(".", "_")
    folder_name = f"{folder_name}_{domain}"

  folder = Folder(
    name=folder_name,
    sender_email=sender_email,
    is_system=False,
  )
  db.add(folder)
  await db.flush()
  return folder
