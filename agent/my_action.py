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

# 挑战类型范围：both=幻灵+普通, phantom=只幻灵, normal=只普通
_challenge_scope = "both"

# 重试设置：0=不重试, 1~5=次数, -1=无限
_retry_limit = 0
_retry_count = 0

HELP_CHAT_ENABLED = True   # 是否开启"救救孩子"（默认关闭）
_RES_SUFFIX = ""          # 分辨率后缀：""=720x1280, "_550"=550x978, "_1080"=1920x1080

# 分辨率 -> task 后缀映射
_RESOLUTION_SUFFIX_MAP = {
    "720x1280":  "",
    "550x978":   "_550",
    "1920x1080": "_1080",
}


def _initial_mode() -> str:
    """根据挑战类型返回初始模式"""
    return "normal" if _challenge_scope == "normal" else "phantom"


def _parse_retry_limit(value) -> int:
    """解析重试次数：infinite -> -1，数字 -> 1~5，其他 -> 0"""
    s = str(value).strip().lower()
    if s == "infinite":
        return -1
    try:
        n = int(s)
    except ValueError:
        return 0
    if n < 0:
        return -1
    return max(0, min(5, n))


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
    """初始化：读取挑战类型/分辨率参数，设置初始模式与入口。"""

    def run(self, context, argv):
        global HELP_CHAT_ENABLED, _RES_SUFFIX, _challenge_scope, _retry_limit, _retry_count
        _campaign_state["formation_index"] = 1

        # 方案 B：参数已平铺到 AutoCampaign 节点顶层字段，从节点定义一次性读取
        data = context.get_node_data("AutoCampaign") or {}

        HELP_CHAT_ENABLED = str(data.get("send_help", "false")).lower() == "true"
        if HELP_CHAT_ENABLED:
            print("[CampaignInit] 已开启「救救孩子」")

        # 读取挑战类型选项
        _challenge_scope = str(data.get("challenge", "both")).lower()
        if _challenge_scope not in ("both", "phantom", "normal"):
            print(f"[CampaignInit] 未知挑战类型: {_challenge_scope}, 回退 both")
            _challenge_scope = "both"

        # 根据挑战类型决定初始模式
        _campaign_state["mode"] = _initial_mode()

        # 读取重试次数选项
        _retry_limit = _parse_retry_limit(data.get("retry", "0"))
        _retry_count = 0
        print(f"[CampaignInit] 重试上限={_retry_limit}")

        # 读取全局分辨率选项，切换坐标缩放 & task 后缀
        res_str = str(data.get("resolution", "720x1280"))
        try:
            w_str, h_str = res_str.split("x")
            coords.set_resolution(int(w_str), int(h_str))
            _RES_SUFFIX = _RESOLUTION_SUFFIX_MAP.get(res_str, "")
        except (ValueError, AttributeError):
            print(f"[CampaignInit] 无法解析分辨率参数: {res_str}, 使用默认 720x1280")

        _update_try_formation(context, 1, _campaign_state["mode"])

        # 动态路由到对应入口，避免与 option 的 next 打架
        entry = _task("CampaignPhantomEntry") if _campaign_state["mode"] == "phantom" else _task("CampaignNormalEntry")
        context.override_next(argv.node_name, [entry])
        print(f"[CampaignInit] 挑战类型={_challenge_scope}, 模式={_campaign_state['mode']}, 入口={entry}")
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
        global _retry_count
        current = _campaign_state["formation_index"]
        mode = _campaign_state["mode"]
        nxt = current + 1

        if nxt > 10:
            if mode == "phantom" and _challenge_scope == "both":
                # 幻灵全失败且选择「都打」→ 点「返回」→ 切到普通关卡
                bx, by = coords.get("BACK_BUTTON")
                context.tasker.controller.post_click(bx, by).wait()
                time.sleep(2)
                _campaign_state["mode"] = "normal"
                _campaign_state["formation_index"] = 1
                _update_try_formation(context, 1, "normal")
                context.override_next(argv.node_name, [_task("CampaignNormalEntry")])
                return True
            else:
                # 整体流程全部失败：优先重试，重试耗尽后再求助/停止
                if _retry_limit == -1 or _retry_count < _retry_limit:
                    _retry_count += 1
                    if _retry_limit == -1:
                        print(f"[CampaignNextFormation] 全部失败，从头重试（第 {_retry_count} 次，无限）")
                    else:
                        print(f"[CampaignNextFormation] 全部失败，从头重试（第 {_retry_count}/{_retry_limit} 次）")
                    bx, by = coords.get("BACK_BUTTON")
                    context.tasker.controller.post_click(bx, by).wait()
                    time.sleep(2)
                    _campaign_state["mode"] = _initial_mode()
                    _campaign_state["formation_index"] = 1
                    _update_try_formation(context, 1, _campaign_state["mode"])
                    entry = _task("CampaignPhantomEntry") if _campaign_state["mode"] == "phantom" else _task("CampaignNormalEntry")
                    context.override_next(argv.node_name, [entry])
                    return True

                print(f"[CampaignNextFormation] 全部失败 mode={mode} scope={_challenge_scope} HELP_CHAT_ENABLED={HELP_CHAT_ENABLED}")
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
