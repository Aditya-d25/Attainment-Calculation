import os
import logging
import warnings

# Suppress Python 3.9 EOL and google-generativeai migration FutureWarnings on startup
warnings.filterwarnings("ignore", category=FutureWarning)

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

from database import Base, engine, ensure_schema_compatibility
from routers import subjects, mapping, excel, frameworks, pdf, auth

# Load environment variables
load_dotenv(override=True)

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
app.include_router(auth.router)
app.include_router(subjects.router)
app.include_router(mapping.router)
app.include_router(excel.router)
app.include_router(frameworks.router)
app.include_router(pdf.router)


@app.get("/login")
async def login_page(request: Request):
    """Serve the glassmorphic login page with Google gateway."""
    user = auth.get_current_user_from_request(request)
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "google_client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        },
    )


@app.get("/")
async def home(request: Request):
    """Serve the main frontend application."""
    user = auth.get_current_user_from_request(request)
    guest_mode = request.query_params.get("guest") == "1"

    if not user and not guest_mode:
        accept = request.headers.get("accept", "")
        # If accessing from browser, redirect to login gateway
        if "text/html" in accept or "*/*" in accept:
            return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"user": user},
    )


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
        "llm_provider": os.getenv("LLM_PROVIDER", "groq"),
        "llm_model": os.getenv("LLM_MODEL", "openai/gpt-oss-120b"),
        "mock_mode": os.getenv("MOCK_MODE", "false").lower() == "true",
        "vector_store": vector_stats,
    }


@app.post("/api/database/truncate")
def truncate_database():
    """Wipe all data from the database and vector store so user can test fresh."""
    from database import SessionLocal
    from models import (
        AIMappingResult, ReferenceMappingEntry, MappingEvaluation,
        CourseOutcome, ProgramOutcome, ProgramSpecificOutcome,
        Subject, FrameworkOutcome, OutcomeFramework, Document
    )
    from fastapi import HTTPException

    db = SessionLocal()
    try:
        db.query(AIMappingResult).delete()
        db.query(ReferenceMappingEntry).delete()
        db.query(MappingEvaluation).delete()
        db.query(CourseOutcome).delete()
        db.query(ProgramOutcome).delete()
        db.query(ProgramSpecificOutcome).delete()
        db.query(FrameworkOutcome).delete()
        db.query(Subject).delete()
        db.query(OutcomeFramework).delete()
        db.query(Document).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database wipe failed: {e}")
    finally:
        db.close()

    try:
        from ai.vector_store import clear_vector_cache
        clear_vector_cache()
    except Exception:
        pass

    return {
        "status": "success",
        "message": "Entire database and vector store truncated successfully! You can now upload a syllabus PDF and test models fresh."
    }


def get_local_ip() -> str:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def print_banner(port: int):
    local_ip = get_local_ip()
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    api_key = os.getenv("GROQ_API_KEY", "")
    key_status = "Configured (Ready)" if api_key else "Missing GROQ_API_KEY"

    print("\n" + "=" * 65)
    print("  🚀 CO-PO MAPPING AGENT - PRODUCTION SERVER")
    print("=" * 65)
    print(f"  • LLM Engine:     Groq Cloud ({model})")
    print(f"  • API Status:     {key_status}")
    print(f"  • Local URL:      http://localhost:{port}")
    print(f"  • Network/WiFi:   http://{local_ip}:{port}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Run AI CO-PO Mapping Agent Server")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")), help="Port to run server on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address to bind")
    args = parser.parse_args()

    print_banner(args.port)
    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=True,
        reload_dirs=["routers", "ai", "services", "frontend"],
        reload_includes=["*.py", "*.html", "*.css", "*.js"],
        reload_excludes=["*.log", "test_log*", "*.db", "chroma_db/*", "uploads/*"],
    )

