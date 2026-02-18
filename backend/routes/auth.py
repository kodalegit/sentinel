"""Authentication routes - login, refresh, current user."""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from auth.dependencies import CurrentUser
from db.config import get_db
from db.models import UserDB
from models import Token, TokenRefresh, LoginRequest, User, UserRole

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_db_to_pydantic(user: UserDB) -> User:
    """Convert UserDB to Pydantic User model."""
    return User(
        id=str(user.id),
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=UserRole(user.role),
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.post("/login", response_model=Token)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user and return access + refresh tokens.
    """
    result = await db.execute(
        select(UserDB).where(UserDB.username == body.username)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    # Don't allow system user to login
    if user.role == "system":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System user cannot login",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(body: TokenRefresh, db: AsyncSession = Depends(get_db)):
    """
    Exchange a refresh token for new access + refresh tokens.
    """
    payload = decode_token(body.refresh_token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    import uuid
    result = await db.execute(select(UserDB).where(UserDB.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.get("/me", response_model=User)
async def get_current_user_info(current_user: CurrentUser):
    """
    Get the current authenticated user's information.
    """
    return _user_db_to_pydantic(current_user)
