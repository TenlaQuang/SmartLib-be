from sqlalchemy import text
from database import SessionLocal

def upgrade_db():
    db = SessionLocal()
    try:
        print("Upgrading 'books' table structure...")
        # Add missing columns
        db.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS description TEXT"))
        db.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS pages INTEGER"))
        db.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS position_in_row INTEGER"))
        db.commit()
        print("Success: DB Upgraded!")
    except Exception as e:
        db.rollback()
        print(f"Error during upgrade: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    upgrade_db()
