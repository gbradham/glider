# GLIDER Code Review

**Repository:** `/Users/garrettbradham/glider` — General Laboratory Interface for Design, Experimentation, and Recording
**Reviewed:** 2026-04-20
**Scope:** Whole repository (~40k LOC Python)
**Emphasis:** Correctness & bugs • Hardware safety • Architecture & tech debt
**Modules covered:** `glider.core`, `glider.hal`, `glider.vision`, `glider.nodes`, `glider.gui`, `glider.agent`, `glider.serialization`, `glider.plugins`, `tests/`

---

## Summary

GLIDER is a well-structured scientific instrumentation app with several genuine strengths: a clean PinManager abstraction that guards against pin conflicts, a coherent session serialization layer with schema validation, consistent use of `logging.getLogger(__name__)` with zero `print()` calls, no `eval` / `exec` / `pickle` / `yaml.load` / `shell=True` anywhere in the codebase, and thoughtful use of asyncio for hardware I/O.

The review surfaced issues clustered in three areas:

1. **Hardware-safety gaps in shutdown and experiment-abort paths** — per-device exceptions during safe-state transitions are caught and logged but the session still advances to READY, and several shutdown calls have no timeout so a hung serial/I2C device can stall the event loop.
2. **An LLM-agent tool-call surface that lets the model mutate hardware during a running experiment without confirmation** — `auto_execute_safe=True` by default, and only `CLEAR_FLOW` / `REMOVE_BOARD` require confirmation.
3. **A plugin loader that runs arbitrary Python from `~/.glider/plugins/`** — not a security surprise (plugins are trusted by design) but worth documenting because a buggy third-party plugin can leave hardware in an undefined state.

Test coverage is the single biggest tech-debt item. Three of the most critical modules — `camera_manager.py` (~2000 LOC), `data_recorder.py`, and `hardware_manager.py` — have **no direct unit tests**.

**Verdict:** Ready to iterate on; not ready to run unattended overnight experiments without addressing the Critical and High items below.

---

## Critical findings

| # | File | Line(s) | Issue |
|---|------|---------|-------|
| C1 | `src/glider/core/glider_core.py` | 688–696 | `_set_all_devices_low` swallows per-device shutdown failures but still advances state to READY |
| C2 | `src/glider/core/hardware_manager.py` | 209–215 | Device shutdown loop has no timeout; a hung device stalls all subsequent shutdowns |
| C3 | `src/glider/agent/agent_controller.py` | 275–282 + `agent/actions.py` 63–66 | Agent can mutate hardware during a running experiment; `DANGEROUS_ACTIONS` covers only 2 of ~10 mutating tools |
| C4 | `src/glider/plugins/plugin_manager.py` | 299–322 | `exec_module` runs arbitrary Python from `~/.glider/plugins/`; a crashing plugin's `setup()` can leave hardware in an undefined state |

### C1 — Per-device shutdown failures are silently logged and the session transitions to READY

```python
async def _set_all_devices_low(self) -> None:
    for device_id, device in self._hardware_manager.devices.items():
        try:
            if hasattr(device, "shutdown"):
                await device.shutdown()
        except Exception as e:
            logger.error(f"Error setting device {device_id} to safe state: {e}")
```

**Why it matters.** This is the path run after an experiment stops or aborts. If a PWM output controlling a heater, a servo, or a relay raises on shutdown (serial write failed, board disconnected), the exception is logged and the loop continues. The caller in `stop_experiment` immediately sets `self._session.state = SessionState.READY`, signaling the UI and downstream logic that the system is safe — but at least one output might still be driving.

**Fix.** Track per-device shutdown success. If any device fails its safe-state transition, transition the session to `ERROR` (or a new `UNSAFE` state), surface it to the UI, and keep the board connected so the user can attempt a manual recovery before powering down. Consider also issuing a board-level `set_all_pins_low()` as a belt-and-suspenders fallback that doesn't depend on per-device implementations behaving.

### C2 — No timeout on `device.shutdown()` during board disconnect

```python
devices_to_shutdown = [d for d in self._devices.values() if d.board.id == board_id]
for device in devices_to_shutdown:
    try:
        await device.shutdown()
    except Exception as e:
        logger.warning(f"Error shutting down device {device.id}: {e}")
```

