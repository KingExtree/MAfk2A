import os
import sys
import time
import traceback

# ---------------------------------------------------------------- 启动日志
# MPE / MFAAvalonia 拉起 agent 时把子进程输出吞掉了，出问题只能靠这个文件。
# 放在项目根目录（agent-startup.log，已 gitignore）。
_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_LOG_PATH = os.path.join(_ROOT, "agent-startup.log")


def _log(msg: str) -> None:
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}][pid {os.getpid()}] {msg}\n")
    except Exception:
        pass


_log(f"---- agent 启动 ----")
_log(f"argv={sys.argv}")
_log(f"cwd={os.getcwd()}")
_log(f"python={sys.executable}")
_log(f"sys.path[0]={sys.path[0] if sys.path else ''}")
_log(f"本文件={os.path.abspath(__file__)}")
_log(f"项目根={_ROOT}")

# 修复 maa 依赖的 askin 包在 Windows 上无条件 import termios 的问题
# termios 是 Unix 专属模块，Windows 上任何 Python 版本都会 ImportError
if sys.platform == "win32" and "termios" not in sys.modules:
    import types
    _termios = types.ModuleType("termios")
    _termios.tcgetattr = lambda fd: None
    _termios.tcsetattr = lambda fd, when, attrs: None
    _termios.TCSANOW = 0
    _termios.ICANON = 0
    _termios.ECHO = 0
    _termios.VTIME = 5
    _termios.VMIN = 6
    _termios.TCSAFLUSH = 2
    sys.modules["termios"] = _termios

try:
    import maa
    _log(f"maa 包={os.path.dirname(maa.__file__)}")
except Exception:
    _log("import maa 失败:\n" + traceback.format_exc())
    raise

from maa.agent.agent_server import AgentServer

_log("AgentServer 导入成功")

# 注册必须发生在 start_up 之前：客户端在握手时会快照服务端注册表（resp.actions），
# 握手完成后再注册它就看不见了，表现为 [ERR][CustomAction.cpp] Action is null。
# 先 import maa.agent.agent_server 会把库切成 agent_server 模式，所以到这里注册是合法的。
import my_action  # noqa: E402,F401

_log(f"my_action 注册完成，动作={sorted(AgentServer._custom_action_holder)}")


def main():
    # 切换到项目根目录，防止管理员权限下 CWD 不正确
    os.chdir(_ROOT)

    if len(sys.argv) < 2:
        _log("缺少 socket_id 参数，退出")
        print("Usage: python main.py <socket_id>")
        print("socket_id is provided by AgentIdentifier.")
        sys.exit(1)

    socket_id = sys.argv[-1]
    _log(f"开始 start_up, identifier={socket_id!r}")

    try:
        ok = AgentServer.start_up(socket_id)
    except Exception:
        _log("start_up 抛异常:\n" + traceback.format_exc())
        raise
    _log(f"start_up 返回 {ok}")
    if not ok:
        print("[Agent] start_up 失败：连不上 AgentClient，检查 MPE/MFAAvalonia 是否在运行")
        sys.exit(1)

    # 自定义动作已在模块级注册（见文件顶部），这里只负责连接与保持
    AgentServer.join()
    _log("join 返回，shut_down")
    AgentServer.shut_down()
    _log("已退出")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        _log("SystemExit")
        raise
    except Exception:
        _log("未捕获异常:\n" + traceback.format_exc())
        raise
