from sqlalchemy import Column, Integer, DateTime, String, Boolean, Float, func, ForeignKey
from sqlalchemy.orm import relationship, backref

from language import LanguageService
from models.base import Base, I128

class Filter(Base):
    __tablename__ = 'filters'

    id = Column(Integer, primary_key=True)
    active = Column(Boolean, default=False)
    min_price = Column(Integer, default=0)
    max_price = Column(Integer, default=-1)
    min_supply = Column(Integer, default=0)
    max_supply = Column(Integer, default=-1)
    amount_stars = Column(Integer, default=-1)
    recipient_telegram_id = Column(I128, nullable=False)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    session = relationship("Session", back_populates="filters")