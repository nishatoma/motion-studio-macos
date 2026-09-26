"""Check that the graphics export keeps real alpha through the FFmpeg finish."""

import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zlib

import app


def alpha_png(path: Path) -> None:
    width, height = 160, 90
    pixels = bytearray()
    for y in range(height):
        pixels.append(0)  # PNG scanline filter
        for x in range(width):
            pixels.extend((255, 200, 20, 255 if 40 <= x < 120 and 20 <= y < 70 else 0))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack("!I", len(data)) + kind + data +
                struct.pack("!I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    path.write_bytes(b"\x89PNG\r\n\x1a\n" +
                     chunk(b"IHDR", struct.pack("!2I5B", width, height, 8, 6, 0, 0, 0)) +
                     chunk(b"IDAT", zlib.compress(bytes(pixels))) + chunk(b"IEND", b""))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class TransparentExportTest(unittest.TestCase):
    def test_manim_alpha_survives_resolve_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".venv/bin").mkdir(parents=True)
            (root / ".venv/bin/manim").touch()
            png = root / "source.png"
            alpha_png(png)
            job_id = "abcdef123456"
            job_dir = root / job_id
            source = job_dir / "media" / "animation.mov"
            source.parent.mkdir(parents=True)
            real_run = subprocess.run
            real_run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "24",
                      "-i", str(png), "-frames:v", "6", "-c:v", "qtrle", "-pix_fmt", "argb", str(source)], check=True)

            manim_commands = []

            def run(command, **kwargs):
                if command[0] == str(root / ".venv/bin/manim"):
                    manim_commands.append(command)
                    return subprocess.CompletedProcess(command, 0, "", "")
                return real_run(command, **kwargs)

            plan = {"template": "storyboard", "scenes": [{"duration": 0.25}]}
            with patch.object(app, "ROOT", root), patch.object(app, "JOBS_DIR", root), patch.object(app.subprocess, "run", side_effect=run):
                app.JOBS[job_id] = {"id": job_id}
                try:
                    app.render_job(job_id, "", "same scene plan", "preview", plan, transparent=True)
                    job = app.JOBS[job_id]
                finally:
                    app.JOBS.pop(job_id, None)

            self.assertEqual(job["status"], "complete", job.get("details"))
            self.assertIn("--transparent", manim_commands[0])
            self.assertEqual(job["download"], f"/files/{job_id}/animation.mov")
            self.assertEqual(job["video"], f"/files/{job_id}/preview.mp4")
            probe = real_run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                              "stream=codec_name,pix_fmt", "-of", "json", str(job_dir / "animation.mov")],
                             capture_output=True, text=True, check=True)
            stream = json.loads(probe.stdout)["streams"][0]
            self.assertEqual(stream["codec_name"], "prores")
            self.assertTrue(stream["pix_fmt"].startswith("yuva"))
            pixels = real_run(["ffmpeg", "-v", "error", "-i", str(job_dir / "animation.mov"),
                               "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
                              capture_output=True, check=True).stdout
            self.assertEqual(pixels[3], 0)
            self.assertEqual(pixels[(45 * 160 + 80) * 4 + 3], 255)
            self.assertTrue((job_dir / "preview.mp4").is_file())


if __name__ == "__main__":
    unittest.main()
