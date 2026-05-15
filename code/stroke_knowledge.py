"""楷体笔画知识库：基础笔画 + 复合笔画 + 可复用部件 + 整字拆解。

三级结构（按书法构型层次）：
  1. PrimitiveStroke — 最小运动单元，8大类 50+ 子类
  2. CompoundStroke  — 多笔画连续组合，5大起笔类 40+ 种
  3. Component        — 偏旁/部首/结构单元，6类 80+ 个

部件可复用（「口」在「中」「福」里同一套规则），整字由部件序列组成。
换字体时只需修改部件内部的笔画定义和方向约束。
"""

import numpy as np
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════════════════
# 数据类定义
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PrimitiveStroke:
    """基础笔画 — 最小运动单元，不可再分。"""
    key: str                      # 拼音键名
    name: str                     # 中文名
    pinyin: str                   # 拼音（带声调）
    category: str                 # 大类: heng/shu/pie/na/dian/ti/gou/zhe
    subcategory: str              # 子类描述
    geometry_type: str            # 几何类型: line/curve/dot/hook/bend
    direction: str                # 书写方向: H/V/DL/DR/UR/UL/any
    typical_angle: Tuple[float, float]  # 角度范围 (度, 0=竖,90=横)
    has_curvature: bool = False   # 是否有曲率（弯曲段）
    has_hook: bool = False        # 是否末端有钩
    has_zhe_point: bool = False   # 是否有折点（方向突变）
    continuous_writing: bool = True  # 是否通常一笔连续书写


@dataclass
class CompoundStroke:
    """组合笔画 — 多个基础笔画连续组合，中间通常不明显抬笔。"""
    key: str                      # 拼音键名
    name: str                     # 中文名
    pinyin: str                   # 拼音
    stroke_sequence: List[str]    # 基础笔画 key 序列
    start_category: str           # 起笔类别: heng_qi/shu_qi/pie_qi/dian_qi/wan_gou
    zhe_count: int = 0            # 折点数量
    has_hook: bool = False        # 是否末端有钩
    has_curve: bool = False       # 是否包含弯曲段
    writing_direction: str = ""   # 书写方向描述
    bezier_suitable: bool = False # 是否适合 Bezier/B样条拟合


@dataclass
class Component:
    """组合部件 / 偏旁 / 结构单元 — 可复用的笔画组合模板。"""
    key: str
    name: str
    pinyin: str = ""
    category: str = "basic"       # basic/left_radical/right_radical/top/bottom/enclosure/high_freq
    typical_position: str = ""    # 在字中的典型位置
    stroke_count: int = 0
    strokes: List[str] = field(default_factory=list)  # 笔画序列（复合笔画键）
    layout_features: Dict[str, bool] = field(default_factory=dict)
    is_closed: bool = False       # 是否封闭结构
    template_suitable: bool = False  # 是否适合作为轨迹模板复用


@dataclass
class CharacterSpec:
    """整字规格 — 部件序列或直接笔画序列。"""
    key: str
    name: str
    stroke_count: int
    components: List[str] = field(default_factory=list)
    strokes: Optional[List[str]] = None
    note: str = ""


# 向后兼容别名
StrokeType = PrimitiveStroke


# ═══════════════════════════════════════════════════════════════════════════
# 1. 基础笔画 PrimitiveStroke — 8大类 50+ 子类
# ═══════════════════════════════════════════════════════════════════════════

BASIC_STROKES: Dict[str, PrimitiveStroke] = {}

def _reg(s: PrimitiveStroke):
    BASIC_STROKES[s.key] = s

# ── 横类 (Heng) ─────────────────────────────────────────────

_reg(PrimitiveStroke("heng",        "横",   "héng",     "heng", "标准",
                     "line", "H", (0, 30)))
_reg(PrimitiveStroke("heng_chang",  "长横", "cháng héng", "heng", "长横",
                     "line", "H", (0, 25)))
_reg(PrimitiveStroke("heng_duan",   "短横", "duǎn héng", "heng", "短横",
                     "line", "H", (0, 35)))
_reg(PrimitiveStroke("heng_xie",    "斜横", "xié héng",  "heng", "斜横",
                     "line", "H", (10, 45)))
_reg(PrimitiveStroke("heng_yang",   "仰横", "yǎng héng", "heng", "仰横",
                     "line", "H", (-5, 20), has_curvature=True))
_reg(PrimitiveStroke("heng_fu",     "覆横", "fù héng",   "heng", "覆横",
                     "line", "H", (0, 30), has_curvature=True))

# ── 竖类 (Shu) ──────────────────────────────────────────────

_reg(PrimitiveStroke("shu",          "竖",     "shù",         "shu", "标准",
                     "line", "V", (60, 120)))
_reg(PrimitiveStroke("shu_chuilu",   "垂露竖", "chuí lù shù",  "shu", "垂露",
                     "line", "V", (70, 110)))
_reg(PrimitiveStroke("shu_xuanzhen", "悬针竖", "xuán zhēn shù", "shu", "悬针",
                     "line", "V", (75, 105)))
_reg(PrimitiveStroke("shu_duan",     "短竖",   "duǎn shù",     "shu", "短竖",
                     "line", "V", (55, 125)))
_reg(PrimitiveStroke("shu_xie",      "斜竖",   "xié shù",      "shu", "斜竖",
                     "line", "V", (40, 75)))
_reg(PrimitiveStroke("shu_zuo",      "左竖",   "zuǒ shù",      "shu", "左竖",
                     "line", "V", (65, 100), has_curvature=True))
_reg(PrimitiveStroke("shu_you",      "右竖",   "yòu shù",      "shu", "右竖",
                     "line", "V", (65, 100), has_curvature=True))

# ── 撇类 (Pie) ──────────────────────────────────────────────

_reg(PrimitiveStroke("pie",        "撇",   "piě",       "pie", "标准",
                     "line", "DL", (30, 70)))
_reg(PrimitiveStroke("pie_ping",   "平撇", "píng piě",  "pie", "平撇",
                     "line", "DL", (15, 45)))
_reg(PrimitiveStroke("pie_duan",   "短撇", "duǎn piě",  "pie", "短撇",
                     "line", "DL", (25, 65)))
_reg(PrimitiveStroke("pie_chang",  "长撇", "cháng piě", "pie", "长撇",
                     "line", "DL", (35, 70)))
_reg(PrimitiveStroke("pie_shu",    "竖撇", "shù piě",   "pie", "竖撇",
                     "curve", "DL", (50, 85), has_curvature=True))
_reg(PrimitiveStroke("pie_xie",    "斜撇", "xié piě",   "pie", "斜撇",
                     "line", "DL", (30, 60)))
_reg(PrimitiveStroke("pie_wan",    "弯撇", "wān piě",   "pie", "弯撇",
                     "curve", "DL", (30, 80), has_curvature=True))

# ── 捺类 (Na) ───────────────────────────────────────────────

_reg(PrimitiveStroke("na",        "捺",   "nà",       "na", "标准",
                     "line", "DR", (110, 160)))
_reg(PrimitiveStroke("na_xie",    "斜捺", "xié nà",   "na", "斜捺",
                     "line", "DR", (115, 155)))
