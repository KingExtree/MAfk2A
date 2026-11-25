"""
MAFK2A 自定义识别
"""
from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context


@AgentServer.custom_recognition("CheckBattleResult")
class CheckBattleResult(CustomRecognition):
    """
    战斗结束后判断胜负。
    先检查胜利画面特征，再检查失败画面特征。
    返回结果中 detail 为 "victory" 或 "defeat"。
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:

        # 先检查胜利标识
        victory = context.run_recognition("VictoryIndicator", argv.image)
        print(f"[CheckBattleResult] VictoryIndicator box={victory.box}, detail={victory.detail}")
        if victory.box:
            print("[CheckBattleResult] 胜利!")
            # 路由到胜利处理
            context.override_next(argv.node_name, ["HandleVictory"])
            return CustomRecognition.AnalyzeResult(
                box=victory.box, detail="victory"
            )

        # 再检查失败标识
        defeat = context.run_recognition("DefeatIndicator", argv.image)
        print(f"[CheckBattleResult] DefeatIndicator box={defeat.box}, detail={defeat.detail}")
        if defeat.box:
            print("[CheckBattleResult] 失败!")
            context.override_next(argv.node_name, ["HandleDefeat"])
            return CustomRecognition.AnalyzeResult(
                box=defeat.box, detail="defeat"
            )

        # 都没识别到，继续等待
        print("[CheckBattleResult] 战斗中...继续等待")
        return CustomRecognition.AnalyzeResult(
            box=(0, 0, 0, 0), detail="waiting"
        )
