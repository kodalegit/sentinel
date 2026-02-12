FROM python:3.12-slim

WORKDIR /app

# SHAP 0.50.0 pulls prerelease numba/llvmlite on Python 3.12.
ENV UV_PRERELEASE=allow

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev --prerelease=allow

# Copy application code
COPY . .

EXPOSE 8000

CMD ["uv", "run", "--prerelease=allow", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