_reg(PrimitiveStroke("na_ping",   "平捺", "píng nà",  "na", "平捺",
                     "line", "DR", (130, 175)))
_reg(PrimitiveStroke("na_fan",    "反捺", "fǎn nà",   "na", "反捺",
                     "line", "DR", (100, 150), has_curvature=True))
_reg(PrimitiveStroke("na_chang",  "长捺", "cháng nà", "na", "长捺",
                     "line", "DR", (110, 160)))
_reg(PrimitiveStroke("na_duan",   "短捺", "duǎn nà",  "na", "短捺",
                     "line", "DR", (110, 165)))

# ── 点类 (Dian) ─────────────────────────────────────────────

_reg(PrimitiveStroke("dian",        "点",   "diǎn",       "dian", "标准",
                     "dot", "any", (-180, 180)))
_reg(PrimitiveStroke("dian_ce",     "侧点", "cè diǎn",    "dian", "侧点",
                     "dot", "DR", (100, 160)))
_reg(PrimitiveStroke("dian_shu",    "竖点", "shù diǎn",   "dian", "竖点",
                     "dot", "V", (60, 120)))
_reg(PrimitiveStroke("dian_pie",    "撇点", "piě diǎn",   "dian", "撇点",
                     "dot", "DL", (30, 70)))
_reg(PrimitiveStroke("dian_na",     "捺点", "nà diǎn",    "dian", "捺点",
                     "dot", "DR", (110, 160)))
_reg(PrimitiveStroke("dian_tiao",   "挑点", "tiǎo diǎn",  "dian", "挑点",
                     "dot", "UR", (130, 170)))
_reg(PrimitiveStroke("dian_zuo",    "左点", "zuǒ diǎn",   "dian", "左点",
                     "dot", "DL", (30, 80)))
_reg(PrimitiveStroke("dian_you",    "右点", "yòu diǎn",   "dian", "右点",
                     "dot", "DR", (100, 150)))
_reg(PrimitiveStroke("dian_chang",  "长点", "cháng diǎn", "dian", "长点",
                     "line", "DR", (110, 160)))

# ── 提类 (Ti) ───────────────────────────────────────────────

_reg(PrimitiveStroke("ti",        "提",   "tí",       "ti", "标准",
                     "line", "UR", (130, 170)))
_reg(PrimitiveStroke("ti_duan",   "短提", "duǎn tí",  "ti", "短提",
                     "line", "UR", (125, 170)))
_reg(PrimitiveStroke("ti_chang",  "长提", "cháng tí", "ti", "长提",
                     "line", "UR", (135, 170)))
_reg(PrimitiveStroke("ti_ping",   "平提", "píng tí",  "ti", "平提",
                     "line", "UR", (150, 180)))
_reg(PrimitiveStroke("ti_xie",    "斜提", "xié tí",   "ti", "斜提",
                     "line", "UR", (130, 165)))

# ── 钩类 (Gou) — 末端带钩的单笔画 ──────────────────────────

_reg(PrimitiveStroke("gou_heng",   "横钩",   "héng gōu",     "gou", "横钩",
                     "hook", "H", (0, 30), has_hook=True))
_reg(PrimitiveStroke("gou_shu",    "竖钩",   "shù gōu",      "gou", "竖钩",
                     "hook", "V", (60, 120), has_hook=True))
_reg(PrimitiveStroke("gou_wan",    "弯钩",   "wān gōu",      "gou", "弯钩",
                     "hook", "V", (60, 120), has_curvature=True, has_hook=True))
_reg(PrimitiveStroke("gou_xie",    "斜钩",   "xié gōu",      "gou", "斜钩",
                     "hook", "DR", (100, 140), has_hook=True))
_reg(PrimitiveStroke("gou_wo",     "卧钩",   "wò gōu",       "gou", "卧钩",
                     "hook", "DR", (140, 175), has_curvature=True, has_hook=True))
_reg(PrimitiveStroke("gou_shuwan", "竖弯钩", "shù wān gōu",  "gou", "竖弯钩",
                     "hook", "V", (60, 160), has_curvature=True, has_hook=True))

# ── 折类 (Zhe) — 含方向突变的单笔画 ────────────────────────

_reg(PrimitiveStroke("zhe_heng",    "横折",   "héng zhé",     "zhe", "横折",
                     "bend", "H", (0, 30), has_zhe_point=True))
_reg(PrimitiveStroke("zhe_shu",     "竖折",   "shù zhé",      "zhe", "竖折",
                     "bend", "V", (60, 120), has_zhe_point=True))
_reg(PrimitiveStroke("zhe_pie",     "撇折",   "piě zhé",      "zhe", "撇折",
                     "bend", "DL", (30, 70), has_zhe_point=True))
_reg(PrimitiveStroke("zhe_shuwan",  "竖弯",   "shù wān",      "zhe", "竖弯",
                     "bend", "V", (60, 160), has_curvature=True))
_reg(PrimitiveStroke("zhe_hengwan", "横折弯", "héng zhé wān", "zhe", "横折弯",
                     "bend", "H", (0, 160), has_curvature=True, has_zhe_point=True))
_reg(PrimitiveStroke("zhe_duo",     "多折",   "duō zhé",      "zhe", "多折",
                     "bend", "any", (-180, 180), has_zhe_point=True))

PRIMITIVE_STROKES = BASIC_STROKES  # 别名


# ═══════════════════════════════════════════════════════════════════════════
# 2. 组合笔画 CompoundStroke — 5大起笔类 40+ 种
# ═══════════════════════════════════════════════════════════════════════════

COMPOUND_STROKES: Dict[str, CompoundStroke] = {}

def _creg(c: CompoundStroke):
    COMPOUND_STROKES[c.key] = c

# ── 横起类 (heng_qi) ────────────────────────────────────────

_creg(CompoundStroke("heng_zhe",         "横折",     "héng zhé",
    ["heng", "shu"], "heng_qi", zhe_count=1))
_creg(CompoundStroke("heng_pie",         "横撇",     "héng piě",
    ["heng", "pie"], "heng_qi", zhe_count=1))
_creg(CompoundStroke("heng_gou",         "横钩",     "héng gōu",
    ["heng", "gou_heng"], "heng_qi", has_hook=True))
_creg(CompoundStroke("heng_zhe_gou",     "横折钩",   "héng zhé gōu",
    ["heng", "shu", "gou_shu"], "heng_qi", zhe_count=1, has_hook=True))
_creg(CompoundStroke("heng_zhe_wan",     "横折弯",   "héng zhé wān",
    ["heng", "shu", "zhe_shuwan"], "heng_qi", zhe_count=1, has_curve=True))
_creg(CompoundStroke("heng_zhe_wan_gou", "横折弯钩", "héng zhé wān gōu",
    ["heng", "shu", "zhe_shuwan", "gou_shuwan"], "heng_qi", zhe_count=2, has_curve=True, has_hook=True))
_creg(CompoundStroke("heng_zhe_zhe",     "横折折",   "héng zhé zhé",
    ["heng", "shu", "heng"], "heng_qi", zhe_count=2))
