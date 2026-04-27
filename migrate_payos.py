import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL not found in .env")
    exit(1)

# Ensure URL works with SQLAlchemy
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

try:
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        print("Adding payment_status column...")
        conn.execute(text("ALTER TABLE registration_requests ADD COLUMN IF NOT EXISTS payment_status VARCHAR(20) DEFAULT 'pending';"))
        
        print("Adding payos_order_code column...")
        conn.execute(text("ALTER TABLE registration_requests ADD COLUMN IF NOT EXISTS payos_order_code BIGINT UNIQUE;"))
        
    print("Database updated successfully!")
except Exception as e:
    print(f"Failed to update database: {e}")
