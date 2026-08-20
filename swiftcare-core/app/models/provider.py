from datetime import time
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import ForeignKey, Numeric, SmallInteger, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class Provider(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True, nullable=False
    )
    specialization: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    license_number: Mapped[str] = mapped_column(String(100), nullable=False)
    consultation_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    default_slot_minutes: Mapped[int] = mapped_column(default=30, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="raise")
    availability: Mapped[List["ProviderAvailability"]] = relationship(
        "ProviderAvailability", back_populates="provider", lazy="raise", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Provider(id={self.id}, specialization='{self.specialization}', fee={self.consultation_fee})>"


class ProviderAvailability(Base, TimestampMixin):
    __tablename__ = "provider_availabilities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id"), index=True, nullable=False
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 0=Monday, 6=Sunday
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    provider: Mapped[Provider] = relationship("Provider", back_populates="availability", lazy="raise")

    def __repr__(self) -> str:
        return f"<ProviderAvailability(id={self.id}, weekday={self.weekday}, {self.start_time}-{self.end_time})>"