_creg(CompoundStroke("heng_zhe_zhe_pie", "横折折撇", "héng zhé zhé piě",
    ["heng", "shu", "heng", "pie"], "heng_qi", zhe_count=2))
_creg(CompoundStroke("heng_zhe_zhe_zhe_gou", "横折折折钩", "héng zhé zhé zhé gōu",
    ["heng", "shu", "heng", "shu", "gou_shu"], "heng_qi", zhe_count=3, has_hook=True))
_creg(CompoundStroke("heng_pie_wan_gou", "横撇弯钩", "héng piě wān gōu",
    ["heng", "pie", "gou_wan"], "heng_qi", zhe_count=1, has_curve=True, has_hook=True))
_creg(CompoundStroke("heng_xie_gou",     "横斜钩",   "héng xié gōu",
    ["heng", "gou_xie"], "heng_qi", zhe_count=1, has_hook=True))
_creg(CompoundStroke("heng_zhe_ti",      "横折提",   "héng zhé tí",
    ["heng", "shu", "ti"], "heng_qi", zhe_count=1))

# ── 竖起类 (shu_qi) ────────────────────────────────────────

_creg(CompoundStroke("shu_zhe",         "竖折",     "shù zhé",
    ["shu", "heng"], "shu_qi", zhe_count=1))
_creg(CompoundStroke("shu_ti",          "竖提",     "shù tí",
    ["shu", "ti"], "shu_qi", zhe_count=1))
_creg(CompoundStroke("shu_gou",         "竖钩",     "shù gōu",
    ["shu", "gou_shu"], "shu_qi", has_hook=True))
_creg(CompoundStroke("shu_wan",         "竖弯",     "shù wān",
    ["shu", "zhe_shuwan"], "shu_qi", has_curve=True))
_creg(CompoundStroke("shu_wan_gou",     "竖弯钩",   "shù wān gōu",
    ["shu", "zhe_shuwan", "gou_shuwan"], "shu_qi", has_curve=True, has_hook=True))
_creg(CompoundStroke("shu_zhe_zhe",     "竖折折",   "shù zhé zhé",
    ["shu", "heng", "shu"], "shu_qi", zhe_count=2))
_creg(CompoundStroke("shu_zhe_zhe_gou", "竖折折钩", "shù zhé zhé gōu",
    ["shu", "heng", "shu", "gou_shu"], "shu_qi", zhe_count=2, has_hook=True))
_creg(CompoundStroke("shu_zhe_pie",     "竖折撇",   "shù zhé piě",
    ["shu", "heng", "pie"], "shu_qi", zhe_count=1))
_creg(CompoundStroke("shu_zhe_zhe_pie", "竖折折撇", "shù zhé zhé piě",
    ["shu", "heng", "shu", "pie"], "shu_qi", zhe_count=2))

# ── 撇起类 (pie_qi) ────────────────────────────────────────

_creg(CompoundStroke("pie_zhe",     "撇折",   "piě zhé",
    ["pie", "heng"], "pie_qi", zhe_count=1))
_creg(CompoundStroke("pie_dian",    "撇点",   "piě diǎn",
    ["pie", "dian"], "pie_qi", zhe_count=1))
_creg(CompoundStroke("pie_ti",      "撇提",   "piě tí",
    ["pie", "ti"], "pie_qi"))
_creg(CompoundStroke("pie_na",      "撇捺",   "piě nà",
    ["pie", "na"], "pie_qi"))
_creg(CompoundStroke("pie_zhe_dian","撇折点", "piě zhé diǎn",
    ["pie", "heng", "dian"], "pie_qi", zhe_count=1))
_creg(CompoundStroke("pie_wan_gou", "撇弯钩", "piě wān gōu",
    ["pie", "gou_wan"], "pie_qi", has_curve=True, has_hook=True))

# ── 点起类 (dian_qi) ────────────────────────────────────────

_creg(CompoundStroke("dian_heng",     "点横",   "diǎn héng",
    ["dian", "heng"], "dian_qi"))
_creg(CompoundStroke("dian_pie_c",    "点撇",   "diǎn piě",
    ["dian", "pie"], "dian_qi"))
_creg(CompoundStroke("dian_ti",       "点提",   "diǎn tí",
    ["dian", "ti"], "dian_qi"))
_creg(CompoundStroke("dian_heng_zhe", "点横折", "diǎn héng zhé",
    ["dian", "heng", "shu"], "dian_qi", zhe_count=1))
_creg(CompoundStroke("dian_heng_pie", "点横撇", "diǎn héng piě",
    ["dian", "heng", "pie"], "dian_qi", zhe_count=1))
_creg(CompoundStroke("dian_shu_c",    "点竖",   "diǎn shù",
    ["dian", "shu"], "dian_qi"))

# ── 弯钩类 (wan_gou) — 含弯曲+钩的复合笔画 ─────────────────

_creg(CompoundStroke("wan_gou_c",          "弯钩",       "wān gōu",
    ["gou_wan"], "wan_gou", has_curve=True, has_hook=True))
_creg(CompoundStroke("wo_gou_c",           "卧钩",       "wò gōu",
    ["gou_wo"], "wan_gou", has_curve=True, has_hook=True))
_creg(CompoundStroke("xie_gou_c",          "斜钩",       "xié gōu",
    ["gou_xie"], "wan_gou", has_hook=True))
_creg(CompoundStroke("shu_wan_gou_c",      "竖弯钩",     "shù wān gōu",
    ["shu", "gou_shuwan"], "wan_gou", has_curve=True, has_hook=True))
_creg(CompoundStroke("heng_zhe_wan_gou_c", "横折弯钩",   "héng zhé wān gōu",
    ["heng", "shu", "gou_shuwan"], "wan_gou", zhe_count=2, has_curve=True, has_hook=True))
_creg(CompoundStroke("heng_pie_wan_gou_c", "横撇弯钩",   "héng piě wān gōu",
    ["heng", "pie", "gou_wan"], "wan_gou", zhe_count=1, has_curve=True, has_hook=True))
_creg(CompoundStroke("shu_zhe_zhe_gou_c",  "竖折折钩",   "shù zhé zhé gōu",
    ["shu", "heng", "shu", "gou_shu"], "wan_gou", zhe_count=2, has_hook=True))
_creg(CompoundStroke("heng_zhe_zhe_zhe_gou_c", "横折折折钩", "héng zhé zhé zhé gōu",
    ["heng", "shu", "heng", "shu", "gou_shu"], "wan_gou", zhe_count=3, has_hook=True))


# 向后兼容：构建 compound_key → stroke_sequence_list 的快速查找表
_COMPOUND_SEQ_MAP: Dict[str, List[str]] = {
    k: v.stroke_sequence for k, v in COMPOUND_STROKES.items()
}


# ═══════════════════════════════════════════════════════════════════════════
# 3. 可复用部件 Component — 6类 80+ 个
# ═══════════════════════════════════════════════════════════════════════════

COMPONENTS: Dict[str, Component] = {}

