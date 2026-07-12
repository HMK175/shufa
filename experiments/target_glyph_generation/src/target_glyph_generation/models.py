"""数据集构建过程中的结构化记录。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FontSource:
    font_id: str
    display_name: str
    version: str
    source_url: str
    license_id: str
    license_url: str
    local_path: str
