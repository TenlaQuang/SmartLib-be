from sqlalchemy import text
from database import SessionLocal

def fix_datatype():
    db = SessionLocal()
    try:
        print("Converting 'deposit_required' from Numeric to Boolean...")
        # Chuyển đổi kiểu dữ liệu và ép kiểu các giá trị cũ (nếu có)
        db.execute(text("ALTER TABLE books ALTER COLUMN deposit_required TYPE BOOLEAN USING (deposit_required::boolean)"))
        db.commit()
        print("Success: Datatype updated to Boolean!")
    except Exception as e:
        db.rollback()
        # Nếu cột chưa có hoặc lỗi khác, thử cách an toàn hơn
        try:
            print("Trying fallback: Drop and Re-create column...")
            db.execute(text("ALTER TABLE books DROP COLUMN IF EXISTS deposit_required"))
            db.execute(text("ALTER TABLE books ADD COLUMN deposit_required BOOLEAN DEFAULT TRUE"))
            db.commit()
            print("Success: Column re-created as Boolean!")
        except Exception as e2:
            db.rollback()
            print(f"Final error: {e2}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_datatype()
