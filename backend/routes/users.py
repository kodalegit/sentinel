"""User management routes - admin only."""

import uuid as _uuid

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_password_hash
from auth.dependencies import AdminOnly, SupervisorOrAdmin
from db.config import get_db
from db.models import UserDB
from models import User, UserCreate, UserUpdate, UserRole

router = APIRouter(prefix="/api/users", tags=["users"])


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


@router.get("", response_model=list[User])
async def list_users(
    admin: AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """List all users. Admin only."""
    result = await db.execute(
        select(UserDB).where(UserDB.role != "system").order_by(UserDB.created_at.desc())
    )
    users = result.scalars().all()
    return [_user_db_to_pydantic(u) for u in users]


@router.post("", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    admin: AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """Create a new user. Admin only."""
    # Check for existing username
    existing = await db.execute(select(UserDB).where(UserDB.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    # Check for existing email
    existing_email = await db.execute(select(UserDB).where(UserDB.email == body.email))
    if existing_email.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists",
        )

    # Don't allow creating system users via API
    if body.role == UserRole.SYSTEM:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create system users",
        )

    user = UserDB(
        username=body.username,
        email=body.email,
        hashed_password=get_password_hash(body.password),
        full_name=body.full_name,
        role=body.role.value,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return _user_db_to_pydantic(user)


@router.get("/{user_id}", response_model=User)
async def get_user(
    user_id: str,
    admin: AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific user. Admin only."""
    result = await db.execute(select(UserDB).where(UserDB.id == _uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _user_db_to_pydantic(user)


@router.patch("/{user_id}", response_model=User)
async def update_user(
    user_id: str,
    body: UserUpdate,
    admin: AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """Update a user. Admin only."""
    result = await db.execute(select(UserDB).where(UserDB.id == _uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Don't allow modifying system user
    if user.role == "system":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify system user",
        )

    # Don't allow changing role to system
    if body.role == UserRole.SYSTEM:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change role to system",
        )

    update_data = body.model_dump(exclude_none=True)

    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    if "role" in update_data:
        update_data["role"] = update_data["role"].value

    for key, value in update_data.items():
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)

    return _user_db_to_pydantic(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: str,
    admin: AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a user (soft delete). Admin only."""
    result = await db.execute(select(UserDB).where(UserDB.id == _uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Don't allow deactivating system user
    if user.role == "system":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate system user",
        )

    # Don't allow admin to deactivate themselves
    if str(user.id) == str(admin.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate yourself",
        )

    user.is_active = False
    await db.commit()


@router.get("/assignable/list", response_model=list[User])
async def list_assignable_users(
    current_user: SupervisorOrAdmin,
    db: AsyncSession = Depends(get_db),
):
    """
    List users that can be assigned to cases.
    Returns active auditors, supervisors, and admins.
    Requires supervisor or admin access.
    """
    result = await db.execute(
        select(UserDB)
        .where(UserDB.is_active == True)
        .where(UserDB.role.in_(["auditor", "supervisor", "admin"]))
        .order_by(UserDB.full_name)
    )
    users = result.scalars().all()
    return [_user_db_to_pydantic(u) for u in users]