def _comp(key, name, pinyin, category, position, sc, strokes, layout=None, closed=False, tmpl=False):
    COMPONENTS[key] = Component(key, name, pinyin, category, position, sc,
                                strokes, layout or {}, closed, tmpl)

# ── 独体基础部件 ────────────────────────────────────────────

_comp("yi",     "一",   "yī",    "basic", "any", 1, ["heng"], tmpl=True)
_comp("gun",    "丨",   "gǔn",   "basic", "center", 1, ["shu"], tmpl=True)
_comp("dian_b","丶",   "diǎn",  "basic", "any", 1, ["dian"], tmpl=True)
_comp("pie_b",  "丿",   "piě",   "basic", "any", 1, ["pie"], tmpl=True)
_comp("er",     "二",   "èr",    "basic", "any", 2, ["heng", "heng"])
_comp("san",    "三",   "sān",   "basic", "any", 3, ["heng", "heng", "heng"])
_comp("shi",    "十",   "shí",   "basic", "center", 2, ["heng", "shu"], {"cross": True})
_comp("ding",   "丁",   "dīng",  "basic", "any", 2, ["heng", "gou_shu"])
_comp("chang",  "厂",   "chǎng", "basic", "enclosure_top_left", 2, ["heng", "pie"])
_comp("ren",    "人",   "rén",   "basic", "any", 2, ["pie", "na"], tmpl=True)
_comp("ru",     "入",   "rù",    "basic", "any", 2, ["pie", "na"])
_comp("ba",     "八",   "bā",    "basic", "any", 2, ["pie", "na"], tmpl=True)
_comp("da",     "大",   "dà",    "basic", "any", 3, ["heng", "pie", "na"], tmpl=True)
_comp("tian_zi","天",   "tiān",  "basic", "any", 4, ["heng", "heng", "pie", "na"])
_comp("fu_zi",  "夫",   "fū",    "basic", "any", 4, ["heng", "heng", "pie", "na"])
_comp("wang",   "王",   "wáng",  "basic", "any", 4, ["heng", "heng", "shu", "heng"])
_comp("tu",     "土",   "tǔ",    "basic", "any", 3, ["heng", "shu", "heng"], tmpl=True)
_comp("shi_gong","工",  "gōng",  "basic", "any", 3, ["heng", "shu", "heng"])
_comp("mu",     "木",   "mù",    "basic", "any", 4, ["heng", "shu", "pie", "na"], tmpl=True)
_comp("ben",    "本",   "běn",   "basic", "any", 5, ["heng", "shu", "pie", "na", "heng"])
_comp("he",     "禾",   "hé",    "basic", "any", 5, ["pie_ping", "heng", "shu", "pie", "na"], tmpl=True)
_comp("mi",     "米",   "mǐ",    "basic", "any", 6, ["dian", "pie", "heng", "shu", "pie", "na"], tmpl=True)
_comp("shui",   "水",   "shuǐ",  "basic", "any", 4, ["gou_shu", "heng_pie", "pie", "na"], tmpl=True)
_comp("huo",    "火",   "huǒ",   "basic", "any", 4, ["dian", "pie", "pie", "na"], tmpl=True)
_comp("xin",    "心",   "xīn",   "basic", "any", 4, ["dian", "gou_wo", "dian", "dian"], tmpl=True)
_comp("shou",   "手",   "shǒu",  "basic", "any", 4, ["pie_ping", "heng", "heng", "gou_shu"])
_comp("mao",    "毛",   "máo",   "basic", "any", 4, ["pie_ping", "heng", "heng", "gou_shuwan"])
_comp("yue",    "月",   "yuè",   "basic", "any", 4, ["pie_shu", "heng_zhe_gou", "heng", "heng"], tmpl=True)
_comp("tian",   "田",   "tián",  "basic", "any", 5,
       ["shu", "heng_zhe", "heng", "shu", "heng"],
       {"closed": True, "loop": True, "inner_cross": True}, closed=True, tmpl=True)
_comp("mu_zi",  "目",   "mù",    "basic", "any", 5,
       ["shu", "heng_zhe", "heng", "heng", "heng"],
       {"closed": True, "loop": True}, closed=True)
_comp("bai",    "白",   "bái",   "basic", "any", 5,
       ["pie_shu", "shu", "heng_zhe", "heng", "heng"], {"closed": True})
_comp("kou",    "口",   "kǒu",   "basic", "any", 3,
       ["shu", "heng_zhe", "heng"],
       {"closed": True, "loop": True}, closed=True, tmpl=True)
_comp("ri",     "日",   "rì",    "basic", "any", 4,
       ["shu", "heng_zhe", "heng", "heng"], {"closed": True, "loop": True}, closed=True, tmpl=True)
_comp("yong",   "用",   "yòng",  "basic", "any", 5,
       ["pie_shu", "heng_zhe_gou", "heng", "heng", "shu"], {"closed": True})
_comp("che",    "车",   "chē",   "basic", "any", 4, ["heng", "pie_zhe", "heng", "shu"], tmpl=True)
_comp("jin",    "斤",   "jīn",   "basic", "any", 4, ["pie_ping", "pie_shu", "heng", "shu"])
_comp("fang",   "方",   "fāng",  "basic", "any", 4, ["dian", "heng", "heng_zhe_gou", "pie"])
_comp("men",    "门",   "mén",   "basic", "enclosure_top", 3,
       ["dian", "shu", "heng_zhe_gou"], {"closed": True, "enclosure": True}, closed=True, tmpl=True)

# ── 左偏旁 ──────────────────────────────────────────────────

