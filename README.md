# Motion Studio for macOS

A local browser dashboard for short video assets for DaVinci Resolve. **Abstract video** animates a first frame directly on Apple silicon with the open LTX-Video 2B model; a ComfyUI workflow remains optional. **Data graphics** retains the Ollama and Manim pipeline for precise charts and labeled diagrams. Model output is never executed as Python.

## Requirements

- macOS 12 or later (Apple silicon or Intel)
- Homebrew
- Ollama for prompt-to-scene generation
- Internet access for first-time package/model downloads

Manim rendering runs locally. An Apple silicon Mac is not required; slower Macs can use the 720p preview preset.

## Visual style

Every render uses a deep charcoal background, warm amber focal points, vivid aqua supporting lines, restrained coral/violet accents, and soft light around bright elements. This applies to graphs, storyboards, and fast mode alike. The glow is added by FFmpeg after Manim finishes, so final 4K renders take an extra encoding pass. Preview at 720p while adjusting timing and composition.

## Setup

1. Install Ollama for macOS from [ollama.com/download](https://ollama.com/download) and open it.
2. In Terminal, download a small model. For example:

   ```sh
   ollama pull qwen2.5-coder:3b
   ```

3. In Finder, open this folder, right-click `setup_mac.command`, choose **Open**, and confirm. It installs Manim and its media dependencies in this project’s `.venv`.
4. Double-click `start.command` (or run it from Terminal). The Terminal window prints the build number and exact `app.py`/HTML paths it loaded.
5. Open <http://127.0.0.1:8765> in your browser.

If macOS blocks a `.command` file, use Terminal:

```sh
cd /path/to/motion-studio-macos
chmod +x setup_mac.command start.command
./setup_mac.command
./start.command
```

## Direct local video setup (Apple silicon)

In Terminal, from the Motion Studio folder:

```sh
chmod +x setup_ltx_mac.command
./setup_ltx_mac.command
```

This clones the official [LTX-Video repository](https://github.com/Lightricks/LTX-Video) into the ignored `vendor/LTX-Video` folder and installs a separate Python environment. Restart `start.command` and confirm the dashboard shows **Local LTX ready**. The first video downloads the open 2B checkpoint and PixArt text encoder from Hugging Face; allow several GB of free disk space. This is local inference and does not consume LTX Studio credits. Close Ollama's large models (`ollama stop MODEL_NAME`) to free unified memory. Our Mac config disables the extra prompt enhancement models, starts with 768×448 at 24 fps, and offers a 1024×576 detail pass. A Mac compatibility preset runs 512×320 in float32 for diagnosing gray output on MPS. It may be slower and is not verified on the M1 Pro. It does not produce native 4K; upscale a successful clip separately if needed.

This backend is based on upstream's documented MPS support. It has not been run on your specific M1 Pro, so treat the first small preview as a compatibility check. The full output and Python errors appear in **Show latest render log**.

## Workflow

### Abstract video: direct local LTX 2B

1. Open **Abstract video**, drop your PNG, JPEG, or WebP first frame, and write the motion prompt.
2. Leave the optional ComfyUI workflow field empty. Choose **Preview** and click **Generate local video**.
3. Review the video in the dashboard. Use **Detail** for a separate higher resolution render. Finished MP4s go to `~/Movies/Nisha Motion Graphics/`.

### Optional LTX Desktop handoff

1. Open **Abstract video** and drop a PNG, JPEG, or WebP first frame into the dashboard. Check its preview.
2. Refine the motion prompt and click **Copy motion prompt**. Click **Download selected frame** if the original is not already saved on your Mac.
3. Open [LTX Desktop](https://github.com/Lightricks/LTX-Desktop/releases), choose **Image to Video**, import the frame, paste the motion prompt, and generate there. Bring its video into Resolve.

LTX Desktop is a separate app; Motion Studio does not silently submit to its private backend. On Apple Silicon, its local mode needs at least 15 GB *free* RAM at launch and a large model download. Its desktop local output tops out at 1080p; 4K in that product uses the paid API. Your 32 GB Mac may qualify if enough memory and disk space are free, but test it before relying on it for production.

### Abstract video: generate inside this dashboard with local ComfyUI

1. Start [ComfyUI](https://github.com/Comfy-Org/ComfyUI) locally on its default `127.0.0.1:8188` address, install an image-to-video model, and verify a workflow generates a video in ComfyUI itself.
2. Export that working workflow **in API format**. In the exported JSON file, replace the positive prompt string with `{{PROMPT}}` and the image filename in the `LoadImage` node with `{{IMAGE}}`. Leave the model, sampler, duration, resolution, and MP4 video save node as configured. The placeholders are literal JSON string contents.
3. In Motion Studio, drop your first frame, select that API JSON file, and click **Generate local video**. Selecting a workflow switches the backend to ComfyUI. The dashboard uploads the frame only to your local ComfyUI server, queues the workflow, polls for completion, and saves the MP4 under `~/Movies/Nisha Motion Graphics/`.

The imported workflow must contain both placeholders and produce an MP4, WebM, or MOV output. The app converts WebM/MOV to MP4 using FFmpeg. This connector does not install ComfyUI or model weights; those depend on your chosen local workflow and available hardware.

### Data graphics

1. Open **Data graphics**, write a visual prompt, choose an Ollama model, **Polished** planning, and the 720p preset. Click **Generate animation**. Polished uses a directed layout for supported monthly-investing graphs; other suitable prompts use the limited storyboard vocabulary.
2. Review the preview. For the approved scene, choose 1080p or 4K and click **Render same scene at selected quality**. This reuses the validated plan without another Ollama request.
3. Click **Download MP4**. Completed MP4s are also under `~/Movies/Nisha Motion Graphics/`.

The directed graph includes a small face-shaped marker placeholder. For an ending milestone, it derives an illustrative constant annual return so the curve actually reaches the requested amount. The percentage appears in a footnote. Replace the marker with your own keyed or masked footage in Resolve if desired.

## Current scope

The Manim storyboard supports seven reusable visual relationships: bold statements, comparisons, flows, timelines, cycles, stacked layers, and networks. It cannot draw arbitrary cinematic imagery from a sentence; use Abstract video for that. Fast mode retains the older shapes and graph vocabulary. This build exports MP4; transparent alpha exports, direct Resolve project integration, and free-form custom Manim code are not included.

The server binds to `127.0.0.1` only. Ollama and Manim communicate locally. The app does not upload prompts or renders to a hosted service.

## Troubleshooting

- **Ollama offline:** open Ollama, then refresh the dashboard.
- **Large model stalls:** run `ollama ps` to see what is loaded. Use `ollama stop MODEL_NAME` for an unused model, or select `qwen2.5-coder:14b`. The storyboard planner limits output and disables thinking where supported; large models still take longer to load than smaller ones.
- **No model listed:** run `ollama pull qwen2.5-coder:3b`, wait for completion, and refresh.
- **Manim setup error:** rerun `setup_mac.command`; if Homebrew reports a missing dependency, install it and rerun the script.
- **Render takes too long:** use Preview (720p/24 fps); 4K rendering time depends on the Mac and scene complexity.
- **Render error:** use **Show latest render log** beneath the status. On failure, the details open automatically. **Copy full log** copies the complete log to your clipboard; **Download full log** saves it as a file. A copy also stays under Movies → Nisha Motion Graphics.
- **Old UI/error persists:** stop the running dashboard with Control-C in its Terminal window, run `git pull origin main` from this project folder, relaunch `start.command`, then hard-refresh the browser with Command-Shift-R. Confirm the header says **BUILD 2026.09.25.9**. If the Terminal says port 8765 is already in use, an older dashboard is still running; close its Terminal window with Control-C first.
- **A preview is only two seconds despite a longer scene plan:** update `app.py` to build 2026.09.25.2. Older builds could download one partial movie file instead of Manim's finished movie.
- **Port already in use:** launch with `MOTION_STUDIO_PORT=8766 .venv/bin/python app.py` and visit port 8766.
