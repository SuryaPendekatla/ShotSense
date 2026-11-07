"""Generates train_shotsense.ipynb from the cells below (keeps the notebook diff-friendly).

    python build_notebook.py
"""
import json
from pathlib import Path

CELLS: list[tuple[str, str]] = []


def md(src: str) -> None:
    CELLS.append(("markdown", src.strip("\n")))


def code(src: str) -> None:
    CELLS.append(("code", src.strip("\n")))


md("""
# ShotSense: training the shot-scale classifier

This notebook trains the model behind ShotSense, which labels each shot of a video with its
**shot scale**: detail, close-up, medium close-up, medium shot, full shot, long shot or extreme long shot.

It runs four steps:

1. Loads [*What a Shot!*](https://huggingface.co/datasets/szymonrucinski/types-of-film-shots), a set of 2,919 film frames (CC-BY-4.0).
2. Trains a **scikit-learn baseline** (HOG features + logistic regression).
3. Fine-tunes an ImageNet-pretrained **ResNet-18 in PyTorch** and compares it with the baseline.
4. Exports the model to **ONNX** for fast CPU inference in the FastAPI backend.

**Run it on Google Colab with a GPU:** open *Runtime → Change runtime type → T4 GPU*, then *Runtime → Run all*.
It takes about 15–25 minutes. When it finishes, it downloads `shotsense.onnx`, `metrics.json` and
`confusion_matrix.png`. Put all three in `backend/model/`.

**Evaluation is honest by design:** the test set contains only human-labelled frames, which are never used for training.
""")

code("""
# Colab already ships PyTorch, torchvision, scikit-learn and scikit-image.
!pip -q install datasets onnx onnxruntime onnxscript
""")

code("""
import copy, json, os, random, time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torchvision
from PIL import Image
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from tqdm.auto import tqdm

SEED = 42
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)

DATASET = "szymonrucinski/types-of-film-shots"
INPUT_W, INPUT_H = 384, 224          # 16:9 canvas; must match backend/app/services/preprocess.py
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
EPOCHS = int(os.environ.get("SHOTSENSE_EPOCHS", 15))
BATCH_SIZE = 32

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("PyTorch", torch.__version__, "| device:", device)
if device.type == "cpu":
    print("WARNING: no GPU. In Colab use Runtime > Change runtime type > T4 GPU, or training will be slow.")
""")

md("""
## 1. Load the data

Each frame has a `label` and an `annotator`: **human** (863 hand-labelled frames) or **ai** (2,056 frames labelled by a
DINOv2 classifier, with low-confidence cases re-checked by Claude Opus). The 4 frames still marked *ambiguous* are dropped.
""")

code("""
from datasets import load_dataset, concatenate_datasets

raw = load_dataset(DATASET)
ds = concatenate_datasets([raw[s] for s in raw]) if len(raw) > 1 else raw[next(iter(raw))]
print(ds)

label_feature = ds.features["label"]
label_to_str = (lambda v: label_feature.names[v]) if hasattr(label_feature, "names") else str

meta = ds.remove_columns(["image"]).to_pandas()
meta["label"] = meta["label"].map(label_to_str)
if "annotator" not in meta:
    meta["annotator"] = "human"
meta["row"] = np.arange(len(meta))
meta = meta[meta["label"] != "ambiguous"].reset_index(drop=True)

CLASSES = sorted(meta["label"].unique())
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASSES)}
meta["y"] = meta["label"].map(CLASS_TO_IDX)
print("Classes:", CLASSES)
pd.crosstab(meta["label"], meta["annotator"], margins=True)
""")

md("""
## 2. Split: human-labelled frames are the gold test set

The human frames are split 40% train / 20% validation / 40% test, stratified by class. All AI-labelled frames go to
training. Validation is used to choose the best epoch and the baseline's regularisation; **test is touched once, at the end.**
""")

