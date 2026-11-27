"""
MAFK2A 自定义动作

约定：
- 决策（选项解析、失败后怎么走）放在 campaign_state.py，可脱离游戏单测；
- 坐标、分辨率后缀统一由 coords.py 提供，动作里不出现硬编码坐标；
- 所有"下一步"都通过 context.override_next 改写，pipeline 里不写死分支。
"""
import json
import subprocess
import time
import ctypes

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

import campaign_state
import coords


# =============================================
# 常量
# =============================================

# 终止节点：所有尝试都失败后停在这里。CampaignAbort 会让整个任务显式失败，
# 避免"什么都没做成"却显示任务成功。
STOP_NODE = "CampaignStop"

# 恢复节点在 pipeline 里叫 "CampaignRecover"（关键节点的 on_error 指向它），
# 动作本体见文件末尾的 CampaignRecover 类。

# 单轮任务允许的自动恢复次数，超过则走求助/停止
RECOVER_LIMIT = 2

# 求救文本
HELP_TEXT = "救救孩子"

# 战斗结算的等待已经下沉到 pipeline：WaitBattleEnd 节点用 next=[VictoryIndicator, DefeatIndicator]
# + timeout/rate_limit 让框架自己轮询，这里不再保留轮询参数。

# 各步骤点击后的等待（秒）
WAIT_SHORT = 1.5
WAIT_MEDIUM = 2.0


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


def _task(name: str) -> str:
    """返回带分辨率后缀的 task 名"""
    return name + _RES_SUFFIX


def _update_try_formation(context: Context, formation_index: int, mode: str):
    """更新 TryFormation 节点的参数。

    注意：必须写完整的结构化 action。只写顶层 custom_action_param 时，
    节点里已有的 action 对象会盖掉它，覆盖实际不生效。
    """
    context.override_pipeline({
        _task("TryFormation"): {
            "action": {
                "type": "Custom",
                "param": {
                    "custom_action": "CampaignFormationSelect",
                    "custom_action_param": {
                        "formation_index": str(formation_index),
                        "campaign_mode": mode,
                    },
                },
            },
        }
    })


def _click(context: Context, name: str):
    """点击 coords 里登记的坐标（点击失败会抛异常，由框架标记节点失败）。"""
    x, y = coords.get(name)
    context.tasker.controller.post_click(x, y).wait()


def _input_text(context: Context, text: str) -> bool:
    """输入文本：优先走控制器（后台窗口也能输入），失败再退回剪贴板。"""
    controller = context.tasker.controller
    post_input_text = getattr(controller, "post_input_text", None)
    if post_input_text is not None:
        try:
            job = post_input_text(text)
            wait = getattr(job, "wait", None)
            if wait is not None:
                wait()
            return True
        except Exception as exc:  # noqa: BLE001 - 各 maafw 版本异常类型不统一
            print(f"[input_text] 控制器文本输入失败: {exc}")
    else:
        print("[input_text] 当前 maafw 没有 post_input_text，改用剪贴板兜底")

    return _clipboard_input_text(text)


def _clipboard_input_text(text: str) -> bool:
    """兜底方案：写剪贴板 + 全局 Ctrl+V。

    keybd_event 发给的是当前前台窗口，游戏没焦点时可能输入到别的程序里，
    所以只作为兜底，不作为主路径。
    """
    if not hasattr(ctypes, "windll"):
        print("[input_text] 非 Windows 环境，无法兜底输入")
        return False
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Set-Clipboard -Value '{text}'"],
            check=False,
        )
    except OSError as exc:
        print(f"[input_text] 写入剪贴板失败: {exc}")
        return False

    time.sleep(0.3)
    user32 = ctypes.windll.user32
    user32.keybd_event(0x11, 0, 0, 0)   # Ctrl down
    user32.keybd_event(0x56, 0, 0, 0)   # V down
    user32.keybd_event(0x56, 0, 2, 0)   # V up
    user32.keybd_event(0x11, 0, 2, 0)   # Ctrl up
    return True


# =============================================
# 任务状态（模块级；每次 CampaignInit 全量重置）
# =============================================
_campaign_state = {
    "mode": "phantom",        # phantom=幻灵挑战, normal=普通挑战
    "formation_index": 1,     # 1~10
}

