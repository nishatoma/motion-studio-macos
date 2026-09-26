"""The explicit financial-stages prompt uses the directed renderer, not Ollama."""

import unittest
from unittest.mock import patch

import app


class FinancialStagesTest(unittest.TestCase):
    def test_prompt_selects_fixed_scene_without_model(self):
        prompt = "Financial stages arrow. Four fixed cards stacked vertically."
        with patch.object(app, "generate_storyboard", side_effect=AssertionError("Ollama should not run")), \
             patch.object(app, "local_json", side_effect=AssertionError("Ollama should not run")):
            for quality in ("polished", "fast"):
                plan = app.generate_plan(prompt, "", quality)
                self.assertEqual(plan["template"], "financial_stages")
                self.assertEqual(app.validated_plan(plan), plan)

    def test_other_prompts_do_not_select_template(self):
        self.assertIsNone(app.financial_stages_plan("Show four stages of investing"))


if __name__ == "__main__":
    unittest.main()
