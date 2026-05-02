from sqlalchemy import text
from database import SessionLocal, engine
import models

def check_locations():
    db = SessionLocal()
    try:
        # Check locations table
        result = db.execute(text("SELECT zone_name, shelf_id, level_number FROM locations LIMIT 20")).fetchall()
        print("--- Locations in DB ---")
        if not result:
            print("No locations found in database!")
        for row in result:
            print(f"Zone: {row[0]}, Shelf: {row[1]}, Level: {row[2]}")
            
        # Check total count
        count = db.query(models.Location).count()
        print(f"\nTotal Location Records: {count}")

        # Check books table count
        book_count = db.query(models.Book).count()
        print(f"Total books: {book_count}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_locations()
