from database import SessionLocal
import models
from sqlalchemy import func

def check_db():
    db = SessionLocal()
    try:
        loc_count = db.query(models.Location).count()
        print(f"--- Số lượng Location (Kệ sách): {loc_count} ---")
        
        locations = db.query(models.Location).limit(10).all()
        for l in locations:
            book_cnt = db.query(models.Book).filter(models.Book.location_id == l.location_id).count()
            print(f"LocID: {l.location_id} | Zone: {l.zone_name} | Shelf: {l.shelf_id} | Level: {l.level_number} | Số sách đang nằm trên kệ: {book_cnt}")

        book_count = db.query(models.Book).count()
        print(f"\n--- Tổng số sách: {book_count} ---")
        null_loc_books = db.query(models.Book).filter(models.Book.location_id == None).count()
        print(f"Số sách chờ xếp (location_id=NULL): {null_loc_books}")

    finally:
        db.close()

if __name__ == "__main__":
    check_db()
