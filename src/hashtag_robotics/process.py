from __future__ import annotations

import asyncio
import contextlib
import fcntl
import os
import pty
import signal
import struct
import termios
from pathlib import Path

import psutil

from hashtag_robotics.models import JobInputKey, JobProcess

KEY_BYTES: dict[JobInputKey, bytes] = {
    JobInputKey.ENTER: b"\r",
    JobInputKey.USE_EXISTING_CALIBRATION: b"\r",
    JobInputKey.RECALIBRATE: b"c\r",
    # LeRobot deliberately supports these one-byte aliases.  They are the
    # reliable control-plane contract: an escape sequence can be split or a
    # bare ESC can be swallowed while the listener waits to decide whether an
    # arrow key follows.  The dashboard is not a physical keyboard, so it must
    # not pretend to be one.
    JobInputKey.END_EPISODE: b"n",
    JobInputKey.RERECORD_EPISODE: b"r",
    JobInputKey.STOP_RECORDING: b"q",
}

BOOT_ID_PATH = Path("/proc/sys/kernel/random/boot_id")
TERMINAL_ROWS = 50
TERMINAL_COLUMNS = 200


class ProcessError(RuntimeError):
    pass


def current_boot_id() -> str | None:
    try:
        return BOOT_ID_PATH.read_text().strip()
    except OSError:
        # Darwin has no /proc boot UUID.  A stable boot epoch still separates
        # a stale PID from one created after a reboot, which is the safety
        # property the persisted process record needs.
        try:
            return f"boot-epoch-{int(psutil.boot_time())}"
        except (OSError, RuntimeError):
            return None


def _process_argv(pid: int) -> list[str]:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        try:
            return psutil.Process(pid).cmdline()
        except (psutil.Error, OSError):
            return []
    return [part for part in raw.decode(errors="replace").split("\0") if part]


def process_matches(record: JobProcess) -> bool:
    argv = _process_argv(record.pid)
    if not argv:
        return False
    expected = Path(record.executable).name
    # Console scripts use a Python shebang, so process metadata can expose
    # either the script itself or ``python <script>``.  Only the executable and
    # its possible interpreter slot are considered; arbitrary arguments must
    # never be allowed to turn a reused PID into a match.
    return any(Path(candidate).name == expected for candidate in argv[:2])


async def terminate_group(pgid: int, grace_seconds: float = 5.0) -> str:
    for order, current in enumerate((signal.SIGINT, signal.SIGTERM, signal.SIGKILL)):
        try:
            os.killpg(pgid, current)
        except ProcessLookupError:
            return "already-gone"
        except PermissionError as error:
            raise ProcessError(f"Cannot signal process group {pgid}.") from error
        deadline = grace_seconds if order == 0 else 2.0
        waited = 0.0
        while waited < deadline:
            await asyncio.sleep(0.2)
            waited += 0.2
            try:
                os.killpg(pgid, 0)
            except ProcessLookupError:
                return current.name
    return "escalated"


async def reap_orphan(record: JobProcess) -> str:
    if record.boot_id and record.boot_id != current_boot_id():
        return "stale-boot"
    if not process_matches(record):
        return "pid-reused"
    return await terminate_group(record.pgid)


