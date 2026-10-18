from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class BrowserSession(Base):
    """An anonymous browser session; its uploads are private and deleted when it expires."""

    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Document(Base):
    __tablename__ = "documents"

    doc_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    # Owning browser session; None for shared documents ingested with the CLI.
    session_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    file_name: Mapped[str] = mapped_column(String(500))
    source_uri: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(Text)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Chunk.position"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    chunk_id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID == Qdrant point id
    doc_id: Mapped[str] = mapped_column(ForeignKey("documents.doc_id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_path: Mapped[list[str]] = mapped_column(JSON, default=list)
    token_count: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)

    document: Mapped[Document] = relationship(back_populates="chunks")


class Trace(Base):
    """One /ask request: what was asked, what was shown to the model, what came back."""

    __tablename__ = "traces"

    query_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    abstained: Mapped[bool] = mapped_column(default=False)
    abstain_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    citations: Mapped[list[dict]] = mapped_column(JSON, default=list)
    context_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    latency_ms: Mapped[dict] = mapped_column(JSON, default=dict)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    otel_trace_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Feedback(Base):
    """A user's rating of one answer, stored with what was asked and cited."""

    __tablename__ = "feedback"

    query_id: Mapped[str] = mapped_column(ForeignKey("traces.query_id", ondelete="CASCADE"), primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    cited_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    rating: Mapped[str] = mapped_column(String(20))  # helpful | not_helpful
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
