from typing import Optional
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class VisitSummary(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "visit_summaries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"), unique=True, nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    diagnosis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    document_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    embeddings: Mapped[list["VisitEmbedding"]] = relationship(
        "VisitEmbedding", back_populates="visit_summary", cascade="all, delete-orphan", lazy="raise"
    )
