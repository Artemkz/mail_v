import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_username
from app.database import get_db
from app.models import Folder, MailboxAccount, Message
from app.schemas.mail import (
  BulkMessageAction,
  BulkMessageResponse,
  CollectResponse,
  ConsolidateResponse,
  DeleteResponse,
  FolderResponse,
  MailboxCreate,
  MailboxResponse,
  MailboxUpdate,
  MarkAllReadResponse,
  MessageResponse,
  MessageStatsResponse,
  MessageUpdate,
  OrganizerResponse,
  SearchRequest,
  SearchResponse,
)
from app.services.collector_service import collect_from_mailboxes
from app.services.consolidate_service import consolidate_to_one_mailbox, set_consolidation_target
from app.services.delete_service import delete_message_on_server
from app.services.message_service import (
  apply_bulk_action,
  get_message_stats,
  mark_all_read,
  update_message_fields,
)
from app.services.organizer_service import organize_by_sender
from app.services.search_service import search_messages

router = APIRouter(
  prefix="/api",
  tags=["mail"],
  dependencies=[Depends(get_current_username)],
)


def _message_response(message: Message, mailbox_email: str | None = None) -> MessageResponse:
  item = MessageResponse.model_validate(message)
  item.mailbox_email = mailbox_email
  return item


@router.post("/mailboxes", response_model=MailboxResponse, status_code=201)
async def create_mailbox(
  payload: MailboxCreate,
  db: AsyncSession = Depends(get_db),
) -> MailboxResponse:
  existing = await db.execute(
    select(MailboxAccount).where(MailboxAccount.email == payload.email)
  )
  if existing.scalar_one_or_none():
    raise HTTPException(status_code=409, detail="Ящик с таким email уже существует")

  mailbox = MailboxAccount(**payload.model_dump())
  db.add(mailbox)
  await db.commit()
  await db.refresh(mailbox)
  return MailboxResponse.model_validate(mailbox)


@router.get("/mailboxes", response_model=list[MailboxResponse])
async def list_mailboxes(db: AsyncSession = Depends(get_db)) -> list[MailboxResponse]:
  result = await db.execute(select(MailboxAccount).order_by(MailboxAccount.id))
  return [MailboxResponse.model_validate(m) for m in result.scalars().all()]


@router.get("/mailboxes/{mailbox_id}", response_model=MailboxResponse)
async def get_mailbox(
  mailbox_id: int,
  db: AsyncSession = Depends(get_db),
) -> MailboxResponse:
  result = await db.execute(
    select(MailboxAccount).where(MailboxAccount.id == mailbox_id)
  )
  mailbox = result.scalar_one_or_none()
  if not mailbox:
    raise HTTPException(status_code=404, detail="Ящик не найден")
  return MailboxResponse.model_validate(mailbox)


@router.patch("/mailboxes/{mailbox_id}", response_model=MailboxResponse)
async def update_mailbox(
  mailbox_id: int,
  payload: MailboxUpdate,
  db: AsyncSession = Depends(get_db),
) -> MailboxResponse:
  result = await db.execute(
    select(MailboxAccount).where(MailboxAccount.id == mailbox_id)
  )
  mailbox = result.scalar_one_or_none()
  if not mailbox:
    raise HTTPException(status_code=404, detail="Ящик не найден")

  if payload.email != mailbox.email:
    existing = await db.execute(
      select(MailboxAccount).where(MailboxAccount.email == payload.email)
    )
    if existing.scalar_one_or_none():
      raise HTTPException(status_code=409, detail="Ящик с таким email уже существует")

  mailbox.name = payload.name
  mailbox.email = payload.email
  mailbox.imap_host = payload.imap_host
  mailbox.imap_port = payload.imap_port
  mailbox.imap_ssl = payload.imap_ssl
  mailbox.username = payload.username
  mailbox.source_folder = payload.source_folder
  mailbox.is_active = payload.is_active
  if payload.password:
    mailbox.password = payload.password

  await db.commit()
  await db.refresh(mailbox)
  return MailboxResponse.model_validate(mailbox)


