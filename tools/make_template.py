"""从整屏截图里裁一个按钮模板，并交叉验证匹配分数。

用途：给 pipeline 的 TemplateMatch 节点补模板。以前模板是"从 MPE 截图里手抠"，
尺寸/内容都靠眼睛，改一次分辨率就得重来。这个脚本把流程固定成三步：
裁 → 存进 assets/resource/image/ → 用另几张截图验证"该命中的命中、不该命中的不误报"。

只依赖 numpy + Pillow（DSH 自带运行时里有），不需要 opencv。

用法示例：

    # 1) 先截一张 720x1280 的整屏图（客户区 1:1）
    # 2) 裁出「战斗」按钮，并用另一张同为准备界面的截图做交叉验证
    python tools/make_template.py shot_prepare.png \
        --crop 532,1158,686,1232 \
        --name battle_button_720p \
        --verify shot_prepare_2.png

    # 3) 再用一张"不该命中"的截图确认不误报
    python tools/make_template.py shot_prepare.png \
        --crop 532,1158,686,1232 \
        --name battle_button_720p \
        --verify shot_stage.png

坐标一律用 720x1280 客户区坐标（裁剪框 x0,y0,x1,y1，右开区间）。
--threshold 只影响打印结论的 PASS/FAIL 判断，不写进 pipeline。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
IMAGE_DIR = REPO_ROOT / "assets" / "resource" / "image"


def load_gray(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.float32).mean(axis=2)


def ncc_map(image: np.ndarray, template: np.ndarray) -> np.ndarray:
    """归一化互相关（等价 cv2.TM_CCOEFF_NORMED，逐行算以免爆内存）。"""
    windows = sliding_window_view(image, template.shape)
    flat = template.ravel()
    zero_t = flat - flat.mean()
    t_norm = float(np.sqrt((zero_t**2).sum()))
    out = np.zeros(windows.shape[:2], dtype=np.float32)
    for y in range(windows.shape[0]):
        block = windows[y].reshape(windows.shape[1], -1).astype(np.float32)
        zero_b = block - block.mean(axis=1, keepdims=True)
        denom = np.sqrt((zero_b**2).sum(axis=1)) * t_norm
        numer = zero_b @ zero_t
        out[y] = np.where(denom > 1e-6, numer / np.maximum(denom, 1e-6), 0.0)
    return out


def best_match(image: np.ndarray, template: np.ndarray) -> tuple[float, int, int]:
    score = ncc_map(image, template)
    y, x = np.unravel_index(int(np.argmax(score)), score.shape)
    return float(score[y, x]), int(x), int(y)


def parse_crop(text: str) -> tuple[int, int, int, int]:
    parts = [int(part) for part in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--crop 需要 x0,y0,x1,y1")
    x0, y0, x1, y1 = parts
    if x1 <= x0 or y1 <= y0:
        raise argparse.ArgumentTypeError("--crop 的 x1/y1 必须大于 x0/y0")
    return x0, y0, x1, y1


def main() -> int:
    parser = argparse.ArgumentParser(description="裁按钮模板并验证匹配分数")
    parser.add_argument("source", type=Path, help="源截图（720x1280 客户区截图）")
    parser.add_argument("--crop", type=parse_crop, required=True, help="裁剪框 x0,y0,x1,y1")
    parser.add_argument("--name", required=True, help="模板文件名（不带 .png）")
    parser.add_argument("--verify", type=Path, action="append", default=[],
                        help="验证用截图，可重复；同图应高分、异图应低分")
    parser.add_argument("--threshold", type=float, default=0.85, help="判定 PASS 的分数线")
    parser.add_argument("--out-dir", type=Path, default=IMAGE_DIR,
                        help="模板输出目录（默认 assets/resource/image）")
    args = parser.parse_args()

    with Image.open(args.source) as source:
        image = source.convert("RGB")
        x0, y0, x1, y1 = args.crop
        if x1 > image.width or y1 > image.height:
            print(f"裁剪框超出图片范围（{image.width}x{image.height}）", file=sys.stderr)
            return 2
        template_image = image.crop((x0, y0, x1, y1))

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{args.name}.png"
    template_image.save(target)
    print(f"模板 {template_image.width}x{template_image.height} -> {target}")

    template = load_gray(target)
    failures = 0
    for path in [args.source, *args.verify]:
        gray = load_gray(path)
        if gray.shape[0] < template.shape[0] or gray.shape[1] < template.shape[1]:
            print(f"  {path.name}: 图比模板小，跳过")
            continue
        score, x, y = best_match(gray, template)
        same = path == args.source
        verdict = "PASS" if score >= args.threshold else "FAIL"
        # 同图必须命中；验证图只要求"不与同图同分"，不做强制判定
        note = "（源图，应≈1.0）" if same else ""
        print(f"  {path.name}: 最高分={score:.4f} 位置=({x},{y}) {verdict}{note}")
        if same and score < 0.99:
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
