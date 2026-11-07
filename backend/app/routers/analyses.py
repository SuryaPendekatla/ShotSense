import os
import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..auth import get_current_user
from ..config import get_settings
from ..db import get_db
from ..models import Analysis, Shot, User
from ..schemas import AnalysisOut, AnalysisSummary
from ..services.classifier import ModelNotLoaded, ShotClassifier
from ..services.llm import ShotFacts, build_breakdown
from ..services.video import VideoError, detect_shots, load_image, thumbnail_data_url

router = APIRouter(prefix="/api/analyses", tags=["analyses"])

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
CHUNK = 1024 * 1024


def _classifier(request: Request) -> ShotClassifier:
    clf: ShotClassifier = request.app.state.classifier
    if not clf.loaded:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "The shot classifier is not loaded. Add the trained model to backend/model.")
    return clf


def _save_upload(upload: UploadFile, suffix: str, max_bytes: int) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := upload.file.read(CHUNK):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE,
                                        f"File is larger than {max_bytes // CHUNK} MB")
                out.write(chunk)
    except BaseException:
        os.unlink(path)
        raise
    if size == 0:
        os.unlink(path)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The uploaded file is empty")
    return path


@router.post("", response_model=AnalysisOut, status_code=status.HTTP_201_CREATED)
def create_analysis(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
    notes: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Analysis:
    settings = get_settings()
    if user.guest is not None and user.guest.analyses_used >= settings.guest_max_analyses:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"The demo includes {settings.guest_max_analyses} analyses and you've used them all. "
                            "Create a free account to keep going.")
    clf = _classifier(request)
    filename = Path(file.filename or "upload").name[:255]
    ext = Path(filename).suffix.lower()
    if ext not in VIDEO_EXTS | IMAGE_EXTS:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            "Upload a video (MP4, MOV, WebM, MKV, AVI) or an image (JPG, PNG, WebP)")
    t0 = time.perf_counter()
    path = _save_upload(file, ext, settings.max_upload_mb * CHUNK)
    try:
        if ext in VIDEO_EXTS:
            info, detected, truncated = detect_shots(path, settings.max_video_seconds, settings.max_shots)
            spans = [(d.start_sec, d.end_sec) for d in detected]
            frames = [d.keyframe for d in detected]
            meta = dict(source_type="video", duration_sec=info.duration_sec, fps=info.fps,
                        width=info.width, height=info.height, truncated=truncated)
        else:
            with open(path, "rb") as fh:
                img = load_image(fh.read())
            spans, frames = [(0.0, 0.0)], [img]
            meta = dict(source_type="image", duration_sec=0.0, fps=0.0,
                        width=img.width, height=img.height, truncated=False)
    except VideoError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))
    finally:
        os.unlink(path)

    try:
        predictions = clf.predict(frames)
    except ModelNotLoaded as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))

    facts = []
    for i, ((start, end), frame, preds) in enumerate(zip(spans, frames, predictions), start=1):
        facts.append(ShotFacts(i, round(start, 3), round(end, 3), preds[0][0], preds[0][1],
                               thumbnail_data_url(frame)))
    notes = notes.strip()[:1000]
    breakdown = build_breakdown(settings, facts, notes)

    analysis = Analysis(
        user_id=user.id,
        title=(title.strip() or Path(filename).stem)[:200],
        filename=filename,
        notes=notes,
        shot_count=len(facts),
        summary=breakdown.summary,
        pacing=breakdown.pacing,
        breakdown_source=breakdown.source,
        model_version=clf.version,
        **meta,
    )
    for f, preds in zip(facts, predictions):
        analysis.shots.append(Shot(
            index=f.index, start_sec=f.start_sec, end_sec=f.end_sec, label=f.label,
            confidence=round(f.confidence, 4),
            top3=[{"label": lab, "confidence": round(p, 4)} for lab, p in preds[:3]],
            thumbnail=f.thumbnail,
            description=breakdown.descriptions.get(f.index, ""),
            prompt=breakdown.prompts.get(f.index, ""),
        ))
    analysis.processing_ms = round((time.perf_counter() - t0) * 1000)
    if user.guest is not None:
        user.guest.analyses_used += 1
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


@router.get("", response_model=list[AnalysisSummary])
def list_analyses(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[AnalysisSummary]:
    rows = db.scalars(
        select(Analysis).where(Analysis.user_id == user.id)
        .options(selectinload(Analysis.shots))
        .order_by(Analysis.created_at.desc()).limit(100)
    ).all()
    out = []
    for a in rows:
        counts: dict[str, int] = {}
        for s in a.shots:
            counts[s.label] = counts.get(s.label, 0) + 1
        out.append(AnalysisSummary(
            id=a.id, title=a.title, filename=a.filename, source_type=a.source_type,
            duration_sec=a.duration_sec, shot_count=a.shot_count, created_at=a.created_at,
            cover=a.shots[0].thumbnail if a.shots else None, label_counts=counts))
    return out


def _get_owned(db: Session, analysis_id: int, user: User) -> Analysis:
    analysis = db.scalar(
        select(Analysis).where(Analysis.id == analysis_id, Analysis.user_id == user.id)
        .options(selectinload(Analysis.shots)))
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
    return analysis


@router.get("/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Analysis:
    return _get_owned(db, analysis_id, user)


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(analysis_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    db.delete(_get_owned(db, analysis_id, user))
    db.commit()
