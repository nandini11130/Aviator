"""FastAPI application entry point. Builds the composition root eagerly at
startup (fail fast if config is bad), wires CORS for the Next.js frontend,
and mounts every route module.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_agent,
    routes_bookings,
    routes_flights,
    routes_payments,
    routes_subscriptions,
    routes_webhooks,
)
from app.api.deps import get_agent_runner, get_container
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_container()
    get_agent_runner()
    yield


settings = get_settings()

app = FastAPI(
    title="Aviator API",
    description="Last-minute empty-seat subscription marketplace.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_flights.router)
app.include_router(routes_bookings.router)
app.include_router(routes_payments.router)
app.include_router(routes_subscriptions.router)
app.include_router(routes_webhooks.router)
app.include_router(routes_agent.router)


@app.get("/health", tags=["health"])
@app.get("/healthz", tags=["health"])
def health_check() -> dict:
    return {"status": "ok", "environment": settings.environment}
