"""Buat / perbarui user admin pertama.

    python scripts/create_admin.py --email admin@zandar.local --password rahasia123 --name "Admin"
"""

import argparse
import asyncio
import os

from sqlalchemy import select

from core.db import SessionLocal
from core.models import User
from core.security import hash_password


async def main() -> None:
    # Argumen opsional; fallback ke env (ADMIN_EMAIL/ADMIN_PASSWORD/ADMIN_NAME) agar
    # bisa dipanggil polos oleh entrypoint container. Idempoten (update bila sudah ada).
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=os.environ.get("ADMIN_EMAIL"))
    parser.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD"))
    parser.add_argument("--name", default=os.environ.get("ADMIN_NAME", "Admin"))
    args = parser.parse_args()

    if not args.email or not args.password:
        print("create_admin: ADMIN_EMAIL/ADMIN_PASSWORD (atau --email/--password) tak diset — seed admin dilewati.")
        return

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.email == args.email))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                email=args.email,
                name=args.name,
                role="admin",
                hashed_password=hash_password(args.password),
            )
            session.add(user)
            print(f"Admin dibuat: {args.email}")
        else:
            user.hashed_password = hash_password(args.password)
            user.role = "admin"
            print(f"Admin diperbarui: {args.email}")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
