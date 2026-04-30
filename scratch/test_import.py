import pandas as pd
import sys
import os

# Cấu hình
CSV_PATH = r"c:\Users\ADMIN\Documents\doanchuyennganh\SmartLibAdmin\library_data_final.csv"
sys.path.append(r"c:\Users\ADMIN\Documents\doanchuyennganh\SmartLib-be")
from database import SessionLocal
import models
from sqlalchemy.orm import Session

def test_import():
    db = SessionLocal()
    zone_map = {"K1": "A", "K2": "B", "K3": "C", "K4": "D", "K5": "E"}
    
    df = pd.read_csv(CSV_PATH, nrows=10)
    for i, row in df.iterrows():
        try:
            print(f"Testing row {i}: {row['title']}")
            genre_name = str(row.get("genre", "Chưa phân loại")).strip()
            category = db.query(models.Category).filter(models.Category.name == genre_name).first()
            if not category:
                category = models.Category(name=genre_name)
                db.add(category)
                db.flush()
            
            loc_id = None
            loc_code = str(row.get("location_code", ""))
            if loc_code and "-" in loc_code:
                parts = loc_code.split("-")
                z_code = zone_map.get(parts[0])
                s_id = parts[1].replace("T", "Kệ ")
                l_num = int(parts[2].replace("H", "")) if len(parts) > 2 else 1
                
                location = db.query(models.Location).filter(
                    models.Location.zone_name == z_code,
                    models.Location.shelf_id == s_id,
                    models.Location.level_number == l_num
                ).first()
                if location:
                    loc_id = location.location_id

            book = models.Book(
                isbn=str(row["isbn"]),
                title=str(row["title"]),
                author=str(row["author"]),
                image_url=str(row.get("image_url", "")),
                category_id=category.category_id,
                location_id=loc_id,
                market_price=50000.0,
                status="available"
            )
            db.add(book)
            db.commit()
            print("Success")
        except Exception as e:
            print(f"Error at row {i}: {e}")
            db.rollback()

if __name__ == "__main__":
    test_import()
