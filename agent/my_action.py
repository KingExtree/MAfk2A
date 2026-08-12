"""
MAFK2A 自定义动作
"""
import json
import subprocess
import time
import ctypes

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

import coords


# =============================================
# 工具函数
# =============================================

def _get_param(argv, key, default=None):
    """兼容不同 MAA 版本：custom_action_param 可能是 dict、JSON 字符串或普通字符串"""
    param = argv.custom_action_param
    if isinstance(param, dict):
        return param.get(key, default)
    if isinstance(param, str) and param:
        try:
            return json.loads(param).get(key, default)
        except json.JSONDecodeError:
            pass
    return default


# =============================================
# 关卡类型状态管理（模块级变量）
# =============版本================================
# mode: "phantom" = 幻灵挑战, "normal" = 挑战
# formation_index: 1~10

_campaign_state = {
    "mode": "phantom",
    "formation_index": 1,
}

HELP_CHAT_ENABLED = True   # 是否开启"救救孩子"（默认关闭）
_RES_SUFFIX = ""          # 分辨率后缀：""=720x1280, "_550"=550x978


def _task(name: str) -> str:
    """返回带分辨率后缀的 task 名"""
    return name + _RES_SUFFIX


def _update_try_formation(context: Context, formation_index: int, mode: str):
    """更新 TryFormation 节点的参数"""
    context.override_pipeline({
        _task("TryFormation"): {
            "custom_action_param": {
                "formation_index": str(formation_index),
                "campaign_mode": mode,
            }
        }
    })


# =============================================
# 自定义动作1
# =============================================

@AgentServer.custom_action("CampaignInit")
class CampaignInit(CustomAction):
    """初始化：幻灵挑战模式，阵容 #1。可通过 send_help 参数开启救救孩子。"""

    def run(self, context, argv):
        global HELP_CHAT_ENABLED, _RES_SUFFIX
        _campaign_state["mode"] = "phantom"
        _campaign_state["formation_index"] = 1
        HELP_CHAT_ENABLED = str(_get_param(argv, "send_help", "false")).lower() == "true"
        if HELP_CHAT_ENABLED:
            print("[CampaignInit] 已开启「救救孩子」")

        # 读取全局分辨率选项，切换坐标缩放 & task 后缀
        res_str = _get_param(argv, "resolution", "720x1280")
        try:
            w_str, h_str = res_str.split("x")
            coords.set_resolution(int(w_str), int(h_str))
            _RES_SUFFIX = "_550" if res_str == "550x978" else ""
        except (ValueError, AttributeError):
            print(f"[CampaignInit] 无法解析分辨率参数: {res_str}, 使用默认 720x1280")

        _update_try_formation(context, 1, "phantom")
        return True


@AgentServer.custom_action("CampaignFormationSelect")
class CampaignFormationSelect(CustomAction):
    """在推荐阵容界面，点 N-1 次右箭头翻到目标阵容页"""

    def run(self, context, argv):
        try:
            index = int(_get_param(argv, "formation_index", "1"))
        except (ValueError, TypeError):
            index = 1

        if index < 1 or index > 10:
            return False

        x, y = coords.get("RIGHT_ARROW")
        for _ in range(index - 1):
            context.tasker.controller.post_click(x, y).wait()
            time.sleep(0.5)
        return True


@AgentServer.custom_action("CampaignResetFormation")
class CampaignResetFormation(CustomAction):
    """胜利：重置阵容 → 点下一关 → 路由回当前模式入口"""

    def run(self, context, argv):
        _campaign_state["formation_index"] = 1
        mode = _campaign_state["mode"]
        next_node = _task("CampaignPhantomEntry") if mode == "phantom" else _task("CampaignNormalEntry")
        _update_try_formation(context, 1, mode)

        nx, ny = coords.get("NEXT_BUTTON")
        context.tasker.controller.post_click(nx, ny).wait()
        time.sleep(1.5)

        context.override_next(argv.node_name, [next_node])
        return True


