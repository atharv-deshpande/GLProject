from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.documents import router as documents_router
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.knowledge import router as knowledge_router


app = FastAPI(
    title="Enterprise Knowledge Intelligence Platform",
    description="Department-aware banking knowledge ingestion and retrieval API.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(documents_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(knowledge_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "application": "EKIP"}


@app.get("/")
async def root():
    return {"message": "Welcome to EKIP", "docs": "/docs"}