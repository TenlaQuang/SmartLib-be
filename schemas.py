from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal

# --- Location Schemas ---
class LocationBase(BaseModel):
    zone_name: Optional[str] = None
    aisle_number: Optional[int] = None
    shelf_id: Optional[str] = None
    level_number: Optional[int] = None

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
    status: Optional[str] = "available"
    market_price: Decimal
    rental_rate_percent: Optional[Decimal] = Decimal("1.0")
    fine_rate_percent: Optional[Decimal] = Decimal("2.0")
    deposit_required: Optional[Decimal] = None
    image_url: Optional[str] = None
    category_id: Optional[int] = None
    location_id: Optional[int] = None

class BookCreate(BookBase):
    pass

class BookUpdate(BaseModel):
    isbn: Optional[str] = None
    title: Optional[str] = None
    status: Optional[str] = None
    market_price: Optional[Decimal] = None
    rental_rate_percent: Optional[Decimal] = None
    fine_rate_percent: Optional[Decimal] = None
    deposit_required: Optional[Decimal] = None
    image_url: Optional[str] = None
    category_id: Optional[int] = None
    location_id: Optional[int] = None

class BookResponse(BookBase):
    book_id: int
    category: Optional[Category] = None
    location: Optional[Location] = None

    class Config:
        from_attributes = True

# --- Registration Schemas ---
class RegistrationRequestCreate(BaseModel):
    user_code: str
    full_name: str
    gender: Optional[str] = None
    birth_year: Optional[int] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None
    invoice_image_url: Optional[str] = None
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

class RegistrationApprove(BaseModel):
    nfc_serial: str

class RegistrationReject(BaseModel):
    reason: str