_challenge_scope = "both"     # both / phantom / normal
_retry_limit = 0              # 0=不重试, 1~5=次数, -1=无限
_retry_count = 0
_recover_count = 0
HELP_CHAT_ENABLED = False     # 是否开启「救救孩子」，默认关闭
_RES_SUFFIX = ""              # ""=720x1280 与 550x978（归一化后共用）, "_1080"=1920x1080


def _entry_node(mode: str) -> str:
    """当前模式下该进的入口节点（带分辨率后缀）"""
    return _task("CampaignPhantomEntry") if mode == "phantom" else _task("CampaignNormalEntry")


def _goto_help_or_stop(context: Context, node_name: str):
    """彻底没辙了：开了求助就退回聊天界面发求救，否则停到终止节点。"""
    if HELP_CHAT_ENABLED:
        for _ in range(2):
            _click(context, "BACK_BUTTON")
            time.sleep(WAIT_SHORT)
        context.override_next(node_name, [_task("CampaignHelpChat")])
        return

    print("[Campaign] 未开启求助，直接停止")
    context.override_next(node_name, [STOP_NODE])


# =============================================
# 自定义动作
# =============================================

@AgentServer.custom_action("CampaignInit")
class CampaignInit(CustomAction):
    """初始化：读取挑战类型/分辨率/重试次数，设置初始模式与入口。"""

    def run(self, context, argv):
        global HELP_CHAT_ENABLED, _RES_SUFFIX, _challenge_scope
        global _retry_limit, _retry_count, _recover_count

        # agent 进程常驻，这里必须把状态全部重置，避免上一轮的值残留到这一轮
        _campaign_state["formation_index"] = 1
        _retry_count = 0
        _recover_count = 0
        _RES_SUFFIX = ""

        # 参数存放在 AutoCampaign 节点的 attach 扩展字段中。
        # attach 在多次 pipeline_override 时用 dict merge 累积合并，不会像顶层字段那样被丢弃，
        # 也不会像 custom_action_param 那样被整体覆盖。
        data = context.get_node_data("AutoCampaign") or {}
        attach = data.get("attach", {}) or {}

        HELP_CHAT_ENABLED = str(attach.get("send_help", "false")).strip().lower() == "true"
        if HELP_CHAT_ENABLED:
            print("[CampaignInit] 已开启「救救孩子」")

        raw_scope = attach.get("challenge", "both")
        _challenge_scope = campaign_state.normalize_scope(raw_scope)
        if _challenge_scope != str(raw_scope).strip().lower():
            print(f"[CampaignInit] 未知挑战类型: {raw_scope}, 回退 both")

        _campaign_state["mode"] = campaign_state.initial_mode(_challenge_scope)

        _retry_limit = campaign_state.parse_retry_limit(attach.get("retry", "0"))

        # 读取全局分辨率选项，切换坐标 & task 后缀
        res_key = str(attach.get("resolution", "portrait"))
        coords.set_resolution_by_key(res_key)
        _RES_SUFFIX = coords.suffix_for(res_key)

        # 截图归一化：竖屏分辨率统一缩放到长边 1280，也就是 720×1280。
        # 这样识别全部在 720 基准上做，点击坐标由框架换算回真实分辨率，
        # 一套模板/一套坐标就能覆盖 720×1280 与 550×978（550×978 长边 978
        # → ×1.3088 → 720×1280，比例 0.56237 与 0.5625 只差 0.02%）。
        # 横屏 1920×1080 不能这样归一（长边归一后是 1280×720，而游戏内容
        # 是竖屏 letterbox 在中间，模板对不上），仍沿用原来的"原尺寸截图"。
        try:
            if _RES_SUFFIX == "_1080":
                context.tasker.controller.set_screenshot_use_raw_size(True)
                print("[CampaignInit] 已设置截图使用原始尺寸 (raw_size=true)")
            else:
                context.tasker.controller.set_screenshot_target_long_side(1280)
                print("[CampaignInit] 已设置截图长边缩放为 1280")
        except Exception as exc:  # noqa: BLE001 - 老版本 maafw 没有这些接口
            print(f"[CampaignInit] 设置截图缩放失败: {exc}")

        _update_try_formation(context, 1, _campaign_state["mode"])

        entry = _entry_node(_campaign_state["mode"])

        # 720 / 550（归一化后共用 720）与 1080 三套都有「先锋关卡」入口模板，
        # 所以两种起始页面统一用候选列表：主界面 → town 命中 → 点它进关卡页 →
        # 它自己的 next 走 entry；已经在关卡页 → town 不命中，框架在同一轮里试 entry。
        # 注意：不能指望 TownEntry 识别失败后走它自己的 on_error——经过 next 进入的节点
        # 识别失败只会让框架重试整个候选列表，直到父节点超时（实测 20 秒毫无反应）。
        # entry 本身已经带分辨率后缀（_entry_node 里走过 _task），这里不能再套 _task。
        # 直接拼后缀，不经过 _task——_task 只加档位/形态之类的修饰，
        # 拼错名字会让框架报 "invalid node id" 而不是报"模板找不到"。
        town = "CampaignTownEntry" + _RES_SUFFIX
        # 名字一旦拼错，框架会把不存在的候选**静默丢掉**，日志里只剩
        # [list=[{... CampaignPhantomEntry_1080}]]，看起来像"没反应"。
        # 所以把实际用的名字打到 interface 日志里，出问题时一眼能对上。
        print(f"[CampaignInit] 候选节点={[town, entry]} 后缀={_RES_SUFFIX!r}")
        # TownEntry 的重试节点也要指向同一个入口，否则普通模式会串到幻灵去。
        # Retry2 是重试链的尾巴，失败后要落到「下一屏」而不是 CampaignRecover：
        # 点成功后「先锋关卡」按钮就没了，重试识别必然失败，此时说明已经进了关卡页。
        context.override_pipeline({
            town: {"next": [entry]},
            f"{town}Retry1": {"next": [entry]},
            f"{town}Retry2": {
                "next": [entry],
                "on_error": [entry],
            },
        })
        context.override_next(argv.node_name, [town, entry])

        print(
            f"[CampaignInit] 分辨率={res_key}（工作空间 {coords.get_current_resolution()[0]}x{coords.get_current_resolution()[1]}）"
            f" 挑战类型={_challenge_scope} 模式={_campaign_state['mode']}"
            f" 重试上限={_retry_limit} 求助={HELP_CHAT_ENABLED} 入口={entry}"
        )
        return True


