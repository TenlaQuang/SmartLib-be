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
        
        print("Creating 'notifications' table if not exists...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id SERIAL PRIMARY KEY,
                user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                type VARCHAR(50) NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications(user_id, is_read)"))
        db.commit()
        print("Success: DB Upgraded!")
    except Exception as e:
        db.rollback()
        print(f"Error during upgrade: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    upgrade_db()
