"""Persistence for ordering sessions shared by the CLI and the TUI.

Snapshots live in `~/.saizeriya-cli/sessions.json` (override with
`SAIZERIYA_CLI_HOME`) and hold both the `ClientState` and the cookie jar, so a
session can be resumed from either front-end.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from .types import CartItem, ClientState


def cli_home() -> Path:
    """Return the directory holding persisted sessions."""
    raw = os.environ.get("SAIZERIYA_CLI_HOME")
    if raw:
        return Path(raw)
    return Path.home() / ".saizeriya-cli"


def sessions_path() -> Path:
    """Return the path of the sessions snapshot file."""
    return cli_home() / "sessions.json"


def read_sessions() -> dict[str, dict[str, Any]]:
    """Read every persisted session snapshot."""
    path = sessions_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_sessions(sessions: dict[str, dict[str, Any]]) -> None:
    """Overwrite the sessions snapshot file."""
    path = sessions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sessions, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def cart_item_to_dict(item: CartItem) -> dict[str, Any]:
    """Serialize a cart entry."""
    return {
        "id": item.id,
        "name": item.name,
        "price": item.price,
        "count": item.count,
        "reorder": item.reorder,
        "modId": item.mod_id,
        "modCount": item.mod_count,
    }


def state_to_dict(state: ClientState) -> dict[str, Any]:
    """Serialize a client state."""
    return {
        "baseURL": state.base_url,
        "nextId": state.next_id,
        "shopId": state.shop_id,
        "tableNo": state.table_no,
        "peopleCount": state.people_count,
        "token": state.token,
        "sessionId": state.session_id,
        "pageKind": state.page_kind,
        "cart": [cart_item_to_dict(item) for item in state.cart],
    }


def state_from_dict(data: dict[str, Any]) -> ClientState:
    """Deserialize a client state."""
    return ClientState(
        base_url=data["baseURL"],
        next_id=data["nextId"],
        shop_id=data["shopId"],
        table_no=data["tableNo"],
        people_count=data["peopleCount"],
        token=data.get("token"),
        session_id=data.get("sessionId"),
        page_kind=data["pageKind"],
        cart=[
            CartItem(
                id=c["id"],
                name=c.get("name"),
                price=c.get("price"),
                count=c["count"],
                reorder=c["reorder"],
                mod_id=c.get("modId", ""),
                mod_count=c.get("modCount", 0) or 0,
            )
            for c in data.get("cart", [])
        ],
    )


def cookies_to_pairs(http: httpx.Client) -> list[list[str]]:
    """Flatten a cookie jar into serializable name/value pairs."""
    return [[cookie.name, cookie.value or ""] for cookie in http.cookies.jar]


def make_http(cookies: list[Any] | None = None) -> httpx.Client:
    """Build an HTTP client seeded with previously saved cookies."""
    http = httpx.Client(follow_redirects=True)
    for entry in cookies or []:
        if isinstance(entry, (list, tuple)) and len(entry) >= 2:  # noqa: PLR2004
            http.cookies.set(str(entry[0]), str(entry[1]))
    return http


def save_session(name: str, http: httpx.Client, state: ClientState, created_at: int) -> None:
    """Persist a session snapshot under `name`."""
    sessions = read_sessions()
    sessions[name] = {
        "name": name,
        "state": state_to_dict(state),
        "cookies": cookies_to_pairs(http),
        "createdAt": created_at,
        "updatedAt": int(time.time() * 1000),
    }
    write_sessions(sessions)


def remove_session(name: str) -> None:
    """Delete the session snapshot stored under `name`."""
    sessions = read_sessions()
    sessions.pop(name, None)
    write_sessions(sessions)
