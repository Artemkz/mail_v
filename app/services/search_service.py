import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Message
from app.schemas.mail import MessageResponse


def _tokenize(text: str) -> list[str]:
  return re.findall(r"\w+", text.lower(), flags=re.UNICODE)


def build_search_text(
  subject: str,
  body_text: str,
  sender_email: str,
  sender_name: str | None,
) -> str:
  parts = [subject, body_text, sender_email]
  if sender_name:
    parts.append(sender_name)
  return " ".join(parts).lower()


def _message_matches_prefixes(search_text: str, prefixes: list[str]) -> bool:
  words = _tokenize(search_text)
  return all(
    any(word.startswith(prefix) for word in words)
    for prefix in prefixes
  )


async def search_messages(
  db: AsyncSession,
  query: str,
  folder_id: int | None = None,
  prefix_length: int | None = None,
) -> list[MessageResponse]:
  prefix_length = prefix_length or settings.search_prefix_length
  tokens = _tokenize(query)

  if not tokens:
    return []

  for token in tokens:
    if len(token) < prefix_length:
      raise ValueError(
        f"Каждое слово запроса должно содержать минимум {prefix_length} символа"
      )

  prefixes = [token[:prefix_length] for token in tokens]

  stmt = select(Message).order_by(Message.received_at.desc())
  if folder_id is not None:
    stmt = stmt.where(Message.folder_id == folder_id)

  result = await db.execute(stmt)
  matched = [
    message
    for message in result.scalars().all()
    if _message_matches_prefixes(message.search_text, prefixes)
  ]
  return [MessageResponse.model_validate(m) for m in matched]
