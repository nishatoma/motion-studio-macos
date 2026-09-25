#!/usr/bin/env python3
"""Local-only motion graphics dashboard for macOS."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
BUILD_ID = "2026.09.25.5"
JOBS_DIR = Path.home() / "Movies" / "Nisha Motion Graphics"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
PORT = int(os.environ.get("MOTION_STUDIO_PORT", "8765"))
MAX_PROMPT = 5000
JOBS: dict[str, dict[str, Any]] = {}
LOCK = threading.Lock()

PRESETS = {
    "preview": {"width": 1280, "height": 720, "fps": 24, "label": "Preview · 720p / 24 fps"},
    "1080p": {"width": 1920, "height": 1080, "fps": 24, "label": "YouTube · 1080p / 24 fps"},
    "4k24": {"width": 3840, "height": 2160, "fps": 24, "label": "YouTube 4K · 24 fps"},
    "4k60": {"width": 3840, "height": 2160, "fps": 60, "label": "4K · 60 fps"},
}
OBJECT_TYPES = ["text", "title", "number", "line", "circle", "rectangle", "graph", "face_marker"]
PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "background": {"type": "string"},
        "beats": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "duration": {"type": "number"},
                "clear_before": {"type": "boolean"},
                "items": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": OBJECT_TYPES},
                        "text": {"type": "string"},
                        "color": {"type": "string"},
                        "position": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                        "size": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                        "curve": {"type": "string", "enum": ["exponential", "linear", "logarithmic"]},
                        "x_label": {"type": "string"},
                        "y_label": {"type": "string"},
                        "marker": {"type": "boolean"}
                    },
                    "required": ["type"],
                    "additionalProperties": False
                }}
            },
            "required": ["items"],
            "additionalProperties": False
        }}
    },
    "required": ["beats"],
    "additionalProperties": False
}

STORYBOARD_LAYOUTS = {"statement", "comparison", "flow", "timeline", "cycle", "layers", "network"}
STORYBOARD_SCHEMA = {
    "type": "object", "properties": {
        "scenes": {"type": "array", "items": {"type": "object", "properties": {
            "layout": {"type": "string", "enum": sorted(STORYBOARD_LAYOUTS)},
            "title": {"type": "string"}, "subtitle": {"type": "string"},
            "labels": {"type": "array", "items": {"type": "string"}},
            "accent": {"type": "string", "enum": ["aqua", "gold", "coral", "violet"]},
            "duration": {"type": "number"},
        }, "required": ["layout", "title", "subtitle", "labels", "accent", "duration"],
            "additionalProperties": False}},
    }, "required": ["scenes"], "additionalProperties": False,
}


def validate_storyboard(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or not isinstance(raw.get("scenes"), list):
        raise ValueError("The model did not return storyboard scenes.")
    if not 1 <= len(raw["scenes"]) <= 6:
        raise ValueError("A storyboard needs 1 to 6 scenes.")
    scenes = []
    for entry in raw["scenes"]:
        if not isinstance(entry, dict) or entry.get("layout") not in STORYBOARD_LAYOUTS:
            raise ValueError("A storyboard scene has an unsupported layout.")
        layout = entry["layout"]
        title = str(entry.get("title", "")).strip()[:72]
        subtitle = str(entry.get("subtitle", "")).strip()[:105]
        labels = entry.get("labels", [])
        if not title or not isinstance(labels, list):
            raise ValueError("Storyboard titles and labels must be present.")
        minimum = {"statement": 0, "comparison": 2, "flow": 2, "timeline": 2,
                   "cycle": 3, "layers": 2, "network": 3}[layout]
        maximum = {"statement": 0, "comparison": 2, "flow": 4, "timeline": 5,
                   "cycle": 5, "layers": 5, "network": 5}[layout]
        if not minimum <= len(labels) <= maximum:
            raise ValueError(f"{layout} needs {minimum} to {maximum} labels.")
        safe_labels = [str(label).strip() for label in labels]
        if any(not label or len(label) > 32 or len(label.split()) > 5 for label in safe_labels):
            raise ValueError("Storyboard labels must be 1 to 5 short words (up to 32 characters).")
        accent = str(entry.get("accent", "aqua"))
        if accent not in {"aqua", "gold", "coral", "violet"}:
            accent = "aqua"
        scenes.append({"layout": layout, "title": title, "subtitle": subtitle,
                       "labels": safe_labels, "accent": accent,
                       "duration": max(2.1, min(5.0, float(entry.get("duration", 3.2))))})
    return {"template": "storyboard", "background": "#07131F", "scenes": scenes,
            "_source": "Ollama storyboard + fixed visual layouts"}


def storyboard_prompt(prompt: str, critique: str = "", large_model: bool = False) -> str:
    return f"""Plan a polished, short 2D motion-graphics storyboard for a YouTube video about any abstract idea.