code("""
human = meta[meta["annotator"] == "human"]
ai = meta[meta["annotator"] != "human"]

h_train, h_rest = train_test_split(human, test_size=0.6, stratify=human["y"], random_state=SEED)
h_val, h_test = train_test_split(h_rest, test_size=2 / 3, stratify=h_rest["y"], random_state=SEED)

splits = {
    "train": pd.concat([ai, h_train]).reset_index(drop=True),
    "val": h_val.reset_index(drop=True),
    "test": h_test.reset_index(drop=True),
}
for name, df in splits.items():
    print(f"{name:5s}: {len(df):5d} frames  ({(df['annotator'] == 'human').sum()} human-labelled)")
""")

md("""
## 3. Preprocessing: letterbox, never crop

Shot scale *is* the framing, so random crops or stretching would change the true label (cropping a long shot can make it look
like a medium shot). Each frame is scaled to fit a 384×224 (16:9) canvas and padded with black bars. The backend uses the exact
same function. Frames are decoded once and cached in memory as uint8 arrays.
""")

code("""
def letterbox(img, width=INPUT_W, height=INPUT_H):
    img = img.convert("RGB")
    w, h = img.size
    scale = min(width / w, height / h)
    new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))
    resized = img.resize((new_w, new_h), Image.BILINEAR)
    canvas = Image.new("RGB", (width, height), (0, 0, 0))
    canvas.paste(resized, ((width - new_w) // 2, (height - new_h) // 2))
    return canvas


def load_split(df):
    out = np.zeros((len(df), INPUT_H, INPUT_W, 3), dtype=np.uint8)
    for i, row in enumerate(tqdm(df["row"].tolist(), desc="decoding", leave=False)):
        out[i] = np.asarray(letterbox(ds[int(row)]["image"]))
    return out


images = {name: load_split(df) for name, df in splits.items()}
labels = {name: df["y"].to_numpy() for name, df in splits.items()}

fig, axes = plt.subplots(2, 4, figsize=(16, 5))
for ax, i in zip(axes.flat, np.random.choice(len(images["test"]), 8, replace=False)):
    ax.imshow(images["test"][i]); ax.set_title(CLASSES[labels["test"][i]]); ax.axis("off")
plt.tight_layout(); plt.show()
""")

md("""
## 4. Baseline: HOG features + logistic regression (scikit-learn)

Histogram-of-oriented-gradients features capture edge layout, which says a lot about how large the subject is in frame.
The regularisation strength `C` is picked on the validation set.
""")

code("""
from skimage.feature import hog
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def hog_features(batch):
    feats = []
    for arr in tqdm(batch, desc="HOG", leave=False):
        grey = Image.fromarray(arr).convert("L")
        g = np.asarray(grey.resize((192, 112)), dtype=np.float32) / 255.0
        thumb = np.asarray(grey.resize((24, 14)), dtype=np.float32).ravel() / 255.0
        feats.append(np.concatenate([hog(g, orientations=9, pixels_per_cell=(16, 16), cells_per_block=(2, 2)), thumb]))
    return np.stack(feats)


X = {name: hog_features(images[name]) for name in images}
best_c, best_val_f1 = None, -1.0
for c in [0.001, 0.01, 0.1, 1.0]:
    clf = make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=3000))
    clf.fit(X["train"], labels["train"])
    val_f1 = f1_score(labels["val"], clf.predict(X["val"]), average="macro")
    print(f"C={c:<6} val macro-F1 = {val_f1:.3f}")
    if val_f1 > best_val_f1:
        best_c, best_val_f1, baseline = c, val_f1, clf

baseline_pred = baseline.predict(X["test"])
baseline_metrics = {
    "model": "HOG + logistic regression (scikit-learn)",
    "C": best_c,
    "accuracy": round(float(accuracy_score(labels["test"], baseline_pred)), 4),
    "macro_f1": round(float(f1_score(labels["test"], baseline_pred, average="macro")), 4),
}
print("Baseline on the test set:", baseline_metrics)
""")

