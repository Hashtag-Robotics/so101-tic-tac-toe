"""Drive the dashboard through Chrome DevTools so the physical UI can be screenshotted."""

from __future__ import annotations

import asyncio
import base64
import json
import sys
import urllib.request
from pathlib import Path

import websockets

SHOTS = Path(__file__).parent / "shots"
CDP = "http://127.0.0.1:9222/json"


async def send(socket, counter, method, params=None):
    counter[0] += 1
    await socket.send(json.dumps({"id": counter[0], "method": method, "params": params or {}}))
    while True:
        message = json.loads(await socket.recv())
        if message.get("id") == counter[0]:
            return message.get("result", {})


async def click(socket, counter, text, selector="button"):
    script = f"""
    (() => {{
      const nodes = [...document.querySelectorAll({selector!r})];
      const hit = nodes.find((node) => node.textContent.trim().includes({text!r}));
      if (!hit) return "missing";
      hit.click();
      return "clicked";
    }})()
    """
    result = await send(
        socket, counter, "Runtime.evaluate", {"expression": script, "returnByValue": True}
    )
    return result.get("result", {}).get("value")


async def shot(socket, counter, name):
    result = await send(socket, counter, "Page.captureScreenshot", {"captureBeyondViewport": True})
    (SHOTS / name).write_bytes(base64.b64decode(result["data"]))
    print("wrote", name)


async def main() -> None:
    targets = json.load(urllib.request.urlopen(CDP))
    page = next(item for item in targets if item["type"] == "page")
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=40_000_000) as socket:
        counter = [0]
        await send(socket, counter, "Page.enable")
        await send(socket, counter, "Runtime.enable")

        # Operate, switched to the real arm with the workspace acknowledged.
        await send(socket, counter, "Page.navigate", {"url": "http://127.0.0.1:8799/#operate"})
        await asyncio.sleep(3.5)
        print("real:", await click(socket, counter, "Gerçek robot"))
        await asyncio.sleep(0.6)
        print(
            "workspace:",
            await click(socket, counter, "", "input[type=checkbox]"),
        )
        await asyncio.sleep(2.2)
        await shot(socket, counter, "operate-real.png")

        # Setup, step five validation output.
        await send(socket, counter, "Page.navigate", {"url": "http://127.0.0.1:8799/#setup"})
        await asyncio.sleep(3.0)
        print("device:", await click(socket, counter, "SO-101 Follower"))
        await asyncio.sleep(0.8)
        print("validate:", await click(socket, counter, "Doğrula"))
        await asyncio.sleep(1.6)
        await shot(socket, counter, "setup-validate.png")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
