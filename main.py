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
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from payos import PayOS
from payos.types import CreatePaymentLinkRequest, ItemData
from sqlalchemy import text, func
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
import email_utils

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
CARD_FEE = int(os.getenv("CARD_FEE", "10000"))  # Phí làm thẻ (VND)

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


import smtplib
from email.mime.text import MIMEText

# ==============================================================================
# Email Helper
# ==============================================================================
def send_email_notification(to_email: str, subject: str, body: str):
    """
    Guil email thong bao toi sinh vien khi phe duyet hoac tu choi.
    """
    sender_email = os.getenv("SMTP_EMAIL")
    sender_password = os.getenv("SMTP_PASSWORD")
    if not sender_email or not sender_password:
        return
        
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
    except Exception as e:
        print(f"SMTP Error: {e}")

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
@app.api_route("/", methods=["GET", "HEAD"])
def read_root():
    return {"message": "SmartLib API v2.1.2 - Online", "status": "ok"}


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


@app.get("/api/books/title-groups")
def get_book_title_groups(q: Optional[str] = None, category_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Trả về danh sách NHÓM ĐẦU SÁCH kèm thống kê Mượn/Trả và tìm kiếm."""
    query = db.query(models.Book)
    
    if q:
        search_filter = f"%{q}%"
        query = query.filter(
            (models.Book.title.ilike(search_filter)) | 
            (models.Book.author.ilike(search_filter)) |
            (models.Book.isbn.ilike(search_filter))
        )
    
    if category_id:
        query = query.filter(models.Book.category_id == category_id)

    books = query.all()
    groups = {}
    for book in books:
        key = book.isbn # Gom nhóm theo ISBN
        if key not in groups:
            groups[key] = {
                "isbn": book.isbn,
                "title": book.title, 
                "author": book.author,
                "image_url": book.image_url, 
                "total_copies": 0, 
                "available_count": 0,
                "borrowed_count": 0,
                "copies_waiting": 0, 
                "locations": {}
            }
        
        groups[key]["total_copies"] += 1
        
        # Thống kê trạng thái mượn trả
        if book.status == "borrowed":
            groups[key]["borrowed_count"] += 1
        else:
            groups[key]["available_count"] += 1

        # Thống kê vị trí xếp kệ
        if book.location_id is None:
            groups[key]["copies_waiting"] += 1
        else:
            loc = book.location
            if loc:
                loc_label = f"Khu {loc.zone_name} - {loc.shelf_id} - Tầng {loc.level_number}"
                groups[key]["locations"][loc_label] = groups[key]["locations"].get(loc_label, 0) + 1
                
    result = []
    for isbn, g in groups.items():
        result.append({
            "isbn": g["isbn"],
            "title": g["title"], 
            "author": g["author"],
            "image_url": g["image_url"], 
            "total_copies": g["total_copies"],
            "available_count": g["available_count"],
            "borrowed_count": g["borrowed_count"],
            "copies_waiting": g["copies_waiting"], 
            "location_summary": [{"location": k, "count": v} for k, v in g["locations"].items()]
        })
    return result


@app.get("/api/books/{book_id}", response_model=schemas.BookResponse)
def get_book(book_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, models.Book, models.Book.book_id, book_id, "sách")


@app.post("/api/books", response_model=schemas.BookResponse)
def create_book(book_in: schemas.BookCreate, db: Session = Depends(get_db)):
    # Kiểm tra sức chứa của vị trí
    if book_in.location_id:
        loc = db.query(models.Location).filter(models.Location.location_id == book_in.location_id).first()
        if loc:
            current_count = db.query(models.Book).filter(models.Book.location_id == book_in.location_id).count()
            if current_count >= loc.max_capacity:
                raise HTTPException(status_code=400, detail=f"Vị trí {loc.zone_name} - {loc.shelf_id} - Hàng {loc.level_number} đã đầy ({loc.max_capacity} cuốn).")

    new_book = models.Book(**book_in.model_dump())
    db.add(new_book)
    _commit_or_rollback(db)
    db.refresh(new_book)
    return new_book


@app.put("/api/books/{book_id}", response_model=schemas.BookResponse)
def update_book(book_id: int, book_in: schemas.BookUpdate, db: Session = Depends(get_db)):
    book = _get_or_404(db, models.Book, models.Book.book_id, book_id, "sách")
    
    # Nếu cập nhật vị trí mới, kiểm tra sức chứa
    if book_in.location_id and book_in.location_id != book.location_id:
        loc = db.query(models.Location).filter(models.Location.location_id == book_in.location_id).first()
        if loc:
            current_count = db.query(models.Book).filter(models.Book.location_id == book_in.location_id).count()
            if current_count >= loc.max_capacity:
                raise HTTPException(status_code=400, detail=f"Vị trí mới đã đầy ({loc.max_capacity} cuốn).")

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


@app.post("/api/books/assign-by-title")
def assign_books_by_title(payload: dict, db: Session = Depends(get_db)):
    """
    Xếp kệ TẤT CẢ bản sao đang chờ (location_id=null) của 1 tựa sách vào cùng 1 vị trí.
    Body: { "title": "...", "location_id": 5 }
    """
    title = payload.get("title")
    location_id = payload.get("location_id")
    
    if not title or not location_id:
        raise HTTPException(status_code=400, detail="Thiếu title hoặc location_id")
    
    loc = db.query(models.Location).filter(models.Location.location_id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Không tìm thấy vị trí kệ")
    
    waiting_books = db.query(models.Book).filter(
        models.Book.title == title,
        models.Book.location_id == None
    ).all()
    
    if not waiting_books:
        raise HTTPException(status_code=404, detail="Không có bản sao nào đang chờ kệ cho tựa sách này")
    
    count = len(waiting_books)
    for book in waiting_books:
        book.location_id = location_id
    
    db.commit()
    return {"message": f"Đã xếp {count} bản sao '{title}' lên kệ thành công."}




@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...)):
    try:
        result = cloudinary.uploader.upload(await file.read(), folder="smartlib_books")
        return {"image_url": result.get("secure_url")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload thất bại: {str(e)}")

@app.get("/api/categories")
def get_categories(db: Session = Depends(get_db)):
    return db.query(models.Category).all()

@app.post("/api/books/import-csv")
async def import_books_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Nhập sách hàng loạt từ file CSV/Excel của người dùng."""
    try:
        content = await file.read()
        filename = file.filename.lower()
        
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))

        # Các cột bắt buộc
        required = ["title", "author", "isbn"]
        for col in required:
            if col not in df.columns:
                raise HTTPException(status_code=400, detail=f"File thiếu cột bắt buộc: {col}")

        # Map Khu vực (K1 -> A, K2 -> B...)
        zone_map = {"K1": "A", "K2": "B", "K3": "C", "K4": "D", "K5": "E"}

        count = 0
        for _, row in df.iterrows():
            if pd.isna(row["title"]): continue
            
            # 1. Xử lý Thể loại (Genre)
            cat_id = None
            genre_name = str(row.get("genre", "Chưa phân loại")).strip()
            category = db.query(models.Category).filter(models.Category.name == genre_name).first()
            if not category:
                category = models.Category(name=genre_name)
                db.add(category)
                db.flush()
            cat_id = category.category_id

            # 2. Xử lý Vị trí (location_code: K1-T1-H1-V1)
            loc_id = None
            loc_code = str(row.get("location_code", ""))
            if loc_code and "-" in loc_code:
                parts = loc_code.split("-")
                # parts[0] = K1, parts[1] = T1, parts[2] = H1
                z_code = zone_map.get(parts[0])
                s_id = parts[1].replace("T", "Kệ ")
                l_num = int(parts[2].replace("H", "")) if len(parts) > 2 else 1
                
                location = db.query(models.Location).filter(
                    models.Location.zone_name == z_code,
                    models.Location.shelf_id == s_id,
                    models.Location.level_number == l_num
                ).first()
                if location:
                    loc_id = location.location_id

            # 3. Tạo sách
            db.add(models.Book(
                isbn=str(row["isbn"]),
                title=str(row["title"]),
                author=str(row["author"]),
                image_url=str(row.get("image_url", "")),
                category_id=cat_id,
                location_id=loc_id,
                market_price=50000, # Giá mặc định nếu ko có
                status="available"
            ))
            count += 1
            
        db.commit()
        return {"message": f"Đã nhập thành công {count} cuốn sách!", "count": count}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi khi nhập file: {str(e)}")


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
@app.post("/api/create-payment-link")
def create_payment_link(payload: schemas.PayosLinkCreate):
    """Tạo link thanh toán PayOS mà chưa lưu thông tin đăng ký vào DB."""
    order_code = int(f"{int(time.time())}") 
    try:
        payment_request = CreatePaymentLinkRequest(
            order_code=order_code,
            amount=CARD_FEE,
            description=f"DK {payload.user_code}"[:25],
            items=[ItemData(name=f"SmartLib {payload.user_code}", quantity=1, price=CARD_FEE)],
            return_url=f"{BACKEND_URL}/payment-success",
            cancel_url=f"{BACKEND_URL}/payment-success",
        )
        payos_response = payos_client.payment_requests.create(payment_request)
        return {
            "order_code": order_code,
            "checkoutUrl": payos_response.checkout_url
        }
    except Exception as payos_err:
        print(f"PayOS Error: {str(payos_err)}")
        raise HTTPException(status_code=400, detail=f"Lỗi kết nối PayOS: {str(payos_err)}. Hãy kiểm tra Client ID/API Key trên Render!")


