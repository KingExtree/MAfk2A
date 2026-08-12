"""Scale MAA pipeline JSON files for all target resolutions.

Reads resolution.json for supported resolutions, scales all coordinate
fields (target / roi) in pipeline JSONs, and writes variant copies.

Usage:
    python scale_pipelines.py <pipeline_source_dir> <variants_output_dir> [--config resolution.json]
"""

import json
import os
import sys
from pathlib import Path


def load_resolutions(config_path: str) -> tuple:
    """Return (base_width, base_height, [(label, width, height), ...]) from config."""
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    base_w = cfg["base_width"]
    base_h = cfg["base_height"]
    variants = []
    for r in cfg.get("supported", []):
        variants.append((r["label"], r["width"], r["height"]))
    return base_w, base_h, variants


# ---------------------------------------------------------------------------
# JSON coordinate scaling
# ---------------------------------------------------------------------------

def _scale_target(target: list, sx: float, sy: float) -> list:
    """Scale a 4-element target array [x, y, w, h]."""
    if isinstance(target, list) and len(target) >= 2:
        x, y = target[0], target[1]
        w = target[2] if len(target) > 2 else 1
        h = target[3] if len(target) > 3 else 1
        return [int(round(x * sx)), int(round(y * sy)), w, h]
    return target


def _scale_roi(roi: list, sx: float, sy: float) -> list:
    """Scale a 4-element roi array [x, y, w, h]."""
    if isinstance(roi, list) and len(roi) >= 4:
        return [
            int(round(roi[0] * sx)),
            int(round(roi[1] * sy)),
            int(round(roi[2] * sx)),
            int(round(roi[3] * sy)),
        ]
    return roi


def scale_node(node: dict, sx: float, sy: float) -> dict:
    """Recursively scale coordinates in a pipeline node.

    Handles both MAA pipeline formats:
      1. Structured: action = {type: "Click", param: {target: [x,y,w,h]}}
      2. Shorthand:  action = "Click", target = [x, y]  (or [x, y, w, h])
    """
    scaled = dict(node)

    # --- Format 1: structured action {type, param: {target}} ---
    action = scaled.get("action")
    if isinstance(action, dict):
        param = action.get("param")
        if isinstance(param, dict) and "target" in param:
            action = dict(action)
            action["param"] = dict(param)
            action["param"]["target"] = _scale_target(param["target"], sx, sy)
            scaled["action"] = action

    # --- Format 2: shorthand target directly on node ---
    if "target" in scaled and isinstance(scaled["target"], list):
        scaled["target"] = _scale_target(scaled["target"], sx, sy)

    # --- Format 1: structured recognition {type, param: {roi}} ---
    recognition = scaled.get("recognition")
    if isinstance(recognition, dict):
        param = recognition.get("param")
        if isinstance(param, dict) and "roi" in param:
            recognition = dict(recognition)
            recognition["param"] = dict(param)
            recognition["param"]["roi"] = _scale_roi(param["roi"], sx, sy)
            scaled["recognition"] = recognition

    # --- Format 2: shorthand roi directly on node ---
    if "roi" in scaled and isinstance(scaled["roi"], list):
        scaled["roi"] = _scale_roi(scaled["roi"], sx, sy)

    # Recursively scale nested/next nodes
    for key in ("next", "sub", "on_error", "interrupt"):
        val = scaled.get(key)
        if isinstance(val, list):
            scaled[key] = [scale_node(n, sx, sy) if isinstance(n, dict) else n for n in val]
        elif isinstance(val, dict):
            scaled[key] = scale_node(val, sx, sy)

    return scaled


def scale_pipeline_file(src: Path, dst: Path, sx: float, sy: float):
    """Scale one pipeline JSON file."""
    with open(src, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        scaled = scale_node(data, sx, sy)
    elif isinstance(data, list):
        scaled = [scale_node(n, sx, sy) if isinstance(n, dict) else n for n in data]
    else:
        scaled = data

    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(scaled, f, indent=2, ensure_ascii=False)


def scale_pipelines(pipeline_dir: Path, variants_dir: Path, base_w: int, base_h: int,
                    variants: list):
    """For each resolution variant, scale all pipeline JSONs and write to variants_dir."""
    json_files = list(pipeline_dir.glob("*.json"))
    if not json_files:
        print(f"  Warning: no .json files found in {pipeline_dir}")
        return

    for label, tw, th in variants:
        sx = tw / base_w
        sy = th / base_h
        variant_key = f"{tw}x{th}"
        out_dir = variants_dir / variant_key / "pipeline"

        print(f"  Generating pipeline: {variant_key} ({label})  sx={sx:.4f} sy={sy:.4f}")

        for jf in json_files:
            dst = out_dir / jf.name
            scale_pipeline_file(jf, dst, sx, sy)

        print(f"    → {len(json_files)} files written to {out_dir}")


# ======================================================================
# Main
# ======================================================================
def main():
    args = sys.argv[1:]

    # Parse --config
    config_path = None
    positional = []
    i = 0
    while i < len(args):
        if args[i] == "--config" and i + 1 < len(args):
            config_path = args[i + 1]
            i += 2
        else:
            positional.append(args[i])
            i += 1

    if len(positional) < 2:
        print("Usage: python scale_pipelines.py <pipeline_source> <variants_output> [--config resolution.json]")
        sys.exit(1)

    pipeline_dir = Path(positional[0])
    variants_dir = Path(positional[1])

    # Resolve config path
    if config_path is None:
        candidates = [
            pipeline_dir.parent.parent / "config" / "resolution.json",
            Path("assets/config/resolution.json"),
        ]
        for c in candidates:
            if c.exists():
                config_path = str(c)
                break
    if config_path is None:
        print("Error: cannot find resolution.json. Use --config to specify.")
        sys.exit(1)

    base_w, base_h, variants = load_resolutions(config_path)
    print(f"Base resolution: {base_w}x{base_h}")
    print(f"Variants: {[f'{w}x{h}' for _, w, h in variants]}")

    scale_pipelines(pipeline_dir, variants_dir, base_w, base_h, variants)
    print("All pipeline variants generated.")


if __name__ == "__main__":
    main()
