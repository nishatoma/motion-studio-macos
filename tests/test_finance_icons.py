"""Explicit icon prompts should bypass the storyboard title generator."""

import unittest
from unittest.mock import patch

import app


class FinanceIconTest(unittest.TestCase):
    def test_both_prompts_render_as_directed_icons(self):
        prompts = {
            "Create a transparent savings jar. One coin fades away, leaving it empty. Show $0.":
                "empty_savings_jar",
            "A credit card taps a small payment terminal once, transparent background.":
                "credit_card_tap",
        }
        with patch.object(app, "generate_storyboard", side_effect=AssertionError("Storyboard must not run")), \
             patch.object(app, "local_json", side_effect=AssertionError("Ollama must not run")):
            for prompt, template in prompts.items():
                for quality in ("polished", "fast"):
                    with self.subTest(prompt=prompt, quality=quality):
                        plan = app.generate_plan(prompt, "", quality)
                        self.assertEqual(plan["template"], template)
                        self.assertEqual(app.validated_plan(plan)["template"], template)

    def test_unrelated_prompts_do_not_become_icons(self):
        self.assertIsNone(app.finance_icon_plan("A credit card debt graph"))
        self.assertIsNone(app.finance_icon_plan("A jar filled with coffee beans"))


if __name__ == "__main__":
    unittest.main()
