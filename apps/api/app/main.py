from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from apps.api.app.api.router import api_router
from apps.api.app.core.config import settings
from apps.api.app.core.database import SessionLocal, create_schema
from apps.api.app.core.rate_limit import RateLimitMiddleware
from apps.api.app.services.seed import seed_demo

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    create_schema()
    with SessionLocal() as session:
        seed_demo(session)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.include_router(api_router, prefix=settings.api_prefix)


@app.middleware("http")
async def request_context(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("x-request-id") or __import__("uuid").uuid4().hex
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    logger.info(
        "request.completed",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status=response.status_code,
    )
    return response
