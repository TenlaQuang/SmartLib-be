from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
import os
import shutil
import uuid
import cloudinary
import cloudinary.uploader

# Import Database và Models/Schemas
from database import engine, get_db, Base
import models
import schemas

# (Tùy chọn) Tự động tạo bảng nếu chưa có, nhưng vì bạn đã chạy SQL trên NeonDB nên ta có thể bỏ qua dòng này. 
# Tuy nhiên, để cho an toàn thì cứ để, nếu bảng có rồi nó sẽ không làm gì.
# models.Base.metadata.create_all(bind=engine)

# Cấu hình Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

app = FastAPI(title="SmartLib API")

# Cấu hình chứa file tĩnh (Hình ảnh)
os.makedirs("static/images", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

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

@app.get("/api/test-db")
def test_db_connection(db: Session = Depends(get_db)):
    """
    API dùng để kiểm tra xem Backend đã kết nối được với Neon PostgreSQL hay chưa.
    """
    try:
        # Thử thực thi một câu lệnh SQL đơn giản
        db.execute(text("SELECT 1"))
        return {"status": "success", "message": "Kết nối Database thành công! Dữ liệu đã sẵn sàng."}
    except Exception as e:
        return {"status": "error", "message": f"Kết nối thất bại. Chi tiết lỗi: {str(e)}"}

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

@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """
    API upload ảnh bìa trực tiếp lên Cloudinary.
    """
    try:
        # Đọc nội dung file
        file_contents = await file.read()
        
        # Upload lên Cloudinary
        result = cloudinary.uploader.upload(file_contents, folder="smartlib_books")
        
        # Lấy URL của ảnh trên Cloudinary
        image_url = result.get("secure_url")
        
        return {"image_url": image_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể upload ảnh: {str(e)}")

@app.post("/api/books", response_model=schemas.BookResponse)
def create_book(book_in: schemas.BookCreate, db: Session = Depends(get_db)):
    """
    API thêm mới một cuốn sách.
    """
    new_book = models.Book(**book_in.model_dump())
    db.add(new_book)
    try:
        db.commit()
        db.refresh(new_book)
        return new_book
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/books/{book_id}", response_model=schemas.BookResponse)
def update_book(book_id: int, book_in: schemas.BookUpdate, db: Session = Depends(get_db)):
    """
    API cập nhật thông tin sách.
    """
    book = db.query(models.Book).filter(models.Book.book_id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuốn sách này")
    
    update_data = book_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(book, key, value)
        
    try:
        db.commit()
        db.refresh(book)
        return book
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/books/{book_id}")
def delete_book(book_id: int, db: Session = Depends(get_db)):
    """
    API xóa sách (Xóa vĩnh viễn hoặc có thể bạn đổi status thành deleted tùy yêu cầu).
    Ở đây sẽ thực hiện xóa vĩnh viễn.
    """
    book = db.query(models.Book).filter(models.Book.book_id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuốn sách này")
        
    try:
        db.delete(book)
        db.commit()
        return {"message": "Xóa sách thành công", "book_id": book_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/locations", response_model=List[schemas.Location])
def get_locations(db: Session = Depends(get_db)):
    """
    Lấy danh sách điểm lưu trữ (vị trí/kệ)
    """
    return db.query(models.Location).all()

@app.post("/api/locations", response_model=schemas.Location)
def create_location(location_in: schemas.LocationCreate, db: Session = Depends(get_db)):
    """
    Tạo vị trí kệ sách mới
    """
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
import os
import shutil
import uuid
import cloudinary
import cloudinary.uploader

# Import Database và Models/Schemas
from database import engine, get_db, Base
import models
import schemas

# (Tùy chọn) Tự động tạo bảng nếu chưa có, nhưng vì bạn đã chạy SQL trên NeonDB nên ta có thể bỏ qua dòng này. 
# Tuy nhiên, để cho an toàn thì cứ để, nếu bảng có rồi nó sẽ không làm gì.
# models.Base.metadata.create_all(bind=engine)

# Cấu hình Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

app = FastAPI(title="SmartLib API")

# Cấu hình chứa file tĩnh (Hình ảnh)
os.makedirs("static/images", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

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

@app.get("/api/test-db")
def test_db_connection(db: Session = Depends(get_db)):
    """
    API dùng để kiểm tra xem Backend đã kết nối được với Neon PostgreSQL hay chưa.
    """
    try:
        # Thử thực thi một câu lệnh SQL đơn giản
        db.execute(text("SELECT 1"))
        return {"status": "success", "message": "Kết nối Database thành công! Dữ liệu đã sẵn sàng."}
    except Exception as e:
        return {"status": "error", "message": f"Kết nối thất bại. Chi tiết lỗi: {str(e)}"}

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

@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """
    API upload ảnh bìa trực tiếp lên Cloudinary.
    """
    try:
        # Đọc nội dung file
        file_contents = await file.read()
        
        # Upload lên Cloudinary
        result = cloudinary.uploader.upload(file_contents, folder="smartlib_books")
        
        # Lấy URL của ảnh trên Cloudinary
        image_url = result.get("secure_url")
        
        return {"image_url": image_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể upload ảnh: {str(e)}")

@app.post("/api/books", response_model=schemas.BookResponse)
def create_book(book_in: schemas.BookCreate, db: Session = Depends(get_db)):
    """
    API thêm mới một cuốn sách.
    """
    new_book = models.Book(**book_in.model_dump())
    db.add(new_book)
    try:
        db.commit()
        db.refresh(new_book)
        return new_book
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/books/{book_id}", response_model=schemas.BookResponse)
def update_book(book_id: int, book_in: schemas.BookUpdate, db: Session = Depends(get_db)):
    """
    API cập nhật thông tin sách.
    """
    book = db.query(models.Book).filter(models.Book.book_id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuốn sách này")
    
    update_data = book_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(book, key, value)
        
    try:
        db.commit()
        db.refresh(book)
        return book
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/books/{book_id}")
def delete_book(book_id: int, db: Session = Depends(get_db)):
    """
    API xóa sách (Xóa vĩnh viễn hoặc có thể bạn đổi status thành deleted tùy yêu cầu).
    Ở đây sẽ thực hiện xóa vĩnh viễn.
    """
    book = db.query(models.Book).filter(models.Book.book_id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuốn sách này")
        
    try:
        db.delete(book)
        db.commit()
        return {"message": "Xóa sách thành công", "book_id": book_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/locations", response_model=List[schemas.Location])
def get_locations(db: Session = Depends(get_db)):
    """
    Lấy danh sách điểm lưu trữ (vị trí/kệ)
    """
    return db.query(models.Location).all()

@app.post("/api/locations", response_model=schemas.Location)
def create_location(location_in: schemas.LocationCreate, db: Session = Depends(get_db)):
    """
    Tạo vị trí kệ sách mới
    """
    new_location = models.Location(**location_in.model_dump())
    db.add(new_location)
    try:
        db.commit()
        db.refresh(new_location)
        return new_location
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/locations/{location_id}", response_model=schemas.Location)
def update_location(location_id: int, location_in: schemas.LocationCreate, db: Session = Depends(get_db)):
    """
    Cập nhật vị trí kệ sách
    """
    location = db.query(models.Location).filter(models.Location.location_id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Không tìm thấy vị trí này")
    
    update_data = location_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(location, key, value)
        
    try:
        db.commit()
        db.refresh(location)
        return location
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/locations/{location_id}")
def delete_location(location_id: int, db: Session = Depends(get_db)):
    """
    Xóa vị trí kệ sách. Tự động gỡ các sách khỏi kệ này (location_id = NULL) trước khi xóa.
    """
    location = db.query(models.Location).filter(models.Location.location_id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Không tìm thấy vị trí này")
        
    try:
        # Smart Delete: Chuyển sách về Kệ Chờ
        db.query(models.Book).filter(models.Book.location_id == location_id).update({"location_id": None})
        
        # Xóa kệ
        db.delete(location)
        db.commit()
        return {"message": "Xóa vị trí thành công", "location_id": location_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/register", response_model=schemas.RegistrationRequestResponse)
def register_user(req_in: schemas.RegistrationRequestCreate, db: Session = Depends(get_db)):
    """
    API tạo yêu cầu đăng ký người dùng mới.
    """
    # Check if user_code already exists in registration_requests
    existing_req = db.query(models.RegistrationRequest).filter(models.RegistrationRequest.user_code == req_in.user_code).first()
    if existing_req:
        raise HTTPException(status_code=400, detail="Mã sinh viên/CCCD này đã có yêu cầu đăng ký.")
        
    new_request = models.RegistrationRequest(**req_in.model_dump())
    db.add(new_request)
    try:
        db.commit()
        db.refresh(new_request)
        return new_request
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
