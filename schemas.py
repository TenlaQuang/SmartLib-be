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
    status: str
    market_price: Decimal
    rental_rate_percent: Decimal
    fine_rate_percent: Decimal
    deposit_required: Optional[Decimal] = None

class BookResponse(BookBase):
    book_id: int
    category: Optional[Category] = None
    location: Optional[Location] = None

    class Config:
        from_attributes = True