Return ONLY JSON matching the schema. Choose one of these visual layouts for each scene:
- statement: one bold idea or surprising question; labels MUST be [].
- comparison: exactly two contrasting concepts; labels are the two sides.
- flow: 2-4 ordered steps or cause-and-effect events.
- timeline: 2-5 chronological stages.
- cycle: 3-5 elements of a repeating loop.
- layers: 2-5 stacked costs, pressures, or components.
- network: 3-5 ideas connected to a central theme.
Use {"1-2" if large_model else "2-4"} scenes with varied layouts, 2.5-4 seconds each. A title is a short on-screen claim (max 7 words), subtitle is one helpful phrase, and each label is at most 4 words. Make the visual relationships specific to the user's idea. Preserve requested names, numbers, and causal order. Do not invent facts or add investment returns. Avoid repeating the same labels across scenes. Choose aqua, gold, coral, or violet for emphasis. The renderer handles positions and animation. Do not include coordinates, Python, markdown, or code fences.
User request: {prompt}{critique}"""


def storyboard_score(plan: dict[str, Any]) -> float:
    """Rank for brevity and distinct content; layout itself is deterministic."""
    seen: set[str] = set()
    score = 0.0
    for scene in plan["scenes"]:
        for label in [scene["title"], *scene["labels"]]:
            key = label.casefold()
            if key in seen:
                score += 8
            seen.add(key)
            score += max(0, len(label) - 30) * 0.3
        if len(scene["title"].split()) > 8:
            score += 5
    if len({scene["layout"] for scene in plan["scenes"]}) == 1 and len(plan["scenes"]) > 1:
        score += 5
    return score


def local_json(url: str, payload: dict[str, Any] | None = None, timeout: int = 10) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def ollama_models() -> list[str]:
    try:
        data = local_json(f"{OLLAMA_URL}/api/tags", timeout=2)
        return [m["name"] for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def validate_color(value: Any, default: str = "#62E6D5") -> str:
    if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return value.upper()
    return default


def validate_spec(spec: Any) -> dict[str, Any]:
    """Allow a small declarative vocabulary; never execute model-authored Python."""
    if not isinstance(spec, dict) or not isinstance(spec.get("beats"), list):
        raise ValueError("The model did not return a valid animation plan.")
    if not 1 <= len(spec["beats"]) <= 12:
        raise ValueError("The animation plan must have between 1 and 12 beats.")
    clean: dict[str, Any] = {"background": validate_color(spec.get("background"), "#07131F"), "beats": []}
    allowed = {"text", "title", "line", "circle", "rectangle", "graph", "face_marker", "number"}
    for beat in spec["beats"]:
        if not isinstance(beat, dict):
            raise ValueError("Each beat must be an object.")
        duration = max(0.4, min(8.0, float(beat.get("duration", 2.0))))
        items = beat.get("items", [])
        if not isinstance(items, list) or len(items) > 10:
            raise ValueError("Each beat can contain up to 10 objects.")
        safe_items = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Every object in the plan must be a JSON object.")
            kind = str(item.get("type", "")).strip().lower().replace("-", "_").replace(" ", "_")
            aliases = {
                "label": "text", "caption": "text", "text_label": "text",
                "heading": "title", "headline": "title",
                "counter": "number", "number_counter": "number",
                "axes": "graph", "chart": "graph", "plot": "graph", "curve": "graph",
                "arrow": "line", "connector": "line",
                "dot": "circle", "point": "circle",
                "box": "rectangle", "bar": "rectangle",
                "face": "face_marker", "head": "face_marker", "person": "face_marker"
            }
            kind = aliases.get(kind, kind)
            if kind not in allowed:
                raise ValueError(f"Unsupported object type '{kind or '(missing)'}'. Try: {', '.join(sorted(allowed))}.")
            out = {"type": kind, "color": validate_color(item.get("color")),
                   "position": _pair(item.get("position", [0, 0]), [-1, 0])}
            if kind in {"text", "title", "number"}:
                text = str(item.get("text", ""))[:100]
                if not text:
                    raise ValueError("Text objects need non-empty text.")
                out["text"] = text
                out["size"] = max(16, min(72, int(item.get("size", 44 if kind == "title" else 30))))
            elif kind in {"line", "circle", "rectangle"}:
                out["size"] = _pair(item.get("size", [3, 1]), [3, 1])
            elif kind == "graph":
                curve = item.get("curve", "exponential")
                out["curve"] = curve if curve in {"exponential", "linear", "logarithmic"} else "exponential"
                out["size"] = _pair(item.get("size", [9, 4.5]), [9, 4.5])
                out["x_label"] = str(item.get("x_label", "Time"))[:30]
                out["y_label"] = str(item.get("y_label", "Value"))[:30]
                out["marker"] = bool(item.get("marker", False))
            elif kind == "face_marker":
                out["size"] = max(0.35, min(1.0, float(item.get("size", 0.55))))
            safe_items.append(out)
        clean["beats"].append({"duration": duration, "clear_before": bool(beat.get("clear_before", False)), "items": safe_items})
    return clean


def _pair(value: Any, fallback: list[float]) -> list[float]:
    if not isinstance(value, list) or len(value) != 2:
        return fallback
    try:
        return [max(-6.5, min(6.5, float(value[0]))), max(-3.4, min(3.4, float(value[1])))]
    except (TypeError, ValueError):
        return fallback


def make_prompt(user_prompt: str) -> str:
    return f"""Create a short, polished 2D motion-graphics sequence for a personal-finance YouTube video.
