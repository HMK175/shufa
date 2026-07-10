"""Classify extracted stroke candidates with the v2 stroke classifier."""

import argparse
import csv
from pathlib import Path

from predict_stroke_type import predict


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = SCRIPT_DIR / "models" / "stroke_classifier_v2.pt"


def classify_candidates(candidates_csv: Path, model_path: Path = DEFAULT_MODEL) -> Path:
    base_dir = candidates_csv.parent
    rows = []
    with candidates_csv.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            image_path = base_dir / row["candidate_image"]
            preds = predict(image_path, model_path, topk=3)
            while len(preds) < 3:
                preds.append(("", 0.0))
            top1, top2, top3 = preds[:3]
            reliable = True
            note = "ok"
            if top1[0] == "ti":
                reliable = False
                note = "ti_unreliable"
            elif top1[1] < 0.60:
                reliable = False
                note = "low_confidence"
            out = {
                "candidate_id": row["candidate_id"],
                "top1_class": top1[0],
                "top1_conf": f"{top1[1]:.4f}",
                "top2_class": top2[0],
                "top2_conf": f"{top2[1]:.4f}",
                "top3_class": top3[0],
                "top3_conf": f"{top3[1]:.4f}",
                "reliable": "true" if reliable else "false",
                "note": note,
            }
            rows.append(out)

    out_csv = base_dir / "candidate_predictions.csv"
    with out_csv.open("w", newline="", encoding="utf-8-sig") as f:
        fields = [
            "candidate_id",
            "top1_class",
            "top1_conf",
            "top2_class",
            "top2_conf",
            "top3_class",
            "top3_conf",
            "reliable",
            "note",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {out_csv} predictions={len(rows)}")
    return out_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify candidate stroke images")
    parser.add_argument("candidates_csv")
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    args = parser.parse_args()
    classify_candidates(Path(args.candidates_csv).resolve(), Path(args.model).resolve())


if __name__ == "__main__":
    main()
