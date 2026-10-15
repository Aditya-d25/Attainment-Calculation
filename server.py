#!/usr/bin/env python3
"""Runner for AI CO-PO Mapping Agent Server."""
import os
import argparse
import uvicorn
from main import print_banner

if __name__ == "__main__":
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
