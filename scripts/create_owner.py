"""Create the named private-workspace owner without logging a password."""
import asyncio
import getpass
from sqlalchemy import select
from services.api.config import settings
from services.api.db.session import async_session_factory, engine
from services.api.db.models import User, Organization
from services.api.security.auth import hash_password


async def create(email, password):
    async with async_session_factory() as db:
        if (await db.execute(select(User.id).where(User.role == 'Owner'))).first():
            raise ValueError('An owner already exists. No account was changed.')
        if (await db.execute(select(User.id).where(User.email == email))).first():
            raise ValueError('Email already exists. No account was changed.')
        org = Organization(name='Private coding workspace')
        db.add(org)
        await db.flush()
        db.add(User(organization_id=org.id, email=email, role='Owner', password_hash=hash_password(password)))
        await db.commit()
    await engine.dispose()
    print('Owner created. Sign in through the web application.')


if __name__ == '__main__':
    email = settings.OWNER_EMAIL or input('Owner email: ').strip()
    password = getpass.getpass('Password (12+ characters): ')
    if len(password) < 12 or len(password.encode()) > 72:
        raise ValueError('Password must have at least 12 characters and no more than 72 UTF-8 bytes.')
    if password != getpass.getpass('Confirm password: '):
        raise ValueError('Passwords do not match.')
    asyncio.run(create(email, password))
