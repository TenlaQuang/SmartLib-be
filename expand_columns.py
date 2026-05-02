from sqlalchemy import text
from database import SessionLocal

def expand_columns():
    db = SessionLocal()
    try:
        print("Expanding column limits in 'books' table...")
        # Mở rộng giới hạn độ dài cho các cột
        db.execute(text("ALTER TABLE books ALTER COLUMN title TYPE VARCHAR(1000)"))
        db.execute(text("ALTER TABLE books ALTER COLUMN author TYPE VARCHAR(1000)"))
        db.execute(text("ALTER TABLE books ALTER COLUMN image_url TYPE VARCHAR(2000)"))
        db.commit()
        print("Success: Column limits expanded!")
    except Exception as e:
        db.rollback()
        print(f"Error expanding columns: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    expand_columns()
