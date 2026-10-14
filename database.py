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
    """Ensure additive columns (framework_id, year, division) exist on legacy databases."""
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    
    with engine.begin() as connection:
        if "subjects" in table_names:
            sub_cols = {column["name"] for column in inspector.get_columns("subjects")}
            if "framework_id" not in sub_cols:
                connection.execute(text("ALTER TABLE subjects ADD COLUMN framework_id INTEGER"))
            if "year" not in sub_cols:
                connection.execute(text("ALTER TABLE subjects ADD COLUMN year VARCHAR(10) DEFAULT 'BE'"))
            if "division" not in sub_cols:
                connection.execute(text("ALTER TABLE subjects ADD COLUMN division VARCHAR(20) DEFAULT 'All'"))

        if "ai_mapping_results" in table_names:
            ai_cols = {column["name"] for column in inspector.get_columns("ai_mapping_results")}
            if "division" not in ai_cols:
                connection.execute(text("ALTER TABLE ai_mapping_results ADD COLUMN division VARCHAR(20) DEFAULT 'All'"))

        if "reference_mappings" in table_names:
            ref_cols = {column["name"] for column in inspector.get_columns("reference_mappings")}
            if "division" not in ref_cols:
                connection.execute(text("ALTER TABLE reference_mappings ADD COLUMN division VARCHAR(20) DEFAULT 'All'"))

        if "mapping_evaluations" in table_names:
            eval_cols = {column["name"] for column in inspector.get_columns("mapping_evaluations")}
            if "division" not in eval_cols:
                connection.execute(text("ALTER TABLE mapping_evaluations ADD COLUMN division VARCHAR(20) DEFAULT 'All'"))