_comp("dan_ren",  "亻", "dān rén páng",  "left_radical", "left", 2, ["pie", "shu"])
_comp("shuang_ren","彳","shuāng rén páng","left_radical","left", 3, ["pie", "pie", "shu"])
_comp("san_dian", "氵", "sān diǎn shuǐ",  "left_radical", "left", 3, ["dian", "dian", "ti"])
_comp("liang_dian","冫","liǎng diǎn shuǐ","left_radical","left", 2, ["dian", "ti"])
_comp("ti_shou",  "扌", "tí shǒu páng",   "left_radical", "left", 3, ["heng", "gou_shu", "ti"])
_comp("shu_xin",  "忄", "shù xīn páng",   "left_radical", "left", 3, ["dian_zuo", "dian_you", "shu"])
_comp("yan_zi",   "讠", "yán zì páng",    "left_radical", "left", 2, ["dian", "heng_zhe_ti"])
_comp("shi_zi",   "礻", "shì zì páng",    "left_radical", "left", 4, ["dian", "heng_pie", "shu", "dian"])
_comp("yi_zi",    "衤", "yī zì páng",     "left_radical", "left", 5, ["dian", "heng_pie", "shu", "pie", "na"])
_comp("mu_pang",  "木", "mù zì páng",     "left_radical", "left", 4, ["heng", "shu", "pie", "dian"])
_comp("he_pang",  "禾", "hé mù páng",     "left_radical", "left", 5, ["pie_ping", "heng", "shu", "pie", "dian"])
_comp("mi_pang",  "米", "mǐ zì páng",     "left_radical", "left", 6, ["dian", "pie", "heng", "shu", "pie", "dian"])
_comp("huo_pang", "火", "huǒ zì páng",    "left_radical", "left", 4, ["dian", "pie", "pie", "dian"])
_comp("tu_pang",  "土", "tǔ zì páng",     "left_radical", "left", 3, ["heng", "shu", "ti"])
_comp("wang_pang","王", "wáng zì páng",   "left_radical", "left", 4, ["heng", "heng", "shu", "ti"])
_comp("shi_pang", "石", "shí zì páng",    "left_radical", "left", 5, ["heng", "pie", "shu", "heng_zhe", "heng"])
_comp("kou_pang", "口", "kǒu zì páng",    "left_radical", "left", 3, ["shu", "heng_zhe", "heng"])
_comp("ri_pang",  "日", "rì zì páng",     "left_radical", "left", 4, ["shu", "heng_zhe", "heng", "heng"])
_comp("yue_pang", "月", "yuè zì páng",    "left_radical", "left", 4, ["pie_shu", "heng_zhe_gou", "heng", "heng"])
_comp("mu_zi_pang","目","mù zì páng",     "left_radical", "left", 5, ["shu", "heng_zhe", "heng", "heng", "heng"])
_comp("nv_pang",  "女", "nǚ zì páng",     "left_radical", "left", 3, ["pie_dian", "pie", "heng"])
_comp("jiao_si",  "纟", "jiǎo sī páng",   "left_radical", "left", 3, ["pie_zhe", "pie_zhe", "ti"])
_comp("che_pang", "车", "chē zì páng",    "left_radical", "left", 4, ["heng", "pie_zhe", "heng", "shu"])
_comp("ma_pang",  "马", "mǎ zì páng",     "left_radical", "left", 3, ["heng_zhe", "shu_zhe_zhe_gou", "heng"])
_comp("bei_pang", "贝", "bèi zì páng",    "left_radical", "left", 4, ["shu", "heng_zhe", "pie", "dian"])
_comp("yu_pang",  "鱼", "yú zì páng",     "left_radical", "left", 8,
       ["pie", "heng_pie", "shu", "heng_zhe", "heng", "shu", "heng", "heng"])
_comp("zu_pang",  "足", "zú zì páng",     "left_radical", "left", 7,
       ["shu", "heng_zhe", "heng", "shu", "heng", "pie", "na"])
_comp("chong_pang","虫","chóng zì páng",  "left_radical", "left", 6,
       ["shu", "heng_zhe", "heng", "shu", "ti", "dian"])
_comp("jin_pang", "钅", "jīn zì páng",    "left_radical", "left", 5,
       ["pie", "heng", "heng", "heng", "shu_zhe"])

# ── 右偏旁 ──────────────────────────────────────────────────

_comp("li_dao",   "刂", "lì dāo páng",  "right_radical", "right", 2, ["heng_zhe_gou", "gou_shu"])
_comp("you_er",   "阝", "yòu ěr páng",  "right_radical", "right", 2, ["heng_zhe_zhe_gou", "shu"])
_comp("dan_er",   "卩", "dān ěr páng",  "right_radical", "right", 2, ["heng_zhe_gou", "shu"])
_comp("fan_wen",  "攵", "fǎn wén páng", "right_radical", "right", 4, ["pie", "heng", "pie", "na"])
_comp("ye_zi",    "页", "yè zì páng",   "right_radical", "right", 6,
       ["heng", "pie_shu", "shu", "heng_zhe", "pie", "dian"])
_comp("niao_pang","鸟", "niǎo zì páng", "right_radical", "right", 5,
       ["pie", "heng_zhe_gou", "dian", "shu_zhe_zhe_gou", "heng"])
_comp("jian_pang","见", "jiàn zì páng", "right_radical", "right", 4,
       ["shu", "heng_zhe", "pie", "gou_shuwan"])
_comp("li_pang",  "力", "lì zì páng",   "right_radical", "right", 2, ["heng_zhe_gou", "pie"])
_comp("cun_pang", "寸", "cùn zì páng",  "right_radical", "right", 3, ["heng", "gou_shu", "dian"])
_comp("ge_pang",  "戈", "gē zì páng",   "right_radical", "right", 4, ["heng", "gou_xie", "pie", "dian"])

# ── 字头 (top components) ───────────────────────────────────

_comp("bao_gai",  "宀", "bǎo gài tóu",  "top", "top", 3,
       ["dian", "dian_zuo", "heng_gou"], {"covers": True}, tmpl=True)
_comp("tu_bao",   "冖", "tū bǎo gài",   "top", "top", 2, ["dian_zuo", "heng_gou"], {"covers": True})
_comp("cao_zi",   "艹", "cǎo zì tóu",   "top", "top", 3, ["heng", "shu", "heng"])
_comp("zhu_zi",   "竹", "zhú zì tóu",   "top", "top", 6,
       ["pie", "heng", "dian", "pie", "heng", "dian"])
_comp("yu_zi",    "雨", "yǔ zì tóu",    "top", "top", 8,
       ["heng", "shu", "heng_zhe_gou", "shu", "dian", "dian", "dian", "dian"], {"covers": True})
_comp("xue_zi",   "穴", "xué zì tóu",   "top", "top", 5,
       ["dian", "dian_zuo", "heng_gou", "pie", "na"], {"covers": True})
_comp("si_dian",  "灬", "sì diǎn dǐ",   "bottom", "bottom", 4,
       ["dian", "dian", "dian", "dian"])
_comp("xin_di",   "心", "xīn zì dǐ",    "bottom", "bottom", 4,
       ["dian", "gou_wo", "dian", "dian"])
_comp("min_di",   "皿", "mǐn zì dǐ",    "bottom", "bottom", 5,
       ["shu", "heng_zhe", "heng", "shu", "heng"], {"closed": True})
_comp("tu_di",    "土", "tǔ zì dǐ",     "bottom", "bottom", 3, ["heng", "shu", "heng"])
_comp("shan_zi",  "山", "shān zì tóu",  "top", "top", 3, ["shu", "shu_zhe", "shu"])

# ── 包围结构 ────────────────────────────────────────────────

_comp("wei_kuang","囗", "wéi zì kuàng", "enclosure", "full", 3,
       ["shu", "heng_zhe", "heng"], {"closed": True, "loop": True, "enclosure": True}, closed=True, tmpl=True)
_comp("qu_kuang", "匚", "qū zì kuàng",  "enclosure", "left_bottom_right", 2,
       ["heng", "shu_zhe"], {"enclosure": True})
_comp("bing_kuang","冂","tóng zì kuàng","enclosure", "top_left_right", 2,
       ["shu", "heng_zhe_gou"], {"enclosure": True})
_comp("guang_zi", "广", "guǎng zì páng","enclosure", "top_left", 3,
       ["dian", "heng", "pie"], {"enclosure": True})
_comp("hu_zi",    "户", "hù zì tóu",    "enclosure", "top_left", 4,
       ["dian", "heng_zhe", "heng", "pie"], {"enclosure": True})
_comp("bing_pang","疒", "bìng zì páng", "enclosure", "top_left", 5,
       ["dian", "heng", "pie", "dian", "ti"], {"enclosure": True})
