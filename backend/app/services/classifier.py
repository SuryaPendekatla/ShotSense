"""ONNX Runtime wrapper around the fine-tuned ResNet-18 shot-scale classifier."""
import hashlib
import json
import logging
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

from .preprocess import to_tensor

log = logging.getLogger("shotsense")

MODEL_FILE = "shotsense.onnx"
METRICS_FILE = "metrics.json"
BATCH = 16


class ModelNotLoaded(RuntimeError):
    pass


class ShotClassifier:
    def __init__(self, model_dir: Path):
        self.model_dir = Path(model_dir)
        self.session: ort.InferenceSession | None = None
        self.classes: list[str] = []
        self.metrics: dict = {}
        self.version = ""
        self.load()

    @property
    def loaded(self) -> bool:
        return self.session is not None

    @property
    def dummy(self) -> bool:
        return bool(self.metrics.get("dummy"))

    def load(self) -> None:
        model_path = self.model_dir / MODEL_FILE
        metrics_path = self.model_dir / METRICS_FILE
        if not model_path.exists() or not metrics_path.exists():
            log.warning("No model found in %s: run training/train_shotsense.ipynb and copy "
                        "%s and %s there.", self.model_dir, MODEL_FILE, METRICS_FILE)
            return
        self.metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        self.classes = list(self.metrics["classes"])
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(str(model_path), opts, providers=["CPUExecutionProvider"])
        n_out = self.session.get_outputs()[0].shape[-1]
        if isinstance(n_out, int) and n_out != len(self.classes):
            raise ValueError(f"Model outputs {n_out} classes but metrics.json lists {len(self.classes)}")
        digest = hashlib.sha256(model_path.read_bytes()).hexdigest()[:10]
        self.version = self.metrics.get("version") or f"resnet18-{digest}"
        log.info("Loaded shot classifier %s with classes %s", self.version, self.classes)

    def predict(self, images: list[Image.Image]) -> list[list[tuple[str, float]]]:
        """Return, per image, all (label, probability) pairs sorted by probability."""
        if self.session is None:
            raise ModelNotLoaded("The shot classifier is not loaded.")
        input_name = self.session.get_inputs()[0].name
        results: list[list[tuple[str, float]]] = []
        for i in range(0, len(images), BATCH):
            batch = np.stack([to_tensor(img) for img in images[i:i + BATCH]]).astype(np.float32)
            logits = self.session.run(None, {input_name: batch})[0]
            logits = logits - logits.max(axis=1, keepdims=True)
            probs = np.exp(logits)
            probs /= probs.sum(axis=1, keepdims=True)
            for row in probs:
                order = np.argsort(row)[::-1]
                results.append([(self.classes[j], float(row[j])) for j in order])
        return results
