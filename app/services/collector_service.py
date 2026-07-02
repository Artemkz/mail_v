from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MailboxAccount, Message
from app.schemas.mail import CollectResponse
from app.services.imap_service import ImapClient
from app.services.organizer_service import organize_by_sender
from app.services.search_service import build_search_text


async def collect_from_mailboxes(
  db: AsyncSession,
  mailbox_id: int | None = None,
  limit_per_mailbox: int = 100,
) -> CollectResponse:
  stmt = select(MailboxAccount).where(MailboxAccount.is_active.is_(True))
  if mailbox_id is not None:
    stmt = stmt.where(MailboxAccount.id == mailbox_id)

  result = await db.execute(stmt)
  mailboxes = result.scalars().all()

  messages_fetched = 0
  mailboxes_processed = 0

  for mailbox in mailboxes:
    try:
      fetched = _fetch_from_imap(mailbox, limit_per_mailbox)
    except Exception as exc:
      print(f"Ошибка сбора с {mailbox.email}: {exc}")
      continue

    mailboxes_processed += 1
    for item in fetched:
      existing = await db.execute(
        select(Message).where(
          Message.mailbox_id == mailbox.id,
          Message.imap_uid == item.imap_uid,
        )
      )
      if existing.scalar_one_or_none():
        continue

      db.add(
        Message(
          mailbox_id=mailbox.id,
          imap_uid=item.imap_uid,
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
      messages_fetched += 1

  await db.commit()

  organizer_result = await organize_by_sender(db)

  return CollectResponse(
    mailboxes_processed=mailboxes_processed,
    messages_fetched=messages_fetched,
    folders_created=organizer_result.folders_created,
    messages_organized=organizer_result.messages_moved,
  )


def _fetch_from_imap(mailbox: MailboxAccount, limit: int):
  with ImapClient(
    host=mailbox.imap_host,
    port=mailbox.imap_port,
    username=mailbox.username,
    password=mailbox.password,
    use_ssl=mailbox.imap_ssl,
  ) as client:
    return client.fetch_messages(folder=mailbox.source_folder, limit=limit)