_comp("zou_zhi",  "辶", "zǒu zhī páng", "enclosure", "bottom_left", 3,
       ["dian", "heng_zhe_zhe_pie", "na_ping"], {"enclosure": True})
_comp("yin_zi",   "廴", "yǐn zì páng",  "enclosure", "bottom_left", 2,
       ["heng_zhe_zhe_pie", "na_ping"], {"enclosure": True})
_comp("zou_di",   "走", "zǒu zì dǐ",    "enclosure", "bottom_left", 7,
       ["heng", "shu", "heng", "shu", "pie", "na"], {"enclosure": True})

# ── 高频结构部件 ────────────────────────────────────────────

_comp("yan",      "言", "yán", "high_freq", "any", 7,
       ["dian", "heng", "heng", "heng", "shu", "heng_zhe", "heng"])
_comp("si",       "糸", "mì",  "high_freq", "any", 6,
       ["pie_zhe", "pie_zhe", "dian", "gou_shu", "pie", "dian"])
_comp("yi_zi2",   "衣", "yī",  "high_freq", "any", 6,
       ["dian", "heng", "pie", "gou_shu", "pie", "na"])
_comp("shi_zi2",  "示", "shì", "high_freq", "any", 5,
       ["heng", "heng", "gou_shu", "pie", "dian"])
_comp("jin_zi",   "金", "jīn", "high_freq", "any", 8,
       ["pie", "na", "heng", "heng", "shu", "dian", "pie", "heng"])
_comp("shi_wu",   "食", "shí", "high_freq", "any", 9,
       ["pie", "na", "dian", "heng_zhe", "heng", "heng", "gou_shu", "pie", "dian"])
_comp("shan",     "山", "shān","high_freq", "any", 3, ["shu", "shu_zhe", "shu"], tmpl=True)
_comp("nv",       "女", "nǚ",  "high_freq", "any", 3,
       ["pie_dian", "pie", "heng"], tmpl=True)
_comp("zi",       "子", "zǐ",  "high_freq", "any", 3,
       ["heng_zhe_gou", "gou_shu", "heng"], tmpl=True)

# 已有键名别名（保持向后兼容）
COMPONENTS["shi_zipang"] = COMPONENTS["shi_zi"]  # 礻


# ═══════════════════════════════════════════════════════════════════════════
# 4. 整字拆解 CharacterSpec
# ═══════════════════════════════════════════════════════════════════════════

CHARACTERS: Dict[str, CharacterSpec] = {}

def _char(key, name, sc, components=None, strokes=None, note=""):
    CHARACTERS[key] = CharacterSpec(key, name, sc, components or [], strokes, note)

_char("yong",  "永", 5,  strokes=["dian", "heng_zhe_gou", "heng_pie", "pie", "na"])
_char("chuan", "川", 3,  strokes=["shu_pie", "shu", "shu"])
_char("zhi",   "之", 3,  strokes=["dian", "heng_pie", "na"])
_char("zhong", "中", 4,  strokes=["shu", "heng_zhe", "heng", "shu"], note="中竖穿过口")
_char("fu",    "福", 13, components=["shi_zi", "yi", "kou", "tian"], note="礻+一+口+田")
_char("ming",  "明", 8,  components=["ri_pang", "yue_pang"], note="日+月")
_char("lin",   "林", 8,  components=["mu_pang", "mu"], note="木+木")
_char("hao",   "好", 6,  components=["nv_pang", "zi"], note="女+子")
_char("xiu",   "休", 6,  components=["dan_ren", "mu"], note="亻+木")
_char("sen",   "森", 12, components=["mu", "mu", "mu"], note="木+木+木")
_char("cun",   "村", 7,  components=["mu_pang", "cun_pang"], note="木+寸")
_char("bei",   "北", 5,  strokes=["shu", "heng", "ti", "pie", "gou_shuwan"])
_char("tian_c","天", 4,  strokes=["heng", "heng", "pie", "na"])
_char("da_c",  "大", 3,  strokes=["heng", "pie", "na"])
_char("ren_c", "人", 2,  strokes=["pie", "na"])
_char("kou_c", "口", 3,  strokes=["shu", "heng_zhe", "heng"])
_char("tian_c2","田",5,  strokes=["shu", "heng_zhe", "heng", "shu", "heng"])
_char("mu_c",  "木", 4,  strokes=["heng", "shu", "pie", "na"])
_char("zi_c",  "子", 3,  strokes=["heng_zhe_gou", "gou_shu", "heng"])
_char("nv_c",  "女", 3,  strokes=["pie_dian", "pie", "heng"])
_char("shan_c","山", 3,  strokes=["shu", "shu_zhe", "shu"])
_char("ri_c",  "日", 4,  strokes=["shu", "heng_zhe", "heng", "heng"])
_char("yue_c", "月", 4,  strokes=["pie_shu", "heng_zhe_gou", "heng", "heng"])
_char("men_c", "门", 3,  strokes=["dian", "shu", "heng_zhe_gou"])
_char("guo",   "国", 8,  components=["wei_kuang", "yu"], note="囗+玉",
       strokes=["shu", "heng_zhe", "heng", "heng", "shu", "heng", "dian", "heng"])
_char("hui",   "回", 6,  components=["wei_kuang", "kou"], note="囗+口")
_char("pin",   "品", 9,  components=["kou", "kou", "kou"], note="口+口+口")


# ═══════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════

def get_stroke_count(name: str) -> Optional[int]:
    """返回字的期望笔画数。"""
    spec = CHARACTERS.get(name.lower())
    if spec:
        return spec.stroke_count
    return None


def get_expected_strokes(name: str) -> Optional[List[str]]:
    """返回字的期望笔画类型序列（展开复合笔画）。"""
    spec = CHARACTERS.get(name.lower())
    if not spec:
        return None
    if spec.strokes:
        return spec.strokes
    result = []
    for comp_key in spec.components:
        comp = COMPONENTS.get(comp_key)
        if comp:
            result.extend(comp.strokes)
    return result


def get_feature_hints(name: str) -> Dict:
    """返回字的聚合结构特征（用于校验骨架拆分）。"""
    spec = CHARACTERS.get(name.lower())
    if not spec:
        return {}
    hints = {}
    for comp_key in spec.components:
        comp = COMPONENTS.get(comp_key)
        if comp:
            for k, v in comp.layout_features.items():
                hints[k] = hints.get(k, 0) + (1 if v else 0)
    return hints


def classify_stroke_direction(stroke: np.ndarray) -> Tuple[float, float]:
    """返回笔画的 PCA 方向角度和首尾角度 (度, 0-180)。"""
    if len(stroke) < 3:
        v = stroke[-1] - stroke[0]
    else:
        centered = stroke.astype(float) - stroke.mean(axis=0)
        _, eigvecs = np.linalg.eigh(np.cov(centered.T))
        v = eigvecs[:, -1]
    deg = np.degrees(np.arctan2(abs(v[0]), abs(v[1])))  # 0=竖, 90=横
    return deg