@AgentServer.custom_action("CampaignNextFormation")
class CampaignNextFormation(CustomAction):
    """失败：阵容 +1 → 路由到推荐阵容；
       超过 10 则切换关卡类型或停止（若开启则发求救）"""

    def run(self, context, argv):
        current = _campaign_state["formation_index"]
        mode = _campaign_state["mode"]
        nxt = current + 1

        if nxt > 10:
            if mode == "phantom":
                # 幻灵全失败 → 点「返回」→ 切到普通关卡
                bx, by = coords.get("BACK_BUTTON")
                context.tasker.controller.post_click(bx, by).wait()
                time.sleep(2)
                _campaign_state["mode"] = "normal"
                _campaign_state["formation_index"] = 1
                _update_try_formation(context, 1, "normal")
                context.override_next(argv.node_name, [_task("CampaignNormalEntry")])
                return True
            else:
                print(f"[CampaignNextFormation] 普通关卡全部失败 HELP_CHAT_ENABLED={HELP_CHAT_ENABLED}")
                if HELP_CHAT_ENABLED:
                    # 点两次「返回」退回聊天界面
                    print("[CampaignNextFormation] 准备求助，点击两次返回...")
                    bx, by = coords.get("BACK_BUTTON")
                    for _ in range(2):
                        context.tasker.controller.post_click(bx, by).wait()
                        time.sleep(1.5)
                    context.override_next(argv.node_name, [_task("CampaignHelpChat")])
                else:
                    print("[CampaignNextFormation] 未开启求助，直接停止")
                    context.override_next(argv.node_name, [_task("CampaignStop")])
                return True

        # 还有阵容可试 → 点「再次战斗」→ 继续当前模式
        rx, ry = coords.get("RETRY_BUTTON")
        context.tasker.controller.post_click(rx, ry).wait()
        time.sleep(2)

        _campaign_state["formation_index"] = nxt
        _update_try_formation(context, nxt, mode)
        context.override_next(argv.node_name, [_task("OpenRecommended")])
        return True


@AgentServer.custom_action("CampaignSendHelp")
class CampaignSendHelp(CustomAction):
    """在工会聊天发送"救救孩子"：点击输入框 → 打字 → 点击发送"""

    def run(self, context, argv):
        # 1. 点击输入框获取焦点
        ix, iy = coords.get("HELP_INPUT")
        context.tasker.controller.post_click(ix, iy).wait()
        time.sleep(0.5)

        # 2. 将文字写入剪贴板，模拟 Ctrl+V 粘贴
        text = "救救孩子"
        subprocess.run(
            f'powershell -command "Set-Clipboard -Value \'{text}\'"',
            shell=True,
        )
        time.sleep(0.3)

        # Ctrl + V
        ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)   # Ctrl down
        ctypes.windll.user32.keybd_event(0x56, 0, 0, 0)   # V down
        ctypes.windll.user32.keybd_event(0x56, 0, 2, 0)   # V up
        ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)   # Ctrl up
        time.sleep(0.5)

        # 3. 点击发送
        sx, sy = coords.get("HELP_SEND")
        context.tasker.controller.post_click(sx, sy).wait()
        time.sleep(0.5)

        print("[CampaignSendHelp] 已发送「救救孩子」")
        return True


@AgentServer.custom_action("WaitForBattleEnd")
class WaitForBattleEnd(CustomAction):
    """循环检测战斗是否结束（胜利/失败），内部自行轮询"""

    def run(self, context, argv):
        import threading

        stop_flag = threading.Event()

        def on_stop():
            stop_flag.set()

        # 注册 MAA 中断回调
        try:
            token = context.tasker.bind_stop_callback(on_stop)
        except Exception:
            token = None

        max_wait = 300  # 最多等 300 秒
        interval = 3    # 每 3 秒检查一次
        elapsed = 0

        while elapsed < max_wait and not stop_flag.is_set():
            time.sleep(interval)
            elapsed += interval

            screenshot = context.tasker.controller.post_screencap().wait().get()
            if screenshot is None or screenshot.size == 0:
                continue

            # 检测胜利
            victory = context.run_recognition(_task("VictoryIndicator"), screenshot)
            if victory.box:
                print(f"[WaitForBattleEnd] 检测到胜利 (elapsed={elapsed}s)")
                context.override_next(argv.node_name, [_task("HandleVictory")])
                return True

            # 检测失败
            defeat = context.run_recognition(_task("DefeatIndicator"), screenshot)
            if defeat.box:
                print(f"[WaitForBattleEnd] 检测到失败 (elapsed={elapsed}s)")
                context.override_next(argv.node_name, [_task("HandleDefeat")])
                return True

        print(f"[WaitForBattleEnd] 超时 (elapsed={elapsed}s)")
        context.override_next(argv.node_name, [_task("CampaignStop")])
        return True
