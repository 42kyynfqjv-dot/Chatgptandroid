import base64
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


def validate_token(value: str, name: str) -> str:
    # 32 random bytes rendered by secrets.token_urlsafe(32) are 43 characters.
    # Entropy cannot be measured here; users must use the documented generator.
    if not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", value):
        raise ValueError(f"{name} must contain 32+ random bytes encoded as unpadded base64url")
    decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if len(decoded) < 32:
        raise ValueError(f"{name} is too short")
    return value


def relay_url(value: str, allow_loopback_http: bool = False) -> str:
    parsed = urlsplit(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("PIXEL_RELAY_URL must be an origin without credentials, path, query, or fragment")
    if not parsed.hostname:
        raise ValueError("PIXEL_RELAY_URL needs a host")
    if parsed.scheme != "https":
        if not (allow_loopback_http and parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "::1", "localhost")):
            raise ValueError("PIXEL_RELAY_URL requires HTTPS (HTTP is allowed only for explicit loopback development)")
    return value.rstrip("/")


@dataclass(frozen=True)
class Settings:
    operator_token: str
    device_token: str
    database: Path
    ttl_seconds: int = 120
    max_pending: int = 100
    max_records: int = 10000
    allow_loopback_http: bool = False

    def __post_init__(self):
        validate_token(self.operator_token, "PIXEL_OPERATOR_TOKEN")
        validate_token(self.device_token, "PIXEL_DEVICE_TOKEN")
        if secrets.compare_digest(self.operator_token, self.device_token):
            raise ValueError("Operator and device tokens must differ")
        if not 10 <= self.ttl_seconds <= 300:
            raise ValueError("TTL must be 10..300 seconds")
        if not 1 <= self.max_pending <= 100 or not self.max_pending <= self.max_records <= 10000:
            raise ValueError("Queue bounds must satisfy 1 <= pending <= 100 and pending <= records <= 10000")

    @classmethod
    def from_env(cls):
        return cls(
            operator_token=os.environ["PIXEL_OPERATOR_TOKEN"],
            device_token=os.environ["PIXEL_DEVICE_TOKEN"],
            database=Path(os.environ.get("PIXEL_DATABASE", "state/actions.sqlite3")),
            ttl_seconds=int(os.environ.get("PIXEL_TTL_SECONDS", "120")),
            allow_loopback_http=os.environ.get("PIXEL_ALLOW_LOOPBACK_HTTP") == "1",
        )