@app.post("/api/register")
async def register_user(
    background_tasks: BackgroundTasks,
    user_code: str = Form(...),
    full_name: str = Form(...),
    gender: str = Form(...),
    birth_year: int = Form(...),
    phone_number: str = Form(...),
    address: str = Form(...),
    email: str = Form(...),
    payos_order_code: int = Form(0),
    nfc_serial: str = Form(None),
    invoice_image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    # 1. Kiểm tra trùng lặp
    existing = db.query(models.RegistrationRequest).filter(
        models.RegistrationRequest.user_code == user_code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Mã sinh viên này đã đăng ký rồi!")

    # 2. Lưu vào DB (Kèm theo ảnh bill và mã đơn hàng đã thanh toán)
    try:
        # Upload ảnh hóa đơn
        image_url = None
        if invoice_image:
            img_res = cloudinary.uploader.upload(await invoice_image.read(), folder="smartlib_invoices")
            image_url = img_res.get("secure_url")

        new_req = models.RegistrationRequest(
            user_code=user_code, full_name=full_name, gender=gender,
            birth_year=birth_year, phone_number=phone_number, address=address,
            email=email, nfc_serial=nfc_serial, invoice_image_url=image_url,
            payos_order_code=payos_order_code
        )
        db.add(new_req)
        db.commit()
        # Gửi email thông báo đã nhận đơn (Chạy ngầm)
        if email:
            html = email_utils.get_new_request_template(full_name, user_code)
            background_tasks.add_task(email_utils.send_html_email, email, "SmartLib - Đã nhận đơn đăng ký", html)

        # Trả về kết quả
        return {"message": "Đăng ký thành công, vui lòng chờ thủ thư duyệt đơn."}

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


# ==============================================================================

# ==============================================================================


# Users & Registration Approval
# ==============================================================================
@app.get("/api/users", response_model=List[schemas.UserResponse])
def get_users(db: Session = Depends(get_db)):
    """Lấy danh sách tất cả người dùng chính thức."""
    return db.query(models.User).order_by(models.User.created_at.desc()).all()

@app.put("/api/users/{user_id}", response_model=schemas.UserResponse)
def update_user(user_id: int, payload: schemas.UserUpdate, db: Session = Depends(get_db)):
    """Cập nhật thông tin người dùng."""
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    
    try:
        db.commit()
        db.refresh(user)
        return user
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Xóa người dùng (Lưu ý: Chỉ nên xóa nếu không có ràng buộc mượn trả)."""
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    
    try:
        db.delete(user)
        db.commit()
        return {"message": "Đã xóa người dùng thành công."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Không thể xóa người dùng này (có thể do ràng buộc dữ liệu).")

@app.get("/api/users/check/{user_code}")
def check_user_for_nfc(user_code: str, db: Session = Depends(get_db)):
    """Kiểm tra mã sinh viên để đăng ký thẻ NFC."""
    user = db.query(models.User).filter(models.User.user_code == user_code).first()
    if not user:
        return {
            "status": "not_found", 
            "message": "Mã sinh viên chưa đăng ký hoặc chưa được thư viện duyệt."
        }
    
    if user.nfc_tag_id:
        return {
            "status": "active", 
            "message": "Sinh viên này đã có thẻ NFC rồi.",
            "full_name": user.full_name
        }
    
    return {
        "status": "pending_nfc", 
        "message": "Thông tin hợp lệ. Vui lòng quẹt thẻ NFC để kích hoạt.",
        "user_id": user.user_id,
        "full_name": user.full_name
    }

@app.get("/api/registration-requests", response_model=List[schemas.RegistrationRequestResponse])
def get_registration_requests(db: Session = Depends(get_db)):
    """Lấy danh sách đơn đăng ký chờ duyệt."""
    return db.query(models.RegistrationRequest).filter(
        models.RegistrationRequest.request_status == 'pending'
    ).all()

@app.post("/api/registration-requests/{request_id}/approve")
def approve_registration_request(request_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Phê duyệt đơn đăng ký."""
    req = db.query(models.RegistrationRequest).filter(models.RegistrationRequest.request_id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn.")
    if req.request_status != "pending":
        raise HTTPException(status_code=400, detail="Đơn đã xử lý.")
        
    try:
        req.request_status = "approved"
        
        # Kiểm tra tồn tại để bảo vệ
        existing_user = db.query(models.User).filter(models.User.user_code == req.user_code).first()
        if existing_user:
             raise HTTPException(status_code=400, detail=f"Mã sinh viên {req.user_code} đã tồn tại trong hệ thống.")

        has_nfc = bool(req.nfc_serial)
        user_status = "active" if has_nfc else "pending_nfc"

        new_user = models.User(
            user_code=req.user_code,
            full_name=req.full_name,
            gender=req.gender,
            birth_year=req.birth_year,
            phone_number=req.phone_number,
            address=req.address,
            email=req.email,
            nfc_tag_id=req.nfc_serial if has_nfc else None,
            status=user_status
        )
        db.add(new_user)
        db.commit()

        if req.email:
            html = email_utils.get_approval_template(req.full_name, has_nfc)
            background_tasks.add_task(email_utils.send_html_email, req.email, "SmartLib - Duyệt đơn đăng ký thành công", html)

        return {"message": "Đã duyệt thành công"}
    except Exception as e:
        db.rollback()
        print(f"Lỗi duyệt đơn: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/registration-requests/{request_id}/reject")
def reject_registration_request(request_id: int, payload: schemas.RegistrationReject, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Từ chối đơn và gửi lý do cho sinh viên."""
    req = db.query(models.RegistrationRequest).filter(models.RegistrationRequest.request_id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đăng ký.")
    if req.request_status != "pending":
        raise HTTPException(status_code=400, detail="Đơn này đã được xử lý.")
        
    try:
        req.request_status = "rejected"
        db.commit()
        
        if req.email:
            html = email_utils.get_rejection_template(req.full_name, payload.reason)
            background_tasks.add_task(email_utils.send_html_email, req.email, "SmartLib - Thông báo kết quả đăng ký", html)
            
        return {"message": "Đã từ chối đơn thành công"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/users/{user_id}/reissue-nfc")
def reissue_nfc_card(user_id: int, payload: schemas.RegistrationApproveWithTag, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Cấp lại thẻ NFC mới từ kho chứa."""
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy user")
        
    tag = db.query(models.NfcTag).filter(models.NfcTag.tag_id == payload.tag_id, models.NfcTag.status == "available").first()
    if not tag:
        raise HTTPException(status_code=400, detail="Thẻ NFC không hợp lệ hoặc đã bị gán.")
        
    try:
        user.nfc_tag_id = tag.nfc_serial
        tag.status = "assigned"
        db.commit()
        
        if user.email:
            html = email_utils.get_reissue_nfc_template(user.full_name, tag.nfc_serial)
            background_tasks.add_task(email_utils.send_html_email, user.email, "SmartLib - Thông báo cấp lại thẻ NFC thành công", html)
            
        return {"message": "Đã cấp lại thành công thẻ từ kho"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users/{user_id}/assign-nfc")
def assign_nfc_to_user(user_id: int, payload: schemas.AssignNFC, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Gán mã NFC thẻ trắng cho người dùng chưa có thẻ."""
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy user")
        
    existing_nfc = db.query(models.User).filter(models.User.nfc_tag_id == payload.nfc_serial).first()
    if existing_nfc:
        raise HTTPException(status_code=400, detail="Thẻ NFC này đã được sử dụng bởi người khác.")
        
    try:
        user.nfc_tag_id = payload.nfc_serial
        user.status = "active"
        db.commit()
        
        if user.email:
            html = email_utils.get_reissue_nfc_template(user.full_name, payload.nfc_serial) # Dùng chung template reissue vì nội dung tương đương
            background_tasks.add_task(email_utils.send_html_email, user.email, "SmartLib - Thẻ của bạn đã được kích hoạt", html)
            
        return {"message": "Đã gán thẻ thành công"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users/{user_id}/remind-nfc")
def remind_nfc_pickup(user_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy user")
        
    if user.status != "pending_nfc":
        raise HTTPException(status_code=400, detail="User này đã có thẻ hoặc không ở trạng thái chờ nhận thẻ.")
        
    try:
        if user.email:
            html = email_utils.get_remind_nfc_template(user.full_name)
            background_tasks.add_task(email_utils.send_html_email, user.email, "Nhắc nhở: Lên nhận thẻ thư viện SmartLib", html)
            
        return {"message": "Đã gửi email nhắc nhở"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/{user_id}/activity", response_model=schemas.UserActivityResponse)
def get_user_activity(user_id: int, db: Session = Depends(get_db)):
    """Lấy thông tin mượn trả của sinh viên."""
    all_trans = db.query(models.Transaction).filter(models.Transaction.user_id == user_id).all()
    
    ongoing = []
    completed = []
    
    for t in all_trans:
        book = db.query(models.Book).filter(models.Book.book_id == t.book_id).first()
        res = schemas.TransactionResponse(
            transaction_id=t.transaction_id,
            book_title=book.title if book else "Không rõ",
            borrow_date=t.borrow_date,
            due_date=t.due_date,
            status=t.status
        )
        if t.status == "ongoing":
            ongoing.append(res)
        else:
            completed.append(res)
            
    return {
        "ongoing_count": len(ongoing),
        "ongoing_books": ongoing,
        "completed_count": len(completed),
        "history": completed
    }

@app.get("/api/locations", response_model=List[schemas.LocationWithCount])
def get_locations(db: Session = Depends(get_db)):
    """Lấy danh sách các kệ sách và thống kê sách độc nhất trên mỗi kệ."""
    locations = db.query(models.Location).order_by(models.Location.zone_name, models.Location.shelf_id, models.Location.level_number).all()
    result = []
    for loc in locations:
        # Tổng số lượng sách
        total_count = db.query(models.Book).filter(models.Book.location_id == loc.location_id).count()
        
        # Thống kê sách độc nhất (Unique Books)
        unique_books_query = db.query(
            models.Book.isbn,
            models.Book.title,
            models.Book.image_url,
            func.count(models.Book.book_id).label("count")
        ).filter(models.Book.location_id == loc.location_id).group_by(
            models.Book.isbn, models.Book.title, models.Book.image_url
        ).all()
        
        unique_books = [
            {"isbn": b.isbn, "title": b.title, "image_url": b.image_url, "count": b.count}
            for b in unique_books_query
        ]

        result.append({
            "location_id": loc.location_id,
            "zone_name": loc.zone_name,
            "shelf_id": loc.shelf_id,
            "level_number": loc.level_number,
            "max_capacity": loc.max_capacity,
            "book_count": total_count,
            "unique_books": unique_books
        })
    return result

@app.get("/api/shelves/{shelf_id}")
def get_shelf_details(shelf_id: str, db: Session = Depends(get_db)):
    """Lấy chi tiết phân tầng và sách trong một kệ cụ thể."""
    locations = db.query(models.Location).filter(models.Location.shelf_id == shelf_id).order_by(models.Location.level_number).all()
    
    result = []
    for loc in locations:
        books = db.query(models.Book).filter(models.Book.location_id == loc.location_id).all()
        result.append({
            "level_number": loc.level_number,
            "books": [
                {
                    "book_id": b.book_id,
                    "title": b.title,
                    "image_url": b.image_url,
                    "isbn": b.isbn
                } for b in books
            ]
        })
    return result

@app.post("/api/login-nfc")
def login_nfc(payload: schemas.AssignNFC, db: Session = Depends(get_db)):
    """Đăng nhập bằng thẻ NFC."""
    user = db.query(models.User).filter(models.User.nfc_tag_id == payload.nfc_serial).first()
    if not user:
        raise HTTPException(status_code=404, detail="Thẻ NFC này chưa được đăng ký trong hệ thống.")
    
    return {
        "status": "success",
        "message": f"Xin chào, {user.full_name}!",
        "user": {
            "user_id": user.user_id,
            "full_name": user.full_name,
            "user_code": user.user_code
        }
    }

@app.post("/api/users/{user_id}/lock-nfc")
def lock_user_nfc(user_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Khóa thẻ NFC từ xa (Dùng khi mất thẻ)."""
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    
    if not user.nfc_tag_id:
        raise HTTPException(status_code=400, detail="Người dùng này chưa có thẻ để khóa.")
    
    try:
        # Lưu lại mã thẻ cũ vào log nếu cần, ở đây ta chỉ cần đổi trạng thái
        user.status = "locked"
        # Ta không xóa nfc_tag_id ngay để biết thẻ nào bị khóa, nhưng status locked sẽ chặn mượn trả
        db.commit()
        
        if user.email:
            html = email_utils.get_lock_nfc_template(user.full_name)
            background_tasks.add_task(email_utils.send_html_email, user.email, "Cảnh báo: Thẻ SmartLib của bạn đã bị khóa", html)
            
        return {"message": "Đã khóa thẻ thành công"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))