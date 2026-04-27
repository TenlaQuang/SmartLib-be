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
from payos import PayOS, ItemData, PaymentData
from fastapi.responses import HTMLResponse
import time

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

# Khởi tạo PayOS
payos_client_id = os.getenv("PAYOS_CLIENT_ID", "YOUR_CLIENT_ID")
payos_api_key = os.getenv("PAYOS_API_KEY", "YOUR_API_KEY")
payos_checksum_key = os.getenv("PAYOS_CHECKSUM_KEY", "YOUR_CHECKSUM_KEY")

payos_client = PayOS(
    client_id=payos_client_id,
    api_key=payos_api_key,
    checksum_key=payos_checksum_key
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
    API tạo yêu cầu đăng ký người dùng mới và tạo link thanh toán PayOS.
    """
    existing_req = db.query(models.RegistrationRequest).filter(models.RegistrationRequest.user_code == req_in.user_code).first()
    if existing_req:
        raise HTTPException(status_code=400, detail="Mã sinh viên/CCCD này đã có yêu cầu đăng ký.")
        
    new_request = models.RegistrationRequest(**req_in.model_dump())
    db.add(new_request)
    try:
        db.commit()
        db.refresh(new_request)
        
        # 1. Tạo order_code duy nhất cho PayOS (phải là số nguyên, max 9007199254740991)
        # Kết hợp timestamp và request_id để đảm bảo duy nhất
        order_code = int(f"{int(time.time())}{new_request.request_id}")
        
        # Lưu order_code vào DB
        new_request.payos_order_code = order_code
        db.commit()
        
        # 2. Tạo dữ liệu thanh toán PayOS
        # Số tiền quy định là 50.000 VND (bạn có thể thay đổi)
        amount = 50000 
        item = ItemData(name=f"Đăng ký thẻ SmartLib - {new_request.user_code}", quantity=1, price=amount)
        
        # Lấy base URL từ môi trường hoặc hardcode URL Backend Render của bạn
        domain = os.getenv("BACKEND_URL", "https://smartlib-be.onrender.com")
        
        payment_data = PaymentData(
            orderCode=order_code,
            amount=amount,
            description=f"DK {new_request.user_code}", # Tối đa 25 ký tự
            items=[item],
            returnUrl=f"{domain}/payment-success",
            cancelUrl=f"{domain}/payment-success" # Có thể làm trang /payment-cancel riêng nếu muốn
        )
        
        # 3. Gọi PayOS tạo link thanh toán
        payos_response = payos_client.createPaymentLink(payment_data)
        
        # Trả về Response kèm theo checkoutUrl
        response_data = schemas.RegistrationRequestResponse.model_validate(new_request)
        response_data.checkoutUrl = payos_response.checkoutUrl
        return response_data
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Lỗi: {str(e)}")

@app.post("/api/payos-webhook")
def payos_webhook(webhook_data: dict, db: Session = Depends(get_db)):
    """
    Webhook để PayOS gọi về khi có thanh toán thành công.
    """
    try:
        # Ở môi trường thực tế, BẠN CẦN verify chữ ký (checksum) của Webhook để đảm bảo bảo mật.
        # webhook_data_verified = payos_client.verifyPaymentWebhookData(webhook_data)
        # data = webhook_data_verified.data
        
        # Đối với PayOS dict (nếu không parse model)
        data = webhook_data.get("data", {})
        order_code = data.get("orderCode")
        
        if order_code:
            # Cập nhật trạng thái thanh toán trong DB
            req = db.query(models.RegistrationRequest).filter(models.RegistrationRequest.payos_order_code == order_code).first()
            if req:
                req.payment_status = "paid"
                db.commit()
                
        return {"success": True}
    except Exception as e:
        print(f"Webhook error: {e}")
        return {"success": False, "error": str(e)}

@app.get("/payment-success", response_class=HTMLResponse)
def payment_success_page():
    """
    Trang web hiển thị sau khi sinh viên thanh toán xong trên trình duyệt.
    """
    return """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Thanh toán SmartLib</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #FFF7DD; color: #80A1BA; text-align: center; padding: 50px; }
            h1 { color: #91C4C3; }
            .container { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto; }
            .icon { font-size: 60px; color: #B4DEBD; margin-bottom: 20px; }
            p { font-size: 18px; line-height: 1.6; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">✔️</div>
            <h1>Giao dịch hoàn tất!</h1>
            <p>Yêu cầu đăng ký thẻ SmartLib của bạn đã được tiếp nhận.</p>
            <p>Vui lòng quay lại ứng dụng và chờ email xác nhận phê duyệt từ thư viện nhé!</p>
            <p style="font-size: 14px; color: #ccc; margin-top: 30px;">Bạn có thể đóng cửa sổ trình duyệt này.</p>
        </div>
    </body>
    </html>
    """
