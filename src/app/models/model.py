import enum
from datetime import datetime
from typing import List

from sqlalchemy import (
    BIGINT,
    TIMESTAMP,
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database.db_handler import Base


class BroadcastStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BroadcastContactStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"


class ToolType(str, enum.Enum):
    KNOWLEDGE = "knowledge"
    API_REQUEST = "api_request"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)
    api_key: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True
    )
    reset_code: Mapped[str | None] = mapped_column(String, nullable=True)
    reset_code_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    whatsapp_accounts: Mapped[List["WhatsAppAccount"]] = relationship(
        "WhatsAppAccount",
        back_populates="user",
        cascade="all, delete",
        passive_deletes=True,
    )
    rag_documents: Mapped[List["RAGDocument"]] = relationship(
        "RAGDocument",
        back_populates="user",
        cascade="all, delete",
        passive_deletes=True,
    )


class WhatsAppAccount(Base):
    __tablename__ = "whatsapp_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    phone_number: Mapped[int] = mapped_column(BIGINT, nullable=False)
    phone_number_id: Mapped[str | None] = mapped_column(String)
    waba_id: Mapped[str | None] = mapped_column(String, nullable=True)
    token: Mapped[str | None] = mapped_column(String)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage_flow: Mapped[dict | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="whatsapp_accounts")
    sessions: Mapped[List["WhatsAppSession"]] = relationship(
        "WhatsAppSession",
        back_populates="whatsapp_account",
        cascade="all, delete",
        passive_deletes=True,
    )
    broadcasts: Mapped[List["Broadcast"]] = relationship(
        "Broadcast",
        back_populates="whatsapp_account",
        cascade="all, delete",
        passive_deletes=True,
    )
    tools: Mapped[List["AssistantTool"]] = relationship(
        "AssistantTool",
        back_populates="whatsapp_account",
        cascade="all, delete",
        passive_deletes=True,
    )


class WhatsAppSession(Base):
    __tablename__ = "whatsapp_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("whatsapp_account.id", ondelete="CASCADE"), nullable=False
    )
    to_number: Mapped[int | None] = mapped_column(BIGINT)
    current_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    whatsapp_account: Mapped["WhatsAppAccount"] = relationship(
        "WhatsAppAccount", back_populates="sessions"
    )
    messages: Mapped[List["WhatsAppMessage"]] = relationship(
        "WhatsAppMessage",
        back_populates="session",
        cascade="all, delete",
        passive_deletes=True,
    )


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("whatsapp_session.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    media: Mapped[dict | list | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    media_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_summarized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_labeled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped["WhatsAppSession"] = relationship(
        "WhatsAppSession", back_populates="messages"
    )


class WhatsAppSessionSummary(Base):
    __tablename__ = "whatsapp_session_summary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("whatsapp_session.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("whatsapp_account.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_language: Mapped[str] = mapped_column(String(20), nullable=False)
    template_snapshot: Mapped[dict | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    status: Mapped[BroadcastStatus] = mapped_column(
        SQLEnum(BroadcastStatus), default=BroadcastStatus.DRAFT, nullable=False
    )
    total_contacts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    whatsapp_account: Mapped["WhatsAppAccount"] = relationship(
        "WhatsAppAccount", back_populates="broadcasts"
    )
    contacts: Mapped[List["BroadcastContact"]] = relationship(
        "BroadcastContact",
        back_populates="broadcast",
        cascade="all, delete",
        passive_deletes=True,
    )


class BroadcastContact(Base):
    __tablename__ = "broadcast_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    broadcast_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("broadcasts.id", ondelete="CASCADE"), nullable=False
    )
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    template_variables: Mapped[dict | list | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    status: Mapped[BroadcastContactStatus] = mapped_column(
        SQLEnum(BroadcastContactStatus),
        default=BroadcastContactStatus.PENDING,
        nullable=False,
    )
    meta_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    broadcast: Mapped["Broadcast"] = relationship(
        "Broadcast", back_populates="contacts"
    )


class AssistantTool(Base):
    __tablename__ = "assistant_tool"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("whatsapp_account.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tool_type: Mapped[ToolType] = mapped_column(
        SQLEnum(ToolType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    config: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    whatsapp_account: Mapped["WhatsAppAccount"] = relationship(
        "WhatsAppAccount", back_populates="tools"
    )


class RAGDocument(Base):
    __tablename__ = "rag_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    collection_name: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    chunks_count: Mapped[int] = mapped_column(Integer, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User")
