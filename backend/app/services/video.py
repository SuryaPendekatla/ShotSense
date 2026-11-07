"""Shot boundary detection and key-frame extraction with OpenCV.

Frames are sampled at ~5 fps. Each sample is compared with the previous one using two
signals: HSV colour-histogram distance (catches cuts between different scenes) and mean
grey-level pixel difference (catches cuts inside one scene, e.g. wide shot -> close-up,
where colours barely change). A cut is declared when the combined score clearly exceeds
the recent baseline, so steady camera motion does not trigger false cuts.
"""
import base64
import io
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageOps

SAMPLE_FPS = 5.0
MIN_SHOT_SEC = 0.4
MIN_CUT_SCORE = 20.0
BASELINE_FACTOR = 3.0
BASELINE_WINDOW = 25
FRAMES_KEPT_PER_SHOT = 16
KEYFRAME_MAX_SIDE = 960


class VideoError(ValueError):
    pass


@dataclass
class VideoInfo:
    duration_sec: float
    fps: float
    width: int
    height: int


@dataclass
class DetectedShot:
    start_sec: float
    end_sec: float
    keyframe: Image.Image


@dataclass
class _ShotBuffer:
    """Keeps at most FRAMES_KEPT_PER_SHOT evenly spaced frames of the current shot."""
    items: list = field(default_factory=list)
    step: int = 1
    count: int = 0

    def add(self, t: float, frame: np.ndarray) -> None:
        if self.count % self.step == 0:
            self.items.append((t, frame))
            if len(self.items) > FRAMES_KEPT_PER_SHOT:
                self.items = self.items[::2]
                self.step *= 2
        self.count += 1

    def middle(self, start: float, end: float) -> np.ndarray:
        mid = (start + end) / 2
        return min(self.items, key=lambda it: abs(it[0] - mid))[1]


def _signature(frame_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    small = cv2.resize(frame_bgr, (160, 90), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    grey = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
    return hist, grey


def _cut_score(prev: tuple, cur: tuple) -> float:
    corr = cv2.compareHist(prev[0], cur[0], cv2.HISTCMP_CORREL)
    hist_dist = float(np.clip(1.0 - corr, 0.0, 1.0)) * 100.0
    pixel_diff = float(np.mean(np.abs(cur[1] - prev[1]))) / 2.55
    return 0.5 * hist_dist + 0.5 * pixel_diff


def _shrink(frame_bgr: np.ndarray) -> np.ndarray:
    h, w = frame_bgr.shape[:2]
    scale = KEYFRAME_MAX_SIDE / max(h, w)
    if scale < 1:
        frame_bgr = cv2.resize(frame_bgr, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    return frame_bgr


def _is_blank(img: Image.Image) -> bool:
    """True for black (or nearly uniform dark) slugs, e.g. fades between shots."""
    grey = np.asarray(img.convert("L").resize((64, 36)), dtype=np.float32)
    return float(grey.mean()) < 18 and float(np.percentile(grey, 99)) < 60


def _to_pil(frame_bgr: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))


def detect_shots(path: str, max_seconds: float, max_shots: int) -> tuple[VideoInfo, list[DetectedShot], bool]:
    """Split a video into shots. Returns (info, shots, truncated)."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise VideoError("Could not read this video. Try an MP4 (H.264) file.")
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or not np.isfinite(fps) or fps <= 0 or fps > 240:
            fps = 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if frame_count and frame_count > 0 and frame_count / fps > max_seconds + 1:
            raise VideoError(f"Video is {frame_count / fps:.0f}s long; the limit is {max_seconds:.0f}s.")

        step = max(1, round(fps / SAMPLE_FPS))
        shots: list[DetectedShot] = []
        scores: list[float] = []
        buffer = _ShotBuffer()
        prev_sig = None
        shot_start = 0.0
        last_t = 0.0
        truncated = False
        idx = 0

        while True:
            if idx % step == 0:
                ok, frame = cap.read()
                if not ok:
                    break
                t = idx / fps
                if t > max_seconds:
                    raise VideoError(f"Video is longer than the {max_seconds:.0f}s limit.")
                sig = _signature(frame)
                if prev_sig is not None:
                    score = _cut_score(prev_sig, sig)
                    baseline = float(np.median(scores[-BASELINE_WINDOW:])) if scores else 0.0
                    is_cut = score > max(MIN_CUT_SCORE, BASELINE_FACTOR * baseline)
                    if is_cut and t - shot_start >= MIN_SHOT_SEC:
                        shots.append(DetectedShot(shot_start, t, _to_pil(buffer.middle(shot_start, t))))
                        if len(shots) >= max_shots:
                            truncated = True
                            break
                        buffer = _ShotBuffer()
                        shot_start = t
                        scores = []
                    else:
                        scores.append(score)
                buffer.add(t, _shrink(frame))
                prev_sig = sig
                last_t = t
            else:
                if not cap.grab():
                    break
            idx += 1

        if not truncated:
            end = max(last_t + step / fps, shot_start)
            if buffer.items:
                shots.append(DetectedShot(shot_start, end, _to_pil(buffer.middle(shot_start, end))))
        if not shots:
            raise VideoError("No frames could be decoded from this video.")
        duration = shots[-1].end_sec if not truncated else max(last_t, shots[-1].end_sec)
        # Fades to black between shots show up as their own "shots": drop them unless
        # the whole video is dark.
        visible = [s for s in shots if not _is_blank(s.keyframe)]
        return VideoInfo(round(duration, 3), float(fps), width, height), visible or shots, truncated
    finally:
        cap.release()


def load_image(data: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        return img.convert("RGB")
    except Exception as exc:  # noqa: BLE001 - any decode failure is a bad upload
        raise VideoError("Could not read this image.") from exc


def thumbnail_data_url(img: Image.Image, max_side: int = 480) -> str:
    thumb = img.copy()
    thumb.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    thumb.save(buf, format="JPEG", quality=80, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
