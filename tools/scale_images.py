"""Scale MAA recognition images for all target resolutions.

Resizes template images proportionally so MAA's template matching
works correctly on different screen resolutions.

Usage:
    python scale_images.py <image_source_dir> <variants_output_dir> [--config resolution.json]
"""

import json
import os
import sys
from pathlib import Path

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def load_resolutions(config_path: str) -> tuple:
    """Return (base_width, base_height, [(label, width, height), ...])."""
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    base_w = cfg["base_width"]
    base_h = cfg["base_height"]
    variants = []
    for r in cfg.get("supported", []):
        variants.append((r["label"], r["width"], r["height"]))
    return base_w, base_h, variants


def scale_image_dir(src_dir: Path, dst_dir: Path, sx: float, sy: float):
    """Scale all PNG images from src_dir to dst_dir using given scale factors."""
    if not HAS_PIL:
        print("  ERROR: Pillow is required for image scaling. Install with: pip install Pillow")
        sys.exit(1)

    png_files = list(src_dir.rglob("*.png"))
    if not png_files:
        print("  Warning: no .png files found under", src_dir)
        return

    scale = (sx * sy) ** 0.5  # geometric mean preserves template aspect ratio
    dst_dir.mkdir(parents=True, exist_ok=True)

    for src_file in png_files:
        rel = src_file.relative_to(src_dir)
        dst_file = dst_dir / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)

        with Image.open(src_file) as img:
            new_w = max(1, int(round(img.width * scale)))
            new_h = max(1, int(round(img.height * scale)))
            img.resize((new_w, new_h), Image.LANCZOS).save(dst_file)

    print(f"  → {len(png_files)} images written to {dst_dir}")


def scale_images(image_dir: Path, variants_dir: Path, base_w: int, base_h: int,
                 variants: list):
    """Scale all PNG images for each resolution variant."""
    if not HAS_PIL:
        print("  ERROR: Pillow is required for image scaling. Install with: pip install Pillow")
        sys.exit(1)

    png_files = list(image_dir.rglob("*.png"))
    if not png_files:
        print("  Warning: no .png files found under", image_dir)
        return

    for label, tw, th in variants:
        # For template matching, image scaling should match screen scaling.
        # Use the average of width and height scale factors for uniform scaling
        # to preserve aspect ratio of template images.
        sx = tw / base_w
        sy = th / base_h
        # Use geometric mean to avoid distorting templates
        scale = (sx * sy) ** 0.5

        variant_key = f"{tw}x{th}"
        out_base = variants_dir / variant_key / "image"

        print(f"  Generating images: {variant_key} ({label})  scale={scale:.4f}")

        for src_file in png_files:
            # Preserve subdirectory structure
            rel = src_file.relative_to(image_dir)
            dst_file = out_base / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)

            with Image.open(src_file) as img:
                new_w = max(1, int(round(img.width * scale)))
                new_h = max(1, int(round(img.height * scale)))
                resized = img.resize((new_w, new_h), Image.LANCZOS)
                resized.save(dst_file)

        print(f"    → {len(png_files)} images written to {out_base}")


# ======================================================================
# Main
# ======================================================================
def main():
    args = sys.argv[1:]

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
        print("Usage: python scale_images.py <image_source> <variants_output> [--config resolution.json]")
        sys.exit(1)

    image_dir = Path(positional[0])
    variants_dir = Path(positional[1])

    if config_path is None:
        candidates = [
            image_dir.parent.parent / "config" / "resolution.json",
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

    scale_images(image_dir, variants_dir, base_w, base_h, variants)
    print("All image variants generated.")


if __name__ == "__main__":
    main()
