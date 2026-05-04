from sqlalchemy import text
from database import SessionLocal

def delete_unshelved_books():
    db = SessionLocal()
    try:
        print("Searching and deleting books waiting to be shelved (location_id is NULL)...")
        # Tìm các cuốn sách không có location_id
        result = db.execute(text("DELETE FROM books WHERE location_id IS NULL"))
        db.commit()
        print(f"Success: Deleted {result.rowcount} unshelved books!")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    delete_unshelved_books()
