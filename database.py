import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://attainment:1234@localhost:3306/co_po_attainment"
)

engine = create_engine(
    DATABASE_URL,
    echo=False
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def ensure_schema_compatibility():
    """Add the one additive column needed by installations created before v2.

    New tables are handled by ``create_all``.  This intentionally avoids a
    destructive migration and keeps existing courses usable.
    """
    inspector = inspect(engine)
    if "subjects" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("subjects")}
    if "framework_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE subjects ADD COLUMN framework_id INTEGER"))
