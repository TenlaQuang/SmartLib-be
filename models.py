from sqlalchemy import Column, Integer, String, Text, ForeignKey, Numeric, DateTime, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Category(Base):
    __tablename__ = "categories"

    category_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    books = relationship("Book", back_populates="category")


class Location(Base):
    __tablename__ = "locations"

    location_id = Column(Integer, primary_key=True, index=True)
    zone_name = Column(String(50), nullable=True)
    aisle_number = Column(Integer, nullable=True)
    shelf_id = Column(String(20), nullable=True)
    level_number = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)

    books = relationship("Book", back_populates="location")


class ImportLog(Base):
    __tablename__ = "import_logs"

    import_id = Column(Integer, primary_key=True, index=True)
    import_date = Column(DateTime, default=datetime.utcnow)
    provider_name = Column(String(255), nullable=True)
    total_quantity = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)

    books = relationship("Book", back_populates="import_log")


class Book(Base):
    __tablename__ = "books"

    book_id = Column(Integer, primary_key=True, index=True)
    isbn = Column(String(20), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.category_id"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.location_id"), nullable=True)
    import_id = Column(Integer, ForeignKey("import_logs.import_id"), nullable=True)
    
    market_price = Column(Numeric(12, 2), nullable=False)
    rental_rate_percent = Column(Numeric(5, 2), default=1.0)
    fine_rate_percent = Column(Numeric(5, 2), default=2.0)
    deposit_required = Column(Numeric(12, 2), nullable=True)
    
    status = Column(String(20), default="available")

    # Mối quan hệ
    category = relationship("Category", back_populates="books")
    location = relationship("Location", back_populates="books")
    import_log = relationship("ImportLog", back_populates="books")