Return ONLY JSON that follows the supplied schema. For each item's `type`, use only one exact value from this list: text, title, number, line, circle, rectangle, graph, face_marker. Do not invent new object types such as axes, arrow, label, or icon; express those ideas using graph, line, text, circle, or face_marker. Create 3 to 7 beats, each 1 to 4 seconds. Every explicitly requested dollar milestone must appear as a text or number item containing its exact label. Never substitute generic circles or lines for named milestones. Keep text concise and legible. Use a dark navy background, aqua accents, restrained bloom-like color contrast, strong composition, and meaningful reveals. Coordinates are centered Manim frame coordinates: x roughly -7 to 7, y roughly -4 to 4. For graphs, use graph type and labels; if the user asks for a face moving along the curve, set the graph item's marker to true. Do not add markdown or code fences.

User's animation request: {user_prompt}"""


def requested_milestones(prompt: str) -> list[str]:
    if not re.search(r"\b(graph|curve|chart)\b", prompt, re.I) or "milestone" not in prompt.lower():
        return []
    amounts = [re.sub(r"\s+", "", match.group()).upper()
               for match in re.finditer(r"\$\s*\d[\d,]*(?:\.\d+)?\s*[KMB]?", prompt, re.I)]
    if len(amounts) > 1 and re.search(r"\b(monthly|every month|per month)\b", prompt, re.I):
        amounts = amounts[1:]
    return list(dict.fromkeys(amounts))


