"""打印游戏窗口/客户区几何，用于核对 Maa 截图空间与桌面坐标的对应关系。"""

import ctypes
import sys
from ctypes import wintypes

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
try:
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    user32.SetProcessDPIAware()

TARGET_EXE = "AFK Journey.exe"


def find_window(exe_name: str):
    found = []
    CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _lp):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(0x1000, False, pid.value)
        if not handle:
            return True
        try:
            size = wintypes.DWORD(1024)
            buf = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                if buf.value.rsplit("\\", 1)[-1].lower() == exe_name.lower():
                    found.append(hwnd)
        finally:
            kernel32.CloseHandle(handle)
        return True

    user32.EnumWindows(CB(cb), 0)
    return found


for hwnd in find_window(TARGET_EXE):
    cls = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls, 256)
    title = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, title, 256)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    client = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(client))
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    w, h = client.right - client.left, client.bottom - client.top
    print(f"hwnd={hwnd} class={cls.value!r} title={title.value!r} visible={bool(user32.IsWindowVisible(hwnd))}")
    print(f"  window  ({rect.left},{rect.top})-({rect.right},{rect.bottom})  {rect.right-rect.left}x{rect.bottom-rect.top}")
    print(f"  client  {w}x{h}  原点=({pt.x},{pt.y})")
    if w and h:
        print(f"  客户区比例 {w/h:.4f}   （720x1280=0.5625, 550x978=0.5624）")
