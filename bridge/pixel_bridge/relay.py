"""HTTPS reverse-proxy target; credentials and routing are server-owned."""
import ipaddress
import secrets
import sqlite3
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings
from .models import Action, CreateAction, DeviceResult, NextAction
from .store import Store, StoreError


class RequestBoundary:
    def __init__(self, app, allow_loopback_http: bool):
        self.app, self.allow_loopback_http = app, allow_loopback_http

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        upstream_send = send
        async def private_send(message):
            if message["type"] == "http.response.start":
                message = {**message, "headers": [*message.get("headers", []), (b"cache-control", b"no-store")]}
            await upstream_send(message)
        send = private_send
        if scope["scheme"] != "https":
            client_ip = (scope.get("client") or ("", 0))[0]
            try:
                local = ipaddress.ip_address(client_ip).is_loopback
            except ValueError:
                local = False
            if not (self.allow_loopback_http and local):
                await JSONResponse({"detail": "HTTPS required"}, 400)(scope, receive, send)
                return
        size = 0
        async def bounded_receive():
            nonlocal size
            message = await receive()
            size += len(message.get("body", b""))
            if size > 4096:
                raise HTTPException(413, "Request body exceeds 4096 bytes")
            return message
        await self.app(scope, bounded_receive, send)


def create_app(settings: Settings | None = None, store: Store | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = store or Store(settings)
    app = FastAPI(title="Pixel action relay", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(RequestBoundary, allow_loopback_http=settings.allow_loopback_http)
    bearer = HTTPBearer(auto_error=False)

    def role(expected: str):
        def check(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
            if credentials is None:
                raise HTTPException(401, "Bearer authentication required", headers={"WWW-Authenticate": "Bearer"})
            if not secrets.compare_digest(credentials.credentials.encode("utf-8"), expected.encode("ascii")):
                raise HTTPException(403, "Credential not authorized for this role")
        return check

    operator, device = role(settings.operator_token), role(settings.device_token)

    @app.exception_handler(StoreError)
    async def store_error(_request: Request, exc: StoreError):
        return JSONResponse({"detail": exc.detail}, exc.status_code)

    @app.exception_handler(sqlite3.Error)
    async def database_error(_request: Request, _exc: sqlite3.Error):
        return JSONResponse({"detail": "Storage unavailable; retry only the identical idempotency key"}, 503)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        # Do not reflect bodies or authentication values into logs/client errors.
        return JSONResponse({"detail": [{"loc": list(e["loc"]), "type": e["type"]} for e in exc.errors()]}, 422)

    @app.post("/v1/actions", response_model=Action, dependencies=[Depends(operator)], operation_id="requestDeviceAction",
              openapi_extra={"x-openai-isConsequential": True},
              description="Queue a phone action for explicit on-device confirmation. Use a new random idempotency key per user-authorized request; reuse the same key only to recover an uncertain response. Never infer completion from handoff.")
    def request_action(request: CreateAction):
        return store.create(request)

    @app.get("/v1/actions/{action_id}", response_model=Action, dependencies=[Depends(operator)], operation_id="getActionStatus")
    def get_action(action_id: UUID):
        return store.get(str(action_id))

    @app.get("/v1/device/next", response_model=NextAction, dependencies=[Depends(device)], include_in_schema=False)
    def next_action():
        return NextAction(action=store.claim())

    @app.post("/v1/device/actions/{action_id}/result", response_model=Action, dependencies=[Depends(device)], include_in_schema=False)
    def report(action_id: UUID, result: DeviceResult):
        return store.report(str(action_id), result)

    return app
