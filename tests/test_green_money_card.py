"""A literal money card request must not become a title storyboard."""

import unittest
from unittest.mock import patch

import app


class GreenMoneyCardTest(unittest.TestCase):
    def test_single_card_skips_ollama_at_each_planning_quality(self):
        prompt = ('Create exactly one graphic: a solid emerald-green rounded rectangle '
                  'with the exact white text "$500" centered inside it. '
                  'Add a soft green bloom on a transparent background.')
        with patch.object(app, "generate_storyboard", side_effect=AssertionError("Ollama should not run")), \
             patch.object(app, "local_json", side_effect=AssertionError("Ollama should not run")):
            for quality in ("polished", "fast"):
                plan = app.generate_plan(prompt, "qwen3.6:27b", quality)
                self.assertEqual(plan["template"], "green_money_card")
                self.assertEqual(app.validated_plan(plan), plan)

    def test_other_finance_prompts_do_not_trigger_the_card(self):
        self.assertIsNone(app.green_money_card_plan("Put $500 in a green savings graph"))
        self.assertIsNone(app.green_money_card_plan("Show a green card for $500 and $1000"))


if __name__ == "__main__":
    unittest.main()
