import os
import sys

# 修复 maa 依赖的 askin 包在 Windows 上无条件 import termios 的问题
# termios 是 Unix 专属模块，Python 3.14 的 askin 未做平台检测
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

from maa.agent.agent_server import AgentServer

import my_action
import my_reco


def main():
    # 切换到项目根目录，防止管理员权限下 CWD 不正确
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    if len(sys.argv) < 2:
        print("Usage: python main.py <socket_id>")
        print("socket_id is provided by AgentIdentifier.")
        sys.exit(1)
        
    socket_id = sys.argv[-1]

    AgentServer.start_up(socket_id)
    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()
