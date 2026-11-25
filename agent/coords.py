"""Resolution-aware coordinate manager.

All coordinates are manually recorded per resolution for maximum reliability.
To add a new resolution, add a new _COORDS_XXX dict, register it in _COORDS
and add its pipeline suffix to RESOLUTION_SUFFIX.

Call set_resolution(w, h) or set_resolution_by_key("720x1280") at runtime
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

_COORDS_550 = {
    # 已退役：截图现在统一归一化到 720×1280（长边 1280），
    # 550×978 的识别与点击都发生在 720 空间里，直接复用 _COORDS_720。
    # 保留这份数据只作历史参考，运行期不会再被选中。
    "RIGHT_ARROW":   (507, 526),
    "NEXT_BUTTON":   (382, 928),
    "RETRY_BUTTON":  (395, 933),
    "BACK_BUTTON":   (52,  925),
    "HELP_INPUT":    (154, 806),
    "HELP_SEND":     (503, 801),
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

_COORDS = {
    (720, 1280):  _COORDS_720,
    (550, 978):   _COORDS_550,
    (1920, 1080): _COORDS_1080,
}

# 分辨率键 -> pipeline 节点后缀。这里是后缀的唯一来源，my_action 不再自带一份。
# 550×978 现在也用 ""：截图被归一化到 720×1280，识别/坐标/模板全部共用一套，
# _550 那套节点已退役（留着不影响运行，只是不再被引用）。
RESOLUTION_SUFFIX = {
    "720x1280":  "",
    "550x978":   "",
    "1920x1080": "_1080",
}

# 截图归一化后，这些真实分辨率在运行期统一按 720×1280 处理
_NORMALIZED_TO = {
    (550, 978): (720, 1280),
}

DEFAULT_RESOLUTION = (720, 1280)

# ---------------------------------------------------------------------------
# Runtime resolution state (default: 720x1280)
# ---------------------------------------------------------------------------
_TARGET_W, _TARGET_H = DEFAULT_RESOLUTION
_ACTIVE_COORDS = _COORDS[DEFAULT_RESOLUTION]


def set_resolution(width: int, height: int) -> bool:
    """Switch the active target resolution at runtime. Returns True on a known size."""
    global _TARGET_W, _TARGET_H, _ACTIVE_COORDS
    width, height = _NORMALIZED_TO.get((width, height), (width, height))
    key = (width, height)
    if key in _COORDS:
        _ACTIVE_COORDS = _COORDS[key]
        _TARGET_W, _TARGET_H = width, height
        print(f"[coords] 分辨率切换至 {width}x{height}")
        return True
    print(f"[coords] 未找到分辨率 {width}x{height} 的坐标，回退至 720x1280")
    _ACTIVE_COORDS = _COORDS[DEFAULT_RESOLUTION]
    _TARGET_W, _TARGET_H = DEFAULT_RESOLUTION
    return False


def set_resolution_by_key(key: str) -> bool:
    """Switch by "720x1280"-style key; falls back to the default on bad input."""
    try:
        width_str, height_str = str(key).strip().lower().split("x")
        width, height = int(width_str), int(height_str)
    except (ValueError, AttributeError):
        print(f"[coords] 无法解析分辨率参数: {key!r}，使用默认 720x1280")
        set_resolution(*DEFAULT_RESOLUTION)
        return False
    return set_resolution(width, height)


def suffix_for(key: str) -> str:
    """Return the pipeline node suffix for a resolution key ("" when unknown)."""
    return RESOLUTION_SUFFIX.get(str(key).strip().lower(), "")


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
