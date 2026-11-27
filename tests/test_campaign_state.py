"""agent 纯逻辑层单元测试（不依赖 MaaFramework、不依赖游戏）。"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))

import campaign_state as cs  # noqa: E402
import coords  # noqa: E402


class RetryLimitTest(unittest.TestCase):
    def test_infinite(self):
        self.assertEqual(cs.parse_retry_limit("infinite"), -1)
        self.assertEqual(cs.parse_retry_limit("INFINITE"), -1)

    def test_negative_means_infinite(self):
        self.assertEqual(cs.parse_retry_limit("-1"), -1)
        self.assertEqual(cs.parse_retry_limit("-9"), -1)

    def test_numbers_are_clamped(self):
        self.assertEqual(cs.parse_retry_limit("0"), 0)
        self.assertEqual(cs.parse_retry_limit("3"), 3)
        self.assertEqual(cs.parse_retry_limit(5), 5)
        self.assertEqual(cs.parse_retry_limit("9"), 5)

    def test_garbage_falls_back_to_zero(self):
        self.assertEqual(cs.parse_retry_limit("abc"), 0)
        self.assertEqual(cs.parse_retry_limit(""), 0)
        self.assertEqual(cs.parse_retry_limit(None), 0)

    def test_whitespace_is_trimmed(self):
        self.assertEqual(cs.parse_retry_limit(" 2 "), 2)


class ScopeTest(unittest.TestCase):
    def test_normalize_scope(self):
        self.assertEqual(cs.normalize_scope("both"), "both")
        self.assertEqual(cs.normalize_scope("PHANTOM"), "phantom")
        self.assertEqual(cs.normalize_scope(" normal "), "normal")
        self.assertEqual(cs.normalize_scope("unknown"), "both")
        self.assertEqual(cs.normalize_scope(None), "both")

    def test_initial_mode(self):
        self.assertEqual(cs.initial_mode("normal"), "normal")
        self.assertEqual(cs.initial_mode("phantom"), "phantom")
        self.assertEqual(cs.initial_mode("both"), "phantom")


class PlanAfterDefeatTest(unittest.TestCase):
    def test_has_more_formations(self):
        step = cs.plan_after_defeat(
            mode="phantom",
            scope="both",
            formation_index=3,
            retry_limit=0,
            retry_count=0,
        )
        self.assertEqual(step.kind, cs.STEP_NEXT_FORMATION)
        self.assertEqual(step.formation, 4)
        self.assertEqual(step.mode, "phantom")

    def test_phantom_exhausted_switches_to_normal(self):
        step = cs.plan_after_defeat(
            mode="phantom",
            scope="both",
            formation_index=cs.MAX_FORMATION_INDEX,
            retry_limit=0,
            retry_count=0,
        )
        self.assertEqual(step.kind, cs.STEP_SWITCH_MODE)
        self.assertEqual(step.mode, "normal")
        self.assertEqual(step.formation, 1)

    def test_all_failed_and_retry_left(self):
        step = cs.plan_after_defeat(
            mode="normal",
            scope="both",
            formation_index=cs.MAX_FORMATION_INDEX,
            retry_limit=2,
            retry_count=0,
        )
        self.assertEqual(step.kind, cs.STEP_RETRY)
        self.assertEqual(step.retry, 1)
        self.assertEqual(step.mode, "phantom")  # both 从头从幻灵开始
        self.assertEqual(step.formation, 1)

    def test_retry_exhausted_gives_up(self):
        step = cs.plan_after_defeat(
            mode="normal",
            scope="both",
            formation_index=cs.MAX_FORMATION_INDEX,
            retry_limit=2,
            retry_count=2,
        )
        self.assertEqual(step.kind, cs.STEP_GIVE_UP)

    def test_infinite_retry_never_gives_up(self):
        step = cs.plan_after_defeat(
            mode="normal",
            scope="normal",
            formation_index=cs.MAX_FORMATION_INDEX,
            retry_limit=-1,
            retry_count=99,
        )
        self.assertEqual(step.kind, cs.STEP_RETRY)
        self.assertEqual(step.retry, 100)
        self.assertEqual(step.mode, "normal")

    def test_phantom_only_scope_never_switches(self):
        step = cs.plan_after_defeat(
            mode="phantom",
            scope="phantom",
            formation_index=cs.MAX_FORMATION_INDEX,
            retry_limit=0,
            retry_count=0,
        )
        self.assertEqual(step.kind, cs.STEP_GIVE_UP)


class CoordsTest(unittest.TestCase):
    def setUp(self):
        coords.set_orientation("portrait")

    tearDown = setUp

    def test_suffix_mapping(self):
        self.assertEqual(coords.suffix_for("720x1280"), "")
        # 550×978 的截图会被归一化到 720×1280，所以共用 "" 那套节点
        self.assertEqual(coords.suffix_for("550x978"), "")
        self.assertEqual(coords.suffix_for("1920x1080"), "_1080")
        self.assertEqual(coords.suffix_for("1024x768"), "")

    def test_switch_known_resolution(self):
        self.assertTrue(coords.set_resolution_by_key("550x978"))
        # 归一化之后工作空间仍是 720×1280，坐标取 720 那一套
        self.assertEqual(coords.get_current_resolution(), (720, 1280))
        self.assertEqual(coords.get("BACK_BUTTON"), (65, 1211))

    def test_unknown_resolution_falls_back(self):
        self.assertFalse(coords.set_resolution_by_key("1280x720"))
        self.assertEqual(coords.get_current_resolution(), coords.DEFAULT_RESOLUTION)
        self.assertEqual(coords.get("BACK_BUTTON"), (65, 1211))

    def test_bad_key_falls_back(self):
        self.assertFalse(coords.set_resolution_by_key("not-a-resolution"))
        self.assertEqual(coords.get_current_resolution(), coords.DEFAULT_RESOLUTION)


if __name__ == "__main__":
    unittest.main()
