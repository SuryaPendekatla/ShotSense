import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .config import BACKEND_DIR, get_settings
from .db import Base, SessionLocal, engine
from .routers import analyses, auth
from .routers.auth import cleanup_guests
from .schemas import LabelInfo, ModelInfo, PublicConfig
from .services.classifier import ShotClassifier
from .services.labels import label_info
from .services.llm import resolve_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()

# Built React app, copied in by the Dockerfile. Absent during local development.
STATIC_DIR = BACKEND_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        cleanup_guests(db)
    app.state.classifier = ShotClassifier(settings.model_dir)
    yield


app = FastAPI(
    title="ShotSense API",
    description="Classifies the shot scale of every shot in a video and writes AI video-generation prompts.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(analyses.router)


@app.get("/api/health", tags=["meta"])
def health(request: Request) -> dict:
    clf: ShotClassifier = request.app.state.classifier
    return {"status": "ok", "model_loaded": clf.loaded}


@app.get("/api/model", response_model=ModelInfo, tags=["meta"])
def model_info(request: Request) -> ModelInfo:
    clf: ShotClassifier = request.app.state.classifier
    labels = [LabelInfo(key=k, name=label_info(k)["name"], abbr=label_info(k)["abbr"],
                        order=label_info(k)["order"]) for k in clf.classes]
    metrics = {k: v for k, v in clf.metrics.items() if k != "classes"}
    return ModelInfo(loaded=clf.loaded, dummy=clf.dummy, version=clf.version,
                     labels=sorted(labels, key=lambda lab: lab.order), metrics=metrics)


@app.get("/api/config", response_model=PublicConfig, tags=["meta"])
def public_config() -> PublicConfig:
    return PublicConfig(
        guest_enabled=settings.guest_enabled,
        guest_max_analyses=settings.guest_max_analyses,
        guest_session_hours=settings.guest_session_hours,
        llm_enabled=resolve_provider(settings) is not None,
        max_upload_mb=settings.max_upload_mb,
        max_video_seconds=settings.max_video_seconds,
    )


if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (STATIC_DIR / full_path).resolve()
        if full_path and candidate.is_file() and STATIC_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
