import asyncio

from app.models import MailboxAccount, Message
from app.services.imap_service import ImapClient


def _delete_on_imap(mailbox: MailboxAccount, imap_uid: str) -> None:
  with ImapClient(
    host=mailbox.imap_host,
    port=mailbox.imap_port,
    username=mailbox.username,
    password=mailbox.password,
    use_ssl=mailbox.imap_ssl,
  ) as client:
    client.delete_message(folder=mailbox.source_folder, imap_uid=imap_uid)


async def delete_message_on_server(message: Message, mailbox: MailboxAccount) -> None:
  await asyncio.to_thread(_delete_on_imap, mailbox, message.imap_uid)
