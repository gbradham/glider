# GLIDER Code Review — Pass 2

**Repository:** `/Users/garrettbradham/glider` — General Laboratory Interface for Design, Experimentation, and Recording
**Reviewer pass:** Section-by-section deep review preparing for stable worldwide release
**Started:** 2026-05-24
**Baseline:** [code-review.md](code-review.md) (2026-04-20) — prior whole-codebase review, treated as known baseline. This pass verifies committed fixes, refines still-open findings, and surfaces new issues.

**Sections:**
1. `glider.core` — ✅ complete
2. `glider.hal` — ✅ complete
3. `glider.vision` — ✅ complete
4. `glider.nodes` — ✅ complete
5. `glider.agent` — ⏭ skipped (not properly implemented yet; not a release blocker)
6. `glider.serialization` + `glider.plugins` — ✅ complete
7. `glider.gui` — ✅ complete
8. Tests + packaging + CI — ✅ complete (manuscript skipped per user)

---

# Section 1 — `glider.core`

**Reviewed:** 2026-05-24 · **Files:** 11 · **LOC:** ~5,444

## Summary

- **C1 fix is incomplete.** Only `stop_experiment` was updated; the common-case auto-completion path (`_handle_flow_complete`) discards the failure list and still flips to READY unconditionally. The fix protects the rarer path.
- **C2 fix is partially incomplete.** Every per-device call now has a timeout (✓), but `emergency_stop` is still a serial `for` loop (N×2s worst case for N devices) and the board-level `board.emergency_stop()` immediately after has no timeout at all.
- **3 new Critical findings**, all in the same family — fire-and-forget asyncio tasks in `flow_engine` and `flow_function` that aren't tracked, aren't cancellable on STOP, and aren't re-checked for state. The practical effect: hardware writes initiated just before STOP complete *after* the safe-state transition.
- **M21 (bare `except:`) is genuinely fixed.** Grep returns zero matches.
- All other prior `core` findings (H5, H9, H11, M1, M2, M3) are still present at the same shape.

## Verification of prior fixes

### C1 — INCOMPLETE: `_handle_flow_complete` discards the failure list

`stop_experiment` is correctly updated and transitions to `ERROR` on any failure. But `_handle_flow_complete` — the path invoked when an `EndExperiment` node fires (i.e., the *normal* end of a successful experiment) — does this:

[src/glider/core/glider_core.py:312-317](src/glider/core/glider_core.py)
```python
# Set all devices to safe state
await self._set_all_devices_low()

# Update session state
if self._session:
    self._session.state = SessionState.READY
```

**Why it matters.** Most experiments end by reaching an `EndExperiment` node, not by the operator clicking Stop. The common case still has the original C1 bug: a hung shutdown on a heater/relay logs an error, but the session transitions to READY and the UI signals "safe to power down." The C1 fix protects only the abort path.

**Fix.** Mirror the `stop_experiment` logic: capture the failures list from `_set_all_devices_low()` and transition to ERROR on non-empty failure. Extract the "drive-to-safe-then-set-state" block into a shared helper so both paths can't drift again.

### C1 — UI surfacing gap

`SessionState.ERROR` propagates to a status-label string and a QSS property, but no modal dialog, no audible alert, no "do not power down" prompt, and the failure detail (`device_id`, error message) never leaves `glider_core.py`. To the operator, ERROR after STOP looks identical to ERROR after a generic flow exception.

**Fix.** Add an `on_unsafe_shutdown(callback)` hook on `GliderCore` that fires with the failures list. Bind in `main_window` to a modal `QMessageBox.critical`. Consider adding a distinct `UNSAFE` state (vs. generic `ERROR`) so the UI can make this semantic, not contextual.

### C2 — INCOMPLETE: `emergency_stop` still serializes and unbounded board call follows

[src/glider/core/hardware_manager.py:578-597](src/glider/core/hardware_manager.py)

Per-device shutdowns in `emergency_stop` are wrapped in `wait_for(..., timeout=2.0)` but still in a serial loop, so the worst case for an N-device rig is N × 2s. The very next loop (`board.emergency_stop()`) has no timeout, undoing the C2 guarantee at the board boundary — a hung serial cable / wedged Pi process can stall emergency stop indefinitely.

**Fix.**
```python
await asyncio.gather(
    *[asyncio.wait_for(d.shutdown(), DEVICE_IO_TIMEOUT_S) for d in self._devices.values()],
    return_exceptions=True,
)
await asyncio.gather(
    *[asyncio.wait_for(b.emergency_stop(), DEVICE_IO_TIMEOUT_S) for b in self._boards.values()],
    return_exceptions=True,
)
```
Iterate the result lists positionally for per-entity logging.

### C2 — covered elsewhere: ✓

Every other `device.shutdown()` / `device.initialize()` call site in `hardware_manager.py` is correctly wrapped. Grep across the module confirms zero unguarded calls outside `emergency_stop`'s neighbor.

### M21 — FIXED

Bare `except:` count in `src/glider/core/`: zero. The cited sites now use `except Exception`. Close this finding.

## Critical findings (NEW)

### Critical — `flow_engine.shutdown()` clears `_nodes` before `stop()` can use them

[src/glider/core/flow_engine.py:682-688](src/glider/core/flow_engine.py)
```python
def shutdown(self) -> None:
    """Shutdown the flow engine."""
    logger.info("Shutting down flow engine")
    asyncio.create_task(self.stop())
    self._nodes.clear()
    self._session = None
    self._flow = None
```

**Why it matters.** This is H5 compounded. `shutdown()` is sync, fires `stop()` as a task, then immediately clears `self._nodes`. When the scheduled `stop()` finally runs, it iterates over an empty `_nodes` dict and never invokes any node's `stop()`. Hardware-bound nodes (output nodes still driving pins, sensor-poll loops still spinning) are never told to clean up. Runs on every app shutdown.

**Fix.** Make `shutdown()` `async def`, `await self.stop()`, *then* clear. If a sync entry is required for compatibility, route through `asyncio.run_coroutine_threadsafe(...).result()` so the dict mutation can't precede `stop()` completion.

### Critical — `_propagate_execution` tasks are untracked and run past STOP

[src/glider/core/flow_engine.py:438-445, 464-472](src/glider/core/flow_engine.py)
```python
if self._state == FlowState.RUNNING:
    logger.info(f"Propagating execution: {fn} -> {tn}")
    # Return the task so callers can await it if needed
    return asyncio.create_task(self._propagate_execution(fn, fo, tn))
```

**Why it matters.** Every execution-flow edge schedules a `_propagate_execution` task that is never added to `self._running_tasks` and never stored anywhere. The "return the task so callers can await it" comment is aspirational — the BaseNode callback machinery discards the return value. When `FlowEngine.stop()` cancels `_running_tasks`, in-flight propagation tasks survive and run to completion. `_propagate_execution` does NOT re-check `self._state`, so a `write_digital` or `set_state` call already in flight when STOP fires will complete *after* the safe-state transition. For a heater control node or a relay, this means the safe-state can be immediately overwritten by stale work.

**Fix.**
```python
task = asyncio.create_task(self._propagate_execution(fn, fo, tn))
self._running_tasks.add(task)
task.add_done_callback(self._running_tasks.discard)
```
And at the top of `_propagate_execution`:
```python
if self._state != FlowState.RUNNING:
    return
```

### Critical — Orphan `_update_callbacks` on source nodes when targets are removed

[src/glider/core/flow_engine.py:360-372, 728+](src/glider/core/flow_engine.py)

`remove_node` pops from `self._nodes` and prunes `self._connections` but does NOT walk source nodes' `_update_callbacks` lists to remove callbacks that closure-capture the now-deleted target ID. On the next source-node update, the orphan callback fires `_propagate_execution(..., to_node_id=<deleted>)`, the lookup at line 470 logs an error, and meanwhile the lambda holds strong refs to expected names, indices, and the FlowEngine itself. Memory leak + a behavioral hazard during live-edit-while-running.

**Fix.** Store callbacks per-connection (`self._connection_callbacks: dict[connection_id, callback]`) so `remove_node` / `remove_connection` can walk every source node and remove the specific callback object. Or, give each callback a `.connection_id` attribute and filter-remove on connection deletion.

## High findings

### High — H5 still present (now compounded by Critical above)

Confirmed at flow_engine.py:685. The fix is captured by the first Critical finding.

### High — H9 still present: `FlowFunctionRunner` timeout cleanup leaks tasks

[src/glider/core/flow_function.py:275-287, 438-446](src/glider/core/flow_function.py)

`_cleanup` calls `node.stop()` on internal nodes but the per-connection callbacks spawn `asyncio.create_task(propagate())` on every fire and those tasks aren't tracked. Same disease as the flow-engine bug, scoped to the sub-flow.

**Fix.** Track every spawned task on the runner (`self._tasks: set[asyncio.Task]`), cancel and gather in `_cleanup` before clearing internal nodes. Don't rely on `node.stop()` to indirectly cancel inflight work.

### High — H11 still present, plus a dead-code bug on top

[src/glider/core/hardware_manager.py:269-301](src/glider/core/hardware_manager.py)

Original H11 (device instantiated before pin alloc; constructor side-effects not unwound on alloc failure) is unchanged. Additionally:

```python
# Create HAL device config
HALDeviceConfig(
    pins=config.pins,
    settings=config.settings,
)
```

constructs an object and immediately drops it on the floor. Likely a refactor leftover — the factory builds its own config from the dict.

**Fix.** (a) Validate + reserve pins before constructing the device; commit reservation only after construction; release on any failure. (b) Delete the dead `HALDeviceConfig(...)` call, or fix the factory to accept the typed config instead of re-parsing a dict.

### High — `ExperimentSession.save()` is non-atomic (parallel to H4 in serializer)

[src/glider/core/experiment_session.py:835-836](src/glider/core/experiment_session.py)
```python
with open(file_path, "w") as f:
    f.write(self.to_json())
```

H4 cited the serializer; this is the same bug in a *second* save path reached via `GliderCore.save_session()`. Fixing only the serializer leaves users vulnerable on this route.

**Fix.** Same as H4 — temp file + `os.fsync` + `os.replace`. Extract `atomic_write_text(path, data)` in a shared utility and use it everywhere.

### High — `remove_board` drops devices without releasing pins or notifying nodes

[src/glider/core/hardware_manager.py:233-251](src/glider/core/hardware_manager.py)
```python
device_ids_to_remove = [d.id for d in self._devices.values() if d.board.id == board_id]
for device_id in device_ids_to_remove:
    del self._devices[device_id]
```

`del` bypasses `remove_device`, so pins are never released. Flow-engine nodes that bound to those devices still hold references to orphaned `BaseDevice`s on a disconnected board; the next `execute()` raises an unhelpful error.

**Fix.** Call `await self.remove_device(device_id)` for each device first (which handles release + shutdown), then notify the flow engine to unbind affected nodes.

## Medium findings

| # | File:line | Issue (one-liner) |
|---|---|---|
| M-new-1 | `data_recorder.py:267-275, 324-368` | M1 still present — `_recording` bool race between `stop()` and `record_event()` can flush a closed file (`ValueError: I/O on closed file`) |
| M-new-2 | `data_recorder.py:321-322` | H1-shape bug: no try/except around `writerow`+`flush`; sampling-loop outer except spams 1 ERROR per tick on disk-full or USB yank |
| M-new-3 | `data_recorder.py:134-140` | `_sample_devices` reads serially inside the tick; for 8 devices @ 100ms, easily overruns; no overrun detection, no per-device read timeout |
| M-new-4 | `flow_engine.py:313-326, 356` | M2 still present — failed `_bind_custom_device_runner` only warns; node is still added to `_nodes` and breaks at first execute |
| M-new-5 | `flow_engine.py:374-462` | M3 still present — out-of-range port indices silently degrade to "fire on every update" instead of being rejected |
| M-new-6 | `flow_engine.py:374-462` | `connection_type="data"` is stored but never honored — data edges trigger `_propagate_execution` identically to exec edges; hammers hardware on every value update |
| M-new-7 | `flow_engine.py:545-566` | `start()` flips state to RUNNING *before* the per-node start loop; partial-start has no rollback |
| M-new-8 | `glider_core.py:238-258`, `experiment_session.py:561-565, 599-603`, `flow_engine.py:98-153` | Callback iteration without `list(...)` copy; self-unregistering callbacks raise `RuntimeError: list changed size during iteration` mid-iteration |
| M-new-9 | `experiment_session.py:555-565` | `SessionState` setter accepts any transition; `can_start`/`can_stop` predicates exist but aren't enforced |
| M-new-10 | `glider_core.py:270-274` | `_on_flow_complete` fire-and-forget with no done-callback; an exception in teardown leaves the system without a terminal state |
| M-new-11 | `flow_engine.py:38, 71-75` | `_node_registry` is a mutable class attribute; duplicate registration silently overwrites (no warning); no locking |

The M-new-1 race and M-new-6 (data-edge hammering hardware) are the two worth promoting to High in a re-prioritization.

## Low findings (selected)

- [glider_core.py:780-811](src/glider/core/glider_core.py) — `shutdown()` only auto-stops `RUNNING`; PAUSED/STOPPING/ERROR fall through, may leak open recorders.
- [data_recorder.py:81-89](src/glider/core/data_recorder.py) — `_generate_filename` has second resolution; two starts in same second collide and overwrite.
- [hardware_manager.py:374-408](src/glider/core/hardware_manager.py) — `add_board` doesn't register state-change callback (unlike `create_board`); UI listeners blind to boards added via this path.
- [flow_function.py:276](src/glider/core/flow_function.py) — Hardcoded 60s timeout; `TimingConfig.function_execution_timeout` exists but is not wired up.
- [glider_core.py:204-208](src/glider/core/glider_core.py) — `set_recording_directory` doesn't `mkdir`; recording start with missing dir fails at file-open.
- [data_recorder.py:253](src/glider/core/data_recorder.py) — `self._file = open(...)` outside a managed context; if `_write_metadata` raises, the handle leaks.
- [library.py:62-89, 147-174, 232-266](src/glider/core/library.py) — Three more non-atomic JSON writes (smaller blast radius than session save).
- [glider_core.py:343-371](src/glider/core/glider_core.py) — Six near-identical try/except blocks registering built-in nodes; collapse to a loop.

## Architecture notes

