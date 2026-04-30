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
@app.get("/")
def read_root():
    return {"message": "SmartLib API v2.1 - Online", "status": "ok"}


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
def get_book_title_groups(db: Session = Depends(get_db)):
    """Trả về danh sách NHÓM ĐẦU SÁCH (gom theo title)."""
    books = db.query(models.Book).all()
    groups = {}
    for book in books:
        key = book.title
        if key not in groups:
            groups[key] = {"title": book.title, "image_url": book.image_url, "total_copies": 0, "copies_waiting": 0, "copies_on_shelf": 0, "locations": {}}
        groups[key]["total_copies"] += 1
        if book.location_id is None:
            groups[key]["copies_waiting"] += 1
        else:
            groups[key]["copies_on_shelf"] += 1
            loc = book.location
            if loc:
                loc_label = f"Khu {loc.zone_name} - {loc.shelf_id}" + (f" (Tầng {loc.level_number})" if loc.level_number else "")
                groups[key]["locations"][loc_label] = groups[key]["locations"].get(loc_label, 0) + 1
    result = []
    for title, g in groups.items():
        result.append({"title": g["title"], "image_url": g["image_url"], "total_copies": g["total_copies"], "copies_waiting": g["copies_waiting"], "copies_on_shelf": g["copies_on_shelf"], "location_summary": [{"location": k, "count": v} for k, v in g["locations"].items()]})
    return result


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


@app.post("/api/register", response_model=schemas.RegistrationRequestResponse)
def register_user(req_in: schemas.RegistrationRequestCreate, db: Session = Depends(get_db)):
    # 1. Kiểm tra trùng lặp
    existing = db.query(models.RegistrationRequest).filter(
        models.RegistrationRequest.user_code == req_in.user_code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Mã sinh viên này đã đăng ký rồi!")

    # 2. Lưu vào DB (Kèm theo ảnh bill và mã đơn hàng đã thanh toán)
    try:
        new_req = models.RegistrationRequest(**req_in.model_dump())
        db.add(new_req)
        db.commit()
        db.refresh(new_req)

        # Trả về kết quả
        return new_req

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
    return db.query(models.User).all()

@app.get("/api/registration-requests", response_model=List[schemas.RegistrationRequestResponse])
def get_registration_requests(db: Session = Depends(get_db)):
    """Lấy danh sách đơn đăng ký chờ duyệt."""
    return db.query(models.RegistrationRequest).filter(
        models.RegistrationRequest.request_status == 'pending'
    ).all()

import traceback

@app.post("/api/registration-requests/{request_id}/approve")
def approve_registration_request(request_id: int, db: Session = Depends(get_db)):
    """Phê duyệt đơn đăng ký."""
    req = db.query(models.RegistrationRequest).filter(models.RegistrationRequest.request_id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn.")
    if req.request_status != "pending":
        raise HTTPException(status_code=400, detail="Đơn đã xử lý.")
        
    try:
        req.request_status = "approved"
        
        # Kiểm tra xem User đã tồn tại chưa để tránh lỗi UniqueViolation
        existing_user = db.query(models.User).filter(models.User.user_code == req.user_code).first()
        if existing_user:
             # Nếu user đã tồn tại, có thể cập nhật thông tin hoặc báo lỗi
             # Ở đây ta báo lỗi cụ thể để thủ thư biết
             raise Exception(f"Mã sinh viên {req.user_code} đã tồn tại trong hệ thống người dùng chính thức.")

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
            if has_nfc:
                body = (f"Chào {req.full_name},\n\n"
                        f"Tài khoản SmartLib của bạn đã được khởi tạo thành công.\n"
                        f"Thẻ vật lý của bạn đã được liên kết với hệ thống.\n\n"
                        f"Trân trọng.")
                send_email_notification(req.email, "Đăng ký thành công", body)
            else:
                body = (f"Chào {req.full_name},\n\n"
                        f"Đơn đăng ký thẻ SmartLib của bạn đã được duyệt!\n"
                        f"Tuy nhiên, bạn chưa có thẻ NFC. Vui lòng đến thư viện trong thời gian sớm nhất để được cấp thẻ vật lý và liên kết tài khoản.\n\n"
                        f"Trân trọng.")
                send_email_notification(req.email, "Đăng ký thành công - Vui lòng nhận thẻ", body)

        return {"message": "Đã duyệt thành công"}
    except Exception as e:
        db.rollback()
        print("LỖI DUYỆT ĐƠN:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")

@app.post("/api/registration-requests/{request_id}/reject")
def reject_registration_request(request_id: int, payload: schemas.RegistrationReject, db: Session = Depends(get_db)):
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
            body = (f"Chào {req.full_name},\n\n"
                    f"Đơn đăng ký của bạn TỪ CHỐI.\n"
                    f"Lý do: {payload.reason}\n\n"
                    f"Vui lòng liên hệ thủ thư.\n"
                    f"Trân trọng,")
            send_email_notification(req.email, "Thông Báo Từ Chối Thư Viện", body)
            
        return {"message": "Đã từ chối đơn thành công"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/users/{user_id}/reissue-nfc")
def reissue_nfc_card(user_id: int, payload: schemas.RegistrationApproveWithTag, db: Session = Depends(get_db)):
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
            body = (f"Chào {user.full_name},\n\n"
                    f"Thẻ của bạn đã được thay mới vì mất cấp lại.\n"
                    f"Mã đánh dấu thẻ vật lý của bạn là: {tag.label}.\n\n"
                    f"Trân trọng.")
            send_email_notification(user.email, "Gán NFC Thẻ Mới Thành Công", body)
            
        return {"message": "Đã cấp lại thành công thẻ từ kho"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users/{user_id}/assign-nfc")
def assign_nfc_to_user(user_id: int, payload: schemas.AssignNFC, db: Session = Depends(get_db)):
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
            body = (f"Chào {user.full_name},\n\n"
                    f"Tài khoản SmartLib của bạn đã được liên kết thành công với thẻ vật lý NFC.\n"
                    f"Bạn đã có thể sử dụng đầy đủ các dịch vụ mượn sách.\n"
                    f"Trân trọng.")
            send_email_notification(user.email, "Kích hoạt Thẻ NFC Thành Công", body)
            
        return {"message": "Đã gán thẻ thành công"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
@app.post("/api/users/{user_id}/remind-nfc")
def remind_nfc_pickup(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy user")
        
    if user.status != "pending_nfc":
        raise HTTPException(status_code=400, detail="User này đã có thẻ.")
        
    try:
        if user.email:
            body = (f"Chào {user.full_name},\n\n"
                    f"Đây là lời nhắc nhở từ thư viện.\n"
                    f"Tài khoản SmartLib của bạn đã được duyệt nhưng bạn vẫn CHƯA đến nhận thẻ vật lý.\n"
                    f"Vui lòng đến quầy thủ thư để nhận thẻ và kích hoạt dịch vụ.\n\n"
                    f"Trân trọng.")
            send_email_notification(user.email, "Nhắc nhở: Lên nhận thẻ thư viện", body)
            
        return {"message": "Đã gửi email nhắc nhở"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))