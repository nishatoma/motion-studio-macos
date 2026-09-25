"""Wan 2.2 TI2V image-to-video through upstream MLX-Video on Apple silicon."""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from local_video import _check_visual_output

ROOT = Path(__file__).resolve().parent
VENV = ROOT / "vendor" / "mlx-video-env"
PYTHON = VENV / "bin" / "python"
MODEL_DIR = Path(os.environ.get("MOTION_STUDIO_WAN_MODEL_DIR", ROOT / "vendor" / "wan2.2-ti2v-5b-mlx-q8")).expanduser()
# Width/height are native generation dimensions. Export dimensions do not
# change the model's detail; they only make a Resolve-ready delivery file.
PRESETS = {
    "preview": (512, 288, 41, 20, None),
    "detail": (768, 448, 49, 40, None),
    "hd": (1280, 704, 49, 40, None),
    "hd_3s": (1280, 704, 73, 40, None),
    "1080p": (1280, 704, 49, 40, (1920, 1080)),
    "1080p_3s": (1280, 704, 73, 40, (1920, 1080)),
    "4k": (1280, 704, 49, 40, (3840, 2160)),
    "4k_3s": (1280, 704, 73, 40, (3840, 2160)),
}
LABELS = {
    "preview": "512×288 native · 1.7 s",
    "detail": "768×448 native · 2 s",
    "hd": "1280×704 native · 2 s",
    "hd_3s": "1280×704 native · 3 s",
    "1080p": "1080p upscale from 1280×704 · 2 s",
    "1080p_3s": "1080p upscale from 1280×704 · 3 s",
    "4k": "4K upscale from 1280×704 · 2 s",
    "4k_3s": "4K upscale from 1280×704 · 3 s",
}


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
    width, height, frames, steps, export_size = PRESETS[preset]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    native_path = output_path.with_name("wan-native.mp4") if export_size else output_path
    command = [str(PYTHON), "-u", "-m", "mlx_video.models.wan_2.generate",
               "--model-dir", str(MODEL_DIR), "--image", str(image_path),
               "--prompt", prompt, "--width", str(width), "--height", str(height),
               "--num-frames", str(frames), "--steps", str(steps),
               "--seed", str(seed), "--tiling", "aggressive",
               "--output-path", str(native_path)]
    log(f"Wan 2.2 TI2V 5B · MLX-Video · {preset}\n"
        f"Model: {MODEL_DIR}\nNative: {width}x{height}, {frames} frames, {steps} steps, 24 fps, seed {seed}\n"
        f"Export: {export_size or (width, height)}; upscale does not add model detail.\n"
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
    if not native_path.is_file() or native_path.stat().st_size == 0:
        raise RuntimeError("Wan MLX finished without an MP4. See the full render log.")
    progress("Checking the exported video…")
    _check_visual_output(native_path, log, provider="Wan MLX")
    if export_size:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("FFmpeg is required for 1080p/4K upscale. Install it with `brew install ffmpeg`.")
        target_width, target_height = export_size
        progress(f"Upscaling the native clip to {target_width}×{target_height}…")
        # Native 1280x704 is slightly wider than 16:9. Trim 14 pixels on
        # each side before scaling so Resolve receives exact 16:9 frames.
        filter_graph = f"crop=1252:704:14:0,scale={target_width}:{target_height}:flags=lanczos,format=yuv420p"
        upscale = subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                                  "-i", str(native_path), "-vf", filter_graph,
                                  "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                                  "-movflags", "+faststart", str(output_path)],
                                 capture_output=True, text=True, timeout=1800)
        log(f"FFmpeg upscale: {upscale.stderr or 'completed'}\n")
        if upscale.returncode or not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("The native Wan clip was saved, but the upscale failed. See the full log.")
    return output_path