def _strokes_touch(s1: np.ndarray, s2: np.ndarray, threshold: float = 80) -> bool:
    """两个笔画的任意端点是否足够近（可能共享交叉区）。"""
    ends = [(s1[0], s1[-1]), (s2[0], s2[-1])]
    for e1 in ends[0]:
        for e2 in ends[1]:
            if np.linalg.norm(e1.astype(float) - e2.astype(float)) < threshold:
                return True
    return False


def _could_form_compound(strokes: List[np.ndarray], i: int, j: int,
                         compound_strokes: Dict) -> Optional[str]:
    """检查 strokes[i]→strokes[j] 是否可能组成某个复合笔画，返回复合笔画键名。"""
    si, sj = strokes[i], strokes[j]
    di = classify_stroke_direction(si)
    dj = classify_stroke_direction(sj)

    for ckey, cspec in compound_strokes.items():
        cseq = cspec.stroke_sequence if hasattr(cspec, 'stroke_sequence') else cspec
        if len(cseq) != 2:
            continue
        ti = _direction_to_type(di)
        tj = _direction_to_type(dj)
        if ti == cseq[0] and tj == cseq[1] and _strokes_touch(si, sj):
            return ckey
    return None


def _direction_to_type(deg: float) -> str:
    """角度 → 基础笔画类型。"""
    if deg < 25:
        return "shu"
    if deg > 65:
        return "heng"
    if 25 <= deg <= 50:
        return "pie"
    if 50 < deg <= 65:
        return "na"
    return "unknown"


def _get_component_boundaries(strokes: List[np.ndarray], char_name: str
                               ) -> Optional[Tuple[List[float], List[str]]]:
    """返回部件 x 分界线列表（用于切割跨部件笔画）。

    仅对左→右布局的部件式汉字有效。
    """
    spec = CHARACTERS.get(char_name.lower())
    if not spec or not spec.components or len(spec.components) <= 1:
        return None

    comp_keys = spec.components
    comp_counts = []
    for ck in comp_keys:
        comp = COMPONENTS.get(ck)
        comp_counts.append(comp.stroke_count if comp else 1)

    centroids = np.array([s.mean(axis=0) for s in strokes])
    xs = centroids[:, 1]
    x_min, x_max = xs.min(), xs.max()
    if x_max - x_min < 20:
        return None

    total = sum(comp_counts)
    boundaries = [x_min]
    cum = 0
    for cnt in comp_counts[:-1]:
        cum += cnt
        boundaries.append(x_min + (x_max - x_min) * cum / total)
    boundaries.append(x_max)
    return boundaries, comp_keys


def _split_cross_component(strokes: List[np.ndarray], char_name: str
                           ) -> List[np.ndarray]:
    """在部件边界处切断跨部件的笔画。

    对每个笔画检测其点序列是否跨越部件分界线，
    在所有跨越边界处依次切断。
    """
    bw = _get_component_boundaries(strokes, char_name)
    if bw is None:
        return strokes

    boundaries, comp_keys = bw
    n_bound = len(boundaries) - 2

    result = []
    for s in strokes:
        xs = s[:, 1].astype(float)
        x_min, x_max = xs.min(), xs.max()

        crossing_bounds = []
        for bi in range(n_bound):
            bx = boundaries[bi + 1]
            if x_min < bx and x_max > bx:
                crossing_bounds.append(bx)

        if not crossing_bounds:
            result.append(s)
            continue

        pieces = [s]
        for bx in sorted(crossing_bounds):
            new_pieces = []
            for piece in pieces:
                pxs = piece[:, 1].astype(float)
                p_min, p_max = pxs.min(), pxs.max()
                if p_min < bx and p_max > bx:
                    cut_idx = int(np.argmin(np.abs(pxs - bx)))
                    left = piece[:cut_idx + 1]
                    right = piece[cut_idx + 1:]
                    both_ok = len(left) >= 5 and len(right) >= 5
                    if both_ok:
                        new_pieces.append(left)
                        new_pieces.append(right)
                    else:
                        new_pieces.append(piece)
                else:
                    new_pieces.append(piece)
            pieces = new_pieces
        result.extend(pieces)

    # 移除靠近部件边界且过短的碎片
    bw2 = _get_component_boundaries(result, char_name)
    if bw2:
        boundaries2, _ = bw2
        filtered = []
        for s in result:
            cx = s[:, 1].astype(float).mean()
            near_boundary = any(abs(cx - b) < 30 for b in boundaries2[1:-1])
            if near_boundary and len(s) < 60:
                continue
            filtered.append(s)
        result = filtered

    return result


def _merge_group(strokes: List[np.ndarray], target: int,
                 max_distance: float = 120) -> List[np.ndarray]:
    """将一组笔画合并到目标数量（贪心两遍：复合笔画 + 方向距离）。

    每步合并后检查结果是否产生极端绕路（path/se > 5x），
    若是则拒绝该合并，避免创造出回溯/自交的坏笔画。
    """
    if len(strokes) <= target:
        return list(strokes)

    def _winding_ratio(pts: np.ndarray) -> float:
        """路径长度 / 首尾距离，>5 说明绕路严重。"""
        se = np.linalg.norm(pts[-1].astype(float) - pts[0].astype(float))
        if se < 1:
            return 999.0
        path = np.sum(np.linalg.norm(np.diff(pts.astype(float), axis=0), axis=1))
        return path / se

    compound_strokes = COMPOUND_STROKES
    result = list(strokes)
    used: Set[int] = set()

    # Pass 1: 复合笔画
    while len(result) - len(used) > target:
        best_score, best_i, best_j, best_merged = -1.0, None, None, None
        for i in range(len(result)):
            if i in used: continue
            for j in range(i+1, len(result)):
                if j in used: continue
                ckey = _could_form_compound(result, i, j, compound_strokes)
                if not ckey: continue
                si, sj = result[i], result[j]
                d1 = np.linalg.norm(si[-1].astype(float)-sj[0].astype(float))
                d2 = np.linalg.norm(sj[-1].astype(float)-si[0].astype(float))
                d = min(d1, d2)
                if d >= max_distance: continue
                merged = np.vstack([si,sj[1:]]) if d1<d2 else np.vstack([sj,si[1:]])
                if _winding_ratio(merged) > 5.0:
                    continue  # 拒绝产生绕路的合并
                score = 100.0/(1+d)
                if score > best_score:
                    best_score = score; best_i, best_j = i, j
                    best_merged = merged
        if best_i is None: break
        result[best_i] = best_merged; used.add(best_j)

    result = [s for idx,s in enumerate(result) if idx not in used]
    used = set()

    # Pass 2: 方向+距离
    if len(result) > target:
        while len(result) - len(used) > target:
            best_score, best_i, best_j, best_merged = -1.0, None, None, None
            for i in range(len(result)):
                if i in used: continue
                for j in range(i+1, len(result)):
                    if j in used: continue
                    si, sj = result[i], result[j]
                    di = classify_stroke_direction(si)
                    dj = classify_stroke_direction(sj)
                    ends = [(si[0],sj[0]),(si[0],sj[-1]),(si[-1],sj[0]),(si[-1],sj[-1])]
                    d = min(np.linalg.norm(e.astype(float)-f.astype(float)) for e,f in ends)
                    if d >= max_distance: continue
                    angle_diff = abs(di-dj)
                    score = 100.0/(1+d) + max(0,(60-angle_diff)/60)
                    if score > best_score:
                        d00=np.linalg.norm(si[0].astype(float)-sj[0].astype(float))
                        d01=np.linalg.norm(si[0].astype(float)-sj[-1].astype(float))
                        d10=np.linalg.norm(si[-1].astype(float)-sj[0].astype(float))
                        d11=np.linalg.norm(si[-1].astype(float)-sj[-1].astype(float))
                        bp = min([(d00,0,0),(d01,0,-1),(d10,-1,0),(d11,-1,-1)], key=lambda x:x[0])
                        _, se, sj_e = bp
                        si_ord = si[::-1] if se==0 else si
                        sj_ord = sj if sj_e==0 else sj[::-1]
                        merged = np.vstack([si_ord, sj_ord[1:]])
                        if _winding_ratio(merged) > 5.0:
                            continue  # 拒绝产生绕路的合并
                        best_score = score; best_i, best_j = i, j
                        best_merged = merged
            if best_i is None: break
            result[best_i] = best_merged; used.add(best_j)
        result = [s for idx,s in enumerate(result) if idx not in used]

    return result