@AgentServer.custom_action("CampaignFormationSelect")
class CampaignFormationSelect(CustomAction):
    """在推荐阵容界面，点 N-1 次右箭头翻到目标阵容页"""

    def run(self, context, argv):
        try:
            index = int(_get_param(argv, "formation_index", "1"))
        except (ValueError, TypeError):
            index = 1

        if index < 1 or index > campaign_state.MAX_FORMATION_INDEX:
            return False

        # 单次点击间隔压到 0.4s：翻到第 10 个阵容时 9 次点击约 4.1s，
        # 仍在 agent 自定义动作的 5 秒响应超时之内
        for _ in range(index - 1):
            _click(context, "RIGHT_ARROW")
            time.sleep(0.4)
        return True


@AgentServer.custom_action("CampaignResetFormation")
class CampaignResetFormation(CustomAction):
    """胜利：重置阵容 → 等结算走完 → 路由回当前模式入口"""

    def run(self, context, argv):
        global _recover_count

        _recover_count = 0  # 过一次关就恢复恢复额度
        _campaign_state["formation_index"] = 1
        mode = _campaign_state["mode"]
        _update_try_formation(context, 1, mode)

        # 不再盲点 NEXT_BUTTON：旧坐标 (494,1210) 在当前版本的结算页上不是「下一关」，
        # 点下去会把人踢回主页面。720p 下改由 VictoryChallenge 识别结算页右下角的
        # 「挑战」按钮（模板 victory_challenge_720p.png）后点它，直接进下一关。
        #
        # 注意：等结算走完的 6 秒放在 HandleVictory 节点的 post_delay 里，不能在这里 sleep——
        # agent 侧自定义动作有 5 秒响应超时（Transceiver timeout_=5000ms），
        # 超过就会被判 socket is not alive → Node.Action.Failed → Tasker.Task.Failed。
        # 720 / 550 / 1080 三套现在都有「挑战」模板（victory_challenge_*.png），
        # 统一走 VictoryChallenge：识别到结算页那颗绿色「挑战」就点它进下一关。
        # 之前 1080 走的是 _entry_node()——那是**关卡页**的入口模板，结算页上认不出来，
        # 于是父节点 20 秒超时，表现就是「通关后卡住」。
        context.override_next(argv.node_name, [_task("VictoryChallenge")])
        return True


