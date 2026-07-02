from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class MailboxCreate(BaseModel):
  name: str = Field(..., min_length=1, max_length=255)
  email: EmailStr
  imap_host: str
  imap_port: int = 993
  imap_ssl: bool = True
  username: str
  password: str
  source_folder: str = "INBOX"


class MailboxResponse(BaseModel):
  id: int
  name: str
  email: EmailStr
  imap_host: str
  imap_port: int
  imap_ssl: bool
  source_folder: str
  is_active: bool
  created_at: datetime

  model_config = {"from_attributes": True}


class FolderResponse(BaseModel):
  id: int
  name: str
  sender_email: str | None
  is_system: bool
  message_count: int = 0
  created_at: datetime

  model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
  id: int
  mailbox_id: int
  folder_id: int | None
  sender_email: str
  sender_name: str | None
  subject: str
  body_text: str
  received_at: datetime

  model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
  query: str = Field(..., min_length=3, description="Поисковый запрос (минимум 3 символа)")
  folder_id: int | None = None


class SearchResponse(BaseModel):
  query: str
  prefix_length: int
  total: int
  messages: list[MessageResponse]


class CollectResponse(BaseModel):
  mailboxes_processed: int
  messages_fetched: int
  folders_created: int
  messages_organized: int


class OrganizerResponse(BaseModel):
  folders_created: int
  messages_moved: int
  senders_processed: int
