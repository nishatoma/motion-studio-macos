# Code Motion

Code Motion extends the existing Python dashboard. Data Graphics (Manim), editable Motion Canvas export, and Abstract Video (Wan/LTX/ComfyUI) remain available.

## Architecture

- `app.py` retains its local HTTP server, dashboard and legacy jobs. New `/api/code-motion/*` routes delegate to `code_motion.Studio` and use a per-launch token and same-origin checks for writes.
- `code_motion.py` owns provider calls, uploads, presets, persisted jobs, revision history, cancellation, frame inspection and export approval. Credentials remain in the Python backend environment. They are never written into projects, browser responses or worker arguments. OpenAI uses the Responses API with structured JSON and image inputs; Ollama uses its local chat API.
- `code-motion/src/worker.mjs` is a Node render service processing one job per container and emitting NDJSON progress. It bundles the generated React/TypeScript `Scene.tsx`, registers a trusted composition wrapper, and uses Remotion's `selectComposition`, `renderMedia`, `renderStill` and `renderFrames`. Remotion manages Chromium frame rendering and encoding; this is not a Playwright screenshot-to-video loop.
- Generated code runs **only** in a Docker Linux container: no external network, no published port, read-only system filesystem, dropped capabilities, no privilege escalation, CPU/memory/process limits, and one writable job mount. No host home, repository, Docker socket, environment secrets or unrelated files are mounted. The internal Remotion asset server exists only in that isolated network namespace.
- Validation parses the TSX AST, restricts imports/media to approved files and trusted dependencies, rejects common dynamic-execution/network/DOM/timer/CSS-animation capabilities, and typechecks before bundling. Static checks are defense in depth; the mandatory container is the security boundary. There is **no host fallback** for generated scenes.

A job contains `Scene.tsx`, trusted root, `job.json`, uploaded public assets, preview, sampled frames, logs and saved state. They live under the existing render directory's `code-motion/` subfolder. Restart recovers finished jobs and marks interrupted work for manual retry. Generated projects do not install dependencies during rendering. Only checked-in setup scripts build/install the reviewed dependency set.

## Use your ChatGPT subscription without an API key

Select **ChatGPT subscription · Codex** in Code Motion, then click **Sign in with ChatGPT** and complete the browser sign-in. This is the official Codex CLI subscription route, not direct OpenAI API access or browser-cookie reuse. Plus access is subject to your account's Codex eligibility and usage limits. Choose **Automatic · Codex default**, select a model such as **GPT-5.6 Sol**, or enter a **Custom model ID**. `CODEX_MODEL` / `CODEX_REVIEW_MODEL` provide optional backend defaults.

Before sign-in, the dropdown shows named presets with an account-access notice. After sign-in, the backend requests the account's available models using the official Codex app-server `model/list` protocol over private stdio and caches metadata for one minute. If discovery fails, presets remain selectable with an explicit availability warning. A preset is not a promise of access. The selected ID is passed unchanged to generation and to new revisions; the app does not silently substitute a different model. API mode retains custom IDs and Ollama lists installed local models. Model metadata does not invoke generation or consume an inference turn.

Generation, image references, code repairs, metadata planning and Auto Review all use this selected provider. It never silently falls back to the billed OpenAI API. API and Ollama providers remain selectable.

The setup installs pinned Codex CLI 0.162.1 as a host-only development dependency; it is excluded from the render container. The backend locates its native Windows/macOS/Linux binary, including ARM64. Codex manages credentials in a private app account profile under the render root's `code-motion/codex-account` directory; credentials are not read by Motion Studio, copied from your browser, returned to the frontend or included in render mounts/exports. One sign-in connects this app-specific profile; an existing ChatGPT browser session alone does not authenticate it automatically.

Requests use schema-constrained `codex exec`, supplied image attachments, read-only mode, disabled shell/browser/computer/app/plugin/agent tools, disabled hooks/web search and a temporary work directory. API keys and inherited Codex access tokens are stripped from the child environment. User CLI config/rules are ignored for generation; trusted instructions and flags are supplied explicitly. The CLI returns JSON; generated TSX still runs only in the existing offline Docker renderer. Closing the app/cancelling a request terminates the active generation process.

