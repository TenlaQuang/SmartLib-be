from database import SessionLocal
import models
from sqlalchemy import text

def clear_all_data():
    db = SessionLocal()
    try:
        print("Đang xoá dữ liệu bảng books...")
        db.query(models.Book).delete()
        print("Đang xoá dữ liệu bảng locations...")
        db.query(models.Location).delete()
        print("Đang xoá dữ liệu bảng categories...")
        db.query(models.Category).delete()
        
        # Reset ID sequence in PostgreSQL (Neon)
        db.execute(text("ALTER SEQUENCE books_book_id_seq RESTART WITH 1;"))
        db.execute(text("ALTER SEQUENCE locations_location_id_seq RESTART WITH 1;"))
        db.execute(text("ALTER SEQUENCE categories_category_id_seq RESTART WITH 1;"))
        
        db.commit()
        print("--- THÀNH CÔNG: Đã xoá toàn bộ dữ liệu sách, kệ và danh mục! ---")
    except Exception as e:
        db.rollback()
        print(f"Lỗi khi xoá: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    clear_all_data()