def money_value(label: str) -> float:
    match = re.fullmatch(r"\$([\d,]+(?:\.\d+)?)([KMB]?)", label.upper())
    if not match:
        raise ValueError(f"Invalid amount: {label}")
    return float(match.group(1).replace(",", "")) * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[match.group(2)]


def directed_growth_plan(prompt: str) -> dict[str, Any] | None:
    """Keep coordinates and financial math out of the small language model."""
    ages = re.search(r"\bage\s+(\d+)\s+to\s+(\d+)\b", prompt, re.I)
    monthly = re.search(r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:invested\s+)?(?:every\s+month|monthly|per\s+month)", prompt, re.I)
    labels = requested_milestones(prompt)
    if not (ages and monthly and 2 <= len(labels) <= 5):
        return None
    start, end = map(int, ages.groups())
    contribution = float(monthly.group(1).replace(",", ""))
    values = [money_value(label) for label in labels]
    if not (18 <= start < end <= 100 and end - start >= 5 and 1 <= contribution <= 100000
            and all(a < b for a, b in zip(values, values[1:]))
            and values[-1] > contribution * 12 * (end - start)):
        return None
    return {
        "template": "portfolio_growth", "background": "#07131F",
        "monthly": contribution, "start_age": start, "end_age": end,
        "milestones": [{"label": label, "value": value} for label, value in zip(labels, values)],
        "marker": bool(re.search(r"\b(face|head)\b", prompt, re.I)),
        "_source": "directed investment graph layout",
    }


def validated_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("template") == "storyboard":
        return validate_storyboard(plan)
    if plan.get("template") != "portfolio_growth":
        clean = validate_spec(plan)
        if plan.get("_source"):
            clean["_source"] = plan["_source"]
        return clean
    start, end = int(plan["start_age"]), int(plan["end_age"])
    monthly = float(plan["monthly"])
    milestones = plan["milestones"]
    if not (18 <= start < end <= 100 and end - start >= 5 and 1 <= monthly <= 100000
            and isinstance(milestones, list) and 2 <= len(milestones) <= 5):
        raise ValueError("Invalid directed graph parameters.")
    clean_milestones = []
    for item in milestones:
        label = str(item["label"])
        value = money_value(label)
        if abs(value - float(item["value"])) > 0.01:
            raise ValueError("Milestone value does not match its label.")
        clean_milestones.append({"label": label, "value": value})
    values = [item["value"] for item in clean_milestones]
    if not all(a < b for a, b in zip(values, values[1:])) or values[-1] <= monthly * 12 * (end - start):
        raise ValueError("Milestones must rise above total contributions.")
    return {"template": "portfolio_growth", "background": "#07131F", "monthly": monthly,
            "start_age": start, "end_age": end, "milestones": clean_milestones,
            "marker": bool(plan.get("marker")), "_source": "directed investment graph layout"}


def check_prompt_coverage(plan: dict[str, Any], prompt: str) -> None:
    milestones = requested_milestones(prompt)
    if not milestones:
        return
    items = [item for beat in plan["beats"] for item in beat["items"]]
    texts = [re.sub(r"\s+", "", item.get("text", "")).upper()
             for item in items if item["type"] in {"text", "title", "number"}]
    missing = [amount for amount in milestones if not any(amount in text for text in texts)]
    if missing:
        raise ValueError("Missing the requested milestone labels: " + ", ".join(missing))
    graphs = [item for item in items if item["type"] == "graph"]
    if not graphs:
        raise ValueError("The requested graph is missing.")
    if re.search(r"\b(face|head)\b", prompt, re.I) and "along" in prompt.lower():
        if not any(graph["marker"] for graph in graphs):
            raise ValueError("The graph needs a moving face marker.")


