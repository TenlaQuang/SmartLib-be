# ==============================================================================
# SmartLib API - FastAPI Backend
# ==============================================================================
import os
import io
import time
import random
from typing import List

import cloudinary
import cloudinary.uploader
import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from payos import PayOS
from payos.types import CreatePaymentLinkRequest, ItemData
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas

# ==============================================================================
# Cấu hình dịch vụ bên ngoài
# ==============================================================================
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

payos_client = PayOS(
    client_id=os.getenv("PAYOS_CLIENT_ID", ""),
    api_key=os.getenv("PAYOS_API_KEY", ""),
    checksum_key=os.getenv("PAYOS_CHECKSUM_KEY", ""),
)

BACKEND_URL = os.getenv("BACKEND_URL", "https://smartlib-be.onrender.com")
CARD_FEE = int(os.getenv("CARD_FEE", "50000"))  # Phí làm thẻ (VND)

# ==============================================================================
# Khởi tạo ứng dụng
# ==============================================================================
app = FastAPI(title="SmartLib API", version="2.0.0")

# Tạo thư mục static nếu chưa có (cần thiết trên Render)
static_dir = "static/images"
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.middleware("http")
async def add_cors_header(request, call_next):
    # Xử lý các request OPTIONS (Preflight)
    if request.method == "OPTIONS":
        response = HTMLResponse(content="", status_code=204)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response
    
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

# ==============================================================================
# Utility helpers
# ==============================================================================
def _generate_isbn(db: Session) -> str:
    """Tạo ISBN-13 hợp lệ và chưa tồn tại trong DB."""
    while True:
        prefix = "978"
        body = "".join([str(random.randint(0, 9)) for _ in range(9)])
        partial = prefix + body
        total = sum(
            int(d) if i % 2 == 0 else int(d) * 3
            for i, d in enumerate(partial)
        )
        check = (10 - (total % 10)) % 10
        isbn = f"{prefix}-{body[0]}-{body[1:5]}-{body[5:9]}-{check}"
        if not db.query(models.Book).filter(models.Book.isbn == isbn).first():
            return isbn


def _get_or_404(db: Session, model, pk_field, pk_value, label: str):
    obj = db.query(model).filter(pk_field == pk_value).first()
    if not obj:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy {label}")
    return obj


def _commit_or_rollback(db: Session):
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ==============================================================================
# Health & Debug
# ==============================================================================
@app.get("/")
def read_root():
    return {"message": "SmartLib API v2.0 - Online"}


