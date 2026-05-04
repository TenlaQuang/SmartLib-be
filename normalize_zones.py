from sqlalchemy import text
from database import SessionLocal

def normalize_zones():
    db = SessionLocal()
    try:
        print("Normalizing Zone names in database...")
        # Cập nhật các tên khu vực thiếu chữ "Khu"
        db.execute(text("UPDATE locations SET zone_name = 'Khu C' WHERE zone_name = 'C'"))
        db.execute(text("UPDATE locations SET zone_name = 'Khu D' WHERE zone_name = 'D'"))
        db.execute(text("UPDATE locations SET zone_name = 'Khu E' WHERE zone_name = 'E'"))
        db.commit()
        print("Success: All zones normalized to 'Khu A-E'!")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    normalize_zones()
