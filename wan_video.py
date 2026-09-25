"""Wan 2.2 TI2V image-to-video through upstream MLX-Video on Apple silicon."""
from __future__ import annotations

import json
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Callable

from local_video import _check_visual_output

ROOT = Path(__file__).resolve().parent
VENV = ROOT / "vendor" / "mlx-video-env"
PYTHON = VENV / "bin" / "python"
MODEL_DIR = Path(os.environ.get("MOTION_STUDIO_WAN_MODEL_DIR", ROOT / "vendor" / "wan2.2-ti2v-5b-mlx-q8")).expanduser()
PRESETS = {"preview": (512, 288, 41, 20), "detail": (768, 448, 49, 40)}


def is_ready() -> bool:
    if not PYTHON.is_file():
        return False
    if not all((MODEL_DIR / name).is_file() for name in
               ("config.json", "model.safetensors", "t5_encoder.safetensors", "vae.safetensors")):
        return False
    try:
        config = json.loads((MODEL_DIR / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return config.get("model_type") == "ti2v" and config.get("in_dim") == 48


def run(prompt: str, image_path: Path, output_path: Path,
        progress: Callable[[str], None], log: Callable[[str], None],
        preset: str = "preview", seed: int = 171198) -> Path:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("Wan MLX requires an Apple silicon Mac.")
    if not is_ready():
        raise RuntimeError("Install Wan MLX with setup_wan_mlx_mac.command, then restart Motion Studio.")
    if preset not in PRESETS:
        raise ValueError("Choose a valid Wan MLX preset.")
    width, height, frames, steps = PRESETS[preset]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [str(PYTHON), "-u", "-m", "mlx_video.models.wan_2.generate",
               "--model-dir", str(MODEL_DIR), "--image", str(image_path),
               "--prompt", prompt, "--width", str(width), "--height", str(height),
               "--num-frames", str(frames), "--steps", str(steps),
               "--seed", str(seed), "--tiling", "aggressive",
               "--output-path", str(output_path)]
    log(f"Wan 2.2 TI2V 5B · MLX-Video · {preset}\n"
        f"Model: {MODEL_DIR}\nSize: {width}x{height}, {frames} frames, {steps} steps, 24 fps, seed {seed}\n"
        f"Command: {PYTHON} -m mlx_video.models.wan_2.generate [prompt omitted] --model-dir {MODEL_DIR}\n")
    progress("Loading Wan MLX model and encoding the first frame…")
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, bufsize=1,
                               env={**os.environ, "PYTHONUNBUFFERED": "1"})
    assert process.stdout is not None
    recent: list[str] = []
    for line in process.stdout:
        log(line)
        recent.append(line.strip())
        recent = recent[-8:]
        if "Encoding input image" in line:
            progress("Encoding the first frame with Wan VAE…")
        elif "Loading transformer" in line:
            progress("Loading the Wan 5B transformer…")
        elif "Decoding" in line or "Saving video" in line:
            progress("Decoding and exporting with MLX-Video…")
        elif re.search(r"\b\d+%\|", line):
            progress("Sampling Wan video… " + line.strip()[-100:])
    code = process.wait()
    if code:
        raise RuntimeError(f"Wan MLX exited with code {code}. See the full log. "
                           f"Last output: {' | '.join(recent[-3:])}")
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("Wan MLX finished without an MP4. See the full render log.")
    progress("Checking the exported video…")
    _check_visual_output(output_path, log, provider="Wan MLX")
    return output_path