md("""
## 5. Fine-tune ResNet-18 (PyTorch)

* ImageNet-pretrained ResNet-18 with a new 7-way head; lower learning rate for the backbone than for the head.
* Augmentation keeps framing intact: horizontal flips, brightness/contrast/saturation jitter and occasional greyscale
  (for black-and-white films), applied on the GPU.
* Class-weighted cross-entropy with label smoothing handles class imbalance and the noisier AI labels.
* Mixed precision, cosine learning-rate schedule with a one-epoch warm-up, best epoch picked by validation macro-F1.
""")

code("""
def to_batch(arr_uint8):
    x = torch.from_numpy(arr_uint8).to(device, non_blocking=True).permute(0, 3, 1, 2).float() / 255.0
    return x


MEAN_T = torch.tensor(MEAN, device=device).view(1, 3, 1, 1)
STD_T = torch.tensor(STD, device=device).view(1, 3, 1, 1)


def normalize(x):
    return (x - MEAN_T) / STD_T


def augment(x):
    b = x.shape[0]
    flip = torch.rand(b, device=device) < 0.5
    x = torch.where(flip.view(b, 1, 1, 1), x.flip(-1), x)
    rnd = lambda lo, hi: torch.empty(b, 1, 1, 1, device=device).uniform_(lo, hi)
    x = x * rnd(0.75, 1.25)
    mean = x.mean(dim=(1, 2, 3), keepdim=True)
    x = (x - mean) * rnd(0.75, 1.25) + mean
    grey = (0.299 * x[:, 0:1] + 0.587 * x[:, 1:2] + 0.114 * x[:, 2:3])
    x = grey + (x - grey) * rnd(0.7, 1.3)
    to_grey = (torch.rand(b, device=device) < 0.1).view(b, 1, 1, 1)
    x = torch.where(to_grey, grey.expand_as(x), x)
    return x.clamp(0, 1)


def batches(name, shuffle):
    idx = np.random.permutation(len(images[name])) if shuffle else np.arange(len(images[name]))
    for i in range(0, len(idx), BATCH_SIZE):
        j = np.sort(idx[i:i + BATCH_SIZE])
        yield to_batch(images[name][j]), torch.from_numpy(labels[name][j]).to(device)


@torch.no_grad()
def predict(model, name):
    model.eval()
    preds = []
    for x, _ in batches(name, shuffle=False):
        with torch.autocast(device.type, enabled=device.type == "cuda"):
            preds.append(model(normalize(x)).argmax(1).cpu())
    return torch.cat(preds).numpy()


model = torchvision.models.resnet18(weights=torchvision.models.ResNet18_Weights.IMAGENET1K_V1)
model.fc = nn.Linear(model.fc.in_features, len(CLASSES))
model = model.to(device)

counts = np.bincount(labels["train"], minlength=len(CLASSES))
class_weights = torch.tensor((counts.sum() / (len(CLASSES) * np.maximum(counts, 1))) ** 0.5, dtype=torch.float32, device=device)
criterion = nn.CrossEntropyLoss(weight=class_weights, label_smoothing=0.1)

head = list(model.fc.parameters())
backbone = [p for n, p in model.named_parameters() if not n.startswith("fc.")]
optimizer = torch.optim.AdamW([{"params": backbone, "lr": 2e-4}, {"params": head, "lr": 1e-3}], weight_decay=1e-4)
steps_per_epoch = int(np.ceil(len(images["train"]) / BATCH_SIZE))
total, warmup = EPOCHS * steps_per_epoch, steps_per_epoch
scheduler = torch.optim.lr_scheduler.LambdaLR(
    optimizer, lambda s: (s + 1) / warmup if s < warmup else 0.5 * (1 + np.cos(np.pi * (s - warmup) / max(1, total - warmup))))
scaler = torch.amp.GradScaler(enabled=device.type == "cuda")

history, best_f1, best_state, best_epoch = [], -1.0, None, 0
for epoch in range(1, EPOCHS + 1):
    model.train()
    t0, running, seen = time.time(), 0.0, 0
    for x, y in batches("train", shuffle=True):
        with torch.autocast(device.type, enabled=device.type == "cuda"):
            loss = criterion(model(normalize(augment(x))), y)
        optimizer.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()
        scheduler.step()
        running += loss.item() * len(y); seen += len(y)
    val_pred = predict(model, "val")
    val_f1 = f1_score(labels["val"], val_pred, average="macro")
    val_acc = accuracy_score(labels["val"], val_pred)
    history.append({"epoch": epoch, "train_loss": running / seen, "val_acc": val_acc, "val_macro_f1": val_f1})
    marker = ""
    if val_f1 > best_f1:
        best_f1, best_state, best_epoch, marker = val_f1, copy.deepcopy(model.state_dict()), epoch, "  <- best"
    print(f"epoch {epoch:2d}  loss {running / seen:.3f}  val acc {val_acc:.3f}  val macro-F1 {val_f1:.3f}  ({time.time() - t0:.0f}s){marker}")

model.load_state_dict(best_state)
print(f"Best epoch: {best_epoch} (val macro-F1 {best_f1:.3f})")
""")

