from __future__ import annotations

import os
import platform
import struct
import subprocess
import threading
from pathlib import Path
from typing import BinaryIO

RAW_FRAME_HEADER = struct.Struct("<4sIIIIQ")
RAW_FRAME_MAGIC = b"HRC1"

_compile_lock = threading.Lock()


class MacOSCaptureError(RuntimeError):
    pass


def ensure_avfoundation_uid_helper(data_dir: Path) -> Path:
    """Compile the tiny native uniqueID capture helper once per source version."""
    if platform.system() != "Darwin":
        raise MacOSCaptureError("The AVFoundation uniqueID camera backend requires macOS.")

    source = Path(__file__).with_name("avfoundation_uid_capture.swift")
    if not source.is_file():
        raise MacOSCaptureError(f"AVFoundation helper source is missing: {source}")

    binary = data_dir / "bin" / "avfoundation-uid-capture"
    with _compile_lock:
        if binary.is_file() and binary.stat().st_mtime_ns >= source.stat().st_mtime_ns:
            return binary

        binary.parent.mkdir(parents=True, exist_ok=True)
        temporary = binary.with_suffix(".building")
        try:
            result = subprocess.run(
                ["xcrun", "swiftc", "-O", str(source), "-o", str(temporary)],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise MacOSCaptureError(f"Could not compile AVFoundation helper: {error}") from error
        if result.returncode != 0 or not temporary.is_file():
            detail = (result.stderr or result.stdout).strip()
            raise MacOSCaptureError(
                "Could not compile the AVFoundation uniqueID helper"
                + (f": {detail}" if detail else ".")
            )
        temporary.chmod(0o755)
        os.replace(temporary, binary)
    return binary


def read_exact(stream: BinaryIO, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise EOFError(f"Camera stream ended with {remaining} byte(s) missing.")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_raw_frame(stream: BinaryIO) -> tuple[int, int, int, int, bytes]:
    header = read_exact(stream, RAW_FRAME_HEADER.size)
    magic, width, height, bytes_per_row, payload_size, timestamp_ns = RAW_FRAME_HEADER.unpack(
        header
    )
    if magic != RAW_FRAME_MAGIC:
        raise MacOSCaptureError("AVFoundation helper emitted an invalid frame header.")
    if not width or not height or bytes_per_row < width * 4:
        raise MacOSCaptureError(
            f"AVFoundation helper emitted invalid dimensions {width}x{height}/{bytes_per_row}."
        )
    expected = bytes_per_row * height
    if payload_size != expected:
        raise MacOSCaptureError(
            f"AVFoundation helper declared {payload_size} frame bytes; expected {expected}."
        )
    return width, height, bytes_per_row, timestamp_ns, read_exact(stream, payload_size)
