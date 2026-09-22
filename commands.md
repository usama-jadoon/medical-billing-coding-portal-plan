# Commands

## Prerequisites

Install:

- Git
- Node.js LTS
- pnpm
- Python 3.12+
- Docker Desktop

Verify:

```powershell
git --version
node --version
pnpm --version
python --version
docker --version
docker compose version
```

## Create repository

```powershell
mkdir medical-coding-portal
cd medical-coding-portal
git init
```

## Frontend

```powershell
pnpm create next-app@latest apps/web --ts --tailwind --eslint --app --src-dir
```

## Python backend

```powershell
mkdir services
mkdir services\api
python -m venv services\api\.venv
.\services\api\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install fastapi uvicorn[standard] pydantic sqlalchemy psycopg[binary] alembic python-multipart
```

## Worker

```powershell
mkdir services\worker
pip install redis celery
```

## Local infrastructure

```powershell
docker compose up -d postgres redis minio
```

## Run frontend

```powershell
pnpm --dir apps/web dev
```

## Run API

```powershell
.\services\api\.venv\Scripts\Activate.ps1
uvicorn services.api.app:app --reload
```

## Database migration

```powershell
alembic upgrade head
```

## Tests

```powershell
pnpm test
```

Python:

```powershell
pytest
```

## Lint

```powershell
pnpm lint
```

## Build

```powershell
pnpm build
```

## Security checks

```powershell
pnpm audit
```

Python dependency audit can be added later with approved tooling.

## Git workflow

```powershell
git status
git add .
git commit -m "chore: initialize medical coding portal"
```

## Environment

Create:

```text
.env
```

Never commit it.

Example variables:

```text
DATABASE_URL=
REDIS_URL=
S3_ENDPOINT=
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_BUCKET=
LLM_PROVIDER=
LLM_BASE_URL=
LLM_API_KEY=
APP_ENV=development
```

## Local development rule

Use synthetic/de-identified records only.

Do not upload real PHI into local development until security and contractual requirements are addressed.
