"""Conversational entry point: a single endpoint that forwards chat messages
to the ADK root agent (`aviator_concierge`), which in turn routes to the four
specialist sub-agents. The REST endpoints in the other route modules remain
available for a traditional UI; this one powers the chat widget.
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from google.adk.runners import InMemoryRunner
from google.genai.errors import APIError
from google.genai import types

from app.agents.tools import authenticated_user
from app.api.deps import get_agent_runner, get_current_user_id
from app.api.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/agent", tags=["agent"])
logger = logging.getLogger(__name__)

_APP_NAME = "aviator"
_AGENT_TIMEOUT_SECONDS = 60


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    runner: InMemoryRunner = Depends(get_agent_runner),
) -> ChatResponse:
    session_id = request.session_id or str(uuid.uuid4())
    session = await runner.session_service.get_session(
        app_name=_APP_NAME, user_id=user_id, session_id=session_id
    )
    if session is None:
        session = await runner.session_service.create_session(
            app_name=_APP_NAME, user_id=user_id, session_id=session_id
        )

    message = types.Content(
        role="user", parts=[types.Part.from_text(text=request.message)]
    )

    reply_parts: list[str] = []
    try:
        async with asyncio.timeout(_AGENT_TIMEOUT_SECONDS):
            with authenticated_user(user_id):
                async for event in runner.run_async(
                    user_id=user_id, session_id=session.id, new_message=message
                ):
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if part.text:
                                reply_parts.append(part.text)
    except TimeoutError as exc:
        logger.warning("ADK chat timed out after %s seconds.", _AGENT_TIMEOUT_SECONDS)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Aviator AI took too long to respond. Please try again.",
        ) from exc
    except APIError as exc:
        if exc.code in (429, 503):
            logger.warning("Vertex AI is temporarily at capacity (status=%s).", exc.code)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Aviator AI is temporarily at capacity. Please try again in a minute.",
                headers={"Retry-After": "60"},
            ) from exc
        logger.exception("The ADK chat request failed (AI provider status=%s).", exc.code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Aviator AI could not process that request. Please try again.",
        ) from exc

    reply = "".join(reply_parts).strip()
    if not reply:
        logger.warning("ADK chat completed without returning a text response.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Aviator AI did not return an answer. Please try again.",
        )

    return ChatResponse(session_id=session.id, reply=reply)
