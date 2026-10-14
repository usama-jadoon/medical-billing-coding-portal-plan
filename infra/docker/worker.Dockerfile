FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/
RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] pydantic pydantic-settings sqlalchemy asyncpg aiosqlite alembic python-multipart pyjwt bcrypt pypdf httpx "openpyxl==3.1.5" "pillow>=11,<13" "pypdfium2>=4.30,<6" "pydantic[email]"

COPY services/ /app/services/
COPY scripts/ /app/scripts/

CMD ["python", "-m", "services.worker.worker"]
