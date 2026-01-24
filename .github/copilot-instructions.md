<!-- Copilot instructions for Project ORION -->
# Copilot / AI Agent Guidance

This file contains concise, repository-specific instructions to help an automated coding assistant (Copilot) contribute safely and effectively to Project ORION.

**Repository Overview**: Project ORION is a Python-based Raspberry Pi sentinel that uses a camera, multiple sensors, and a YOLO-style object detector to detect threats and send alerts to a backend. Key modules live under `orion/modules/` and the orchestrator is `orion/main.py`.

- **Entry point**: `orion/main.py` — orchestrates modes (`SENTRY`, `INTRUDER`), starts the web server, and manages hardware lifecycle.
- **Configs**: `orion/modules/config.py` — single source of truth for backend URL, model paths, camera and timing constants.
- **Hardware**: `orion/modules/hardware.py` — camera, GPIO sensors, microphone (ADS1115), and GPS mock.
- **AI**: `orion/modules/ai_engine.py` — OpenCV DNN YOLO integration, detection parsing, and debugging toggles.
- **Comm**: `orion/modules/communication.py` — backend register/alert/status endpoints and payload format.
- **Web**: `orion/modules/web_server.py` — Flask streaming and control endpoints, optional ngrok tunneling.

**Goals When Editing Code**
- Preserve the single-source `config.py` pattern: prefer adding toggles or constants there rather than hardcoding values.
- Keep camera and hardware lifecycles safe: use `CameraManager.initialize()` / `.release()` and honor the `lock` patterns in `hardware.py`.
- Avoid blocking the camera thread: network calls (alerts, registration) must remain asynchronous or run in background threads.
- Use existing logging format (python `logging`) and levels; add logs rather than printing to stdout.

**Common Tasks & How To Do Them**
- Add new detection classes: update `THREAT_CLASSES` in `modules/config.py` and ensure `ai_engine._parse_detections` mapping remains consistent with `coco.names`.
- Change model files: update `YOLO_WEIGHTS`, `YOLO_CONFIG`, and `YOLO_CLASSES` in `modules/config.py`. Ensure paths are correct relative to package root.
- Add a new Flask endpoint: update `VideoServer._setup_routes()` in `modules/web_server.py`. Keep route handlers lightweight and non-blocking.
- Debug streaming/ngrok: check `NGROK_ENABLED` in `config.py`. If ngrok is unreliable, default to local stream URL for backend registration.

**Testing / Running Locally**
- Use a Python 3 venv: `python3 -m venv .venv && source .venv/bin/activate` then `pip install -r orion/requirements.txt`.
- Run the sentinel: `python3 orion/main.py` from repository root.
- For fast feedback on non-hardware changes, stub hardware with mocks (use the `GPSTracker` mock and avoid initializing GPIO on non-Pi machines).

**Safety & Runtime Notes**
- Network operations should use timeouts and handle exceptions gracefully (see `communication.py`). Do not crash the main loop on backend failures.
- Camera operations must be protected by `CameraManager.lock` to avoid race conditions between streaming and detection threads.
- When adding dependencies, prefer lightweight packages suitable for Raspberry Pi.

**Code Change Guidelines**
- Small, focused changes only: follow the repository style and keepdiffs minimal.
- Use `apply_patch` for edits when acting as an automation agent. Update tests or docs if behavior changes.
- If a change affects runtime behavior (stream lifecycle, alert cadence), add or update a short note in `orion/README.md`.

**What to Ask the Human**
- If a change needs credentials or hardware access (ngrok token, GPIO testing), ask before committing or running hardware-affecting code.
- When uncertain about model format (MindSpore vs ONNX vs YOLO), ask which model the user prefers and whether they want CPU-only inference.

**If Asked About the Model You're Running**
- State: "I am using GPT-5 mini."  

-- End of instructions --
