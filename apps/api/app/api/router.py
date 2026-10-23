from fastapi import APIRouter

from apps.api.app.api.routes import (
    auth,
    chat,
    documents,
    evals,
    governance,
    health,
    jobs,
    memories,
    skills,
    tickets,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(memories.router, prefix="/memories", tags=["memories"])
api_router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
api_router.include_router(evals.router, prefix="/evals", tags=["evals"])
api_router.include_router(skills.router, prefix="/skills", tags=["skills"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(governance.router, tags=["governance"])
