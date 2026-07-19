# Contributing to GLIDER

Thanks for your interest. GLIDER is a scientific instrument that researchers rely on for reproducible experimental data, so the contribution bar is "would I trust this to run unattended overnight?"

This document covers the practical workflow. For architectural context, read [code-review-2.md](code-review-2.md) first — it documents the systems and known limitations.

---

## Getting set up

```bash
git clone https://github.com/LaingLab/glider
cd glider
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -e ".[pc,dev]"
```

Verify your environment works:

```bash
ruff check src tests
black --check src tests
pytest tests/ -v
glider --help
```

If any of those fail before you've touched a file, open an issue.

---

## Before you start work

**Open an issue first.** GLIDER is a small project with a focused scope. A PR that arrives without prior discussion is much more likely to be declined or reworked. Issues are also where compatibility constraints (Pi hardware, supported Python versions, manuscript-linked APIs) get surfaced before you've invested time.

For trivial fixes (typos, one-line bug fixes, obvious omissions): an issue is not required.

For new features, hardware drivers, or anything that changes saved-file format: an issue is required, and may also need a brief design note in the PR description.

---

## Code style

- **Formatter:** `black` with line length 100.
- **Linter:** `ruff` with the configuration in `pyproject.toml`. Don't disable rules to suppress your own warnings — fix the warning or open a discussion if the rule is wrong for this codebase.
- **Type hints:** strongly preferred on all public functions and methods. We don't yet enforce with `mypy` in CI but will in 1.1; new code should be type-clean.
- **Logging, not print:** every module has `logger = logging.getLogger(__name__)` at the top. Use it. The codebase is `print()`-free and we'd like to keep it that way.
- **No `eval`, `exec`, `pickle`, `shell=True`, `yaml.load` without `SafeLoader`.** This is checked by the security review process. If you genuinely need one of these (you almost certainly don't), open an issue first.
- **Async patterns:** every coroutine that does hardware I/O must have a timeout. The pattern is `await asyncio.wait_for(device.write(...), timeout=DEVICE_IO_TIMEOUT_S)`. Fire-and-forget `asyncio.create_task` without storing the task handle is a recipe for "STOP doesn't actually stop" bugs — see Section 1 of [code-review-2.md](code-review-2.md).

---

## Testing

Every PR must include tests for the change. Specifically:

- **New node type:** at minimum, a round-trip test (set every property, save state, load state, assert equality) and an exec-output dispatch test (register a callback, fire each exec output, assert the callback ran). See `tests/unit/nodes/test_base_node.py` for the pattern.
- **New hardware driver:** unit tests against a fake board (see `tests/fixtures/` — `FakeBoard` is being built out; if it's not yet present when you read this, use the existing `MockBoard` and document the gaps).
- **Bug fix:** a regression test that fails before your fix and passes after.

Run the suite locally before pushing:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src pytest tests/ -v
```

GUI tests use `pytest-qt`'s `qtbot` fixture. Don't add tests that require a real display.

---

## Hardware contributions

Adding support for a new board or device:

1. **Board:** subclass `BaseBoard` in `src/glider/hal/boards/`. Implement `connect`, `disconnect`, `set_pin_mode`, `write_digital`, `write_analog`, `read_digital`, `read_analog`, `emergency_stop`. **Every I/O method must be `async` and must have an internal timeout** — read [code-review-2.md](code-review-2.md) Section 2 to understand why.
2. **Device class:** subclass `BaseDevice` in `src/glider/hal/base_device.py`. Implement `initialize` and `shutdown`. Always clear `self._initialized = False` in `shutdown` (don't leave the device in a half-state if reinit fails).
3. **Entry point:** register the board in `pyproject.toml` under `[project.entry-points."glider.driver"]`. Document the wiring in `docs/`.
4. **Tests:** add a test file in `tests/unit/hal/`. Faithful fake boards beat MagicMocks every time.

---

## File format changes

Anything that touches `.glider` JSON schema, the per-node `to_dict` format, or the `ExperimentSchema` dataclasses is a **breaking change** unless explicitly migration-tested. The procedure:

1. Bump `SCHEMA_VERSION` in `src/glider/serialization/schema.py`.
2. Add a migration function that loads the old version and produces the new format.
3. Add a test fixture: an `.glider` file in the old format, plus a test that asserts it loads correctly in the new GLIDER.
4. Update `CHANGELOG.md` under `### Changed` with the migration note.

---

## Commit messages

Use imperative present tense ("Add", not "Added"). One-line summary on the first line, blank line, then body if needed.

Reference issues (`Fixes #123`, `Closes #456`) where applicable.

**Do not attribute commits to AI tools.** GLIDER is published scientific software. Authorship matters for academic integrity. If you used an AI assistant during development, that's fine, but the commit author and any acknowledgements should be human.

---

## Pull requests

- One logical change per PR. "Refactor X" + "Add feature Y" should be two PRs.
- Update `CHANGELOG.md` under `## [Unreleased]` in the same PR.
- If you touched anything in the "Known limitations" list of `CHANGELOG.md`, update or remove that bullet.
- The PR description should include: what the change does, why it's needed, how you tested it, and any backwards-compatibility implications.

---

## Reporting bugs

When opening a bug report, please include:

- **Platform** (OS, Python version, GLIDER version)
- **Hardware** (board type, devices connected)
- **Steps to reproduce**
- **Expected vs. actual behavior**
- **Logs** — GLIDER writes structured logs; include the last 100 lines from `~/.glider/logs/` if available
- **`.glider` file** if relevant (sanitise any subject IDs first)

Bugs that involve potential data corruption (CSV truncation, video file unplayable, wrong sensor values) or hardware safety (outputs driving after STOP, hung shutdown) are highest priority and should be tagged `safety`.

---

## License

By contributing, you agree your contributions will be licensed under the MIT License (see [LICENSE](LICENSE)).
