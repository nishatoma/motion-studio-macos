"""Small local API contract test; no video model download required."""
import json
import tempfile
import threading
import time
import unittest
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import abstract_video
import app


WORKFLOW = {
    "1": {"class_type": "LoadImage", "inputs": {"image": "{{IMAGE}}"}},
    "2": {"class_type": "Text", "inputs": {"text": "{{PROMPT}}"}},
}
MINIMAX = {
    "1": {"class_type": "LoadImage", "inputs": {"image": "old.png"}},
    "2": {"class_type": "ImageScale", "inputs": {"image": ["1", 0], "width": 1344}},
    "3": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
        "first_frame": ["2", 0], "prompt": "old prompt", "duration": 5.0}},
    "4": {"class_type": "SaveVideo", "inputs": {"video": ["3", 0]}},
}
IMAGE = b"\x89PNG\r\n\x1a\n" + b"test data"


class FakeComfy(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def reply(self, value):
        body = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        if self.path == "/upload/image":
            assert IMAGE in body
            self.reply({"name": "uploaded.png"})
        elif self.path == "/prompt":
            planned = json.loads(body)["prompt"]
            assert planned["1"]["inputs"]["image"] == "uploaded.png"
            assert (planned["2"]["inputs"].get("text") == "three streams" or
                    planned["3"]["inputs"].get("prompt") == "three streams")
            if "3" in planned and planned["3"]["class_type"] == "MiniMaxH3ImageToVideo":
                assert planned["3"]["inputs"]["duration"] == 5.0
            self.reply({"prompt_id": "test-id"})

    def do_GET(self):
        if self.path == "/history?max_items=20":
            self.reply({"previous": {"status": {"status_str": "success"},
                                     "prompt": [19, MINIMAX, {"client_id": "abc"}, []]}})
        elif self.path.startswith("/history/"):
            self.reply({"test-id": {"status": {"completed": True}, "outputs": {
                "3": {"videos": [{"filename": "clip.mp4", "type": "output"}]}}}})
        elif self.path.startswith("/view?"):
            movie = b"test mp4 bytes"
            self.send_response(200)
            self.send_header("Content-Length", str(len(movie)))
            self.end_headers()
            self.wfile.write(movie)
        else:
            self.reply({"devices": []})


def multipart(fields):
    boundary = "MotionTest" + uuid.uuid4().hex
    data = b"".join(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        + value + b"\r\n" for name, value in fields.items()
    ) + f"--{boundary}--\r\n".encode()
    return boundary, data


class AbstractVideoTest(unittest.TestCase):
    def test_uses_last_minimax_run_without_json_or_placeholders(self):
        comfy = ThreadingHTTPServer(("127.0.0.1", 0), FakeComfy)
        previous_url, previous_file, previous_dir = (
            abstract_video.COMFYUI_URL, abstract_video.WORKFLOW_FILE, app.JOBS_DIR)
        abstract_video.COMFYUI_URL = f"http://127.0.0.1:{comfy.server_port}"
        threading.Thread(target=comfy.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                app.JOBS_DIR = Path(folder)
                abstract_video.WORKFLOW_FILE = Path(folder) / "saved.json"
                motion = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
                threading.Thread(target=motion.serve_forever, daemon=True).start()
                try:
                    boundary, data = multipart({"prompt": b"three streams", "image": IMAGE,
                                                "backend": b"comfy", "preset": b"workflow"})
                    req = urllib.request.Request(
                        f"http://127.0.0.1:{motion.server_port}/api/abstract/jobs", data=data,
                        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
                    with urllib.request.urlopen(req) as response:
                        job_id = json.load(response)["id"]
                    for _ in range(30):
                        with urllib.request.urlopen(
                                f"http://127.0.0.1:{motion.server_port}/api/jobs/{job_id}") as response:
                            job = json.load(response)
                        if job["status"] in {"complete", "error"}:
                            break
                        time.sleep(0.1)
                    self.assertEqual(job["status"], "complete", job.get("details"))
                    self.assertTrue(abstract_video.WORKFLOW_FILE.is_file())
                    self.assertEqual(json.loads(abstract_video.WORKFLOW_FILE.read_text()), MINIMAX)
                finally:
                    motion.shutdown()
                    motion.server_close()
        finally:
            comfy.shutdown()
            comfy.server_close()
            abstract_video.COMFYUI_URL, abstract_video.WORKFLOW_FILE, app.JOBS_DIR = (
                previous_url, previous_file, previous_dir)

    def test_replaces_only_the_connected_first_frame(self):
        workflow = json.loads(json.dumps(MINIMAX))
        workflow["5"] = {"class_type": "LoadImage", "inputs": {"image": "other.png"}}
        result = abstract_video.fill_minimax_workflow(workflow, "new prompt", "new.png")
        self.assertEqual(result["1"]["inputs"]["image"], "new.png")
        self.assertEqual(result["5"]["inputs"]["image"], "other.png")
        self.assertEqual(workflow["3"]["inputs"]["prompt"], "old prompt")

    def test_upload_and_local_generation(self):
        comfy = ThreadingHTTPServer(("127.0.0.1", 0), FakeComfy)
        previous_url, previous_dir = abstract_video.COMFYUI_URL, app.JOBS_DIR
        abstract_video.COMFYUI_URL = f"http://127.0.0.1:{comfy.server_port}"
        threading.Thread(target=comfy.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                app.JOBS_DIR = Path(folder)
                motion = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
                threading.Thread(target=motion.serve_forever, daemon=True).start()
                try:
                    boundary, data = multipart({"prompt": b"three streams", "image": IMAGE,
                                                "workflow": json.dumps(WORKFLOW).encode()})
                    request = urllib.request.Request(
                        f"http://127.0.0.1:{motion.server_port}/api/abstract/jobs", data=data,
                        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
                    with urllib.request.urlopen(request) as response:
                        job_id = json.load(response)["id"]
                    for _ in range(30):
                        with urllib.request.urlopen(
                                f"http://127.0.0.1:{motion.server_port}/api/jobs/{job_id}") as response:
                            job = json.load(response)
                        if job["status"] in {"complete", "error"}:
                            break
                        time.sleep(0.1)
                    self.assertEqual(job["status"], "complete", job.get("details"))
                    self.assertEqual(job["kind"], "abstract")
                    with urllib.request.urlopen(f"http://127.0.0.1:{motion.server_port}{job['video']}") as response:
                        self.assertEqual(response.read(), b"test mp4 bytes")
                finally:
                    motion.shutdown()
                    motion.server_close()
        finally:
            comfy.shutdown()
            comfy.server_close()
            abstract_video.COMFYUI_URL, app.JOBS_DIR = previous_url, previous_dir

    def test_requires_two_placeholders(self):
        with self.assertRaisesRegex(ValueError, "\\{\\{IMAGE\\}\\}"):
            abstract_video.fill_workflow({"1": {"class_type": "Text", "inputs": {
                "text": "{{PROMPT}}"}}}, "prompt", "image.png")


if __name__ == "__main__":
    unittest.main()