def finance_graph_fallback(prompt: str) -> dict[str, Any] | None:
    """Preserve named milestones if a small model leaves them out twice."""
    milestones = requested_milestones(prompt)
    if not 2 <= len(milestones) <= 6:
        return None
    monthly = re.search(r"\$\s*\d[\d,]*(?:\.\d+)?", prompt)
    title = (monthly.group().replace(" ", "") + " / month") if monthly else "Growth over time"
    ages = re.search(r"age\s+(\d+)\s+to\s+(\d+)", prompt, re.I)
    age_label = f"Age {ages.group(1)} to {ages.group(2)}" if ages else "Age"
    show_marker = bool(re.search(r"\b(face|head)\b", prompt, re.I))
    beats: list[dict[str, Any]] = [
        {"duration": 1.0, "items": [{"type": "title", "text": title,
                                      "position": [-2.0, 3.0], "size": 42, "color": "#F4F9FB"}]},
        {"duration": 3.0, "items": [{"type": "graph", "curve": "exponential",
                                      "position": [-2.0, -0.15], "size": [6.5, 3.4],
                                      "x_label": age_label, "y_label": "Portfolio Value",
                                      "marker": show_marker, "color": "#62E6D5"}]},
    ]
    for index, amount in enumerate(milestones):
        beats.append({"duration": 1.0, "items": [{"type": "number", "text": amount,
                       "position": [4.1, 2.0 - index * 0.85], "size": 43,
                       "color": "#F6C76B" if index == len(milestones) - 1 else "#62E6D5"}]})
    plan = validate_spec({"background": "#07131F", "beats": beats})
    plan["_source"] = "built-in graph layout (model omitted requested milestones)"
    return plan


def layout_penalty(plan: dict[str, Any]) -> float:
    """Estimate collisions among visible text, faces, and graph regions."""
    visible: list[tuple[dict[str, Any], tuple[float, float, float, float]]] = []
    penalty = 0.0
    for beat in plan["beats"]:
        if beat["clear_before"]:
            visible = []
        for item in beat["items"]:
            kind = item["type"]
            if kind in {"title", "text", "number"}:
                width = min(13.5, len(item["text"]) * item["size"] / 110)
                height = item["size"] / 58
            elif kind == "graph":
                width, height = item["size"]
            elif kind == "face_marker":
                width = height = 2 * item["size"]
            else:
                continue
            x, y = item["position"]
            box = (x - width / 2, y - height / 2, x + width / 2, y + height / 2)
            if box[0] < -6.95 or box[2] > 6.95 or box[1] < -3.9 or box[3] > 3.9:
                penalty += 12
            for other, old in visible:
                if kind == other["type"] == "graph":
                    continue
                if "graph" not in (kind, other["type"]) and not (
                    kind in {"title", "text", "number", "face_marker"}
                    or other["type"] in {"title", "text", "number", "face_marker"}
                ):
                    continue
                overlap = max(0, min(box[2], old[2]) - max(box[0], old[0])) * max(
                    0, min(box[3], old[3]) - max(box[1], old[1]))
                penalty += overlap * 10
            visible.append((item, box))
    return penalty


def generate_storyboard(prompt: str, model: str) -> dict[str, Any]:
    best, best_score = None, float("inf")
    critique = ""
    last_error = None
    size_match = re.search(r":(\d+)b(?:$|[-_])", model, re.I)
    billions = int(size_match.group(1)) if size_match else 7
    attempts = 1 if billions >= 14 else 2 if billions >= 7 else 3
    large_model = billions >= 14
    for attempt in range(attempts):
        try:
            response = local_json(f"{OLLAMA_URL}/api/generate", {
                "model": model, "prompt": storyboard_prompt(prompt, critique, large_model),
                "stream": False, "think": False, "format": STORYBOARD_SCHEMA,
                "keep_alive": 0 if large_model else "5m",
                "options": {"temperature": 0.2, "num_ctx": 4096,
                            "num_predict": 850 if large_model else 1200},
            }, timeout=300)
            candidate = validate_storyboard(json.loads(response.get("response", "")))
            score = storyboard_score(candidate)
            if score < best_score:
                best, best_score = candidate, score
            critique = "\nMake a distinct, more concise storyboard with different visual relationships."
        except urllib.error.URLError as exc:
            raise RuntimeError("Ollama is not responding. Open Ollama and try again.") from exc
        except TimeoutError as exc:
            if best is not None:
                break
            raise RuntimeError(f"{model} did not finish a storyboard within 5 minutes. Run 'ollama ps' to check for other loaded models, stop those you are not using, or select a smaller model such as qwen2.5-coder:14b.") from exc
        except (ValueError, TypeError, KeyError) as exc:
            last_error = exc
            critique = f"\nThe previous response was invalid: {exc}. Follow the exact layout label counts."
    if best is None:
        raise RuntimeError(f"The model returned no usable storyboard: {last_error}") from last_error
    best["_source"] = f"Ollama storyboard · best of {attempts} ({model})"
    return best


