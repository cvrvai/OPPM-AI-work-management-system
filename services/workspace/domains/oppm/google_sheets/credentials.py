"""Credential encryption/decryption and Google API service builders."""

import asyncio
import base64
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from domains.notification.repository import AuditRepository
from domains.workspace.repository import WorkspaceRepository

from .constants import (
    _GOOGLE_CREDENTIALS_KEY,
    _GOOGLE_SCOPES,
)

logger = logging.getLogger(__name__)


def _build_workspace_cipher() -> Fernet:
    settings = get_settings()
    key_bytes = hashlib.sha256(settings.jwt_secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def _encrypt_workspace_credential(plain_text: str) -> str:
    return _build_workspace_cipher().encrypt(plain_text.encode("utf-8")).decode("utf-8")


def _decrypt_workspace_credential(cipher_text: str) -> str:
    try:
        decrypted = _build_workspace_cipher().decrypt(cipher_text.encode("utf-8"))
    except InvalidToken:
        raise HTTPException(status_code=500, detail="Invalid encrypted Google service account credential")
    return decrypted.decode("utf-8")


def _resolve_service_account_info(strict: bool = True) -> tuple[dict[str, Any] | None, str | None]:
    settings = get_settings()
    if settings.google_service_account_json.strip():
        try:
            return json.loads(settings.google_service_account_json), None
        except json.JSONDecodeError as error:
            logger.warning("Invalid GOOGLE_SERVICE_ACCOUNT_JSON: %s", error)
            detail = "Invalid Google service account JSON configuration"
            if strict:
                raise HTTPException(status_code=500, detail=detail)
            return None, detail

    if settings.google_service_account_file.strip():
        file_path = Path(settings.google_service_account_file)
        if not file_path.exists():
            detail = "Google service account file does not exist"
            if strict:
                raise HTTPException(status_code=500, detail=detail)
            return None, detail
        try:
            return json.loads(file_path.read_text(encoding="utf-8")), None
        except (OSError, json.JSONDecodeError) as error:
            logger.warning("Failed to read Google service account file: %s", error)
            detail = "Invalid Google service account file configuration"
            if strict:
                raise HTTPException(status_code=500, detail=detail)
            return None, detail

    return None, None


def _load_service_account_info(strict: bool = True) -> dict[str, Any] | None:
    info, _ = _resolve_service_account_info(strict=strict)
    return info


async def _resolve_workspace_service_account_info(
    session: AsyncSession,
    workspace_id: str,
    strict: bool = True,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    workspace_repo = WorkspaceRepository(session)
    workspace = await workspace_repo.find_by_id(workspace_id)
    if workspace:
        settings_blob = dict(workspace.settings or {})
        credentials = settings_blob.get(_GOOGLE_CREDENTIALS_KEY)
        if isinstance(credentials, dict):
            encrypted_json = credentials.get("encrypted_json")
            if isinstance(encrypted_json, str) and encrypted_json.strip():
                try:
                    decrypted_json = _decrypt_workspace_credential(encrypted_json)
                    return json.loads(decrypted_json), None, "database"
                except HTTPException as error:
                    if strict:
                        raise error
                    return None, error.detail, "database"
                except json.JSONDecodeError:
                    detail = "Invalid Google service account data stored for workspace"
                    if strict:
                        raise HTTPException(status_code=500, detail=detail)
                    return None, detail, "database"

    env_info, env_error = _resolve_service_account_info(strict=strict)
    return env_info, env_error, _credential_source()


def _credential_source() -> str | None:
    settings = get_settings()
    if settings.google_service_account_json.strip():
        return "env_json"
    if settings.google_service_account_file.strip():
        return "file"
    return None


def _service_account_email_from_info(info: dict[str, Any] | None) -> str | None:
    if not info:
        return None
    return info.get("client_email")


async def _service_account_email(session: AsyncSession, workspace_id: str) -> str | None:
    info, _, _ = await _resolve_workspace_service_account_info(session, workspace_id, strict=False)
    return _service_account_email_from_info(info)


async def _backend_configuration_error(session: AsyncSession, workspace_id: str) -> str | None:
    _, error, _ = await _resolve_workspace_service_account_info(session, workspace_id, strict=False)
    return error


async def _is_backend_configured(session: AsyncSession, workspace_id: str) -> bool:
    info, _, _ = await _resolve_workspace_service_account_info(session, workspace_id, strict=False)
    return info is not None


def _build_google_credentials(info: dict[str, Any] | None):
    if not info:
        raise HTTPException(status_code=503, detail="Google Sheets integration is not configured on the backend")

    try:
        from google.oauth2 import service_account
    except ImportError as error:
        logger.warning("Google Sheets dependencies missing: %s", error)
        raise HTTPException(status_code=503, detail="Google Sheets dependencies are not installed on the backend")

    return service_account.Credentials.from_service_account_info(info, scopes=_GOOGLE_SCOPES)


def _build_authorized_http(credentials):
    """Return an AuthorizedHttp transport with SSL verification disabled.

    Inside Docker containers the system CA bundle is often incomplete,
    causing [SSL: CERTIFICATE_VERIFY_FAILED] errors against Google APIs.
    Disabling certificate validation at the transport level is the
    standard workaround for containerised service-account workloads that
    communicate exclusively with Google's own endpoints.
    """
    try:
        import httplib2
        import google_auth_httplib2
        http = httplib2.Http(disable_ssl_certificate_validation=True)
        return google_auth_httplib2.AuthorizedHttp(credentials, http=http)
    except ImportError:
        return None


def _build_sheets_service(info: dict[str, Any] | None):
    try:
        from googleapiclient.discovery import build
    except ImportError as error:
        logger.warning("Google Sheets dependencies missing: %s", error)
        raise HTTPException(status_code=503, detail="Google Sheets dependencies are not installed on the backend")

    credentials = _build_google_credentials(info)
    authorized_http = _build_authorized_http(credentials)
    if authorized_http is not None:
        return build("sheets", "v4", http=authorized_http, cache_discovery=False)
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _build_drive_service(info: dict[str, Any] | None):
    try:
        from googleapiclient.discovery import build
    except ImportError as error:
        logger.warning("Google Drive dependencies missing: %s", error)
        raise HTTPException(status_code=503, detail="Google Drive dependencies are not installed on the backend")

    credentials = _build_google_credentials(info)
    authorized_http = _build_authorized_http(credentials)
    if authorized_http is not None:
        return build("drive", "v3", http=authorized_http, cache_discovery=False)
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


async def upsert_google_sheets_workspace_credentials(
    session: AsyncSession,
    workspace_id: str,
    user_id: str,
    service_account_json: str,
) -> dict[str, Any]:
    workspace_repo = WorkspaceRepository(session)
    audit_repo = AuditRepository(session)
    workspace = await workspace_repo.find_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    try:
        info = json.loads(service_account_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid service account JSON")

    client_email = info.get("client_email")
    private_key = info.get("private_key")
    if not client_email or not private_key:
        raise HTTPException(status_code=400, detail="Service account JSON must include client_email and private_key")

    encrypted_json = _encrypt_workspace_credential(service_account_json)
    settings_blob = dict(workspace.settings or {})
    settings_blob[_GOOGLE_CREDENTIALS_KEY] = {
        "encrypted_json": encrypted_json,
        "client_email": client_email,
    }

    await workspace_repo.update(workspace_id, {"settings": settings_blob})
    await audit_repo.log(
        workspace_id,
        user_id,
        "update",
        "workspace_google_sheets_credentials",
        workspace_id,
        new_data={"client_email": client_email, "credential_source": "database"},
    )

    return await get_google_sheets_setup_status(session, workspace_id)


async def delete_google_sheets_workspace_credentials(
    session: AsyncSession,
    workspace_id: str,
    user_id: str,
) -> dict[str, Any]:
    workspace_repo = WorkspaceRepository(session)
    audit_repo = AuditRepository(session)
    workspace = await workspace_repo.find_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    settings_blob = dict(workspace.settings or {})
    previous = settings_blob.pop(_GOOGLE_CREDENTIALS_KEY, None)
    await workspace_repo.update(workspace_id, {"settings": settings_blob})
    await audit_repo.log(
        workspace_id,
        user_id,
        "delete",
        "workspace_google_sheets_credentials",
        workspace_id,
        old_data={"had_credentials": bool(previous)},
        new_data={"had_credentials": False},
    )

    return await get_google_sheets_setup_status(session, workspace_id)


async def get_google_sheets_setup_status(session: AsyncSession, workspace_id: str) -> dict[str, Any]:
    """Return backend Google Sheets configuration status for setup UX."""
    info, error, source = await _resolve_workspace_service_account_info(session, workspace_id, strict=False)
    return {
        "backend_configured": info is not None,
        "service_account_email": _service_account_email_from_info(info),
        "backend_configuration_error": error,
        "credential_source": source,
    }
