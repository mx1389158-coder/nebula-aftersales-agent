from fastapi import APIRouter

from apps.api.app.api.routes import (
    auth,
    chat,
    conversations,
    documents,
    evals,
    governance,
    health,
    jobs,
    memories,
    skills,
    tickets,
)
from apps.api.app.core.config import settings

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
if not settings.business_service_enabled:
    api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(memories.router, prefix="/memories", tags=["memories"])
api_router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
api_router.include_router(evals.router, prefix="/evals", tags=["evals"])
api_router.include_router(skills.router, prefix="/skills", tags=["skills"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(governance.router, tags=["governance"])
