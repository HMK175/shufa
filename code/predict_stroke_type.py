"""Predict stroke type for one single-stroke image."""

import argparse
from pathlib import Path

import cv2
import numpy as np

try:
    import torch
    import torch.nn.functional as F
except ImportError:  # pragma: no cover
    torch = None
    F = None

from stroke_classifier import StrokeClassifier


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = SCRIPT_DIR / "models" / "stroke_classifier.pt"


def load_image_tensor(path: Path, image_size: int):
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"image not readable: {path}")
    image = cv2.resize(image, (image_size, image_size), interpolation=cv2.INTER_AREA)
    image = 1.0 - (image.astype(np.float32) / 255.0)
    return torch.from_numpy(image).unsqueeze(0).unsqueeze(0)


def predict(image_path: Path, model_path: Path, topk: int = 3):
    if torch is None:
        print("PyTorch is not installed. Install torch before prediction.")
        return []
    checkpoint = torch.load(str(model_path), map_location="cpu")
    classes = checkpoint["classes"]
    image_size = int(checkpoint.get("image_size", 128))
    model = StrokeClassifier(num_classes=len(classes))
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    tensor = load_image_tensor(image_path, image_size)
    with torch.no_grad():
        probs = F.softmax(model(tensor), dim=1)[0]
    k = min(topk, len(classes))
    values, indices = torch.topk(probs, k=k)
    return [(classes[int(idx)], float(value)) for value, idx in zip(values, indices)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict stroke type")
    parser.add_argument("image")
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--topk", type=int, default=3)
    args = parser.parse_args()

    results = predict(Path(args.image).resolve(), Path(args.model).resolve(), topk=args.topk)
    print(f"image={Path(args.image).resolve()}")
    for rank, (class_name, score) in enumerate(results, start=1):
        print(f"{rank}. {class_name}: {score:.4f}")


if __name__ == "__main__":
    main()
