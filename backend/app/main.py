from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
import logging

from app.core.observability import configure_logging, new_request_id, request_id_var
from app.core.database import SessionLocal
from app.modules.operations.audit import record_audit

from app.api.v1.documents import router as documents_router
from app.api.v1.departments import router as departments_router
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.library import router as library_router


configure_logging()
logger = logging.getLogger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = new_request_id(request.headers.get("X-Request-ID"))
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            if request.url.path not in {"/", "/health"} and not request.url.path.startswith("/openapi"):
                try:
                    with SessionLocal() as db:
                        record_audit(db, action="HTTP_REQUEST", request_id=request_id,
                                     method=request.method, path=request.url.path,
                                     status_code=response.status_code)
                        db.commit()
                except Exception:
                    logger.exception("Unable to persist request audit event")
            logger.info("http_request", extra={"request_id": request_id, "method": request.method,
                                               "path": request.url.path, "status_code": response.status_code})
            return response
        finally:
            request_id_var.reset(token)


app = FastAPI(
    title="Enterprise Knowledge Intelligence Platform",
    description="Department-aware banking knowledge ingestion and retrieval API.",
    version="0.1.0",
)

app.add_middleware(ObservabilityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

app.include_router(documents_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(departments_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(library_router, prefix="/api/v1")
app.include_router(knowledge_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "application": "EKIP"}


@app.get("/")
async def root():
    return {"message": "Welcome to EKIP", "docs": "/docs"}