class ManagedProcess:
    def __init__(
        self,
        executable: str,
        arguments: tuple[str, ...],
        environment: dict[str, str],
        interactive: bool = False,
    ) -> None:
        self.executable = executable
        self.arguments = arguments
        self.environment = environment
        self.interactive = interactive
        self._process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.StreamReader | None = None
        self._transport: asyncio.ReadTransport | None = None
        self._master: int | None = None
        self._pending = b""
        self._eof = False

    async def start(self) -> JobProcess:
        if self._process is not None:
            raise ProcessError("The managed process was already started.")
        environment = {**os.environ, **self.environment}
        if self.interactive:
            await self._start_with_pty(environment)
        else:
            await self._start_with_pipe(environment)

        process = self._process
        if process is None:
            raise ProcessError("The managed process failed to start.")
        return JobProcess(
            pid=process.pid,
            pgid=os.getpgid(process.pid),
            executable=self.executable,
            arguments=list(self.arguments),
            pty=self.interactive,
            boot_id=current_boot_id(),
        )

    async def _start_with_pipe(self, environment: dict[str, str]) -> None:
        self._process = await asyncio.create_subprocess_exec(
            self.executable,
            *self.arguments,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
            env=environment,
        )
        self._reader = self._process.stdout

    async def _start_with_pty(self, environment: dict[str, str]) -> None:
        master, slave = pty.openpty()
        _configure_terminal(slave)
        try:
            self._process = await asyncio.create_subprocess_exec(
                self.executable,
                *self.arguments,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                start_new_session=True,
                env=environment,
            )
        finally:
            os.close(slave)

        self._master = master
        os.set_blocking(master, False)
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.connect_read_pipe(
            lambda: protocol,
            os.fdopen(os.dup(master), "rb", 0),
        )
        self._reader = reader

    async def read_available(self, timeout: float = 0.2) -> list[str]:
        if self._reader is None:
            return []
        chunk = b""
        try:
            chunk = await asyncio.wait_for(self._reader.read(4096), timeout=timeout)
        except TimeoutError:
            chunk = b""
        except OSError:
            self._eof = True
        if chunk:
            self._pending += chunk
        elif self._reader.at_eof():
            self._eof = True

        # A reader that is already at EOF answers without ever awaiting, so a
        # caller polling `while returncode is None` would spin without giving
        # the loop a chance to deliver the child-exit callback that sets it.
        if not chunk:
            await asyncio.sleep(0)

        lines: list[str] = []
        while b"\n" in self._pending:
            raw, self._pending = self._pending.split(b"\n", 1)
            lines.append(raw.decode(errors="replace"))
        if not chunk and self._pending.strip():
            lines.append(self._pending.decode(errors="replace"))
            self._pending = b""
        return lines

    def write_key(self, key: JobInputKey) -> None:
        if not self.interactive or self._master is None:
            raise ProcessError("This command does not accept operator input.")
        if self._process is None or self._process.returncode is not None:
            raise ProcessError("The command is no longer running.")
        try:
            os.write(self._master, KEY_BYTES[key])
        except OSError as error:
            raise ProcessError(f"Could not deliver '{key.value}' to the command.") from error

    @property
    def at_eof(self) -> bool:
        return self._eof

    @property
    def returncode(self) -> int | None:
        return self._process.returncode if self._process else None

    async def wait(self) -> int:
        if self._process is None:
            raise ProcessError("The managed process was never started.")
        return await self._process.wait()

    async def stop(self, grace_seconds: float = 5.0) -> str:
        if self._process is None or self._process.returncode is not None:
            return "already-gone"
        try:
            pgid = os.getpgid(self._process.pid)
        except ProcessLookupError:
            # The child exited before its returncode was observed; there is no
            # group left to signal, and an emergency stop must not raise here.
            return "already-gone"
        outcome = await terminate_group(pgid, grace_seconds)
        with contextlib.suppress(ProcessLookupError):
            await self._process.wait()
        return outcome

    def close(self) -> None:
        if self._transport is not None:
            self._transport.close()
            self._transport = None
        if self._master is not None:
            with contextlib.suppress(OSError):
                os.close(self._master)
            self._master = None


def _configure_terminal(slave: int) -> None:
    with contextlib.suppress(OSError):
        attributes = termios.tcgetattr(slave)
        attributes[3] &= ~termios.ECHO
        termios.tcsetattr(slave, termios.TCSANOW, attributes)
    with contextlib.suppress(OSError):
        size = struct.pack("HHHH", TERMINAL_ROWS, TERMINAL_COLUMNS, 0, 0)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, size)
