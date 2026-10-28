"""Aggregate router for all ``/api/v1`` endpoints."""

from fastapi import APIRouter

from app.api.v1 import auth, projects, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(projects.router)
