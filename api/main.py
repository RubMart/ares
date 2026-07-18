from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.dependencies import init_services, shutdown_services
from api.routes.catalog import router as catalog_router
from api.routes.health import router as health_router
from api.routes.search import router as search_router
from config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_services()
    yield
    shutdown_services()


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(catalog_router)
app.include_router(search_router)
