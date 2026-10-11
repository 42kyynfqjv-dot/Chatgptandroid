"""Run the source-tree MCP adapter independently of the caller's directory."""
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))

from pixel_bridge.mcp_server import main  # noqa: E402


if __name__ == "__main__":
    main()
