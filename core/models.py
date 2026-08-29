"""Model SQLAlchemy — implementasi ERD PRD §8.1 + §10.6.

PostgreSQL adalah sumber kebenaran; Qdrant & Neo4j adalah indeks turunan
yang bisa dibangun ulang dari tabel-tabel ini + raw lake (MinIO).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ---------------------------------------------------------------- asosiasi

comment_topics = Table(
    "comment_topics",
    Base.metadata,
    Column("comment_id", UUID(as_uuid=True), ForeignKey("comments.id", ondelete="CASCADE"), primary_key=True),
    Column("topic_id", UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
    Column("score", Float, nullable=True),
)

narrative_evidence = Table(
    "narrative_evidence",
    Base.metadata,
    Column("narrative_id", UUID(as_uuid=True), ForeignKey("narratives.id", ondelete="CASCADE"), primary_key=True),
    Column("comment_id", UUID(as_uuid=True), ForeignKey("comments.id", ondelete="CASCADE"), primary_key=True),
)


# ---------------------------------------------------------------- inti

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="analyst")  # admin|lead|analyst
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[uuid.UUID] = _uuid_pk()
    # company|org|state|politic|figure|individual|trending|event (PRD §10.1)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = _created_at()


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("targets.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # planning|collecting|analyzing|verifying|done
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planning")
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")  # low|medium|high|critical
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    budget_cap_usd: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    # local_only: klasifikasi wajib model lokal, konten tidak keluar infra (PRD §7.4)
    data_policy: Mapped[str] = mapped_column(String(20), nullable=False, default="local_only")  # local_only|api_ok
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created_at()

    collections: Mapped[list["Collection"]] = relationship(back_populates="investigation")


# ---------------------------------------------------------------- koleksi

class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = _uuid_pk()
    platform: Mapped[str] = mapped_column(String(30), nullable=False)  # youtube|reddit|rss|telegram|forum
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # ref kredensial (vault), rate limit
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = _created_at()


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = _uuid_pk()
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False)
    query: Mapped[dict] = mapped_column(JSONB, nullable=False)  # keyword, channel, periode
    schedule_cron: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _created_at()

    investigation: Mapped[Investigation] = relationship(back_populates="collections")


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")  # queued|running|done|failed
    items_collected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (UniqueConstraint("platform", "external_id", name="uq_comments_platform_external"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    collection_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collection_runs.id"), nullable=False)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    author_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # pseudonim (HMAC) — UU PDP
    content: Mapped[str] = mapped_column(Text, nullable=False)
    lang: Mapped[str | None] = mapped_column(String(8), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_ref: Mapped[str | None] = mapped_column(Text, nullable=True)  # pointer objek MinIO
    dedup_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _created_at()


# ---------------------------------------------------------------- analisis

class Analysis(Base):
    __tablename__ = "analyses"

    comment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), primary_key=True
    )
    sentiment: Mapped[str | None] = mapped_column(String(10), nullable=True)  # pos|neg|neu|mixed
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    emotion: Mapped[str | None] = mapped_column(String(20), nullable=True)
    intent: Mapped[str | None] = mapped_column(String(20), nullable=True)
    toxicity: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_bot_suspect: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # hasil job CIB
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = _uuid_pk()
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    keywords: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Narrative(Base):
    __tablename__ = "narratives"

    id: Mapped[uuid.UUID] = _uuid_pk()
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _created_at()


class NarrativeAssessment(Base):
    """Skoring dua-sumbu PRD §10: ABC+D → Otentisitas × Kebenaran → kuadran."""

    __tablename__ = "narrative_assessments"

    narrative_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("narratives.id", ondelete="CASCADE"), primary_key=True
    )
    score_actors: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_behavior: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_content: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_distribution: Mapped[float | None] = mapped_column(Float, nullable=True)
    authenticity: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0 organik .. 1 terkoordinasi
    veracity: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0 salah .. 1 benar
    quadrant: Mapped[str | None] = mapped_column(String(20), nullable=True)  # healthy|agenda|rumor|operation
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    disarm_ttp: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------- verifikasi klaim (Graph E)

class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = _uuid_pk()
    narrative_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("narratives.id", ondelete="SET NULL"), nullable=True
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    check_worthy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = _created_at()


class EvidenceSource(Base):
    __tablename__ = "evidence_sources"

    id: Mapped[uuid.UUID] = _uuid_pk()
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    credibility_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    provenance: Mapped[str | None] = mapped_column(String(20), nullable=True)  # c2pa|none|unknown


class ClaimVerdict(Base):
    __tablename__ = "claim_verdicts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False)
    # supported|refuted|insufficient|conflicting — taksonomi AVeriTeC
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_refs: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # draft|reviewed — verdict sensitif berstatus draft sampai analis menyetujui
    review_status: Mapped[str] = mapped_column(String(10), nullable=False, default="draft")
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = _created_at()


# ---------------------------------------------------------------- output & sistem

class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = _uuid_pk()
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False, default="restricted")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    content_ref: Mapped[str | None] = mapped_column(Text, nullable=True)  # pointer MinIO
    generated_by_run: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    graph_name: Mapped[str] = mapped_column(String(20), nullable=False)  # planner|analysis|report|veracity
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    langfuse_trace_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime] = _created_at()
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EntityRegistry(Base):
    """Jembatan baris relasional ↔ node Neo4j (PRD §8.1)."""

    __tablename__ = "entity_registry"

    id: Mapped[uuid.UUID] = _uuid_pk()
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False
    )
    neo4j_element_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = _created_at()
