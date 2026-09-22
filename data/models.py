from sqlalchemy.types import Integer, Text, String, DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey
import datetime
from data.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer ,primary_key=True)
    name: Mapped[str] = mapped_column(String)
    user_name: Mapped[str] = mapped_column(String)
    phone_number: Mapped[str] = mapped_column(String)
    city:  Mapped[str] = mapped_column(String)
    creation_date: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))

class Place(Base):
    __tablename__ = "places"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship("User")
    address: Mapped[str] = mapped_column(String)
    cost: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(Text)
    photo: Mapped[str] = mapped_column(String)
    downloaded_documents: Mapped[str] = mapped_column(String)
    creation_date: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))

class SavedObject(Base):
    __tablename__ = "saved_objects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    object_id: Mapped[int] = mapped_column(ForeignKey("places.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    object: Mapped["Place"] = relationship("Place")
    user: Mapped["User"] = relationship("User")