@AgentServer.custom_action("CampaignNextFormation")
class CampaignNextFormation(CustomAction):
    """失败：换阵容 → 幻灵切普通 → 整轮重试 → 求助/停止（决策见 campaign_state）"""

    def run(self, context, argv):
        global _retry_count

        step = campaign_state.plan_after_defeat(
            mode=_campaign_state["mode"],
            scope=_challenge_scope,
            formation_index=_campaign_state["formation_index"],
            retry_limit=_retry_limit,
            retry_count=_retry_count,
        )

        if step.kind == campaign_state.STEP_NEXT_FORMATION:
            _campaign_state["formation_index"] = step.formation
            _update_try_formation(context, step.formation, step.mode)
            context.override_next(argv.node_name, [_task("BattleRetry")])
            print(f"[CampaignNextFormation] 换阵容 {step.formation}（模式={step.mode}）")
            return True

        if step.kind == campaign_state.STEP_SWITCH_MODE:
            _click(context, "BACK_BUTTON")
            time.sleep(WAIT_MEDIUM)
            _campaign_state["mode"] = step.mode
            _campaign_state["formation_index"] = step.formation
            _update_try_formation(context, step.formation, step.mode)
            context.override_next(argv.node_name, [_entry_node(step.mode)])
            print("[CampaignNextFormation] 幻灵全部失败，切换到普通关卡")
            return True

        if step.kind == campaign_state.STEP_RETRY:
            _retry_count = step.retry
            if _retry_limit == -1:
                print(f"[CampaignNextFormation] 全部失败，从头重试（第 {step.retry} 次，无限）")
            else:
                print(f"[CampaignNextFormation] 全部失败，从头重试（第 {step.retry}/{_retry_limit} 次）")
            _click(context, "BACK_BUTTON")
            time.sleep(WAIT_MEDIUM)
            _campaign_state["mode"] = step.mode
            _campaign_state["formation_index"] = step.formation
            _update_try_formation(context, step.formation, step.mode)
            context.override_next(argv.node_name, [_entry_node(step.mode)])
            return True

        # 真的没辙了
        print(
            "[CampaignNextFormation] 全部失败"
            f" mode={_campaign_state['mode']} scope={_challenge_scope}"
            f" 重试={_retry_count}/{_retry_limit} 求助={HELP_CHAT_ENABLED}"
        )
        _goto_help_or_stop(context, argv.node_name)
        return True


@AgentServer.custom_action("CampaignRecover")
class CampaignRecover(CustomAction):
    """关键节点失败（点的位置不对、识别不到）后的兜底：点返回、重新进关卡。

    没有识别能力时无法判断当前在哪个界面，所以只做最保守的"退一步再重进"，
    并用 _recover_count 限制次数，避免反复失败时原地打转。
    """

    def run(self, context, argv):
        global _recover_count

        if _recover_count >= RECOVER_LIMIT:
            print(f"[CampaignRecover] 已恢复 {_recover_count} 次仍失败，放弃本轮")
            _goto_help_or_stop(context, argv.node_name)
            return True

        _recover_count += 1
        print(f"[CampaignRecover] 第 {_recover_count}/{RECOVER_LIMIT} 次恢复：点返回后重新进入")

        _click(context, "BACK_BUTTON")
        time.sleep(WAIT_MEDIUM)

        mode = _campaign_state["mode"]
        _campaign_state["formation_index"] = 1
        _update_try_formation(context, 1, mode)
        context.override_next(argv.node_name, [_entry_node(mode)])
        return True


@AgentServer.custom_action("CampaignSendHelp")
class CampaignSendHelp(CustomAction):
    """在工会聊天发送「救救孩子」：点击输入框 → 输入文本 → 点击发送"""

    def run(self, context, argv):
        _click(context, "HELP_INPUT")
        time.sleep(0.8)

        if not _input_text(context, HELP_TEXT):
            print("[CampaignSendHelp] 文本输入失败，跳过发送")
            return False

        time.sleep(0.5)
        _click(context, "HELP_SEND")
        time.sleep(0.5)

        print(f"[CampaignSendHelp] 已发送「{HELP_TEXT}」")
        return True


@AgentServer.custom_action("CampaignAbort")
class CampaignAbort(CustomAction):
    """终止节点专用：显式让任务失败。

    以前 CampaignStop 是个空节点，任务会以"成功"结束，界面上看不出其实一次都没推过去。
    返回 False 后 MaaFramework 会把整个任务标记为失败。
    """

    def run(self, context, argv):
        print("[CampaignAbort] 全部尝试失败，任务终止")
        return False

