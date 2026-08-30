"""Knowledge graph (Fase 3) — entitas NER + ko-okurensi dari Neo4j.

POST /investigations/{id}/graph/build → picu NER→Neo4j (Celery).
GET  /investigations/{id}/graph       → node + edge untuk visualisasi.
"""

import asyncio
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from api.deps import CurrentUser, DbSession
from core.models import AuditLog, Investigation

router = APIRouter(tags=["graph"])


class BuildAccepted(BaseModel):
    task_id: str
    status: str


@router.post(
    "/investigations/{investigation_id}/graph/build",
    response_model=BuildAccepted, status_code=status.HTTP_202_ACCEPTED,
)
async def build(investigation_id: uuid.UUID, session: DbSession, user: CurrentUser) -> BuildAccepted:
    inv = await session.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigasi tidak ditemukan")
    session.add(AuditLog(user_id=user.id, action="graph.build", resource=f"investigation:{investigation_id}"))
    await session.commit()

    from workers.tasks import build_graph as task

    t = task.delay(str(investigation_id))
    return BuildAccepted(task_id=t.id, status="queued")


@router.get("/investigations/{investigation_id}/graph")
async def get_graph(investigation_id: uuid.UUID, user: CurrentUser) -> dict:
    """Node + edge knowledge graph (dari Neo4j). Kosong bila belum dibangun."""
    from core import graph

    inv = str(investigation_id)
    data = await asyncio.to_thread(graph.read_graph, inv)
    stats = await asyncio.to_thread(graph.graph_stats, inv)
    return {**data, "stats": stats}
