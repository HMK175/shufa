"""楷体笔画知识库：基础笔画 + 复合笔画 + 可复用部件 + 整字拆解。

部件可复用（「口」在「中」「福」里同一套规则），整字由部件序列组成。
换字体时只需修改部件内部的笔画定义和方向约束。
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════
# 基础笔画类型
# ═══════════════════════════════════════════════════════════

@dataclass
class StrokeType:
    key: str           # 内部键名
    name: str          # 中文名
    direction: str     # 大致方向: H/V/DL/DR/UL/...
    typical_angle: Tuple[float, float]  # 角度范围 (度)


BASIC_STROKES = {
    "heng": StrokeType("heng", "横", "H",    (0, 30)),
    "shu":  StrokeType("shu",  "竖", "V",    (60, 120)),
    "pie":  StrokeType("pie",  "撇", "DL",   (30, 70)),
    "na":   StrokeType("na",   "捺", "DR",   (110, 160)),
    "dian": StrokeType("dian", "点", "any",  (-180, 180)),
    "ti":   StrokeType("ti",   "提", "UR",   (130, 170)),
}

COMPOUND_STROKES = {
    "heng_zhe":     ["heng", "shu"],       # 横折：横→竖
    "heng_zhe_gou": ["heng", "shu"],       # 横折钩：横→竖（钩在末端曲率检测）
    "heng_pie":     ["heng", "pie"],       # 横撇：横→撇
    "shu_zhe":      ["shu", "heng"],       # 竖折：竖→横
    "shu_gou":      ["shu", "shu"],        # 竖钩：竖→竖（钩=末端急弯）
    "shu_pie":      ["shu", "pie"],        # 竖撇：竖→撇
    "pie_dian":     ["pie", "dian"],       # 撇点：撇→点
}


# ═══════════════════════════════════════════════════════════
# 可复用部件（含笔画序列 + 结构特征）
# ═══════════════════════════════════════════════════════════

@dataclass
class Component:
    key: str
    name: str
    stroke_count: int
    strokes: List[str]         # 笔画类型序列（含复合笔画键）
    features: Dict[str, bool]  # 结构特征


COMPONENTS = {
    "kou": Component(
        key="kou", name="口", stroke_count=3,
        strokes=["shu", "heng_zhe", "heng"],
        features={"closed": True, "loop": True},
    ),
    "tian": Component(
        key="tian", name="田", stroke_count=5,
        strokes=["shu", "heng_zhe", "heng", "shu", "heng"],
        features={"closed": True, "loop": True, "inner_cross": True},
    ),
    "shi_zipang": Component(
        key="shi_zipang", name="礻(示字旁)", stroke_count=4,
        strokes=["dian", "heng_pie", "shu", "dian"],
        features={"left_side": True},
    ),
    "yi": Component(
        key="yi", name="一", stroke_count=1,
        strokes=["heng"],
        features={},
    ),
}


# ═══════════════════════════════════════════════════════════
# 整字拆解
# ═══════════════════════════════════════════════════════════

@dataclass
class CharacterSpec:
    key: str
    name: str
    stroke_count: int
    components: List[str]      # 部件 key 序列
    strokes: Optional[List[str]] = None  # 无部件时直接给笔画序列
    note: str = ""


CHARACTERS = {
    "chuan": CharacterSpec(
        key="chuan", name="川", stroke_count=3,
        components=[],
        strokes=["shu_pie", "shu", "shu"],
    ),
    "fu": CharacterSpec(
        key="fu", name="福", stroke_count=13,
        components=["shi_zipang", "yi", "kou", "tian"],
        note="礻 + 一 + 口 + 田",
    ),
    "yong": CharacterSpec(
        key="yong", name="永", stroke_count=5,
        components=[],
        strokes=["dian", "heng_zhe_gou", "heng_pie", "pie", "na"],
    ),
    "zhi": CharacterSpec(
        key="zhi", name="之", stroke_count=3,
        components=[],
        strokes=["dian", "heng_pie", "na"],
    ),
    "zhong": CharacterSpec(
        key="zhong", name="中", stroke_count=4,
        components=[],  # 中竖穿过口，不适合空间分区
        strokes=["shu", "heng_zhe", "heng", "shu"],
    ),
}


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

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
    # 从部件展开
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
            for k, v in comp.features.items():
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

    for ckey, cseq in compound_strokes.items():
        if len(cseq) != 2:
            continue
        # 映射：笔画方向 → 类型
        ti = _direction_to_type(di)
        tj = _direction_to_type(dj)
        if ti == cseq[0] and tj == cseq[1] and _strokes_touch(si, sj):
            return ckey
    return None


def _direction_to_type(deg: float) -> str:
    """角度 → 基础笔画类型。"""
    # deg: 0≈竖, 90≈横
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

        # 找所有跨越的边界
        crossing_bounds = []
        for bi in range(n_bound):
            bx = boundaries[bi + 1]
            if x_min < bx and x_max > bx:
                crossing_bounds.append(bx)

        if not crossing_bounds:
            result.append(s)
            continue

        # 在所有边界处切断
        pieces = [s]
        for bx in sorted(crossing_bounds):
            new_pieces = []
            for piece in pieces:
                pxs = piece[:, 1].astype(float)
                p_min, p_max = pxs.min(), pxs.max()
                if p_min < bx and p_max > bx:
                    cut_idx = int(np.argmin(np.abs(pxs - bx)))
                    left = piece[:cut_idx + 1]
                    right = piece[cut_idx + 1:]  # 不重叠
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

    # 移除靠近部件边界且过短的碎片（跨部件连接的残留）
    bw2 = _get_component_boundaries(result, char_name)
    if bw2:
        boundaries2, _ = bw2
        filtered = []
        for s in result:
            cx = s[:, 1].astype(float).mean()
            # 检查是否靠近边界
            near_boundary = any(abs(cx - b) < 30 for b in boundaries2[1:-1])
            if near_boundary and len(s) < 60:
                continue  # 丢弃边界附近的短碎片
            filtered.append(s)
        result = filtered

    return result


def _merge_group(strokes: List[np.ndarray], target: int,
                 max_distance: float = 200) -> List[np.ndarray]:
    """将一组笔画合并到目标数量（贪心三遍）。"""
    if len(strokes) <= target:
        return list(strokes)

    result = list(strokes)
    used = set()

    # Pass 1: 复合笔画
    while len(result) - len(used) > target:
        best_score, best_i, best_j, best_merged = -1, None, None, None
        for i in range(len(result)):
            if i in used: continue
            for j in range(i+1, len(result)):
                if j in used: continue
                ckey = _could_form_compound(result, i, j, COMPOUND_STROKES)
                if not ckey: continue
                si, sj = result[i], result[j]
                d1 = np.linalg.norm(si[-1].astype(float)-sj[0].astype(float))
                d2 = np.linalg.norm(sj[-1].astype(float)-si[0].astype(float))
                d = min(d1, d2)
                if d >= max_distance: continue
                score = 100.0/(1+d)
                if score > best_score:
                    best_score = score; best_i, best_j = i, j
                    best_merged = np.vstack([si,sj[1:]]) if d1<d2 else np.vstack([sj,si[1:]])
        if best_i is None: break
        result[best_i] = best_merged; used.add(best_j)

    result = [s for idx,s in enumerate(result) if idx not in used]
    used = set()

    # Pass 2: 方向+距离
    if len(result) > target:
        while len(result) - len(used) > target:
            best_score, best_i, best_j, best_merged = -1, None, None, None
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
                        best_score = score; best_i, best_j = i, j
                        d00=np.linalg.norm(si[0].astype(float)-sj[0].astype(float))
                        d01=np.linalg.norm(si[0].astype(float)-sj[-1].astype(float))
                        d10=np.linalg.norm(si[-1].astype(float)-sj[0].astype(float))
                        d11=np.linalg.norm(si[-1].astype(float)-sj[-1].astype(float))
                        bp = min([(d00,0,0),(d01,0,-1),(d10,-1,0),(d11,-1,-1)], key=lambda x:x[0])
                        _, se, sj_e = bp
                        si_ord = si[::-1] if se==0 else si
                        sj_ord = sj if sj_e==0 else sj[::-1]
                        best_merged = np.vstack([si_ord, sj_ord[1:]])
            if best_i is None: break
            result[best_i] = best_merged; used.add(best_j)
        result = [s for idx,s in enumerate(result) if idx not in used]
        used = set()

    # Pass 3: 盲合
    if len(result) > target:
        while len(result) - len(used) > target:
            best_d, best_i, best_j = float("inf"), None, None
            for i in range(len(result)):
                if i in used: continue
                for j in range(i+1, len(result)):
                    if j in used: continue
                    si, sj = result[i], result[j]
                    ends = [(si[0],sj[0]),(si[0],sj[-1]),(si[-1],sj[0]),(si[-1],sj[-1])]
                    d = min(np.linalg.norm(e.astype(float)-f.astype(float)) for e,f in ends)
                    if d < best_d: best_d = d; best_i, best_j = i, j
            if best_i is None: break
            si, sj = result[best_i], result[best_j]
            d00=np.linalg.norm(si[0].astype(float)-sj[0].astype(float))
            d01=np.linalg.norm(si[0].astype(float)-sj[-1].astype(float))
            d10=np.linalg.norm(si[-1].astype(float)-sj[0].astype(float))
            d11=np.linalg.norm(si[-1].astype(float)-sj[-1].astype(float))
            bp = min([(d00,0,0),(d01,0,-1),(d10,-1,0),(d11,-1,-1)], key=lambda x:x[0])
            _, se, sj_e = bp
            si_ord = si[::-1] if se==0 else si
            sj_ord = sj if sj_e==0 else sj[::-1]
            result[best_i] = np.vstack([si_ord, sj_ord[1:]])
            used.add(best_j)
        result = [s for idx,s in enumerate(result) if idx not in used]

    return result


def guided_merge(strokes: List[np.ndarray], char_name: str,
                 max_distance: float = 200) -> List[np.ndarray]:
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

    # 尝试部件内合并
    bw = _get_component_boundaries(strokes, char_name)
    if bw is not None:
        boundaries, comp_keys = bw
        n_comp = len(comp_keys)
        # 按 x 坐标分组
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
        # 部件内合并后若总数不对，退回全局合并
        if len(all_strokes) != expected:
            all_strokes = _merge_group(strokes, expected, max_distance)
        return all_strokes

    # 无部件信息：全局合并
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

    # 按序号分配：笔画已按书写顺序排列，顺序对应部件序列
    result = {"char": char_name, "components": {}, "all_match": True}
    idx = 0
    for ci, ck in enumerate(comp_keys):
        comp = COMPONENTS.get(ck)
        expected = comp_counts[ci]
        # 取 expected 个笔画
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
