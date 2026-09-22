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
    fastapi uvicorn[standard] pydantic pydantic-settings sqlalchemy psycopg[binary] aiosqlite alembic python-multipart pyjwt bcrypt pypdf httpx "pydantic[email]" aiofiles

COPY services/ /app/services/

EXPOSE 8000

CMD ["uvicorn", "services.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
