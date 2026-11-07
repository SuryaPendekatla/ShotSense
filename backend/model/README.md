# Model files

The backend loads two files from this folder:

| File | What it is |
| --- | --- |
| `shotsense.onnx` | The fine-tuned ResNet-18, exported to ONNX |
| `metrics.json` | Class names, test metrics and the baseline comparison |

The repository ships a tiny **placeholder model** so the app runs straight away. Its labels are random, and the UI says so.

To get real predictions, run `training/train_shotsense.ipynb` in Google Colab. It downloads `shotsense.onnx`,
`metrics.json` and `confusion_matrix.png`. Copy all three here, replacing the placeholder files, then restart the backend.

To recreate the placeholder: `python scripts/make_dummy_model.py model/` from the `backend` folder.
