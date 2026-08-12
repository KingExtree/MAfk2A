"""Resolution switcher for MAFK2A end users.

Switches the active resolution by copying the correct pipeline files
and recognition images from pre-generated variants into the resource directory.
Also updates resolution.json so the agent (coords.py) picks up the change.

Usage:
    python switch_resolution.py                  # interactive selection
    python switch_resolution.py 550x978          # direct switch
    python switch_resolution.py --list           # show available resolutions
"""

import json
import os
import shutil
import sys
from pathlib import Path


# Working directory: the directory containing this script (install root)
ROOT = Path(__file__).parent.resolve()


def load_config():
    with open(ROOT / "resolution.json", "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg):
    with open(ROOT / "resolution.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def list_resolutions(cfg):
    active = cfg.get("active", {})
    active_key = f"{active.get('width', '?')}x{active.get('height', '?')}"
    print("Available resolutions:")
    for i, r in enumerate(cfg.get("supported", [])):
        key = f"{r['width']}x{r['height']}"
        marker = " ← active" if key == active_key else ""
        print(f"  [{i}] {r['label']}{marker}")
    return active_key


def switch_to(cfg, target_key: str):
    """Copy variant files to resource/ and update active in config."""
    variants_dir = ROOT / "variants"
    resource_dir = ROOT / "resource"

    variant_path = variants_dir / target_key
    if not variant_path.exists():
        print(f"Error: variant '{target_key}' not found in {variants_dir}")
        print("Available variants:")
        for d in sorted(variants_dir.iterdir()):
            if d.is_dir():
                print(f"  {d.name}")
        sys.exit(1)

    width, height = target_key.split("x")
    width, height = int(width), int(height)

    # Find matching label
    label = target_key
    for r in cfg.get("supported", []):
        if r["width"] == width and r["height"] == height:
            label = r["label"]
            break

    print(f"Switching to: {label} ({target_key})")

    # Copy pipeline files
    src_pipeline = variant_path / "pipeline"
    dst_pipeline = resource_dir / "pipeline"
    if src_pipeline.exists():
        # Clear and copy
        if dst_pipeline.exists():
            shutil.rmtree(dst_pipeline)
        shutil.copytree(src_pipeline, dst_pipeline)
        count = len(list(dst_pipeline.glob("*.json")))
        print(f"  Pipeline: {count} files copied")

    # Copy image files
    src_image = variant_path / "image"
    dst_image = resource_dir / "image"
    if src_image.exists():
        if dst_image.exists():
            shutil.rmtree(dst_image)
        shutil.copytree(src_image, dst_image)
        count = len(list(dst_image.rglob("*.png")))
        print(f"  Images:   {count} files copied")

    # Update active resolution
    cfg["active"] = {"width": width, "height": height}
    save_config(cfg)

    print(f"Done. Active resolution: {target_key}")


def main():
    cfg = load_config()
    active_key = list_resolutions(cfg)

    # Parse arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--list":
            return
        # Direct switch by key (e.g. 550x978)
        switch_to(cfg, arg)
        return

    # Interactive mode
    supported = cfg.get("supported", [])
    if not supported:
        print("No supported resolutions configured.")
        return

    if len(supported) == 1:
        key = f"{supported[0]['width']}x{supported[0]['height']}"
        print(f"Only one resolution available: {supported[0]['label']}")
        if key != active_key:
            switch_to(cfg, key)
        return

    try:
        choice = input(f"\nSelect resolution [0-{len(supported)-1}] (Enter to keep current): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if not choice:
        print("Keeping current resolution.")
        return

    try:
        idx = int(choice)
        if 0 <= idx < len(supported):
            key = f"{supported[idx]['width']}x{supported[idx]['height']}"
            switch_to(cfg, key)
        else:
            print(f"Invalid index: {idx}")
    except ValueError:
        print(f"Invalid input: {choice}")


if __name__ == "__main__":
    main()
