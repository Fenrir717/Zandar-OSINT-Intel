from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    get_settings().database_url,
    echo=False,
    pool_pre_ping=True,
    # Gagal-cepat bila sebuah statement menunggu lock terlalu lama (mis. karena
    # proses lain menahan transaksi) — mencegah worker menggantung tanpa batas.
    connect_args={
        "server_settings": {
            "lock_timeout": "15000",  # ms
            "idle_in_transaction_session_timeout": "60000",  # ms — bunuh transaksi yatim
        }
    },
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
