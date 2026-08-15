"""Resolution-aware coordinate manager.

All coordinates are manually recorded per resolution for maximum reliability.
To add a new resolution, add a new _COORDS_XXX dict and register it in _COORDS.

Call set_resolution(w, h) at runtime (e.g. from CampaignInit) to switch.
If never called, defaults to 720x1280.
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

_COORDS_550 = {
    "RIGHT_ARROW":   (507, 526),
    "NEXT_BUTTON":   (382, 928),
    "RETRY_BUTTON":  (395, 933),
    "BACK_BUTTON":   (52,  925),
    "HELP_INPUT":    (154, 806),
    "HELP_SEND":     (503, 801),
}

# TODO: 1920x1080 横屏坐标待用户自行录入（当前为占位值 0,0）
_COORDS_1080 = {
    "RIGHT_ARROW":   (1216, 578),
    "NEXT_BUTTON":   (1197, 1025),
    "RETRY_BUTTON":  (1197, 1024),
    "BACK_BUTTON":   (476, 1009),
    "HELP_INPUT":    (840, 885),
    "HELP_SEND":     (1207, 885),
}

_COORDS = {
    (720, 1280):  _COORDS_720,
    (550, 978):   _COORDS_550,
    (1920, 1080): _COORDS_1080,
}

# ---------------------------------------------------------------------------
# Runtime resolution state (default: 720x1280)
# ---------------------------------------------------------------------------
_TARGET_W = 720
_TARGET_H = 1280
_ACTIVE_COORDS = _COORDS_720


def set_resolution(width: int, height: int):
    """Switch the active target resolution at runtime. Call once during init."""
    global _TARGET_W, _TARGET_H, _ACTIVE_COORDS
    key = (width, height)
    if key in _COORDS:
        _ACTIVE_COORDS = _COORDS[key]
        _TARGET_W, _TARGET_H = width, height
        print(f"[coords] 分辨率切换至 {width}x{height}")
    else:
        print(f"[coords] 未找到分辨率 {width}x{height} 的坐标，回退至 720x1280")
        _ACTIVE_COORDS = _COORDS_720
        _TARGET_W, _TARGET_H = 720, 1280


def get_current_resolution() -> tuple:
    """Return (width, height) of the active target resolution."""
    return (_TARGET_W, _TARGET_H)


def get_base_resolution() -> tuple:
    """Return (width, height) of the base/reference resolution."""
    return (720, 1280)


# ---------------------------------------------------------------------------
# Coordinate lookup
# ---------------------------------------------------------------------------

def get(name: str) -> tuple:
    """Return (x, y) for a named coordinate at the active resolution."""
    return _ACTIVE_COORDS[name]
