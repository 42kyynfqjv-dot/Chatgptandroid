"""Real SDK client -> stdio subprocess -> loopback relay -> durable queue."""
import asyncio
import os
import secrets
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path

import uvicorn
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from pixel_bridge.config import Settings
from pixel_bridge.models import DeviceResult
from pixel_bridge.relay import create_app
from pixel_bridge.store import Store


class StdioProtocolTest(unittest.IsolatedAsyncioTestCase):
    async def test_actual_sdk_stdio_tools_and_relay_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(secrets.token_urlsafe(32), secrets.token_urlsafe(32), Path(directory) / "test.sqlite3", allow_loopback_http=True)
            store = Store(settings)
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            server = uvicorn.Server(uvicorn.Config(create_app(settings, store), log_level="error", access_log=False, proxy_headers=False))
            thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
            thread.start()
            try:
                for _ in range(500):
                    if server.started:
                        break
                    await asyncio.sleep(0.01)
                self.assertTrue(server.started, "Loopback relay did not start")
                environment = dict(os.environ)
                environment.pop("PIXEL_DEVICE_TOKEN", None)
                environment.update(PIXEL_RELAY_URL=f"http://127.0.0.1:{port}", PIXEL_OPERATOR_TOKEN=settings.operator_token, PIXEL_ALLOW_LOOPBACK_HTTP="1")
                # A local test socket is not an external network destination.
                # Preserve every proxy variable, adding only loopback to NO_PROXY.
                for name in ("NO_PROXY", "no_proxy"):
                    environment[name] = environment.get(name, "") + ",127.0.0.1,localhost"
                launcher = Path(__file__).resolve().parents[1] / "run_mcp.py"
                params = StdioServerParameters(command=sys.executable, args=[str(launcher)], env=environment, cwd=tempfile.gettempdir())
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        listing = await session.list_tools()
                        self.assertEqual({tool.name for tool in listing.tools}, {"open_app", "set_alarm", "get_action_status"})
                        called = await session.call_tool("open_app", {"app": "clock", "idempotency_key": "stdio_open_12345678"})
                        self.assertFalse(called.isError, called)
                        action = called.structuredContent
                        self.assertEqual(action["status"], "queued")
                        claimed = store.claim()
                        self.assertEqual(claimed.id, action["id"])
                        store.report(claimed.id, DeviceResult(status="handed_off", detail="Test harness intent handoff"))
                        checked = await session.call_tool("get_action_status", {"action_id": claimed.id})
                        self.assertEqual(checked.structuredContent["status"], "handed_off")
                        repeated = await session.call_tool("open_app", {"app": "clock", "idempotency_key": "stdio_open_12345678"})
                        self.assertEqual(repeated.structuredContent["id"], claimed.id)
                        self.assertIsNone(store.claim())
                        alarm = await session.call_tool("set_alarm", {"hour": 7, "minute": 30, "label": "Wake up", "idempotency_key": "stdio_alarm_1234567"})
                        self.assertFalse(alarm.isError, alarm)
                        self.assertEqual(alarm.structuredContent["params"]["hour"], 7)
                        invalid = await session.call_tool("open_app", {"app": "shell", "idempotency_key": "stdio_bad_123456789"})
                        self.assertTrue(invalid.isError)
                        for hour in (True, 24):
                            invalid_alarm = await session.call_tool("set_alarm", {"hour": hour, "minute": 30, "idempotency_key": "stdio_bad_alarm_123456"})
                            self.assertTrue(invalid_alarm.isError)
            finally:
                server.should_exit = True
                await asyncio.to_thread(thread.join, 5)
                sock.close()
                self.assertFalse(thread.is_alive(), "Test relay failed to shut down")
