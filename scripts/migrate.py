"""Upgrade a fresh or legacy development database without discarding records."""
import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from services.api.db.session import engine
from services.api.config import settings


async def inspect_tables():
    async with engine.connect() as connection:
        result = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
    await engine.dispose()
    return result


def main():
    tables = asyncio.run(inspect_tables())
    if settings.DATABASE_URL.startswith('sqlite+aiosqlite:///'):
        path = Path(settings.DATABASE_URL.split('///', 1)[1])
        if path.is_file():
            backup = path.with_name(path.name + datetime.now(timezone.utc).strftime('.%Y%m%d%H%M%S.backup'))
            with sqlite3.connect(path) as source, sqlite3.connect(backup) as destination:
                source.backup(destination)
            print(f'Database backup: {backup}')
    config = Config('alembic.ini')
    if 'encounters' in tables and 'alembic_version' not in tables:
        command.stamp(config, '001_initial_schema')
    command.upgrade(config, 'head')
    print('Database is at the current schema.')


if __name__ == '__main__':
    main()
