"""Motion Canvas handoff is explicit, bounded, and independent of Manim."""

import io
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import app
import motion_canvas_export


VECTOR = {"beats": [
    {"duration": 0.6, "items": [
        {"type": "polygon", "id": "card", "position": [-1, 0],
         "points": [[-1, -0.6], [1, -0.6], [1, 0.6], [-1, 0.6]],
         "color": "#FFB56B", "fill_opacity": 0.3, "glow": True},
        {"type": "ring", "position": [1, 0], "size": [0.5, 0.5]},
        {"type": "path", "position": [0, 1], "points": [[-1, 0], [0, 0.2], [1, 0]]}]},
    {"duration": 0.5, "items": [], "actions": [
        {"target": "card", "type": "move_to", "position": [1, 0]}]},
]}


class MotionCanvasExportTest(unittest.TestCase):
    def test_graphics_tab_is_first_and_default(self):
        html = (app.WEB / "index.html").read_text()
        self.assertLess(html.index('id="graphicsTab"'), html.index('id="abstractTab"'))
        self.assertIn('mode="graphics"', html)
        self.assertIn('id="abstractFields" class="mode-fields" hidden', html)

    def test_project_is_structured_and_does_not_embed_executable_prompt(self):
        plan = app.validate_spec(VECTOR)
        plan["_source"] = "a prompt with `malicious();`"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "project.zip"
            motion_canvas_export.write_project(plan, path)
            with ZipFile(path) as archive:
                self.assertIn("motion-canvas-project/src/scenes/generated.tsx", archive.namelist())
                self.assertIn("motion-canvas-project/src/project.ts", archive.namelist())
                source = archive.read("motion-canvas-project/src/scenes/generated.tsx").decode()
                data = json.loads(archive.read("motion-canvas-project/src/scene.json"))
                self.assertNotIn("malicious();", source)
                self.assertNotIn("malicious();", json.dumps(data))
                self.assertEqual(data["beats"][1]["actions"][0]["target"], "card")
                self.assertIn("new Path", source)
                self.assertIn("shadowBlur", source)

    def test_templates_and_graphs_are_not_misrepresented_as_supported(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "project.zip"
            with self.assertRaisesRegex(ValueError, "vector beats"):
                motion_canvas_export.write_project({"template": "awareness_strike"}, path)
            with self.assertRaisesRegex(ValueError, "not graphs"):
                motion_canvas_export.write_project({"beats": [{"items": [{"type": "graph"}]}]}, path)

    def test_project_job_api_returns_zip_not_a_video(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, "JOBS_DIR", Path(folder)), \
                patch.object(app, "ollama_models", return_value=["test-model"]), \
                patch.object(app, "generate_illustration", return_value={**app.validate_spec(VECTOR), "_source": "test"}):
            server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                bad = urllib.request.Request(base + "/api/motion-canvas/jobs",
                                             data=json.dumps({"prompt": "a growth graph", "model": "test-model"}).encode(),
                                             headers={"Content-Type": "application/json"})
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(bad)
                self.assertEqual(error.exception.code, 400)
                request = urllib.request.Request(base + "/api/motion-canvas/jobs",
                                                 data=json.dumps({"prompt": "Draw a credit card tapping a terminal", "model": "test-model"}).encode(),
                                                 headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request) as response:
                    job_id = json.load(response)["id"]
                for _ in range(30):
                    with urllib.request.urlopen(base + "/api/jobs/" + job_id) as response:
                        job = json.load(response)
                    if job["status"] in {"complete", "error"}:
                        break
                    time.sleep(0.05)
                self.assertEqual(job["status"], "complete", job.get("details"))
                self.assertEqual(job["kind"], "motion_canvas")
                self.assertNotIn("video", job)
                with urllib.request.urlopen(base + job["download"]) as response:
                    self.assertEqual(response.headers["Content-Type"], "application/zip")
                    with ZipFile(io.BytesIO(response.read())) as archive:
                        self.assertIn("motion-canvas-project/README.md", archive.namelist())
            finally:
                app.JOBS.pop(job_id, None)
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
