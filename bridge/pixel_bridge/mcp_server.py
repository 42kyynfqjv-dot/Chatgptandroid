"""Official MCP Python SDK adapter; normal mode is stdio."""
import argparse
import os
from uuid import UUID

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .config import relay_url, validate_token
from .models import Action, AlarmRequest, AppName, Hour, IdempotencyKey, Label, Minute, OpenAppRequest


class RelayClient:
    def __init__(self):
        self.origin = relay_url(os.environ["PIXEL_RELAY_URL"], os.environ.get("PIXEL_ALLOW_LOOPBACK_HTTP") == "1")
        self.token = validate_token(os.environ["PIXEL_OPERATOR_TOKEN"], "PIXEL_OPERATOR_TOKEN")

    async def call(self, method: str, path: str, payload: dict | None = None) -> Action:
        # No automatic retry: an interrupted response does not mean no action.
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            try:
                response = await client.request(method, self.origin + path, json=payload,
                                                headers={"Authorization": "Bearer " + self.token})
            except httpx.HTTPError:
                raise ValueError("Relay response unavailable. Do not create another action. Retry only with the identical idempotency key, or query the known action ID.") from None
        if response.status_code != 200:
            raise ValueError(f"Relay returned HTTP {response.status_code}; no success is implied. Preserve the original idempotency key.")
        return Action.model_validate(response.json())


def create_server() -> FastMCP:
    relay = RelayClient()
    server = FastMCP("Pixel action bridge", host="127.0.0.1", port=8766,
                     instructions="Single owner and device. Every phone action needs visible approval on the phone. handed_off means Android received an intent; it does not prove an alarm was saved or an app opened. Never replay unknown actions or invent their result.")
    write = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True)

    @server.tool(annotations=write)
    async def open_app(app: AppName, idempotency_key: IdempotencyKey) -> Action:
        """Request a visible, confirmed app launch. Use a unique random 16..80 character URL-safe key per authorized request; reuse it only when recovering the same request."""
        request = OpenAppRequest(action="open_app", params={"app": app}, idempotency_key=idempotency_key)
        return await relay.call("POST", "/v1/actions", request.model_dump())

    @server.tool(annotations=write)
    async def set_alarm(hour: Hour, minute: Minute, idempotency_key: IdempotencyKey, label: Label = "") -> Action:
        """Request Clock for device-local hour/minute after on-device approval. Clock may display or create the alarm; inspect and confirm the desired time there. A handoff never proves the alarm exists."""
        request = AlarmRequest(action="set_alarm", params={"hour": hour, "minute": minute, "label": label}, idempotency_key=idempotency_key)
        return await relay.call("POST", "/v1/actions", request.model_dump())

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
    async def get_action_status(action_id: str) -> Action:
        """Read queue/handoff status. unknown must be reconciled on the phone and must not trigger automatic replay."""
        return await relay.call("GET", "/v1/actions/" + str(UUID(action_id)))

    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio",
                        help="HTTP binds only 127.0.0.1:8766; it has no OAuth and must never be exposed directly")
    args = parser.parse_args()
    create_server().run(transport=args.transport)


if __name__ == "__main__":
    main()
