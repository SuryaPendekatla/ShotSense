from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    created_at: datetime


class Prediction(BaseModel):
    label: str
    confidence: float


class ShotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    index: int
    start_sec: float
    end_sec: float
    label: str
    confidence: float
    top3: list[Prediction]
    thumbnail: str
    description: str
    prompt: str


class AnalysisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    filename: str
    source_type: str
    duration_sec: float
    shot_count: int
    created_at: datetime
    cover: str | None = None
    label_counts: dict[str, int] = {}


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    filename: str
    source_type: str
    notes: str
    duration_sec: float
    fps: float
    width: int
    height: int
    shot_count: int
    truncated: bool
    summary: str
    pacing: str
    breakdown_source: str
    model_version: str
    processing_ms: int
    created_at: datetime
    shots: list[ShotOut]


class LabelInfo(BaseModel):
    key: str
    name: str
    abbr: str
    order: int


class ModelInfo(BaseModel):
    loaded: bool
    dummy: bool
    version: str
    labels: list[LabelInfo]
    metrics: dict


class PublicConfig(BaseModel):
    demo_enabled: bool
    demo_email: str | None = None
    demo_password: str | None = None
    llm_enabled: bool
    max_upload_mb: int
    max_video_seconds: int
