from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "healthy"}


@router.get("/ready")
def ready(request: Request):
    if not getattr(request.app.state, "ready", False):
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ready"}