**Why it matters.** `device.shutdown()` awaits a serial (telemetrix) or I²C write. If the board has already gone dead physically (USB cable yanked, Pi crashed), the underlying I/O can block indefinitely. The `disconnect_board` coroutine itself then hangs, which blocks the Qt event loop via qasync, which freezes the UI — exactly when the operator most needs the UI responsive.

**Fix.** Wrap each `await device.shutdown()` in `asyncio.wait_for(..., timeout=2.0)`. On timeout, log a warning and proceed to the next device. Consider using `asyncio.gather(*[wait_for(d.shutdown()) for d in devices], return_exceptions=True)` to shut down in parallel.

### C3 — Agent can reconfigure hardware mid-experiment

The tool dispatcher `HardwareToolExecutor.execute` (`agent/tools/hardware_tools.py:190`) routes to `_execute_add_device`, `_execute_remove_device`, `_execute_connect_board`, `_execute_disconnect_board`, etc. I grep'd for `session.state`, `is_running`, and `SessionState.RUNNING` in `agent/tools/` — **zero matches**. And in `agent_controller.py`:

```python
if self._config.auto_execute_safe:
    for action in batch.actions:
        if not action.requires_confirmation:
            action.confirm()
            result = await self._execute_action(action)
```

Combined with:

```python
DANGEROUS_ACTIONS = {
    ActionType.CLEAR_FLOW,
    ActionType.REMOVE_BOARD,
}
```

**Why it matters.** With `auto_execute_safe=True` (the default, `agent/config.py:43`), the model can call `remove_device`, `disconnect_board`, `add_device`, `set_pin_mode`, `write_digital`, etc. with zero user confirmation, including while an experiment is actively recording. A hallucinated or adversarially-prompted "let me just reconfigure pin 7" during a live trial would drop outputs and corrupt the data timeline.

**Fix.** Two changes, both small:
- Gate all hardware-mutating tools on `core.session.state not in (RUNNING, PAUSED)`. The executor should return a structured error (`{"success": False, "error": "experiment is running"}`) that the agent can surface to the user.
- Expand `DANGEROUS_ACTIONS` to include every tool that writes hardware state or modifies device configuration (`REMOVE_DEVICE`, `ADD_DEVICE`, `DISCONNECT_BOARD`, `SET_PIN_MODE`, `WRITE_DIGITAL`, `WRITE_ANALOG`, `WRITE_SERVO`). The current allowlist is too permissive given the blast radius.

Optionally add a rate limiter on the executor (max N calls per 10s) to bound the damage of a runaway agent loop.

### C4 — Plugin loader executes arbitrary Python from a user-writable directory

```python
spec = importlib.util.spec_from_file_location(module_name, Path(info.path) / "__init__.py")
module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module
spec.loader.exec_module(module)
...
if asyncio.iscoroutinefunction(setup_func):
    await setup_func()
else:
    setup_func()
```

**Why it matters.** This isn't a surprise — it's how Python plugin systems usually work, and `~/.glider/plugins/` is the user's own directory, so "security" isn't really the framing. The real risk is **stability and hardware safety**: a plugin's `setup()` runs at startup before any of the safety scaffolding is wired up. If `setup()` raises, the plugin is logged as failed but the rest of the app proceeds as if it weren't there; if `setup()` claims pins or registers callbacks and then partially fails, the hardware manager can end up with dangling state.

Also: `sys.path.insert(0, str(plugin_path.parent))` at line 291 permanently mutates the import path. A plugin whose package shadows a core module name (e.g., `plugins/vision/...`) could intercept subsequent imports of `glider.vision` in subtle ways.

**Fix.**
- Wrap `setup_func()` in a try/except that reverts any partial registration (removed nodes, released pins) on failure. Treat plugin-setup failure as a hard error and refuse to let the plugin register anything.
- Prefer `sys.path` append over prepend, or better, load from an explicit import path without touching `sys.path` (use `importlib.util` fully and add the module to `sys.modules` under a namespaced key like `glider_plugin_<name>`).
- Document a plugin manifest field for required glider version and refuse to load mismatched plugins.

---

## High severity findings

