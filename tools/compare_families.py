"""逐字段比对 720 家族与 _1080 / _550 家族，找出"结构没对齐"的地方。"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d = json.loads(Path("assets/resource/pipeline/campaign.json").read_text(encoding="utf-8"))
names = set(d)

SUFFIXES = ("_1080", "_550")
FIELDS = ("timeout", "pre_delay", "post_delay", "rate_limit", "repeat")


def base_of(name):
    for s in SUFFIXES:
        if name.endswith(s):
            return name[: -len(s)], s
    return name, ""


def expect(ref, suffix):
    """基础名 + 后缀；基础名本身已带后缀则原样返回。"""
    b, s = base_of(ref)
    if s:  # 引用里已带后缀
        return ref
    return ref + suffix if ref + suffix in names else ref


problems = []
for name in sorted(names):
    b, suf = base_of(name)
    if not suf or b not in d:
        continue
    node, base = d[name], d[b]

    # 1) 动作类型
    a1 = (node.get("action") or {}).get("type")
    a2 = (base.get("action") or {}).get("type")
    if a1 != a2:
        problems.append(f"[动作] {name}: {a1} != 720 的 {a2}")

    # 2) 识别类型
    r1 = (node.get("recognition") or {}).get("type", "-")
    r2 = (base.get("recognition") or {}).get("type", "-")
    if r1 != r2:
        problems.append(f"[识别] {name}: {r1} != 720 的 {r2}")

    # 3) 引用是否指向带后缀的同类节点
    for field in ("next", "on_error"):
        refs1 = node.get(field) or []
        refs2 = base.get(field) or []
        if len(refs1) != len(refs2):
            problems.append(f"[{field}] {name}: {len(refs1)} 项, 720 是 {len(refs2)} 项")
            continue
        for got, want in zip(refs1, refs2):
            exp = expect(want, suf)
            if got != exp:
                problems.append(f"[{field}] {name}: {got} (720 对应应为 {exp})")
            if got not in names:
                problems.append(f"[悬空] {name}.{field} -> {got} 不存在")

    # 4) 时序字段
    for f in FIELDS:
        v1, v2 = node.get(f), base.get(f)
        if v1 != v2:
            problems.append(f"[{f}] {name}: {v1} != 720 的 {v2}")

print(f"节点总数 {len(names)}；带后缀 {sum(1 for n in names if base_of(n)[1])}")
if not problems:
    print("没有发现结构不对齐")
for p in problems:
    print(p)
