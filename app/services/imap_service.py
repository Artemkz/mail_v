import email
import imaplib
import re
from dataclasses import dataclass
from datetime import datetime
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime


@dataclass
class FetchedMessage:
  imap_uid: str
  message_id: str | None
  sender_email: str
  sender_name: str | None
  subject: str
  body_text: str
  received_at: datetime


def _decode_mime_header(value: str | None) -> str:
  if not value:
    return ""
  parts: list[str] = []
  for chunk, charset in decode_header(value):
    if isinstance(chunk, bytes):
      parts.append(chunk.decode(charset or "utf-8", errors="replace"))
    else:
      parts.append(chunk)
  return "".join(parts)


def _extract_body(msg: email.message.Message) -> str:
  if msg.is_multipart():
    chunks: list[str] = []
    for part in msg.walk():
      content_type = part.get_content_type()
      disposition = str(part.get("Content-Disposition", ""))
      if content_type == "text/plain" and "attachment" not in disposition:
        payload = part.get_payload(decode=True)
        if payload:
          charset = part.get_content_charset() or "utf-8"
          chunks.append(payload.decode(charset, errors="replace"))
    return "\n".join(chunks)

  payload = msg.get_payload(decode=True)
  if not payload:
    return ""
  charset = msg.get_content_charset() or "utf-8"
  return payload.decode(charset, errors="replace")


def _parse_received_at(msg: email.message.Message) -> datetime:
  date_header = msg.get("Date")
  if not date_header:
    return datetime.utcnow()
  try:
    return parsedate_to_datetime(date_header).replace(tzinfo=None)
  except (TypeError, ValueError):
    return datetime.utcnow()


class ImapClient:
  def __init__(
    self,
    host: str,
    port: int,
    username: str,
    password: str,
    use_ssl: bool = True,
  ) -> None:
    self.host = host
    self.port = port
    self.username = username
    self.password = password
    self.use_ssl = use_ssl
    self._connection: imaplib.IMAP4_SSL | imaplib.IMAP4 | None = None

  def connect(self) -> None:
    if self.use_ssl:
      self._connection = imaplib.IMAP4_SSL(self.host, self.port)
    else:
      self._connection = imaplib.IMAP4(self.host, self.port)
    self._connection.login(self.username, self.password)

  def disconnect(self) -> None:
    if self._connection is not None:
      try:
        self._connection.logout()
      except Exception:
        pass
      self._connection = None

  def __enter__(self) -> "ImapClient":
    self.connect()
    return self

  def __exit__(self, exc_type, exc, tb) -> None:
    self.disconnect()

  def fetch_messages(self, folder: str = "INBOX", limit: int = 100) -> list[FetchedMessage]:
    if self._connection is None:
      raise RuntimeError("IMAP-соединение не установлено")

    status, _ = self._connection.select(folder, readonly=True)
    if status != "OK":
      raise RuntimeError(f"Не удалось открыть папку {folder}")

    status, data = self._connection.search(None, "ALL")
    if status != "OK" or not data or not data[0]:
      return []

    uids = data[0].split()
    selected_uids = uids[-limit:] if limit else uids
    result: list[FetchedMessage] = []

    for uid in selected_uids:
      status, msg_data = self._connection.fetch(uid, "(RFC822)")
      if status != "OK" or not msg_data:
        continue

      raw_email = msg_data[0][1]
      if not isinstance(raw_email, bytes):
        continue

      msg = email.message_from_bytes(raw_email)
      sender_name, sender_email = parseaddr(_decode_mime_header(msg.get("From")))
      sender_email = sender_email.lower().strip()
      if not sender_email:
        continue

      result.append(
        FetchedMessage(
          imap_uid=uid.decode() if isinstance(uid, bytes) else str(uid),
          message_id=msg.get("Message-ID"),
          sender_email=sender_email,
          sender_name=sender_name or None,
          subject=_decode_mime_header(msg.get("Subject")),
          body_text=_extract_body(msg),
          received_at=_parse_received_at(msg),
        )
      )

    return result


def sanitize_folder_name(sender_email: str) -> str:
  local_part = sender_email.split("@", 1)[0]
  safe = re.sub(r"[^\w.\-]+", "_", local_part, flags=re.UNICODE)
  return f"Отправитель_{safe}"[:200]
