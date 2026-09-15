import json
import os
import secrets
import socket
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter()
SOCKET_PATH = Path(os.environ.get("AIDEE_ADMIN_SOCKET", "/run/aidee/admin.sock"))
MAX_RESPONSE_BYTES = 65536
ASSISTANT_ID = r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$"
LANGFUSE_KEY = r"^[^\r\n]{8,256}$"
LANGFUSE_URL = (
    r"^https://[A-Za-z0-9.-]+(?::[0-9]{2,5})?(?:/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=-]*)?$"
)


class LangfuseBody(BaseModel):
    assistant_id: Optional[str] = Field(default=None, pattern=ASSISTANT_ID)
    enabled: bool
    public_key: Optional[str] = Field(default=None, pattern=LANGFUSE_KEY)
    secret_key: Optional[str] = Field(default=None, pattern=LANGFUSE_KEY)
    base_url: Optional[str] = Field(default=None, pattern=LANGFUSE_URL)


class OpencodeBody(BaseModel):
    assistant_id: Optional[str] = Field(default=None, pattern=ASSISTANT_ID)
    action: str = Field(pattern=r"^(install|uninstall)$")


def call_admin(operation, extra=None):
    request_id = f"{operation.replace('_', '-')}-{secrets.token_hex(4)}"
    if extra and extra.get("assistant_id"):
        request_id = (
            f"{operation.replace('_', '-')}-{extra['assistant_id']}-"
            f"{secrets.token_hex(3)}"
        )
    request_id = request_id[:64]
    request = {
        "schema_version": 1,
        "request_id": request_id,
        "owner_approved": True,
        "operation": operation,
    }
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


@router.get("/overview")
def overview():
    return call_admin("fleet_overview")


@router.post("/langfuse")
def langfuse(body: LangfuseBody):
    extra = {"enabled": body.enabled}
    if body.assistant_id:
        raise HTTPException(
            status_code=400,
            detail="Langfuse keys are set on the controller dashboard",
        )
    if body.enabled:
        if body.public_key:
            extra["public_key"] = body.public_key
        if body.secret_key:
            extra["secret_key"] = body.secret_key
        if body.base_url:
            extra["base_url"] = body.base_url
    return call_admin("set_controller_langfuse", extra)


@router.post("/opencode")
def opencode(body: OpencodeBody):
    extra = {"action": body.action}
    if body.assistant_id:
        extra["assistant_id"] = body.assistant_id
        operation = "set_assistant_opencode"
    else:
        operation = "set_controller_opencode"
    return call_admin(operation, extra)