def generate_plan(prompt: str, model: str, planning_quality: str = "polished") -> dict[str, Any]:
    if planning_quality == "polished":
        directed = directed_growth_plan(prompt)
        if directed:
            return validated_plan(directed)
        return generate_storyboard(prompt, model)
    retry_note = ""
    best_plan, best_score = None, float("inf")
    attempts = 1 if planning_quality == "fast" else 3
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = local_json(f"{OLLAMA_URL}/api/generate", {
                "model": model, "prompt": make_prompt(prompt) + retry_note, "stream": False,
                "format": PLAN_SCHEMA, "options": {"temperature": 0.1}
            }, timeout=300)
        except urllib.error.URLError as exc:
            raise RuntimeError("Ollama is not responding. Open Ollama and try again.") from exc
        except TimeoutError as exc:
            raise RuntimeError("The model took too long. Try a smaller model or a shorter prompt.") from exc
        raw = response.get("response", "")
        try:
            plan = validate_spec(json.loads(raw))
            check_prompt_coverage(plan, prompt)
            if planning_quality == "fast":
                return plan
            score = layout_penalty(plan)
            if score < best_score:
                best_plan, best_score = plan, score
            retry_note = ("\n\nCreate a DIFFERENT composition. Keep titles outside chart areas, "
                          "avoid text/face overlaps, and keep everything inside the frame.")
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            last_error = exc
            retry_note = f"\n\nYour previous response was invalid: {exc}. Regenerate the complete plan using only the schema and exact object types above."
    if best_plan is not None:
        best_plan["_source"] = f"Ollama · best of {attempts} layouts (estimated overlap {best_score:.1f})"
        return best_plan
    fallback = finance_graph_fallback(prompt)
    if fallback is not None:
        return fallback
    raise RuntimeError(f"The model returned no usable scene plan: {last_error}") from last_error