@app.get("/api/test-db")
def test_db(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "message": "Kết nối Database thành công!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ==============================================================================
# Books
# ==============================================================================
@app.get("/api/books", response_model=List[schemas.BookResponse])
def get_books(db: Session = Depends(get_db), limit: int = 100):
    return db.query(models.Book).limit(limit).all()


@app.get("/api/books/{book_id}", response_model=schemas.BookResponse)
def get_book(book_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, models.Book, models.Book.book_id, book_id, "sách")


@app.post("/api/books", response_model=schemas.BookResponse)
def create_book(book_in: schemas.BookCreate, db: Session = Depends(get_db)):
    new_book = models.Book(**book_in.model_dump())
    db.add(new_book)
    _commit_or_rollback(db)
    db.refresh(new_book)
    return new_book


@app.put("/api/books/{book_id}", response_model=schemas.BookResponse)
def update_book(book_id: int, book_in: schemas.BookUpdate, db: Session = Depends(get_db)):
    book = _get_or_404(db, models.Book, models.Book.book_id, book_id, "sách")
    for key, value in book_in.model_dump(exclude_unset=True).items():
        setattr(book, key, value)
    _commit_or_rollback(db)
    db.refresh(book)
    return book


@app.delete("/api/books/{book_id}")
def delete_book(book_id: int, db: Session = Depends(get_db)):
    book = _get_or_404(db, models.Book, models.Book.book_id, book_id, "sách")
    db.delete(book)
    _commit_or_rollback(db)
    return {"message": "Xóa sách thành công", "book_id": book_id}


@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...)):
    try:
        result = cloudinary.uploader.upload(await file.read(), folder="smartlib_books")
        return {"image_url": result.get("secure_url")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload thất bại: {str(e)}")


@app.post("/api/books/import-excel")
async def import_books_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Nhập sách hàng loạt từ Excel. Cột bắt buộc: title, market_price. Tùy chọn: quantity."""
    try:
        df = pd.read_excel(io.BytesIO(await file.read()))
        for col in ["title", "market_price"]:
            if col not in df.columns:
                raise HTTPException(status_code=400, detail=f"File thiếu cột: {col}")

        count = 0
        for _, row in df.iterrows():
            if pd.isna(row["title"]):
                continue
            qty = int(row.get("quantity", 1)) if not pd.isna(row.get("quantity", 1)) else 1
            for _ in range(qty):
                db.add(models.Book(
                    isbn=_generate_isbn(db),
                    title=str(row["title"]),
                    market_price=float(row["market_price"]),
                    status="available",
                ))
                count += 1

        db.commit()
        return {"message": f"Nhập thành công {count} cuốn sách."}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# Locations
# ==============================================================================
@app.get("/api/locations", response_model=List[schemas.Location])
def get_locations(db: Session = Depends(get_db)):
    return db.query(models.Location).all()


@app.post("/api/locations", response_model=schemas.Location)
def create_location(loc_in: schemas.LocationCreate, db: Session = Depends(get_db)):
    new_loc = models.Location(**loc_in.model_dump())
    db.add(new_loc)
    _commit_or_rollback(db)
    db.refresh(new_loc)
    return new_loc


@app.put("/api/locations/{location_id}", response_model=schemas.Location)
def update_location(location_id: int, loc_in: schemas.LocationCreate, db: Session = Depends(get_db)):
    loc = _get_or_404(db, models.Location, models.Location.location_id, location_id, "vị trí")
    for key, value in loc_in.model_dump(exclude_unset=True).items():
        setattr(loc, key, value)
    _commit_or_rollback(db)
    db.refresh(loc)
    return loc


@app.delete("/api/locations/{location_id}")
def delete_location(location_id: int, db: Session = Depends(get_db)):
    loc = _get_or_404(db, models.Location, models.Location.location_id, location_id, "vị trí")
    db.query(models.Book).filter(models.Book.location_id == location_id).update({"location_id": None})
    db.delete(loc)
    _commit_or_rollback(db)
    return {"message": "Xóa vị trí thành công", "location_id": location_id}


# ==============================================================================
# Registration & PayOS Payment
# ==============================================================================
@app.post("/api/register", response_model=schemas.RegistrationRequestResponse)
def register_user(req_in: schemas.RegistrationRequestCreate, db: Session = Depends(get_db)):
    # 1. Kiểm tra trùng lặp
    existing = db.query(models.RegistrationRequest).filter(
        models.RegistrationRequest.user_code == req_in.user_code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Mã sinh viên này đã đăng ký rồi!")

    # 2. Lưu vào DB
    try:
        new_req = models.RegistrationRequest(**req_in.model_dump())
        db.add(new_req)
        db.commit()
        db.refresh(new_req)

        # Tạo mã đơn hàng duy nhất cho PayOS
        order_code = int(f"{int(time.time())}") 
        new_req.payos_order_code = order_code
        db.commit()

        # 3. Gọi PayOS (Đây là đoạn dễ lỗi nhất nếu thiếu Environment Variables)
        try:
            payment_request = CreatePaymentLinkRequest(
                order_code=order_code,
                amount=CARD_FEE,
                description=f"DK {new_req.user_code}"[:25],
                items=[ItemData(name=f"SmartLib {new_req.user_code}", quantity=1, price=CARD_FEE)],
                return_url=f"{BACKEND_URL}/payment-success",
                cancel_url=f"{BACKEND_URL}/payment-success",
            )
            payos_response = payos_client.payment_requests.create(payment_request)
            
            # Trả về kết quả
            return {
                "request_id": new_req.request_id,
                "user_code": new_req.user_code,
                "full_name": new_req.full_name,
                "request_status": new_req.request_status,
                "checkoutUrl": payos_response.checkout_url
            }
        except Exception as payos_err:
            # Nếu PayOS lỗi, chúng ta vẫn trả về 200 nhưng kèm thông báo lỗi để debug
            print(f"PayOS Error: {str(payos_err)}")
            raise HTTPException(status_code=400, detail=f"Lỗi kết nối PayOS: {str(payos_err)}. Hãy kiểm tra Client ID/API Key trên Render!")

    except Exception as db_err:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Lỗi Database: {str(db_err)}")



@app.post("/api/payos-webhook")
def payos_webhook(payload: dict, db: Session = Depends(get_db)):
    """Nhận thông báo thanh toán thành công từ PayOS."""
    try:
        order_code = payload.get("data", {}).get("orderCode")
        if order_code:
            req = db.query(models.RegistrationRequest).filter(
                models.RegistrationRequest.payos_order_code == order_code
            ).first()
            if req:
                req.payment_status = "paid"
                db.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/payment-success", response_class=HTMLResponse)
def payment_success_page():
    """Trang xác nhận thanh toán thành công, hiện ra sau khi chuyển khoản."""
    return """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Thanh toán SmartLib</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', sans-serif;
      background: #FFF7DD;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .card {
      background: white;
      border-radius: 20px;
      box-shadow: 0 8px 30px rgba(128,161,186,0.2);
      padding: 50px 40px;
      max-width: 480px;
      width: 100%;
      text-align: center;
    }
    .icon { font-size: 72px; margin-bottom: 20px; }
    h1 { color: #91C4C3; font-size: 28px; margin-bottom: 16px; }
    p { color: #80A1BA; font-size: 16px; line-height: 1.7; margin-bottom: 10px; }
    .note { font-size: 13px; color: #ccc; margin-top: 24px; }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">✅</div>
    <h1>Giao dịch hoàn tất!</h1>
    <p>Yêu cầu đăng ký thẻ <strong>SmartLib</strong> của bạn đã được tiếp nhận.</p>
    <p>📩 Vui lòng quay lại ứng dụng và chờ <strong>email xác nhận</strong> phê duyệt từ thư viện.</p>
    <p class="note">Bạn có thể đóng cửa sổ trình duyệt này.</p>
  </div>
</body>
</html>"""
