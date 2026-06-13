"""Planner interfaces for the isolated LLM-style trajectory experiment.

The planner turns natural-language tasks into structured plans. It never emits
trajectory points or CSV content; deterministic trajectory tools do that later.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from knowledge import MakeMeAHanziKnowledge
from style_modifiers import (
    DEFAULT_STYLE_MODIFIERS,
    MODIFIER_CHOICES,
    apply_style_modifiers_to_style_params,
    merge_text_and_model_modifiers,
    normalize_style_modifiers,
    parse_style_modifiers_from_text,
)


EXP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PLANNER_PROMPT = EXP_DIR / "configs" / "planner_prompt.md"
DEFAULT_API_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEFAULT_API_MODEL = "deepseek-v4-pro"
STYLE_ALIASES = {
    "楷书": "kaishu",
    "楷体": "kaishu",
    "正楷": "kaishu",
    "kaishu": "kaishu",
    "行楷": "xingkai",
    "行书": "xingkai",
    "xingkai": "xingkai",
    "隶书": "lishu",
    "隶体": "lishu",
    "隸書": "lishu",
    "lishu": "lishu",
}
STYLE_DISPLAY = {
    "kaishu": "楷书",
    "xingkai": "行楷",
    "lishu": "隶书",
}
DANGEROUS_DIRECT_OUTPUT_KEYS = {"trajectory", "trajectory_csv", "csv", "points", "point_sequence", "trajectory_points"}
REQUEST_STATUSES = {"ok", "unsupported", "ambiguous", "invalid"}
UNSUPPORTED_STYLE_ALIASES = {
    "草书": "caoshu",
    "草体": "caoshu",
    "行草": "xingcao",
    "火星文": "huoxingwen",
    "caoshu": "caoshu",
    "xingcao": "xingcao",
    "huoxingwen": "huoxingwen",
}
AMBIGUOUS_STYLE_HINTS = {"好看", "漂亮", "美观", "自然", "随意"}
REQUEST_CHAR_NOISE_TOKENS = [
    "帮我",
    "请",
    "写一个",
    "写一個",
    "写个",
    "写",
    "书写",
    "生成",
    "风格",
    "的",
    "字",
    "一个",
    "一個",
    "一",
    "整体",
    "稍微",
    "一点",
    "一些",
    "更",
    "不要",
    "不",
    "输出",
    "只给",
    "计划",
    "轨迹",
    "坐标",
    "笔画",
    "之间",
    "之間",
    "起来",
    "连起来",
    "連起來",
    "连笔",
    "连接",
    "连贯",
    "宽扁",
    "圆滑",
    "平滑",
    "保守",
    "规整",
    "連貫",
    "连贯",
    "粗一点",
    "粗一些",
    "更粗",
    "细一点",
    "细一些",
    "更细",
    "横向",
    "舒展",
    "宽",
    "扁",
    "CSV",
    "csv",
]


class PlannerAPIError(RuntimeError):
    """Friendly API planner error that never includes secrets."""


def _coerce_profile_value(value: Any) -> float | bool:
    if isinstance(value, bool):
        return value
    return float(value)


def load_style_profiles(path: Path | str) -> dict[str, dict[str, float | bool]]:
    with Path(path).open(encoding="utf-8") as f:
        data = json.load(f)
    return {
        name: {key: _coerce_profile_value(value) for key, value in params.items()}
        for name, params in data.items()
        if isinstance(params, dict) and not name.startswith("_")
    }


def _extract_style(task_text: str, profiles: dict[str, dict[str, float | bool]]) -> str:
    lowered = task_text.lower()
    for key, value in STYLE_ALIASES.items():
        if key.lower() in lowered and value in profiles:
            return value
    return "kaishu"


def _find_requested_style(task_text: str) -> tuple[str, str, bool]:
    lowered = task_text.lower()
    for key, value in sorted(STYLE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if key.lower() in lowered:
            return key, value, True
    for key, value in sorted(UNSUPPORTED_STYLE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if key.lower() in lowered:
            return key, value, False
    return "", "", False


def _has_ambiguous_style_hint(task_text: str) -> bool:
    return any(token in task_text for token in AMBIGUOUS_STYLE_HINTS)


def _extract_requested_chars_raw(task_text: str) -> str:
    text = task_text
    noise_tokens = list(REQUEST_CHAR_NOISE_TOKENS)
    noise_tokens.extend(STYLE_ALIASES.keys())
    noise_tokens.extend(UNSUPPORTED_STYLE_ALIASES.keys())
    noise_tokens.extend(AMBIGUOUS_STYLE_HINTS)
    for token in sorted(noise_tokens, key=len, reverse=True):
        text = text.replace(token, "")
    text = re.sub(r"[A-Za-z0-9_./\\:;，,。！？!?\s\"'“”‘’（）()\[\]{}<>《》、\-+=]+", "", text)
    return "".join(re.findall(r"[\u4e00-\u9fff]", text))


def _analyze_request_boundary(
    task_text: str,
    style_profiles: dict[str, dict[str, float | bool]],
) -> dict[str, str]:
    requested_style_raw, requested_style_code, style_supported = _find_requested_style(task_text)
    requested_chars_raw = _extract_requested_chars_raw(task_text)
    mapped_style = requested_style_code if style_supported and requested_style_code in style_profiles else "kaishu"
    status = "ok"
    rejection_reason = ""

    if not requested_chars_raw:
        requested_chars_raw = _extract_char(task_text)
    if not requested_chars_raw:
        status = "invalid"
        rejection_reason = "request must include one single target character"
    elif len(requested_chars_raw) != 1:
        status = "invalid"
        rejection_reason = f"request must target one single target character, got: {requested_chars_raw}"
    elif requested_style_raw and not style_supported:
        status = "unsupported"
        rejection_reason = f"unsupported style requested: {requested_style_raw}"
        mapped_style = requested_style_code

    return {
        "request_status": status,
        "requested_style_raw": requested_style_raw,
        "requested_chars_raw": requested_chars_raw,
        "mapped_style": mapped_style,
        "rejection_reason": rejection_reason,
    }


def _attach_request_boundary(plan: dict[str, Any], boundary: dict[str, str]) -> dict[str, Any]:
    plan["request_status"] = boundary["request_status"]
    plan["requested_style_raw"] = boundary["requested_style_raw"]
    plan["requested_chars_raw"] = boundary["requested_chars_raw"]
    plan["mapped_style"] = str(plan.get("style") or boundary["mapped_style"])
    plan["rejection_reason"] = boundary["rejection_reason"]
    return plan


def _strip_known_words(task_text: str) -> str:
    text = task_text
    for token in [
        "写一个",
        "写",
        "书写",
        "生成",
        "风格",
        "的",
        "不要连笔",
        "不连笔",
        "连笔",
        "整体",
        "宽扁",
        "扁一些",
        "宽一些",
        "横向舒展",
        "一些",
        "一点",
    ]:
        text = text.replace(token, "")
    for token in STYLE_ALIASES:
        text = text.replace(token, "")
    return text


def _extract_char(task_text: str) -> str:
    for pattern in [
        r"风格的([\u4e00-\u9fff])",
        r"寫一個.*?的([\u4e00-\u9fff])",
        r"写一个.*?的([\u4e00-\u9fff])",
    ]:
        match = re.search(pattern, task_text)
        if match:
            return match.group(1)

    stripped = _strip_known_words(task_text)
    chars = re.findall(r"[\u4e00-\u9fff]", stripped)
    if chars:
        return chars[0]

    chars = re.findall(r"[\u4e00-\u9fff]", task_text)
    if chars:
        return chars[-1]
    return ""


def _wants_no_connection(task_text: str) -> bool:
    return any(token in task_text for token in ["不要连笔", "不连笔", "不要连接", "不连接"])


def _wants_connection(task_text: str) -> bool:
    return any(token in task_text for token in ["更连贯", "连笔", "连起来", "连接"]) and not _wants_no_connection(task_text)


def _wants_flat_shape(task_text: str) -> bool:
    return any(token in task_text for token in ["宽扁", "扁一些", "宽一些", "横向舒展", "更扁", "更宽"])


def _base_constraints(task_text: str, style: str, profile: dict[str, float | bool]) -> dict[str, bool]:
    profile_allows = bool(profile.get("allow_interstroke_connections", False))
    if _wants_no_connection(task_text):
        allow_connections = False
    elif _wants_connection(task_text):
        allow_connections = profile_allows
    else:
        allow_connections = profile_allows
    return {
        "allow_interstroke_connections": allow_connections,
        "emphasize_flat_shape": _wants_flat_shape(task_text),
    }


def _apply_constraints_to_style_params(
    style_params: dict[str, float | bool],
    constraints: dict[str, bool],
) -> dict[str, float | bool]:
    out = dict(style_params)
    if not constraints.get("allow_interstroke_connections", False):
        out["allow_interstroke_connections"] = False
        out["connection_strength"] = 0.0
    else:
        out["allow_interstroke_connections"] = True

    if constraints.get("emphasize_flat_shape", False):
        h_scale = float(out.get("horizontal_scale", 1.0))
        v_scale = float(out.get("vertical_scale", 1.0))
        out["horizontal_scale"] = round(min(1.35, h_scale * 1.08), 4)
        out["vertical_scale"] = round(max(0.72, v_scale * 0.95), 4)
    return out


def _empty_plan(task: str, mode: str, source: str, warning: str | None = None) -> dict[str, Any]:
    warnings = [warning] if warning else []
    return {
        "task": task,
        "char": "",
        "style": "",
        "style_params": {},
        "constraints": {
            "allow_interstroke_connections": False,
            "emphasize_flat_shape": False,
        },
        "style_modifiers": dict(DEFAULT_STYLE_MODIFIERS),
        "stroke_plan": {
            "source": "makemeahanzi",
            "order": "source_order",
            "generator": "deterministic_style_profile",
        },
        "planner_mode": mode,
        "source": source,
        "warnings": warnings,
        "notes": "",
        "raw_response": None,
        "request_status": "invalid",
        "requested_style_raw": "",
        "requested_chars_raw": "",
        "mapped_style": "",
        "rejection_reason": warning or "planner did not return a usable request plan",
    }


def _build_mock_plan(task_text: str, style_profiles: dict[str, dict[str, float | bool]]) -> dict[str, Any]:
    boundary = _analyze_request_boundary(task_text, style_profiles)
    style = boundary["mapped_style"]
    if style not in style_profiles and boundary["request_status"] != "unsupported":
        style = _extract_style(task_text, style_profiles)
    char = boundary["requested_chars_raw"] or _extract_char(task_text)
    base_params = dict(style_profiles.get(style, {}))
    style_modifiers = parse_style_modifiers_from_text(task_text)
    style_params = apply_style_modifiers_to_style_params(base_params, style_modifiers)
    constraints = {
        "allow_interstroke_connections": bool(style_params.get("allow_interstroke_connections", False)),
        "emphasize_flat_shape": style_modifiers["shape_emphasis"] in {"flatter", "wider"},
    }
    warnings: list[str] = []
    if not boundary["requested_style_raw"] and _has_ambiguous_style_hint(task_text):
        warnings.append("no supported style requested; defaulted to kaishu")
    notes = (
        f"Rule-based mock planner selected char={char or '<missing>'}, "
        f"style={style}, allow_interstroke_connections={constraints['allow_interstroke_connections']}."
    )
    if constraints["emphasize_flat_shape"]:
        notes += " Applied a small horizontal emphasis to style_params."
    plan = {
        "task": task_text,
        "char": char,
        "style": style,
        "style_params": style_params,
        "constraints": constraints,
        "style_modifiers": style_modifiers,
        "stroke_plan": {
            "source": "makemeahanzi",
            "order": "source_order",
            "generator": "deterministic_style_profile",
            "tools": ["knowledge.get_glyph", "trajectory_tools.build_styled_trajectory"],
        },
        "planner_mode": "mock",
        "source": "mock_rule_based",
        "warnings": warnings,
        "notes": notes,
        "raw_response": None,
    }
    return _attach_request_boundary(plan, boundary)


def _normalize_style_name(raw_style: Any) -> str:
    style_text = str(raw_style or "").strip()
    if style_text in STYLE_ALIASES:
        return STYLE_ALIASES[style_text]
    lowered = style_text.lower()
    return STYLE_ALIASES.get(lowered, lowered)


def _bool_or_default(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return default


def _normalize_constraints(
    task_text: str,
    style: str,
    profile: dict[str, float | bool],
    raw_constraints: Any,
) -> dict[str, bool]:
    constraints = _base_constraints(task_text, style, profile)
    if isinstance(raw_constraints, dict):
        if "allow_interstroke_connections" in raw_constraints:
            constraints["allow_interstroke_connections"] = _bool_or_default(
                raw_constraints.get("allow_interstroke_connections"),
                constraints["allow_interstroke_connections"],
            )
        if "emphasize_flat_shape" in raw_constraints:
            constraints["emphasize_flat_shape"] = _bool_or_default(
                raw_constraints.get("emphasize_flat_shape"),
                constraints["emphasize_flat_shape"],
            )
    return constraints


def _normalize_api_plan(
    task_text: str,
    raw_content: str,
    raw_plan: dict[str, Any],
    style_profiles: dict[str, dict[str, float | bool]],
) -> dict[str, Any]:
    boundary = _analyze_request_boundary(task_text, style_profiles)
    warnings = [str(item) for item in raw_plan.get("warnings", []) if item] if isinstance(raw_plan.get("warnings"), list) else []
    for key in sorted(DANGEROUS_DIRECT_OUTPUT_KEYS):
        if key in raw_plan:
            warnings.append(f"removed forbidden planner field from api response: {key}")

    model_char = str(raw_plan.get("char") or _extract_char(task_text))
    char = boundary["requested_chars_raw"] if boundary["request_status"] == "ok" and boundary["requested_chars_raw"] else model_char
    model_style = _normalize_style_name(raw_plan.get("style") or _extract_style(task_text, style_profiles))
    if boundary["request_status"] == "ok" and boundary["requested_style_raw"]:
        style = boundary["mapped_style"]
        if model_style != style:
            warnings.append(f"api style={model_style} overridden by explicit requested style={style}")
    elif boundary["request_status"] == "ok":
        style = "kaishu"
        if model_style != style:
            warnings.append(f"no supported style requested; defaulted to kaishu instead of api style={model_style}")
    else:
        style = model_style
        boundary["mapped_style"] = model_style
    profile = dict(style_profiles.get(style, {}))
    style_modifiers = merge_text_and_model_modifiers(task_text, raw_plan.get("style_modifiers"))
    constraints = _normalize_constraints(task_text, style, profile, raw_plan.get("constraints"))
    if boundary["request_status"] == "ok" and not boundary["requested_style_raw"]:
        style_modifiers["connection_preference"] = "none"
    style_params = apply_style_modifiers_to_style_params(profile, style_modifiers) if profile else {}
    constraints["allow_interstroke_connections"] = bool(style_params.get("allow_interstroke_connections", False))
    constraints["emphasize_flat_shape"] = style_modifiers["shape_emphasis"] in {"flatter", "wider"}

    raw_stroke_plan = raw_plan.get("stroke_plan") if isinstance(raw_plan.get("stroke_plan"), dict) else {}
    stroke_plan = {
        "source": str(raw_stroke_plan.get("source", "makemeahanzi")),
        "order": str(raw_stroke_plan.get("order", "source_order")),
        "generator": str(raw_stroke_plan.get("generator", "deterministic_style_profile")),
        "tools": raw_stroke_plan.get(
            "tools",
            ["knowledge.get_glyph", "trajectory_tools.build_styled_trajectory"],
        ),
    }
    model = _api_model()
    plan = {
        "task": task_text,
        "char": char,
        "style": style,
        "style_params": style_params,
        "constraints": constraints,
        "style_modifiers": style_modifiers,
        "stroke_plan": stroke_plan,
        "planner_mode": "api",
        "source": _source_from_model(model),
        "warnings": warnings,
        "notes": str(raw_plan.get("notes", "")),
        "raw_response": raw_content,
    }
    return _attach_request_boundary(plan, boundary)


def _api_configured() -> bool:
    return bool(_api_key() and _api_endpoint() and _api_model())


def _api_key() -> str:
    return os.environ.get("LLM_STYLE_PLANNER_API_KEY", "").strip()


def _api_endpoint() -> str:
    return os.environ.get("LLM_STYLE_PLANNER_ENDPOINT", "").strip() or DEFAULT_API_ENDPOINT


def _api_model() -> str:
    return os.environ.get("LLM_STYLE_PLANNER_MODEL", "").strip() or DEFAULT_API_MODEL


def _api_missing_message() -> str:
    missing = []
    if not _api_key():
        missing.append("LLM_STYLE_PLANNER_API_KEY")
    if not _api_endpoint():
        missing.append("LLM_STYLE_PLANNER_ENDPOINT")
    if not _api_model():
        missing.append("LLM_STYLE_PLANNER_MODEL")
    if missing:
        return "api planner not configured; set " + ", ".join(missing)
    return ""


def _local_configured() -> bool:
    return bool(os.environ.get("LLM_STYLE_PLANNER_LOCAL_CMD"))


def _configured_placeholder_plan(task: str, mode: str) -> dict[str, Any]:
    warning = f"{mode} planner interface is configured but not implemented in this probe; no model call was made."
    return _empty_plan(task, mode=mode, source=f"{mode}_placeholder", warning=warning)


def _source_from_model(model: str) -> str:
    return model.replace("-", "_").replace(".", "_")


def _read_planner_prompt(path: Path = DEFAULT_PLANNER_PROMPT) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return (
            "Return one JSON object with char, style, constraints, stroke_plan, and notes. "
            "Do not output trajectory points, CSV rows, or robot commands."
        )


def _style_profile_summary(style_profiles: dict[str, dict[str, float | bool]]) -> dict[str, dict[str, Any]]:
    return {
        style: {
            "allow_interstroke_connections": bool(params.get("allow_interstroke_connections", False)),
            "connection_strength": float(params.get("connection_strength", 0.0)),
            "horizontal_scale": float(params.get("horizontal_scale", 1.0)),
            "vertical_scale": float(params.get("vertical_scale", 1.0)),
        }
        for style, params in style_profiles.items()
    }


def _chat_completion_content(response_payload: dict[str, Any]) -> str:
    try:
        return str(response_payload["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise PlannerAPIError("api planner response missing choices[0].message.content") from exc


def _extract_json_object(text: str) -> dict[str, Any]:
    content = text.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s*```$", "", content)
    if not content.startswith("{"):
        first = content.find("{")
        last = content.rfind("}")
        if first >= 0 and last > first:
            content = content[first : last + 1]
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise PlannerAPIError("api planner returned non-JSON content") from exc
    if not isinstance(parsed, dict):
        raise PlannerAPIError("api planner JSON must be an object")
    return parsed


def _call_deepseek_planner(
    task: str,
    style_profiles: dict[str, dict[str, float | bool]],
    timeout: int = 30,
) -> tuple[str, dict[str, Any]]:
    key = _api_key()
    endpoint = _api_endpoint()
    model = _api_model()
    if not key or not endpoint or not model:
        raise PlannerAPIError(_api_missing_message())

    system_prompt = _read_planner_prompt()
    user_prompt = (
        "User task:\n"
        f"{task}\n\n"
        "Supported style profiles:\n"
        f"{json.dumps(_style_profile_summary(style_profiles), ensure_ascii=False)}\n\n"
        "Return only one JSON object. Do not include Markdown or explanatory text."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 1000,
        "response_format": {"type": "json_object"},
    }
    request = Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise PlannerAPIError(f"api planner request failed: HTTP {exc.code}") from exc
    except URLError as exc:
        raise PlannerAPIError(f"api planner request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise PlannerAPIError("api planner request failed: timeout") from exc
    except OSError as exc:
        raise PlannerAPIError(f"api planner request failed: {exc}") from exc

    try:
        response_payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise PlannerAPIError("api planner response body was not JSON") from exc
    content = _chat_completion_content(response_payload)
    return content, _extract_json_object(content)


def validate_plan(
    plan: dict[str, Any],
    style_profiles: dict[str, dict[str, float | bool]],
    graphics_path: Path | str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    request_status = str(plan.get("request_status", "ok"))
    rejection_reason = str(plan.get("rejection_reason", ""))
    requested_chars_raw = str(plan.get("requested_chars_raw", ""))
    if request_status not in REQUEST_STATUSES:
        errors.append(f"unknown request_status: {request_status}")
    elif request_status == "unsupported":
        errors.append(rejection_reason or "unsupported style requested")
    elif request_status == "invalid":
        errors.append(rejection_reason or "invalid user request")
    elif request_status == "ambiguous":
        warnings.append(rejection_reason or "ambiguous request; default planner policy was applied")

    if requested_chars_raw and len(requested_chars_raw) != 1:
        errors.append(f"request must target one single target character, got: {requested_chars_raw}")

    char = str(plan.get("char", ""))
    style = str(plan.get("style", ""))
    if not char:
        errors.append("char is required")
    elif len(char) != 1:
        errors.append(f"char length should be 1 Chinese character, got {len(char)}")

    if not style:
        errors.append("style is required")
    elif style not in style_profiles:
        errors.append(f"style is not available in style profiles: {style}")

    if char and graphics_path is not None:
        try:
            MakeMeAHanziKnowledge(graphics_path).get_glyph(char)
        except Exception as exc:  # noqa: BLE001 - validation should return friendly errors
            errors.append(f"makemeahanzi glyph lookup failed for char={char}: {exc}")

    if style in style_profiles:
        profile = style_profiles[style]
        profile_allows = bool(profile.get("allow_interstroke_connections", False))
        constraints = plan.get("constraints", {})
        style_params = plan.get("style_params", {})
        requested_allow = bool(constraints.get("allow_interstroke_connections", False))
        params_allow = bool(style_params.get("allow_interstroke_connections", False))
        if requested_allow and not profile_allows:
            errors.append(f"allow_interstroke_connections conflicts with style profile for style={style}")
        if params_allow and not profile_allows:
            errors.append(f"style_params allow connections but style profile forbids them for style={style}")

    modifiers = plan.get("style_modifiers", DEFAULT_STYLE_MODIFIERS)
    if not isinstance(modifiers, dict):
        errors.append("style_modifiers must be an object")
    else:
        normalized = normalize_style_modifiers(modifiers)
        for key, choices in MODIFIER_CHOICES.items():
            raw_value = str(modifiers.get(key, normalized[key]))
            if raw_value not in choices:
                errors.append(f"unsupported style modifier {key}={modifiers.get(key)}")

    for key in DANGEROUS_DIRECT_OUTPUT_KEYS:
        if key in plan:
            errors.append(f"planner must not include direct trajectory/CSV/point output field: {key}")

    if plan.get("raw_response") and not isinstance(plan.get("raw_response"), (str, dict)):
        warnings.append("raw_response should be string, object, or null")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def plan_task(
    task: str,
    mode: str = "mock",
    style_profiles: dict[str, dict[str, float | bool]] | None = None,
    graphics_path: Path | str | None = None,
    fallback_to_mock: bool = False,
) -> dict[str, Any]:
    if style_profiles is None:
        raise ValueError("style_profiles are required for plan_task")
    mode = mode.lower().strip()
    if mode not in {"mock", "api", "local"}:
        plan = _empty_plan(task, mode=mode, source="invalid_mode", warning=f"unknown planner mode: {mode}")
        validation = validate_plan(plan, style_profiles, graphics_path)
        validation["errors"].insert(0, f"unknown planner mode: {mode}")
        validation["ok"] = False
        plan["validation"] = validation
        return plan

    fallback_warning = ""
    if mode == "mock":
        plan = _build_mock_plan(task, style_profiles)
    elif mode == "api":
        if not _api_configured():
            missing = _api_missing_message()
            fallback_warning = (
                f"{missing}; use --fallback-to-mock for the rule-based planner"
                if missing
                else "api planner not configured; use --fallback-to-mock"
            )
            if fallback_to_mock:
                plan = _build_mock_plan(task, style_profiles)
                plan["warnings"].append(fallback_warning)
            else:
                plan = _empty_plan(task, mode="api", source="api_unconfigured", warning=fallback_warning)
        else:
            try:
                raw_content, raw_plan = _call_deepseek_planner(task, style_profiles)
                plan = _normalize_api_plan(task, raw_content, raw_plan, style_profiles)
            except PlannerAPIError as exc:
                fallback_warning = str(exc)
                if fallback_to_mock:
                    plan = _build_mock_plan(task, style_profiles)
                    plan["warnings"].append(fallback_warning)
                else:
                    plan = _empty_plan(task, mode="api", source=_source_from_model(_api_model()), warning=fallback_warning)
    else:
        if not _local_configured():
            fallback_warning = (
                "local planner not configured; use --fallback-to-mock or set "
                "LLM_STYLE_PLANNER_LOCAL_CMD"
            )
            if fallback_to_mock:
                plan = _build_mock_plan(task, style_profiles)
                plan["warnings"].append(fallback_warning)
            else:
                plan = _empty_plan(task, mode="local", source="local_unconfigured", warning=fallback_warning)
        else:
            plan = _configured_placeholder_plan(task, "local")

    validation = validate_plan(plan, style_profiles, graphics_path)
    api_error_plan = plan.get("planner_mode") == "api" and bool(plan.get("warnings")) and not plan.get("char")
    if plan["source"].endswith("_unconfigured") or plan["source"].endswith("_placeholder") or api_error_plan:
        validation = {
            "ok": False,
            "errors": [plan["warnings"][0] if plan["warnings"] else f"{mode} planner unavailable"],
            "warnings": [],
        }
    plan["validation"] = validation
    return plan


class RuleBasedPlanner:
    """Compatibility wrapper around the mock planner."""

    def __init__(self, style_profiles: dict[str, dict[str, float | bool]], graphics_path: Path | str | None = None):
        self.style_profiles = style_profiles
        self.graphics_path = graphics_path

    def plan(self, task_text: str) -> dict[str, Any]:
        return plan_task(
            task_text,
            mode="mock",
            style_profiles=self.style_profiles,
            graphics_path=self.graphics_path,
        )
