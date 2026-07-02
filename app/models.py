from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MailboxAccount(Base):
  __tablename__ = "mailbox_accounts"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  name: Mapped[str] = mapped_column(String(255))
  email: Mapped[str] = mapped_column(String(255), unique=True)
  imap_host: Mapped[str] = mapped_column(String(255))
  imap_port: Mapped[int] = mapped_column(Integer, default=993)
  imap_ssl: Mapped[bool] = mapped_column(default=True)
  username: Mapped[str] = mapped_column(String(255))
  password: Mapped[str] = mapped_column(String(255))
  source_folder: Mapped[str] = mapped_column(String(255), default="INBOX")
  is_active: Mapped[bool] = mapped_column(default=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

  messages: Mapped[list["Message"]] = relationship(back_populates="mailbox")


class Folder(Base):
  __tablename__ = "folders"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  name: Mapped[str] = mapped_column(String(255), unique=True)
  sender_email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
  is_system: Mapped[bool] = mapped_column(default=False)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

  messages: Mapped[list["Message"]] = relationship(back_populates="folder")


class Message(Base):
  __tablename__ = "messages"
  __table_args__ = (
    UniqueConstraint("mailbox_id", "imap_uid", name="uq_mailbox_uid"),
    Index("ix_messages_sender", "sender_email"),
    Index("ix_messages_subject", "subject"),
    Index("ix_messages_body", "body_text"),
  )

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  mailbox_id: Mapped[int] = mapped_column(ForeignKey("mailbox_accounts.id"))
  folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id"), nullable=True)
  imap_uid: Mapped[str] = mapped_column(String(64))
  message_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
  sender_email: Mapped[str] = mapped_column(String(255))
  sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
  subject: Mapped[str] = mapped_column(String(1024), default="")
  body_text: Mapped[str] = mapped_column(Text, default="")
  search_text: Mapped[str] = mapped_column(Text, default="", index=True)
  received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

  mailbox: Mapped["MailboxAccount"] = relationship(back_populates="messages")
  folder: Mapped["Folder | None"] = relationship(back_populates="messages")
