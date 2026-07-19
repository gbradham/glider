"""
Atomic file writes.

Every save path in GLIDER that produces a JSON/text artifact (.glider files,
calibration files, zone configs, plugin configs, library entries, etc.) MUST
go through this helper. The reason is concrete: ``open(path, "w")`` truncates
the file before any bytes are written. A crash, power loss, disk-full, or
``KeyboardInterrupt`` between truncate and write completion leaves the file
empty or partial. For a scientific tool whose central artifact is the
``.glider`` experiment description, that loses irrecoverable work.

The helper writes to a sibling temp file, fsyncs, then ``os.replace``-renames
into place. ``os.replace`` is atomic on POSIX and on NTFS — readers either see
the old file or the new file, never a half-written one.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


def atomic_write_text(
    path: Union[str, os.PathLike], content: str, encoding: str = "utf-8"
) -> None:
    """
    Atomically write text content to ``path``.

    The parent directory is created if needed. On exceptions the temp file
    is removed; the target is never left partially written.

    Args:
        path: Destination file path (str or Path-like).
        content: Full text to write.
        encoding: Text encoding (default ``"utf-8"``).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # mkstemp returns an already-open low-level FD; using it (rather than
    # NamedTemporaryFile) lets us fsync explicitly before close.
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp = Path(tmp_name)

    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def atomic_write_bytes(path: Union[str, os.PathLike], content: bytes) -> None:
    """
    Atomically write binary content to ``path``.

    Mirror of :func:`atomic_write_text` for binary payloads.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp = Path(tmp_name)

    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
