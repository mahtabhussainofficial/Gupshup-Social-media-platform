import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import storage
from .config import settings
from .database import get_db
from .routers import auth, comments, pages, posts, users, vote

BASE_DIR = Path(__file__).resolve().parent
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage.media_root()  # make sure the upload folder exists before the first upload
    yield


app = FastAPI(title=f"{settings.app_name} API", lifespan=lifespan)

# CORS only matters for *other* websites calling this API from a browser. The HTML pages
# are served by this same app (same origin), so they do not need it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The /docs page loads scripts from a CDN, so the strict policy is not applied to it.
CSP = "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


@app.middleware("http")
async def security_and_timing(request: Request, call_next):
    start = time.perf_counter()
    response: Response = await call_next(request)
    response.headers["X-Process-Time-ms"] = f"{(time.perf_counter() - start) * 1000:.1f}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"  # reset links must not leak to other sites
    if not request.url.path.startswith(DOCS_PATHS):
        response.headers["Content-Security-Policy"] = CSP
    return response


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/media", StaticFiles(directory=storage.media_root()), name="media")

app.include_router(posts.router)
app.include_router(users.router)
app.include_router(auth.router)
app.include_router(vote.router)
app.include_router(comments.router)
app.include_router(pages.router)  # the HTML pages


@app.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)):
    """Used by Docker and Azure to check the app is alive and can reach the database."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: database unreachable")
        return JSONResponse({"status": "error", "database": "unreachable"}, status_code=503)
    return {"status": "ok", "database": "ok"}