code("""
hist = pd.DataFrame(history)
fig, ax = plt.subplots(1, 2, figsize=(12, 3.5))
ax[0].plot(hist["epoch"], hist["train_loss"], marker="o"); ax[0].set_title("Training loss"); ax[0].set_xlabel("epoch")
ax[1].plot(hist["epoch"], hist["val_acc"], marker="o", label="accuracy")
ax[1].plot(hist["epoch"], hist["val_macro_f1"], marker="o", label="macro-F1")
ax[1].set_title("Validation"); ax[1].set_xlabel("epoch"); ax[1].legend()
plt.tight_layout(); plt.show()
""")

md("""
## 6. Final evaluation on the held-out, human-labelled test set
""")

code("""
test_pred = predict(model, "test")
test_acc = float(accuracy_score(labels["test"], test_pred))
test_f1 = float(f1_score(labels["test"], test_pred, average="macro"))
per_class = f1_score(labels["test"], test_pred, average=None, labels=range(len(CLASSES)))
print(classification_report(labels["test"], test_pred, labels=range(len(CLASSES)), target_names=CLASSES, digits=3, zero_division=0))

order = ["detail", "closeUp", "mediumCloseUp", "mediumShot", "fullShot", "longShot", "extremeLongShot"]
order = [c for c in order if c in CLASSES] + [c for c in CLASSES if c not in order]
idx = [CLASS_TO_IDX[c] for c in order]
cm = confusion_matrix(labels["test"], test_pred, labels=idx, normalize="true")
fig, ax = plt.subplots(figsize=(7.5, 6.5))
im = ax.imshow(cm, cmap="Blues", vmin=0, vmax=1)
ax.set_xticks(range(len(order)), order, rotation=45, ha="right"); ax.set_yticks(range(len(order)), order)
for i in range(len(order)):
    for j in range(len(order)):
        ax.text(j, i, f"{cm[i, j]:.2f}", ha="center", va="center", color="white" if cm[i, j] > 0.5 else "black", fontsize=9)
ax.set_xlabel("Predicted"); ax.set_ylabel("True (human label)")
ax.set_title(f"ResNet-18 on human-labelled test set\\naccuracy {test_acc:.1%}, macro-F1 {test_f1:.1%}")
fig.colorbar(im, fraction=0.046); plt.tight_layout()
plt.savefig("confusion_matrix.png", dpi=150); plt.show()

comparison = pd.DataFrame([
    {"model": baseline_metrics["model"], "accuracy": baseline_metrics["accuracy"], "macro-F1": baseline_metrics["macro_f1"]},
    {"model": "ResNet-18 fine-tuned (PyTorch)", "accuracy": round(test_acc, 4), "macro-F1": round(test_f1, 4)},
])
comparison
""")

md("""
## 7. Export to ONNX and verify

The backend serves the model with ONNX Runtime on CPU, which keeps the Docker image small (no PyTorch needed in production).
The check below confirms the ONNX model gives the same predictions as PyTorch.
""")

