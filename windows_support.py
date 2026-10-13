"""Small cross-platform paths and a fixed Windows setup command."""
from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path


def output_dir() -> Path:
    if platform.system() == "Windows":
        # Default Windows Videos folder; no macOS-specific Movies path.
        videos = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Videos"
        return videos / "Nisha Motion Graphics"
    return Path.home() / "Movies" / "Nisha Motion Graphics"


def manim_binary(root: Path) -> Path:
    return root / ".venv" / ("Scripts/manim.exe" if platform.system() == "Windows" else "bin/manim")


def ffmpeg_binary() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    if platform.system() == "Windows":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            link = Path(local) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"
            if link.is_file():
                return str(link)
    return None


def setup_command(root: Path) -> list[str]:
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", str(root / "setup_windows.ps1")]


def tool_binary(name: str) -> str | None:
    """Find native tools even when WinGet changed PATH after the app started."""
    found = shutil.which(name)
    if found:
        return found
    if platform.system() != "Windows":
        return None
    program_files = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    candidates = {
        "node": [program_files / "nodejs/node.exe", local / "Programs/nodejs/node.exe"],
        "docker": [program_files / "Docker/Docker/resources/bin/docker.exe"],
        "ffmpeg": [local / "Microsoft/WinGet/Links/ffmpeg.exe"],
        "ffprobe": [local / "Microsoft/WinGet/Links/ffprobe.exe"],
    }.get(name, [])
    return next((str(path) for path in candidates if path.is_file()), None)


def code_setup_command(root: Path) -> list[str]:
    if platform.system() == "Windows":
        return ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(root / "setup_code_motion.ps1")]
    return ["bash",str(root / "setup_code_motion.command")]
