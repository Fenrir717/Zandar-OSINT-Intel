from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from core.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    get_settings().database_url,
    echo=False,
    # NullPool: JANGAN pool koneksi lintas event-loop. Setiap task Celery memakai
    # asyncio.run() → loop BARU; koneksi asyncpg terikat ke loop pembuatnya, jadi
    # koneksi ter-pool dari loop lama (apalagi dengan --pool=threads yang menjalankan
    # banyak loop bersamaan) → "Event loop is closed". NullPool bikin koneksi segar
    # per-checkout di loop saat ini. API (uvicorn, satu loop) tetap benar.
    poolclass=NullPool,
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