| # | File | Line(s) | Issue |
|---|------|---------|-------|
| H1 | `src/glider/vision/tracking_logger.py` | 350–371 | `csv.writerow` not wrapped in try/except; one failure aborts the log and leaves the file open |
| H2 | `src/glider/vision/camera_manager.py` | multiple (35 hits of `except Exception`) | Overbroad exception handlers in camera init/streaming paths hide real device failures |
| H3 | `src/glider/vision/camera_manager.py` | ~1048, 1229, 1336, 1355, 1378, 1448, 1583 | `cv2.VideoCapture` lifecycle is opened/released across many code paths; at least one FFmpeg-fallback path doesn't release the original capture before retrying |
| H4 | `src/glider/serialization/serializer.py` | 88–90 | `save()` writes directly to the target path — no temp-file + atomic rename, so a crash mid-write corrupts the `.glider` file |
| H5 | `src/glider/core/flow_engine.py` | ~685 | `shutdown()` launches `stop()` via `create_task` without awaiting; errors are lost and cleanup may race with process exit |
| H6 | `src/glider/hal/base_device.py` | ~634–656 | ADS1115 `initialize()` performs I²C probe with no timeout — a disconnected ADC hangs the event loop |
| H7 | `src/glider/gui/controllers/*.py` | many (`self._run_async(...)` pattern) | Fire-and-forget tasks with no handle stored; exceptions inside the coroutine are silently swallowed unless the coroutine catches them itself |
| H8 | `src/glider/hal/base_board.py` | 334 + 341 | Reconnect attempts swallow `Exception` with bare `pass`; if reconnection keeps failing the user gets no signal at all |
| H9 | `src/glider/core/flow_function.py` | 275–284 | On timeout, cleanup runs but internal nodes are not cancelled — they continue driving shared board resources |
| H10 | `src/glider/hal/boards/pi_gpio_board.py` | ~194 | `set_pin_mode` closes the previous gpiozero device in a thread with no timeout; a stuck `.close()` blocks the new allocation, leaving the pin in an undefined state |
| H11 | `src/glider/core/hardware_manager.py` | 256–295 | Device object is instantiated before pin allocation; if allocation fails, any side effects of the device constructor (board bookkeeping, callback registration) aren't unwound |

### H1 — Tracking CSV writes can die mid-row and abort logging

```python
self._writer.writerow([...18 fields...])
```

There is no surrounding try/except in `log_frame`. Any `IOError`, disk-full, or encoding failure (e.g., a `class_name` with a control character) propagates out to the caller, which is a camera frame callback. The callback then stops being invoked on the next frame because the exception cancels whatever task owns it, and the file handle stays open. The UI shows nothing.

**Fix.** Wrap writerow+flush in `try/except Exception`, log with rate limiting (one warning per second to avoid log flood), and expose a `logger_healthy` signal the UI can bind to. Consider flushing only on zone transitions instead of every frame if flush latency is a concern.

### H2 — 35 `except Exception:` blocks in `camera_manager.py`

Of those 35, **9 are `except Exception: pass`** (silent swallow). Many are in the camera-init, codec-negotiation, and FFmpeg-fallback paths. The problem is operational: when a camera misbehaves in production — wrong FourCC, permission denied, device busy — the error is indistinguishable from "this codec isn't supported, let's try the next one."

**Fix.** Replace broad catches with specific exceptions (`cv2.error`, `OSError`, `PermissionError`, `subprocess.TimeoutExpired`). For the fallback loops, log the specific reason each attempt failed so the user can see "tried YUYV → device busy; tried MJPG → not supported; tried FFmpeg → ffmpeg not on PATH" instead of "camera failed."

### H4 — `Serializer.save()` is not atomic

```python
with open(path, "w", encoding="utf-8") as f:
    f.write(schema.to_json(indent=2))
```

