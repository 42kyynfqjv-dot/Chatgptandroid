"""Export operator-only GPT Actions schema without reading credentials or state."""
import argparse
import json
import secrets
import tempfile
from pathlib import Path

from .config import Settings, relay_url
from .relay import create_app


def export_schema(origin: str) -> dict:
    # Ephemeral local state only; schema export must not need real session keys.
    with tempfile.TemporaryDirectory() as directory:
        settings = Settings(secrets.token_urlsafe(32), secrets.token_urlsafe(32), Path(directory) / "schema.sqlite3")
        schema = create_app(settings).openapi()
    schema["servers"] = [{"url": relay_url(origin)}]
    schema["info"]["description"] = "Prototype single-owner phone relay. Bearer API key is the session's operator credential. Every action still requires on-device confirmation. Action statuses never prove app-level completion."
    return schema


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", required=True, help="Actual public HTTPS relay origin")
    args = parser.parse_args()
    print(json.dumps(export_schema(args.origin), indent=2))
