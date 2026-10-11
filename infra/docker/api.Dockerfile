FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/
RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] pydantic pydantic-settings sqlalchemy asyncpg aiosqlite alembic python-multipart pyjwt bcrypt pypdf httpx "pydantic[email]"

COPY services/ /app/services/
COPY alembic.ini /app/

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn services.api.app:app --host 0.0.0.0 --port 8000"]