Official documentation: https://learn.chatgpt.com/docs/auth and https://learn.chatgpt.com/docs/non-interactive-mode

### Sign-in says “Not found” after updating

Updating files while the Python process is running can load the new dashboard against an old server. Close the Motion Studio command window (or press Ctrl+C in its terminal), then launch **start_windows.bat** on Windows or **start.command** on macOS and reload the page. A browser refresh alone does not restart Python, and this does not require rerunning Windows setup.

The dashboard checks the server's API version/capabilities before enabling sign-in or generation. An old server now gives these restart instructions. A missing login route also produces a restart message. Current server login routes accept the canonical `/api/code-motion/account/login`, compatibility aliases `/api/code-motion/auth/login` and `/api/code-motion/login`, and trailing slashes/query strings. Writes still require the local per-launch token and same-origin checks. Missing Codex executables return actionable setup errors rather than a dropped connection.

## Windows: setup completed but Code Motion says it is not ready

The original Windows setup installs the legacy tools. Code Motion additionally needs Docker Desktop running **Linux containers**, a built `motion-studio-remotion:1` image and the bundled Codex CLI for subscription mode.

Click **Check renderer**. The dashboard separately checks the Docker connection, Linux containers, the prepared renderer, FFmpeg and FFprobe. It shows the selected connection and Docker's error details; a failed connection is not automatically described as an uninstalled or stopped Docker app. Windows per-user Docker installs and nested WinGet FFmpeg packages are checked as well as standard installation locations. macOS also checks bundled Docker/Homebrew locations when PATH is stale.

If Docker is running but the renderer is missing, click **Generate preview**. It automatically prepares the renderer, then continues with your requested generation. **Prepare renderer** runs the same preparation separately. Progress and the exact failing stage appear in **Renderer preparation log**; **Cancel preparation** stops the active host child process. The app reuses an existing renderer and Codex installation. It does not rerun ComfyUI/Manim installation. API/Ollama preparation does not require host Node/Codex when only the Docker image needs building.

Preparation now runs through the shared, checked-in `code_motion_setup.py` on all platforms. The Windows PowerShell launcher delegates to Python. Node versions use `node --version`, and npm is launched through its JS entry with Node, avoiding PowerShell 5.1 embedded-quote handling and `.cmd` wrapper quoting. Normal native stderr output is captured as build progress rather than interpreted as an installation failure. Each install/build step has a timeout (900/1800 seconds), preserves its exit code and log, and cleans up its child processes on cancellation or app shutdown. Only fixed, reviewed dependency/build commands run; generated scene code never supplies setup commands.

If the current Docker connection fails or selects Windows containers, Windows/macOS may try `desktop-linux` and `default` only after verifying a local named-pipe or Unix-socket endpoint. A successful Linux connection is used consistently for image checks, building, rendering and container cleanup. Stale Docker host/TLS overrides are removed only from that fallback child's environment; your global Docker configuration is not changed. SSH/TCP fallback contexts are not selected. If no usable connection is found, the actual connection error is retained for diagnosis. Windows requires Docker Desktop with WSL2 Linux containers. Restart Motion Studio once after updating project files; repeated Windows setup is not needed just because Docker was connected through a stale context.

## Install

Additional requirements: Node.js 22+, Docker Desktop with Linux containers, FFmpeg/FFprobe and Pillow. Docker Desktop on Windows requires WSL2. Start Docker Desktop before rendering. The render image includes Chromium and FFmpeg; using Debian Chromium allows native Linux ARM64 builds on Apple silicon.

macOS:

```bash
./setup_mac.command
# Install/start Docker Desktop if not already available:
./setup_code_motion.command
export OPENAI_API_KEY='your-api-key'
export OPENAI_MODEL='your-code-and-vision-capable-model'
# Optional: a separate vision-capable review model
export OPENAI_REVIEW_MODEL='your-vision-capable-model'
./start.command
```

Windows (PowerShell):

