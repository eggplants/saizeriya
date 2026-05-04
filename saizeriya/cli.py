"""Interactive CLI for `saizeriya`."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shlex
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

import httpx

from . import fetch_menu
from .client import SaizeriyaClient
from .types import AccountSummary, CartItem, ClientState

USAGE = """\
Usage:
  saizeriya start <name> <qrurl> [--people <count>]
  saizeriya use <name>
  saizeriya list
  saizeriya rm <name>
  saizeriya fetch-menu [--out <path>] [--shop <id>]... [--max-code <n>]
                       [--table-no <n>] [--people <n>] [--lng <n>]
                       [--no-shuffle]

After start/use, available commands:
  state
  people <count>
  lookup <code>
  add <code> [count] [--mod-id <id>] [--mod-count <count>] [--reorder]
  cart
  cart-page
  remove <index>
  submit
  account
  receipt
  call [staff|dessert]
  menu
  history
  reorder <code>
  alcohol
  check <order|last|midnight>
  help
  exit"""


class _ReplParseError(Exception):
    """Raised when REPL argument parsing fails."""


class _ReplArgumentParser(argparse.ArgumentParser):
    """Argument parser that raises instead of terminating the process."""

    def error(self, message: str) -> NoReturn:
        raise _ReplParseError(message)

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        if message:
            raise _ReplParseError(message)
        detail = f"exit status {status}"
        raise _ReplParseError(detail)


def _cli_home() -> Path:
    raw = os.environ.get("SAIZERIYA_CLI_HOME")
    if raw:
        return Path(raw)
    return Path.home() / ".saizeriya-cli"


def _sessions_path() -> Path:
    return _cli_home() / "sessions.json"


def _read_sessions() -> dict[str, dict[str, Any]]:
    path = _sessions_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_sessions(sessions: dict[str, dict[str, Any]]) -> None:
    path = _sessions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sessions, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _cart_item_to_dict(item: CartItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "price": item.price,
        "count": item.count,
        "reorder": item.reorder,
        "modId": item.mod_id,
        "modCount": item.mod_count,
    }


def _state_to_dict(state: ClientState) -> dict[str, Any]:
    return {
        "baseURL": state.base_url,
        "nextId": state.next_id,
        "shopId": state.shop_id,
        "tableNo": state.table_no,
        "peopleCount": state.people_count,
        "token": state.token,
        "sessionId": state.session_id,
        "pageKind": state.page_kind,
        "cart": [_cart_item_to_dict(item) for item in state.cart],
    }


def _state_from_dict(data: dict[str, Any]) -> ClientState:
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


def _cookies_to_pairs(http: httpx.Client) -> list[list[str]]:
    return [[cookie.name, cookie.value or ""] for cookie in http.cookies.jar]


def _save_session(name: str, http: httpx.Client, client: SaizeriyaClient, created_at: int) -> None:
    sessions = _read_sessions()
    sessions[name] = {
        "name": name,
        "state": _state_to_dict(client.get_state()),
        "cookies": _cookies_to_pairs(http),
        "createdAt": created_at,
        "updatedAt": int(time.time() * 1000),
    }
    _write_sessions(sessions)


def _make_http(cookies: list[Any] | None = None) -> httpx.Client:
    http = httpx.Client(follow_redirects=True)
    for entry in cookies or []:
        if isinstance(entry, (list, tuple)) and len(entry) >= 2:  # noqa: PLR2004
            http.cookies.set(str(entry[0]), str(entry[1]))
    return http


def _print_state(state: ClientState) -> None:
    print(  # noqa: T201
        f"shop={state.shop_id} table={state.table_no} "
        f"people={state.people_count} page={state.page_kind} cart={len(state.cart)}",
    )


def _print_lookup(result: dict[str, Any]) -> None:
    if result.get("result") != "OK" or not result.get("item_data"):
        print(result)  # noqa: T201
        return
    item = result["item_data"]
    availability = "sold out" if item.get("state") == 0 else "available"
    print(f"{item.get('id', '')} {item.get('name', '')} {item.get('price', '')}yen {availability}")  # noqa: T201
    if item.get("mod_id"):
        print(f"modifier: {item['mod_id']} {item.get('mod_name', '')}")  # noqa: T201
    for msg in item.get("messages", []) or []:
        print(msg)  # noqa: T201


def _print_cart(state: ClientState) -> None:
    if not state.cart:
        print("Cart is empty.")  # noqa: T201
        return
    for index, item in enumerate(state.cart):
        price = "" if item.price is None else f" {item.price}yen"
        name = item.name or ""
        print(f"{index + 1}. {item.id} x{item.count} {name}{price}")  # noqa: T201


def _print_account(account: AccountSummary) -> None:
    if not account.lines:
        print("No account lines.")  # noqa: T201
    for line in account.lines:
        print(f"{line.name} x{line.count} {line.price}yen")  # noqa: T201
    print(f"total: {account.total}yen ({account.count} items)")  # noqa: T201
    if account.control_no:
        print(f"control: {account.control_no}")  # noqa: T201


def _build_repl_parser() -> _ReplArgumentParser:
    parser = _ReplArgumentParser(prog="", add_help=False)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("state", add_help=False)

    p_people = sub.add_parser("people", add_help=False)
    p_people.add_argument("count", type=int)

    p_lookup = sub.add_parser("lookup", add_help=False)
    p_lookup.add_argument("code")

    p_add = sub.add_parser("add", add_help=False)
    p_add.add_argument("code")
    p_add.add_argument("count", nargs="?", type=int, default=1)
    p_add.add_argument("--mod-id", dest="mod_id", default="")
    p_add.add_argument("--mod-count", dest="mod_count", type=int, default=0)
    p_add.add_argument("--reorder", action="store_true")

    sub.add_parser("cart", add_help=False)
    sub.add_parser("cart-page", add_help=False)

    p_remove = sub.add_parser("remove", add_help=False)
    p_remove.add_argument("index", type=int)

    sub.add_parser("submit", add_help=False)
    sub.add_parser("account", add_help=False)
    sub.add_parser("receipt", add_help=False)

    p_call = sub.add_parser("call", add_help=False)
    p_call.add_argument("target", nargs="?", choices=("staff", "dessert"), default="staff")

    sub.add_parser("menu", add_help=False)
    sub.add_parser("history", add_help=False)

    p_reorder = sub.add_parser("reorder", add_help=False)
    p_reorder.add_argument("code")

    sub.add_parser("alcohol", add_help=False)

    p_check = sub.add_parser("check", add_help=False)
    p_check.add_argument("target", choices=("order", "last", "midnight"))

    sub.add_parser("help", add_help=False)
    sub.add_parser("exit", add_help=False)
    sub.add_parser("quit", add_help=False)

    return parser


_REPL_PARSER = _build_repl_parser()


def _run_command(client: SaizeriyaClient, args: list[str]) -> str:  # noqa: C901, PLR0912
    if not args:
        return "continue"

    try:
        ns = _REPL_PARSER.parse_args(args)
    except _ReplParseError as exc:
        raise ValueError(str(exc)) from exc

    command: str = ns.command

    if command == "help":
        print(USAGE)  # noqa: T201
        return "continue"
    if command in ("exit", "quit"):
        return "exit"
    if command == "state":
        _print_state(client.get_state())
    elif command == "people":
        _print_state(client.set_people_count(ns.count))
    elif command == "lookup":
        _print_lookup(client.lookup_item(ns.code))
    elif command == "add":
        _print_state(
            client.add_item(
                ns.code,
                count=ns.count,
                mod_id=ns.mod_id,
                mod_count=ns.mod_count,
                reorder=ns.reorder,
            ),
        )
    elif command == "cart":
        _print_cart(client.get_state())
    elif command == "cart-page":
        _print_state(client.go_to_cart())
    elif command == "remove":
        _print_state(client.remove_cart_item(ns.index - 1))
    elif command == "submit":
        _print_state(client.submit_order())
    elif command == "account":
        _, account = client.get_account()
        _print_account(account)
    elif command == "receipt":
        _, account, _ = client.get_receipt()
        _print_account(account)
    elif command == "call":
        result = client.call_dessert() if ns.target == "dessert" else client.call_staff()
        print(result)  # noqa: T201
    elif command == "menu":
        _print_state(client.go_to_menu())
    elif command == "history":
        _print_state(client.go_to_history())
    elif command == "reorder":
        _print_state(client.reorder(ns.code))
    elif command == "alcohol":
        print(client.confirm_alcohol())  # noqa: T201
    elif command == "check":
        if ns.target == "order":
            print(client.check_order_started())  # noqa: T201
        elif ns.target == "last":
            print(client.check_last_order())  # noqa: T201
        else:
            print(client.check_midnight())  # noqa: T201
    return "continue"


def _run_repl(name: str, client: SaizeriyaClient, http: httpx.Client, created_at: int) -> None:
    print(f'Session "{name}" is ready. Type help for commands.')  # noqa: T201
    prompt = f"saizeriya:{name}> "
    while True:
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()  # noqa: T201
            break
        try:
            args = shlex.split(line)
        except ValueError as exc:
            print(f"parse error: {exc}", file=sys.stderr)  # noqa: T201
            continue
        try:
            result = _run_command(client, args)
            _save_session(name, http, client, created_at)
            if result == "exit":
                break
        except Exception as exc:  # noqa: BLE001
            print(str(exc), file=sys.stderr)  # noqa: T201


def _cmd_start(ns: argparse.Namespace) -> None:
    http = _make_http()
    try:
        client = SaizeriyaClient(
            qr_url_source=ns.qrurl,
            people_count=ns.people_count,
            http=http,
        )
    except Exception:
        http.close()
        raise

    created_at = int(time.time() * 1000)
    try:
        _save_session(ns.name, http, client, created_at)
        _print_state(client.get_state())
        _run_repl(ns.name, client, http, created_at)
    finally:
        with contextlib.suppress(Exception):
            http.close()


def _cmd_use(ns: argparse.Namespace) -> None:
    sessions = _read_sessions()
    snapshot = sessions.get(ns.name)
    if not snapshot:
        msg = f"Session not found: {ns.name}"
        raise ValueError(msg)

    http = _make_http(snapshot.get("cookies", []))
    try:
        state = _state_from_dict(snapshot["state"])
        client = SaizeriyaClient(initial_state=state, http=http)
        _print_state(client.get_state())
        _run_repl(
            ns.name,
            client,
            http,
            int(snapshot.get("createdAt", time.time() * 1000)),
        )
    finally:
        with contextlib.suppress(Exception):
            http.close()


def _cmd_list() -> None:
    sessions = _read_sessions()
    for snapshot in sessions.values():
        updated = datetime.fromtimestamp(
            snapshot["updatedAt"] / 1000,
            tz=timezone.utc,
        ).isoformat()
        print(  # noqa: T201
            f"{snapshot['name']}\t{updated}\ttable={snapshot['state']['tableNo']}",
        )


def _cmd_rm(ns: argparse.Namespace) -> None:
    sessions = _read_sessions()
    sessions.pop(ns.name, None)
    _write_sessions(sessions)
    print(f"Removed {ns.name}")  # noqa: T201


def _cmd_fetch_menu(ns: argparse.Namespace) -> None:
    shops = ns.shops or list(fetch_menu.SHOPS)
    fetch_menu.crawl(
        shops=shops,
        out=ns.out,
        item_code_count=ns.max_code,
        table_no=ns.table_no,
        language=ns.lng,
        people_count=ns.people,
        shuffle=not ns.no_shuffle,
    )


def _build_top_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="saizeriya", description="Saizeriya order CLI.")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p_start = sub.add_parser("start", help="Start a new ordering session")
    p_start.add_argument("name")
    p_start.add_argument("qrurl")
    p_start.add_argument("--people", dest="people_count", type=int, default=None)

    p_use = sub.add_parser("use", help="Resume a saved session")
    p_use.add_argument("name")

    sub.add_parser("list", help="List saved sessions")

    p_rm = sub.add_parser("rm", help="Remove a saved session")
    p_rm.add_argument("name")

    p_fetch = sub.add_parser("fetch-menu", help="Crawl menu data for shops")
    p_fetch.add_argument("--out", type=Path, default=fetch_menu.DEFAULT_OUTPUT)
    p_fetch.add_argument("--shop", action="append", dest="shops", default=None)
    p_fetch.add_argument("--max-code", dest="max_code", type=int, default=fetch_menu.DEFAULT_ITEM_CODE_COUNT)
    p_fetch.add_argument("--table-no", dest="table_no", default=fetch_menu.DEFAULT_TABLE_NO)
    p_fetch.add_argument("--people", default=fetch_menu.DEFAULT_PEOPLE_COUNT)
    p_fetch.add_argument("--lng", default=fetch_menu.DEFAULT_LANGUAGE)
    p_fetch.add_argument("--no-shuffle", dest="no_shuffle", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] == "help":
        parser = _build_top_parser()
        parser.print_help()
        return

    parser = _build_top_parser()
    ns = parser.parse_args(argv)

    if ns.command is None:
        parser.print_help()
        return

    try:
        if ns.command == "start":
            _cmd_start(ns)
        elif ns.command == "use":
            _cmd_use(ns)
        elif ns.command == "list":
            _cmd_list()
        elif ns.command == "rm":
            _cmd_rm(ns)
        elif ns.command == "fetch-menu":
            _cmd_fetch_menu(ns)
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)  # noqa: T201
        sys.exit(1)


if __name__ == "__main__":
    main()
