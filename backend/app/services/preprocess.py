"""Image preprocessing shared by training and inference.

The training notebook uses an identical `letterbox` function. Shot scale depends on
framing, so frames are never cropped or stretched: they are scaled to fit a 16:9
canvas and padded with black bars, exactly as a widescreen film would be letterboxed.
"""
import numpy as np
from PIL import Image

INPUT_W, INPUT_H = 384, 224
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def letterbox(img: Image.Image, width: int = INPUT_W, height: int = INPUT_H) -> Image.Image:
    img = img.convert("RGB")
    w, h = img.size
    scale = min(width / w, height / h)
    new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))
    resized = img.resize((new_w, new_h), Image.BILINEAR)
    canvas = Image.new("RGB", (width, height), (0, 0, 0))
    canvas.paste(resized, ((width - new_w) // 2, (height - new_h) // 2))
    return canvas


def to_tensor(img: Image.Image) -> np.ndarray:
    """PIL image -> normalised float32 array of shape (3, INPUT_H, INPUT_W)."""
    arr = np.asarray(letterbox(img), dtype=np.float32) / 255.0
    arr = (arr - MEAN) / STD
    return arr.transpose(2, 0, 1)
