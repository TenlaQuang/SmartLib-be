# ==============================================================================
# SmartLib API - FastAPI Backend
# ==============================================================================
import os
import io
import time
import random
import smtplib
from typing import List
from email.mime.text import MIMEText

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
# Cau hinh dich vu ben ngoai
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
CARD_FEE = int(os.getenv("CARD_FEE", "10000"))  # Phi lam the (VND)

# ==============================================================================
# Khoi tao ung dung
# ==============================================================================
app = FastAPI(title="SmartLib API", version="2.0.0")

# Tao thu muc static neu chua co (can thiet tren Render)
static_dir = "static/images"
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.middleware("http")
async def add_cors_header(request, call_next):
    # Xu ly cac request OPTIONS (Preflight)
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
# Email Helper
# ==============================================================================
def send_email_notification(to_email: str, subject: str, body: str):
    """
    Gui email thong bao den sinh vien khi duyet hoac tu choi don dang ky.
    Can cau hinh SMTP_EMAIL va SMTP_PASSWORD trong .env / Render Environment.
    """
    sender_email = os.getenv("SMTP_EMAIL")
    sender_password = os.getenv("SMTP_PASSWORD")
    if not sender_email or not sender_password:
        print(f"[WARN] Chua cau hinh SMTP_EMAIL/SMTP_PASSWORD. Skip gui email toi {to_email}.")
        print(f"  Tieu de: {subject}\n  Noi dung: {body}")
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
            print(f"[OK] Da gui email thanh cong toi {to_email}")
    except Exception as e:
        print(f"[ERROR] Loi khi gui email toi {to_email}: {e}")

# ==============================================================================
# Utility helpers
# ==============================================================================
def _generate_isbn(db: Session) -> str:
    """Tao ISBN-13 hop le va chua ton tai trong DB."""
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
        raise HTTPException(status_code=404, detail=f"Khong tim thay {label}")
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
        return {"status": "ok", "message": "Ket noi Database thanh cong!"}
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
    return _get_or_404(db, models.Book, models.Book.book_id, book_id, "sach")


@app.post("/api/books", response_model=schemas.BookResponse)
def create_book(book_in: schemas.BookCreate, db: Session = Depends(get_db)):
    new_book = models.Book(**book_in.model_dump())
    db.add(new_book)
    _commit_or_rollback(db)
    db.refresh(new_book)
    return new_book


@app.put("/api/books/{book_id}", response_model=schemas.BookResponse)
def update_book(book_id: int, book_in: schemas.BookUpdate, db: Session = Depends(get_db)):
    book = _get_or_404(db, models.Book, models.Book.book_id, book_id, "sach")
    for key, value in book_in.model_dump(exclude_unset=True).items():
        setattr(book, key, value)
    _commit_or_rollback(db)
    db.refresh(book)
    return book


@app.delete("/api/books/{book_id}")
def delete_book(book_id: int, db: Session = Depends(get_db)):
    book = _get_or_404(db, models.Book, models.Book.book_id, book_id, "sach")
    db.delete(book)
    _commit_or_rollback(db)
    return {"message": "Xoa sach thanh cong", "book_id": book_id}


