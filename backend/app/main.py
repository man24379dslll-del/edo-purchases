import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    auth_router, admin_router, contractors_router,
    contracts_router, approvals_router, reports_router, files_router, payments_router,
)

app = FastAPI(title="ЭДО Договоров API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(admin_router.router)
app.include_router(contractors_router.router)
app.include_router(contracts_router.router)
app.include_router(approvals_router.router)
app.include_router(reports_router.router)
app.include_router(files_router.router)
app.include_router(files_router.documents_router)
app.include_router(payments_router.router)


@app.on_event("startup")
def ensure_upload_dir():
    os.makedirs(settings.upload_dir, exist_ok=True)


@app.get("/api/health")
def health():
    return {"status": "ok"}
