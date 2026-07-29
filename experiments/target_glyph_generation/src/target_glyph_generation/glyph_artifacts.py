"""Detect and mask detached right-border scanning artifacts in glyph images."""

from collections import deque
import csv
from pathlib import Path

from PIL import Image


def find_isolated_right_border_lines(image: Image.Image) -> list[dict[str, int]]:
    """Return detached, thin vertical components attached to the right border."""
    grayscale = image.convert("L")
    width, height = grayscale.size
    components = _connected_components(grayscale, threshold=80)
    if not components:
        return []
    largest = max(components, key=lambda component: component["area"])
    actions = []
    for component in components:
        if component is largest:
            continue
        component_width = component["x1"] - component["x0"] + 1
        component_height = component["y1"] - component["y0"] + 1
        if (
            component["x1"] == width - 1
            and component_height >= round(height * 0.78)
            and component_width <= 4
            and component["area"] >= round(component_height * 0.55)
        ):
            actions.append(
                {
                    "x0": component["x0"],
                    "y0": component["y0"],
                    "x1": component["x1"],
                    "y1": component["y1"],
                    "area": component["area"],
                }
            )
    return sorted(actions, key=lambda action: (action["x0"], action["y0"], action["area"]))


def mask_isolated_right_border_lines(image: Image.Image) -> tuple[Image.Image, list[dict[str, int]]]:
    """Whiten detached right-border line components without modifying the source image."""
    actions = find_isolated_right_border_lines(image)
    if not actions:
        return image.copy(), actions
    result = image.copy()
    background = 255 if result.mode in {"1", "L"} else (255, 255, 255)
    for action in actions:
        for x in range(action["x0"], action["x1"] + 1):
            for y in range(action["y0"], action["y1"] + 1):
                result.putpixel((x, y), background)
    return result, actions


def audit_right_border_lines(
    input_csv: Path, output_csv: Path, path_column: str = "target_path"
) -> dict[str, int]:
    """Write a reproducible action manifest for images with detached right-border lines."""
    input_csv = Path(input_csv)
    output_csv = Path(output_csv)
    required_fields = {"style_id", "source_split", "raw_filename", path_column}
    try:
        with input_csv.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or not required_fields.issubset(reader.fieldnames):
                raise ValueError(f"伪影审计输入缺少必要列：{input_csv}")
            input_rows = list(reader)
    except OSError as error:
        raise ValueError(f"无法读取伪影审计输入：{input_csv}") from error

    actions = []
    for row in input_rows:
        image_path = Path(row[path_column])
        if not image_path.is_file():
            raise ValueError(f"伪影审计原图不存在：{image_path}")
        try:
            with Image.open(image_path) as image:
                components = find_isolated_right_border_lines(image)
        except OSError as error:
            raise ValueError(f"无法读取伪影审计原图：{image_path}") from error
        if components:
            actions.append(
                {
                    "style_id": row["style_id"],
                    "source_split": row["source_split"],
                    "raw_filename": row["raw_filename"],
                    "target_path": str(image_path),
                    "image_preprocess": "mask_isolated_right_border_line",
                    "component_count": len(components),
                }
            )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "style_id",
                "source_split",
                "raw_filename",
                "target_path",
                "image_preprocess",
                "component_count",
            ),
        )
        writer.writeheader()
        writer.writerows(actions)
    return {"scanned_count": len(input_rows), "detected_count": len(actions)}


def _connected_components(image: Image.Image, threshold: int) -> list[dict[str, object]]:
    width, height = image.size
    foreground = [pixel < threshold for pixel in image.getdata()]
    visited = bytearray(width * height)
    components: list[dict[str, object]] = []
    for start_index, is_foreground in enumerate(foreground):
        if not is_foreground or visited[start_index]:
            continue
        queue = deque([start_index])
        visited[start_index] = 1
        pixels = []
        while queue:
            index = queue.popleft()
            pixels.append(index)
            x, y = index % width, index // width
            for offset_y in (-1, 0, 1):
                for offset_x in (-1, 0, 1):
                    neighbor_x, neighbor_y = x + offset_x, y + offset_y
                    if not (0 <= neighbor_x < width and 0 <= neighbor_y < height):
                        continue
                    neighbor_index = neighbor_y * width + neighbor_x
                    if foreground[neighbor_index] and not visited[neighbor_index]:
                        visited[neighbor_index] = 1
                        queue.append(neighbor_index)
        xs = [index % width for index in pixels]
        ys = [index // width for index in pixels]
        components.append(
            {
                "x0": min(xs),
                "y0": min(ys),
                "x1": max(xs),
                "y1": max(ys),
                "area": len(pixels),
            }
        )
    return components
