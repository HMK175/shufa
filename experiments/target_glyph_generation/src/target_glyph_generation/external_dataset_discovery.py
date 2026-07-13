"""外部书法图像数据集的只读发现器。"""

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
import re


CHINESE_STYLE_DATASET_ID = "chinese_style"
CALLIGRAPHER_DATASET_ID = "calligrapher20"
CHINESE_STYLE_DISPLAY_NAMES = {"lishu": "隶书", "xingkai": "行楷"}
SOURCE_SPLITS = ("train", "test")


@dataclass(frozen=True)
class ImageRecord:
    """一张外部参考字图像的稳定身份记录。"""

    dataset_id: str
    style_id: str
    style_display_name: str
    source_split: str
    raw_filename: str
    raw_index: str
    image_path: Path

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.dataset_id, self.style_id, self.source_split, self.raw_filename)


def discover_chinese_style_images(root: Path) -> list[ImageRecord]:
    """发现 ChineseStyle 中独立的隶书和行楷单图记录。"""
    root = Path(root)
    if not root.is_dir():
        raise ValueError(f"ChineseStyle 数据根目录不存在：{root}")

    records: list[ImageRecord] = []
    keys: set[tuple[str, str, str, str]] = set()
    for source_split in SOURCE_SPLITS:
        for style_id, style_display_name in CHINESE_STYLE_DISPLAY_NAMES.items():
            style_dir = root / source_split / style_id
            if not style_dir.is_dir():
                continue
            filename_pattern = re.compile(rf"{re.escape(style_id)}_(\d+)\.jpg")
            for image_path in sorted(style_dir.glob("*.jpg"), key=lambda path: path.name):
                if not image_path.is_file():
                    continue
                match = filename_pattern.fullmatch(image_path.name)
                if match is None:
                    raise ValueError(f"ChineseStyle 图像格式错误：{image_path}")
                record = ImageRecord(
                    dataset_id=CHINESE_STYLE_DATASET_ID,
                    style_id=style_id,
                    style_display_name=style_display_name,
                    source_split=source_split,
                    raw_filename=image_path.name,
                    raw_index=match.group(1),
                    image_path=image_path,
                )
                if record.key in keys:
                    raise ValueError(f"ChineseStyle 发现重复图像记录：{record.key}")
                keys.add(record.key)
                records.append(record)

    if not records:
        raise ValueError(f"ChineseStyle 未发现有效图像：{root}")
    return _sort_records(records)


def discover_calligrapher_images(
    data_root: Path, sources: Mapping[str, Mapping[str, object]]
) -> list[ImageRecord]:
    """发现按书法家目录组织的单图记录，不对跨书法家编号进行配对。"""
    data_root = Path(data_root)
    if not data_root.is_dir():
        raise ValueError(f"书法家数据根目录不存在：{data_root}")

    display_names = _source_display_names(sources)
    records: list[ImageRecord] = []
    keys: set[tuple[str, str, str, str]] = set()
    filename_pattern = re.compile(r"(\d+)\.jpg")

    for source_split in SOURCE_SPLITS:
        split_dir = data_root / source_split
        if not split_dir.is_dir():
            continue

        _reject_split_root_jpg_images(split_dir)
        for writer_id in sorted(display_names):
            writer_dir = split_dir / writer_id
            if not writer_dir.is_dir():
                continue
            for image_path in sorted(writer_dir.rglob("*"), key=lambda path: str(path)):
                if not image_path.is_file():
                    continue
                if image_path.parent != writer_dir:
                    raise ValueError(f"书法家图像格式错误：{image_path}")
                match = filename_pattern.fullmatch(image_path.name)
                if match is None:
                    raise ValueError(f"书法家图像格式错误：{image_path}")
                record = ImageRecord(
                    dataset_id=CALLIGRAPHER_DATASET_ID,
                    style_id=writer_id,
                    style_display_name=display_names[writer_id],
                    source_split=source_split,
                    raw_filename=image_path.name,
                    raw_index=match.group(1),
                    image_path=image_path,
                )
                if record.key in keys:
                    raise ValueError(f"书法家数据发现重复图像记录：{record.key}")
                keys.add(record.key)
                records.append(record)

    if not records:
        raise ValueError(f"书法家数据没有发现已选图像：{data_root}")
    return _sort_records(records)


