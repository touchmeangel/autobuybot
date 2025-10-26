from sqlalchemy import Column, Integer, DateTime, String, Boolean, Float, func, ForeignKey
from sqlalchemy.orm import relationship, backref

from language import LanguageService
from models.base import Base, I128


class Session(Base):
    __tablename__ = 'sessions'

    id = Column(Integer, primary_key=True)
    session_string = Column(String, nullable=False)
    api_id = Column(Integer, nullable=False)
    api_hash = Column(String, nullable=False)
    filters = relationship("Filter", back_populates="session", cascade="all, delete-orphan", lazy="selectin", order_by="Filter.id")
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="sessions")