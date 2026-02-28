"""
Neo4j driver and connection management.
Provides async driver instance and session helpers.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession

from config import settings

logger = logging.getLogger(__name__)

_driver: AsyncDriver | None = None


async def get_neo4j_driver() -> AsyncDriver:
    """Get or create the Neo4j async driver singleton."""
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        # Verify connectivity
        try:
            await _driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {settings.neo4j_uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
    return _driver


async def close_neo4j_driver():
    """Close the Neo4j driver on shutdown."""
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
        logger.info("Neo4j driver closed")


@asynccontextmanager
async def get_neo4j_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a Neo4j session for executing queries."""
    driver = await get_neo4j_driver()
    async with driver.session(database=settings.neo4j_database) as session:
        yield session


async def check_neo4j_health() -> dict:
    """Check Neo4j connectivity and return status."""
    try:
        driver = await get_neo4j_driver()
        await driver.verify_connectivity()
        
        async with get_neo4j_session() as session:
            result = await session.run("RETURN 1 as health")
            record = await result.single()
            
        return {
            "status": "healthy",
            "uri": settings.neo4j_uri,
            "database": settings.neo4j_database,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


async def check_gds_available() -> bool:
    """Check if Neo4j Graph Data Science library is available."""
    try:
        async with get_neo4j_session() as session:
            result = await session.run("RETURN gds.version() as version")
            record = await result.single()
            if record:
                logger.info(f"Neo4j GDS version: {record['version']}")
                return True
    except Exception as e:
        logger.warning(f"Neo4j GDS not available: {e}")
    return False