- **Two parallel "stop" pipelines** — `stop_experiment` and `_handle_flow_complete` implement almost-identical cleanup. C1 fix touched one and missed the other (that's exactly how the bug got reintroduced into the common path). Extract `_teardown_experiment(reason)` and route both call sites through it.
- **Fire-and-forget asyncio is the dominant correctness risk in `core`.** `flow_engine._propagate_execution`, `flow_function.make_exec_callback`, `flow_engine.shutdown`, `glider_core._on_flow_complete` — all spawn untracked tasks. Build one helper: `_spawn_tracked(self, coro) -> asyncio.Task` that adds to a tracked set with a done-callback that logs exceptions; replace every `create_task` in this module with it.
- **`_update_callbacks` as the engine↔node integration point is fragile.** Underscore-prefixed list, mutated from both sides, no de-registration API. A `Subscription` object with `unsubscribe()` would let `remove_node` actually tear down its wiring (and close the Critical orphan-callback finding).
- **`SessionState` is semantically overloaded.** ERROR means three different things (connect failed, node raised, post-C1 safe-state transition failed). Distinguish `UNSAFE` so the UI can show different operator guidance for each.
- **`HardwareManager.create_device` is dense bookkeeping that wants a builder.** The dead `HALDeviceConfig(...)` call is a symptom. Validate → reserve → construct → commit, with explicit rollback, makes H11 atomicity natural.

## What's good in this module

- C2 fix is right in shape and complete at every non-emergency-stop site. The `DEVICE_IO_TIMEOUT_S` constant is the right tuning surface.
- C1 fix's structure is correct (failure list, ERROR transition); just needs to be applied to the second call site and surfaced to the UI.
- `DataRecorder._sampling_loop` cancellation discipline (stored task handle, explicit cancel, await for clean teardown) is exactly the pattern the rest of the module should adopt.
- M21 is genuinely fixed — no bare `except:` anywhere in `core`.
- `ExperimentSession` as a pure data model (no I/O, no asyncio) is well-factored — only impurity is `save`/`load`.
- State callbacks already include per-callback try/except — just need the copy-before-iterate fix.
- No dynamic code execution / `pickle.loads` / shell pipelines in this module. Boundary discipline at the core layer is excellent.

**Bottom line for `glider.core`:** structurally sound. The C1 and C2 fixes are directionally right but incomplete — finishing them is a few hours of work. The three new Critical findings (fire-and-forget tasks in the flow engine) are the real blocker for unattended overnight use; they mean STOP doesn't actually halt all in-flight hardware writes. Worth doing before the next release tag.

---

# Section 2 — `glider.hal`

**Reviewed:** 2026-05-24 · **Files:** 9 · **LOC:** ~2,636

## Summary

- **H6 fix (ADS1115 init timeout) is the right shape but incomplete in two ways:** (a) the wrapped `asyncio.to_thread` cancels the await but leaks the underlying thread, which keeps holding the I2C bus handle and the partially-constructed `busio.I2C` instance until the driver eventually returns; (b) the timeout pattern is not applied to any of the other ten device `initialize()` paths in this module, several of which also call into telemetrix/gpiozero blocking constructors without any bound.
- **HAL-owned C2 gap:** `BaseBoard.emergency_stop` is a base-class no-op, and both concrete overrides (`TelemetrixBoard.emergency_stop`, `PiGPIOBoard.emergency_stop`) iterate pins/devices serially with no per-call timeout — exactly the contract Section 1 flagged as broken at the call site in `HardwareManager.emergency_stop`. Fixing the caller alone does not close this.
- **Two new Critical findings:** (1) `PiGPIOBoard.set_pin_mode` closes the prior gpiozero device before constructing the new one, so a stuck `.close()` or a constructor exception leaves the pin in an undefined state with the PinManager bookkeeping desynced from the actual `_devices` dict; (2) `TelemetrixThread.call_method` runs a 5-second blocking `future.result(timeout=5.0)` inside every digital/analog/PWM/servo write, and the async write methods invoke it synchronously — every single board write can stall the qasync loop for up to 5 s on a wedged serial cable.
- **`_initialized` flag is set on success but never cleared on shutdown.** A failed re-initialisation after shutdown leaves the device in a state where `is_initialized == True` but the underlying resource (e.g., ADS1115's `self._ads`) is `None`. Several `shutdown()` paths gate cleanup on `self._initialized`, so second-time shutdown after a failed reinit can write to a half-torn-down resource.
- **Three more Highs:** reconnect-failure exception swallow (H8 unchanged), gpiozero `.close()` has no timeout (H10 unchanged), `set_pin_mode` doesn't validate pin capability before writing (new — Telemetrix happily configures pin 0 as PWM on Arduino Uno), `BaseBoard.emergency_stop` is an abstract no-op that `MockBoard` inherits silently (so the entire test suite cannot catch e-stop regressions), Telemetrix global callback registry leaks closure refs, thread-safety race on `_pin_values`, and `is_connected` property has side effects.
- **Module-wide finding:** `TelemetrixThread._run` reassigns `sys.stdout = NullWriter()` to suppress telemetrix's `print()` calls. `sys.stdout` is process-global; every other module's `print()` (and Python's default traceback printing for unhandled exceptions on other threads) is silently swallowed for the life of the process.
- **`PinManager` remains the bright spot of this module** — its allocation-time conflict detection is the cleanest safety abstraction in the codebase. The bugs around it are at the call sites (boards mutating `_devices` directly, `HardwareManager.remove_board` bypassing it), not in the abstraction itself.

## Verification of prior fixes

### H6 — PARTIAL: timeout shape correct, but I2C thread leaks and pattern is not generalised

[src/glider/hal/base_device.py:629–676](src/glider/hal/base_device.py)

```python
async def initialize(self) -> None:
    I2C_INIT_TIMEOUT_S = 3.0
    def _init_ads():
        import busio, board
        i2c = busio.I2C(board.SCL, board.SDA)  # constructed inside the thread
        ads = ADS.ADS1115(i2c, address=self._i2c_address)
        ...
        return ads
    try:
        self._ads = await asyncio.wait_for(
            asyncio.to_thread(_init_ads), timeout=I2C_INIT_TIMEOUT_S
        )
    except asyncio.TimeoutError as e:
        raise RuntimeError(...) from e
    self._initialized = True
```

**Why it matters.** The fix correctly stops the qasync loop from being blocked on a wedged I2C bus (the UI stays responsive — original H6 symptom resolved). But:

1. **Thread leak on timeout.** `asyncio.wait_for` cancels the awaiter, not the underlying thread. The worker keeps running until the Adafruit driver returns, holding `/dev/i2c-1` and the partially-constructed `busio.I2C` in memory. A user retry then runs a *second* `busio.I2C(board.SCL, board.SDA)` constructor concurrently with the still-blocked first one — `busio.I2C` is not designed for that.
2. **Not generalised.** Every other device's `initialize()` (DigitalOutput, PWMOutput, Servo, AnalogInput, MotorGovernor) is unbounded. The outer `HardwareManager.initialize_device` wraps in `wait_for(..., DEVICE_IO_TIMEOUT_S=2.0)`, but the inner per-call telemetrix path can still cumulatively exceed 2 s on healthy-but-slow hardware (MotorGovernor issues five writes during init), and a wedged cable hits the 5 s `future.result` *inside* the first telemetrix call.

**Fix.** Have `_init_ads` deinit the I2C handle in a `try/except` before returning so a timeout-orphaned thread releases the bus on its way out. Move `I2C_INIT_TIMEOUT_S` next to `DEVICE_IO_TIMEOUT_S` (or new `hal/timeouts.py`) and apply the same `wait_for` to every `BaseDevice.initialize` override that does more than a single board write — ideally via a template method (`_do_initialize` + `BaseDevice.initialize` does the timeout wrap).

### C2 — HAL-owned gap: board-level `emergency_stop` has no per-pin timeout

[src/glider/hal/boards/telemetrix_board.py:566–581](src/glider/hal/boards/telemetrix_board.py), [src/glider/hal/boards/pi_gpio_board.py:311–320](src/glider/hal/boards/pi_gpio_board.py)

```python
async def emergency_stop(self) -> None:
    if not self.is_connected or self._telemetrix_thread is None:
        return
    try:
        for pin, mode in self._pin_modes.items():
            if mode == PinMode.OUTPUT:
                if cap and PinType.PWM in cap.supported_types:
                    self._call_telemetrix("analog_write", pin, 0)
                else:
                    self._call_telemetrix("digital_write", pin, 0)
    except Exception as e:
        logger.error(f"Error during emergency stop: {e}")
```

**Why it matters.** Section 1 flagged that `HardwareManager.emergency_stop` calls `board.emergency_stop()` without `wait_for`. This is the implementation half: even with a caller-side timeout, the first pin's `_call_telemetrix(...)` spawns a `future.result(timeout=5.0)` on the telemetrix thread. If the cable is yanked, the first call blocks 5 s, the next blocks another 5 s. For an 8-output rig that is 40 s of e-stop latency. `PiGPIOBoard.emergency_stop` has the same shape with `asyncio.to_thread(device.off)` per pin. On any exception the loop breaks early and remaining pins are never driven low.

**Fix.**
```python
async def emergency_stop(self) -> None:
    if not self.is_connected:
        return
    output_pins = [(p, m) for p, m in self._pin_modes.items() if m == PinMode.OUTPUT]
    results = await asyncio.gather(
        *[self._safe_drive_low(p) for p, _ in output_pins],
        return_exceptions=True,
    )
    for (pin, _), result in zip(output_pins, results):
        if isinstance(result, Exception):
            logger.error(f"E-stop failed for pin {pin}: {result}")
```
With `_safe_drive_low` wrapping the per-pin write in `asyncio.wait_for(..., 0.25)`. Same for `PiGPIOBoard`. Also shorten the inner `TelemetrixThread.call_method`'s 5 s timeout (or thread a `timeout` parameter through).

## Critical findings (NEW)

### Critical — `PiGPIOBoard.set_pin_mode` close-before-construct leaks ownership and desyncs PinManager

[src/glider/hal/boards/pi_gpio_board.py:179–229](src/glider/hal/boards/pi_gpio_board.py)

```python
# Close existing device if any
if pin in self._devices:
    await asyncio.to_thread(self._devices[pin].close)

if pin_type == PinType.DIGITAL:
    if mode == PinMode.OUTPUT:
        device = await asyncio.to_thread(lambda: gpiozero.DigitalOutputDevice(pin))
        self._devices[pin] = device
```

**Why it matters.** Three concrete failure modes:

1. **Pin leak on close failure.** `self._devices[pin].close` is wrapped in `asyncio.to_thread` with no timeout (H10) and no `try/except`. A stuck `gpiozero.close()` propagates the exception, the function returns before `self._devices[pin]` is overwritten, and the pin stays "claimed" by a dead device. Next `set_pin_mode` tries to close the same dead device again.
2. **PinManager ownership desync.** `set_pin_mode` mutates `self._devices[pin]` directly — there is no path back to `PinManager`. A buggy plugin that grabs a pin without going through PinManager can have its second `set_pin_mode` silently replace the gpiozero handle owned by the first device.
3. **Half-failed device on exception.** If `gpiozero.DigitalOutputDevice(pin)` raises (permission denied, pin already exported), the old device is gone, the new one isn't stored, and `PinManager` still says it's allocated.

**Fix.** Construct first, then swap-and-close:
```python
new_device = await asyncio.to_thread(lambda: gpiozero.DigitalOutputDevice(pin))
old_device = self._devices.pop(pin, None)
self._devices[pin] = new_device
if old_device is not None:
    try:
        await asyncio.wait_for(asyncio.to_thread(old_device.close), timeout=1.0)
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"Failed to close prior device on pin {pin}: {e}")
```
Make `PinManager` the single source of truth for `(pin → device_id)`; have boards consult it before granting writes.

### Critical — Every Telemetrix board write blocks the qasync loop on `future.result(timeout=5.0)`

[src/glider/hal/boards/telemetrix_board.py:144–154, 468–504](src/glider/hal/boards/telemetrix_board.py)

```python
def call_method(self, method_name: str, *args, **kwargs) -> Any:
    ...
    async def _call():
        method = getattr(self._telemetrix, method_name)
        return await method(*args, **kwargs)
    try:
        future = asyncio.run_coroutine_threadsafe(_call(), self._loop)
        return future.result(timeout=5.0)  # BLOCKING
    ...

# And every write:
async def write_digital(self, pin: int, value: bool) -> None:
    self._call_telemetrix("digital_write", pin, 1 if value else 0)  # sync call from async method
    self._pin_values[pin] = value
```

**Why it matters.** `_call_telemetrix` is synchronous; it calls `future.result(timeout=5.0)`. Invoked from `async` methods without `asyncio.to_thread`. `future.result()` is a **blocking** wait — called from the qasync event loop, it blocks the entire UI thread for up to 5 s. On a healthy bus the call returns in microseconds (invisible day-to-day); on a wedged USB cable, every output write freezes the UI for 5 s. The `BaseBoard` docstring promises "the async design ensures non-blocking operation" — this implementation violates that. Compounds the C2 finding above: e-stop on a wedged board = 5 s freeze per output pin, and the operator can't click Disconnect because the UI is frozen.

**Fix.** Wrap the blocking call once at the bridge:
```python
async def _call_telemetrix(self, method_name: str, *args, **kwargs) -> Any:
    if self._telemetrix_thread is None:
        raise RuntimeError("Board not connected")
    return await asyncio.to_thread(
        self._telemetrix_thread.call_method, method_name, *args, **kwargs
    )
```
Then `await self._call_telemetrix(...)` everywhere. Reduce the 5 s `future.result` timeout to ~0.5 s (closer to actual Firmata round-trip).

### Critical — `_initialized` flag is never cleared on shutdown; reinit-after-shutdown leaves devices in a half-state

[src/glider/hal/base_device.py:55, 244, 323, 384, 459, 529, 676, 828, 679–681](src/glider/hal/base_device.py)

```python
async def shutdown(self) -> None:  # ADS1115Device
    """Shutdown the ADS1115."""
    self._ads = None
    # NOTE: self._initialized stays True

# Later guard:
if not self._initialized or self._ads is None:
    raise RuntimeError("ADS1115 not initialized")
```

**Why it matters.** Across every concrete device class, `self._initialized = True` is set on success in `initialize`, but no `shutdown` path resets it. Consequences:

1. **`DigitalOutputDevice.shutdown` and `PWMOutputDevice.shutdown` gate on `self._initialized` to issue safe-state writes.** Second call re-issues the write — wasteful but harmless. After `shutdown → initialize → second shutdown`, if the second `initialize` raised (timeout, disconnect), `_initialized` is True from the first init, so the second shutdown writes via a board that may have been disconnected and reconnected with different pin modes.
2. **`ADS1115Device.is_initialized` is True even after `_ads = None`.** Downstream UI/recorder/agent code that uses `device.is_initialized` to decide whether to query gets a misleading True.
3. **No serialisation between `initialize` and `shutdown`.** Both `async`; `HardwareManager` wraps each in `wait_for` independently. Concurrent firing (agent tool + UI button) has undefined write order on the board.

**Fix.** Add a default `BaseDevice.shutdown` that always clears the flag:
```python
async def shutdown(self) -> None:
    try:
        await self._do_shutdown()
    finally:
        self._initialized = False
```
And add an `asyncio.Lock` per device to serialise `initialize` / `shutdown`.

## High findings

- **High** — H8 still present: [base_board.py:327–335](src/glider/hal/base_board.py) — reconnect attempts swallow `Exception: pass` forever, no backoff, no max retries, no UI surface. **Fix:** log per attempt at WARNING, exponential backoff (5→10→30→60), notify error callbacks, terminal `ERROR` after a max.
- **High** — H10 still present: [pi_gpio_board.py:193–194, 166–171](src/glider/hal/boards/pi_gpio_board.py) — `gpiozero.close()` has no timeout. A stuck close blocks `disconnect()` indefinitely, defeating the C2 fix at the layer above. **Fix:** wrap every `to_thread(device.close)` in `wait_for(..., 1.0)`; remove from `self._devices` either way.
- **High** — `set_pin_mode` doesn't validate pin capability against `BoardCapabilities`. [telemetrix_board.py:407–466](src/glider/hal/boards/telemetrix_board.py), [pi_gpio_board.py:179–229](src/glider/hal/boards/pi_gpio_board.py) — A buggy plugin or hand-edited save can `set_pin_mode(0, OUTPUT, PWM)` on Arduino Uno's serial-RX pin and Telemetrix will dutifully try. `write_servo` similarly skips capability check. **Fix:** add `BaseBoard._validate_pin_for(pin, pin_type)` and call at the top of every mode/write.
- **High** — [base_board.py:349–355](src/glider/hal/base_board.py), [mock_board.py](src/glider/hal/mock_board.py) — `BaseBoard.emergency_stop` is a base-class `pass`. `MockBoard` inherits silently. Every test that exercises `HardwareManager.emergency_stop` against `MockBoard` passes trivially. **Fix:** make `emergency_stop` `@abstractmethod`, implement in MockBoard with `_notify_callbacks(pin, 0)`, add `inject_hang_for_pin(pin, seconds)` so e-stop tests can simulate wedged boards.
- **High** — [telemetrix_board.py:25–28, 367–399](src/glider/hal/boards/telemetrix_board.py) — `_analog_callback_registry` global leaks closure refs. Disconnected board's registered callbacks fire and log `"No board registered"` per analog event. **Fix:** move registry add/remove into `TelemetrixThread.start/stop`, or use `weakref.finalize` so entries can't outlive the instance.
- **High** — [telemetrix_board.py:283, 432, 474, 487, 504, 532, 542, 558–561](src/glider/hal/boards/telemetrix_board.py) — `_pin_values_lock` is taken in 2 places (`read_analog`, `_process_analog_data`); every other writer touches `self._pin_values` without it. `_digital_callback` runs on the telemetrix thread; concurrent `write_digital` on the qasync side races. The "thread-safe" docstring is contradicted by the implementation. `_notify_callbacks` iterates `self._callbacks[pin]` (a list) unlocked → `RuntimeError: list changed size during iteration` if asyncio loop registers concurrently. **Fix:** take the lock on every write/read consistently.
- **High** — [telemetrix_board.py:303–321](src/glider/hal/boards/telemetrix_board.py) — `is_connected` property fires `_set_state(DISCONNECTED)` and every registered state callback as a side effect. Every write begins with `if not self.is_connected:` — so the side-effect runs on every write. **Fix:** make `is_connected` a pure read; move thread-liveness check to a watchdog or `connect()` only.

## Medium findings (full table)

24 findings, including:

- `DigitalInputDevice.on_change` has no unregister (callback accumulation, prevents GC)
- M5 still present — `ServoDevice.shutdown` is a `pass`; servo holds last position under e-stop
- ADS1115 reads (`read_channel`, `read_voltage`, `read_all`) have no timeout (H6 fixed init, not reads)
- `read_all` reconfigures `AnalogIn` per channel — 4× the necessary I2C traffic at 100 Hz
- `register_callback`/`unregister_callback` mutate `self._callbacks[pin]` without lock; `_notify_callbacks` iterates without lock
- `_notify_*` methods use `except Exception: pass`
- `start_reconnect` silently dropped on second call; user has no signal
- **`TelemetrixThread._run` reassigns `sys.stdout = NullWriter()` globally** — process-wide for the daemon thread's lifetime. **This swallows every other module's `print()` and unhandled-exception tracebacks on background threads.** Should use `contextlib.redirect_stdout` scoped to telemetrix calls only.
- `TelemetrixBoard.connect` not idempotent (double-click spawns two threads on same serial port)
- `read_digital`/`read_analog` silently fall back to cached values on error (stale interlock sensors)
- `PiGPIOBoard.connect` doesn't actually contact pigpiod — just an import check
- PiGPIO ignores `DeviceConfig.settings` (PWM frequency, servo pulse widths default-only)
- `_setup_input_callback` never unregisters on disconnect (`call_soon_threadsafe` on closed loop)
- `PiGPIOBoard.emergency_stop` calls `device.off()` on Servos — detaches signal, possibly causing drift
- `PinManager` allocation methods are not synchronised despite "thread-safe" docstring
- `PinManager.clear_all` releases bookkeeping but doesn't reset actual pin hardware state
- `MockBoard.__init__` fires CONNECTED state into empty callback list (lost)
- `MockBoard` doesn't validate pins, doesn't track `_initialized`, doesn't override `write_servo` (inherits NotImplementedError)

Full details in code-review-2.md.

## Low findings (selected)

- Six near-identical `__init__` patterns across device classes; consolidate into `BaseDevice._read_setting(name, default)`
- `DEVICE_REGISTRY` is module-level mutable dict, no registration API
- `create_device_from_dict` loses round-trip on unknown types
- `_reconnect_interval = 5.0` hardcoded; should be settings-driven
- `ARDUINO_UNO_PINS`/`ARDUINO_MEGA_PINS` share pin objects (mutating one mutates the other)
- `_debug_callback_silent` is dead code
- `PinManager.validate_pin_type` defined but never called — opt-in only

## Architecture notes

- **`BaseBoard` does too much** — owns reconnect lifecycle, callback registry, error notification, state transitions, all with shared mutable state and no synchronisation. Extract `ReconnectController`, `CallbackRegistry`, `StateMachine`.
- **Missing "configure pin idempotently" contract.** `set_pin_mode` semantics differ per board (Telemetrix: re-issue is harmless; gpiozero: must close first; mock: just stores). A single per-board cache check at the top would eliminate the H10/Critical-1 PiGPIO patterns.
- **Telemetrix thread bridge is right architecture, wrong implementation.** Running telemetrix in a dedicated thread with its own loop is correct (qasync compat, isolating telemetrix's print-heavy logging). But `_call_telemetrix` being a blocking sync call is the bug; wrap once at the bridge.
- **`PinManager` is the only HAL safety abstraction PiGPIOBoard's `_devices` dict directly contradicts** (boards mutate pin→device bindings without consulting PinManager). Make `_devices` front a unified resource table per board owned by PinManager.
- **`MockBoard` mock-fidelity is the single biggest test debt in this module.** Cannot exercise timeout, threading, callback-loss, or e-stop bugs that matter. Building out `MockBoard` with `inject_hang`/`inject_exception`/history tracking would let the entire H6/C2/H8/Critical-e-stop surface be tested without real Arduino.
- **`_initialized` flag overloads two concepts** — "I have done first-time setup" vs. "I am currently usable." Split into `_initialized_once` and `_currently_open` (or a `_state: DeviceState` enum).

## What's good in this module

- **`PinManager` remains the cleanest safety abstraction in the codebase.** Two-pass allocation (validate-all-then-commit, no partial state) is exactly right.
- **HAL boundary is well-drawn.** `BaseBoard`/`BaseDevice` express the hardware contract cleanly; device-type dispatch via `actions` dict avoids a giant if/elif. New device types are genuinely easy to add.
- **`DeviceConfig` as a typed dataclass** prevents whole categories of dict-typo bugs.
- **H6 fix is directionally correct.** The 3 s `I2C_INIT_TIMEOUT_S` is well-chosen and the error message points the operator at `i2cdetect` — operator empathy this layer should aim for everywhere.
- **C2 fix at the call site is the right shape** — every per-device shutdown bounded by `DEVICE_IO_TIMEOUT_S`. Remaining work is at the HAL implementation side.
- **Telemetrix's threading isolation** is the correct architecture for a library that owns its own event loop. Bugs are in the bridge, not the design.
- **`asyncio.to_thread` is used consistently** in `PiGPIOBoard`. Pattern is right; gaps are the missing timeouts on closes, not the wrapping.
- **No `eval` / `pickle` / `subprocess.shell=True` / `os.system` anywhere in the module.** HAL is where dynamic-code anti-patterns most often creep in; this codebase resists cleanly.

**Bottom line for `glider.hal`:** The abstractions are right; the implementations leak. H6 is partial — timeout works for the UI but the thread leaks and the pattern isn't generalised. The three new Criticals (PiGPIO pin desync, blocking Telemetrix writes, `_initialized` never cleared) all violate the "non-blocking by design" promise of the HAL docstrings and all surface as either UI freezes or hardware-state desync. The `MockBoard` is too anaemic to defend against any of the bugs that matter most in this layer — building it out is the highest-leverage test investment in the entire codebase.

---

# Section 3 — `glider.vision`

**Reviewed:** 2026-05-24 · **Files:** 10 (+ 1 top-level script) · **LOC:** ~6,235

## Summary

- **H1 (tracking_logger) is unchanged and is the single highest-impact bug in this module.** Every `csv.writerow` and `_file.flush()` runs without a try/except. The tracking CSV is the experiment's primary scientific output — one disk-full event, USB-stick yank, or encoding glitch on a track-id name terminates the log silently, leaves the file handle open and the trailer unwritten, and the operator gets no signal until they go to open the file post-hoc.
- **H2 (camera_manager broad excepts) is unchanged in count (35) and shape (11 silent `except: pass`).** The newly-added Miniscope LED/EWL I2C code (commit `d44ea5d`) repeats the same anti-pattern. This is the *science correctness* version of the bug Section 2 found in the HAL — a silent EWL focus set leaves the lens at the wrong voltage, and 30 minutes of subsequent imaging is out of focus.
- **H3 (VideoCapture lifecycle) is unchanged.** The FFmpeg-fallback path in `_try_connect_grayscale_camera` clearly leaks a `VideoCapture` (overwrites `self._capture` without releasing the prior one). At least two other paths in the same function leak on early-return.
- **M6 (frame queue drops) is unchanged.** No counter, no log, no signal — the operator has no idea the CV processor is running on a sub-sample.
- **M7 (`_bytetrack_ages` unbounded) is unchanged.** Pruned only in `reset()`; `_update_trails` correctly prunes adjacent state but overlooked this dict.
- **M8 (multi_video_recorder callback leak) is unchanged.** `start()` registers, `stop()` doesn't deregister.
- **2 new Critical findings:** (1) Miniscope LED/EWL public API accepts unbounded values; clamp is buried in helpers and not consistently applied. (2) The Miniscope frame-grab loop calls subprocess-spawning helpers (`_send_miniscope_i2c_command` → 4× `subprocess.run`, each 2s timeout) from the capture thread itself during the "darkness watchdog" path — up to 8s capture-thread freeze per LED kick.
- **3 new High findings:** frame-callback iteration without lock (same pattern Sections 1/2 found); multi-camera frame timestamps use `time.time()` (NTP step can rewind mid-experiment); video writers released without atomic finalisation (crash mid-stop leaves unplayable mp4).
- **`behavior_analyzer.py` (new module) is solid in shape** — clean, focused, dataclass-based, no OpenCV dep, serializable, ~250 LOC. Three minor issues: `_object_states` not bounded, `update_settings` mutates from GUI thread without lock while `analyze` reads on capture thread, `_classify_state` mutates state in a read-named method.
- **`miniscope_stream.py` at repo root duplicates ~150 LOC** of Miniscope I2C control with `camera_manager.py`. Duplication is verbatim for `create_miniscope_command` and `send_miniscope_config`, but **divergent** for `set_ewl` — the script uses `-127..127` (value = 127 + focus), `CameraManager.set_ewl_focus` uses `0..255` (128 = neutral). A user who calibrates focus in the standalone script and transcribes the number into the GUI gets the wrong physical focus.

## Verification of prior fixes

### H1 — STILL PRESENT: `csv.writerow` has no exception handling

[src/glider/vision/tracking_logger.py:350-371, 374-396, 400-424, 443-457](src/glider/vision/tracking_logger.py:350)

```python
self._writer.writerow(
    [self._frame_count, iso_timestamp, f"{elapsed_ms:.1f}", obj.track_id, ...]
)
...
self._file.flush()
```

Every call site of `self._writer.writerow` and `self._file.flush()` in `log_frame`, `log_event`, and `stop` is unguarded. `_file` is also opened at line 181 without try/except.

**Why it matters.** Tracking CSV is the experiment's *primary scientific output*. `log_frame` is invoked from `CVProcessor._tracking_callbacks` on the capture thread. If `writerow` raises `OSError`, the exception unwinds through the callback dispatch loop, gets caught at cv_processor.py:548 ("Tracking callback error"), and the next frame's tracking tries to write to a half-failed file handle. Meanwhile `_recording` stays True and `is_recording` lies to the UI. On Windows the file handle stays locked. **Science correctness**: an experiment that *appears* to be running cleanly produces a truncated CSV that ends mid-row.

**Fix.** Wrap each `writerow + flush` in `try/except Exception`, log at WARNING with rate-limiting (1/5s), set `self._recording = False` on the *second* consecutive failure (one transient shouldn't abort a 4-hour experiment, but ten in a row mean the disk is gone), expose a `logger_healthy` signal for the UI. Flush only every Nth frame or on zone transitions (currently every frame, dominating perf).

### H2 — STILL PRESENT at same count (35 except-Exception, 11 silent `pass`); NEW Miniscope I2C code repeats the pattern

[src/glider/vision/camera_manager.py:multiple, especially Miniscope helpers ~318-540](src/glider/vision/camera_manager.py)

Counts confirmed by grep: **35 `except Exception` total, 11 followed immediately by `pass`** (lines 194, 1113, 1202, 1242, 1416, 1426, 1476, 1564, 1714, 1722, 1869). Slightly worse than the baseline's 9 silent — two new silent catches were added during the Miniscope LED/EWL work.

```python
def _send_miniscope_i2c_command(device_index, contrast, gamma, sharpness) -> bool:
    ...
    try:
        subprocess.run([...], capture_output=True, timeout=2)
        subprocess.run([...], capture_output=True, timeout=2)
        subprocess.run([...], capture_output=True, timeout=2)
        return True
    except Exception as e:
        logger.debug(f"I2C command failed: {e}")
        return False
```

**Why it matters.** Three problems compounded:

1. **`subprocess.run` doesn't raise on non-zero exit by default.** Only `FileNotFoundError`/`TimeoutExpired` hit the except. A `v4l2-ctl` that exits 1 because the control is unsupported succeeds silently — function returns True even though no I2C transaction occurred. Caller logs "LED set to 50%" while the LED stays off.
2. **Three consecutive subprocess calls, each 2s timeout, no aggregate timeout.** Worst case 6s of capture-thread block per I2C command; `_apply_miniscope_hardware_controls` issues 3+ commands serially.
3. **Return-value chain ignored at most GUI call sites.** `set_led_power` returns the bool but the slider's slot doesn't check it.

**Fix.** Add `check=True` to every `subprocess.run`; catch `CalledProcessError`, `TimeoutExpired`, `FileNotFoundError` distinctly. Audit the return-value chain from `_send_miniscope_i2c_command` up to the GUI; surface failure as a Qt signal.

### H3 — STILL PRESENT: `VideoCapture` leaked in grayscale-fallback path

[src/glider/vision/camera_manager.py:1354-1378](src/glider/vision/camera_manager.py:1354)

```python
self._capture = cv2.VideoCapture(self._settings.camera_index, backend)
if self._capture.isOpened():
    self._capture.set(cv2.CAP_PROP_CONVERT_RGB, 1)
    for _attempt in range(10):
        ret, frame = self._capture.read()
        if ret and frame is not None and frame.size > 0:
            return True
        time.sleep(0.1)
    logger.info("RGB conversion mode also failed")
    # NO RELEASE HERE — capture leaks if we fall through

if sys.platform == "win32":
    ...
    self._capture = cv2.VideoCapture(f"video={device_name}", cv2.CAP_FFMPEG)
    # ^ overwrites the leaked capture from line 1355
```

**Why it matters.** *Operational*. On Windows DirectShow, a leaked `VideoCapture` keeps the USB camera enumerated as in-use; the user has to re-plug to retry. Six similar assignment sites in this function alone.

**Fix.** Add a `self._cleanup_capture()` call before every `self._capture = cv2.VideoCapture(...)` assignment. Better: extract the fallback chain into a generator that yields `(backend, attempt_factory)` tuples and have one outer loop that owns `try/finally cleanup`.

### M6/M7/M8 — all still present

- M6 [camera_manager.py:902, 2075-2080](src/glider/vision/camera_manager.py:902) — silent drops; *science correctness* gap (tracking CSV and video file diverge in frame count). Fix: add `_dropped_frames` counter; switch to single-slot latest-frame holder.
- M7 [cv_processor.py:332, 602-604, 922](src/glider/vision/cv_processor.py:332) — `_bytetrack_ages` only pruned on `reset()`. Fix: add prune block in `_update_trails` mirroring the existing `_trail_history` prune.
- M8 [multi_video_recorder.py:183-186, 262-300](src/glider/vision/multi_video_recorder.py:183) — Fix: call `remove_frame_callback` in `stop()`; add context-manager protocol.

## Critical findings (NEW)

### Critical — Miniscope LED/EWL public API accepts unbounded values; clamp is buried in helpers and not consistently applied

[src/glider/vision/camera_manager.py:1908-1954, 484-540, 668-698, 726-750](src/glider/vision/camera_manager.py:1908)

```python
def set_led_power(self, power_percent: int) -> bool:
    ...
    self._settings.led_power = power_percent  # <-- no validation
    if sys.platform == "win32" and self._capture is not None:
        return _set_miniscope_led_opencv(self._capture, power_percent)
    else:
        return _set_miniscope_led(self._settings.camera_index, power_percent)

def set_ewl_focus(self, focus_value: int) -> bool:
    ...
    self._settings.ewl_focus = focus_value  # <-- no validation
    if sys.platform == "win32" and self._capture is not None:
        return _set_miniscope_ewl_opencv(self._capture, focus_value)
    else:
        return _set_miniscope_ewl_focus(self._settings.camera_index, focus_value)
```

Meanwhile, `CameraSettings.from_dict` accepts any int for `led_power`/`ewl_focus` from a saved JSON file with no validation. Several internal helpers clamp inconsistently — `_set_miniscope_led` clamps `power_percent` to `0..100` and then maps via `int(255 - (power_percent * 255 / 100))` with a second clamp to `0..254` (safe), but `_set_miniscope_led_opencv` uses the looser `power_percent * 2.55` formula. **The cross-helper inconsistency means whether the math is safe depends on which path you're on.**

**Why it matters.** *Science correctness AND hardware safety*. The Miniscope V4 LED is a power LED driven by a digital potentiometer; the EWL is an electrowetting lens whose voltage must stay within manufacturer spec. The clamping is defense in depth and is good, but the public API silently lying about success (returning True after clamping a 999 down to 254) means the GUI slider and the actual hardware drift out of sync — the operator records `ewl_focus=999` in their lab notebook, but the actual focus was 254, and the rep is unreproducible. If the agent (Section 1 C3) is asked to write camera settings via tool calls and that path isn't fully gated, an LLM can set `led_power=200` during a live experiment with no confirmation.

**Fix.** Validate at the public-API boundary, fail loudly:
```python
LED_POWER_MIN, LED_POWER_MAX = 0, 100
EWL_FOCUS_MIN, EWL_FOCUS_MAX = 0, 255

def set_led_power(self, power_percent: int) -> bool:
    if not LED_POWER_MIN <= power_percent <= LED_POWER_MAX:
        raise ValueError(f"LED power {power_percent} outside [{LED_POWER_MIN},{LED_POWER_MAX}]")
    ...
```
Same for `set_ewl_focus`. Validate in `CameraSettings.from_dict` (reject loaded files with out-of-range values; don't silently clamp). Add unit tests proving `led_value ∈ [0, 254]` for every legal `power_percent`, and that `power_percent=101` raises. Where possible, read back the hardware-acknowledged state for confirmation.

### Critical — Miniscope "darkness watchdog" issues I2C commands from inside the capture thread

[src/glider/vision/camera_manager.py:2048-2057, 318-370, 484-540](src/glider/vision/camera_manager.py:2048)

```python
# In _capture_loop, on the capture thread:
if self._settings.miniscope_mode:
    miniscope_frame_count += 1
    if miniscope_frame_count % miniscope_check_interval == 0:  # every 30 frames
        mean_brightness = np.mean(frame)
        if mean_brightness < 1.0:
            logger.warning(
                f"Miniscope darkness detected ({mean_brightness:.2f}) - kicking LED"
            )
            _wake_up_miniscope(self._settings.camera_index)
```

`_wake_up_miniscope` issues four `subprocess.run` calls, each up to 2s timeout — up to 8s of blocking on the capture thread per "kick." During those 8s, no frames are grabbed; at 30fps that's 240 frames buffered or dropped depending on driver. First frame after the kick has a long delay; downstream tracking timing is wrong; the video file has a visible glitch.

Worse: `_set_miniscope_led_opencv` and `_set_miniscope_ewl_opencv` (called from the GUI via `set_led_power`/`set_ewl_focus`) call `cap.set(...)` on the *same* `VideoCapture` the capture thread is `grab()`ing on. OpenCV's `VideoCapture` is not documented as thread-safe; on Windows DirectShow, simultaneous `set(CAP_PROP_*)` and `grab()` can return wrong frames or deadlock.

**Why it matters.** *Operational + science correctness*. An 8-second freeze in the middle of a behavioral assay is visible as "stuck UI" and ruins that trial's data. The race on `cap.set` causes intermittent black/corrupted frames that look like miniscope darkness — triggering *another* watchdog kick that triggers *another* freeze. Death spiral on a marginal LED driver.

**Fix.** Two changes: (1) Move LED-kicking off the capture thread via a `queue.Queue` to a dedicated "miniscope health" thread. The capture thread just records that brightness dropped. (2) Serialise `cap.set` / `cap.grab` with a dedicated lock owned by `CameraManager`, taken in both `_capture_loop` and every public `set_*` method.

## High findings (NEW)

### High — Frame-callback iteration without lock; concurrent `on_frame`/`remove_frame_callback` races

[src/glider/vision/camera_manager.py:903-904, 1797-1809, 2083-2087](src/glider/vision/camera_manager.py:903), [multi_camera_manager.py:283-288](src/glider/vision/multi_camera_manager.py:283)

```python
self._frame_callbacks: list[Callable] = []
self._lock = threading.Lock()
...
def on_frame(self, callback) -> None:
    self._frame_callbacks.append(callback)  # no lock

# In _capture_loop on capture thread:
for callback in self._frame_callbacks:  # no lock, no list() copy
    callback(frame, timestamp)
```

Same bug Sections 1/2 flagged in `core` and `hal`. Most of the time the GUI doesn't register/unregister during streaming, but `VideoRecorder.start` registers via `camera.on_frame` — first time an operator clicks "Start Recording" *during* live streaming, they hit this race.

**Fix.** Iterate over a list copy: `for callback in list(self._frame_callbacks):`. Append/remove sites should take `self._lock`. Better: extract a shared `CallbackRegistry` class (this is the third place in the codebase needing the same primitive).

### High — Multi-camera frame timestamps are `time.time()` wall-clock, not monotonic, not cross-camera synchronised

[src/glider/vision/camera_manager.py:2059, 909](src/glider/vision/camera_manager.py:2059)

Each `CameraManager` instance timestamps frames with `time.time()` independently. NTP step (lab PCs running `chronyd`) can rewind timestamps mid-experiment; no master-sync across cameras; encoded video uses fixed FPS even though actual capture has USB jitter.

**Why it matters.** *Science correctness.* For multi-camera setups (topdown + side, or left/right halves of an arena), post-hoc analysis needs to align frames across cameras. NTP step can swing the delta wildly.

**Fix.** Use `time.monotonic()` for inter-frame deltas; `time.time()` only for the wall-clock anchor at experiment start. For cross-camera sync, capture `time.monotonic()` at the start of every grab cycle in `MultiCameraManager` (have it own the timing). For highest science-correctness, expose a hardware-trigger mode gating OpenCV grab on external TTL.

### High — Video file integrity: writers released without atomic finalisation

[src/glider/vision/video_recorder.py:305-312, 346-397](src/glider/vision/video_recorder.py:305), [multi_video_recorder.py:274-292](src/glider/vision/multi_video_recorder.py:274)

If the Python process is killed before `release()` completes, the .mp4's moov atom is never written and the file is unplayable in standard players (mp4 puts moov at the end by default).

**Why it matters.** *Science correctness*. An overnight 8-hour recording, then the lab PC reboots before the operator clicks Stop (Windows Update, power blip), produces an 8-hour mp4 that won't play. Frames are physically on disk; recovery needs `ffmpeg -movflags faststart` surgery most lab users can't do.

**Fix.** Options in cost order: (1) use Matroska (.mkv) container which is crash-tolerant. (2) Write to `{name}.part`, atomic-rename on stop (same pattern as Section 1 H4). (3) Segmented recording (1 minute per segment) with concat manifest — industry-standard HLS-style; crash loses at most 1 minute. At minimum: wrap `release()` in try/except and log "Recording may be unplayable — recovery path: ffmpeg -i ..." with the pre-formatted command.

### High — `miniscope_stream.py` duplicates Miniscope I2C code AND uses a different EWL focus convention

[miniscope_stream.py:32-133](miniscope_stream.py), [src/glider/vision/camera_manager.py:612-750](src/glider/vision/camera_manager.py:612)

```python
# miniscope_stream.py — set_ewl:
focus = max(-127, min(127, focus))      # -127..127 range
value = 127 + focus                      # neutral=0 -> value 127

# camera_manager.py — _set_miniscope_ewl_opencv:
focus_value = max(0, min(255, focus_value))   # 0..255 range, 128=neutral
```

`create_miniscope_command` ≡ `_create_miniscope_command` (verbatim). `send_miniscope_config` ≡ `_send_miniscope_config_opencv` (verbatim). `set_led` ≡ `_set_miniscope_led_opencv` (logic identical, formatting different). But the EWL conventions are fundamentally different.

**Why it matters.** *Science correctness*. A user calibrates focus with the standalone `miniscope_stream.py` script ("focus = -30 gives me a sharp image"), then types `-30` into the GUI's EWL Focus field. The GUI uses `0..255` semantics: `-30` either fails validation, clamps to 0, or wraps to some other voltage. Recorded experiment is at the wrong focus. Lab notebook says "EWL=-30" — unreproducible.

`miniscope_stream.py` also uses `print()` 24 times (violating the codebase-wide "zero print statements" property), and isn't imported by anything.

**Fix.** Consolidate into `glider/vision/miniscope_control.py` exposing one canonical API. Decide ONE EWL convention (0..255 matches hardware register width; -127..127 is a UX choice the GUI can map at the boundary). Document the convention prominently. Convert `miniscope_stream.py`'s `print` calls to `logging`, or delete the file if subsumed by the camera panel UI.

## Medium findings (24 total)

| # | File:line | Issue |
|---|---|---|
| M-vis-1..3 | (see M6/M7/M8 above) | Three prior open mediums still present |
| M-vis-4 | `behavior_analyzer.py:93, 105-112, 217-224` | `_object_states` unbounded with ByteTrack ID churn; `update_settings` mutates without lock while `analyze` reads on capture thread |
| M-vis-5 | `cv_processor.py:495, 532-554` | `process_frame` takes `_lock` for detect/track but drops it before iterating callback lists; same race pattern |
| M-vis-6 | `tracking_logger.py:181` | `open(self._file_path, "w")` outside context manager and without try/except; partial state on raise |
| M-vis-7 | `tracking_logger.py:474` | Inconsistent `_start_time is None` guards |
| M-vis-8 | `calibration.py:299-322` | Non-atomic JSON save (parallel to H4 in serializer) |
| M-vis-9 | `zones.py:318-322` | Same non-atomic save pattern |
| M-vis-10 | `calibration.py:312-329` | No schema validation on load; no check that calibration resolution matches current camera resolution (silent 3x error) |
| M-vis-11 | `camera_manager.py:188-195, 191-194` | `FFmpegCapture.release` has nested silent excepts; subprocess leaks block next camera open |
| M-vis-12 | `camera_manager.py:1908-1954` | `set_led_power`/`set_ewl_focus` fall through to Linux v4l2-ctl path when `_capture is None` even on Windows |
| M-vis-13 | `camera_manager.py:2049-2057` | Darkness watchdog threshold `mean < 1.0` triggers on legitimate dark frames (mouse in dark phase); should be configurable |
| M-vis-14 | `video_recorder.py:318-331` | `_fix_video_fps` does full read+write of entire file synchronously inside `stop()`; UI freezes for minutes on long recordings |
| M-vis-15 | `cv_processor.py:447-467` | `_load_yolo_model` catches `ImportError` and silently switches backend; user thinks YOLO is running, only sees background subtraction |
| M-vis-16 | `cv_processor.py:629-660` | `tracker="bytetrack.yaml"` literal string; brittle to ultralytics changes |
| M-vis-17 | `multi_camera_manager.py:248-275` | `on_frame`/`remove_frame_callback` not synchronised |
| M-vis-18 | `multi_camera_manager.py:259-269` | `on_primary_frame` overwrite-style storage; `hasattr` code smell; second call overwrites silently |
| M-vis-19 | `camera_manager.py:1759-1780` | `stop_streaming` joins thread with `timeout=2.0` then proceeds even if thread is alive (e.g., blocked in 8s `_wake_up_miniscope`) |
| M-vis-20 | `camera_manager.py:1706-1729` | `disconnect()` race: thread keeps running with released capture → potential segfault on `cap.grab()` on freed handle |
| M-vis-21 | `behavior_analyzer.py:179-193` | `_classify_state` mutates `obj_state.low_movement_frames` as a side effect; should split into `_observe`+`_classify` |
| M-vis-22 | `behavior_analyzer.py:42-44` | Default `dart_threshold = 50.0 px/frame` magic number; should be body_lengths_per_second or normalised |
| M-vis-23 | `zones.py:444-452` | `ZoneTracker.reset` leaves stale keys in `_prev_zone_objects` |
| M-vis-24 | `camera_manager.py:954-1024` | `enumerate_cameras` replaces `sys.stderr = io.StringIO()` and sets `OPENCV_LOG_LEVEL=SILENT` env globally; swallows other-thread tracebacks during the enumeration window (same disease as the HAL telemetrix `NullWriter` finding) |

## Low findings (selected)

- `COMMON_RESOLUTIONS` concatenated with detected can produce duplicate dropdown entries
- macOS uses `cv2.CAP_ANY`; no explicit AVFoundation backend tried — suboptimal latency
- `force_backend: Optional[str]` accepts arbitrary strings; typos fall to "auto" silently
- `calibration.save()` doesn't `mkdir(parents=True)` on parent — confusing FileNotFoundError for new users
- `_max_trail_length = 30` hardcoded; should be a setting (slow-tracking session wants longer trails)
- Default codec `"mp4v"` doesn't decode in some older mobile clients
- `tracking_logger` filename uses second-resolution timestamp; same collision risk as data_recorder
- `MultiCameraManager._enabled` flag is dead code (accessor/mutator only)
- `behavior_analyzer.get_state_color` hardcodes BGR tuples; should live in a shared color-constants module
- `zones.contains_point` allocates a new numpy array per point test — at 8 zones × 4 objects × 30fps = ~1000 alloc/sec
- `miniscope_stream.py` lives at repo root; should be in `scripts/` or `tools/` with a console_scripts entry point

## Architecture notes

- **`CameraManager` is the largest file in the codebase (2125 LOC) and the highest-leverage refactor target after `main_window`.** It owns: enumeration, format negotiation, OpenCV connection, picamera2 connection, FFmpeg subprocess fallback, capture-thread loop, frame-queue, callback dispatch, FPS measurement, Miniscope wake-up, Miniscope LED/EWL controls (v4l2 + OpenCV variants), and `FFmpegCapture`. Suggested decomposition:
    - `vision/camera/enumeration.py` — `enumerate_cameras` + `_get_windows_camera_names`
    - `vision/camera/capture_backends.py` — `FFmpegCapture` and `_try_connect_*` family
    - `vision/camera/capture_thread.py` — `_capture_loop` + queue/callback dispatch
    - `vision/miniscope_control.py` — entire Miniscope I2C family, consumes `miniscope_stream.py`
    - `vision/camera_manager.py` (slim) — orchestrates above
- **`MultiCameraManager` is "many `CameraManager`s in a dict" with different lock discipline.** Consolidate on a shared `CallbackRegistry` or document the lock contract explicitly.
- **Three threads, no clear contract for what runs where.** OpenCV grab thread, Qt event loop, qasync asyncio loop. Callbacks are sync functions invoked on the grab thread; GUI must marshal via `QMetaObject.invokeMethod(Qt.QueuedConnection)`. A `CallbackContext = Literal["sync_fast", "sync_can_block", "async"]` annotation on `on_frame()` would document the policy.
- **Miniscope control lives in three places** (Linux v4l2-ctl, Windows OpenCV-property, `miniscope_stream.py`). Baseline flagged two; count has grown by one.
- **Calibration doesn't validate against the camera it's being used with.** No camera fingerprint; same calibration silently applies to different camera (different lens, different FOV) → wrong tracking distances. Add a `camera_fingerprint` field and warn on mismatch.
- **Recording assumes constant FPS.** `_fix_video_fps` retroactive re-encode is an admission this is wrong. Cleaner long-term: variable-FPS container (Matroska + per-frame timestamps).
- **`behavior_analyzer.py` is the rare clean module** that doesn't need a major refactor — just bounded-dict and thread-safety fixes. Good candidate for the *first* unit test in the vision module's coverage gap.

## What's good in this module

- **`behavior_analyzer.py` is a model new-module addition.** Small, focused, dataclass-based, all-pure-Python (no OpenCV dep), serializable settings, clean separation of analysis from rendering. Can be unit-tested without a camera.
- **`CameraSettings`/`CVSettings`/`BehaviorSettings` all have `to_dict`/`from_dict` symmetry.** Round-trip serialization is straightforward; only issue is missing range validation in `from_dict`.
- **`zones.py` is the cleanest file in `vision/`.** Strict separation of data/state/logic. Polygon point-test using `cv2.pointPolygonTest` is correct. Has direct unit tests.
- **`calibration.py` is similarly clean.** Pure data + simple geometry, no threading, no I/O outside save/load. Resolution-independence via normalised 0..1 coords is the right design.
- **Frame normalisation for grayscale cameras** correctly upcasts 2D Y800 to 3-channel BGR at the boundary, keeping type-check spaghetti out of the rest of the pipeline.
- **`VideoRecorder.start` raises on `VideoWriter` failure** instead of returning False — call site can't accidentally proceed with a None writer.
- **Picamera2 import is lazy** with tri-state cache — the right pattern for an optional dependency that's expensive to import.
- **`_capture_loop` rate-limits its error logging** to one per 30 failures — disconnecting mid-stream produces one warning, not thousands.
- **`FFmpegCapture` quacks like `cv2.VideoCapture`.** Clean duck-typed wrapper; model for how external deps should be wrapped.
- **No `eval`/`exec`/`pickle`/`shell=True` anywhere in the module.** Vision modules that shell out to ffmpeg are often where these creep in; this codebase resists.

**Bottom line for `glider.vision`:** the prior six findings are all still present; H1 (tracking_logger CSV) and the new Critical-1 (Miniscope LED/EWL unbounded values) are the two highest-impact issues — both directly affect *science correctness*, not just operational smoothness. The new Critical-2 (LED kicks from the capture thread) and the three High findings (callback iteration races, wall-clock timestamps, non-atomic video finalisation) are the kind of "works fine until it doesn't" bugs that an overnight unattended run will hit eventually. `behavior_analyzer.py` is the bright spot — a clean new module that didn't break anything during integration. Fixing this module fully means rewriting parts of the 2125-LOC `camera_manager.py`, which is a 1-week refactor more than a 1-hour patch; the *immediate* triage is H1 (4 lines of try/except in tracking_logger) and the public-API range validation on `set_led_power`/`set_ewl_focus` (10 lines). Those two together close the highest-blast-radius science-correctness gaps.

---

# Section 4 — `glider.nodes`

**Reviewed:** 2026-05-24 · **Files:** 14 (+ 4 `__init__.py`) · **LOC:** ~3,475

## Summary

- **The biggest finding in this section is architectural:** GLIDER has *two* callback channels on nodes — `_update_callbacks` (which `flow_engine.create_connection` appends to) and `_exec_callbacks` (which `ExecNode.exec_output` and `ZoneInputNode.exec_output` iterate). The flow engine **never** populates `_exec_callbacks`; the registrar `on_exec` is never called anywhere. **Every node that fires `exec_output(index)` via the inherited `ExecNode.exec_output` produces nothing** — channel B is always empty. Spot-checks via grep confirmed: `_exec_callbacks` is appended-to only in the `on_exec` method (zero call sites), and the channel iteration is empty at runtime. Affected nodes: `ButtonNode`, `SequenceNode`, both `ToggleNode` variants, `ToggleSwitchNode`, `NumericInputNode.submit`, `ZoneInputNode.exec_output`. Working nodes (StartExperiment, Delay, Output, MotorGovernor, CustomDevice, LoopNode._exec_body, WaitForInput, StartFunction, FunctionCall) work *only because* their authors manually overrode `exec_output` to bypass the broken channel and iterate `_update_callbacks` directly.
- **`ZoneInputNode.update_zone_state(...)` is defined but never called anywhere.** Grep returns exactly one hit — the definition. The vision module has zone tracking and the data recorder reads zone states for CSV, but **nothing** dispatches enter/exit events into the flow-engine node. Combined with the channel bug, zone-driven experiments via the visual flow are completely dead.
- **`RunnerDashboard.widget_value_changed` has zero subscribers.** Touch widgets emit → dashboard re-emits → no `connect()` anywhere. The touch UI in the runner mode is functionally a display-only surface; button presses, toggle flips, slider drags never reach any node. For a touchscreen-driven experimental rig (the stated use case), human-in-the-loop control is non-functional.
- **All four baseline node findings (M9, M10, M11, M12) are still present** at shifted line numbers. M12 (LoopNode bool flag vs `asyncio.Event`) is the most operationally significant — STOP-during-loop-delay waits up to the configured interval (potentially 30s for an ITI) before halting.
- **3 new Criticals:** (1) No node `execute()` re-checks engine state, so Section 1's fire-and-forget bug means hardware writes complete after the safe-state transition. (2) Hardware nodes (`DigitalWrite`, `PWMWrite`, `DigitalRead`, `AnalogRead`, `DeviceAction`) call `device.execute_action(...)` with no `asyncio.wait_for` — same bug Section 2 found at the HAL boundary, a wedged Telemetrix freezes every node write for 5s. (3) The dead callback channel (above).
- **3 new Highs:** `ZoneInputNode.update_zone_state` never called (above); Runner Touch widgets are dead in dispatch path (above); `FunctionCallNode` swallows sub-flow timeout and proceeds as if the function completed normally (downstream nodes execute as if injections happened when they didn't — *science correctness*); polling-loop nodes catch generic exceptions and continue silently with no retry cap; hardware nodes don't validate input ranges before writing (same pattern as Section 3 Miniscope finding).
- **22 medium findings** including: two-state pattern bug (`self._state` dict + typed attributes split, round-trip loses changes), `SequenceNode.execute` does `for i in range(4): self.exec_output(i)` — fans out, doesn't sequence; `FlowFunctionRunner` caches end nodes (stale on graph edit); diamond inheritance bug in `ButtonNode` skips `InterfaceNode.__init__`; `HardwareNode.execute` catches exceptions and returns without firing exec output (flow wedges with no propagation path); `TimerNode._timer_loop` busy-loops on persistent input error (eats a CPU core); two `DelayNode`s, two `LoopNode`s, two `ToggleNode`s registered under different names but conceptually the same; `ToggleNode.execute` is `pass` (Toggle/SetOn/SetOff exec inputs visible in UI but never processed).
- **`base_node.py`'s abstraction is mostly clean.** Dataclass-based, sensible hierarchy. Bugs are at the *contract* boundary (callback channels, state-mechanism split, missing capability check), not in the class hierarchy itself.

## Verification of prior fixes

### M9 — STILL PRESENT: callback iteration without snapshot copy

[src/glider/nodes/base_node.py:197-201, 332-336, 411-415](src/glider/nodes/base_node.py:197) + ~20 other unguarded iteration sites across the module.

```python
for callback in self._update_callbacks:   # <-- no list() copy
    try:
        callback(output_name, value)
    except Exception as e:
        logger.error(f"Output callback error: {e}")
```

Same shape Sections 1/2/3 flagged in core/HAL/vision callback registries. Latent because nothing currently self-unregisters during iteration — but the moment a future change adds a fire-once-then-detach pattern (one-shot Wait, conditional Branch with auto-cleanup), every node hits it.

**Fix.** Same recipe — iterate `list(self._update_callbacks)`. Better: extract a shared `CallbackRegistry` helper (now the fourth place needing one).

### M10 — STILL PRESENT and worse than baseline noted: `to_dict` is unused by both serialization paths

[src/glider/nodes/base_node.py:287-296](src/glider/nodes/base_node.py:287), [src/glider/serialization/serializer.py:313-329](src/glider/serialization/serializer.py:313), [src/glider/core/experiment_session.py:347-376](src/glider/core/experiment_session.py:347)

No `node_schema_version`. Worse: `BaseNode.to_dict` is never called by either save path — `serializer.py` reads `node.property_names` (which no node defines) and `NodeConfig` is hand-built in the GUI layer. Three different shapes for the same node state; a migration table cannot be added cleanly because the source of truth is fragmented.

**Why it matters.** *Science correctness.* The first time a node renames a state key (e.g., `DelayNode.duration` → `delay_seconds`), every existing `.glider` file loses its configured value and falls back to the default — silently. Changes the timing of every saved trial.

**Fix.** Consolidate to one serialization path (make `to_dict`/`from_dict` authoritative; route both `serializer.py` and `experiment_session.NodeConfig` through it). Add `_schema_version: ClassVar[int] = 1` per node class plus an `_migrate(state, from_version)` hook.

### M11 — STILL PRESENT: `stop()` has no timeout at any layer

[src/glider/nodes/base_node.py:271-277](src/glider/nodes/base_node.py:271), [src/glider/core/flow_engine.py:595-605](src/glider/core/flow_engine.py:595)

Per-node `stop()` is awaited serially without `wait_for`. `WaitForInputNode.stop` flips `_waiting=False` but the in-flight poll's `await self._device.read()` (which Section 2 showed can block 5s on a wedged Telemetrix) still has to return before the cancellation is observed.

**Why it matters.** *Operational + hardware safety.* For an 8-output rig with 2 polling nodes on a wedged board, `flow_engine.stop()` takes 10s sequentially. During those 10s the UI is frozen *and* the safe-state transition hasn't run yet — outputs continue driving.

**Fix.** Wrap per-node stop in `asyncio.wait_for(node.stop(), NODE_STOP_TIMEOUT_S=2.0)` in `flow_engine.stop`. On timeout, log and proceed — safe-state is more important than polite shutdown.

### M12 — STILL PRESENT: `LoopNode._running` is a bool; `stop()` doesn't wake `asyncio.sleep`

[src/glider/nodes/control_nodes.py:63-88, 133-136](src/glider/nodes/control_nodes.py:63) (note: baseline cited the wrong file path — actual is `nodes/control_nodes.py`, not `nodes/logic/control_nodes.py`)

```python
while self._running:
    ...
    await self._exec_body_async()
    if delay > 0 and self._running:
        await asyncio.sleep(delay)   # <-- not cancellable by stop()
```

**Why it matters.** *Operational + science correctness.* For an infinite loop with 30s ITI, operator-clicked STOP waits up to 30s before exit. The body may have completed and the device is in some intermediate state — and Section 1's untracked propagation tasks from the body are still in flight. Worst case: STOP logged, UI shows STOPPED, 28s later a `DigitalWrite` from inside the body fires HIGH after `_set_all_devices_low` already ran.

**Fix.** Replace `_running` with `asyncio.Event`; use `asyncio.wait_for(self._stop_event.wait(), timeout=delay)` so STOP wakes the sleep. Same treatment for `WaitForInputNode`.

## Critical findings (NEW)

### Critical — Two callback channels; only one is wired to flow engine. Many node types are silently disconnected from downstream execution

[src/glider/nodes/base_node.py:319-336](src/glider/nodes/base_node.py:319), [src/glider/core/flow_engine.py:447-451](src/glider/core/flow_engine.py:447)

```python
# base_node.py — ExecNode:
class ExecNode(GliderNode):
    def __init__(self):
        super().__init__()
        self._exec_callbacks: list[Callable[[int], None]] = []     # <-- channel B

    def on_exec(self, callback: Callable[[int], None]) -> None:    # <-- never called
        self._exec_callbacks.append(callback)

    def exec_output(self, index: int = 0) -> None:
        for callback in self._exec_callbacks:                       # <-- iterates B
            try:
                callback(index)
            ...

# flow_engine.py — create_connection:
if hasattr(from_node, "_update_callbacks"):
    from_node._update_callbacks.append(on_exec_output)              # <-- appends to A only
```

`grep -rn "\.on_exec(" src/` returns zero hits — the registrar is never invoked. The flow engine only knows about `_update_callbacks` (channel A). `ExecNode.exec_output` only iterates `_exec_callbacks` (channel B). Therefore every node whose exec output fires via the inherited `ExecNode.exec_output` produces nothing — channel B is always empty.

**Affected nodes (silently broken):**
- `ButtonNode.press()` → `self.exec_output(0)` → channel B → no-op
- `SequenceNode.execute()` → fires all 4 exec outputs → channel B → no-op
- `ToggleNode` (logic) `_update_outputs()` → `exec_output(1)/(2)` → channel B → no-op for On/Off
- `ToggleSwitchNode.toggle()` → channel B → no-op for Changed
- `NumericInputNode.submit()` → channel B → no-op for Submitted
- `ZoneInputNode.exec_output(2/3)` → channel B → no-op for On Enter / On Exit

**Working nodes** (override `exec_output` to iterate `_update_callbacks` directly): `StartExperimentNode`, `DelayNode`, `OutputNode`, `InputNode`, `MotorGovernorNode`, `CustomDeviceNode`, `LoopNode._exec_body`, `WaitForInputNode._exec_triggered`, `StartFunctionNode`, `FunctionCallNode`.

**Why it matters.** *Science correctness + operational.* An operator builds `Button -> DigitalWrite`, presses the button — nothing happens. Builds `Toggle -> Branch` — nothing fires when the toggle changes. Uses `ZoneInput -> EndExperiment` to auto-terminate on zone exit — nothing happens. The bug is invisible because (a) the rest of the flow logs propagation correctly, (b) affected nodes log their internal state change cheerfully, (c) operator just sees "the flow isn't doing the thing." Debugging requires reading `flow_engine.py` to discover the channel split.

**Fix.** Delete `_exec_callbacks` entirely. Have `ExecNode.exec_output(index)` look up the output name from `self.definition.outputs[index].name` and dispatch through `_update_callbacks` exactly like data outputs:
```python
def exec_output(self, index: int = 0) -> None:
    if index < len(self.definition.outputs):
        output_name = self.definition.outputs[index].name
    else:
        output_name = str(index)
    for callback in list(self._update_callbacks):
        try:
            callback(output_name, True)
        except Exception as e:
            logger.error(f"Exec callback error on {self._glider_id}:{output_name}: {e}")
```
Add a regression test that constructs every node, registers a callback on every output, fires every exec output, and asserts the callback ran.

### Critical — No node `execute()` re-checks engine state; combined with Section 1 fire-and-forget, hardware writes complete after safe-state transition

[src/glider/nodes/experiment_nodes.py:152-187, 270-301, 345-386](src/glider/nodes/experiment_nodes.py:152), [src/glider/nodes/hardware/digital_nodes.py:62-73, 139-149](src/glider/nodes/hardware/digital_nodes.py:62), [src/glider/nodes/hardware/analog_nodes.py:81-102, 208-220](src/glider/nodes/hardware/analog_nodes.py:81)

Every hardware-writing `execute()`/`hardware_operation()` trusts that the engine will never call it past STOP. Section 1 proved the engine *does* — `flow_engine._propagate_execution` spawns untracked tasks that aren't cancelled and don't re-check `self._state` before invoking `to_node.execute()`. A `DigitalWriteNode` write started 1ms before STOP completes after `_set_all_devices_low` has driven the pin low.

**Why it matters.** *Hardware safety + science correctness.* Same C1 family as Section 1 but observed at the node layer: a heater controlled by `OutputNode.execute()` is set HIGH right before the operator clicks STOP because the trial's success criterion misfired; safe-state pulls it low; orphan write fires HIGH again 200ms later; heater stays on overnight.

**Fix.** Two changes, defence in depth: (a) at the top of every hardware-writing `execute()`, re-check engine state via a `_check_state()` lambda the flow engine injects at node creation (avoids back-reference cycle); (b) fix Section 1 root cause: `_propagate_execution` re-checks `self._state != FlowState.RUNNING` before invoking `to_node.execute()`. Both needed because either alone leaves a race window.

### Critical — Hardware node `execute_action` calls have no `asyncio.wait_for`; a wedged Telemetrix freezes the flow

[src/glider/nodes/hardware/digital_nodes.py:67, 142](src/glider/nodes/hardware/digital_nodes.py:67), [src/glider/nodes/hardware/analog_nodes.py:84, 214](src/glider/nodes/hardware/analog_nodes.py:84), [src/glider/nodes/hardware/device_nodes.py:88, 151](src/glider/nodes/hardware/device_nodes.py:88), [src/glider/nodes/experiment_nodes.py:175-180, 225-227, 283-292, 369-378](src/glider/nodes/experiment_nodes.py:175)

Section 2 established `TelemetrixThread.call_method` blocks the asyncio loop up to 5s. Every node-level `await self._device.execute_action(...)` inherits that latency. `WaitForInputNode._poll_device` calls `device.read()` 20 times per second; on a wedged cable each call blocks 5s.

**Why it matters.** *Operational + hardware safety.* Flow engine's `_propagate_execution` awaits `to_node.execute()` — single hung node write blocks subsequent execution in the chain, blocks the safe-state path on STOP, blocks UI thread.

**Fix.** Wrap every node-level device I/O in `asyncio.wait_for` with `NODE_IO_TIMEOUT_S = 1.0` (tighter than `DEVICE_IO_TIMEOUT_S = 2.0` — nodes should fail fast, not retry). Best long-term: fix Section 2's `TelemetrixThread.call_method` blocking at the HAL boundary — eliminates the need for node-level timeouts.

## High findings

### High — `ZoneInputNode.update_zone_state` defined but never called

[src/glider/nodes/vision/zone_nodes.py:112-141](src/glider/nodes/vision/zone_nodes.py:112)

`grep -r 'update_zone_state' src/` returns exactly one hit — the definition. `cv_processor.py` has the zone tracker and `get_zone_states()` accessor; `data_recorder.py` reads it for the CSV column; **nothing dispatches into ZoneInputNode**.

**Why it matters.** *Science correctness.* Entire `ZoneInputNode` feature is dead. Saved experiments using zone-driven flow control don't fail loudly — node sits in the graph, widget renders, `Occupied` stays False forever, exec outputs never fire. Operator building "if mouse enters zone, deliver reward" gets no reward.

**Fix.** In `cv_processor.process_frame` (after tracker update), dispatch into the flow engine's `ZoneInputNode` instances. Beware the threading boundary — `cv_processor` runs on the capture thread (Section 3 finding); marshal via `loop.call_soon_threadsafe`. Better: have `cv_processor` publish events via an event bus; `ZoneInputNode.start()` subscribes. Once Critical-1 (channels) is fixed, the exec outputs will route correctly too.

### High — Runner Touch widgets dead in dispatch path: `widget_value_changed` has zero subscribers

[src/glider/gui/runner/dashboard.py:34, 137-140](src/glider/gui/runner/dashboard.py:34)

```python
widget_value_changed = pyqtSignal(str, object)  # node_id, value
...
widget.value_changed.connect(
    lambda v, n=node: self.widget_value_changed.emit(n.id, v)
)
```

`grep -rn 'widget_value_changed' src/` returns two hits, both inside `dashboard.py`. Nothing subscribes. `update_widget(node_id, value)` exists as the *forward* path (data → widget), but the *reverse* (widget → node) is built but not connected.

**Why it matters.** *Operational + science correctness.* Operator-facing version of the channel-split Critical. Touch Button visually depresses; nothing reaches `ButtonNode.press()`. For a touchscreen-driven rig (stated use case), runner mode is display-only — no human-in-the-loop control.

**Fix.** In the runner controller, connect `dashboard.widget_value_changed` to a slot that maps `node_id → node` and calls the appropriate node method (`press()`, `set_state_value()`, `set_value()`). Add an integration test that simulates a `QTest.mouseClick` and asserts `ButtonNode._press_count` increments.

### High — `FunctionCallNode` swallows sub-flow timeout and proceeds as if it completed

[src/glider/nodes/flow_function_nodes.py:239-254](src/glider/nodes/flow_function_nodes.py:239), [src/glider/nodes/flow_function_nodes.py:110-115](src/glider/nodes/flow_function_nodes.py:110)

`FlowFunctionRunner.execute` swallows `TimeoutError` (logs warning only). `FunctionCallNode.execute` sees the await return cleanly and fires `exec_output(0)`. Downstream nodes execute as if the sub-flow completed normally. Compounding: Section 1's H9 (still open) means inflight subgraph propagation tasks aren't cancelled either — so on timeout, the parent flow proceeds AND the sub-flow's hardware writes keep firing in the background.

**Why it matters.** *Science correctness + hardware safety.* Sub-flow controlling a sequence of injections fails to complete in 60s (a `WaitForInput` was waiting on a never-arriving signal). Parent flow proceeds as if injections happened. CSV records "injection complete." Mouse received no injection. 30s later the injection step *does* complete because nothing cancelled it — now firing at the wrong point in the parent flow's timeline.

**Fix.** Three changes: (a) `FlowFunctionRunner.execute` re-raises `TimeoutError` after cleanup; (b) `FunctionCallNode.execute` does *not* fire `exec_output(0)` on exception — surface to flow engine to transition to ERROR; (c) implement Section 1 H9 fix: track and cancel sub-flow tasks in `_cleanup`.

### High — Polling-loop hardware nodes catch generic exceptions and continue silently

[src/glider/nodes/hardware/digital_nodes.py:166-176](src/glider/nodes/hardware/digital_nodes.py:166), [src/glider/nodes/hardware/analog_nodes.py:129-139](src/glider/nodes/hardware/analog_nodes.py:129)

```python
while True:
    try:
        await self.hardware_operation()
        await asyncio.sleep(self._poll_interval)
    except asyncio.CancelledError:
        break
    except Exception as e:
        self.set_error(str(e))     # <-- swallows
        await asyncio.sleep(self._poll_interval)
```

No error counter, no max-retry, no signal to flow engine. Compare `WaitForInputNode._poll_device` (control_nodes.py:282-288) which tracks `error_count` and raises after 3 — that's the right pattern, just not applied here.

**Why it matters.** *Operational.* 4-hour experiment with `DigitalReadNode` `continuous=True` on a pin disconnected at hour 1 → log accumulates ~144,000 ERROR messages, no UI surface, disk fills, CPU-saturated machine, useless experiment.

**Fix.** Adopt WaitForInputNode pattern: `error_count` with `max_consecutive_errors=5`, exponential backoff (`min(poll_interval * 2**error_count, 5.0)`), terminate on exhaustion, expose `_error` for flow engine.

### High — Hardware nodes don't validate input ranges before writing

[src/glider/nodes/hardware/digital_nodes.py:62-67](src/glider/nodes/hardware/digital_nodes.py:62), [src/glider/nodes/experiment_nodes.py:152-187, 270-301, 345-386](src/glider/nodes/experiment_nodes.py:152)

`PWMWriteNode` is the *only* hardware node that range-clamps (0..255). Every other accepts whatever is in `_state["value"]` or input port and writes straight to the device. `MotorGovernorNode` accepts any string action — typo `"upp"` silently no-ops, motor doesn't move, trial proceeds. `CustomDeviceNode.execute` passes any type through to `write_pin(pin_name, value)`.

Same shape as Section 3's Critical-1 (Miniscope unbounded). A saved `.glider` with `state["value"]=999` on a CustomDeviceNode wired to PWM writes 999 — telemetrix accepts; some firmwares wrap, some clamp, some raise. For servo angle, out-of-range can drive past mechanical stop and damage the mechanism.

**Why it matters.** *Hardware safety + science correctness.*

**Fix.** Per-node `validate_input(value) -> value` classmethod raising `ValueError`. For `MotorGovernorNode`'s action enum, use `Enum` deserialized with strict mapping. Pair with the M-tier baseline finding's fix: `HardwareNode.bind_device` validates device capability via `typing.Protocol`.

## Medium findings (22 total)

| # | File:line | Issue |
|---|---|---|
| M-nodes-1..4 | (M9, M10, M11, M12 above) | Four prior open mediums still present |
| M-nodes-5 | All `set_state`/`get_state` overrides | Two-state pattern: nodes split state between `self._state` dict and typed attributes; `set_state(state)` restores typed attribute but never re-syncs `self._state`; subsequent `get_state()` returns stale dict; round-trip loses changes |
| M-nodes-6 | `flow_nodes.py:36-38 (SequenceNode)` | `for i in range(4): self.exec_output(i)` — fans out, doesn't sequence. Even when Critical-1 is fixed, all four "then" outputs fire simultaneously |
| M-nodes-7 | `flow_function_nodes.py:67-70` | `_find_end_nodes` walks `self._flow_engine._connections` directly without copy; concurrent connection add/remove races |
| M-nodes-8 | `flow_function_nodes.py:112` | Hardcoded 60s function timeout; `TimingConfig.function_execution_timeout` not wired (same as Section 1) |
| M-nodes-9 | `zone_nodes.py:136, 140` | Baseline magic indices `(2, 3)` for "On Enter"/"On Exit" still present |
| M-nodes-10 | `input_nodes.py:189-195, 254-266` | `set_value` clamps to `_min_value`/`_max_value`; if loaded state has min > max, all writes clamp to one bound with no error |
| M-nodes-11 | `input_nodes.py:17 (ButtonNode)` | Diamond inheritance: `ButtonNode.__init__` calls `ExecNode.__init__` only, skipping `InterfaceNode.__init__` — `notify_widget` raises `AttributeError: '_widget_callbacks'` |
| M-nodes-12 | `control_nodes.py:218-291 (WaitForInputNode)` | Uses `time.time()` for timeout check; NTP step can trigger early/rewind. Same shape as Section 3 |
| M-nodes-13 | `experiment_nodes.py:103-121 (DelayNode)` | `await asyncio.sleep(duration)` not cancellable; STOP mid-delay → sleep continues to natural end → `exec_output(0)` fires post-STOP |
| M-nodes-14 | `base_node.py:154-160` | `on_output_update` / `on_error` append-only — no `remove_*` method; flows leak callbacks on rebuild |
| M-nodes-15 | `base_node.py:215-226` | `bind_device` no capability check, no thread-safety, no notification; mid-poll `bind_device` changes `self._device` between two `_poll_loop` iterations with no synchronization |
| M-nodes-16 | `base_node.py:358-376 (HardwareNode.execute)` | Catches Exception, calls `set_error`, *returns without firing `exec_output(0)`*. No `error` exec output → flow wedges at failing node with no propagation, operator sees nothing in flow timeline |
| M-nodes-17 | `flow_function_nodes.py:78-121` | `FlowFunctionRunner._find_end_nodes` caches across calls; if graph is edited (end node added/removed), next call uses stale cache and either never completes or completes from wrong node |
| M-nodes-18 | `experiment_nodes.py:30, 60` | `StartExperimentNode.start` not idempotent; double-click on Start launches two parallel flows on same nodes (both poll same devices, both reach EndExperiment, both fire `_notify_complete`) |
| M-nodes-19 | `base_node.py:236-244` | `set_error`/`clear_error` mutate `self._error` with no callback notification; `_error_callbacks` list registered but never invoked |
| M-nodes-20 | `logic/control_nodes.py:111-173 (ToggleNode)` | `ToggleNode.execute` is `pass` no-op; Toggle/SetOn/SetOff exec inputs visible in UI, never processed; `Button -> Toggle.Toggle` connection does nothing |
| M-nodes-21 | `interface/display_nodes.py:48-57 (LabelNode)` | `format_str.format(value)` with user-supplied format string from input port; CPython `__format__` mostly safe but unnecessarily wide surface — use `str(value)` or whitelist |
| M-nodes-22 | `interface/display_nodes.py:180-183 (ChartNode)` | `max_points` setter creates new `deque`; widget callbacks may still reference old deque → frozen view |
| M-nodes-23 | `logic/flow_nodes.py:131-148 (TimerNode)` | `_timer_loop` catches Exception and re-enters loop with no backoff; if input wiring breaks, loops at infinite speed, eats a CPU core |
| M-nodes-24 | `base_node.py:39-46 (PortDefinition)` | `default_value: Any = None` for ports declared `data_type=bool` defaults to `None`; nodes do `int(self.get_input(1) or 0)` — `0` (valid) silently coerces to fallback because of Python truthiness |

## Low findings (selected)

- `InterfaceNode.__init__` sets `_visible_in_runner=True` unconditionally; ChartNode/LabelNode may not want runner-visible default
- Most node `execute()` methods log 5+ lines at INFO per invocation — 2500+ lines per experiment run; move to DEBUG
- Two `DelayNode`s, two `LoopNode`s, two `ToggleNode`s registered under different names but conceptually the same — consolidate
- `PIDNode` uses `time.time()` for `dt`; NTP step can produce negative dt (the `if dt <= 0` guard catches but loses an integration tick)
- `DivideNode` returns `0.0` on div-by-zero with `set_error`; downstream can't distinguish "true zero" from "error fell back"; output `float('nan')` instead
- `SliderNode.set_value` doesn't snap to `_step` (only widget enforces); programmatic `set_value(33.7)` with `step=1.0` stays 33.7
- `ZoneInputNode.get_display_name` produces `"Zone: "` when `_zone_name == ""` instead of `"Zone Input"`
- Three `NodeDefinition.name` collisions silently let later registration win (Section 1 M-new-11 baseline)
- Sub-package `__init__.py` files have no `register_all` entry; top-level callers must know which sub-modules exist

## Architecture notes

- **One node-state mechanism, please.** The split between `self._state: dict` and typed attributes produces M-nodes-5 and forces every node author to override `get_state`/`set_state` symmetrically. Recommendation: all state in `self._state` (a `dataclass` per node would be even better); typed attributes become `@property` views into `self._state`. Then `to_dict`/`from_dict` is trivially correct and `_schema_version` lives next to the dict.
- **One callback channel, please.** Critical-1. Delete `_exec_callbacks`; route exec via output-name dispatch through `_update_callbacks`. Simplifies the (currently-unimplemented) unsubscribe path that the Section 1 orphan-callback Critical needs.
- **The flow engine ↔ node contract is implicit and under-tested.** Nodes assume the engine will call `start()` before `execute()`, won't call `execute()` after STOP, will pass `_update_callbacks` registrations exactly once per outgoing connection. None of these are stated; none enforced. A `NodeProtocol` (typing.Protocol) with documented preconditions and a `FlowEngineHandle` interface that nodes call into (instead of inheriting magic attributes) would let both sides be type-checked — and lets nodes re-check state via a clean API (Critical-2 fix).
- **`HardwareNode.bind_device` needs a capability protocol.** A `DigitalOutputProtocol` (with `execute_action("set", bool)`) and `AnalogInputProtocol` (with `execute_action("read") -> int`) would let `bind_device` validate at bind time, not at first execute.
- **"Touch widgets are dead in the runner" implies an integration-test gap.** No end-to-end test exists for "operator presses runner button → node exec output fires → downstream executes." A PyQt-based integration test using `QTest.mouseClick` would have caught this in CI.
- **Two `DelayNode`s, two `LoopNode`s, two `ToggleNode`s.** Naming collisions are symptoms of organic growth. Consolidate into `nodes/control/` and `nodes/io/` with one canonical implementation per concept.
- **`ZoneInputNode` is the canary that vision↔flow integration was never finished.** Section 3 noted multiple zone-logic locations (vision/zones.py, vision/cv_processor.py, nodes/vision/zone_nodes.py); the missing dispatch is the operationally-visible symptom. Fix (a `ZoneOrchestrator` per Section 3 architecture note) belongs upstream of nodes; nodes just subscribe.

## What's good in this module

- **`base_node.py`'s abstraction is the right shape.** Dataclass-based `PortDefinition`/`NodeDefinition`/`NodeCategory`, clean `GliderNode → DataNode/ExecNode → HardwareNode/LogicNode/InterfaceNode` hierarchy. Intent is clear; bugs are at the integration boundary.
- **`DataNode.update_event` catches exceptions cleanly** with `try: self.process(); self.clear_error()` / `except: self.set_error(...)` — exactly the right pattern.
- **`LoopNode._exec_body_async` is the most thoughtful flow-engine integration in this module.** Awaiting the returned tasks from callbacks (`asyncio.isfuture(result)` check + `asyncio.gather`) is the right pattern for ensuring loop iterations are sequential. Bug is M12, not the body-execution model.
- **`WaitForInputNode._poll_device` has the right error-handling pattern** (consecutive count, max retries, raise on exhaustion). Template the other polling loops should adopt.
- **`PWMWriteNode.hardware_operation` validates input range.** Replicate for every other hardware node.
- **`PIDNode.process` implements anti-windup correctly** — integral only accumulates when output isn't saturated. Subtle, easy to get wrong, correct here.
- **`ThresholdNode.process` implements hysteresis correctly.** Asymmetric thresholds based on previous state.
- **`MapRangeNode` and `ClampNode` guard against degenerate ranges**. Math nodes are robust.
- **`ChartNode` uses `collections.deque(maxlen=N)`** — correct bounded-history; doesn't leak.
- **No `eval`/`exec`/`pickle`/`subprocess`/`shell=True` anywhere.** Clean.
- **Categories and colors consistent.** Hardware green, logic blue, interface orange — helpful for the visual programming UX.
- **`FlowFunctionRunner` separates the runner from the node.** Right separation; bugs are in the runner, not the abstraction.

**Bottom line for `glider.nodes`:** the abstractions are clean but the integration with the flow engine and the runner is half-finished. The single most operationally-visible bug is Critical-1 (two callback channels, only one wired) — it silently disables many node types in any flow that uses them. The Touch widget dispatch gap (High-2) makes the runner mode non-interactive. The `ZoneInputNode` wiring gap (High-1) makes the entire vision-driven flow path inert. None surface as exceptions or test failures; they manifest as "the experiment doesn't do the thing." Fixing Critical-1 unblocks a class of bugs; fixing High-1 and High-2 closes off two large feature surfaces that look implemented but aren't. The four baseline mediums (M9–M12) are still present and worth the few hours each. The critical and high hardware findings (no timeouts, no range validation, no state re-check) are the same pattern Sections 1 and 2 found at the layers below — fixing once at the HAL boundary (Section 2 Critical-2) eliminates most of the node-level damage automatically.

---

# Section 5 — `glider.agent`

**Status:** Skipped per user instruction on 2026-05-24. The agent module is not yet properly implemented and is not considered a release blocker for the stable worldwide release. Either the panel will be hidden in the initial release or it is understood as experimental.

If/when the agent module is finished, the C3 fix (already committed in `tools/hardware_tools.py` and `tools/experiment_tools.py` with `_LOCKED_SESSION_STATES = {RUNNING, PAUSED, STOPPING}` and `READ_ONLY_*_TOOLS` frozensets) should be re-verified end-to-end, plus the newer `tools/knowledge_tools.py` (635 LOC) and `analysis/analysis_tools.py` (701 LOC) should be audited fresh.

---

# Section 6 — `glider.serialization` + `glider.plugins`

**Reviewed:** 2026-05-24 · **Files:** 5 · **LOC:** ~1,509

## Summary

- **All five baseline findings (C4, H4, M15, M16, M17) are still present** — no commits have touched these modules since the 2026-04-20 baseline.
- **M16 is materially worse than the baseline described, and grep-verified:** `_extract_node_properties` reads `node.property_names`, but **no node class anywhere in the codebase defines `property_names`**. `grep -rn "property_names" src/` returns exactly one hit — the read site itself. Therefore the function always returns an empty dict. **Every node-local property** (camera index, GPIO pin, threshold value, timer duration, conditional expression) **is silently dropped on every save.** Reload "succeeds" with blank state. No error, no warning. This is the worst-case data-integrity bug in the codebase — and explains why Section 4's `to_dict`/`property_names`/`NodeConfig` shape disconnect matters operationally: there is no path that actually preserves node state across save/load.
- **`atomic_write` does not exist anywhere in the codebase. Only one of 12 `open(..., "w")` save paths uses `os.replace`** ([video_recorder.py:391](src/glider/vision/video_recorder.py:391)). Every other `.glider`, `.json`, `.yaml`, calibration, zone, library, and config save truncates the target in place — H4 cascades across the entire app. **Creating `glider/serialization/atomic.py` is the single highest-leverage stability fix in the codebase.**
- **4 new Highs** beyond the baseline refinements: plugin `setup()` runs in the asyncio loop with no isolation/no timeout/no rollback (refines C4); `sys.path.insert(0, ...)` is permanent and unbounded (a plugin directory containing `logging.py` or `json.py` shadows stdlib for the rest of the process); plugin failure logging truncates tracebacks (loses stack frames); plugin load order is dict-iteration order with no dependency declaration.
- **9 new Mediums** including: schema version validator crashes on non-semver strings ("dev", "1.0.0-rc1"); `PortSchema(**p)` strict-kwargs unpack means any new optional field is a breaking change; `isinstance(x, int)` accepts `True`/`False` (Python booleans are ints); `_apply_hardware_config` `**unpacks` user-controlled JSON into `add_board`/`add_device` kwargs (settings collision risk); plugin-registered nodes can silently overwrite built-ins (a plugin registering `"DigitalWriteNode"` replaces the core implementation); `reload_plugin` leaves old class instances alive with stale code; no DoS bounds on node/connection counts; partial-state mutation on schema validation failure.
- **The bright spot:** no `pickle` / `marshal` / `dill` / `yaml.load` / `eval` anywhere in these modules. JSON-only with structured `from_dict` validation, granular exception handling, path-carrying validation errors. **No unsafe deserialization surface** — the most important security property in a file-format module is correct.

## Verification of prior fixes

| Baseline | Status | Current location |
|---|---|---|
| **C4** plugin loader unsafe / `sys.path` mutation / no setup-failure rollback | Still present | [plugin_manager.py:286-330](src/glider/plugins/plugin_manager.py:286) |
| **H4** non-atomic `.glider` save | Still present | [serializer.py:87-89](src/glider/serialization/serializer.py:87) |
| **M15** schema version refuses future versions outright | Still present | [serializer.py:400-407](src/glider/serialization/serializer.py:400) |
| **M16** `_extract_node_properties` silently drops non-JSON values | Still present + worse than described (see Critical refinement) | [serializer.py:313-329](src/glider/serialization/serializer.py:313) |
| **M17** unknown node types skipped, data lost on round-trip | Still present | [serializer.py:364-376](src/glider/serialization/serializer.py:364) |

## Critical refinement (baseline M16 elevated)

### Critical — Node properties are never serialized; every save silently drops all node state

[src/glider/serialization/serializer.py:313-329](src/glider/serialization/serializer.py:313)

```python
def _extract_node_properties(self, node) -> dict[str, Any]:
    properties = {}
    for prop_name in getattr(node, "property_names", []):
        if hasattr(node, prop_name):
            value = getattr(node, prop_name)
            if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                properties[prop_name] = value
    return properties
```

**Grep verification:** `grep -rn "property_names" src/` returns exactly **one** hit — the read site at `serializer.py:318`. Zero node class anywhere defines `property_names`. `getattr(node, "property_names", [])` therefore always returns `[]`. Combined with Section 4's finding that `BaseNode.to_dict` is never called by either save path, **no node-local property is ever written to a `.glider` file**.

**Why it matters.** *Science correctness, highest impact.* This is the bug that explains why "save and reload doesn't work right" reports manifest as configuration drift: every camera index, GPIO pin, threshold value, ITI duration, PWM frequency, servo angle, ML model path, zone shape, calibration ID configured in the GUI inspector vanishes on save. Reload restores nodes to their dataclass defaults. The flow graph topology is preserved (because connections are independently serialized), but every parameter is gone. The user is rebuilding configuration on every load — not realising the system *thinks* it loaded successfully.

**Fix.** Two-stage, but the first stage alone closes the gap:
1. **Immediate (1-day fix):** wire `BaseNode.to_dict` / `BaseNode.from_dict` (which exist but are unused — Section 4 M-nodes-1) into `_extract_node_properties` and the load path. Add a regression test `test_round_trip.py` that creates every registered node, sets every property, calls `dump → load → dump`, and asserts equality. **This single test should be the first thing in the CI pipeline.**
2. **Long-term (1-week):** define a `NodeStateProtocol` on `GliderNode` with abstract `serialize_state() -> dict` / `deserialize_state(d)` methods. Replace `_extract_node_properties` with `node.serialize_state()`. Add `_schema_version: ClassVar[int]` to each node class with an `_migrate(state, from_version)` hook.

## High findings

### High — H4 cascades app-wide: 12 save paths, only 1 atomic

[src/glider/serialization/serializer.py:87-89](src/glider/serialization/serializer.py:87) + 11 sister sites: [experiment_session.py:835](src/glider/core/experiment_session.py:835), [library.py:85, 170, 260](src/glider/core/library.py), [vision/zones.py:320](src/glider/vision/zones.py:320), [vision/calibration.py:299](src/glider/vision/calibration.py:299), [agent/config.py:104](src/glider/agent/config.py:104), [core/config.py:183](src/glider/core/config.py:183), etc.

```python
# Every site has this shape:
with open(path, "w", encoding="utf-8") as f:
    f.write(content)
```

**Why it matters.** *Science correctness.* `open("w")` truncates *before* any bytes are written. Power loss, crash, disk-full, `KeyboardInterrupt`, OS kill mid-write — any of these between truncate and `f.write()` returning leaves an empty or partial file. For the user this is "I lost my experiment design." The fix is well-understood and three lines per call site, but the right shape is a single helper.

**Fix.** Create `glider/serialization/atomic.py`:
```python
import os, tempfile
from pathlib import Path

def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)  # atomic on POSIX + NTFS
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise
```
Migrate every `open(..., "w")` save site to use it. Audit-grep at the end to confirm zero non-atomic JSON saves remain.

### High — Plugin `setup()` blocks the qasync loop with no isolation, no timeout, no rollback (C4 refined)

[src/glider/plugins/plugin_manager.py:299-330](src/glider/plugins/plugin_manager.py:299)

```python
spec.loader.exec_module(module)               # arbitrary Python on startup
...
if asyncio.iscoroutinefunction(setup_func):
    await setup_func()
else:
    setup_func()                               # blocks qasync loop
```

**Why it matters.** *Stability + hardware safety.* Three failure modes: (1) a sync `setup()` that opens a serial port / sleeps / shells out freezes the UI loop on startup. (2) No timeout: a plugin hanging at import (e.g., `requests.get(...)` at module top level) blocks app startup forever with no log identifying which plugin is the culprit. (3) If `setup()` raises *after* `_register_plugin_components` has put a board driver / device / node into the global registries, the rollback at `:332-371` only sets `info.error` — partially registered classes stay in `_node_registry`, `_drivers`, `DEVICE_REGISTRY`. A user clicking "use this driver" later instantiates half-initialized code.

**Fix.** (a) Wrap `exec_module` + `setup_func` in `asyncio.wait_for(..., timeout=30)`, log full plugin path on timeout. (b) Snapshot the registries before `_register_plugin_components`; on any exception, walk the snapshot diff and remove just the additions. (c) Run sync `setup_func` in `loop.run_in_executor(None, setup_func)` so a blocking plugin can't freeze GUI; document that plugin authors get a worker thread and must not touch Qt directly.

### High — `sys.path.insert(0, ...)` is permanent and shadows stdlib

[src/glider/plugins/plugin_manager.py:290-291](src/glider/plugins/plugin_manager.py:290)

```python
if plugin_path.parent not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(plugin_path.parent))
```

**Why it matters.** *Stability.* Once inserted, the plugin parent directory stays at the FRONT of `sys.path` for the process lifetime. Every subsequent `import x` checks `~/.glider/plugins/` before stdlib and site-packages. A plugin directory containing a top-level `logging.py`, `json.py`, `numpy.py`, or `queue.py` will shadow the real module for the rest of the run — bizarre `AttributeError`s deep inside unrelated code.

**Fix.** Don't mutate `sys.path` at all. Use `importlib.util.spec_from_file_location(name, init_py, submodule_search_locations=[str(plugin_path)])` — lets the plugin import its own submodules without polluting global path. If transitive-dep `sys.path` mutation is needed, append to the *end*, not the front, and remove it in `unload_plugin`.

### High — Plugin load order is dict-iteration order; exceptions logged without tracebacks

[src/glider/plugins/plugin_manager.py:249-264, 332-371](src/glider/plugins/plugin_manager.py:249)

```python
for name, info in self._plugins.items():     # filesystem-order dependent
    if info.enabled and not info.loaded:
        results[name] = await self.load_plugin(name)
...
except Exception as e:
    logger.error(f"... {type(e).__name__}: {e}")    # truncates traceback
```

**Why it matters.** *Stability.* No declared load order or dependency graph; plugins iterated in dict insertion order (discovery order, filesystem-dependent). If plugin B uses a class registered by plugin A, B may fail half the time depending on disk ordering. Tracebacks truncated to `type(e).__name__: {e}` — for a plugin crash, you almost always need the full stack to diagnose.

**Fix.** Sort plugins by an explicit `priority` field in manifest (default 100). Log `logger.exception(...)` (which includes the full traceback) in the catch-all. Drop misleading `async` from `_register_plugin_components`.

## Medium findings (9 total)

| # | File:line | Issue |
|---|---|---|
| M-ser-1 | [serializer.py:387-413](src/glider/serialization/serializer.py:387) | Version validator crashes on non-semver ("dev", "1.0.0-rc1", "1.0"); "future-major rejected" message is unhelpful. Use `packaging.version.Version`; show actionable upgrade hint. |
| M-ser-2 | [serializer.py:313-329](src/glider/serialization/serializer.py:313) | **Critical-refinement above subsumes this** — kept here to flag the secondary `isinstance` filter that also drops numpy ints/floats and `Path` objects silently. |
| M-ser-3 | [schema.py:101-104, 316-318](src/glider/serialization/schema.py:101) | `PortSchema(**p)` and `DashboardWidgetSchema(**data)` strict-kwargs unpack — any new optional field is a *breaking change* unless you also bump schema version and migrate. Implement explicit `from_dict(d)` that validates known fields and ignores unknown with debug log. |
| M-ser-4 | [schema.py:144-151, 232, 344](src/glider/serialization/schema.py:144) | `isinstance(x, int)` accepts `True`/`False` (booleans are ints in Python). JSON `true` for `from_port` produces `from_port=1`. Use `isinstance(x, int) and not isinstance(x, bool)`. |
| M-ser-5 | [serializer.py:331-356](src/glider/serialization/serializer.py:331) | `_apply_hardware_config` `**unpacks` user-controlled `settings` dict into `add_board(**settings)` and `add_device(**settings)`. A malformed file with `settings: {"port": "/dev/ttyUSB99"}` collides with the explicit `port=` kwarg → TypeError; or `settings: {"baudrate": "fast"}` passes a string into a low-level pyserial call. Pass `settings=board_config.settings` and let the receiver `.get(...)` known keys. |
| M-plugin-1 | [plugin_manager.py:373-397](src/glider/plugins/plugin_manager.py:373) + [core/flow_engine.py:72-75](src/glider/core/flow_engine.py:72) | Plugin-registered nodes can silently overwrite built-ins — a plugin registering `"DigitalWriteNode"` replaces the core class; every experiment using the built-in now resolves to plugin code (could fry a sample/animal). Refuse overwrite by default; add explicit `force=True` opt-in; log warning with both qualnames. Same for `BOARD_DRIVERS` and `DEVICE_TYPES`. |
| M-plugin-2 | [plugin_manager.py:437-448](src/glider/plugins/plugin_manager.py:437) | `reload_plugin` re-executes `exec_module` but doesn't `del sys.modules[...]`, doesn't unregister from registries, doesn't `importlib.invalidate_caches()`. Old node *instances* hold references to old class — `isinstance(node, NewClass)` is False; type checks break. Either remove `reload_plugin` from the public API or do it properly. |
| M-ser-6 | [schema.py:486-490](src/glider/serialization/schema.py:486) | No bounds on node/connection counts; a crafted file with 10M empty nodes OOMs on `from_dict` walk. Add soft caps: `MAX_NODES=10_000`, `MAX_CONNECTIONS=50_000`, `MAX_PROPERTY_BYTES=1_000_000` per node. |
| M-ser-7 | [serializer.py:138-192](src/glider/serialization/serializer.py:138) | `apply_to_session` is not transactional: sets metadata → clears hardware → clears flow → applies; if `_apply_flow_config` raises midway (connection refers to nonexistent node), session has new metadata + cleared hardware + partial flow. Pre-validate cross-references in `_validate_and_migrate` before mutating. Snapshot session state; restore on exception. |

## Low findings (selected)

- `serializer.py:84-85` — `not path.suffix == ".glider"` reads awkwardly; prefer `path.suffix != self.FILE_EXTENSION`
- `schema.py:405-409` — `datetime.now()` without `tz=timezone.utc` (timezone-naive timestamps in metadata)
- `plugin_manager.py:466-502` — `install_requirements` shells out to `pip install` with plugin-supplied package names; no version pinning, no `--user`, no virtualenv check. A plugin requesting `["torch"]` pulls 2 GB. Frame as docs: require explicit user consent at UI layer.
- `plugin_manager.py:301-307` — Doesn't log the full filesystem path being `exec_module`'d, only the plugin `name`. Add the absolute path log line immediately before `exec_module` for forensics.
- `plugin_manager.py:99-101` — `mkdir(parents=True, exist_ok=True)` in `__init__` on every PluginManager instantiation; recreates the dir even if user deleted it
- `serializer.py:439-447` — Module-global `_serializer` singleton; node-registry state is process-wide
- `plugin_manager.py:450-464` — `enable_plugin` / `disable_plugin` modify `info.enabled` in-memory only; **no persistence** — user's choice lost on every restart
- `plugin_manager.py:60-72, 266` — `manifest.json` only requires `name`; no required `glider_version`, no `entry_point`, no `plugin_type`. Plugins built for GLIDER 0.1 silently load against GLIDER 1.0 with whatever ABI breaks.

## Architecture notes

- **`.glider` is plain-JSON, indent=2.** Right call (human-readable, diffable, git-friendly). No pickle/marshal/dill/yaml/eval anywhere in serialization or plugins (grep-verified zero hits). **No unsafe deserialization surface** — the single most important security property in a file-format module is correct.
- **`atomic_write` doesn't exist.** Only `video_recorder.py:391` uses `os.replace`. The other 11 `open(..., "w")` callsites all truncate-in-place. **Single highest-leverage fix in the codebase for stability.**
- **Round-trip integrity is broken at three layers:** (a) node properties never serialize (Critical above); (b) unknown node types dropped on load with warning only (M17); (c) schema additions crash old loaders because dataclass `**kwargs` is strict (M-ser-3). Until all three are fixed, `dump(load(file))` is not equal to `file` for any non-trivial experiment.
- **Version migration is currently a no-op.** `_migrate_schema` (`:415-435`) says "Migration logic would go here" and only bumps the version string. No per-node `schema_version`, no migration registry, no test fixture for old-version files. Before worldwide release, write at least one migration (even a no-op) to lock in the pattern.
- **Plugin trust model is implicit.** Plugins run with full process privileges. For trusted scientific users this is defensible, but it needs to be explicit — auto-written `~/.glider/plugins/README.md` on first run, UI "unverified plugin" warning before first load with one-time stored consent.
- **`PluginInfo.enabled` is not persisted.** A user disabling a misbehaving plugin will see it reload at next startup. Add atomically-written `~/.glider/plugins/state.json`.

## What's good in this module

- **No unsafe deserialization** (pickle/marshal/dill/yaml/eval). Pure JSON. Grep-verified.
- **`SchemaValidationError` carries a path** (`path=f"{path}.boards[{i}]"`) — actionable error messages like `hardware.boards[2].pin: Expected int, got str`. Very nice.
- **Granular exception handling on load** — distinguishes `FileNotFoundError`, `PermissionError`, `UnicodeDecodeError`, `OSError`, `JSONDecodeError`, `SchemaValidationError`. Materially better than `except Exception`.
- **Plugin discovery covers both entry-points and a user directory** — dual mechanism is the right shape for a Python plugin system.
- **Plugin `load_plugin` exception handling** breaks out specific exception types (`ModuleNotFoundError`, `SyntaxError`, `AttributeError`, etc.) with actionable messages. Each writes to `info.error` so UI can show *why* a plugin failed. Excellent.
- **`SCHEMA_VERSION` is a module-level constant** with clear single source of truth.
- **Dataclasses with `to_dict`/`from_dict` symmetry** are the right idiom — no over-engineering with pydantic/marshmallow.

**Bottom line for `glider.serialization` + `glider.plugins`:** the security shape is right (no pickle, no eval, JSON-only, structured validation), but the data-integrity shape is badly broken. The Critical refinement of M16 means **save+load is currently corrupting every experiment configuration silently** — fixing it is a 1-day patch (wire `BaseNode.to_dict` into `_extract_node_properties` + a round-trip regression test) and should be done before the next release tag, not before worldwide release. The atomic-write gap is a 1-day codebase-wide fix that closes H4 + 11 cascading paths in one helper. The plugin C4 refinement is a longer rewrite but plugins are trusted by design, so it's stability work, not security work — frame it accordingly in the release notes. After these three, the module is genuinely close to release-ready.

---

# Section 7 — `glider.gui`

**Reviewed:** 2026-05-24 · **Files:** 34 · **LOC:** ~16,539

## Summary

- **H7 partially fixed.** `_run_async` ([main_window.py:4404-4414](src/glider/gui/main_window.py:4404)) correctly *tracks* tasks (`self._pending_tasks.add(task)` + `discard` done-callback), closing the GC-leak half of the bug. But the done-callback discards silently — **exceptions inside the coroutine still vanish into asyncio's default unhandled-exception logger.** No UI surface, no log path beyond `asyncio`'s defaults.
- **M13 (undo/redo) is materially worse than baseline noted.** `UndoStack.redo()` does NOT actually re-execute the command — it just shuffles it between stacks. `MainWindow._redo_command` re-implements redo via a giant `isinstance` chain and reaches into `self._undo_stack._undo_stack.pop()` (private-attribute access at line 4441) to clean up double-push artifacts. `MoveNodeCommand` redo doesn't restore `_old_x/_old_y` symmetry — multi-step undo→redo→undo drifts to the original position, not the just-redone position.
- **M14 (dialog validation) confirmed partial.** Three dialogs validate in an `_on_accept` slot (works for `exec()`, fails for programmatic `accept()`). `experiment_dialog.py:349-364` does NOT validate at all — empty experiment names are mutated into `metadata.name` live on every keystroke with no `strip()`, no length cap, no rejection.
- **L baseline findings confirmed.** Busy-wait in `closeEvent` (`time.sleep(0.01)` + `QApplication.processEvents()`); mode-detection cache not invalidated on display change.

- **2 new Criticals, both grep-verified:**
  1. **`RunnerDashboard` is never instantiated anywhere in the codebase.** Grep returns three hits total — class definition, package re-export, type-list export string. **Zero constructor calls.** The entire touch-widget UI subsystem (`runner/dashboard.py` + `runner/widget_factory.py` + 812-line `widgets/touch_widgets.py`) is dead code with respect to the running application. The runner mode that users actually see is built ad-hoc inline in main_window and uses different widget plumbing. Section 4 High-2 said "the signal has no subscribers"; the actual situation is that the entire UI subsystem isn't even constructed.
  2. **ERROR state has no user-visible modal.** `_on_core_state_change` only mutates a QSS `statusState` property; `_on_core_error` only `emit()`s a signal that has **zero `connect()` subscribers** (grep-verified — defined at line 182, emitted at line 1318, never received). Yet `QMessageBox.critical` is used 7+ times elsewhere in main_window for routine file-save errors. The pattern exists; it's just not wired to the actual safety-critical state path. After a Section 1 C1 unsafe shutdown, the operator sees a red status label that's indistinguishable from a transient connection error — same color, same text, no instruction not to power down.

- **4 new Highs:**
  1. `WidgetFactory.update_from_node` callbacks are never deregistered; rebuilding the dashboard leaks closure references to deleted Qt widgets, then the next callback invocation hits `RuntimeError: wrapped C/C++ object has been deleted` (segfault risk on Linux).
  2. `closeEvent` cancels pending tasks without `await asyncio.gather(*tasks, return_exceptions=True)` — cancellation is advisory; tasks race with `_core.shutdown()`.
  3. Hardware-disconnection handler calls `_run_async(self._core.pause())` then opens a modal `exec()` while pause is still in flight — fragile in qasync, and the dialog's "Reconnect" button is enabled before pause completes.
  4. Miniscope LED/EWL slider slots ignore the return value of `set_led_power`/`set_ewl_focus` — GUI half of Section 3 Critical-1; slider visually shows 50%, label shows 50%, hardware may be at 0% with no operator signal.

- **13 new Mediums** including: `_poll_input` queues `_run_async` tasks per timer tick with no in-flight flag; `_on_pwm_changed`/`_on_servo_changed` fire on every spinbox keystroke with no debounce; magic parent-traversal via `hasattr(parent, "_on_add_board")`; node-item delete leak risk; `camera_panel.closeEvent` never deregisters frame callbacks.

- **`main_window.py` is too dense for a single pass** (4937 LOC). The agent audited `_run_async`, state handlers, `closeEvent`, undo/redo wiring, and `_setup_node_ports` — but at least three more functional surfaces (menu builder, runner-mode setup, the device control panel duplicated in lines 4509-4890) were not audited. **Recommend a separate dedicated pass for main_window.py alone**, ideally after the god-object decomposition starts.

## Verification of prior fixes

### H7 — PARTIAL: tracking is fixed, exception surfacing is not

[src/glider/gui/main_window.py:4404-4414](src/glider/gui/main_window.py:4404)

```python
def _run_async(self, coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    self._pending_tasks.add(task)
    task.add_done_callback(self._pending_tasks.discard)
    return task
```

GC-of-orphan-task half is closed (good). But `discard` never inspects `task.exception()` — baseline complaint "exceptions inside the coroutine are silently swallowed" still stands. Controllers wrap each coroutine in `try/except` that pops a `QMessageBox.critical` — that's the workaround. Wherever an inner coroutine forgets that wrapper (e.g., `hardware_controller.disconnect_all`), exceptions are lost.

**Fix.**
```python
def _run_async(self, coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    self._pending_tasks.add(task)
    def _done(t):
        self._pending_tasks.discard(t)
        if not t.cancelled():
            exc = t.exception()
            if exc is not None:
                logger.exception("Unhandled exception in async task", exc_info=exc)
                self._async_error_occurred.emit(str(exc))  # new pyqtSignal
    task.add_done_callback(_done)
    return task
```
Bind `_async_error_occurred` to a single `QMessageBox.critical` slot — no controller-side try/except needed.

### M13 — STILL PRESENT and worse than baseline: redo path fundamentally broken

[src/glider/gui/commands.py:253-261](src/glider/gui/commands.py:253), [src/glider/gui/main_window.py:4434-4488](src/glider/gui/main_window.py:4434)

```python
# commands.py:
def redo(self) -> Optional[Command]:
    if not self._redo_stack:
        return None
    command = self._redo_stack.pop()
    # Re-execute by undoing the undo
    self._undo_stack.append(command)
    return command  # <-- doesn't re-apply anything
```

Real redo lives in `MainWindow._redo_command` — giant `isinstance` chain re-implementing each command's forward operation. To avoid double-push on the undo stack, it does `self._undo_stack._undo_stack.pop()` (line 4441) — direct private-attribute manipulation.

Concrete bugs:
1. **`MoveNodeCommand` redo loses original position.** Stored `_old_x/_old_y` are unchanged through redo; second undo restores to the *very first* original, not the just-redone position. Multi-step undo→redo drift.
2. **No exception handling at stack boundary.** If `command.undo()` raises (session reload, node ID gone), `UndoStack.undo` pops, calls undo, exception escapes, redo-push never reached. Command is lost from both stacks.

**Fix.** Promote `Command.redo()` to a first-class method on each command class; `UndoStack.redo` calls `command.redo()`. Wrap both `undo()` and `redo()` in try/except that re-pushes on failure. Remove `MainWindow._redo_command` entirely.

### M14 — STILL PRESENT for `experiment_dialog`; PARTIAL elsewhere

[src/glider/gui/dialogs/experiment_dialog.py:349-364](src/glider/gui/dialogs/experiment_dialog.py:349) — `_on_info_changed` mutates `metadata.name = self._name_edit.text()` live on every keystroke with no validation.

Three other dialogs validate in `_on_accept` slot — works for `dialog.exec()`, bypassed if any code does `dialog.accept()` programmatically (or if Enter-key auto-accept is hooked).

**Fix.** Override `accept()` (`def accept(self): if not self._validate(): return; super().accept()`) rather than wiring to a custom slot. For experiment_dialog, add top-of-`_on_info_changed` guard: `if not metadata.name.strip(): return; if len(metadata.name) > 200: return`. The name leaks into `tracking_logger`'s CSV — control characters in the name can corrupt the file.

### L (busy-wait) — STILL PRESENT

[src/glider/gui/main_window.py:4922-4934](src/glider/gui/main_window.py:4922) — 10s worst-case 100% CPU spin during shutdown, with `processEvents()` allowing reentrancy (new clicks can trigger `_run_async` tasks added to an already-cleared `_pending_tasks` set). Fix: two-stage close — hide main window immediately, show modal "Shutting down..." dialog with no interactive elements, run shutdown on dedicated thread.

### L (mode cache) — STILL PRESENT

[src/glider/gui/view_manager.py:94-96](src/glider/gui/view_manager.py:94) — `_detected_mode` cached once, never invalidated on `QScreen.geometryChanged` or `QApplication.primaryScreenChanged`. Low impact in lab setups.

## Cross-references from prior sections

### Section 1 C1 — UI surfacing gap CONFIRMED

[src/glider/gui/main_window.py:1014-1077, 1316-1319](src/glider/gui/main_window.py:1014)

`_on_core_state_change` updates a QSS property; `_on_core_error` only emits `error_occurred` and logs. **`error_occurred` has zero `connect()` calls** — grep at line 182 (definition) and 1318 (emit), nothing else. After a Section 1 C1 unsafe shutdown, operator sees the same red ERROR label as after a transient connection error.

**Fix.** Wire as shown in the Critical finding below.

### Section 4 High-1 — `ZoneInputNode.update_zone_state` wiring CONFIRMED missing

`grep -rn "update_zone_state" src/glider/gui/` returns zero hits. No GUI path dispatches zone events into the node.

**Fix.** Once `CVProcessor` exposes an `on_zone_event` registrar (Section 3 architecture note), wire in `MainWindow._connect_signals`:
```python
def _on_zone_event(zone_id, object_count, occupied):
    if not (self._core.flow_engine and self._core.flow_engine.is_running):
        return
    loop = asyncio.get_event_loop()
    for node in self._core.flow_engine.nodes.values():
        if type(node).__name__ == "ZoneInputNode" and getattr(node, "_zone_id", None) == zone_id:
            loop.call_soon_threadsafe(node.update_zone_state, occupied, object_count)
self._cv_processor.on_zone_event(_on_zone_event)
```
`loop.call_soon_threadsafe` is mandatory — `process_frame` runs on capture thread; without marshaling, you race on `_pin_values`.

### Section 4 High-2 — `widget_value_changed` CONFIRMED has no subscribers AND `RunnerDashboard` never instantiated

See Critical-1 below — this is worse than Section 4 noted. Not just "no subscribers" — the entire subsystem is dead code.

### Section 4 Critical-1 — `_exec_callbacks` GUI subscribers CONFIRMED zero

`grep -rn "on_exec\b\|_exec_callbacks" src/glider/gui/` returns zero hits. Safe to delete `_exec_callbacks` at the node layer.

## Critical findings (NEW)

### Critical — `RunnerDashboard` and `WidgetFactory` are dead code; touchscreen mode is non-functional

[src/glider/gui/runner/dashboard.py:25](src/glider/gui/runner/dashboard.py:25), [src/glider/gui/runner/widget_factory.py:13](src/glider/gui/runner/widget_factory.py:13), [src/glider/gui/widgets/touch_widgets.py](src/glider/gui/widgets/touch_widgets.py) (812 lines)

```bash
$ grep -rn "RunnerDashboard(" src/
# (no output)
```

```bash
$ grep -rn "WidgetFactory\.create_widget\|WidgetFactory(" src/
src/glider/gui/runner/dashboard.py:129:            widget = WidgetFactory.create_widget(node)
src/glider/gui/runner/dashboard.py:154:            widget = WidgetFactory.create_widget(node)
```

`WidgetFactory` is only called from `RunnerDashboard` — which is itself never instantiated. The runner UI that the user actually sees in Pi mode is built ad-hoc in `main_window` and does not include any of this machinery.

**Why it matters.** *Operational + science correctness.* For a 480×800 touchscreen kiosk (the stated use case), the operator cannot press a virtual button to fire `ButtonNode.press()`. Combined with Section 4 Critical-1 (channel split) and Section 4 High-1 (zone wiring missing), **the entire flow-engine-driven interactive surface is non-functional in runner mode**.

**Fix.** Decide canonical path:
- **If `RunnerDashboard` is the future:** wire it in `_setup_runner_view` (somewhere in main_window):
  ```python
  self._runner_dashboard = RunnerDashboard(self)
  self._runner_dashboard.set_flow_engine(self._core.flow_engine)
  self._runner_dashboard.widget_value_changed.connect(self._on_runner_widget_value)
  runner_layout.addWidget(self._runner_dashboard)

  def _on_runner_widget_value(self, node_id, value):
      node = self._core.flow_engine.get_node(node_id) if self._core.flow_engine else None
      if node is None: return
      if hasattr(node, "press") and isinstance(value, bool):
          if value: node.press()
      elif hasattr(node, "set_value"):
          node.set_value(value)
      elif hasattr(node, "toggle"):
          node.toggle()
  ```
- **If the inline runner UI is canonical:** delete `RunnerDashboard`, `WidgetFactory`, and the unused half of `touch_widgets.py`. Dead code that *looks* like the right place to add features will mislead future contributors.

Add a smoke test asserting at least one `RunnerDashboard` is constructed when `ViewMode.RUNNER` is detected — CI catches the regression.

### Critical — ERROR state has no user-visible modal

[src/glider/gui/main_window.py:1026-1077, 1316-1319, 182](src/glider/gui/main_window.py:1026)

```python
def _on_core_state_change(self, state):
    state_name = state.name
    self.state_changed.emit(state_name)
    if hasattr(self, "_status_label"):
        self._status_label.setText(state_name)
        self._status_label.setProperty("statusState", state_name)
    # NO branch for state_name == "ERROR"

def _on_core_error(self, source, error):
    self.error_occurred.emit(source, str(error))  # signal has zero connect() calls
    logger.error(f"Error from {source}: {error}")
```

`grep` confirms `error_occurred` is defined at line 182 and emitted at line 1318. **Zero `connect()` subscribers.** Meanwhile `QMessageBox.critical` is used 7+ times in this same file for routine file-save / board-add / device-add errors. The pattern exists; it's just not wired to the safety-critical state path.

**Why it matters.** *Hardware safety + operational.* Per Section 1 C1, ERROR after STOP can mean "transient error, safe to power down" OR "a heater is still driving HIGH and you must not unplug." Both render as a red status label and a log line. UI half of the most dangerous bug in the application.

**Fix.** In `_on_core_state_change`, after the property update:
```python
if state_name == "ERROR":
    self._show_unsafe_modal()

def _show_unsafe_modal(self):
    failures = getattr(self._core, "last_shutdown_failures", [])
    detail = "\n".join(f"  - {f.device_id}: {f.error}" for f in failures) if failures else "Unknown"
    QMessageBox.critical(
        self, "UNSAFE STATE — Hardware may still be active",
        f"One or more devices failed to enter safe state.\n\n"
        f"Failed devices:\n{detail}\n\n"
        f"DO NOT power down hardware. Reconnect and manually verify outputs are low.",
        QMessageBox.StandardButton.Ok,
    )
```
Connect `error_occurred` to a similar modal so generic errors are also visible. Pair with Section 1's fix of adding a distinct `UNSAFE` `SessionState` (vs. generic `ERROR`).

## High findings

### High — `WidgetFactory.update_from_node` callbacks never deregistered; rebuild leaks dangling Qt-widget references

[src/glider/gui/runner/widget_factory.py:60-69](src/glider/gui/runner/widget_factory.py:60), [src/glider/gui/runner/dashboard.py:161-166](src/glider/gui/runner/dashboard.py:161)

```python
# widget_factory.py:
def update_from_node(*args):
    display_val = node.get_display_value()
    widget.set_value(display_val)  # closure-captures Qt widget

if hasattr(node, "register_update_callback"):
    node.register_update_callback(update_from_node)

# dashboard.py — clear_widgets:
def clear_widgets(self):
    for widget in self._widgets.values():
        widget.setParent(None)
        widget.deleteLater()
    self._widgets.clear()
    # No unregister_update_callback call.
```

There is **no `unregister_update_callback` API anywhere in the codebase** (Section 4 M-nodes-14). Once registered, `update_from_node` stays in `node._update_callbacks` forever. After `clear_widgets`, the closure still holds a strong reference to a `deleteLater`'d Qt widget — on the next node update, `widget.set_value(...)` hits a deleted C++ object → `RuntimeError: wrapped C/C++ object has been deleted` (segfault risk on Linux).

**Why it matters.** *Operational.* Dashboard rebuilds happen on layout-mode change, view-mode switch (Desktop↔Runner), and flow-engine reload. The dashboard works the first time and crashes on iteration. Latent today because `RunnerDashboard` is never instantiated (Critical-1) — but the moment it is, this fires.

**Fix.** (a) Add `BaseNode.unregister_update_callback(callback)`; (b) have `WidgetFactory.create_widget` return the registered callback; (c) `clear_widgets` deregisters before destroying widgets.

### High — `closeEvent` cancels tasks without awaiting cancellation; races with `_core.shutdown()`

[src/glider/gui/main_window.py:4906-4935](src/glider/gui/main_window.py:4906)

```python
for task in self._pending_tasks:
    if not task.done():
        task.cancel()  # advisory; not yet observed
self._pending_tasks.clear()

# Immediately:
future = asyncio.ensure_future(self._core.shutdown())
```

**Why it matters.** *Hardware safety.* `task.cancel()` schedules `CancelledError` at the next `await` point — it hasn't been observed by the coroutines yet. The next line clears `_pending_tasks` (the only references). A `_run_async(self._core.hardware_manager.set_output(pin, True))` task started 50ms before close fires its `write_digital` *after* `_core.shutdown` has set everything low.

**Fix.** Drain cancellation before shutdown:
```python
for task in list(self._pending_tasks):
    if not task.done(): task.cancel()
pending = list(self._pending_tasks)
if pending:
    drain = asyncio.ensure_future(asyncio.gather(*pending, return_exceptions=True))
    timeout = time.time() + 2.0
    while not drain.done() and time.time() < timeout:
        QApplication.processEvents()
self._pending_tasks.clear()
```

### High — Hardware-disconnection handler runs `pause()` and opens modal `exec()` concurrently

[src/glider/gui/main_window.py:1342-1349](src/glider/gui/main_window.py:1342)

```python
def _on_hardware_connection_change(self, board_id, state):
    ...
    self._run_async(self._core.pause())
    self._show_hardware_disconnection_dialog(board_id, state)  # dialog.exec() blocks Qt loop
```

**Why it matters.** *Operational, potentially hardware-safety.* `dialog.exec()` spins a nested Qt event loop; with qasync this fragile combination *usually* works but any `asyncio.sleep` inside `pause` may not wake while the modal is shown. User sees "Hardware disconnected, paused" dialog before pause is guaranteed to have completed; clicking "Reconnect" immediately tries to re-init on a board mid-safe-state.

**Fix.** Make handler `async`, `await self._core.pause()` first, then show dialog. Or gate "Reconnect" button on a `pause_complete` signal.

### High — Miniscope LED/EWL slots ignore return value; silent hardware failure

[src/glider/gui/dialogs/camera_settings_dialog.py:1107-1119](src/glider/gui/dialogs/camera_settings_dialog.py:1107)

```python
def _on_led_power_changed(self, value: int):
    self._led_power_label.setText(f"{value}%")
    if self._camera_manager is not None and self._camera_manager.is_connected:
        self._camera_manager.set_led_power(value)  # returns bool, ignored

def _on_ewl_focus_changed(self, value: int):
    self._ewl_focus_label.setText(str(value))
    if self._camera_manager is not None and self._camera_manager.is_connected:
        self._camera_manager.set_ewl_focus(value)  # returns bool, ignored
```

**Why it matters.** *Science correctness.* GUI half of Section 3 Critical-1. Slider shows 50%, label shows 50%; if `_send_miniscope_i2c_command` failed (subprocess non-zero exit, wrong OpenCV property, camera disconnected mid-call), the LED is at whatever it was before. Operator records `led_power=50` in lab notebook; actual LED was 0. Data at wrong illumination. Irreproducible.

**Fix.**
```python
def _on_led_power_changed(self, value: int):
    self._led_power_label.setText(f"{value}%")
    if self._camera_manager is not None and self._camera_manager.is_connected:
        ok = self._camera_manager.set_led_power(value)
        if not ok:
            self._led_power_label.setText(f"{value}% (failed)")
            self._led_power_label.setStyleSheet("color: red;")
            QMessageBox.warning(self, "LED Command Failed",
                f"Could not set LED power to {value}%. Check camera connection and miniscope mode.")
```
Pair with Section 3's fix to make `set_led_power` raise on out-of-range (vs silently clamp).

## Medium findings (13 total)

| # | File:line | Issue |
|---|---|---|
| M-gui-1 | `runner/dashboard.py:92-120` | `rebuild_dashboard` doesn't explicitly disconnect signals from previous widgets (clear_widgets does deleteLater, but explicit `disconnect()` is safer) |
| M-gui-2 | `controllers/device_control_controller.py:412-414` | `_poll_input` spawns `_run_async` task per timer tick with no in-flight flag; if device-read > poll_interval, tasks queue unboundedly — telemetrix hammered, memory grows |
| M-gui-3 | `controllers/device_control_controller.py:310-346` | `_on_pwm_changed`/`_on_servo_changed` fire `_run_async` per spinbox tick (every keystroke or scroll-wheel notch); ~20 writes/sec when holding arrows |
| M-gui-4 | `controllers/hardware_controller.py:111-117` | Baseline M20: `device.board is board` doesn't handle `device.board is None`. Still present |
| M-gui-5 | `controllers/hardware_controller.py:256-269` | Magic parent-traversal via `hasattr(parent, "_on_add_board")` + `parent._on_add_board()`. Breaks on reparent or rename. Use pyqtSignal |
| M-gui-6 | `gui/commands.py:93-127` | `MoveNodeCommand` undo/redo drift (see M13 above) |
| M-gui-7 | `gui/node_graph/graph_view.py:281-296` | `remove_node` doesn't `deleteLater()`; Qt scene takes ownership but Python-side cycles between NodeItem↔PortItem↔ConnectionItem may not collect on long editing sessions |
| M-gui-8 | `gui/node_graph/graph_view.py:521-526, 588-598` | Delete handlers iterate `selectedItems()` while mutating; safe only because Qt returns a copy. Snapshot with `list(...)` for defensive code |
| M-gui-9 | `gui/dialogs/experiment_dialog.py:349-364` | No validation; name length unbounded; can contain control chars that break tracking CSV |
| M-gui-10 | `gui/runner/dashboard.py:124-140` | Lambda signal connections never disconnected; if `rebuild_dashboard` ever skips `clear_widgets`, N×M connections accumulate |
| M-gui-11 | `gui/panels/camera_panel.py:399, 866-880` | `closeEvent` stops CV thread but never `remove_frame_callback(self._on_frame)` — dangling bound-method reference on camera's callback list |
| M-gui-12 | `gui/panels/camera_panel.py:681-682` | `self._multi_cam.on_frame(...)` registered but no remove on stop/close. Same as Section 3 M8 at GUI layer |
| M-gui-13 | `gui/main_window.py:4440-4441` | `_redo_command` reaches into `self._undo_stack._undo_stack.pop()` — direct private attribute access. Indicates redo is fundamentally not a clean abstraction |

## Low findings (selected)

- `view_manager.py:181-186` — `get_scrollbar_width()` returns hardcoded 40; QSS specifies 30 elsewhere. Single source of truth would help
- `main_window.py` — Hardcoded background colors inline at lines 335, 346, 350, 368, 385, 392, 638, 1110, 1184, 1298. Move to `styles/desktop.qss` and `styles/touch.qss`
- `runner/widget_factory.py:50` — `"AnalogReadNode": TouchLabel` displays a numeric input as a label; reasonable but undocumented intent
- `controllers/device_control_controller.py:64-68` — `_analog_callback_*` triple of instance attributes unused (dead state)
- `widgets/touch_widgets.py:28-34` — `_get_system_font()` returns a string but every TouchWidget hardcodes font-family via QSS — function unused
- `commands.py:269-272` — `UndoStack.clear()` clears stacks but `_update_undo_redo_actions()` isn't called after; menu items stale
- `main_window.py:949-950` — Two separate handlers for `_emergency_btn.clicked` and `emergency_action.triggered` — single named-Action would be cleaner
- `node_graph/graph_view.py:559-563` — Context-menu "Add Node" lists only 5 of ~30 registered node types; build dynamically from registry
- `dialogs/camera_settings_dialog.py:411-417` — Miniscope Mode checkbox tooltip says "v4l2-ctl commands"; true on Linux, but on Windows uses OpenCV `cap.set(...)`. Cross-platform behavior should be reflected

## Architecture notes

- **`main_window.py` urgently needs decomposition.** Baseline note still stands at 4937 LOC. Recent additions (Miniscope, runner UI, undo/redo glue) make every change ripple. Suggested split: (a) main_window shrinks to coordinator + menubar (≤500 LOC); (b) extract `gui/runner/runner_view.py` (where `RunnerDashboard` would be wired); (c) extract `gui/undo_controller.py` (owns undo stack + polymorphic `Command.redo()` dispatch); (d) extract `gui/shutdown_controller.py` for closeEvent. The device-control panel duplicated in lines 4509-4890 (when `DeviceControlController` exists) is a smoking-gun sign main_window is doing the controllers' work.

- **Two parallel runner-UI implementations.** `RunnerDashboard` + `WidgetFactory` + `TouchWidget*` (~1200 LOC) lives alongside an inline runner UI in main_window. Pick one, delete the other. This is the highest-leverage architectural cleanup.

- **`_run_async` should be a single shared utility** — not a method passed as `Callable` into every controller (5 controllers × 1 arg). A single `AsyncRunner` (or `gui/async_utils.py` with a Qt-signal for exceptions) lets the H7 exception-surfacing fix land in one place.

- **Cross-thread discipline is mostly OK.** `camera_panel.py` uses `pyqtSignal` to marshal frame data from capture to Qt thread (lines 221-222, 401-403, 510). `CVWorker` lives on its own `QThread` with `quit()/wait()` in `closeEvent`. *But* `register_update_callback` callbacks in `widget_factory.py` are invoked from wherever the node `update_event` fires (asyncio loop thread, not guaranteed-Qt). `widget.set_value(...)` from wrong thread is undefined; use `QMetaObject.invokeMethod(... Qt.QueuedConnection)` or wrap via signal/slot.

- **PyQt6 modal `exec()` + qasync is fragile.** Several sites call `dialog.exec()` from sync slots triggered by async tasks. Prefer non-modal dialogs (`dialog.show()` + signal-based response) for any dialog opened from an `_run_async` chain.

- **Undo/redo is half-built.** Should be pure GoF Command; instead it's a hybrid where `Command.execute()` is `pass` and real execution is done by the caller before pushing. Redo has to re-derive what `execute` would do. Either make `Command.execute()` authoritative (callers go through `Command(...).run()`) or make redo live on each command class.

- **Hardcoded QSS strings throughout.** Centralise into `gui/styles/`. The QSS files exist but a lot of styling is duplicated inline.

## What's good in this module

- **`_run_async` task tracking** is the right pattern; just needs exception inspection in done-callback to fully close H7.
- **`camera_panel.py`'s threading discipline is exemplary.** Frame callbacks marshalled via `pyqtSignal`; CVWorker on its own `QThread` with clean lifecycle. Lines 213-216 even include a "Thread Safety" docstring section. **Template for the rest of the GUI.**
- **`ViewManager`** — cleanest architectural piece. Single source of truth for mode/stylesheet/font.
- **`HardwareTreeController` and `DeviceControlController` are correctly factored** — encapsulated, take core + run_async callable, emit signals to parent. Pattern is sound; bug is that main_window keeps parallel copy of device control panel (lines 4509-4890).
- **`Command` hierarchy is right shape**, even with broken redo glue. Per-command classes fit Qt undo idiom; migratable to `QUndoStack`/`QUndoCommand` for free integration.
- **`RunnerDashboard` and `TouchWidget*` are well-designed touch widgets** — large hit targets (≥80px), high-contrast styling, kinetic scrolling. *If they were wired*, they'd be a solid runner UI. The implementations are not the problem.
- **Dialog QSS adaptation for touch mode** (`_get_touch_group_style`, `_is_touch_mode` branches in camera_settings_dialog) is thoughtful — same dialog renders differently on Pi vs desktop without code duplication.
- **Hardware disconnection routing to paused-experiment dialog** — *intent* is right (the bug is execution order). Operator-empathy code worth preserving.
- **No `eval`/`exec()`/`pickle`/`subprocess shell=True` anywhere in GUI.** Dynamic-code anti-patterns absent.

**Bottom line for `glider.gui`:** the architecture is mostly right (view_manager, controllers, _run_async tracking, camera-panel threading). Bugs cluster in three places: (1) runner-mode UI is half-built — touch-widget machinery is dead code (a complete subsystem nothing instantiates); (2) error/safety surfacing is invisible — ERROR state mutates a QSS property but never opens a modal, leaving the Section 1 C1 hardware-still-driving scenario silent; (3) `main_window.py` is too dense to audit confidently in one pass and continues to grow. The two new Criticals are both "the right code exists, it just isn't wired" — small fixes with large operator-safety impact. Recommended order: (a) wire ERROR → `QMessageBox.critical` (10 lines); (b) wire `RunnerDashboard` OR delete dead modules (1 day, choice required); (c) `_run_async` exception-surfacing (1 hour); (d) `closeEvent` cancellation drain (30 lines); (e) Miniscope return-value check (5 lines per slot). Then schedule a dedicated `main_window.py` review pass before the next significant feature lands.

---

# Section 8 — Tests + Packaging + CI/CD

**Reviewed:** 2026-05-24 · **Files:** 12 test files (~3,968 LOC), `pyproject.toml`, `glider.spec`, `.github/workflows/ci.yml`, `README.md`. Manuscript skipped per user instruction.

## Summary

- **Test coverage is the worst structural problem in the codebase.** Every load-bearing untested module from the 2026-04-20 baseline (`camera_manager.py`, `tracking_logger.py`, `data_recorder.py`, `hardware_manager.py`, `plugin_manager.py`, `pi_gpio_board.py`, `cv_processor.py`) **still has zero direct tests** — grep-verified. **No GUI tests exist** despite `pytest-qt` in dev deps. **No per-node-type tests** beyond `test_base_node.py` (which tests only the abstract base, not the 30+ concrete node classes where every Section 4 bug lives).
- **Existing tests are predominantly dataclass-shape tests, not behaviour tests.** At least 8 of 12 test files are dominated by `to_dict`/`from_dict` symmetry tests. `test_flow_engine.py` is 35 lines for a 963-LOC engine (only `init`, `register_node`, `start_stop` covered — 3 test functions, grep-verified). `test_telemetrix_board.py` is 30 lines for a 598-LOC board (2 test functions). **Zero concurrency / thread-safety / async-cancellation / timeout tests.**
- **Coverage upper bound: ~9% of LOC** has any test coverage. Branch coverage is much lower because tests check symmetry rather than logic paths.
- **Every Critical and High finding from Sections 1–7 would have been caught by a test that doesn't exist.** Section 6 Critical (node properties never serialize) is a 30-second round-trip test. Section 4 Critical-1 (dead callback channel) is a "register callback, fire exec, assert callback ran" test. Section 1 Criticals (writes survive STOP) are a "fire writes, click STOP, assert no further writes" test. Section 6 H4 (non-atomic save) is a "kill mid-write, reload, assert no corruption" test. **The fact that these bugs were found by code review and not by CI is direct evidence of the coverage gap.**
- **Packaging has three release-blockers.** `pyproject.toml` declares `requires-python = ">=3.9"` while README says "3.11, 3.12, 3.13" and CI tests 3.10/3.11/3.12 — **three contradictory version policies** (actually FIVE sources, no two agree). `MockBoard` is in `src/`, not `tests/`, so it ships to end users. No LICENSE file in the repo despite `license = {text = "MIT"}` in pyproject — **legally all-rights-reserved.**
- **`glider.spec` is missing ~90% of hidden imports.** No `picamera2`, `gpiozero`, `lgpio`, `serial.tools`, `httpx`, `ryvencore`, `adafruit_circuitpython_ads1x15`. Only 4 of ~30 node modules listed. No codesigning for macOS/Windows. PyInstaller is run **by hand with no CI smoke build** — first time someone builds a release on a fresh checkout, they discover what's missing.
- **CI is missing the things it most needs.** No coverage report (so "we have tests" is unverifiable). No PyInstaller smoke build. No type-check (mypy/pyright). Python 3.13 (advertised) not tested. **No Raspberry Pi target** — the entire `pi_gpio_board.py` codepath is never executed by CI.
- **README is 42 lines of "Documentation Coming Soon."** No LICENSE, no CITATION.cff, no CHANGELOG, no CONTRIBUTING, no screenshots, no hardware list, no troubleshooting. **For a scientific instrument asking labs to commit overnight unattended experiments to it, this is the single biggest user-adoption blocker.**

## Test coverage audit

For each load-bearing module from the baseline (verified by `grep -rln 'test_<module>' tests/`):

| Module | LOC | Direct tests |
|---|---|---|
| `vision/camera_manager.py` | 2,125 | none |
| `vision/tracking_logger.py` | 508 | none |
| `vision/cv_processor.py` | 937 | none |
| `vision/multi_camera_manager.py` | ~400 | none |
| `vision/multi_video_recorder.py` | ~300 | none |
| `vision/video_recorder.py` | ~400 | none |
| `vision/behavior_analyzer.py` | ~250 (new) | none |
| `core/data_recorder.py` | 386 | none |
| `core/hardware_manager.py` | 632 | only via integration fixture |
| `core/glider_core.py` | ~840 | none |
| `core/flow_engine.py` | 963 | 35-line file, 3 tests |
| `core/flow_function.py` | ~450 | none |
| `core/library.py` | ~270 | none |
| `plugins/plugin_manager.py` | 506 | none |
| `hal/boards/pi_gpio_board.py` | 337 | none |
| `hal/boards/telemetrix_board.py` | 598 | 30-line file, 2 tests |
| `hal/base_device.py` | ~860 | none |
| `hal/base_board.py` | ~370 | none |
| All `nodes/*` (30+ concrete classes) | 3,475 | only abstract base |
| All `gui/*` | 16,539 | none |
| `serialization/serializer.py` | ~450 | only schema |

### Critical (release readiness) — Test classification mismatch

By test method count across all 12 files:

- **`to_dict`/`from_dict`/round-trip tests:** ~85
- **Constructor / dataclass default tests:** ~40
- **State-machine / lifecycle / behaviour tests:** ~25
- **Error-path / edge-case tests:** ~8
- **Concurrency / thread-safety tests:** **0**
- **Async cancellation / timeout tests:** **0**

This ratio is exactly inverse to where the bugs are. Sections 1-7 found ~0 bugs in dataclass symmetry, ~15 Criticals in concurrency/lifecycle/callback orchestration, ~10 Criticals in async cancellation/timeout/event-loop blocking, ~20 Highs in error paths.

**Why it matters.** *Release readiness.* The tests as written give a green CI badge while the codebase has 8 confirmed Criticals from this review series. A team reading "all tests pass" and shipping a release will ship those Criticals. Tests must mirror bug risk.

### Critical — `MockBoard` fidelity is too thin (re-flag of Section 2 finding)

`conftest.py` provides a `mock_board` fixture that is a `MagicMock` with `AsyncMock` methods returning literal values. Section 2 Critical: `BaseBoard.emergency_stop` is a no-op the real `MockBoard` inherits silently. The MagicMock-based fixture in conftest is *worse* — no fidelity to the real interface contract. A test using this fixture cannot exercise e-stop semantics, callback dispatch threading, reconnect logic, hang detection, timeout behaviour, or partial-failure recovery.

**Fix.** Build out `tests/fixtures/fake_board.py` with a real Python class (not MagicMock) that implements `BaseBoard` faithfully with `inject_hang(method, duration)` and `inject_exception(method, exc)` hooks. This single fixture unlocks tests for every Section 1, 2, and 4 Critical.

## Missing tests that should exist

Each of these would catch at least one bug from this review series in CI before release. **Add these tests *before* fixing the underlying bugs** — a red CI test turns "we should fix this someday" into "the build is broken until we fix this."

| Priority | Test | Catches |
|---|---|---|
| Critical | Round-trip for every registered node (parametric) | Section 6 Critical (node properties never serialize) |
| Critical | Exec-output dispatch for every node | Section 4 Critical-1 (dead `_exec_callbacks` channel) |
| Critical | STOP semantics: writes after STOP must not fire | Section 1 Criticals (fire-and-forget propagation) |
| Critical | Atomic save: kill mid-write, reload, assert intact | Section 6 H4 + cascades |
| Critical | MockBoard fidelity (`inject_hang`, `inject_exception`) | Unblocks Sections 1/2/4 test work |
| Critical | Callback iteration thread-safety (self-unregister-during-iteration) | Section 1/2/3/4 callback races |
| High | Plugin failure rollback (registries snapshot/restore) | Section 6 C4 refinement |
| High | GUI smoke: construct `MainWindow`, assert title | Section 7 Critical-1 (runner dashboard) |
| High | Hardware tool blocked during RUNNING | C3 fix regression |
| High | Schema migration: v1 file loads in v2 GLIDER | Baseline M10 (unaddressed) |

## Packaging findings

### Critical — Python version policy contradicts itself in five places

```toml
# pyproject.toml
requires-python = ">=3.9"
classifiers = [..., "Programming Language :: Python :: 3.10/3.11/3.12/3.13"]
[tool.black]
target-version = ["py310", "py311", "py312"]   # no 3.13
```

```yaml
# .github/workflows/ci.yml
python-version: ["3.10", "3.11", "3.12"]
```

```markdown
# README.md
Python 3.11, 3.12, or 3.13
```

**Five sources, no two agree.** `pip install` allows Python 3.9; code fails at import on first `match` statement (3.10+) or PEP 604 `X | Y` union (3.10+). A new lab on 3.9 gets ImportError with no idea why.

**Fix.** Pick one. Recommended: `requires-python = ">=3.11,<3.14"`, classifiers 3.11/3.12/3.13, black `py311`, CI matrix 3.11/3.12/3.13, README "3.11, 3.12, 3.13" (already correct).

### Critical — No LICENSE file despite pyproject claiming MIT

`pyproject.toml:10` declares `license = {text = "MIT"}`. `ls /Users/garrettbradham/glider/LICENSE*` returns no matches. **The repo is legally all-rights-reserved** — `pip install` doesn't grant any rights; pyproject is a hint, not a licence. Additionally: if bundled YOLO model weights (`models/`) are from ultralytics, those are AGPL-3.0 — bundling AGPL models in an MIT-claimed installer violates AGPL terms.

**Fix.** Add `LICENSE` (MIT text) at repo root. Audit `models/` for licence terms; if AGPL, either remove from installer (download on first run) or re-licence the project.

### High — `MockBoard` ships to end users (`src/`, not `tests/`)

`mock_board.py` lives in `src/glider/hal/mock_board.py`. This means every `pip install glider` ships a 97-LOC mock. Two problems: (a) bloats the installer; (b) the mock can be accidentally imported in production code, masking real-hardware bugs.

**Fix.** Move to `tests/fixtures/mock_board.py`. Or, if it's needed at runtime (for "demo mode"), gate import behind an explicit `MockBoardForTesting` import path that doesn't collide with real boards in the factory.

### Medium — `optional-dependencies.pc` includes PyQt6 but plain `pip install glider` gives no GUI

A user doing `pip install glider` (the natural first command) gets no PyQt6 — the app fails at first import. `[pc]` extras must be specified explicitly. For a desktop scientific tool, GUI is not optional.

**Fix.** Move `PyQt6`, `pyqtgraph`, `qasync` to base `dependencies`. Keep `[rpi]` for Pi-only deps. Add `[ml]` for `ultralytics`/`torch` (currently in base, but only the YOLO tracking path needs them).

### Medium — `glider.spec` PyInstaller spec missing ~90% of hidden imports

```python
# glider.spec
hiddenimports = ['glider.nodes.experiment_nodes', ...]  # only 4 modules
```

Missing: `picamera2`, `gpiozero`, `lgpio`, `serial.tools`, `httpx`, `ryvencore`, `adafruit_circuitpython_ads1x15`, every plugin entry-point, and 26 of 30 node modules. Bundled app crashes on first non-trivial use with `ModuleNotFoundError`.

**Fix.** Use `from PyInstaller.utils.hooks import collect_submodules` and `hiddenimports = collect_submodules('glider') + collect_submodules('ryvencore') + ['picamera2', ...]`. Add CI smoke build that runs `dist/glider/glider --help` after `pyinstaller glider.spec`.

### Medium — No codesigning hooks for macOS/Windows

`glider.spec` builds `.app` and `.exe` but doesn't sign them. macOS users get "GLIDER cannot be opened because the developer cannot be verified"; Windows users get SmartScreen warning. For worldwide release, either (a) codesign (requires Apple Developer Program + Authenticode cert, ~$200/year combined) or (b) ship with prominent documentation that explains right-click→Open on macOS and "More info → Run anyway" on Windows.

## CI/CD findings

### Critical — No coverage reporting

CI runs `pytest tests/` with no `--cov`. Without coverage data, no signal about the 9% coverage gap, no PR gate. **Single most actionable lever for shipping stable.**

**Fix.**
```yaml
- run: pytest tests/ --cov=glider --cov-report=xml --cov-fail-under=10
- uses: codecov/codecov-action@v4
  if: matrix.os == 'ubuntu-latest' && matrix.python-version == '3.12'
```
Set `--cov-fail-under` to today's number, ratchet up 2-3% per release.

### Critical — Python 3.13 not tested despite being advertised

CI matrix: `3.10/3.11/3.12`. README: `3.11/3.12/3.13`. **Neither end is right.** Python 3.13 has changed asyncio internals — exactly the area with the most concurrency bugs in this codebase.

**Fix.** CI matrix `3.11/3.12/3.13` matching README.

### Critical — Tests not run on Raspberry Pi; entire Pi codepath uncovered

`hal/boards/pi_gpio_board.py` (337 LOC), Pi paths in `vision/camera_manager.py` (picamera2, miniscope I2C), and `optional-dependencies.rpi` are never executed by CI. A Pi-specific regression ships with no signal.

**Fix.** Cheapest path: add a Pi import-only job that installs `gpiozero` + `lgpio` and imports `pi_gpio_board`. Catches 50% of regressions for free. Long-term: self-hosted Pi runner with `[self-hosted, raspberry-pi]` label.

### High — No type-check (mypy/pyright)

Codebase has type hints throughout; CI doesn't enforce them. Static analysis catches in seconds what unit tests catch in hours.

**Fix.** Add `mypy src/glider --ignore-missing-imports --check-untyped-defs` to CI. Start permissive, tighten over time.

### High — No PyInstaller smoke build, no dependabot/security scanning

PyInstaller spec rots silently. No `.github/dependabot.yml`, no `pip-audit` — CVE in Pillow/ultralytics/httpx lands with no notification.

### Medium — `pytest-asyncio` mode not configured

`pyproject.toml` has `pytest-asyncio>=0.21.0` but no `asyncio_mode` configured. Default `strict` mode silently skips tests without `@pytest.mark.asyncio`. A contributor adding async tests won't know they're being skipped. Also: `event_loop` fixture in `conftest.py:21-26` is deprecated in pytest-asyncio 0.21+ and **will be removed in 1.0** — a future `pip install -U` breaks every async test.

**Fix.** Add `[tool.pytest.ini_options] asyncio_mode = "auto"` to pyproject. Delete the deprecated `event_loop` fixture; pytest-asyncio handles loop creation internally.

### Medium — `ruff` config doesn't include `S` (security) or `ASYNC` rules

Missing: `S` (catches `shell=True`, hardcoded passwords, `mktemp`), `ASYNC` (catches sync-blocking-call-in-async-function — directly relevant to Section 2 Critical-2 where `future.result(timeout=5.0)` blocks the qasync loop).

**Fix.** Add `"S"`, `"ASYNC"` to ruff `select` in pyproject. The Section 2 Telemetrix Critical would have been a lint error.

### Low — `actions/cache` not used; CI re-downloads pip wheels every run

~30s × 9 cells = 4.5min wasted per push. Add `cache: 'pip'` to `setup-python` action.

### Low — No release workflow

No `release.yml` for tag-triggered build/sign/publish. Releases are presumably manual.

## README / release-readiness findings

### Critical — README is 42 lines of "Documentation Coming Soon"

No description of *what GLIDER does*. No screenshots. No supported hardware list. No mention of the `GLIDER Software Design Document.pdf` in the repo root or `/docs/GLIDER_Technical_Documentation.pdf`. No troubleshooting. No LICENSE file in repo. No CITATION.cff for academic citation. No CHANGELOG.md. No CONTRIBUTING.md.

**Why it matters.** *Release readiness, user adoption, scientific reproducibility.* Scientific instruments are adopted by labs based on (1) reproducibility of results, (2) citation in published work, (3) reasonable confidence the tool will not corrupt experiments. README is the first signal for all three. "Documentation Coming Soon" tells a prospective user "this is alpha software you'll have to support yourself" — **fatal for adoption in lab settings**.

**Fix.** Minimum viable README (~300 lines) covering: what GLIDER does, screenshots, supported hardware list, install for non-developers, citation info, link to manuscript, troubleshooting, contributing guide. Add `LICENSE` (MIT text), `CITATION.cff` (with DOI placeholder), `CHANGELOG.md` (starting with `## [Unreleased]`), and `CONTRIBUTING.md`. ~1 day total.

## What's good

- **`tests/integration/test_experiment_workflow.py` is real integration testing**, not unit-in-disguise. The "create session → configure → save → load → assert" pattern is the right shape for science-data-flow correctness.
- **`tests/unit/serialization/test_schema.py` (471 lines) is the deepest test file** in the suite. Full round-trip coverage on every schema dataclass. **The model that should be applied to nodes (which has no equivalent).**
- **`tests/unit/vision/test_zones.py` (575 lines) and `test_calibration.py` (410 lines) are genuinely good behaviour tests** — point-in-polygon, point-in-circle, distance calibration math. The only `vision/` modules with proper test coverage.
- **`tests/unit/hal/test_pin_manager.py` (290 lines) covers the abstraction's contract well** — allocation, conflict detection, release, two-phase allocation. PinManager is also the cleanest abstraction in the HAL; tests reflect that.
- **CI runs all three platforms** (Ubuntu, Windows, macOS) on every push.
- **`fail-fast: false`** correctly set.
- **`QT_QPA_PLATFORM: offscreen`** correctly set in CI — GUI test infrastructure is in place, only the GUI tests themselves are missing.
- **`pyproject.toml` linter config is consistent** — ruff and black agree on line length, exclusions well-thought-out.
- **Bundle identifier is set** (`com.lainglab.glider`).
- **`MockBoard` exists as a real class** (foundation for the fidelity rebuild is in place).
- **No `print()` statements in tests** — consistent with the codebase-wide discipline.

---

# Release-readiness verdict (across all 8 sections)

GLIDER has the *right shape* for a serious scientific instrument and the *right discipline* in the small (no `eval`, no `pickle`, no `shell=True`, consistent logging, structured schema validation, clean PinManager abstraction). The work to date is the work of an engineering team that knows what good looks like.

It is **not ready for a 1.0.0 stable worldwide release tag yet.**

## Must-fix before 1.0.0 (release blockers)

1. **Section 6 Critical (node properties never serialize — `property_names` undefined everywhere).** Every saved experiment silently loses every node parameter. Single highest-impact bug in the codebase. ~1 day fix; ~1 hour for the round-trip test.
2. **Section 4 Critical-1 (two callback channels, only one wired — 6 node classes silently broken)** + Section 7 Critical-1 (RunnerDashboard never instantiated). Touch buttons, toggles, sequences, numeric inputs, zone-inputs all produce no output; the entire touch-runner UI is non-functional. ~1 day fix; ~1 hour for parametric "every node fires its exec output" test.
3. **Section 1 Criticals (fire-and-forget propagation tasks complete after STOP).** STOP doesn't actually halt in-flight hardware writes — direct hardware-safety risk. ~2 days fix; ~1 day tests.
4. **Section 2 Critical (PiGPIO pin desync + Telemetrix blocks qasync loop 5s + `_initialized` never cleared).** Three bugs violating the "non-blocking by design" HAL contract. UI freezes 5s per write on a wedged board. ~3 days; significant test work because `MockBoard` needs rebuilding first.
5. **Section 6 H4 — atomic save** (12 cascading paths). `.glider` files corrupt on power loss. ~1 day for the helper + migrate all call sites; ~1 hour for regression test.
6. **Section 3 Critical-1 (Miniscope LED/EWL unbounded values + helper inconsistency).** Public API silently clamps; lab notebook and hardware drift apart. ~0.5 day for range validation + tests.
7. **Section 7 Critical-1 and Critical-2 (RunnerDashboard wiring; ERROR has no modal).** Decide canonical runner UI path; wire `error_occurred` to `QMessageBox.critical`. ~1 day total.
8. **LICENSE file missing + potential AGPL/MIT YOLO model conflict.** Repo currently legally all-rights-reserved despite pyproject claim. Bundling AGPL YOLO weights in MIT installer violates AGPL terms. ~0.5 day to add LICENSE; audit `models/` for licence.
9. **Python version policy contradicts itself in 5 places** (>=3.9, 3.10-3.12, 3.11-3.13). Pick one, propagate everywhere. ~0.5 day.
10. **PyInstaller spec missing ~90% of hidden imports** — bundled app crashes on first non-trivial use. Fix with `collect_submodules` + CI smoke build. ~1 day.
11. **README is 42 lines of "Documentation Coming Soon."** Worldwide release without minimum README is dead-on-arrival for lab adoption. ~1 day for ~300-line README + LICENSE + CITATION.cff + CHANGELOG.md + CONTRIBUTING.md.
12. **Add the 10 high-leverage tests** (node round-trip, exec-output dispatch, STOP semantics, atomic save, callback iteration thread-safety, plugin failure rollback, GUI smoke, MockBoard fidelity, hardware-tools-blocked-during-RUNNING, schema migration). ~2 weeks of test work — but **without these every fix above is one PR away from regression**. Add them *before* the fixes.

**Estimated total release-blocker effort: 4–6 person-weeks** (heavily parallelisable once MockBoard fidelity is rebuilt).

## Strongly recommended before 1.0.0 (high-impact stability)

13. Section 1 H9 (FlowFunctionRunner subgraph tasks leak past timeout) + Section 4 Critical-3 (no `asyncio.wait_for` around node hardware writes) — same fire-and-forget family as #3.
14. Section 3 H1 (tracking CSV `writerow` has no try/except). 4 lines; rescues every experiment from a single bad write.
15. Section 6 C4 refinement (plugin setup-failure rollback, `sys.path` mutation). Plugin author can currently burn out system at startup.
16. CI: add `pytest-cov` with `--cov-fail-under`, mypy, PyInstaller smoke build, Python 3.13 to matrix. ~2 days.
17. `pytest-asyncio` mode (`asyncio_mode = "auto"`) + remove deprecated `event_loop` fixture. ~30 minutes.
18. Add CITATION.cff, CHANGELOG.md, CONTRIBUTING.md. ~1 day total.

## Defer post-1.0.0 (cleanup that won't block release)

- Full `main_window.py` decomposition (Section 7 architecture note) — 4937 LOC god object. Worth dedicated 1-week refactor as 1.1.
- Section 7 runner-mode dead-code cleanup (delete `RunnerDashboard` OR wire it — decision required, then ~3 days either way; combined with #2 above).
- Two-state-mechanism node refactor (Section 4 M-nodes-5) — better long-term but disruptive.
- Codesigning for macOS/Windows installers — required for *truly* worldwide release but defensible to ship as "right-click → Open" with documentation for 1.0.0, then add signing in 1.1.
- Self-hosted Pi runner — pragmatic to defer with import-only coverage in the meantime.
- Move `pandas` and `ultralytics` to optional-deps groups (saves 2 GB install for users who don't need ML).

## Bottom line

**GLIDER is currently a beta-quality 0.9 release marketed as a 1.0.** The engineering work to get to 1.0 is well-scoped (4–6 weeks if focused) and consists almost entirely of *finishing things that were started* — wiring connections that already exist (RunnerDashboard, error_occurred signal), serializing data that was already designed to be serialized (node properties via existing `to_dict`/`from_dict`), tracking tasks that already get spawned (fire-and-forget propagation), adding tests that the test infrastructure was set up to receive (qtbot, async fixtures, MockBoard scaffolding).

The single highest-leverage move is **add the 10 listed tests first, even before fixing the underlying bugs they expose.** A red CI test for every Critical turns "we should fix this someday" into "the build is broken until we fix this." Without those tests, fix work is a treadmill.

The README + LICENSE + CITATION work is small (~2 days) but is **the actual gate to "worldwide release."** Without those three, no lab outside LaingLab will adopt GLIDER even if every Critical is fixed. With them plus the test scaffolding, GLIDER becomes a credible 1.0 candidate that other labs can trust to run overnight unattended.
