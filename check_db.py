import os, sqlalchemy
from dotenv import load_dotenv
load_dotenv()
engine = sqlalchemy.create_engine(os.getenv('DATABASE_URL'))
with engine.connect() as conn:
    res = conn.execute(sqlalchemy.text("SELECT column_name FROM information_schema.columns WHERE table_name = 'transactions'")).fetchall()
    print(res)
