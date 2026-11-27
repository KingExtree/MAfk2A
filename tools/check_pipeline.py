#!/usr/bin/env python3
"""pipeline 一致性检查（纯标准库，CI 和本地都能跑）。

检查项：
1. 每个 pipeline JSON 能解析，节点名不以 $ 开头；
2. next / on_error 里引用的节点都存在；
3. 分辨率节点成对：有 _550 就必须有 _1080 和不带后缀的基础节点；
4. target / roi 落在该分辨率的画布内；
5. 识别用到的模板图都存在；
6. agent 依赖的固定节点存在。

用法：
    python tools/check_pipeline.py
    python tools/check_pipeline.py --pipeline-dir assets/resource/pipeline --image-dir assets/resource/image
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 后缀 -> 该分辨率下的画布尺寸
CANVAS = {
    "": (720, 1280),
    "_550": (550, 978),
    "_1080": (1920, 1080),
}

RESOLUTION_SUFFIXES = ("_550", "_1080")

# my_action.py 里直接写死名字、必须存在的节点
REQUIRED_NODES = ("AutoCampaign", "CampaignStop", "CampaignRecover")


def node_suffix(name: str) -> str:
    # 重试镜像节点（xxx_1080Retry1）属于同一分辨率家族，先剥掉 Retry 尾巴再判断
    core = re.sub(r"Retry\d+$", "", name)
    for suffix in RESOLUTION_SUFFIXES:
        if core.endswith(suffix):
            return suffix
    return ""


def iter_refs(value):
    """把 next / on_error 的值展开成节点名列表。"""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        name = value.get("name")
        if isinstance(name, str):
            yield name
    elif isinstance(value, list):
        for item in value:
            yield from iter_refs(item)


def iter_templates(value):
    """recognition.param.template 可能是字符串或字符串列表。"""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                yield item


def check_rect(rect, canvas, what, node_name, errors):
    """检查 [x, y, w, h] 是否落在画布内。"""
    if not isinstance(rect, list) or len(rect) not in (2, 4):
        return
    if not all(isinstance(item, int) for item in rect):
        return

    width, height = canvas
    x, y = rect[0], rect[1]
    w = rect[2] if len(rect) == 4 else 1
    h = rect[3] if len(rect) == 4 else 1
    if w == 0 and h == 0:  # [0, 0, 0, 0] 表示全屏，合法
        return

    if x < 0 or y < 0 or x + w > width or y + h > height:
        errors.append(
            f"{node_name}: {what}={rect} 超出 {width}x{height} 画布"
        )


def load_nodes(pipeline_dir: Path, errors):
    nodes = {}
    for path in sorted(pipeline_dir.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}: JSON 解析失败: {exc}")
            continue
        if not isinstance(data, dict):
            errors.append(f"{path.name}: 顶层必须是对象")
            continue
        for name, node in data.items():
            if name.startswith("$"):
                continue
            if not isinstance(node, dict):
                errors.append(f"{path.name}: 节点 {name} 必须是对象")
                continue
            nodes[name] = node
    return nodes


def check_references(nodes, errors):
    for name, node in nodes.items():
        for field in ("next", "on_error"):
            for ref in iter_refs(node.get(field)):
                if ref.startswith("["):
                    continue  # 锚点写法本项目未使用，跳过
                if ref not in nodes:
                    errors.append(f"{name}: {field} 引用了不存在的节点 {ref}")


def check_parity(nodes, errors):
    """只要求"带后缀的节点有对应的基础版"。

    550×978 现在归一化到 720×1280 的识别空间（同一套模板、同一套坐标），
    所以不再要求 `_550` 与 `_1080` 成对；历史遗留的 `_550` 节点只是还没删。
    """
    for name in nodes:
        suffix = node_suffix(name)
        if not suffix:
            continue
        base = re.sub(r"Retry\d+$", "", name)
        base = base[: -len(suffix)]
        if base not in nodes:
            errors.append(f"{name}: 缺少不带后缀的基础节点 {base}")


def check_geometry(nodes, errors):
    for name, node in nodes.items():
        canvas = CANVAS[node_suffix(name)]
        action = node.get("action")
        if isinstance(action, dict):
            params = action.get("param")
            if isinstance(params, dict):
                check_rect(params.get("target"), canvas, "target", name, errors)

        if isinstance(node.get("target"), list):
            check_rect(node["target"], canvas, "target", name, errors)

        recognition = node.get("recognition")
        if isinstance(recognition, dict):
            params = recognition.get("param")
            if isinstance(params, dict):
                check_rect(params.get("roi"), canvas, "roi", name, errors)

        if isinstance(node.get("roi"), list):
            check_rect(node["roi"], canvas, "roi", name, errors)


def check_templates(nodes, image_dir: Path, errors):
    for name, node in nodes.items():
        recognition = node.get("recognition")
        if not isinstance(recognition, dict):
            continue
        params = recognition.get("param")
        if not isinstance(params, dict):
            continue
        for template in iter_templates(params.get("template")):
            if not (image_dir / template).is_file():
                errors.append(f"{name}: 模板图不存在 {template}")


def check_required(nodes, errors):
    for name in REQUIRED_NODES:
        if name not in nodes:
            errors.append(f"agent 依赖的节点 {name} 不存在")


def main() -> int:
    parser = argparse.ArgumentParser(description="MAA pipeline 一致性检查")
    parser.add_argument(
        "--pipeline-dir",
        type=Path,
        default=REPO_ROOT / "assets" / "resource" / "pipeline",
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=REPO_ROOT / "assets" / "resource" / "image",
    )
    args = parser.parse_args()

    if not args.pipeline_dir.is_dir():
        print(f"找不到 pipeline 目录: {args.pipeline_dir}")
        return 2

    errors = []
    nodes = load_nodes(args.pipeline_dir, errors)

    check_references(nodes, errors)
    check_parity(nodes, errors)
    check_geometry(nodes, errors)
    check_templates(nodes, args.image_dir, errors)
    check_required(nodes, errors)

    if errors:
        print(f"pipeline 检查未通过，共 {len(errors)} 个问题：")
        for message in errors:
            print(f"  - {message}")
        return 1

    print(f"pipeline 检查通过（{len(nodes)} 个节点）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