def guided_merge(strokes: List[np.ndarray], char_name: str,
                 max_distance: float = 120) -> List[np.ndarray]:
    """根据知识库引导合并多余笔画。

    若字有部件拆解且可空间分区，则在部件内独立合并，
    禁止跨部件拼接。
    """
    spec = CHARACTERS.get(char_name.lower())
    if not spec:
        return strokes

    expected = spec.stroke_count
    if len(strokes) <= expected:
        return strokes

    bw = _get_component_boundaries(strokes, char_name)
    if bw is not None:
        boundaries, comp_keys = bw
        n_comp = len(comp_keys)
        centroids = np.array([s.mean(axis=0) for s in strokes])
        xs = centroids[:, 1]
        groups = [[] for _ in range(n_comp)]
        for si, cx in enumerate(xs):
            assigned = 0
            for j in range(n_comp):
                if boundaries[j] <= cx <= boundaries[j + 1]:
                    assigned = j
                    break
            else:
                assigned = min(range(n_comp),
                              key=lambda j: min(abs(cx-boundaries[j]), abs(cx-boundaries[j+1])))
            groups[assigned].append(si)

        result_parts = []
        for ci in range(n_comp):
            group_strokes = [strokes[i] for i in groups[ci]]
            comp = COMPONENTS.get(comp_keys[ci])
            target = comp.stroke_count if comp else 1
            merged = _merge_group(group_strokes, target, max_distance)
            result_parts.append(merged)

        all_strokes = []
        for g in result_parts:
            all_strokes.extend(g)
        if len(all_strokes) != expected:
            all_strokes = _merge_group(strokes, expected, max_distance)
        return all_strokes

    return _merge_group(strokes, expected, max_distance)


def validate_components(strokes: List[np.ndarray], char_name: str) -> Dict:
    """按部件校验笔画（用于有部件拆解的字）。

    按知识库中部件笔画数顺序分配（笔画已排序→部件顺序自然对应），
    检查部件级笔画数是否正确。
    """
    spec = CHARACTERS.get(char_name.lower())
    if not spec or not spec.components:
        return {"char": char_name, "status": "no_components"}

    comp_keys = spec.components
    if not comp_keys:
        return {"char": char_name, "status": "no_components"}

    comp_counts = []
    for ck in comp_keys:
        comp = COMPONENTS.get(ck)
        comp_counts.append(comp.stroke_count if comp else 1)

    result = {"char": char_name, "components": {}, "all_match": True}
    idx = 0
    for ci, ck in enumerate(comp_keys):
        comp = COMPONENTS.get(ck)
        expected = comp_counts[ci]
        end_idx = min(idx + expected, len(strokes))
        actual = end_idx - idx
        match = actual == expected and expected <= len(strokes) - idx
        result["components"][ck] = {
            "name": comp.name if comp else ck,
            "expected": expected,
            "actual": actual,
            "match": match,
        }
        if not match:
            result["all_match"] = False
        idx = end_idx

    return result


def validate_stroke_count(name: str, extracted_count: int) -> Dict:
    """对照知识库校验笔画数，返回差异信息。"""
    expected = get_stroke_count(name)
    hints = get_feature_hints(name)
    result = {
        "char": name,
        "expected": expected,
        "extracted": extracted_count,
        "correct": expected is not None and extracted_count == expected,
        "diff": (extracted_count - expected) if expected else None,
        "hints": hints,
    }
    return result


# ═══════════════════════════════════════════════════════════════════════════
# 新增查询 API
# ═══════════════════════════════════════════════════════════════════════════

def get_primitive_strokes_by_category(category: str) -> List[PrimitiveStroke]:
    """按大类获取所有基础笔画（如 'heng', 'shu', 'pie' 等）。"""
    return [s for s in BASIC_STROKES.values() if s.category == category]


def get_compound_strokes_by_start(start_category: str) -> List[CompoundStroke]:
    """按起笔类别获取所有组合笔画。"""
    return [c for c in COMPOUND_STROKES.values() if c.start_category == start_category]


def get_components_by_category(category: str) -> List[Component]:
    """按结构类别获取部件。"""
    return [c for c in COMPONENTS.values() if c.category == category]


def lookup_primitive(name_or_key: str) -> Optional[PrimitiveStroke]:
    """按中文名或键名查找基础笔画。"""
    if name_or_key in BASIC_STROKES:
        return BASIC_STROKES[name_or_key]
    for s in BASIC_STROKES.values():
        if s.name == name_or_key:
            return s
    return None


def lookup_compound(name_or_key: str) -> Optional[CompoundStroke]:
    """按中文名或键名查找组合笔画。"""
    if name_or_key in COMPOUND_STROKES:
        return COMPOUND_STROKES[name_or_key]
    for c in COMPOUND_STROKES.values():
        if c.name == name_or_key:
            return c
    return None


def lookup_component(name_or_key: str) -> Optional[Component]:
    """按中文名或键名查找部件。"""
    if name_or_key in COMPONENTS:
        return COMPONENTS[name_or_key]
    for c in COMPONENTS.values():
        if c.name == name_or_key:
            return c
    return None


def get_categories_summary() -> Dict:
    """返回知识库统计摘要。"""
    cats = {}
    for s in BASIC_STROKES.values():
        cats.setdefault(s.category, 0)
        cats[s.category] += 1
    comp_cats = {}
    for c in COMPOUND_STROKES.values():
        comp_cats.setdefault(c.start_category, 0)
        comp_cats[c.start_category] += 1
    comp_types = {}
    for c in COMPONENTS.values():
        comp_types.setdefault(c.category, 0)
        comp_types[c.category] += 1
    return {
        "primitive_strokes": dict(cats),
        "compound_strokes": dict(comp_cats),
        "components": dict(comp_types),
        "characters": len(CHARACTERS),
    }
