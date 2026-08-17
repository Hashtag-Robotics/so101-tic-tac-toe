from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import requires_lerobot

from hashtag_robotics.models import JobInputKey, JobProcess
from hashtag_robotics.process import (
    ManagedProcess,
    ProcessError,
    current_boot_id,
    process_matches,
    reap_orphan,
)

FAKE_CALIBRATE = """
import sys

print("-------------------------------------------", flush=True)
print("NAME            |    MIN |    POS |    MAX", flush=True)
print("shoulder_pan    |   1114 |   2000 |   3027", flush=True)
sys.stdout.write("Move follower01 to the middle of its range of motion and press ENTER....")
sys.stdout.flush()
input()
print("Calibration saved to /tmp/hashtag/follower01.json", flush=True)
"""

FAKE_STREAM = """
for index in range(3):
    print(f"Teleop loop time: 1{index}.00ms (30 Hz)", flush=True)
"""

FAKE_GROUP = """
import os
import subprocess
import sys
import time

child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
print(f"child={child.pid}", flush=True)
time.sleep(60)
"""

FAKE_LEROBOT_CONTROLS = """
import time
from hashtag_robotics.lerobot_wrappers import _force_terminal_recording_controls
from lerobot.utils.keyboard_input import init_keyboard_listener

_force_terminal_recording_controls()
listener, events = init_keyboard_listener()
print("RECORDER_READY", flush=True)
try:
    while not events["stop_recording"]:
        if events["exit_early"]:
            events["exit_early"] = False
            events["rerecord_episode"] = False
        time.sleep(0.01)
finally:
    if listener is not None:
        listener.stop()
"""


def write_script(tmp_path: Path, name: str, body: str) -> str:
    script = tmp_path / name
    script.write_text(body)
    return str(script)


async def drain_until(
    managed: ManagedProcess,
    predicate: Callable[[str], bool],
    timeout: float = 15.0,
) -> list[str]:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    collected: list[str] = []
    while loop.time() < deadline:
        for line in await managed.read_available(timeout=0.2):
            collected.append(line)
            if predicate(line):
                return collected
        if managed.at_eof and managed.returncode is not None:
            break
    raise AssertionError(f"Predicate was never satisfied. Saw: {collected}")


async def test_pty_process_delivers_operator_enter(tmp_path: Path) -> None:
    managed = ManagedProcess(
        sys.executable,
        (write_script(tmp_path, "fake_calibrate.py", FAKE_CALIBRATE),),
        {},
        interactive=True,
    )
    record = await managed.start()
    assert record.pty is True
    assert record.pid == record.pgid
    assert record.boot_id == current_boot_id()
    assert process_matches(record) is True
    try:
        await drain_until(managed, lambda line: "press ENTER" in line)
        managed.write_key(JobInputKey.ENTER)
        await drain_until(managed, lambda line: "Calibration saved to" in line)
        assert await managed.wait() == 0
    finally:
        await managed.stop()
        managed.close()


async def test_pty_does_not_echo_injected_keys(tmp_path: Path) -> None:
    managed = ManagedProcess(
        sys.executable,
        (write_script(tmp_path, "fake_calibrate.py", FAKE_CALIBRATE),),
        {},
        interactive=True,
    )
    await managed.start()
    try:
        await drain_until(managed, lambda line: "press ENTER" in line)
        managed.write_key(JobInputKey.ENTER)
        lines = await drain_until(managed, lambda line: "Calibration saved to" in line)
        assert all("^M" not in line for line in lines)
        await managed.wait()
    finally:
        await managed.stop()
        managed.close()


@requires_lerobot
async def test_dashboard_controls_receive_real_lerobot_acknowledgements(tmp_path: Path) -> None:
    """Exercise LeRobot's actual terminal listener without connecting hardware."""
    managed = ManagedProcess(
        sys.executable,
        (write_script(tmp_path, "fake_lerobot_controls.py", FAKE_LEROBOT_CONTROLS),),
        {},
        interactive=True,
    )
    await managed.start()
    try:
        await drain_until(managed, lambda line: "RECORDER_READY" in line)
        managed.write_key(JobInputKey.END_EPISODE)
        await drain_until(managed, lambda line: "Right arrow key pressed" in line)
        managed.write_key(JobInputKey.RERECORD_EPISODE)
        await drain_until(managed, lambda line: "Left arrow key pressed" in line)
        managed.write_key(JobInputKey.STOP_RECORDING)
        await drain_until(managed, lambda line: "Escape key pressed" in line)
        assert await managed.wait() == 0
    finally:
        await managed.stop()
        managed.close()


async def test_pipe_process_streams_lines_and_rejects_input(tmp_path: Path) -> None:
    managed = ManagedProcess(
        sys.executable,
        (write_script(tmp_path, "fake_stream.py", FAKE_STREAM),),
        {},
        interactive=False,
    )
    record = await managed.start()
    assert record.pty is False
    try:
        await drain_until(managed, lambda line: "12.00ms" in line)
        with pytest.raises(ProcessError, match="operator input"):
            managed.write_key(JobInputKey.ENTER)
        assert await managed.wait() == 0
    finally:
        await managed.stop()
        managed.close()


async def test_stop_terminates_the_whole_process_group(tmp_path: Path) -> None:
    managed = ManagedProcess(
        sys.executable,
        (write_script(tmp_path, "fake_group.py", FAKE_GROUP),),
        {},
        interactive=False,
    )
    await managed.start()
    lines = await drain_until(managed, lambda line: line.startswith("child="))
    child_pid = int(lines[-1].split("=", 1)[1])

    outcome = await managed.stop(grace_seconds=1.0)
    managed.close()
    assert outcome != "already-gone"
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)


async def test_reap_orphan_never_signals_after_a_reboot() -> None:
    record = JobProcess(
        pid=os.getpid(),
        pgid=os.getpgid(0),
        executable="lerobot-calibrate",
        boot_id="00000000-0000-0000-0000-000000000000",
    )
    assert await reap_orphan(record) == "stale-boot"


async def test_reap_orphan_never_signals_a_reused_pid() -> None:
    record = JobProcess(
        pid=os.getpid(),
        pgid=os.getpgid(0),
        executable="lerobot-calibrate",
        boot_id=current_boot_id(),
    )
    assert await reap_orphan(record) == "pid-reused"
