"""Windows paths, workflow selection, and local setup authorization."""
import json
import io
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import app
import windows_support
from test_abstract_video import IMAGE, WORKFLOW, multipart


class WindowsSupportTest(unittest.TestCase):
    def test_platform_paths_and_winget_ffmpeg_link(self):
        with tempfile.TemporaryDirectory() as tmp, patch("windows_support.platform.system", return_value="Windows"):
            root = Path(tmp)
            self.assertEqual(windows_support.manim_binary(root), root / ".venv/Scripts/manim.exe")
            with patch.dict(os.environ, {"USERPROFILE": tmp, "LOCALAPPDATA": tmp}), \
                    patch("windows_support.shutil.which", return_value=None):
                self.assertEqual(windows_support.output_dir(), root / "Videos/Nisha Motion Graphics")
                link = root / "Microsoft/WinGet/Links/ffmpeg.exe"
                link.parent.mkdir(parents=True)
                link.touch()
                self.assertEqual(windows_support.ffmpeg_binary(), str(link))

    def test_windows_comfy_auto_discovers_workflow_or_accepts_custom_one(self):
        fields = {"prompt": b"three streams", "image": IMAGE, "backend": b"comfy", "preset": b"workflow"}
        boundary, body = multipart(fields)
        _, _, workflow, preset, backend = app.parse_abstract_request(
            f"multipart/form-data; boundary={boundary}", body)
        self.assertEqual((workflow, preset, backend), (None, "workflow", "comfy"))
        fields["workflow"] = json.dumps(WORKFLOW).encode()
        boundary, body = multipart(fields)
        _, _, workflow, preset, backend = app.parse_abstract_request(f"multipart/form-data; boundary={boundary}", body)
        self.assertEqual((preset, backend), ("workflow", "comfy"))
        self.assertEqual(workflow, WORKFLOW)

    def test_render_invokes_windows_manim_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manim = root / ".venv/Scripts/manim.exe"
            manim.parent.mkdir(parents=True)
            manim.touch()
            job_id = "abc123abc123"
            with patch("windows_support.platform.system", return_value="Windows"), \
                    patch.object(app, "ROOT", root), patch.object(app, "JOBS_DIR", root), \
                    patch.object(app.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "failed")) as run:
                app.JOBS[job_id] = {"id": job_id}
                try:
                    app.render_job(job_id, "", "same scene plan", "preview",
                                   {"template": "storyboard", "scenes": [{"duration": 2.0}]})
                    self.assertEqual(app.JOBS[job_id]["status"], "error")
                    self.assertEqual(run.call_args.args[0][0], str(manim))
                finally:
                    app.JOBS.pop(job_id, None)

    def test_windows_setup_needs_local_host_and_token(self):
        with patch("app.platform.system", return_value="Windows"):
            server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with urllib.request.urlopen(base + "/api/health") as response:
                    health = json.load(response)
                self.assertEqual(health["platform"], "Windows")
                self.assertEqual(health["setup_token"], app.SETUP_TOKEN)
                request = urllib.request.Request(base + "/api/windows/setup", data=b"", method="POST")
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    urllib.request.urlopen(request)
                self.assertEqual(denied.exception.code, 403)
                request.add_header("X-Motion-Studio-Setup", app.SETUP_TOKEN)
                request.add_header("Origin", "https://untrusted.example")
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    urllib.request.urlopen(request)
                self.assertEqual(denied.exception.code, 403)
                request.remove_header("Origin")
                with app.SETUP_LOCK:
                    app.SETUP.update(status="idle", message="idle", log="")
                with patch("app.run_windows_setup") as setup_runner:
                    with urllib.request.urlopen(request) as response:
                        self.assertEqual(response.status, 202)
                    for _ in range(20):
                        if setup_runner.called:
                            break
                        threading.Event().wait(0.01)
                    setup_runner.assert_called_once()
                with urllib.request.urlopen(base + "/api/windows/setup") as response:
                    self.assertEqual(json.load(response)["status"], "running")
            finally:
                with app.SETUP_LOCK:
                    app.SETUP.update(status="idle", message="idle", log="")
                server.shutdown()
                server.server_close()

    def test_windows_setup_reports_process_output_and_failure(self):
        class FakeProcess:
            stdout = io.StringIO("Checking FFmpeg...\nDone.\n")

            def wait(self):
                return 7

        with app.SETUP_LOCK:
            app.SETUP.update(status="running", message="Starting", log="")
        try:
            with patch("app.subprocess.Popen", return_value=FakeProcess()) as popen:
                app.run_windows_setup()
                self.assertEqual(popen.call_args.args[0], windows_support.setup_command(app.ROOT))
            with app.SETUP_LOCK:
                self.assertEqual(app.SETUP["status"], "error")
                self.assertIn("Checking FFmpeg", app.SETUP["log"])
                self.assertIn("code 7", app.SETUP["message"])
        finally:
            with app.SETUP_LOCK:
                app.SETUP.update(status="idle", message="idle", log="")


if __name__ == "__main__":
    unittest.main()
