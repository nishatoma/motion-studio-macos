# Motion Studio for macOS

A local browser dashboard for generating short 2D motion graphics for DaVinci Resolve. It uses Ollama to turn a natural-language prompt into a constrained JSON scene plan, then uses Manim to render an MP4. The plan is validated and mapped to a small set of built-in shapes and chart types; the model never supplies executable Python.

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
4. Double-click `start.command` (or run it from Terminal).
5. Open <http://127.0.0.1:8765> in your browser.

If macOS blocks a `.command` file, use Terminal:

```sh
cd /path/to/motion-studio-macos
chmod +x setup_mac.command start.command
./setup_mac.command
./start.command
```

## Workflow

1. Write a visual prompt in the dashboard and choose the Ollama model.
2. Render a 720p preview while refining timing and layout.
3. Choose 1080p or 4K/24 fps for the final render.
4. Completed MP4s are saved under `~/Movies/Nisha Motion Graphics/` and can be imported into Resolve.

The graph tool includes a simple face-shaped marker placeholder. Replace it with your own keyed or masked footage in Resolve if desired.

## Current scope

Supported visual elements: titles/text, numbers, lines, circles, rectangles, exponential/linear/logarithmic graphs, and a simple face marker. Beats reveal together and remain on screen until the next beat clears them. This first macOS build exports MP4; transparent alpha exports, direct Resolve project integration, and free-form custom Manim code are not included.

The server binds to `127.0.0.1` only. Ollama and Manim communicate locally. The app does not upload prompts or renders to a hosted service.

## Troubleshooting

- **Ollama offline:** open Ollama, then refresh the dashboard.
- **No model listed:** run `ollama pull qwen2.5-coder:3b`, wait for completion, and refresh.
- **Manim setup error:** rerun `setup_mac.command`; if Homebrew reports a missing dependency, install it and rerun the script.
- **Render takes too long:** use Preview (720p/24 fps); 4K rendering time depends on the Mac and scene complexity.
- **Port already in use:** launch with `MOTION_STUDIO_PORT=8766 .venv/bin/python app.py` and visit port 8766.
