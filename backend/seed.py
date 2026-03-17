"""
Seed script runner. Run from the backend directory:
    uv run python seed.py
"""

import argparse
import asyncio
from db.seed import reset_and_seed, reset_application_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        nargs="?",
        default="synthetic",
        choices=["synthetic", "reset"],
    )
    args = parser.parse_args()
    if args.mode == "reset":
        asyncio.run(reset_application_data())
    else:
        asyncio.run(reset_and_seed())
