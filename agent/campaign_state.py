"""纯逻辑层：与 MaaFramework 无关，可以被单元测试直接导入。

这里只放"决策"（解析选项、根据失败次数决定下一步），不放任何副作用
（点击、截图、override_pipeline 一律留在 my_action.py）。
这样任务状态机可以脱离游戏和框架单独验证。
"""

from typing import NamedTuple

# 阵容上限：TryFormation 只准备了 1~10 号阵容
MAX_FORMATION_INDEX = 10

# 合法的挑战类型
VALID_SCOPES = ("both", "phantom", "normal")

# 失败后的下一步类型
STEP_NEXT_FORMATION = "next_formation"  # 还有阵容可试，换下一个
STEP_SWITCH_MODE = "switch_mode"        # 幻灵全败且「都打」，切普通关卡
STEP_RETRY = "retry"                    # 整轮重来
STEP_GIVE_UP = "give_up"                # 求助或停止


class Step(NamedTuple):
    """plan_after_defeat 的返回值，只描述意图，由调用方执行。"""

    kind: str
    mode: str = ""
    formation: int = 1
    retry: int = 0


def normalize_scope(value) -> str:
    """把挑战类型选项规范成 VALID_SCOPES 里的值，非法值回退 both。"""
    scope = str(value).strip().lower()
    return scope if scope in VALID_SCOPES else "both"


def initial_mode(scope: str) -> str:
    """整轮开始时先打哪种关卡：只打普通时从普通开始，其余从幻灵开始。"""
    return "normal" if normalize_scope(scope) == "normal" else "phantom"


def parse_retry_limit(value) -> int:
    """解析重试次数：infinite -> -1（无限），数字 -> 0~5，其他 -> 0。"""
    text = str(value).strip().lower()
    if text == "infinite":
        return -1
    try:
        count = int(text)
    except ValueError:
        return 0
    if count < 0:
        return -1
    return max(0, min(5, count))


def plan_after_defeat(
    *,
    mode: str,
    scope: str,
    formation_index: int,
    retry_limit: int,
    retry_count: int,
) -> Step:
    """一次战斗失败后该做什么。

    优先级：换阵容 > 幻灵切普通 > 整轮重试 > 放弃（求助/停止）。
    """
    scope = normalize_scope(scope)
    next_index = formation_index + 1

    if next_index <= MAX_FORMATION_INDEX:
        return Step(STEP_NEXT_FORMATION, mode=mode, formation=next_index)

    if mode == "phantom" and scope == "both":
        return Step(STEP_SWITCH_MODE, mode="normal", formation=1)

    if retry_limit == -1 or retry_count < retry_limit:
        return Step(
            STEP_RETRY,
            mode=initial_mode(scope),
            formation=1,
            retry=retry_count + 1,
        )

    return Step(STEP_GIVE_UP)