def render_job(job_id: str, prompt: str, model: str, preset: str,
               existing_plan: dict[str, Any] | None = None, planning_quality: str = "polished") -> None:
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    log_path = job_dir / "motion-studio.log"
    log_path.write_text("Motion Studio job started.\n", encoding="utf-8")
    process_output = ""
    with LOCK:
        job = JOBS[job_id]
        job["status"] = "planning"
        job["message"] = ("Reusing the scene plan…" if existing_plan is not None
                          else "Designing a clean graph layout…" if planning_quality == "polished" and directed_growth_plan(prompt)
                          else "Planning a visual storyboard with the selected model…" if planning_quality == "polished"
                          else "Asking your local model to plan the animation…")
    try:
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"Model: {model}\nPreset: {preset}\nPlanning quality: {planning_quality}\n")
        plan = existing_plan if existing_plan is not None else generate_plan(prompt, model, planning_quality)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"Plan source: {plan.get('_source', 'existing scene' if existing_plan is not None else 'Ollama')}\n")
        spec_path = job_dir / "scene.json"
        spec_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        spec_path.chmod(0o600)
        job["status"] = "rendering"
        job["message"] = f"Rendering {PRESETS[preset]['label']}…"
        preset_cfg = PRESETS[preset]
        env = os.environ.copy()
        env["MOTION_STUDIO_SPEC"] = str(spec_path)
        env["MOTION_STUDIO_OUTPUT_DIR"] = str(job_dir)
        env["MOTION_STUDIO_WIDTH"] = str(preset_cfg["width"])
        env["MOTION_STUDIO_HEIGHT"] = str(preset_cfg["height"])
        env["MOTION_STUDIO_FPS"] = str(preset_cfg["fps"])
        manim = ROOT / ".venv" / "bin" / "manim"
        if not manim.exists():
            raise RuntimeError("Manim is not installed yet. Run setup_mac.command and restart the dashboard.")
        # Avoid Manim 0.19's brittle --resolution parser. The scene applies
        # dimensions and frame rate from the environment when Manim imports it.
        command = [str(manim), "render", "--media_dir", str(job_dir / "media"),
                   "--output_file", "animation", str(ROOT / "scene_renderer.py"), "GeneratedScene"]
        with log_path.open("a", encoding="utf-8") as log:
            log.write("Manim command: " + " ".join(command) + "\n")
            log.write(f"Build: {BUILD_ID}\nProject root: {ROOT}\n")
        proc = subprocess.run(command, env=env, capture_output=True, text=True, timeout=1800)
        process_output = "STDOUT\n" + proc.stdout + "\nSTDERR\n" + proc.stderr
        with log_path.open("a", encoding="utf-8") as log:
            log.write("\n" + process_output)
        finished_movies = [path for path in (job_dir / "media").rglob("animation.mp4")
                           if "partial_movie_files" not in path.parts]
        if proc.returncode != 0 or not finished_movies:
            raise RuntimeError("Manim render failed. Expand the error details below to see the full output.")
        final_path = job_dir / "animation.mp4"
        finished_movie = max(finished_movies, key=lambda path: path.stat().st_mtime)
        shutil.copy2(finished_movie, final_path)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\nCopied finished movie: {finished_movie}\n")
        with LOCK:
            message = ("Render ready. Visuals use a directed layout."
                       if plan.get("template") else "Render ready.")
            if plan.get("template") == "portfolio_growth":
                duration = 0.85 + len(plan["milestones"]) * 1.83 + 1.2
            elif plan.get("template") == "storyboard":
                duration = sum(s["duration"] for s in plan["scenes"]) + 0.35 * (len(plan["scenes"]) - 1)
            else:
                duration = sum(b["duration"] + (0.35 if b.get("clear_before") else 0)
                               for b in plan["beats"]) + 0.4
            job.update(status="complete", message=message, video=f"/files/{job_id}/animation.mp4",
                        filename=str(final_path), plan=plan, duration=duration,
                        details=process_output, log_url=f"/logs/{job_id}", preset=preset,
                        quality=PRESETS[preset]["label"],
                        plan_source=plan.get("_source", "Ollama"))
    except Exception as exc:
        diagnostics = process_output or traceback.format_exc()
        try:
            with log_path.open("a", encoding="utf-8") as log:
                log.write("\nERROR\n" + diagnostics + "\nPython traceback:\n" + traceback.format_exc())
        except OSError:
            pass
        with LOCK:
            job.update(status="error", message=str(exc),
                       details=diagnostics + "\n\nPython traceback:\n" + traceback.format_exc(),
                       log_url=f"/logs/{job_id}")


