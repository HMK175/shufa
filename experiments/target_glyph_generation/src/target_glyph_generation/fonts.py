"""受控字体来源清单的读取与基础审计。"""

from pathlib import Path

import yaml

from .licenses import is_accepted_license
from .models import FontSource


REQUIRED_FONT_FIELDS = {
    "font_id",
    "display_name",
    "version",
    "source_url",
    "license_id",
    "license_url",
    "local_path",
}


def load_font_sources(path: Path) -> list[FontSource]:
    """读取字体清单，并拒绝缺字段、重复 ID 与非白名单许可。"""
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    records = payload.get("fonts", [])
    if not isinstance(records, list):
        raise ValueError("fonts 必须是列表")

    for record in records:
        if not isinstance(record, dict):
            raise ValueError("字体记录必须是对象")
        license_id = record.get("license_id", "")
        if not is_accepted_license(license_id):
            raise ValueError(f"未接受的许可证：{record.get('font_id', '<unknown>')}={license_id}")
        missing = REQUIRED_FONT_FIELDS - set(record)
        if missing:
            raise ValueError(f"字体记录缺少字段：{', '.join(sorted(missing))}")

    sources = [FontSource(**record) for record in records]
    ids = [source.font_id for source in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("font_id 不可重复")
    return sources
