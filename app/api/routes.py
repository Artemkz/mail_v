import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Folder, MailboxAccount, Message
from app.schemas.mail import (
  CollectResponse,
  FolderResponse,
  MailboxCreate,
  MailboxResponse,
  MessageResponse,
  OrganizerResponse,
  SearchRequest,
  SearchResponse,
)
from app.services.collector_service import collect_from_mailboxes
from app.services.organizer_service import organize_by_sender
from app.services.search_service import search_messages

router = APIRouter(prefix="/api", tags=["mail"])


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


@router.post("/collect", response_model=CollectResponse)
async def collect_mail(
  mailbox_id: int | None = Query(default=None, description="ID ящика или все активные"),
  limit: int = Query(default=100, ge=1, le=500),
  db: AsyncSession = Depends(get_db),
) -> CollectResponse:
  return await collect_from_mailboxes(db, mailbox_id=mailbox_id, limit_per_mailbox=limit)


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


@router.get("/messages", response_model=list[MessageResponse])
async def list_messages(
  folder_id: int | None = None,
  sender_email: str | None = None,
  limit: int = Query(default=50, ge=1, le=200),
  db: AsyncSession = Depends(get_db),
) -> list[MessageResponse]:
  stmt = select(Message).order_by(Message.received_at.desc()).limit(limit)
  if folder_id is not None:
    stmt = stmt.where(Message.folder_id == folder_id)
  if sender_email:
    stmt = stmt.where(Message.sender_email == sender_email.lower())

  result = await db.execute(stmt)
  return [MessageResponse.model_validate(m) for m in result.scalars().all()]


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
    select(Message)
    .where(Message.folder_id == folder_id)
    .order_by(Message.received_at.desc())
    .limit(limit)
  )
  return [MessageResponse.model_validate(m) for m in result.scalars().all()]
