"""Authentication adapter. In production, verifies a Firebase Auth ID token
sent as `Authorization: Bearer <token>`. In local development (no Firebase
project configured), falls back to a plain `X-User-Id` header so the whole
product can be exercised without any cloud credentials.
"""
from __future__ import annotations

from fastapi import Header, HTTPException, status

import firebase_admin
from firebase_admin import auth as firebase_auth

_firebase_app: firebase_admin.App | None = None


def init_firebase(project_id: str) -> None:
    global _firebase_app
    if _firebase_app is None:
        _firebase_app = firebase_admin.initialize_app(options={"projectId": project_id})


def verify_firebase_token(id_token: str) -> str:
    """Returns the Firebase `uid` for a valid ID token, raises HTTP 401 otherwise."""
    try:
        decoded = firebase_auth.verify_id_token(id_token)
    except Exception as exc:  # noqa: BLE001 - surfaced as a generic auth failure
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        ) from exc
    return decoded["uid"]


def local_dev_user_id(x_user_id: str = Header(...)) -> str:
    """Dev-only dependency: trusts a client-supplied header. Never enable
    this path in production - see `get_current_user_id` in `app/api/deps.py`.
    """
    return x_user_id
