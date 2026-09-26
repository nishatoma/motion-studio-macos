"""Exact one-word strike-through prompts bypass the open-ended storyboard."""

import unittest
from unittest.mock import patch

import app


class AwarenessStrikeTest(unittest.TestCase):
    def test_user_prompt_selects_directed_scene_without_ollama(self):
        prompt = 'Show the word "awareness" with a red line going through it. Make it a 2 seconds video.'
        with patch.object(app, "generate_storyboard", side_effect=AssertionError("Ollama should not run")), \
             patch.object(app, "local_json", side_effect=AssertionError("Ollama should not run")):
            for quality in ("polished", "fast"):
                plan = app.generate_plan(prompt, "", quality)
                self.assertEqual(plan["template"], "awareness_strike")
                self.assertEqual(app.validated_plan(plan), plan)

    def test_short_trigger_and_unrelated_prompts(self):
        self.assertEqual(app.awareness_strike_plan("Awareness strikethrough")["template"], "awareness_strike")
        self.assertIsNone(app.awareness_strike_plan("Awareness is important"))


if __name__ == "__main__":
    unittest.main()
