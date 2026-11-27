"""Resolution-aware coordinate manager.

坐标按**屏幕方向**记录：竖屏（任意尺寸，截图归一化到 720×1280）与横屏（1920×1080）。
新增方向时加一个 _COORDS_XXX，注册进 _ORIENTATION_COORDS，并在 RESOLUTION_SUFFIX 里给后缀。

Call set_orientation("portrait"/"landscape") at runtime
(e.g. from CampaignInit) to switch. If never called, defaults to 720x1280.
"""

# ---------------------------------------------------------------------------
# Per-resolution coordinate dictionaries
# ---------------------------------------------------------------------------
_COORDS_720 = {
    "RIGHT_ARROW":   (658, 682),
    "NEXT_BUTTON":   (494, 1210),
    "RETRY_BUTTON":  (511, 1207),
    "BACK_BUTTON":   (65,  1211),
    "HELP_INPUT":    (241, 1049),
    "HELP_SEND":     (655, 1046),
}

# TODO: 1920x1080 横屏坐标仍需在真机上逐个核对
_COORDS_1080 = {
    "RIGHT_ARROW":   (1216, 578),
    "NEXT_BUTTON":   (1197, 1025),
    "RETRY_BUTTON":  (1197, 1024),
    "BACK_BUTTON":   (476, 1009),
    "HELP_INPUT":    (840, 885),
    "HELP_SEND":     (1207, 885),
}

_ORIENTATION_COORDS = {
    "portrait":  _COORDS_720,
    "landscape": _COORDS_1080,
}

# 分辨率键 -> pipeline 节点后缀。这里是后缀的唯一来源，my_action 不再自带一份。
# 550×978 现在也用 ""：截图被归一化到 720×1280，识别/坐标/模板全部共用一套，
# _550 那套节点已退役（留着不影响运行，只是不再被引用）。
RESOLUTION_SUFFIX = {
    "portrait":  "",
    "landscape": "_1080",
}

# 兼容旧写法：具体尺寸也能映射到方向
ORIENTATION_ALIASES = {
    "720x1280": "portrait",
    "550x978": "portrait",
    "1920x1080": "landscape",
}

DEFAULT_ORIENTATION = "portrait"
DEFAULT_RESOLUTION = (720, 1280)

# ---------------------------------------------------------------------------
# Runtime resolution state (default: 720x1280)
# ---------------------------------------------------------------------------
_TARGET_W, _TARGET_H = DEFAULT_RESOLUTION
_ORIENTATION = DEFAULT_ORIENTATION
_ACTIVE_COORDS = _ORIENTATION_COORDS[DEFAULT_ORIENTATION]


def set_orientation(orientation: str) -> bool:
    """按屏幕方向切换（portrait / landscape）。"""
    global _ORIENTATION, _ACTIVE_COORDS, _TARGET_W, _TARGET_H
    key = str(orientation).strip().lower()
    key = ORIENTATION_ALIASES.get(key, key)
    known = key in _ORIENTATION_COORDS
    if not known:
        print(f"[coords] 未知方向 {orientation!r}，回退至 portrait")
        key = DEFAULT_ORIENTATION
    _ORIENTATION = key
    _ACTIVE_COORDS = _ORIENTATION_COORDS[key]
    _TARGET_W, _TARGET_H = DEFAULT_RESOLUTION if key == "portrait" else (1920, 1080)
    print(f"[coords] 屏幕方向={key}（坐标基准 {_TARGET_W}x{_TARGET_H}）")
    return known


def set_resolution_by_key(key: str) -> bool:
    """兼容入口：接受方向名或 "1920x1080" 这类旧写法。"""
    return set_orientation(key)


def current_orientation() -> str:
    return _ORIENTATION


def suffix_for(key: str) -> str:
    """Return the pipeline node suffix for a resolution key ("" when unknown)."""
    key = str(key).strip().lower()
    key = ORIENTATION_ALIASES.get(key, key)
    return RESOLUTION_SUFFIX.get(key, "")


def get_current_resolution() -> tuple:
    """Return (width, height) of the active target resolution."""
    return (_TARGET_W, _TARGET_H)


def get_base_resolution() -> tuple:
    """Return (width, height) of the base/reference resolution."""
    return DEFAULT_RESOLUTION


# ---------------------------------------------------------------------------
# Coordinate lookup
# ---------------------------------------------------------------------------

def get(name: str) -> tuple:
    """Return (x, y) for a named coordinate at the active resolution."""
    return _ACTIVE_COORDS[name]
