"""修复 / 重建 MPE 需要的 image 目录联接。

背景：MPE（mpelb）把资源包以**相对路径** "." 传给 MaaFramework，模板是按
`<cwd>/image/<name>` 去找的。开发树里模板真实位置是 `assets/resource/image/`，
所以在仓库根和 `assets/` 下各放一个指向它的目录联接（junction）。联接一旦被
某个工具"材料化"成普通目录，就会留下陈旧副本，新模板加载不到，表现为：
`TemplateMatcher ... templates or threshold is empty` → 任务点了没反应。

用法：python tools/fix_image_links.py [--dry-run]
"""

import ctypes
import os
import shutil
import sys
from pathlib import Path

TARGET = Path("assets/resource/image")
LINKS = [Path("image"), Path("assets/image")]


def main() -> int:
    dry = "--dry-run" in sys.argv
    target = TARGET.resolve()
    if not target.is_dir():
        print(f"模板目录不存在: {target}")
        return 1

    is_windows = os.name == "nt"
    ok = True
    for link in LINKS:
        if link.exists() or link.is_symlink():
            count = len(list(link.glob("*.png"))) if link.is_dir() else -1
            real_target = target if count == len(list(target.glob("*.png"))) else None
            if real_target is not None:
                print(f"{link}: 已是同步的联接/副本（{count} 个模板）")
                continue
            print(f"{link}: 存在但不同步（{count} 个模板 ≠ {len(list(target.glob('*.png')))}），需要重建")
            if not dry:
                # 只删目录联接/普通目录，且必须不含 .git
                if (link / ".git").exists():
                    print(f"  跳过：{link} 看起来是仓库根，不敢删")
                    ok = False
                    continue
                if link.is_symlink():
                    link.unlink()
                else:
                    shutil.rmtree(link)
        else:
            print(f"{link}: 不存在，需要创建")

        if dry:
            continue
        if not is_windows:
            link.symlink_to(target, target_is_directory=True)
        else:
            rc = ctypes.windll.kernel32.CreateSymbolicLinkW(
                str(link), str(target), 0x1  # SYMBOLIC_LINK_FLAG_DIRECTORY
            )
            if not rc:  # 没有权限建符号链接时退回 junction
                os.system(f'mklink /J "{link}" "{target}" >nul')
        print(f"  已建立 -> {target}")

    if not dry:
        for link in LINKS:
            n = len(list(link.glob("*.png"))) if link.is_dir() else 0
            print(f"校验 {link}: {n} 个模板")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
