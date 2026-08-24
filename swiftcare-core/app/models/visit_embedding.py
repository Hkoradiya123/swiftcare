from sqlalchemy import Column, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

try:
    from pgvector.sqlalchemy import Vector
    _VECTOR_TYPE = Vector(1536)
except ImportError:
    # fallback so models can be imported in test env (SQLite) without pgvector
    from sqlalchemy import JSON
    _VECTOR_TYPE = JSON


class VisitEmbedding(Base, TimestampMixin):
    __tablename__ = "visit_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    visit_summary_id: Mapped[int] = mapped_column(ForeignKey("visit_summaries.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = Column(_VECTOR_TYPE, nullable=False)

    visit_summary: Mapped["VisitSummary"] = relationship(
        "VisitSummary", back_populates="embeddings", lazy="raise"
    )
