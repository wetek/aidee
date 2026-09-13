import json
import os
import secrets
import socket
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter()
SOCKET_PATH = Path(os.environ.get("AIDEE_ADMIN_SOCKET", "/run/aidee/admin.sock"))
MAX_RESPONSE_BYTES = 65536
ASSISTANT_ID = r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$"


class AssistantBody(BaseModel):
    assistant_id: str = Field(pattern=ASSISTANT_ID)


class CredentialsBody(AssistantBody):
    dashboard_username: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9._-]{0,63}$")
    dashboard_password: str = Field(
        min_length=8,
        max_length=128,
        pattern=r"^[^\r\n]+$",
    )


def call_admin(operation, assistant_id=None, extra=None):
    request_id = f"{operation.replace('_', '-')}-{secrets.token_hex(4)}"
    if assistant_id:
        request_id = f"{operation.replace('_', '-')}-{assistant_id}-{secrets.token_hex(3)}"
    request_id = request_id[:64]
    request = {
        "schema_version": 1,
        "request_id": request_id,
        "owner_approved": True,
        "operation": operation,
    }
    if assistant_id is not None:
        request["assistant_id"] = assistant_id
    if extra:
        request.update(extra)
    message = json.dumps(request, separators=(",", ":")).encode()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.connect(str(SOCKET_PATH))
            connection.sendall(message)
            response = connection.recv(MAX_RESPONSE_BYTES + 1)
    except OSError as error:
        raise HTTPException(
            status_code=503,
            detail=f"administration helper unavailable: {error}",
        ) from error
    if len(response) > MAX_RESPONSE_BYTES:
        raise HTTPException(
            status_code=502,
            detail="administration helper response is too large",
        )
    try:
        payload = json.loads(response)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=502,
            detail="administration helper returned invalid JSON",
        ) from error
    if payload.get("ok") is not True:
        raise HTTPException(
            status_code=400,
            detail=str(payload.get("error") or "administration helper failed"),
        )
    return payload.get("result") or {}


@router.get("/assistants")
def assistants():
    return call_admin("list_assistants")


@router.post("/reveal")
def reveal(body: AssistantBody):
    return call_admin("reveal_dashboard_password", body.assistant_id)


@router.post("/reset")
def reset(body: AssistantBody):
    return call_admin("reset_dashboard_password", body.assistant_id)


@router.post("/set")
def set_credentials(body: CredentialsBody):
    return call_admin(
        "set_dashboard_credentials",
        body.assistant_id,
        {
            "dashboard_username": body.dashboard_username,
            "dashboard_password": body.dashboard_password,
        },
    )
