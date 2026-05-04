from sqlalchemy import text
from database import SessionLocal

def allow_duplicate_isbn():
    db = SessionLocal()
    try:
        print("Removing Unique constraint from ISBN to allow multiple copies...")
        # Gỡ bỏ ràng buộc UNIQUE trên cột isbn
        # Lưu ý: Tên ràng buộc thường là 'uq_books_isbn' hoặc tự tìm
        db.execute(text("ALTER TABLE books DROP CONSTRAINT IF EXISTS books_isbn_key"))
        db.execute(text("DROP INDEX IF EXISTS ix_books_isbn"))
        db.execute(text("CREATE INDEX ix_books_isbn ON books (isbn)"))
        db.commit()
        print("Success: ISBN is no longer unique. Multiple copies allowed!")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    allow_duplicate_isbn()
