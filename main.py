import os
import logging
import warnings

# Suppress Python 3.9 EOL and google-generativeai migration FutureWarnings on startup
warnings.filterwarnings("ignore", category=FutureWarning)

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from database import Base, engine, ensure_schema_compatibility
from routers import subjects, mapping, excel, frameworks, pdf

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# Create all database tables
Base.metadata.create_all(bind=engine)
ensure_schema_compatibility()

# Create FastAPI app
app = FastAPI(
    title="AI CO-PO Mapping Agent",
    description=(
        "AI-powered system for generating, reviewing, and evaluating "
        "CO-PO/PSO mappings using a hybrid embedding + LLM pipeline."
    ),
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")
TEMPLATE_DIR = os.path.join(FRONTEND_DIR, "templates")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATE_DIR, exist_ok=True)
os.makedirs(os.path.join(os.path.dirname(__file__), "uploads"), exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# Register API routers
app.include_router(subjects.router)
app.include_router(mapping.router)
app.include_router(excel.router)
app.include_router(frameworks.router)
app.include_router(pdf.router)


@app.get("/")
async def home(request: Request):
    """Serve the main frontend application."""
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    vector_stats = None
    try:
        from ai.vector_store import get_vector_store_stats
        vector_stats = get_vector_store_stats()
    except Exception:
        pass

    return {
        "status": "running",
        "app": "AI CO-PO Mapping Agent",
        "mock_mode": os.getenv("MOCK_MODE", "true").lower() == "true",
        "vector_store": vector_stats,
    }