@router.delete("/mailboxes/{mailbox_id}", response_model=DeleteResponse)
async def delete_mailbox(
  mailbox_id: int,
  db: AsyncSession = Depends(get_db),
) -> DeleteResponse:
  result = await db.execute(
    select(MailboxAccount).where(MailboxAccount.id == mailbox_id)
  )
  mailbox = result.scalar_one_or_none()
  if not mailbox:
    raise HTTPException(status_code=404, detail="Ящик не найден")

  messages_result = await db.execute(
    delete(Message).where(Message.mailbox_id == mailbox_id)
  )
  deleted_messages = messages_result.rowcount

  await db.delete(mailbox)
  await db.commit()

  return DeleteResponse(
    deleted=True,
    id=mailbox_id,
    detail=f"Ящик удалён, писем удалено: {deleted_messages}",
  )


@router.post("/collect", response_model=CollectResponse)
async def collect_mail(
  mailbox_id: int | None = Query(default=None, description="ID ящика или все активные"),
  limit: int = Query(default=100, ge=1, le=500),
  db: AsyncSession = Depends(get_db),
) -> CollectResponse:
  return await collect_from_mailboxes(db, mailbox_id=mailbox_id, limit_per_mailbox=limit)


@router.post("/consolidate", response_model=ConsolidateResponse)
async def consolidate_mail(
  destination_id: int | None = Query(
    default=None,
    description="ID целевого ящика или ящик с флагом is_consolidation_target",
  ),
  limit: int = Query(default=100, ge=1, le=500),
  db: AsyncSession = Depends(get_db),
) -> ConsolidateResponse:
  try:
    return await consolidate_to_one_mailbox(
      db,
      destination_id=destination_id,
      limit_per_mailbox=limit,
    )
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/mailboxes/{mailbox_id}/consolidation-target", response_model=MailboxResponse)
async def mark_consolidation_target(
  mailbox_id: int,
  db: AsyncSession = Depends(get_db),
) -> MailboxResponse:
  try:
    mailbox = await set_consolidation_target(db, mailbox_id)
  except ValueError as exc:
    raise HTTPException(status_code=404, detail=str(exc)) from exc
  return MailboxResponse.model_validate(mailbox)


@router.post("/organize", response_model=OrganizerResponse)
async def organize_mail(db: AsyncSession = Depends(get_db)) -> OrganizerResponse:
  return await organize_by_sender(db)


@router.post("/search", response_model=SearchResponse)
async def search_mail(
  payload: SearchRequest,
  db: AsyncSession = Depends(get_db),
) -> SearchResponse:
  from app.config import settings

  try:
    messages = await search_messages(db, payload.query, folder_id=payload.folder_id)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc

  return SearchResponse(
    query=payload.query,
    prefix_length=settings.search_prefix_length,
    total=len(messages),
    messages=messages,
  )


@router.get("/messages/stats", response_model=MessageStatsResponse)
async def message_stats(db: AsyncSession = Depends(get_db)) -> MessageStatsResponse:
  return await get_message_stats(db)


@router.get("/messages", response_model=list[MessageResponse])
async def list_messages(
  folder_id: int | None = None,
  sender_email: str | None = None,
  filter: str | None = Query(
    default="inbox",
    description="inbox, unread, starred, archived, all",
  ),
  limit: int = Query(default=50, ge=1, le=200),
  db: AsyncSession = Depends(get_db),
) -> list[MessageResponse]:
  stmt = (
    select(Message, MailboxAccount.email)
    .join(MailboxAccount, Message.mailbox_id == MailboxAccount.id)
    .order_by(Message.received_at.desc())
    .limit(limit)
  )
  if folder_id is not None:
    stmt = stmt.where(Message.folder_id == folder_id)
  if sender_email:
    stmt = stmt.where(Message.sender_email == sender_email.lower())

  if filter == "unread":
    stmt = stmt.where(Message.is_archived.is_(False), Message.is_read.is_(False))
  elif filter == "starred":
    stmt = stmt.where(Message.is_archived.is_(False), Message.is_starred.is_(True))
  elif filter == "archived":
    stmt = stmt.where(Message.is_archived.is_(True))
  elif filter == "all":
    pass
  else:
    stmt = stmt.where(Message.is_archived.is_(False))

  result = await db.execute(stmt)
  return [_message_response(msg, mailbox_email) for msg, mailbox_email in result.all()]


