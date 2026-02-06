"""
Seed script runner. Run from the backend directory:
    uv run python seed.py
"""

import asyncio
from db.seed import reset_and_seed

if __name__ == "__main__":
    asyncio.run(reset_and_seed())
