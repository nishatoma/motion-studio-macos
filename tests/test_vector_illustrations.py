"""Object requests use bounded vector parts and explicit motion instead of titles."""

import json
import unittest
from unittest.mock import patch

import app


SAVINGS_PLAN = {"beats": [
    {"duration": 0.45, "items": [
        {"type": "path", "id": "jar", "position": [0, 0],
         "points": [[-1, 1], [-1, -0.8], [0, -1], [1, -0.8], [1, 1]],
         "color": "#F4F9FB", "stroke_width": 5},
        {"type": "ellipse", "id": "coin", "position": [0, -0.5],
         "size": [0.6, 0.4], "fill_opacity": 0.8, "color": "#FFB56B"},
        {"type": "line", "position": [0, 1.1], "size": [2.2, 0.1]}]},
    {"duration": 0.45, "items": [{"type": "number", "text": "$0", "position": [0, -1.6]}],
     "actions": [{"target": "coin", "type": "fade_out"}]},
]}


class VectorIllustrationTest(unittest.TestCase):
    def test_polished_object_prompt_uses_vector_planner(self):
        prompt = "Draw an empty savings jar. One gold coin fades away. Show $0."
        with patch.object(app, "local_json", return_value={"response": json.dumps(SAVINGS_PLAN)}), \
             patch.object(app, "generate_storyboard", side_effect=AssertionError("No storyboard")):
            plan = app.generate_plan(prompt, "qwen3.6:27b", "polished")
        self.assertIn("vector illustration", plan["_source"])
        self.assertEqual(plan["beats"][1]["actions"], [{"target": "coin", "type": "fade_out"}])
        self.assertEqual(plan["beats"][0]["items"][0]["points"][0], [-1.0, 1.0])

    def test_card_parts_can_move_and_keep_fill_and_glow(self):
        card = {"beats": [
            {"duration": 0.5, "items": [
                {"type": "polygon", "id": "card", "position": [-1, 0],
                 "points": [[-1, -0.6], [1, -0.6], [1, 0.6], [-1, 0.6]],
                 "fill_color": "#FFB56B", "fill_opacity": 0.25, "glow": True},
                {"type": "ring", "size": [0.5, 0.5], "position": [0, 0]},
                {"type": "rectangle", "size": [0.8, 1.3], "position": [1.5, 0]}]},
            {"duration": 0.5, "items": [], "actions": [
                {"target": "card", "type": "shift", "position": [1.0, 0]}]},
        ]}
        with patch.object(app, "local_json", return_value={"response": json.dumps(card)}):
            plan = app.generate_plan("A credit card taps a payment terminal", "qwen3.6:27b")
        self.assertTrue(plan["beats"][0]["items"][0]["glow"])
        self.assertEqual(plan["beats"][0]["items"][0]["fill_opacity"], 0.25)
        self.assertEqual(plan["beats"][1]["actions"][0]["position"], [1.0, 0.0])

    def test_invalid_motion_and_geometry_are_rejected(self):
        missing = {"beats": [{"items": [], "actions": [{"target": "ghost", "type": "fade_out"}]}]}
        with self.assertRaisesRegex(ValueError, "earlier beat"):
            app.validate_spec(missing)
        bad_points = {"beats": [{"items": [{"type": "polygon", "points": [[0, 0], [1, 0]]}]}]}
        with self.assertRaisesRegex(ValueError, "3 to 16"):
            app.validate_spec(bad_points)

    def test_no_unrequested_titles_and_existing_fixed_plan_rerenders(self):
        wrong = {"beats": [{"items": [
            {"type": "path", "points": [[0, 0], [1, 1]]},
            {"type": "ellipse", "size": [1, 1]},
            {"type": "line", "size": [1, 1]},
            {"type": "title", "text": "The Empty Jar"}]}]}
        with patch.object(app, "local_json", return_value={"response": json.dumps(wrong)}):
            with self.assertRaisesRegex(RuntimeError, "No generated title"):
                app.generate_illustration("Draw a jar with no text", "qwen3.6:27b")
        old = {"template": "empty_savings_jar"}
        self.assertEqual(app.validated_plan(old)["template"], "empty_savings_jar")


if __name__ == "__main__":
    unittest.main()