@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...)):
    try:
        result = cloudinary.uploader.upload(await file.read(), folder="smartlib_books")
        return {"image_url": result.get("secure_url")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload that bai: {str(e)}")


@app.post("/api/books/import-excel")
async def import_books_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Nhap sach hang loat tu Excel. Cot bat buoc: title, market_price. Tuy chon: quantity."""
    try:
        df = pd.read_excel(io.BytesIO(await file.read()))
        for col in ["title", "market_price"]:
            if col not in df.columns:
                raise HTTPException(status_code=400, detail=f"File thieu cot: {col}")

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
        return {"message": f"Nhap thanh cong {count} cuon sach."}
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
    loc = _get_or_404(db, models.Location, models.Location.location_id, location_id, "vi tri")
    for key, value in loc_in.model_dump(exclude_unset=True).items():
        setattr(loc, key, value)
    _commit_or_rollback(db)
    db.refresh(loc)
    return loc


@app.delete("/api/locations/{location_id}")
def delete_location(location_id: int, db: Session = Depends(get_db)):
    loc = _get_or_404(db, models.Location, models.Location.location_id, location_id, "vi tri")
    db.query(models.Book).filter(models.Book.location_id == location_id).update({"location_id": None})
    db.delete(loc)
    _commit_or_rollback(db)
    return {"message": "Xoa vi tri thanh cong", "location_id": location_id}


# ==============================================================================
# Registration & PayOS Payment
# ==============================================================================
@app.post("/api/register", response_model=schemas.RegistrationRequestResponse)
def register_user(req_in: schemas.RegistrationRequestCreate, db: Session = Depends(get_db)):
    # 1. Kiem tra trung lap
    existing = db.query(models.RegistrationRequest).filter(
        models.RegistrationRequest.user_code == req_in.user_code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ma sinh vien nay da dang ky roi!")

    # 2. Luu vao DB
    try:
        new_req = models.RegistrationRequest(**req_in.model_dump())
        db.add(new_req)
        db.commit()
        db.refresh(new_req)

        # Tao ma don hang duy nhat cho PayOS
        order_code = int(f"{int(time.time())}")
        new_req.payos_order_code = order_code
        db.commit()

        # 3. Goi PayOS
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

            return {
                "request_id": new_req.request_id,
                "user_code": new_req.user_code,
                "full_name": new_req.full_name,
                "request_status": new_req.request_status,
                "checkoutUrl": payos_response.checkout_url
            }
        except Exception as payos_err:
            print(f"PayOS Error: {str(payos_err)}")
            raise HTTPException(status_code=400, detail=f"Loi PayOS: {str(payos_err)}. Hay kiem tra Client ID/API Key tren Render!")

    except Exception as db_err:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Loi Database: {str(db_err)}")


@app.post("/api/payos-webhook")
def payos_webhook(payload: dict, db: Session = Depends(get_db)):
    """Nhan thong bao thanh toan thanh cong tu PayOS."""
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


# ==============================================================================
# Registration - Duyet don / Tu choi
# ==============================================================================
@app.get("/api/registration-requests", response_model=List[schemas.RegistrationRequestResponse])
def get_registration_requests(db: Session = Depends(get_db)):
    """Lay danh sach cac don dang ky dang cho duyet."""
    return db.query(models.RegistrationRequest).filter(
        models.RegistrationRequest.request_status == "pending"
    ).all()


@app.post("/api/registration-requests/{request_id}/approve")
def approve_registration_request(
    request_id: int,
    payload: schemas.RegistrationApprove,
    db: Session = Depends(get_db)
):
    """Duyet don dang ky, tao User moi voi the NFC."""
    req = db.query(models.RegistrationRequest).filter(
        models.RegistrationRequest.request_id == request_id
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Khong tim thay don dang ky.")
    if req.request_status != "pending":
        raise HTTPException(status_code=400, detail=f"Don nay da duoc xu ly ({req.request_status}).")

    # Kiem tra xem NFC nay da duoc gan cho user nao chua
    existing_nfc = db.query(models.User).filter(
        models.User.nfc_tag_id == payload.nfc_serial
    ).first()
    if existing_nfc:
        raise HTTPException(status_code=400, detail="The NFC nay da duoc gan cho mot nguoi dung khac.")

    try:
        req.request_status = "approved"

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

        # Gui Email thong bao
        if req.email:
            body = (
                f"Chao {req.full_name},\n\n"
                f"Don dang ky lam the muon sach thu vien cua ban DA DUOC DUYET.\n"
                f"Tai khoan cua ban da duoc lien ket voi the NFC mang so serial: {payload.nfc_serial}.\n\n"
                f"Vui long den quay thu thu de nhan the vat ly.\n\n"
                f"Tran trong,\nBan Quan Tri Thu Vien."
            )
            send_email_notification(req.email, "Thong Bao Duyet Dang Ky Thu Vien", body)

        return {"message": "Da duyet va tao nguoi dung thanh cong"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/registration-requests/{request_id}/reject")
def reject_registration_request(
    request_id: int,
    payload: schemas.RegistrationReject,
    db: Session = Depends(get_db)
):
    """Tu choi don dang ky."""
    req = db.query(models.RegistrationRequest).filter(
        models.RegistrationRequest.request_id == request_id
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Khong tim thay don dang ky.")
    if req.request_status != "pending":
        raise HTTPException(status_code=400, detail=f"Don nay da duoc xu ly ({req.request_status}).")

    try:
        req.request_status = "rejected"
        db.commit()

        # Gui Email tu choi
        if req.email:
            body = (
                f"Chao {req.full_name},\n\n"
                f"Rat tiec, don dang ky thu vien cua ban bi TU CHOI.\n"
                f"Ly do: {payload.reason}\n\n"
                f"Vui long lien he thu thu de duoc lam thu tuc hoan tien (neu co).\n\n"
                f"Tran trong,\nBan Quan Tri Thu Vien."
            )
            send_email_notification(req.email, "Thong Bao Tu Choi Dang Ky Thu Vien", body)

        return {"message": "Da tu choi don dang ky"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# Users
# ==============================================================================
@app.get("/api/users", response_model=List[schemas.UserResponse])
def get_users(db: Session = Depends(get_db)):
    """Lay danh sach tat ca nguoi dung da duoc phe duyet."""
    return db.query(models.User).all()


# ==============================================================================
# Payment success page
# ==============================================================================
@app.get("/payment-success", response_class=HTMLResponse)
def payment_success_page():
    """Trang xac nhan thanh toan thanh cong, hien ra sau khi chuyen khoan."""
    return """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Thanh toan SmartLib</title>
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
    <h1>Giao dich hoan tat!</h1>
    <p>Yeu cau dang ky the <strong>SmartLib</strong> cua ban da duoc tiep nhan.</p>
    <p>📩 Vui long quay lai ung dung va cho <strong>email xac nhan</strong> phe duyet tu thu vien.</p>
    <p class="note">Ban co the dong cua so trinh duyet nay.</p>
  </div>
</body>
</html>"""
