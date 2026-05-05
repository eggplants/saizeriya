"""Mock HTTP server for Saizeriya's in-store ordering system."""

from typing import TYPE_CHECKING

from .server import CartLine, MenuItem, Server, Table, TableState
from .templates import OrderDisplayLine, RenderContext

if TYPE_CHECKING:
    from starlette.applications import Starlette


def app() -> Starlette:
    """Create a new mock server instance."""
    s = Server()
    return s.app


__all__ = [
    "CartLine",
    "MenuItem",
    "OrderDisplayLine",
    "RenderContext",
    "Server",
    "Table",
    "TableState",
]
