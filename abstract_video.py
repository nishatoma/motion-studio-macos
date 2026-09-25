"""Image-to-video jobs through a user-supplied ComfyUI API workflow.

The workflow is data, never Python code. The user selects which installed
video model and sampler ComfyUI runs; Motion Studio only fills two strings.
"""
from __future__ import annotations

import json
import mimetypes
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable

COMFYUI_URL = "http://127.0.0.1:8188"
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_WORKFLOW_BYTES = 2 * 1024 * 1024
IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
VIDEO_SUFFIXES = {".mp4", ".webm", ".mov"}


def image_extension(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    raise ValueError("Choose a PNG, JPEG, or WebP first frame.")


def fill_workflow(raw: Any, prompt: str, image_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw or not all(
        isinstance(node, dict) and isinstance(node.get("class_type"), str)
        for node in raw.values()
    ):
        raise ValueError("Export a ComfyUI workflow in API format, then select its JSON file.")
    serialized = json.dumps(raw)
    if "{{PROMPT}}" not in serialized or "{{IMAGE}}" not in serialized:
        raise ValueError("The API workflow needs {{PROMPT}} and {{IMAGE}} in its prompt and LoadImage fields.")

    def replace(value: Any) -> Any:
        if isinstance(value, str):
            return value.replace("{{PROMPT}}", prompt).replace("{{IMAGE}}", image_name)
        if isinstance(value, list):
            return [replace(child) for child in value]
        if isinstance(value, dict):
            return {key: replace(child) for key, child in value.items()}
        return value

    return replace(raw)


def _json(path: str, payload: dict[str, Any] | None = None, timeout: int = 15) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(COMFYUI_URL + path, data=data,
                                     headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read(2 * 1024 * 1024).decode("utf-8"))


def is_ready() -> bool:
    try:
        return isinstance(_json("/system_stats", timeout=1), dict)
    except (OSError, ValueError):
        return False


def _upload_image(data: bytes, suffix: str) -> str:
    filename = "motion-studio-" + uuid.uuid4().hex + suffix
    boundary = "MotionStudio" + uuid.uuid4().hex
    prefix = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; "
              f"filename=\"{filename}\"\r\nContent-Type: "
              f"{mimetypes.guess_type(filename)[0]}\r\n\r\n").encode()
    body = prefix + data + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(COMFYUI_URL + "/upload/image", data=body,
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        uploaded = json.loads(response.read(1024 * 1024).decode("utf-8"))
    if not uploaded.get("name"):
        raise RuntimeError("ComfyUI did not accept the reference image.")
    return uploaded["name"]


def _video_output(history: dict[str, Any]) -> dict[str, str] | None:
    for node in history.get("outputs", {}).values():
        if not isinstance(node, dict):
            continue
        for entries in node.values():
            if not isinstance(entries, list):
                continue
            for item in entries:
                if (isinstance(item, dict) and isinstance(item.get("filename"), str)
                        and Path(item["filename"]).suffix.lower() in VIDEO_SUFFIXES):
                    return item
    return None


def run(prompt: str, image_data: bytes, workflow: dict[str, Any], output: Path,
        progress: Callable[[str], None], log: Callable[[str], None]) -> Path:
    suffix = image_extension(image_data)
    # Check placeholders before any expensive model work.
    fill_workflow(workflow, prompt, "reference" + suffix)
    progress("Uploading the reference frame to local ComfyUI…")
    image_name = _upload_image(image_data, suffix)
    planned = fill_workflow(workflow, prompt, image_name)
    queued = _json("/prompt", {"prompt": planned, "client_id": uuid.uuid4().hex})
    if not queued.get("prompt_id"):
        raise RuntimeError("ComfyUI rejected the workflow: " + json.dumps(queued)[:1200])
    prompt_id = queued["prompt_id"]
    log(f"Queued ComfyUI prompt: {prompt_id}\n")
    progress("Generating moving imagery in local ComfyUI…")
    deadline = time.monotonic() + 3600
    while time.monotonic() < deadline:
        result = _json("/history/" + urllib.parse.quote(prompt_id, safe=""), timeout=20)
        history = result.get(prompt_id, {})
        if history.get("status", {}).get("status_str") == "error":
            raise RuntimeError("ComfyUI generation failed: " + json.dumps(history.get("status", {}))[:1600])
        video = _video_output(history)
        if video:
            query = urllib.parse.urlencode({"filename": video["filename"],
                                            "subfolder": video.get("subfolder", ""),
                                            "type": video.get("type", "output")})
            progress("Saving the generated video…")
            source = output.with_name("comfy-source" + Path(video["filename"]).suffix.lower())
            with urllib.request.urlopen(COMFYUI_URL + "/view?" + query, timeout=60) as response:
                with source.open("wb") as target:
                    while block := response.read(1024 * 1024):
                        target.write(block)
            if source.stat().st_size == 0:
                raise RuntimeError("ComfyUI returned an empty video file.")
            if source.suffix == ".mp4":
                source.replace(output)
            else:
                ffmpeg = shutil.which("ffmpeg")
                if not ffmpeg:
                    raise RuntimeError("FFmpeg is needed to convert this video for Resolve.")
                command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
                           "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-movflags", "+faststart", str(output)]
                converted = subprocess.run(command, capture_output=True, text=True, timeout=1800)
                if converted.returncode:
                    raise RuntimeError("FFmpeg could not convert the video: " + converted.stderr[-1600:])
            log(f"Saved {video['filename']} ({output.stat().st_size} bytes).\n")
            return output
        if history.get("status", {}).get("completed"):
            raise RuntimeError("The workflow finished without an MP4, WebM, or MOV output. Add a video save node.")
        time.sleep(2)
    raise TimeoutError("ComfyUI did not finish within one hour. Check its queue and logs.")