```powershell
.\setup_windows.ps1
# Install/start Docker Desktop (WSL2 Linux containers), then:
.\setup_code_motion.ps1
$env:OPENAI_API_KEY = 'your-api-key'
$env:OPENAI_MODEL = 'your-code-and-vision-capable-model'
$env:OPENAI_REVIEW_MODEL = 'your-vision-capable-model' # optional
.\start_windows.bat
```

The scripts do not install/start Docker Desktop silently. For API mode, keys are backend environment variables; enter them in your local shell/session or your OS credential-backed launcher, never into a project or frontend. `.env` files are ignored but not automatically loaded. A ChatGPT subscription does not provide OpenAI API credits. Pick models that support structured outputs; references and review also need image input support. API/image usage incurs provider charges.

For local generation select Ollama and an installed coding model. Set `OLLAMA_URL` only to a loopback HTTP endpoint. Image references require a vision-capable Ollama model. Auto Review uses the selected OpenAI API or ChatGPT subscription provider; the UI disables it when Ollama is selected. Generation and review model names are configurable rather than hardcoded.

## Dashboard workflow

1. Open `http://127.0.0.1:8765` and select **Code Motion**.
2. Choose provider/model. Describe a scene and set duration, aspect ratio, fps, resolution and visual preset. Optional **Let AI choose duration and format** interprets those settings and a beat structure from the prompt. Leave it off for exact manual settings.
3. Upload screenshots, images, sanitized SVG artwork, fonts and sound effects. Upload a soundtrack separately. Raster references are sent as resized images to the provider; SVG markup and font aliases are provided as design context. Follow the rights applicable to your uploaded assets. Fonts become `ReferenceFont0`, `ReferenceFont1`, etc.
4. A timing map is an array of events: `[{"time":0.5,"label":"title enters"},{"time":2,"label":"impact"},{"time":4,"label":"final reveal"}]`. Seconds convert to exact rounded frame indices and enter the generation prompt. The soundtrack uses a trusted Remotion Audio wrapper. Beat maps guide generated code; they are not an automatic beat detector or a guarantee that an AI follows every event correctly.
5. Generate a preview at up to 640 pixels on its longest edge, with the saved composition's fps and duration. Generation retries validation/render failures at most twice. Full resolution uses the same saved code and metadata.
6. Optionally enable Auto Review. It samples the beginning/end, evenly distributed frames, model-suggested dense moments and beat boundaries. The selected OpenAI provider returns concrete frame-specific feedback; the studio permits 0–3 visual revisions, independently of validation repairs. Each revision retains a previous preview for comparison. Failed visual revisions restore the last validated code/preview. Review remains advisory; unresolved feedback is visible, never disguised by a quality score.
7. Inspect the video, notes and logs. Revise with an additional prompt, regenerate, or return to a saved job. **Tick manual approval** before exporting. Export is locked to that preview's metadata/assets/code; make a new preview to change them. Saved styles accept your typography/color/layout/motion direction, including notes from a successful scene.

Default presets cover documentary graphics, talking-head overlays, finance charts, cinematic titles, and vertical Shorts/Reels. Supported base dimensions: 1280×720, 1920×1080, 3840×2160, 1080×1920; portrait/square aspect selections adapt those dimensions. 24, 30 and 60 fps appear in the UI. All movement must use frames, spring/interpolation/easing; masks, SVGs, layers, parallax and camera pushes are expressed in generated JSX. Scenes are constrained to React and the supported Remotion APIs rather than arbitrary npm dependencies.

## Resolve exports

| Format | Purpose | Alpha |
| --- | --- | --- |
| H.264 MP4 | Normal Resolve footage | No |
| High-quality MP4 | H.264 CRF 16 | No |
| ProRes 4444 MOV | Overlays; PCM audio when present | Yes, `yuva444p10le` encoding |
| PNG sequence ZIP | Exact numbered frames; `timing.json` | Yes |
| Editable Remotion project ZIP | TSX, root, approved assets and pinned dependencies | Preserved in scene settings |

MP4 is rejected for transparent scenes. Browser previews are MP4 and cannot display genuine alpha. ProRes export checks both the encoded alpha pixel format and decoded midpoint transparency; revise a scene that paints an opaque background. PNG export verifies frame count, dimensions and RGBA when requested. FFprobe verifies final movie dimensions, fps and duration. PNG sequences carry their frame rate in `timing.json`; import them as an image sequence in Resolve and set the clip rate accordingly. Soundtrack is in the project's public assets; PNG sequences do not embed audio.

