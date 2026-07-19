# Changelog

All notable changes to GLIDER are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- LICENSE file (MIT).
- CITATION.cff for academic citation.
- CHANGELOG.md and CONTRIBUTING.md.
- Production-ready README with install, hardware list, troubleshooting.
- `glider/serialization/atomic.py` — `atomic_write_text()` helper used by all save paths.
- ERROR-state modal dialog: when the session enters ERROR (especially after a failed safe-state shutdown), the operator now sees an explicit `QMessageBox.critical` rather than only a status-bar color change.
- Range validation on `CameraManager.set_led_power` and `set_ewl_focus`: out-of-range values now raise `ValueError` rather than being silently clamped in helper code.
- Node-state round-trip: per-node `to_dict` / `from_dict` is now the authoritative serialization path. Node properties (camera index, GPIO pin, threshold, ITI, etc.) round-trip through `.glider` files correctly.
- `RunnerDashboard` is now wired into the main window's runner-mode view; touch widgets (Button, Toggle, Slider, NumericInput) dispatch to the corresponding node methods.
- Unified `ExecNode.exec_output` dispatch: removed the dead `_exec_callbacks` channel; exec outputs now route through `_update_callbacks` with output-name dispatch, fixing six node types that were silently disconnected from downstream execution (ButtonNode, SequenceNode, ToggleNode, ToggleSwitchNode, NumericInputNode, ZoneInputNode).

### Fixed
- Atomic save: all 12 JSON/text save sites in the codebase now use `atomic_write_text()` (temp file + `os.fsync` + `os.replace`). A crash mid-save no longer corrupts `.glider`, calibration, zone, or config files.
- Python version policy unified across `pyproject.toml`, CI matrix, `black` target, `ruff` target, and README — all now `3.11 / 3.12 / 3.13`.
- `pytest-asyncio` configured to `asyncio_mode = "auto"` so contributors' async tests aren't silently skipped.
- C1 (per-device shutdown failures → ERROR state) and C2 (2-second `DEVICE_IO_TIMEOUT_S` on every device I/O) — completed in prior commit, surfaced here for release notes.
- C3 (agent hardware/experiment tools gated on `SessionState.RUNNING/PAUSED/STOPPING`) — completed in prior commit.
- H6 (ADS1115 I²C init now wrapped in 3-second timeout) — completed in prior commit.

### Changed
- CI matrix updated from `3.10/3.11/3.12` to `3.11/3.12/3.13`.
- CI lint/format now scoped to `src tests` instead of repository root (avoids noise on PyInstaller bootstrap artifacts).
- CI `setup-python` action now caches pip dependencies.
- `requires-python` tightened from `>=3.9` to `>=3.11,<3.14` (matches what the codebase actually uses — `match` statements and PEP 604 unions require 3.10+; we standardise on 3.11 as the floor).

### Known limitations (targeted for 0.4.0)
- `flow_engine._propagate_execution` does not yet track spawned tasks; in-flight hardware writes can complete after STOP. Mitigation: the node-level `execute()` re-check is the planned defence in depth.
- `TelemetrixThread.call_method` still uses a blocking 5-second `future.result()`; HAL refactor to wrap once at the bridge is queued for 0.4.0.
- `MockBoard` fidelity rebuild (`inject_hang`, `inject_exception`) is queued; current mock cannot exercise the e-stop / timeout / reconnect bugs.
- Full test coverage build-out (per [code-review-2.md](code-review-2.md) Section 8) remains a priority — current coverage is ~9% of LOC.
- macOS and Windows installer codesigning is not yet in place; users will see "developer cannot be verified" warnings on first launch. Right-click → Open works.

## [0.2.0] — 2026-05-24 (development release; originally packaged as 1.0.0)

Second development release. See [code-review.md](code-review.md) for the engineering baseline review and [code-review-2.md](code-review-2.md) for the pre-release deep review.

### Major features
- Visual flow programming for experimental protocols.
- Direct GPIO/serial/I²C/camera control across Arduino, Raspberry Pi, and PC.
- Multi-camera capture with YOLO + ByteTrack object tracking and zone enter/exit events.
- UCLA Miniscope V4 integration (LED + electrowetting lens focus control).
- Touchscreen-optimised "runner mode" for Pi kiosk deployment.
- One-file `.glider` JSON experiment storage with embedded metadata.
- Live behavior analysis (resting / walking / darting / freezing classification).
- Synchronous CSV logging of every trial event and per-frame tracking position.
- Plugin system for user-supplied node and driver extensions.
