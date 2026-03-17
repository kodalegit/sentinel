"""Agent settings routes for LLM configuration."""

import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from models import AgentSettingsUpdate, AgentSettingsResponse, LLMModelCatalogResponse
from db.config import get_db, async_session
from db import repository as repo
from auth.dependencies import AdminOnly
from config import settings as app_settings
from intelligence.agent import reset_agent
from intelligence.model_catalog import get_llm_model_catalog

router = APIRouter(prefix="/api/settings", tags=["settings"])

ENV_LLM_DEFAULTS = {
    "llm_provider": app_settings.llm_provider,
    "llm_model": app_settings.llm_model,
    "llm_base_url": app_settings.llm_base_url,
    "llm_temperature": app_settings.llm_temperature,
    "openai_api_key": app_settings.openai_api_key,
    "anthropic_api_key": app_settings.anthropic_api_key,
    "google_api_key": app_settings.google_api_key,
}


def _build_fernet(secret: str) -> Fernet:
    """Build a Fernet instance from an application secret."""
    salt = b"sentinel_agent_settings"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
    return Fernet(key)


def _get_fernet() -> Fernet:
    """Get Fernet instance for encrypting sensitive settings."""
    return _build_fernet(app_settings.settings_encryption_key)


def _encrypt_value(value: str) -> str:
    """Encrypt a sensitive value."""
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()


def _decrypt_value(encrypted: str) -> str:
    """Decrypt a sensitive value."""
    candidates = [app_settings.settings_encryption_key]
    if app_settings.jwt_secret_key not in candidates:
        candidates.append(app_settings.jwt_secret_key)
    if "default_secret" not in candidates:
        candidates.append("default_secret")

    for secret in candidates:
        try:
            return _build_fernet(secret).decrypt(encrypted.encode()).decode()
        except Exception:
            continue

    raise ValueError("Unable to decrypt sensitive setting")


def _resolve_runtime_llm_settings(
    settings_dict: dict[str, str],
    *,
    override_api_key: str | None = None,
) -> tuple[str, str, str | None, float, str | None]:
    provider = settings_dict.get("llm_provider") or ENV_LLM_DEFAULTS["llm_provider"]
    model = settings_dict.get("llm_model") or ENV_LLM_DEFAULTS["llm_model"]
    base_url = settings_dict.get("llm_base_url") or ENV_LLM_DEFAULTS["llm_base_url"]
    temperature = float(
        settings_dict.get("llm_temperature", ENV_LLM_DEFAULTS["llm_temperature"])
    )
    api_key = override_api_key
    if api_key is None and settings_dict.get("llm_api_key"):
        api_key = _decrypt_value(settings_dict["llm_api_key"])
    if api_key is None:
        normalized_provider = provider.lower()
        if normalized_provider == "openai":
            api_key = ENV_LLM_DEFAULTS["openai_api_key"]
        elif normalized_provider == "anthropic":
            api_key = ENV_LLM_DEFAULTS["anthropic_api_key"]
        elif normalized_provider in {"google", "google_genai"}:
            api_key = ENV_LLM_DEFAULTS["google_api_key"]

    return provider, model, base_url, temperature, api_key


def _apply_runtime_llm_settings(
    settings_dict: dict[str, str],
    *,
    override_api_key: str | None = None,
) -> tuple[str, str, str | None, float, str | None]:
    provider, model, base_url, temperature, api_key = _resolve_runtime_llm_settings(
        settings_dict,
        override_api_key=override_api_key,
    )

    app_settings.llm_provider = provider
    app_settings.llm_model = model
    app_settings.llm_base_url = base_url
    app_settings.llm_temperature = temperature
    app_settings.openai_api_key = None
    app_settings.anthropic_api_key = None
    app_settings.google_api_key = None

    normalized_provider = provider.lower()
    if normalized_provider == "openai":
        app_settings.openai_api_key = api_key
    elif normalized_provider == "anthropic":
        app_settings.anthropic_api_key = api_key
    elif normalized_provider in {"google", "google_genai"}:
        app_settings.google_api_key = api_key

    return provider, model, base_url, temperature, api_key


async def sync_runtime_llm_settings_from_db(db: AsyncSession | None = None) -> None:
    if db is not None:
        settings_dict = await repo.get_agent_settings(db)
        _apply_runtime_llm_settings(settings_dict)
        return

    async with async_session() as session:
        settings_dict = await repo.get_agent_settings(session)
    _apply_runtime_llm_settings(settings_dict)


@router.get("/llm", response_model=AgentSettingsResponse)
async def get_llm_settings(
    current_user: AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """Get current LLM configuration (admin only)."""
    settings_dict = await repo.get_agent_settings(db)
    provider, model, base_url, temperature, api_key = _resolve_runtime_llm_settings(
        settings_dict
    )

    return AgentSettingsResponse(
        llm_provider=provider,
        llm_model=model,
        llm_api_key_set=bool(api_key),
        llm_base_url=base_url,
        llm_temperature=temperature,
        embedding_provider=settings_dict.get("embedding_provider", "openai"),
        embedding_model=settings_dict.get("embedding_model", "text-embedding-3-small"),
    )


@router.get("/llm/catalog", response_model=LLMModelCatalogResponse)
async def get_llm_catalog(current_user: AdminOnly):
    """Get the static repo-backed LLM provider and model catalog."""
    return get_llm_model_catalog()


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

    await sync_runtime_llm_settings_from_db(db)
    reset_agent()

    return await get_llm_settings(current_user, db)


@router.post("/llm/test")
async def test_llm_connection(
    current_user: AdminOnly,
    db: AsyncSession = Depends(get_db),
    body: AgentSettingsUpdate | None = None,
):
    """Test the current LLM configuration."""
    from langchain.chat_models import init_chat_model

    settings_dict = await repo.get_agent_settings(db)
    overrides = body.model_dump(exclude_none=True) if body else {}

    runtime_settings = dict(settings_dict)
    if "llm_provider" in overrides:
        runtime_settings["llm_provider"] = overrides["llm_provider"]
    if "llm_model" in overrides:
        runtime_settings["llm_model"] = overrides["llm_model"]
    if "llm_base_url" in overrides:
        runtime_settings["llm_base_url"] = overrides["llm_base_url"]
    if "llm_temperature" in overrides:
        runtime_settings["llm_temperature"] = str(overrides["llm_temperature"])

    provider, model, base_url, temperature, api_key = _resolve_runtime_llm_settings(
        runtime_settings,
        override_api_key=overrides.get("llm_api_key"),
    )

    try:
        kwargs = {
            "model": model,
            "model_provider": provider,
            "temperature": temperature,
        }
        if base_url:
            kwargs["base_url"] = base_url
        if api_key:
            kwargs["api_key"] = api_key

        llm = init_chat_model(**kwargs)

        response = await llm.ainvoke(
            [{"role": "user", "content": "Say 'OK' if you can hear me."}]
        )

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
