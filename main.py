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
import pandas as pd
import io
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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


def send_email_notification(to_email: str, subject: str, body: str):
    sender_email = os.getenv("SMTP_EMAIL")
    sender_password = os.getenv("SMTP_PASSWORD")
    if not sender_email or not sender_password:
        print(f"Cảnh báo: Chưa cấu hình SMTP_EMAIL và SMTP_PASSWORD trong .env. Bỏ qua gửi email tới {to_email}.")
        print(f"Nội dung thư dự kiến:\nTiêu đề: {subject}\nNội dung: {body}")
        return
        
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
            print(f"Đã gửi email thành công tới {to_email}")
    except Exception as e:
        print(f"Lỗi khi gửi email tới {to_email}: {e}")
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

@app.post("/api/books/import-excel")
async def import_books_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Nhập sách hàng loạt từ file Excel.
    Cột yêu cầu: title, market_price
    Cột tùy chọn: quantity (mặc định 1)
    """
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        required_cols = ['title', 'market_price']
        for col in required_cols:
            if col not in df.columns:
                raise HTTPException(status_code=400, detail=f"File Excel thiếu cột bắt buộc: {col}")
                
        books_created = 0
        
        for index, row in df.iterrows():
            if pd.isna(row['title']):
                continue
            title = str(row['title'])
            market_price = float(row['market_price']) if not pd.isna(row['market_price']) else 0.0
            quantity = int(row['quantity']) if 'quantity' in df.columns and not pd.isna(row['quantity']) else 1
            
            for _ in range(quantity):
                while True:
                    prefix = "978"
                    d1 = str(random.randint(0, 9))
                    d2 = str(random.randint(0, 9999)).zfill(4)
                    d3 = str(random.randint(0, 9999)).zfill(4)
                    partial = prefix + d1 + d2 + d3
                    sum_digits = sum(int(digit) if i % 2 == 0 else int(digit) * 3 for i, digit in enumerate(partial))
                    remainder = sum_digits % 10
                    check_digit = 0 if remainder == 0 else 10 - remainder
                    isbn = f"{prefix}-{d1}-{d2}-{d3}-{check_digit}"
                    
                    existing = db.query(models.Book).filter(models.Book.isbn == isbn).first()
                    if not existing:
                        break
                        
                new_book = models.Book(
                    isbn=isbn,
                    title=title,
                    market_price=market_price,
                    status="available"
                )
                db.add(new_book)
                books_created += 1
                
        db.commit()
        return {"message": f"Nhập thành công {books_created} cuốn sách."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/books", response_model=schemas.BookResponse)
def create_book(book_in: schemas.BookCreate, db: Session = Depends(get_db)):
    """
    API thêm mới một cuốn sách.
    """
    if book_in.location_id is not None:
        existing_location_book = db.query(models.Book).filter(
            models.Book.title == book_in.title,
            models.Book.location_id != None,
            models.Book.location_id != book_in.location_id
        ).first()
        if existing_location_book:
            raise HTTPException(status_code=400, detail=f"Sách '{book_in.title}' đã được xếp ở vị trí khác. Một tựa sách chỉ ở duy nhất 1 vị trí.")
            
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
    
    target_title = book_in.title if book_in.title else book.title
    if 'location_id' in book_in.model_dump(exclude_unset=True) and book_in.location_id is not None:
        existing_location_book = db.query(models.Book).filter(
            models.Book.title == target_title,
            models.Book.book_id != book_id,
            models.Book.location_id != None,
            models.Book.location_id != book_in.location_id
        ).first()
        if existing_location_book:
            raise HTTPException(status_code=400, detail=f"Sách '{target_title}' đã được xếp ở vị trí khác. Một tựa sách chỉ ở duy nhất 1 vị trí.")
            
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

@app.get("/api/registration-requests", response_model=List[schemas.RegistrationRequestResponse])
def get_registration_requests(db: Session = Depends(get_db)):
    """
    Lấy danh sách các đơn đăng ký đang chờ duyệt.
    """
    return db.query(models.RegistrationRequest).filter(models.RegistrationRequest.request_status == 'pending').all()

@app.post("/api/registration-requests/{request_id}/approve")
def approve_registration_request(request_id: int, payload: schemas.RegistrationApprove, db: Session = Depends(get_db)):
    """
    Duyệt đơn đăng ký, tạo User mới với thẻ NFC.
    """
    req = db.query(models.RegistrationRequest).filter(models.RegistrationRequest.request_id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đăng ký.")
    if req.request_status != "pending":
        raise HTTPException(status_code=400, detail=f"Đơn này đã được xử lý ({req.request_status}).")
        
    # Kiểm tra xem NFC này đã được gán cho user nào chưa
    existing_nfc = db.query(models.User).filter(models.User.nfc_tag_id == payload.nfc_serial).first()
    if existing_nfc:
        raise HTTPException(status_code=400, detail="Thẻ NFC này đã được gán cho một người dùng khác.")
        
    try:
        # Cập nhật trạng thái
        req.request_status = "approved"
        
        # Tạo User mới
        new_user = models.User(
            user_code=req.user_code,
            full_name=req.full_name,
            gender=req.gender,
            birth_year=req.birth_year,
            phone_number=req.phone_number,
            address=req.address,
            email=req.email,
            nfc_tag_id=payload.nfc_serial,
            status="active"
        )
        db.add(new_user)
        db.commit()
        
        # Gửi Email thông báo
        if req.email:
            body = (f"Chào {req.full_name},\\n\\n"
                    f"Đơn đăng ký làm thẻ mượn sách thư viện của bạn ĐÃ ĐƯỢC DUYỆT.\\n"
                    f"Tài khoản của bạn đã được liên kết với thẻ NFC mang số serial: {payload.nfc_serial}.\\n\\n"
                    f"Vui lòng đến quầy thủ thư để nhận thẻ vật lý (trong trường hợp thư viện cấp thẻ cho bạn).\\n\\n"
                    f"Trân trọng,\\nBan Quản Trị Thư Viện.")
            send_email_notification(req.email, "Thông Báo Duyệt Đăng Ký Thư Viện", body)
            
        return {"message": "Đã duyệt và tạo người dùng thành công"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/registration-requests/{request_id}/reject")
def reject_registration_request(request_id: int, payload: schemas.RegistrationReject, db: Session = Depends(get_db)):
    """
    Từ chối đơn đăng ký.
    """
    req = db.query(models.RegistrationRequest).filter(models.RegistrationRequest.request_id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đăng ký.")
    if req.request_status != "pending":
        raise HTTPException(status_code=400, detail=f"Đơn này đã được xử lý ({req.request_status}).")
        
    try:
        req.request_status = "rejected"
        db.commit()
        
        # Gửi Email từ chối
        if req.email:
            body = (f"Chào {req.full_name},\\n\\n"
                    f"Rất tiếc, đơn đăng ký thư viện của bạn bị TỪ CHỐI.\\n"
                    f"Lý do: {payload.reason}\\n\\n"
                    f"Vui lòng liên hệ thủ thư để được làm thủ tục hoàn tiền (nếu có).\\n\\n"
                    f"Trân trọng,\\nBan Quản Trị Thư Viện.")
            send_email_notification(req.email, "Thông Báo Từ Chối Đăng Ký Thư Viện", body)
            
        return {"message": "Đã từ chối đơn đăng ký"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
