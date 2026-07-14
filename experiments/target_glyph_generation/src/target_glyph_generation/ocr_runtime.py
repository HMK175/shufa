"""Lazy local PaddleOCR execution for independently discovered image records."""

from collections.abc import Callable, Iterable
from itertools import islice
import os

from target_glyph_generation.external_dataset_discovery import ImageRecord


def run_local_ocr(
    records: Iterable[ImageRecord],
    model_name: str = "PP-OCRv5_server_rec",
    batch_size: int = 8,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[tuple[str, float]]:
    """Recognize records in input order without importing PaddleOCR until needed."""
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")

    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "BOS")
    recognition_model = _load_text_recognition()(model_name=model_name)
    record_list = list(records)
    record_iterator = iter(record_list)
    predictions: list[tuple[str, float]] = []
    while batch := list(islice(record_iterator, batch_size)):
        results = list(
            recognition_model.predict(
                [str(record.image_path) for record in batch], batch_size=batch_size
            )
        )
        if len(results) != len(batch):
            raise ValueError("OCR must return exactly one result per input record")
        predictions.extend((result["rec_text"], float(result["rec_score"])) for result in results)
        if progress_callback is not None:
            progress_callback(len(predictions), len(record_list))
    return predictions


def _load_text_recognition():
    """Import PaddleOCR only during an OCR invocation."""
    from paddleocr import TextRecognition

    return TextRecognition
