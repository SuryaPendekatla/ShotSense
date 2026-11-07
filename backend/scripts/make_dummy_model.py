"""Create a placeholder ONNX model with the same inputs and outputs as the real one.

Use it to run the app and the tests before you have trained the real model:
    python scripts/make_dummy_model.py model/
The UI shows a warning while the dummy model is loaded. Predictions are meaningless.
"""
import json
import sys
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

CLASSES = ["closeUp", "detail", "extremeLongShot", "fullShot", "longShot", "mediumCloseUp", "mediumShot"]
H, W = 224, 384


def build(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    pool = 8  # 224x384 input -> 28x48 grid -> flattened features
    feat = 3 * (H // pool) * (W // pool)
    weight = numpy_helper.from_array(rng.normal(0, 0.05, (feat, len(CLASSES))).astype(np.float32), "W")
    bias = numpy_helper.from_array(np.zeros(len(CLASSES), dtype=np.float32), "B")
    nodes = [
        helper.make_node("AveragePool", ["input"], ["pooled"], kernel_shape=[pool, pool], strides=[pool, pool]),
        helper.make_node("Flatten", ["pooled"], ["flat"], axis=1),
        helper.make_node("Gemm", ["flat", "W", "B"], ["logits"]),
    ]
    graph = helper.make_graph(
        nodes, "shotsense_dummy",
        [helper.make_tensor_value_info("input", TensorProto.FLOAT, ["batch", 3, H, W])],
        [helper.make_tensor_value_info("logits", TensorProto.FLOAT, ["batch", len(CLASSES)])],
        initializer=[weight, bias],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 9
    onnx.checker.check_model(model)
    onnx.save(model, out_dir / "shotsense.onnx")
    (out_dir / "metrics.json").write_text(json.dumps({
        "classes": CLASSES, "dummy": True, "version": "dummy-untrained",
        "note": "Placeholder model. Run training/train_shotsense.ipynb for the real one.",
    }, indent=2))
    print(f"Wrote dummy model to {out_dir}")


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else "model"))