If the process crashes or the machine loses power mid-write (it's a lab PC with peripheral disconnects), the user's `.glider` experiment file is truncated. For a tool whose central promise is experiment reproducibility, this is a surprisingly easy foot-gun.

**Fix.** Write to `path.with_suffix('.glider.tmp')`, `os.fsync` the file handle, close, then `os.replace(tmp, path)`. `os.replace` is atomic on POSIX and on Windows.

### H6 — ADS1115 init has no I²C timeout

The Adafruit CircuitPython ADS1x15 driver performs a probe read during construction. If the chip isn't on the bus (loose wire, power flicker), this can hang for the I²C bus's default timeout — which on Linux is effectively unbounded in some drivers. Because `initialize()` runs on the qasync event loop, the UI freezes while it hangs.

**Fix.** Wrap ADS construction in `asyncio.wait_for(asyncio.to_thread(...), timeout=2.0)` and surface `I2CInitError` as a device-level failure the hardware manager can recover from.

### H7 — `_run_async(...)` fire-and-forget pattern loses exceptions

`device_control_controller.py` and `hardware_controller.py` have dozens of call sites that do `self._run_async(self._core.hardware_manager.some_op(...))` without storing the task or attaching a completion callback. If `some_op` raises, the task object's exception is only reported if Python's `asyncio` default exception handler logs it — and in GUI contexts with qasync that often doesn't reach a user-visible surface.

**Fix.** Add a standard wrapper that attaches `task.add_done_callback(self._on_async_error)` and emits a Qt signal on exception. Alternatively, use `asyncio.create_task(..., name="...")` and install a single exception handler on the event loop.

---

## Medium severity findings

| # | File | Line(s) | Issue |
|---|------|---------|-------|
| M1 | `src/glider/core/data_recorder.py` | 269–275, 340 | `self._recording` is a plain bool with no lock; concurrent stop/start is racy, though in practice only called from the GUI thread |
| M2 | `src/glider/core/flow_engine.py` | 314–356 | Node is added to `self._nodes[node_id]` even if `_bind_custom_device_runner` fails — leaves a half-initialized node |
| M3 | `src/glider/core/flow_engine.py` | 416–445 | `create_connection` does not validate that port indices are within bounds of the source/target node definitions; invalid connections silently no-op |
| M4 | `src/glider/hal/boards/telemetrix_board.py` | 25–28 | Global `_analog_callback_registry` holds references to disconnected boards forever (minor leak on long-running sessions with reconnect) |
| M5 | `src/glider/hal/base_device.py` | ~532 | `ServoDevice.shutdown` is a no-op; servo holds last position under an e-stop, which may be mechanically undesirable |
| M6 | `src/glider/vision/camera_manager.py` | ~905, 1100+ | Frame queue `maxsize=2` drops frames silently; no counter or log of drops |
| M7 | `src/glider/vision/cv_processor.py` | 602–604, 332 | `_bytetrack_ages` dict is never pruned when objects disappear; grows unboundedly on long tracking sessions |
| M8 | `src/glider/vision/multi_video_recorder.py` | 184–186, 262–300 | `start()` registers frame callbacks on `MultiCameraManager` but `stop()` does not deregister them |
| M9 | `src/glider/nodes/base_node.py` | 197–201, 332–336 | Callback lists iterated directly; a callback that removes itself mutates the list mid-iteration |
| M10 | `src/glider/nodes/base_node.py` | 287–296 | `to_dict` / `from_dict` have no schema version, so future changes can silently drop state |
| M11 | `src/glider/nodes/base_node.py` | 263–285 | `stop()` has no timeout; a node in a tight loop can block shutdown |
| M12 | `src/glider/nodes/logic/control_nodes.py` | 63–88, 133–136 | `LoopNode._running` is a plain bool; `stop()` during an `await asyncio.sleep(...)` doesn't cancel the sleep — prefer `asyncio.Event` |
| M13 | `src/glider/gui/commands.py` | undo/redo methods | Undo/redo stacks can desync if the underlying operation raises; exception is not handled |
| M14 | `src/glider/gui/dialogs/*.py` | multiple | Dialogs don't override `accept()` to validate required fields; empty-name experiments can be created |
| M15 | `src/glider/serialization/serializer.py` | 400–407 | Schema version check refuses future versions outright; preferable to accept with warning |
| M16 | `src/glider/serialization/serializer.py` | 313–329 | `_extract_node_properties` silently drops non-JSON-serializable values without warning |
| M17 | `src/glider/serialization/serializer.py` | 365–376 | Unknown node types are skipped with a warning but the saved data is lost; should preserve as opaque blob for round-trip |
| M18 | `src/glider/agent/agent_controller.py` | 65 | `AgentConfig.load()` is not wrapped; a malformed config file prevents the agent from starting at all |
| M19 | `src/glider/agent/tools/experiment_tools.py` | 236–255 | Node-type string mapping is hardcoded and duplicates the flow-engine's node registry |
| M20 | `src/glider/gui/controllers/hardware_controller.py` | 111–127 | `device.board is board` comparison doesn't handle `device.board is None` |
| M21 | `src/glider/core/glider_core.py` | 382, 384 + `core/flow_engine.py` 304–307 | Bare `except:` (without `Exception`) catches `KeyboardInterrupt` and `SystemExit` — not what you want in shutdown paths |

### M10 — Node state has no schema version

```python
def to_dict(self) -> dict:
    return {"id": self.id, "name": self.name, "state": self._state, ...}
```

If in v1.1 a node renames `state["duration"]` to `state["delay_seconds"]`, every v1.0 saved experiment silently loses its duration setting. There's a top-level `schema_version` on the `ExperimentSchema` but no per-node versioning.

**Fix.** Either promote schema version to cover node state (requires a registered migration table) or embed a `{"node_schema_version": 1, ...}` field per node and let each node class own its own migration.

### M12 — `LoopNode` uses a bool flag instead of `asyncio.Event`

```python
self._running = True
while self._running:
    ...
    await asyncio.sleep(self._interval)  # <- won't wake early when _running flips to False
```

`stop()` flips the flag but the coroutine sleeps until its next tick. For a 5-second loop interval, experiment abort waits up to 5 seconds. Switch to `asyncio.Event` and `await asyncio.wait_for(event.wait(), timeout=self._interval)` to get both "woke up on time" and "woke up because we were stopped."

---

## Low severity findings

- `src/glider/hal/base_device.py:831` — MotorGovernor pulse duration (50ms) is hardcoded; should live in `settings`.
- `src/glider/core/glider_core.py:220–222` — `state` property returns IDLE when uninitialized; consider a distinct UNINITIALIZED value.
- `src/glider/nodes/vision/zone_nodes.py:136, 140` — Magic output indices (2, 3); replace with named constants.
- `src/glider/agent/tools/hardware_tools.py:38` — Tool enum lists `["arduino", "telemetrix", "raspberry_pi", "pigpio"]` — four strings for what maps to two implementations. Normalize.
- `src/glider/gui/view_manager.py:92–122` — Mode detection cache is never invalidated on display change; fine for single-monitor setups.
- `src/glider/agent/tools/experiment_tools.py:58` + `hardware_tools.py:112` — Tool JSON Schemas use `additionalProperties: True`; tighten to False to reject unknown parameters from the model.
- `src/glider/gui/panels/agent_panel.py:176` — No `setMaxLength(4000)`; user can paste 100 KB and have it silently truncated.
- `src/glider/vision/camera_manager.py:239` — Hardcoded `/proc/device-tree/model` for Pi detection. Fine on target, but document the platform assumption.
- `src/glider/gui/main_window.py:~4930` — `time.sleep(0.01)` busy-wait inside a Qt slot.

---

## Architecture & tech debt

**`main_window.py` is a god object.** The file is ~70 KB and owns menu creation, view switching, dialog routing, controller wiring, runner-mode setup, and node-graph integration. This is the single biggest refactor target. Suggested decomposition:

- A `MenuBuilder` that owns actions and their wiring.
- Push dialog creation through `view_manager` (which already exists) so main_window doesn't import every dialog module.
- Extract runner-mode setup to a `RunnerModeController`.

**Duplication between single- and multi-camera managers.** `camera_manager.py` (~2000 LOC) and `multi_camera_manager.py` have near-identical frame callback routing. Factor the callback/queue machinery into a `FrameRouter` mixin or a shared utility.

**Miniscope control appears in two places.** `camera_manager.py` (~lines 484–573) and top-level `miniscope_stream.py` (~lines 73–133) both implement LED/EWL I²C commands. Consolidate into `glider/vision/miniscope_control.py` and have both callers use it.

**Zone logic is spread across three files.** `vision/zones.py`, `vision/cv_processor.py` (~374–401), and `nodes/vision/zone_nodes.py`. A `ZoneOrchestrator` that owns the tracker, publishes enter/exit events, and is the single source of truth for node subscriptions would simplify reasoning.

**`HardwareNode.bind_device` doesn't validate capability.** A `DigitalOutputNode` can be bound to a device that doesn't support `set_state()`. Replace the implicit "has this method" assumption with a protocol (`typing.Protocol`) per node-device pairing and fail at bind time.

**Per-node schema versioning** — see M10 above. As soon as the node library evolves past v1.0, you'll want this.

---

## Test coverage gaps

The `tests/` directory has reasonable coverage of the low-hanging modules (schema, pin_manager, telemetrix_board, zones, calibration, flow_engine, experiment_session, config, types, base_node), plus one integration test. But the five most load-bearing modules have **no direct tests**:

| Module | Approximate LOC | Direct tests |
|---|---|---|
| `vision/camera_manager.py` | ~2000 | none |
| `vision/tracking_logger.py` | ~500 | none |
| `core/data_recorder.py` | ~400 | none |
| `core/hardware_manager.py` | ~500 | indirect only |
| `plugins/plugin_manager.py` | ~400 | none |
| `hal/boards/pi_gpio_board.py` | ~300 | none |

Priority recommendations:

1. **`data_recorder`** — testable with a `MockBoard` and an in-memory CSV; covers sampling-loop cancellation, metadata layout, and the zone state capture path.
2. **`hardware_manager`** — every safety claim this module makes (pin conflicts rejected, devices cleaned up on board disconnect, shutdown on `remove_board`) deserves a test. All testable with `MockBoard`.
3. **`plugin_manager`** — needs a fixture plugin that raises in `setup()` to verify cleanup on failure (and catch C4 regressions).
4. **`tracking_logger`** — write an end-to-end test that logs 100 frames and confirms the CSV is still parseable after an injected `IOError` on frame 50.
5. **`camera_manager`** — the hardest because of OpenCV, but the non-camera bits (format negotiation logic, capability parsing, frame queue) can be extracted and tested.

A secondary priority is a property-based test (hypothesis) on the serializer: round-trip `dump → load → dump` should be idempotent for any valid session.

---

## What's good

- **Zero `print()` statements**, consistent `logging.getLogger(__name__)` throughout, central setup in `__main__.py`. Logging discipline is above average for a science-instrumentation codebase.
- **No dangerous dynamic eval.** No `eval`, `exec`, `compile`, `__import__` (except the plugin path), `pickle.loads`, `yaml.load` without SafeLoader, or `subprocess` with `shell=True`. The one place this usually goes wrong in Python codebases is clean here.
- **`PinManager`** is a genuinely valuable safety abstraction — catching pin conflicts at allocation time instead of at first-write is the kind of guard rail that prevents whole classes of wiring bugs.
- **`MockBoard`** gives the test suite a real shot at exercising the HAL without hardware.
- **Schema validation** (`serialization/schema.py`) uses detailed `from_dict` validation with path context in error messages — very debuggable.
- **Solid asyncio discipline in most places** — `data_recorder._sampling_loop` uses `create_task` with a stored handle and properly awaits cancellation in `stop()`. That's the pattern the `_run_async` call sites (H7) should be retrofitted to follow.
- **Extensibility via `CustomDevice` and `FlowFunction`** lets users add functionality without forking the core — a well-structured architectural choice that's harder than it looks to get right.
- **0 TODO / FIXME / XXX / HACK comments** in the source tree. Unusual; either the team polishes aggressively or tracks debt externally.

---

## Quick-win checklist

Things that are <1 hour each and materially improve safety / stability:

1. **C1 fix** — in `_set_all_devices_low`, track per-device success; transition to `ERROR` state if any failed, and surface the failure list to the UI.
2. **C2 / H6 fix** — wrap every `await device.shutdown()` and every `device.initialize()` in `asyncio.wait_for(..., timeout=2.0)`.
3. **C3 fix (phase 1)** — add a 3-line guard at the top of each `HardwareToolExecutor._execute_*` method: `if self._core.session and self._core.session.state in (RUNNING, PAUSED): return {"success": False, "error": "experiment in progress"}`.
4. **C3 fix (phase 2)** — expand `DANGEROUS_ACTIONS` to include every hardware-mutating `ActionType`.
5. **H4 fix** — three-line atomic-write helper in `serializer.save()`.
6. **H1 fix** — try/except around the `writerow` in `tracking_logger.log_frame`.
7. **H2 fix** — replace all `except Exception: pass` in `camera_manager.py` with at minimum `except Exception as e: logger.debug("...", exc_info=e)`.
8. **M14 fix** — override `accept()` in `experiment_dialog` to reject empty `name`.
9. **M18 fix** — wrap `AgentConfig.load()` in `try/except` with fallback to defaults.

Start there. Everything else can land in a subsequent pass.
