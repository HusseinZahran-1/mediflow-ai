from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.routers import admin, ai, auth, clinical, departments, doctors, patients, queue, triage, visits
from app.utils.seed import seed_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_database(db)
    yield


configure_logging()
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Academic AI prototype — Not intended for real clinical decisions.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)

for api_router in [auth.router, patients.router, departments.router, visits.router, triage.router, queue.router, doctors.router, clinical.router, ai.router, admin.router]:
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["System"])
def health() -> dict[str, str]:
    return {"status": "healthy", "service": settings.APP_NAME, "version": "1.0.0"}


@app.get("/", tags=["System"])
def root() -> dict[str, str]:
    return {"name": settings.APP_NAME, "docs": "/docs", "notice": "Academic AI prototype — Not intended for real clinical decisions."}
