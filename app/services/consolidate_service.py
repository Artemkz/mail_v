import asyncio

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConsolidationRecord, MailboxAccount, Message
from app.schemas.mail import ConsolidateResponse
from app.services.imap_service import FetchedMessage, ImapClient
from app.services.organizer_service import organize_by_sender
from app.services.search_service import build_search_text


def _fetch_from_imap(mailbox: MailboxAccount, limit: int) -> list[FetchedMessage]:
  with ImapClient(
    host=mailbox.imap_host,
    port=mailbox.imap_port,
    username=mailbox.username,
    password=mailbox.password,
    use_ssl=mailbox.imap_ssl,
  ) as client:
    return client.fetch_messages(folder=mailbox.source_folder, limit=limit)


def _append_to_destination(
  destination: MailboxAccount,
  raw_rfc822: bytes,
) -> str:
  with ImapClient(
    host=destination.imap_host,
    port=destination.imap_port,
    username=destination.username,
    password=destination.password,
    use_ssl=destination.imap_ssl,
  ) as client:
    return client.append_message(folder=destination.source_folder, raw_rfc822=raw_rfc822)


async def _get_destination(
  db: AsyncSession,
  destination_id: int | None,
) -> MailboxAccount | None:
  if destination_id is not None:
    result = await db.execute(
      select(MailboxAccount).where(MailboxAccount.id == destination_id)
    )
    return result.scalar_one_or_none()

  result = await db.execute(
    select(MailboxAccount).where(
      MailboxAccount.is_consolidation_target.is_(True),
      MailboxAccount.is_active.is_(True),
    )
  )
  return result.scalar_one_or_none()


async def consolidate_to_one_mailbox(
  db: AsyncSession,
  destination_id: int | None = None,
  limit_per_mailbox: int = 100,
) -> ConsolidateResponse:
  destination = await _get_destination(db, destination_id)
  if not destination:
    raise ValueError(
      "Не выбран целевой ящик. Отметьте ящик как «сборник» или укажите destination_id."
    )
  if not destination.is_active:
    raise ValueError("Целевой ящик неактивен")

  sources_result = await db.execute(
    select(MailboxAccount).where(
      MailboxAccount.is_active.is_(True),
      MailboxAccount.id != destination.id,
    )
  )
  sources = sources_result.scalars().all()

  messages_copied = 0
  messages_skipped = 0
  sources_processed = 0
  errors: list[str] = []

  for source in sources:
    try:
      fetched = await asyncio.to_thread(_fetch_from_imap, source, limit_per_mailbox)
    except Exception as exc:
      errors.append(f"{source.email}: {exc}")
      continue

    sources_processed += 1

    for item in fetched:
      existing = await db.execute(
        select(ConsolidationRecord).where(
          ConsolidationRecord.source_mailbox_id == source.id,
          ConsolidationRecord.source_imap_uid == item.imap_uid,
        )
      )
      if existing.scalar_one_or_none():
        messages_skipped += 1
        continue

      try:
        dest_uid = await asyncio.to_thread(_append_to_destination, destination, item.raw_rfc822)
      except Exception as exc:
        errors.append(f"{source.email} UID {item.imap_uid}: {exc}")
        continue

      db.add(
        ConsolidationRecord(
          source_mailbox_id=source.id,
          source_imap_uid=item.imap_uid,
          destination_mailbox_id=destination.id,
          destination_imap_uid=dest_uid or None,
          message_id=item.message_id,
        )
      )

      dup_in_dest = await db.execute(
        select(Message).where(
          Message.mailbox_id == destination.id,
          Message.imap_uid == (dest_uid or item.imap_uid),
        )
      )
      if not dup_in_dest.scalar_one_or_none():
        db.add(
          Message(
            mailbox_id=destination.id,
            imap_uid=dest_uid or f"src-{source.id}-{item.imap_uid}",
            message_id=item.message_id,
            sender_email=item.sender_email,
            sender_name=item.sender_name,
            subject=item.subject,
            body_text=item.body_text,
            search_text=build_search_text(
              item.subject,
              item.body_text,
              item.sender_email,
              item.sender_name,
            ),
            received_at=item.received_at,
          )
        )

      await db.execute(
        delete(Message).where(
          Message.mailbox_id == source.id,
          Message.imap_uid == item.imap_uid,
        )
      )

      messages_copied += 1

  await db.commit()

  organizer_result = await organize_by_sender(db)

  return ConsolidateResponse(
    destination_mailbox_id=destination.id,
    destination_email=destination.email,
    sources_processed=sources_processed,
    messages_copied=messages_copied,
    messages_skipped=messages_skipped,
    folders_created=organizer_result.folders_created,
    messages_organized=organizer_result.messages_moved,
    errors=errors,
  )


async def set_consolidation_target(
  db: AsyncSession,
  mailbox_id: int,
) -> MailboxAccount:
  result = await db.execute(
    select(MailboxAccount).where(MailboxAccount.id == mailbox_id)
  )
  mailbox = result.scalar_one_or_none()
  if not mailbox:
    raise ValueError("Ящик не найден")

  all_mailboxes = await db.execute(select(MailboxAccount))
  for item in all_mailboxes.scalars().all():
    item.is_consolidation_target = item.id == mailbox_id

  await db.commit()
  await db.refresh(mailbox)
  return mailbox
