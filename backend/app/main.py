from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    auth_router, admin_router, contractors_router,
    contracts_router, purchases_router, approvals_router, reports_router,
)

app = FastAPI(title="ЭДО Закупок API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(admin_router.router)
app.include_router(contractors_router.router)
app.include_router(contracts_router.router)
app.include_router(purchases_router.router)
app.include_router(approvals_router.router)
app.include_router(reports_router.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
