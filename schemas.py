from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

# --- Location Schemas ---
class LocationBase(BaseModel):
    zone_name: Optional[str] = None
    aisle_number: Optional[int] = None
    shelf_id: Optional[str] = None
    level_number: Optional[int] = None
    max_capacity: Optional[int] = 50

class LocationWithCount(LocationBase):
    location_id: int
    book_count: int
    unique_books: Optional[List[dict]] = []
    
    class Config:
        from_attributes = True

class Location(LocationBase):
    location_id: int
    class Config:
        from_attributes = True

class LocationCreate(LocationBase):
    pass

# --- Category Schemas ---
class CategoryBase(BaseModel):
    name: str

class Category(CategoryBase):
    category_id: int
    class Config:
        from_attributes = True

# --- Book Schemas ---
class BookBase(BaseModel):
    isbn: str
    title: str
    author: Optional[str] = None
    category_id: Optional[int] = None
    location_id: Optional[int] = None
    market_price: float = 0.0
    rental_rate_percent: float = 1.0
    fine_rate_percent: float = 2.0
    deposit_required: bool = True
    status: str = "available"
    image_url: Optional[str] = None
    description: Optional[str] = None
    pages: Optional[int] = None
    position_in_row: Optional[int] = None

class BookCreate(BookBase):
    pass

class BookUpdate(BaseModel):
    isbn: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    category_id: Optional[int] = None
    location_id: Optional[int] = None
    market_price: Optional[float] = None
    rental_rate_percent: Optional[float] = None
    fine_rate_percent: Optional[float] = None
    deposit_required: Optional[bool] = None
    status: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    pages: Optional[int] = None
    position_in_row: Optional[int] = None

class BookResponse(BookBase):
    book_id: int
    category: Optional[Category] = None
    location: Optional[Location] = None

    class Config:
        from_attributes = True

class PaginatedBookResponse(BaseModel):
    total: int
    page: int
    page_size: int
    data: List[BookResponse]

# --- Registration Schemas ---
class PayosLinkCreate(BaseModel):
    user_code: str

class RegistrationRequestCreate(BaseModel):
    user_code: str
    full_name: str
    gender: Optional[str] = None
    birth_year: Optional[int] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None
    invoice_image_url: Optional[str] = None
    payos_order_code: Optional[int] = None
    nfc_serial: Optional[str] = None

class RegistrationRequestResponse(BaseModel):
    request_id: int
    user_code: str
    full_name: str
    request_status: str
    gender: Optional[str] = None
    birth_year: Optional[int] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None
    invoice_image_url: Optional[str] = None
    payos_order_code: Optional[int] = None
    nfc_serial: Optional[str] = None
    checkoutUrl: Optional[str] = None

    class Config:
        from_attributes = True

# --- User Schemas ---
class UserBase(BaseModel):
    user_code: str
    full_name: str
    gender: Optional[str] = None
    birth_year: Optional[int] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None
    nfc_tag_id: Optional[str] = None
    user_type: Optional[str] = "student"
    status: Optional[str] = "active"

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    user_id: int

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    gender: Optional[str] = None
    birth_year: Optional[int] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    user_type: Optional[str] = None

class RegistrationApprove(BaseModel):
    nfc_serial: str

class RegistrationReject(BaseModel):
    reason: str

class NFCReissue(BaseModel):
    new_nfc_serial: str

class NfcTagCreate(BaseModel):
    nfc_serial: str
    label: str

class NfcTagResponse(BaseModel):
    tag_id: int
    nfc_serial: str
    label: str
    status: str
    
    class Config:
        from_attributes = True

class RegistrationApproveWithTag(BaseModel):
    tag_id: int

class AssignNFC(BaseModel):
    nfc_serial: str

class TransactionResponse(BaseModel):
    transaction_id: int
    book_title: str
    borrow_date: datetime
    due_date: datetime
    status: str
    
    class Config:
        from_attributes = True

class UserActivityResponse(BaseModel):
    ongoing_count: int
    ongoing_books: List[TransactionResponse]
    completed_count: int
    history: List[TransactionResponse]

# --- Borrow Request Schemas ---
class BorrowRequestCreate(BaseModel):
    user_id: int
    isbns: List[str]

class BorrowRequestDetailResponse(BaseModel):
    detail_id: int
    isbn: str

    class Config:
        from_attributes = True

class BorrowRequestResponse(BaseModel):
    request_id: int
    user_id: int
    status: str
    created_at: datetime
    details: List[BorrowRequestDetailResponse]

    class Config:
        from_attributes = True

# --- Return Request Schemas ---
class ReturnRequestCreate(BaseModel):
    user_id: int
    isbns: List[str]

class ReturnRequestDetailResponse(BaseModel):
    detail_id: int
    isbn: str

    class Config:
        from_attributes = True

class ReturnRequestResponse(BaseModel):
    request_id: int
    user_id: int
    status: str
    created_at: datetime
    details: List[ReturnRequestDetailResponse]

    class Config:
        from_attributes = True
