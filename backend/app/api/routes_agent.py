"""Conversational entry point: a single endpoint that forwards chat messages
to the ADK root agent (`aviator_concierge`), which in turn routes to the four
specialist sub-agents. The REST endpoints in the other route modules remain
available for a traditional UI; this one powers the chat widget.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.api.deps import get_agent_runner, get_current_user_id
from app.api.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/agent", tags=["agent"])

_APP_NAME = "aviator"


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

    # The user's own id travels with every message so tool calls (e.g.
    # book_empty_seat) can act on behalf of the authenticated caller without
    # trusting whatever the model infers from free text.
    message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=f"[user_id={user_id}] {request.message}")],
    )

    reply_parts: list[str] = []
    async for event in runner.run_async(
        user_id=user_id, session_id=session.id, new_message=message
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    reply_parts.append(part.text)

    return ChatResponse(session_id=session.id, reply="".join(reply_parts).strip())