def validate_chinese_style_audit_inventory(root: Path, records: Iterable[ImageRecord]) -> None:
    """Reject incomplete ChineseStyle inventories before OCR audit inference."""
    root = Path(root)
    if not root.is_dir():
        raise ValueError(f"ChineseStyle dataset root directory does not exist: {root}")

    missing_directories = [
        f"{source_split}/{style_id}"
        for source_split in SOURCE_SPLITS
        for style_id in CHINESE_STYLE_DISPLAY_NAMES
        if not (root / source_split / style_id).is_dir()
    ]
    if missing_directories:
        raise ValueError(
            "ChineseStyle dataset inventory incomplete: missing directories: "
            + ", ".join(missing_directories)
        )

    split_style_counts = Counter((record.source_split, record.style_id) for record in records)
    missing_split_styles = [
        f"{source_split}/{style_id}: discovered {split_style_counts[(source_split, style_id)]}"
        for source_split in SOURCE_SPLITS
        for style_id in CHINESE_STYLE_DISPLAY_NAMES
        if split_style_counts[(source_split, style_id)] == 0
    ]
    if missing_split_styles:
        raise ValueError(
            "ChineseStyle dataset inventory incomplete: missing records for required split/styles: "
            + ", ".join(missing_split_styles)
        )


def validate_calligrapher_audit_inventory(
    data_root: Path,
    records: Iterable[ImageRecord],
    sources: Mapping[str, Mapping[str, object]],
) -> None:
    """Reject incomplete configured calligrapher inventories before OCR audit inference."""
    data_root = Path(data_root)
    if not data_root.is_dir():
        raise ValueError(f"Calligrapher dataset root directory does not exist: {data_root}")

    expected_totals = _source_expected_totals(sources)
    missing_directories = [
        f"{source_split}/{writer_id}"
        for source_split in SOURCE_SPLITS
        for writer_id in sorted(expected_totals)
        if not (data_root / source_split / writer_id).is_dir()
    ]
    if missing_directories:
        raise ValueError(
            "Calligrapher dataset inventory incomplete: missing directories: "
            + ", ".join(missing_directories)
        )

    record_counts: Counter[str] = Counter()
    split_writer_counts: Counter[tuple[str, str]] = Counter()
    for record in records:
        record_counts[record.style_id] += 1
        split_writer_counts[(record.source_split, record.style_id)] += 1
    missing_split_writers = [
        f"{source_split}/{writer_id}: discovered {split_writer_counts[(source_split, writer_id)]}"
        for source_split in SOURCE_SPLITS
        for writer_id in sorted(expected_totals)
        if split_writer_counts[(source_split, writer_id)] == 0
    ]
    if missing_split_writers:
        raise ValueError(
            "Calligrapher dataset inventory incomplete: missing records for required split/writers: "
            + ", ".join(missing_split_writers)
        )

    mismatched_totals = [
        f"{writer_id}: expected {expected_total}, discovered {record_counts[writer_id]}"
        for writer_id, expected_total in sorted(expected_totals.items())
        if record_counts[writer_id] != expected_total
    ]
    if mismatched_totals:
        raise ValueError(
            "Calligrapher dataset inventory incomplete: writer image totals differ: "
            + "; ".join(mismatched_totals)
        )


def _source_display_names(sources: Mapping[str, Mapping[str, object]]) -> dict[str, str]:
    display_names: dict[str, str] = {}
    for writer_id, source in sources.items():
        if not isinstance(writer_id, str) or not writer_id:
            raise ValueError(f"书法家目录 ID 必须是非空字符串：{writer_id}")
        display_name = source.get("display_name") if isinstance(source, Mapping) else None
        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError(f"书法家来源缺少 display_name：{writer_id}")
        display_names[writer_id] = display_name.strip()
    return display_names


def _source_expected_totals(sources: Mapping[str, Mapping[str, object]]) -> dict[str, int]:
    expected_totals: dict[str, int] = {}
    for writer_id, source in sources.items():
        expected_total = source.get("expected_total") if isinstance(source, Mapping) else None
        if (
            isinstance(expected_total, bool)
            or not isinstance(expected_total, int)
            or expected_total <= 0
        ):
            raise ValueError(
                f"Calligrapher source expected_total must be a positive integer: {writer_id}"
            )
        expected_totals[writer_id] = expected_total
    return expected_totals


def _reject_split_root_jpg_images(split_dir: Path) -> None:
    for entry in sorted(split_dir.iterdir(), key=lambda path: path.name):
        if entry.is_file() and entry.suffix.lower() == ".jpg":
            raise ValueError(f"书法家图像格式错误：{entry}")


def _sort_records(records: list[ImageRecord]) -> list[ImageRecord]:
    split_order = {source_split: index for index, source_split in enumerate(SOURCE_SPLITS)}
    return sorted(
        records,
        key=lambda record: (
            split_order[record.source_split],
            record.style_id,
            int(record.raw_index),
            record.raw_filename,
        ),
    )
