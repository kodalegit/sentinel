"""Agent settings routes for LLM configuration."""

import base64
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from models import AgentSettingsUpdate, AgentSettingsResponse
from db.config import get_db
from db import repository as repo
from auth.dependencies import AdminOnly
from config import settings as app_settings
from intelligence.agent import reset_agent

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _get_fernet() -> Fernet:
    """Get Fernet instance for encrypting/decrypting API keys."""
    salt = b"sentinel_agent_settings"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(
        kdf.derive(app_settings.jwt_secret.encode() if hasattr(app_settings, 'jwt_secret') else b"default_secret")
    )
    return Fernet(key)


def _encrypt_value(value: str) -> str:
    """Encrypt a sensitive value."""
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()


def _decrypt_value(encrypted: str) -> str:
    """Decrypt a sensitive value."""
    f = _get_fernet()
    return f.decrypt(encrypted.encode()).decode()


@router.get("/llm", response_model=AgentSettingsResponse)
async def get_llm_settings(
    current_user: AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """Get current LLM configuration (admin only)."""
    settings_dict = await repo.get_agent_settings(db)

    return AgentSettingsResponse(
        llm_provider=settings_dict.get("llm_provider") or app_settings.llm_provider,
        llm_model=settings_dict.get("llm_model") or app_settings.llm_model,
        llm_api_key_set=bool(settings_dict.get("llm_api_key")),
        llm_base_url=settings_dict.get("llm_base_url") or app_settings.llm_base_url,
        llm_temperature=float(settings_dict.get("llm_temperature", app_settings.llm_temperature)),
        embedding_provider=settings_dict.get("embedding_provider", "openai"),
        embedding_model=settings_dict.get("embedding_model", "text-embedding-3-small"),
    )


@router.patch("/llm", response_model=AgentSettingsResponse)
async def update_llm_settings(
    body: AgentSettingsUpdate,
    current_user: AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """Update LLM configuration (admin only)."""
    update_data = body.model_dump(exclude_none=True)

    for key, value in update_data.items():
        if key == "llm_api_key" and value:
            value = _encrypt_value(value)
        elif key == "llm_temperature":
            value = str(value)
        await repo.set_agent_setting(db, key, str(value), current_user.id)

    await db.commit()

    reset_agent()

    return await get_llm_settings(current_user, db)


@router.post("/llm/test")
async def test_llm_connection(
    current_user: AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """Test the current LLM configuration."""
    from langchain.chat_models import init_chat_model

    settings_dict = await repo.get_agent_settings(db)

    provider = settings_dict.get("llm_provider") or app_settings.llm_provider
    model = settings_dict.get("llm_model") or app_settings.llm_model
    base_url = settings_dict.get("llm_base_url") or app_settings.llm_base_url
    temperature = float(settings_dict.get("llm_temperature", app_settings.llm_temperature))

    try:
        kwargs = {
            "model": model,
            "model_provider": provider,
            "temperature": temperature,
        }
        if base_url:
            kwargs["base_url"] = base_url

        llm = init_chat_model(**kwargs)

        response = await llm.ainvoke([{"role": "user", "content": "Say 'OK' if you can hear me."}])

        return {
            "success": True,
            "provider": provider,
            "model": model,
            "response": response.content[:100] if response.content else "No response",
        }

    except Exception as e:
        return {
            "success": False,
            "provider": provider,
            "model": model,
            "error": str(e)[:200],
        }