@router.get("/messages/{message_id}", response_model=MessageResponse)
async def get_message(
  message_id: int,
  db: AsyncSession = Depends(get_db),
) -> MessageResponse:
  result = await db.execute(
    select(Message, MailboxAccount.email)
    .join(MailboxAccount, Message.mailbox_id == MailboxAccount.id)
    .where(Message.id == message_id)
  )
  row = result.one_or_none()
  if not row:
    raise HTTPException(status_code=404, detail="Письмо не найдено")
  message, mailbox_email = row
  return _message_response(message, mailbox_email)


@router.patch("/messages/{message_id}", response_model=MessageResponse)
async def patch_message(
  message_id: int,
  payload: MessageUpdate,
  db: AsyncSession = Depends(get_db),
) -> MessageResponse:
  result = await db.execute(
    select(Message, MailboxAccount.email)
    .join(MailboxAccount, Message.mailbox_id == MailboxAccount.id)
    .where(Message.id == message_id)
  )
  row = result.one_or_none()
  if not row:
    raise HTTPException(status_code=404, detail="Письмо не найдено")
  message, mailbox_email = row

  try:
    message = await update_message_fields(db, message, payload)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc

  return _message_response(message, mailbox_email)


@router.post("/messages/bulk", response_model=BulkMessageResponse)
async def bulk_messages(
  payload: BulkMessageAction,
  db: AsyncSession = Depends(get_db),
) -> BulkMessageResponse:
  try:
    return await apply_bulk_action(
      db,
      payload.message_ids,
      payload.action,
      folder_id=payload.folder_id,
    )
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/messages/mark-all-read", response_model=MarkAllReadResponse)
async def mark_messages_all_read(
  folder_id: int | None = None,
  archived: bool = Query(default=False),
  db: AsyncSession = Depends(get_db),
) -> MarkAllReadResponse:
  marked = await mark_all_read(db, folder_id=folder_id, archived=archived)
  return MarkAllReadResponse(marked=marked)


@router.delete("/messages/{message_id}", response_model=DeleteResponse)
async def delete_message(
  message_id: int,
  db: AsyncSession = Depends(get_db),
) -> DeleteResponse:
  result = await db.execute(select(Message).where(Message.id == message_id))
  message = result.scalar_one_or_none()
  if not message:
    raise HTTPException(status_code=404, detail="Письмо не найдено")

  mailbox_result = await db.execute(
    select(MailboxAccount).where(MailboxAccount.id == message.mailbox_id)
  )
  mailbox = mailbox_result.scalar_one_or_none()
  if not mailbox:
    raise HTTPException(status_code=404, detail="Ящик письма не найден")

  try:
    await delete_message_on_server(message, mailbox)
  except Exception as exc:
    raise HTTPException(
      status_code=502,
      detail=f"Не удалось удалить письмо на почтовом сервере: {exc}",
    ) from exc

  await db.delete(message)
  await db.commit()

  return DeleteResponse(
    deleted=True,
    id=message_id,
    detail="Письмо удалено из приложения и с почтового сервера",
  )


@router.get("/folders", response_model=list[FolderResponse])
async def list_folders(db: AsyncSession = Depends(get_db)) -> list[FolderResponse]:
  result = await db.execute(select(Folder).order_by(Folder.name))
  folders = result.scalars().all()

  response: list[FolderResponse] = []
  for folder in folders:
    count_result = await db.execute(
      select(func.count(Message.id)).where(Message.folder_id == folder.id)
    )
    count = count_result.scalar_one()
    item = FolderResponse.model_validate(folder)
    item.message_count = count
    response.append(item)
  return response


@router.get("/folders/{folder_id}/messages", response_model=list[MessageResponse])
async def folder_messages(
  folder_id: int,
  limit: int = Query(default=50, ge=1, le=200),
  db: AsyncSession = Depends(get_db),
) -> list[MessageResponse]:
  folder_exists = await db.execute(select(Folder).where(Folder.id == folder_id))
  if not folder_exists.scalar_one_or_none():
    raise HTTPException(status_code=404, detail="Папка не найдена")

  result = await db.execute(
    select(Message, MailboxAccount.email)
    .join(MailboxAccount, Message.mailbox_id == MailboxAccount.id)
    .where(Message.folder_id == folder_id)
    .order_by(Message.received_at.desc())
    .limit(limit)
  )
  return [_message_response(msg, mailbox_email) for msg, mailbox_email in result.all()]