class Handler(BaseHTTPRequestHandler):
    server_version = "MotionStudio/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("[motion-studio] " + fmt % args)

    def _send(self, status: int, body: bytes, content_type: str = "application/json; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, value: Any) -> None:
        self._send(status, json.dumps(value).encode("utf-8"))

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/" or path == "/index.html":
            self._send(200, (WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/health":
            self._json(200, {"models": ollama_models(), "manim": (ROOT / ".venv" / "bin" / "manim").exists(),
                             "output": str(JOBS_DIR), "ollama_url": OLLAMA_URL,
                             "build": BUILD_ID, "project_root": str(ROOT), "app_file": str(Path(__file__).resolve())})
        elif path.startswith("/api/jobs/"):
            job_id = path.rsplit("/", 1)[-1]
            with LOCK:
                job = JOBS.get(job_id)
            self._json(200 if job else 404, job or {"error": "Job not found"})
        elif path.startswith("/files/"):
            parts = path.split("/")
            if len(parts) != 4 or not re.fullmatch(r"[a-f0-9]{12}", parts[2]) or parts[3] != "animation.mp4":
                return self._json(404, {"error": "File not found"})
            file_path = JOBS_DIR / parts[2] / "animation.mp4"
            if not file_path.exists():
                return self._json(404, {"error": "File not found"})
            self._send(200, file_path.read_bytes(), "video/mp4")
        elif path.startswith("/logs/"):
            job_id = path.rsplit("/", 1)[-1]
            if not re.fullmatch(r"[a-f0-9]{12}", job_id):
                return self._json(404, {"error": "Log not found"})
            log_path = JOBS_DIR / job_id / "motion-studio.log"
            if not log_path.exists():
                return self._json(404, {"error": "Log not found"})
            self._send(200, log_path.read_bytes(), "text/plain; charset=utf-8")
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        rerender_match = re.fullmatch(r"/api/jobs/([a-f0-9]{12})/rerender", self.path)
        if self.path != "/api/jobs" and not rerender_match:
            return self._json(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 12000 or length <= 0:
                return self._json(413, {"error": "Request is too large or empty."})
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                return self._json(400, {"error": "Invalid request body."})
            preset = str(body.get("preset", "preview"))
            if preset not in PRESETS:
                return self._json(400, {"error": "Choose a valid render preset."})
            if rerender_match:
                with LOCK:
                    source = JOBS.get(rerender_match.group(1))
                    if not source or source.get("status") != "complete":
                        return self._json(404, {"error": "Finished scene not found. Generate a new preview first."})
                    plan = validated_plan(source["plan"])
                    job_id = uuid.uuid4().hex[:12]
                    JOBS[job_id] = {"id": job_id, "status": "queued", "message": "Queued…", "created": time.time()}
                threading.Thread(target=render_job,
                                 args=(job_id, "", "same scene plan", preset, plan), daemon=True).start()
                return self._json(202, {"id": job_id})
            prompt = str(body.get("prompt", "")).strip()
            model = str(body.get("model", "")).strip()
            planning_quality = str(body.get("planning_quality", "polished"))
            if planning_quality not in {"fast", "polished"}:
                return self._json(400, {"error": "Choose a valid planning quality."})
            if not prompt or len(prompt) > MAX_PROMPT:
                return self._json(400, {"error": f"Enter a prompt between 1 and {MAX_PROMPT} characters."})
            if model not in ollama_models():
                return self._json(400, {"error": "Choose a model shown in the dashboard. Confirm Ollama is running."})
            job_id = uuid.uuid4().hex[:12]
            with LOCK:
                JOBS[job_id] = {"id": job_id, "status": "queued", "message": "Queued…", "created": time.time()}
            threading.Thread(target=render_job,
                             args=(job_id, prompt, model, preset, None, planning_quality), daemon=True).start()
            self._json(202, {"id": job_id})
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})


def main() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError as exc:
        if getattr(exc, "errno", None) in {48, 98, 10048}:
            raise SystemExit(f"Port {PORT} is already in use. Stop the older Motion Studio window with Control-C, then run start.command again.") from exc
        raise
    print(f"Motion Studio build {BUILD_ID} is running at http://127.0.0.1:{PORT}")
    print(f"Loaded app.py: {Path(__file__).resolve()}")
    print(f"Loaded web UI: {(WEB / 'index.html').resolve()}")
    print(f"Renders will be saved to: {JOBS_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Motion Studio…")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
