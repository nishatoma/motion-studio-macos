"""Direct LTX-Video runner; isolated from Motion Studio's Manim environment."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent
LTX_DIR = Path(os.environ.get("MOTION_STUDIO_LTX_DIR", ROOT / "vendor" / "LTX-Video")).expanduser()
PYTHON = LTX_DIR / ".venv" / "bin" / "python"
CONFIG = ROOT / "configs" / "ltxv-2b-mac.yaml"


def is_ready() -> bool:
    return PYTHON.is_file() and (LTX_DIR / "inference.py").is_file() and CONFIG.is_file()


def run(prompt: str, image_path: Path, output_path: Path,
        progress: Callable[[str], None], log: Callable[[str], None],
        preset: str = "preview", seed: int = 171198) -> Path:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("The direct LTX backend currently requires an Apple silicon Mac.")
    if not is_ready():
        raise RuntimeError("Install the local LTX 2B backend with setup_ltx_mac.command, then restart Motion Studio.")
    # Keep frame counts at 8n+1 and dimensions divisible by 32. A short first
    # pass is intentional on 32 GB unified memory; 720p can still run out of RAM.
    width, height, frames = (768, 448, 49) if preset == "preview" else (1024, 576, 73)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    render_dir = output_path.parent / "ltx-output"
    render_dir.mkdir(exist_ok=True)
    command = [str(PYTHON), "inference.py", "--prompt", prompt,
               "--conditioning_media_paths", str(image_path),
               "--conditioning_start_frames", "0", "--pipeline_config", str(CONFIG),
               "--width", str(width), "--height", str(height),
               "--num_frames", str(frames), "--frame_rate", "24",
               "--seed", str(seed), "--output_path", str(render_dir)]
    log("LTX-Video 2B distilled, Apple MPS\n"
        f"Resolution: {width}x{height}, frames: {frames}, fps: 24, seed: {seed}\n"
        f"First run downloads open model weights and text encoder to Hugging Face cache.\n"
        f"Command: {command[0]} inference.py [prompt omitted] --pipeline_config {CONFIG}\n")
    progress("Loading local LTX model (first run downloads weights)…")
    process = subprocess.Popen(command, cwd=LTX_DIR, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, bufsize=1)
    assert process.stdout is not None
    recent = []
    for line in process.stdout:
        log(line)
        recent.append(line.rstrip())
        recent = recent[-12:]
        if "100%" in line and "/8" in line:
            progress("Sampling finished; decoding and saving frames…")
        elif "Output saved to" in line:
            progress("Checking the exported video…")
        elif "it/s" in line or "Loading" in line or "Downloading" in line:
            progress(line.strip()[-180:])
    code = process.wait()
    if code:
        raise RuntimeError(f"Local LTX generation exited with code {code}. "
                           f"See the full render log. Last output: {' | '.join(recent[-3:])}")
    movies = list(render_dir.glob("*.mp4"))
    if len(movies) != 1:
        raise RuntimeError(f"Expected one MP4 from LTX, found {len(movies)}. See the render log.")
    _check_visual_output(movies[0], log)
    shutil.copy2(movies[0], output_path)
    return output_path


def _check_visual_output(movie: Path, log: Callable[[str], None]) -> None:
    """Reject a uniformly colored render while retaining upstream MP4 for diagnosis."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        log("FFmpeg unavailable; skipped visual output check.\n")
        return
    command = [ffmpeg, "-v", "error", "-i", str(movie), "-vf",
               "fps=1,scale=64:36,format=rgb24", "-frames:v", "4",
               "-f", "rawvideo", "-"]
    result = subprocess.run(command, capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError("LTX saved an MP4, but FFmpeg could not read its frames: "
                           + result.stderr.decode("utf-8", errors="replace")[-300:])
    frame_bytes = 64 * 36 * 3
    frames = [result.stdout[i:i + frame_bytes]
              for i in range(0, len(result.stdout), frame_bytes)
              if len(result.stdout[i:i + frame_bytes]) == frame_bytes]
    if not frames:
        raise RuntimeError("LTX saved an MP4 with no readable frames.")
    ranges = [max(frame) - min(frame) for frame in frames]
    log(f"Output check: {len(frames)} sampled frames, RGB ranges {ranges}.\n")
    if len(frames) >= 2 and all(span <= 10 for span in ranges):
        raise RuntimeError(
            "LTX produced a nearly uniform video (gray/blank frames). "
            "The MP4 was kept under ltx-output for diagnosis. "
            "This can be a model or Apple MPS numerical failure; "
            "a different video encoder will not restore missing image detail."
        )
