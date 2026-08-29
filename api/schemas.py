import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    role: str

    model_config = {"from_attributes": True}


class InvestigationCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str | None = None
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    data_policy: str = Field(default="local_only", pattern="^(local_only|api_ok)$")
    budget_cap_usd: float | None = Field(default=None, ge=0)
    project_id: uuid.UUID | None = None  # None → dibuatkan project default milik user


class InvestigationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = None
    status: str | None = Field(default=None, pattern="^(planning|collecting|analyzing|verifying|done)$")
    priority: str | None = Field(default=None, pattern="^(low|medium|high|critical)$")
    progress: int | None = Field(default=None, ge=0, le=100)
    budget_cap_usd: float | None = Field(default=None, ge=0)


class InvestigationOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None
    status: str
    priority: str
    progress: int
    data_policy: str
    budget_cap_usd: float | None
    deadline: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
