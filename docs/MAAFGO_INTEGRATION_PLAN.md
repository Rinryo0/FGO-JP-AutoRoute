# MaaFgo / MaaFramework Integration Plan

Status: Phase 0 — architecture and dependency review  
Target branch: `feature/maafgo-framework-integration`

## Goal

Evolve FGO-JP-AutoRoute using the architecture demonstrated by MaaFgo while preserving this repository's existing Windows-native Tkinter application, MuMu ADB connection, Japanese OCR prototype, and fail-closed behavior.

This is an integration plan, not a claim that MaaFramework has already been embedded or that unattended route execution is ready.

## What the repositories currently contain

### FGO-JP-AutoRoute

- Windows-native Tkinter dashboard.
- MuMu / ADB discovery and screen capture.
- RapidOCR + ONNX Runtime based Japanese screen classification.
- Unknown or ambiguous screens remain `UNKNOWN`.
- Route catalogue and local SQLite session/statistics storage.
- GitHub Actions builds a Windows x64 executable; Python is only needed on the cloud build runner.

### MaaFgo

MaaFgo's README describes a different, larger architecture:

- MaaFramework for image recognition and automation pipelines.
- Python agent and custom actions.
- MXU (Tauri 2 + React) as its desktop shell.
- OCR / YOLO / ONNX-based perception and navigation components.
- Separate battle planning, perception, execution, and runtime modules.

For this project, MaaFgo is initially an architectural reference. We should not replace the existing Tkinter shell with MXU unless the owner explicitly chooses that later.

## Recommended integration boundary

Keep the current app and introduce an optional automation-runtime adapter:

1. **UI layer** — retain Tkinter, settings, preview, status, logs, and emergency stop.
2. **Device layer** — retain the existing ADB / MuMu connection and capture implementation.
3. **Perception layer** — keep the current OCR classifier as a diagnostic and fallback signal; add a separate adapter for MaaFramework recognition results.
4. **Task layer** — represent supported screens and transitions as explicit, testable tasks. Unknown states must not trigger actions.
5. **Safety gate** — require a recognized state, sufficient confidence, valid route data, and explicit user start. Keep resource-spending actions manual and retain an immediate stop control.
6. **Packaging layer** — bundle runtime dependencies in the Windows build only after a clean-room build and license review.

## Phased implementation

### Phase 0 — completed by this document

- Inspect both repository structures and current desktop architecture.
- Identify MaaFgo's use of MaaFramework, Python agent modules, and MXU.
- Record the licensing and packaging review required before importing code or assets.

### Phase 1 — dependency spike

- Review the official MaaFramework Python binding/API and its supported Windows distribution method.
- Build a minimal, isolated adapter that can initialize and shut down the runtime without controlling the game.
- Keep the existing OCR path operational if the framework is unavailable.
- Add unit tests for adapter initialization, failure reporting, and clean shutdown.

### Phase 2 — perception bridge

- Translate framework recognition results into the app's existing `ScreenDetection` model.
- Add fixture-based tests for supported screen labels and unknown states.
- Do not permit low-confidence or unknown results to dispatch actions.

### Phase 3 — supervised task integration

- Add only explicitly tested, user-started task transitions.
- Keep a visible task state, log each transition, and preserve the emergency stop.
- Require manual confirmation for resource use and other irreversible choices.

### Phase 4 — Windows packaging

- Pin all runtime versions.
- Include required notices and third-party licenses.
- Verify the packaged EXE on a clean Windows 11 machine without Python installed.
- Publish build artifacts only after CI and manual smoke tests pass.

## Licensing and attribution gate

The current MaaFgo repository's root `LICENSE` file is GNU Affero General Public License version 3 (AGPL-3.0). Its README also identifies separate components and dependencies. Therefore:

- Do not copy MaaFgo source files, assets, models, or data into this repository as part of this initial integration.
- Treat MaaFgo as an architectural reference until a deliberate AGPL-3.0 compliance decision is made.
- Before redistributing a derivative or bundled copy of AGPL-covered code, review the complete license obligations, including source availability, notices, and corresponding-source requirements.
- Review the license of MaaFramework, its Python bindings, MXU, models, and every transitive dependency independently; do not assume they share MaaFgo's license.
- Preserve third-party notices and record exact pinned versions.

This document is engineering guidance, not legal advice.

## Acceptance criteria

- Existing Tkinter app still launches.
- Existing MuMu connection and OCR preview continue to work when the optional runtime is absent.
- Runtime initialization failure is visible and does not crash the app.
- Unknown screen states never dispatch actions.
- Tests cover initialization, shutdown, error handling, and state conversion.
- Windows EXE build remains reproducible and does not require Python on the user's PC.
