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

    def test_truncated_json_retries_with_more_room_and_a_compact_plan(self):
        responses = [
            {"response": '{"beats":[{"items":[', "done_reason": "length"},
            {"response": json.dumps(SAVINGS_PLAN), "done_reason": "stop"},
        ]
        with patch.object(app, "local_json", side_effect=responses) as call:
            plan = app.generate_illustration("Draw a jar and fade a coin. Show $0.", "qwen3.6:27b")
        self.assertIn("vector illustration", plan["_source"])
        self.assertEqual(call.call_count, 2)
        self.assertEqual(call.call_args_list[0].args[1]["options"]["num_predict"], 6000)
        self.assertIn("output limit", call.call_args_list[1].args[1]["prompt"])

    def test_malformed_json_retries_before_reporting_error(self):
        with patch.object(app, "local_json", side_effect=[
            {"response": '{"beats": [}', "done_reason": "stop"},
            {"response": json.dumps(SAVINGS_PLAN), "done_reason": "stop"},
        ]) as call:
            app.generate_illustration("Draw a jar and fade a coin. Show $0.", "qwen3.6:27b")
        self.assertEqual(call.call_count, 2)

    def test_empty_model_text_is_discarded_without_losing_requested_labels(self):
        buffer_plan = {"beats": [
            {"duration": 0.7, "items": [
                {"type": "path", "id": "buffer", "points": [[-1, 0], [0, -0.5], [1, 0]]},
                {"type": "rectangle", "id": "deposit", "position": [-1, 0], "size": [1, 0.4]},
                {"type": "ring", "position": [1, 0], "size": [0.5, 0.5]},
                {"type": "text", "id": "unused", "text": "  "},
                {"type": "number", "text": "$500"}]},
            {"duration": 0.7, "items": [
                {"type": "text", "text": "1 MONTH OF LIVING EXPENSES"}],
             "actions": [{"target": "unused", "type": "fade_out"},
                         {"target": "deposit", "type": "move_to", "position": [0, 0]}]},
        ]}
        prompt = ("Draw a cash buffer. Show $500 contributions and label the goal "
                  "1 month of living expenses. Three $500 deposits must not imply "
                  "that $1,500 covers everyone.")
        with patch.object(app, "local_json", return_value={"response": json.dumps(buffer_plan)}) as call:
            plan = app.generate_illustration(prompt, "qwen3.6:27b")
        self.assertEqual(call.call_count, 1)
        self.assertFalse(any(item.get("id") == "unused" for beat in plan["beats"] for item in beat["items"]))
        self.assertEqual(plan["beats"][1]["actions"],
                         [{"target": "deposit", "type": "move_to", "position": [0.0, 0.0]}])
        self.assertEqual(app.requested_illustration_amounts(prompt), {"$500"})

    def test_required_goal_or_prohibited_amount_cannot_be_dropped(self):
        plan = json.loads(json.dumps(SAVINGS_PLAN))
        prompt = "Draw a jar; show $0 and label 1 MONTH OF LIVING EXPENSES. Do not show $1,500."
        with patch.object(app, "local_json", return_value={"response": json.dumps(plan)}):
            with self.assertRaisesRegex(RuntimeError, "goal label"):
                app.generate_illustration(prompt, "qwen3.6:27b")
        plan["beats"][1]["items"].append({"type": "text", "text": "1 MONTH OF LIVING EXPENSES"})
        plan["beats"][1]["items"].append({"type": "number", "text": "$1,500"})
        with patch.object(app, "local_json", return_value={"response": json.dumps(plan)}):
            with self.assertRaisesRegex(RuntimeError, "explicitly excluded"):
                app.generate_illustration(prompt, "qwen3.6:27b")

    def test_missing_requested_labels_fill_empty_number_and_text_slots(self):
        plan = json.loads(json.dumps(SAVINGS_PLAN))
        plan["beats"][1]["items"] = [
            {"type": "number", "text": "", "position": [-1, 0]},
            {"type": "text", "text": "", "position": [1, 0]},
        ]
        prompt = ("Draw a cash buffer. Show $500 contributions and label the goal "
                  "1 month of living expenses. Do not show $1,500.")
        with patch.object(app, "local_json", return_value={"response": json.dumps(plan)}) as call:
            result = app.generate_illustration(prompt, "qwen3.6:27b")
        self.assertEqual(call.call_count, 1)
        self.assertEqual([item["text"] for item in result["beats"][1]["items"]],
                         ["$500", "1 MONTH OF LIVING EXPENSES"])

    def test_new_object_action_is_delayed_and_repeated_actions_stay_sequential(self):
        plan = {"beats": [
            {"duration": 1.8, "items": [
                {"type": "path", "id": "coin", "points": [[-1, 0], [0, 1], [1, 0]]},
                {"type": "ellipse", "size": [1, 1]},
                {"type": "rectangle", "size": [2, 1]}],
             "actions": [
                 {"target": "coin", "type": "move_to", "position": [1, 0]},
                 {"target": "coin", "type": "scale", "factor": 0.5}]},
        ]}
        with patch.object(app, "local_json", return_value={"response": json.dumps(plan)}) as call:
            result = app.generate_illustration("Draw a coin and move it to the right.", "qwen3.6:27b")
        self.assertEqual(call.call_count, 1)
        self.assertEqual([len(beat["actions"]) for beat in result["beats"]], [0, 1, 1])
        self.assertEqual([beat["actions"][0]["type"] for beat in result["beats"][1:]],
                         ["move_to", "scale"])
        self.assertAlmostEqual(sum(beat["duration"] for beat in result["beats"]), 1.8)

    def test_unknown_action_target_is_reported_with_beat_and_id(self):
        plan = json.loads(json.dumps(SAVINGS_PLAN))
        plan["beats"][1]["actions"][0]["target"] = "missing_coin"
        with patch.object(app, "local_json", return_value={"response": json.dumps(plan)}) as call:
            with self.assertRaisesRegex(RuntimeError, "Beat 2: action target 'missing_coin'"):
                app.generate_illustration("Draw a jar and fade a coin. Show $0.", "qwen3.6:27b")
        self.assertEqual(call.call_count, 3)

    def test_invalid_and_duplicate_ids_repair_action_targets(self):
        plan = {"beats": [
            {"duration": 1.2, "items": [
                {"type": "path", "id": "1 coin", "points": [[-1, 0], [0, 1], [1, 0]]},
                {"type": "ellipse", "id": "1 coin", "position": [1, 0], "size": [1, 1]},
                {"type": "ring", "id": "outer ring", "size": [1.5, 1.5]}],
             "actions": [{"target": "1 coin", "type": "move_to", "position": [2, 0]}]},
            {"duration": 0.8, "items": [],
             "actions": [{"target": "outer ring", "type": "fade_out"}]},
        ]}
        with patch.object(app, "local_json", return_value={"response": json.dumps(plan)}) as call:
            result = app.generate_illustration("Draw a coin and move it; fade the ring.", "qwen3.6:27b")
        self.assertEqual(call.call_count, 1)
        ids = [item["id"] for beat in result["beats"] for item in beat["items"]]
        self.assertEqual(ids, ["part_1_coin", "part_1_coin_2", "outer_ring"])
        self.assertEqual(result["beats"][1]["actions"][0]["target"], "part_1_coin_2")
        self.assertEqual(result["beats"][2]["actions"][0]["target"], "outer_ring")

    def test_identical_redraw_reuses_object_and_clear_can_reuse_id(self):
        plan = json.loads(json.dumps(SAVINGS_PLAN))
        plan["beats"][1]["items"].append(json.loads(json.dumps(plan["beats"][0]["items"][1])))
        with patch.object(app, "local_json", return_value={"response": json.dumps(plan)}):
            result = app.generate_illustration("Draw a jar and fade a coin. Show $0.", "qwen3.6:27b")
        self.assertEqual([item.get("id") for item in result["beats"][1]["items"]], [None])
        self.assertEqual(result["beats"][1]["actions"][0]["target"], "coin")
        app.validate_spec({"beats": [
            {"items": [{"type": "circle", "id": "coin"}]},
            {"clear_before": True, "items": [{"type": "ring", "id": "coin"}]},
        ]})

    def test_changed_redraw_gets_new_id_and_action_moves_new_object(self):
        plan = json.loads(json.dumps(SAVINGS_PLAN))
        plan["beats"][1]["items"].append({"type": "ellipse", "id": "coin", "position": [2, 0], "size": [0.6, 0.4]})
        plan["beats"][1]["actions"] = [{"target": "coin", "type": "shift", "position": [1, 0]}]
        with patch.object(app, "local_json", return_value={"response": json.dumps(plan)}):
            result = app.generate_illustration("Draw a jar and shift a coin. Show $0.", "qwen3.6:27b")
        self.assertEqual(result["beats"][1]["items"][1]["id"], "coin_2")
        self.assertEqual(result["beats"][2]["actions"][0]["target"], "coin_2")


if __name__ == "__main__":
    unittest.main()
