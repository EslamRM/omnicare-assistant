import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import auth, chat, health
from app.core.config import get_settings
from app.services.rag import RagService
import app.agent.nodes as agent_nodes

settings = get_settings()
logging.basicConfig(level=settings.log_level, format='%(message)s')
logger = logging.getLogger("omnicare")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize heavyweight dependencies once per process."""
    try:
        app.state.rag_service = RagService()
        agent_nodes._rag_service = app.state.rag_service
        app.state.ready = True
        logger.info('{"event":"startup","status":"ready"}')
    except Exception:
        app.state.ready = False
        logger.exception('{"event":"startup","status":"failed"}')
        raise
    yield


app = FastAPI(title="OmniCare GenAI Assistant", version="1.0.0", lifespan=lifespan)
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info('{"event":"request","request_id":"%s","method":"%s","path":"%s","duration_ms":%s}', request_id, request.method, request.url.path, duration_ms)
        if response is not None:
            response.headers["X-Request-ID"] = request_id


@app.exception_handler(Exception)
async def safe_exception_handler(request: Request, exc: Exception):
    logger.exception('{"event":"unhandled_error","request_id":"%s","path":"%s"}', getattr(request.state, "request_id", "unknown"), request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": {"code": "internal_error", "message": "An internal error occurred. Please try again."}},
        headers={"X-Request-ID": getattr(request.state, "request_id", "unknown")},
    )
