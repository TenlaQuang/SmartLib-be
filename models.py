from sqlalchemy import Column, Integer, String, Text, ForeignKey, Numeric, DateTime, Float, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

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
    max_capacity = Column(Integer, default=50) # Giới hạn 50 cuốn mỗi hàng
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
    isbn = Column(String(20), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    author = Column(String(255), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.category_id"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.location_id"), nullable=True)
    import_id = Column(Integer, ForeignKey("import_logs.import_id"), nullable=True)
    
    market_price = Column(Numeric(12, 2), nullable=False)
    rental_rate_percent = Column(Numeric(5, 2), default=1.0)
    fine_rate_percent = Column(Numeric(5, 2), default=2.0)
    deposit_required = Column(Numeric(12, 2), nullable=True)
    
    status = Column(String(20), default="available")
    image_url = Column(String(500), nullable=True)

    # Mối quan hệ
    category = relationship("Category", back_populates="books")
    location = relationship("Location", back_populates="books")
    import_log = relationship("ImportLog", back_populates="books")

class RegistrationRequest(Base):
    __tablename__ = "registration_requests"

    request_id = Column(Integer, primary_key=True, index=True)
    user_code = Column(String(20), unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    gender = Column(String(10), nullable=True)
    birth_year = Column(Integer, nullable=True)
    phone_number = Column(String(15), nullable=True)
    address = Column(Text, nullable=True)
    email = Column(String(100), nullable=True)
    invoice_image_url = Column(String(500), nullable=True)
    nfc_serial = Column(String(100), nullable=True)
    request_status = Column(String(20), default="pending")
    payment_status = Column(String(20), default="pending")
    payos_order_code = Column(BigInteger, unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    user_code = Column(String(20), unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    gender = Column(String(10), nullable=True)
    birth_year = Column(Integer, nullable=True)
    phone_number = Column(String(15), nullable=True)
    address = Column(Text, nullable=True)
    email = Column(String(100), nullable=True)
    nfc_tag_id = Column(String(50), unique=True, nullable=True)
    user_type = Column(String(20), default="student")
    status = Column(String(20), default="pending_nfc")
    created_at = Column(DateTime, default=datetime.utcnow)

class NfcTag(Base):
    __tablename__ = "nfc_inventory"

    tag_id = Column(Integer, primary_key=True, index=True)
    nfc_serial = Column(String(100), unique=True, index=True, nullable=False)
    label = Column(String(100), nullable=False)
    status = Column(String(20), default="available") # available | assigned
    created_at = Column(DateTime, default=datetime.utcnow)
class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    book_id = Column(Integer, ForeignKey("books.book_id"), nullable=False)
    borrow_date = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime, nullable=False)
    return_date = Column(DateTime, nullable=True)
    deposit_amount = Column(Numeric(12, 2), nullable=True)
    total_fee = Column(Numeric(12, 2), default=0)
    refund_amount = Column(Numeric(12, 2), default=0)
    status = Column(String(20), default="ongoing")
