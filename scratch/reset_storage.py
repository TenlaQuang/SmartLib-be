import sys
import os
from sqlalchemy import text

# Thêm đường dẫn hiện tại vào sys.path
sys.path.append(os.getcwd())

from database import SessionLocal, engine, Base
import models

def reset_and_seed():
    print("--- DROPPING ALL TABLES WITH CASCADE ---")
    with engine.connect() as conn:
        # Tắt check foreign key hoặc dùng CASCADE cho Postgres
        conn.execute(text("DROP TABLE IF EXISTS wallet_transactions CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS transactions CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS import_logs CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS books CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS locations CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS registration_requests CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS nfc_inventory CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS users CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS categories CASCADE;"))
        conn.commit()
    
    print("Recreating tables with new schema...")
    Base.metadata.create_all(bind=engine)
    print("Schema synced and all data cleared.")

    db = SessionLocal()
    try:
        print("--- Creating new structure (5 Zones x 3 Shelves x 3 Rows) ---")
        zones = ["Khu A", "Khu B", "Khu C", "Khu D", "Khu E"]
        locations_added = 0

        for zone in zones:
            for shelf_idx in range(1, 4): # Shelf 1, 2, 3
                for row_idx in range(1, 4): # Row 1, 2, 3
                    new_loc = models.Location(
                        zone_name=zone,
                        shelf_id=f"Ke {shelf_idx}",
                        level_number=row_idx,
                        max_capacity=50,
                        description=f"{zone} - Ke {shelf_idx} - Hang {row_idx}"
                    )
                    db.add(new_loc)
                    locations_added += 1
        
        db.commit()
        print(f"Success! Created {locations_added} fixed locations.")
        print("Max capacity set to 50 books per row.")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_and_seed()
