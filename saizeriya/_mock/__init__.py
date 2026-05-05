"""Mock HTTP server for Saizeriya's in-store ordering system."""

import argparse
from typing import TYPE_CHECKING

import uvicorn

from .server import CartLine, MenuItem, Server, Table, TableState
from .templates import OrderDisplayLine, RenderContext

if TYPE_CHECKING:
    from starlette.applications import Starlette


def app() -> Starlette:
    """Create a new mock server instance."""
    s = Server()
    return s.app


def main() -> None:
    """Start the mock server via uvicorn."""
    parser = argparse.ArgumentParser(description="Saizeriya mock server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    uvicorn.run("saizeriya._mock:app", host=args.host, port=args.port, reload=args.reload, factory=True)


__all__ = [
    "CartLine",
    "MenuItem",
    "OrderDisplayLine",
    "RenderContext",
    "Server",
    "Table",
    "TableState",
]
