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


def load_font_sources(path: Path, require_v2_metadata: bool = False) -> list[FontSource]:
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
        if require_v2_metadata:
            if not record.get("family_id", ""):
                raise ValueError(f"字体记录缺少 family_id：{record.get('font_id', '<unknown>')}")
            category = record.get("category", "")
            if not isinstance(category, str) or category not in {"regular", "writing"}:
                raise ValueError(
                    f"字体记录 category 必须是 regular 或 writing：{record.get('font_id', '<unknown>')}={category}"
                )
            if not record.get("variant_role", ""):
                raise ValueError(f"字体记录缺少 variant_role：{record.get('font_id', '<unknown>')}")
            metadata = {}
            for field in ("ecosystem_id", "script_class", "style_role"):
                value = record.get(field, "")
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(
                        f"字体记录 {field} 必须是非空字符串：{record.get('font_id', '<unknown>')}={value}"
                    )
                metadata[field] = value
            if category == "regular":
                if metadata["script_class"] != "regular":
                    raise ValueError(
                        f"常规字体 script_class 必须是 regular：{record.get('font_id', '<unknown>')}"
                    )
                if metadata["style_role"] not in {"text", "display"}:
                    raise ValueError(
                        f"常规字体 style_role 必须是 text 或 display：{record.get('font_id', '<unknown>')}"
                    )
            else:
                if metadata["script_class"] not in {
                    "kaishu",
                    "xingkai",
                    "lishu",
                    "caoshu",
                    "transitional",
                }:
                    raise ValueError(
                        f"书写字体 script_class 不在允许书体中：{record.get('font_id', '<unknown>')}"
                    )
                if metadata["style_role"] != "writing":
                    raise ValueError(
                        f"书写字体 style_role 必须是 writing：{record.get('font_id', '<unknown>')}"
                    )

    sources = [FontSource(**record) for record in records]
    ids = [source.font_id for source in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("font_id 不可重复")
    return sources
