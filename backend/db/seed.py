"""
Seed the database with synthetic procurement data.
Translates the existing in-memory synthetic data into PostgreSQL records.
"""

import asyncio
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.config import async_session, engine, Base
from db.models import (
    CompanyDB,
    DirectorDB,
    OfficialDB,
    OfficialRelationshipDB,
    TenderDB,
    BidDB,
    CompanyDirectorDB,
    UserDB,
)
from data.synthetic import generate_synthetic_data


# Stable UUID mapping: old string IDs -> UUIDs (deterministic for consistency)
def make_uuid(old_id: str) -> uuid.UUID:
    """Generate a deterministic UUID from an old string ID."""
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"sentinel.{old_id}")


async def seed_database():
    """Populate the database with synthetic data."""
    data = generate_synthetic_data()

    async with async_session() as db:
        async with db.begin():
            # 1. Directors
            for d in data["directors"]:
                db.add(
                    DirectorDB(
                        id=make_uuid(d.id),
                        name=d.name,
                        national_id=getattr(d, "national_id", None),
                    )
                )
            await db.flush()

            # 2. Companies
            for c in data["companies"]:
                db.add(
                    CompanyDB(
                        id=make_uuid(c.id),
                        name=c.name,
                        registration_number=c.registration_number,
                        registration_date=c.registration_date,
                        address=c.address,
                        phone=c.phone,
                        physical_address=getattr(c, "physical_address", None)
                        or c.address,
                        postal_address=getattr(c, "postal_address", None),
                        contact_email=getattr(c, "contact_email", None),
                        supplier_type=getattr(c, "supplier_type", None),
                        brs_number=getattr(c, "brs_number", None),
                        egp_registration_number=getattr(
                            c, "egp_registration_number", None
                        ),
                        source_system=getattr(c, "source_system", "synthetic"),
                        data_quality_flags=getattr(c, "data_quality_flags", None),
                    )
                )
            await db.flush()

            # 3. Company-Director associations
            for c in data["companies"]:
                for dir_id in c.director_ids:
                    db.add(
                        CompanyDirectorDB(
                            company_id=make_uuid(c.id),
                            director_id=make_uuid(dir_id),
                        )
                    )
            await db.flush()

            # 4. Officials
            for o in data["officials"]:
                db.add(
                    OfficialDB(
                        id=make_uuid(o.id),
                        name=o.name,
                        department=o.department,
                        position=o.position,
                    )
                )
            await db.flush()

            # 5. Official-Director relationships
            for o in data["officials"]:
                for person_id, rel_type in o.related_persons.items():
                    db.add(
                        OfficialRelationshipDB(
                            official_id=make_uuid(o.id),
                            person_id=make_uuid(person_id),
                            relationship_type=rel_type.value,
                        )
                    )
            await db.flush()

            # 6. Tenders
            for t in data["tenders"]:
                db.add(
                    TenderDB(
                        id=make_uuid(t.id),
                        reference_number=t.reference_number,
                        title=t.title,
                        description=t.description,
                        procuring_entity=t.procuring_entity,
                        category=t.category,
                        estimated_value=t.estimated_value,
                        awarded_amount=t.awarded_amount,
                        published_date=t.published_date,
                        deadline=t.deadline,
                        status=t.status.value,
                        awarded_to=make_uuid(t.awarded_to) if t.awarded_to else None,
                        procurement_officer_id=(
                            make_uuid(t.procurement_officer_id)
                            if t.procurement_officer_id
                            else None
                        ),
                        procurement_method=getattr(t, "procurement_method", None),
                        procurement_category=getattr(t, "procurement_category", None),
                        pe_type=getattr(t, "pe_type", None),
                        currency=getattr(t, "currency", "KES"),
                        source_system=getattr(t, "source_system", "synthetic"),
                    )
                )
            await db.flush()

            # 7. Bids
            for b in data["bids"]:
                db.add(
                    BidDB(
                        id=make_uuid(b.id),
                        tender_id=make_uuid(b.tender_id),
                        company_id=make_uuid(b.company_id),
                        amount=b.amount,
                        submission_date=b.submission_date,
                        technical_score=getattr(b, "technical_score", None),
                    )
                )
            await db.flush()

    print(
        f"Seeded: {len(data['directors'])} directors, {len(data['companies'])} companies, "
        f"{len(data['officials'])} officials, {len(data['tenders'])} tenders, {len(data['bids'])} bids"
    )


SYSTEM_USER_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")

DEFAULT_USERS = [
    {
        "id": SYSTEM_USER_ID,
        "username": "system",
        "email": "system@sentinel.local",
        "full_name": "System User",
        "role": "system",
        "password": None,  # Cannot login
    },
    {
        "id": uuid.UUID("a0000000-0000-0000-0000-000000000002"),
        "username": "admin",
        "email": "admin@sentinel.local",
        "full_name": "Admin User",
        "role": "admin",
        "password": "admin123",
    },
    {
        "id": uuid.UUID("a0000000-0000-0000-0000-000000000003"),
        "username": "supervisor",
        "email": "supervisor@sentinel.local",
        "full_name": "Jane Supervisor",
        "role": "supervisor",
        "password": "super123",
    },
    {
        "id": uuid.UUID("a0000000-0000-0000-0000-000000000004"),
        "username": "auditor",
        "email": "auditor@sentinel.local",
        "full_name": "John Auditor",
        "role": "auditor",
        "password": "audit123",
    },
]


async def seed_users():
    """Seed default users if they don't exist."""
    from auth.security import get_password_hash

    async with async_session() as db:
        async with db.begin():
            for user_data in DEFAULT_USERS:
                existing = await db.execute(
                    select(UserDB).where(UserDB.username == user_data["username"])
                )
                if existing.scalar_one_or_none():
                    continue

                hashed = (
                    get_password_hash(user_data["password"])
                    if user_data["password"]
                    else "$2b$12$disabled-cannot-login-placeholder-hash-value"
                )
                db.add(
                    UserDB(
                        id=user_data["id"],
                        username=user_data["username"],
                        email=user_data["email"],
                        hashed_password=hashed,
                        full_name=user_data["full_name"],
                        role=user_data["role"],
                    )
                )

    print(
        f"Seeded {len(DEFAULT_USERS)} default users (admin, supervisor, auditor, system)"
    )


async def reset_and_seed():
    """Drop all tables, recreate, and seed."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await seed_users()
    await seed_database()
    print("Database reset and seeded successfully.")


if __name__ == "__main__":
    asyncio.run(reset_and_seed())
