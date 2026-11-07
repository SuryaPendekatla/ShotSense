"""Synthetic test media with known shot boundaries."""
import cv2
import numpy as np

W, H, FPS = 640, 360, 25
SCENE_SEC = 3
CUTS = [3.0, 6.0, 9.0]  # expected boundaries for make_video()


def _scene_frame(scene: int, i: int, rng: np.random.Generator, noise: np.ndarray) -> np.ndarray:
    t = i / FPS
    frame = np.zeros((H, W, 3), np.uint8)
    if scene == 0:  # wide: blue room, large white circle drifting (camera move)
        frame[:] = (160, 70, 30)
        cv2.circle(frame, (int(220 + 20 * t), 180), 120, (240, 240, 240), -1)
    elif scene == 1:  # same palette, much tighter subject: only pixels change, not colours
        frame[:] = (160, 70, 30)
        cv2.rectangle(frame, (0, 0), (W, H // 2), (240, 240, 240), -1)
        cv2.circle(frame, (int(500 - 10 * t), 260), 40, (240, 240, 240), -1)
    elif scene == 2:  # warm textured scene with a slow pan
        shift = int(8 * t * FPS) % W
        frame = np.roll(noise, shift, axis=1)
    else:  # green scene with fast-moving stripes (motion must not cause cuts)
        frame[:] = (40, 150, 40)
        for x in range(-200, W + 200, 80):
            xx = x + int(60 * t)
            cv2.rectangle(frame, (xx, 0), (xx + 30, H), (90, 210, 90), -1)
    return frame


def make_video(path: str) -> None:
    rng = np.random.default_rng(1)
    noise = np.zeros((H, W, 3), np.uint8)
    noise[..., 2] = rng.integers(150, 255, (H, W))
    noise[..., 1] = rng.integers(60, 140, (H, W))
    noise[..., 0] = rng.integers(0, 50, (H, W))
    noise = cv2.GaussianBlur(noise, (7, 7), 0)
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    assert writer.isOpened(), "OpenCV could not open a video writer"
    for scene in range(4):
        for i in range(SCENE_SEC * FPS):
            writer.write(_scene_frame(scene, i, rng, noise))
    writer.release()


def make_png() -> bytes:
    img = np.full((720, 1280, 3), (30, 30, 30), np.uint8)
    cv2.circle(img, (640, 360), 250, (200, 180, 160), -1)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()