code("""
import onnx
import onnxruntime as ort

export_model = copy.deepcopy(model).float().cpu().eval()
dummy = torch.randn(1, 3, INPUT_H, INPUT_W)
export_kwargs = dict(input_names=["input"], output_names=["logits"],
                     dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}})
try:
    torch.onnx.export(export_model, (dummy,), "shotsense.onnx", opset_version=17, dynamo=False, **export_kwargs)
except Exception as exc:  # newer PyTorch versions only ship the dynamo-based exporter
    print("TorchScript exporter unavailable, using the dynamo exporter:", type(exc).__name__)
    torch.onnx.export(export_model, (dummy,), "shotsense.onnx", dynamo=True, **export_kwargs)
onnx.save_model(onnx.load("shotsense.onnx"), "shotsense.onnx", save_as_external_data=False)  # one self-contained file
onnx.checker.check_model("shotsense.onnx")

session = ort.InferenceSession("shotsense.onnx", providers=["CPUExecutionProvider"])
sample = images["test"][:8].astype(np.float32) / 255.0
sample = ((sample - MEAN) / STD).transpose(0, 3, 1, 2).astype(np.float32)
onnx_logits = session.run(None, {"input": sample})[0]
with torch.no_grad():
    torch_logits = export_model(torch.from_numpy(sample)).numpy()
max_diff = float(np.abs(onnx_logits - torch_logits).max())
assert (onnx_logits.argmax(1) == torch_logits.argmax(1)).all(), "ONNX and PyTorch disagree"
print(f"ONNX export OK: {os.path.getsize('shotsense.onnx') / 1e6:.1f} MB, max logit difference {max_diff:.2e}")

trained_at = datetime.now(timezone.utc)
metrics = {
    "version": f"resnet18-{trained_at:%Y%m%d-%H%M}",
    "classes": CLASSES,
    "input": {"width": INPUT_W, "height": INPUT_H, "letterbox": True, "mean": MEAN.tolist(), "std": STD.tolist()},
    "dataset": {"name": DATASET, "license": "CC-BY-4.0",
                "n_train": int(len(images["train"])), "n_val": int(len(images["val"])), "n_test": int(len(images["test"])),
                "test_set": "human-labelled frames only, never used for training"},
    "test": {"accuracy": round(test_acc, 4), "macro_f1": round(test_f1, 4),
             "per_class_f1": {c: round(float(per_class[i]), 4) for i, c in enumerate(CLASSES)}},
    "baseline": baseline_metrics,
    "training": {"epochs": EPOCHS, "best_epoch": best_epoch, "val_macro_f1": round(float(best_f1), 4)},
    "trained_at": trained_at.isoformat(timespec="seconds"),
}
with open("metrics.json", "w") as fh:
    json.dump(metrics, fh, indent=2)
print(json.dumps({k: metrics[k] for k in ["version", "test", "baseline"]}, indent=2))
""")

md("""
## 8. Download the model and get your resume numbers

Put `shotsense.onnx`, `metrics.json` and `confusion_matrix.png` into `backend/model/`, then restart the backend.
""")

code("""
print("Resume bullet (numbers from this run):")
print(f"- Fine-tuned an ImageNet-pretrained ResNet-18 in PyTorch to classify 7 cinematic shot scales, reaching "
      f"{test_f1:.0%} macro-F1 ({test_acc:.0%} accuracy) on a held-out, human-labelled test set vs. "
      f"{baseline_metrics['macro_f1']:.0%} macro-F1 for a scikit-learn HOG + logistic-regression baseline; "
      f"exported to ONNX for CPU inference.")

try:
    from google.colab import files
    for name in ["shotsense.onnx", "metrics.json", "confusion_matrix.png"]:
        files.download(name)
except ImportError:
    print("Not running in Colab: the files are in", os.getcwd())
""")


def build(path: Path) -> None:
    nb = {
        "cells": [],
        "metadata": {
            "accelerator": "GPU",
            "colab": {"provenance": [], "gpuType": "T4"},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 0,
    }
    for kind, src in CELLS:
        cell = {"cell_type": kind, "metadata": {}, "source": src.splitlines(keepends=True)}
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        nb["cells"].append(cell)
    path.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {path} ({len(CELLS)} cells)")


if __name__ == "__main__":
    build(Path(__file__).with_name("train_shotsense.ipynb"))
