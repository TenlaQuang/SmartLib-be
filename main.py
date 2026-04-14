from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

# Import Database và Models/Schemas
from database import engine, get_db, Base
import models
import schemas

# (Tùy chọn) Tự động tạo bảng nếu chưa có, nhưng vì bạn đã chạy SQL trên NeonDB nên ta có thể bỏ qua dòng này. 
# Tuy nhiên, để cho an toàn thì cứ để, nếu bảng có rồi nó sẽ không làm gì.
# models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="SmartLib API")

# Setup CORS for flutter web / local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to SmartLib API System (Connected to PostgreSQL)"}

@app.get("/api/books", response_model=List[schemas.BookResponse])
def get_books(db: Session = Depends(get_db), limit: int = 100):
    """
    API lấy danh sách sách, kèm theo thông tin thể loại và vị trí nằm trên kệ.
    """
    books = db.query(models.Book).limit(limit).all()
    return books

@app.get("/api/books/{book_id}", response_model=schemas.BookResponse)
def get_book_by_id(book_id: int, db: Session = Depends(get_db)):
    """
    API lấy thông tin một cuốn sách cụ thể bằng ID.
    """
    book = db.query(models.Book).filter(models.Book.book_id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuốn sách này")
    return book
