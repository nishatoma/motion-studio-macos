# Validation record — 2026-10-13

## Passed in the available Linux environment

- Python: **57 tests run, 56 passed, 1 skipped**. The original 37 regression tests all passed. New tests cover settings/timing maps, metadata planning, provider requests, asset validation, upload/path safety, local HTTP token/origin checks, byte-range downloads, isolated-worker command construction/cleanup, bounded repairs, cancellation, persisted jobs/styles, revision/rollback, alpha approval/export restrictions, editable ZIP export and real rendered MOV verification.
- Node TSX validation: **20/20 passed**, covering valid examples, forbidden imports, network/DOM/execution capabilities, timers/CSS motion, dynamic imports and asset paths.
- Playwright dashboard integration: **passed** for third-tab navigation, existing tabs, provider/settings, saved styles, preview controls, approval gate and export link. Render-job responses were mocked; style writes and page serving used the real Python backend.
- Remotion fixture rendering: **passed** using checked-in trusted TSX scenes, with real Chromium, media encoding and FFprobe checks. These are not AI-generated test results.
- Real MOV alpha validation: decoded alpha contains transparent pixels; ProRes pixel format includes alpha. PNG sequence contains 72 RGBA frames at 1280×720.
- Audio fixture: three supplied synthetic soundtrack hits at 0.5/2/4 seconds, with a matching exact-frame timing map and an encoded audio stream. Decoded audio energy checks passed at all three event times. Generated spring entrances use the corresponding frame indices; there is no general automatic audio/visual synchronization verifier.
- Production dependencies: `npm audit --omit=dev --audit-level=high` reported **0 vulnerabilities** at validation time.
- Python/JavaScript syntax, shell script syntax and `git diff --check` passed.

| Render | Dimensions | FPS | Duration | Encoded pixel format |
| --- | --- | --- | --- | --- |
| A — Financial graph | 1280×720 | 24 | 8.000 s | yuv420p |
| B — Kinetic typography | 1920×1080 | 24 | 6.000 s | yuv420p |
| C — Transparent credit card | 1280×720 | 24 | 3.000 s | yuva444p12le (ProRes 4444, alpha) |
| D — Three audio events | 1280×720 | 24 | 5.013 s container; 120 video frames | yuv420p + AAC |
| 4K metadata check | 3840×2160 | 24 | 1.000 s | yuv420p |
| Vertical metadata check | 1080×1920 | 24 | 1.000 s | yuv420p |

The ProRes encoder is configured with `yuva444p10le`; FFprobe reports the decoded ProRes stream as `yuva444p12le`. Both preserve alpha. The audio MP4 container is 13 ms longer due to AAC packet padding; the video remains exactly 120 frames at 24 fps.

Representative graph, typography and overlay frames were visually inspected. The financial fixture's counter follows its illustrative curve. It does not claim that a particular contribution or return achieves the illustrated result.

## Not tested here

- **Actual Docker image build and production sandbox rendering:** no Docker executable/daemon in this environment. A separate opt-in integration test and GitHub Actions workflow build the image and run A–D through the production Python pipeline with a mocked provider. Those results must be checked on GitHub or locally; they are not included in the passed local tests.
- **Live OpenAI or Ollama generation/reference analysis and OpenAI visual-review quality:** no configured provider key/service. API shapes, repair/review control flow and rollback were tested using mocked provider responses. Model output quality, model capability/access and API billing require a real account.
- **macOS/Windows installer execution, Apple silicon Docker builds, and Resolve import/playback:** this host runs Linux. Platform scripts were updated; macOS shell syntax and existing Windows path/setup regression tests passed. Actual installation and Resolve import need checks on those systems.
- **Uploaded-font and reference-image aesthetics across arbitrary inputs:** files/manifests and generation context are implemented; live provider design interpretation is untested. Raster uploads, SVG active-content rejection and approved asset paths are covered by tests.
- **30/60 fps media outputs, long 4K scenes, arbitrary AI-generated code and complex supplied soundtracks:** controls and frame math are implemented, but recorded media tests use 24 fps and short examples.

The hosted runner denies OS interface enumeration. The **fixture-only** render test substituted loopback interface metadata for Remotion's port discovery. The production application/worker has no such shim and still requires Docker. This accommodation changes neither the scene code nor Remotion's frame renderer.

## Example files and local reproduction

Run `cd code-motion && npx remotion browser ensure && npm run smoke` for trusted developer fixtures. Results appear under `code-motion/smoke-output/{financial,kinetic,overlay,audio,4k,vertical}/`, including `preview.mp4`, full-resolution `animation.mp4` or `animation.mov`, sampled PNGs and the overlay PNG sequence. A machine needs Chromium's system libraries for this developer test; the normal application uses the Docker image instead.

Run the opt-in Docker tests described in [CODE_MOTION.md](CODE_MOTION.md) to validate the actual application rendering boundary. GitHub Actions uploads examples from that pipeline as a downloadable workflow artifact.

## Subscription and Windows-readiness follow-up

Local follow-up checks: 67 Python tests run, 66 passed and the Docker integration skipped; 20 Node validation tests passed. New tests cover ChatGPT versus API authentication, optional Codex default model, schema/image transport, stripped API credentials, disabled tools, no API fallback, same-provider vision review, native Windows tool discovery and distinct Docker readiness states. The installed pinned CLI's real help/feature list and unauthenticated login-status command were checked. Browser tests cover subscription selection and refresh controls in addition to the prior preview/approval/export flow.

Live ChatGPT browser sign-in and subscription-backed inference cannot be completed in this environment without the user's account. The Windows fixes were tested through simulated installation paths and process responses; actual Windows setup still needs a check on the user's PC. Rendering behavior is unchanged; the original Docker integration passed in GitHub Actions run 38441216027.

## Sign-in routing and model-picker follow-up

Local checks: **73 Python tests run, 72 passed, 1 Docker opt-in test skipped**; **20 Node validator tests passed**; the expanded Playwright dashboard test passed. New checks exercise the real token-protected sign-in HTTP route (CLI login mocked), aliases/trailing query paths, account/model routes, API version handshake, missing CLI errors, paginated stdio model discovery, process cleanup, model-catalog caching/fallback, and exact selected-model transport to Codex. Browser checks select GPT-5.6 Sol for generation, GPT-6.1 Sol for a revision, a custom API model ID, and exercise stale-server and missing-login-route restart guidance.

The pinned native Codex CLI's actual stdio `initialize` / `model/list` exchange succeeded in a temporary unauthenticated profile and returned eight valid model entries, including `gpt-5.6-sol`. This validates the protocol integration, **not** access to those models with a user's subscription. Live browser OAuth, account-specific catalog availability and subscription inference remain untested. The render engine is unchanged; the complete GitHub workflow additionally builds and tests the production Docker renderer after this branch is pushed.
