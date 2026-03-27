"""
Database configuration and session management.
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from config import settings


def _normalize_async_database_url(database_url: str) -> tuple[str, dict[str, object]]:
    connect_args: dict[str, object] = {}
    parsed = urlsplit(database_url)
    query_params = parse_qsl(parsed.query, keep_blank_values=True)

    # asyncpg-incompatible params to strip from URL (pass via connect_args or drop)
    asyncpg_incompatible = {"channel_binding"}

    filtered_query_params: list[tuple[str, str]] = []
    for key, value in query_params:
        if key == "ssl" and value == "require":
            connect_args["ssl"] = "require"
            continue
        if key in asyncpg_incompatible:
            continue
        filtered_query_params.append((key, value))

    normalized_url = urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(filtered_query_params),
            parsed.fragment,
        )
    )
    return normalized_url, connect_args


_async_database_url, _async_connect_args = _normalize_async_database_url(
    settings.database_url
)

engine = create_async_engine(
    _async_database_url,
    echo=settings.db_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    connect_args=_async_connect_args,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """Dependency for FastAPI endpoints."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