An editable project is executable code: review it before `npm install`/`npm start` outside the studio sandbox. The studio never runs install instructions authored by a model. Check Remotion's current licensing terms for your use: https://www.remotion.dev/license

## Reliability and limits

- `CODE_MOTION_TIMEOUT` defaults to 900 seconds per worker run, including bundle, render and samples. API calls have 180-second timeouts; Codex generation has a 300-second timeout. Cancelling an in-flight provider request suppresses subsequent work but cannot interrupt that HTTP call immediately.
- `CODE_MOTION_MAX_JOB_BYTES` defaults to 4 GiB; the worker's output is checked every two seconds. Reduce resolution/duration for large PNG sequences. Containers have 4 GiB RAM, two CPUs, 256 processes and bounded temporary storage.
- One rendering pipeline runs at a time. Cancellation and application shutdown remove the named container, rather than merely killing its Docker client.
- Static validation catches many mistakes, not every JavaScript trick. Docker isolation assumes a maintained Docker/kernel/Chromium installation; this is a local studio, not a public multi-tenant render host.
- Objective checks cover syntax/types, allowed assets/imports, output metadata, transparency and nearly uniform sampled frames. Vision checks cover visible readability/layout/style defects. Still-frame review cannot establish full temporal smoothness, numerical truth or exact audio sync. Manual review is always required.
- Uploaded SVGs reject active content, external resources and entities. Uploads are limited to 25 MB, raster images to 20 megapixels, references to 12, and scenes to 60 seconds. Cross-origin writes and path traversal are rejected.
- A reference's timing, sound, lighting and depth can be inferred only from the material actually supplied. A screenshot does not contain motion timing. Supply a detailed prompt/timing map for that information.

## Test examples and reproduction

Checked-in TSX scenes under `code-motion/examples/` are **trusted test fixtures**, not results of a live AI call.

| Test | Example prompt | Fixture / settings |
| --- | --- | --- |
| A | “An eight-second financial line graph grows from $0 to $1 million over 35 years; show a year counter and labeled illustrative curve.” | `financial.tsx`, 1280×720, 24 fps, 8 s |
| B | “THE COST OF LIVING, six seconds, layered cinematic typography with spring reveals and a gentle push.” | `kinetic.tsx`, 1920×1080, 24 fps, 6 s |
| C | “Three-second transparent credit card overlay with a $500 transaction and downward arrow.” | `overlay.tsx`, 1280×720, 24 fps, 3 s; ProRes and 72 PNGs |
| D | “Five seconds: title enters at 0.5 s, impact at 2 s, final reveal at 4 s.” | `audio.tsx`, 1280×720, 24 fps; three generated audio hits and frame timing map |

```bash
python -m unittest discover -s tests -v
npm ci --prefix code-motion
npm test --prefix code-motion
# Browser integration, using Playwright's browser:
cd code-motion
npx playwright install --with-deps chromium
PLAYWRIGHT_USE_DEFAULT=1 npm run test:dashboard
cd ..
# Production render pipeline with a mocked provider and actual offline Docker rendering:
docker build -t motion-studio-remotion:1 code-motion
CODE_MOTION_DOCKER_TESTS=1 python -m unittest discover -s tests -p test_code_motion_docker.py -v
```

The GitHub workflow builds the container and uploads its example previews/exports as `code-motion-example-renders`. Docker integration covers generation, preview, revision and all export types with a mocked provider. It does not need API keys. Live OpenAI generation/vision quality needs your own API account.

For developer diagnostics only, `cd code-motion && npx remotion browser ensure && npm run smoke` renders checked-in fixtures directly on the host into `code-motion/smoke-output/<fixture>/`. This is never reachable through the application and is not an unsafe fallback for model code. On hosted runners that deny OS interface enumeration, that test script substitutes loopback interface metadata; the production worker has no such shim. See `docs/VALIDATION.md` for the recorded results.
