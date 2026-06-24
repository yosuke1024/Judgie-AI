"""
FastAPI application entry point.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import CORS_ORIGINS
from app.middleware.ip_filter import IPLimitMiddleware
from app.models.db import init_db
from app.routers import auth, chat, evaluations, export, settings, submissions, tasks, teams, manual


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_db()
    yield


app = FastAPI(
    title="Judgie-AI API",
    description="AI-powered Project Evaluation Platform",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# IP limit middleware (added after CORS to be the outermost middleware)
app.add_middleware(IPLimitMiddleware)

# Register routers

app.include_router(auth.router)
app.include_router(teams.router)
app.include_router(evaluations.router)
app.include_router(submissions.router)
app.include_router(chat.router)
app.include_router(settings.router)
app.include_router(export.router)
app.include_router(tasks.router)
app.include_router(manual.router)


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "2.0.0"}


# Serve React static files in production
# In development, the React dev server runs separately

if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

    @app.exception_handler(StarletteHTTPException)
    async def spa_fallback(request, exc):
        """Serve index.html for any frontend SPA routes not handled by StaticFiles."""
        if exc.status_code == 404 and not request.url.path.startswith("/api"):
            index_path = os.path.join("static", "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
