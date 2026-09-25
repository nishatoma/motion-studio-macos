# Motion Studio for macOS

A local browser dashboard for generating short 2D motion graphics for DaVinci Resolve. Supported monthly-investing graph prompts use a directed layout with calculated milestone positions. Other abstract prompts use an Ollama storyboard that selects from statements, comparisons, flows, timelines, cycles, layers, and networks. Manim renders the MP4; model output is never executed as Python.

## Requirements

- macOS 12 or later (Apple silicon or Intel)
- Homebrew
- Ollama for prompt-to-scene generation
- Internet access for first-time package/model downloads

Manim rendering runs locally. An Apple silicon Mac is not required; slower Macs can use the 720p preview preset.

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

## Workflow

1. Write a visual prompt, choose the Ollama model, **Polished** planning, and the 720p preset. Click **Generate animation** to create a new scene plan and preview. Polished uses a directed layout for supported monthly-investing graphs. For other prompts it creates one concise storyboard with 14B+ models, two candidates with 7B, or three with smaller models. Fast uses one experimental shape plan.
2. Review the complete preview. If you want a new scene plan, revise the prompt and click **Generate animation** again.
3. For the approved scene, choose 1080p or 4K and click **Render same scene at selected quality**. This reuses the validated plan without another Ollama request.
4. Click **Download MP4** after that render finishes. Download always saves the quality currently shown in the player. Completed MP4s are also under `~/Movies/Nisha Motion Graphics/` and can be imported into Resolve.

The directed graph includes a small face-shaped marker placeholder. For an ending milestone, it derives an illustrative constant annual return so the curve actually reaches the requested amount. The percentage appears in a footnote. Replace the marker with your own keyed or masked footage in Resolve if desired.

## Current scope

The storyboard supports seven reusable visual relationships: bold statements, comparisons, flows, timelines, cycles, stacked layers, and networks. It can visualize many abstract prompts, but it cannot draw arbitrary characters, cinematic scenes, or bespoke illustrations from a sentence. Fast mode retains the older shapes and graph vocabulary. This build exports MP4; transparent alpha exports, direct Resolve project integration, and free-form custom Manim code are not included.

The server binds to `127.0.0.1` only. Ollama and Manim communicate locally. The app does not upload prompts or renders to a hosted service.

## Troubleshooting

- **Ollama offline:** open Ollama, then refresh the dashboard.
- **Large model stalls:** run `ollama ps` to see what is loaded. Use `ollama stop MODEL_NAME` for an unused model, or select `qwen2.5-coder:14b`. The storyboard planner limits output and disables thinking where supported; large models still take longer to load than smaller ones.
- **No model listed:** run `ollama pull qwen2.5-coder:3b`, wait for completion, and refresh.
- **Manim setup error:** rerun `setup_mac.command`; if Homebrew reports a missing dependency, install it and rerun the script.
- **Render takes too long:** use Preview (720p/24 fps); 4K rendering time depends on the Mac and scene complexity.
- **Render error:** use **Show latest render log** beneath the status. On failure, the details open automatically. **Copy full log** copies the complete log to your clipboard; **Download full log** saves it as a file. A copy also stays under Movies → Nisha Motion Graphics.
- **Old UI/error persists:** stop the running dashboard with Control-C in its Terminal window, run `git pull origin main` from this project folder, relaunch `start.command`, then hard-refresh the browser with Command-Shift-R. Confirm the header says **BUILD 2026.09.25.6**. If the Terminal says port 8765 is already in use, an older dashboard is still running; close its Terminal window with Control-C first.
- **A preview is only two seconds despite a longer scene plan:** update `app.py` to build 2026.09.25.2. Older builds could download one partial movie file instead of Manim's finished movie.
- **Port already in use:** launch with `MOTION_STUDIO_PORT=8766 .venv/bin/python app.py` and visit port 8766.
