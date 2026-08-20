from sqlalchemy.orm import DeclarativeBase


class RelayBase(DeclarativeBase):
    __table_args__ = {"schema": "relay"}
