from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from core.config import get_settings


class Base(DeclarativeBase):
    pass


def _create_engine():
    return create_async_engine(
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


# Engine global untuk API (uvicorn) — satu event-loop yang hidup lama, aman dipakai ulang.
engine = _create_engine()
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


@asynccontextmanager
async def worker_session() -> AsyncGenerator[AsyncSession, None]:
    """Sesi DB untuk task Celery (setiap task = asyncio.run() → event loop BARU).

    NullPool sudah mencegah koneksi asyncpg ter-pool lintas-loop, tetapi objek
    *engine* itu sendiri menyimpan asyncio.Lock internal yang terikat ke loop
    pertama yang menyentuhnya. Di --pool=threads (banyak loop paralel) engine
    global yang sama dipakai dari loop lain → RuntimeError: "Lock is bound to a
    different event loop". Solusi: engine SEGAR per task, dibuat & dibuang di
    dalam loop task ini sendiri.
    """
    eng = _create_engine()
    maker = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    try:
        async with maker() as session:
            yield session
    finally:
        await eng.dispose()
