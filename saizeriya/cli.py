"""Interactive CLI for `saizeriya`."""

from __future__ import annotations

import contextlib
import json
import os
import shlex
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from . import fetch_menu
from .client import SaizeriyaClient
from .types import AccountSummary, CartItem, ClientState

if TYPE_CHECKING:
    from collections.abc import Sequence

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


def _parse_int_option(args: Sequence[str], name: str) -> int | None:
    if name not in args:
        return None
    index = list(args).index(name)
    if index + 1 >= len(args):
        msg = f"{name} requires an integer value"
        raise ValueError(msg)
    try:
        return int(args[index + 1])
    except ValueError as exc:
        msg = f"{name} requires an integer value"
        raise ValueError(msg) from exc


def _require_arg(args: Sequence[str], index: int, name: str) -> str:
    if index >= len(args) or not args[index]:
        msg = f"{name} is required"
        raise ValueError(msg)
    return args[index]


def _run_command(client: SaizeriyaClient, args: list[str]) -> str:  # noqa: C901, PLR0911, PLR0912, PLR0915
    if not args:
        return "continue"
    command = args[0]

    if command == "help":
        print(USAGE)  # noqa: T201
        return "continue"
    if command in ("exit", "quit"):
        return "exit"
    if command == "state":
        _print_state(client.get_state())
        return "continue"
    if command == "people":
        count = int(_require_arg(args, 1, "count"))
        _print_state(client.set_people_count(count))
        return "continue"
    if command == "lookup":
        _print_lookup(client.lookup_item(_require_arg(args, 1, "code")))
        return "continue"
    if command == "add":
        code = _require_arg(args, 1, "code")
        count = 1
        if len(args) >= 3 and not args[2].startswith("--"):  # noqa: PLR2004
            count = int(args[2])
        mod_id = ""
        if "--mod-id" in args:
            mi = args.index("--mod-id")
            if mi + 1 < len(args):
                mod_id = args[mi + 1]
        mod_count = _parse_int_option(args, "--mod-count") or 0
        reorder = "--reorder" in args
        _print_state(
            client.add_item(
                code,
                count=count,
                mod_id=mod_id,
                mod_count=mod_count,
                reorder=reorder,
            ),
        )
        return "continue"
    if command == "cart":
        _print_cart(client.get_state())
        return "continue"
    if command == "cart-page":
        _print_state(client.go_to_cart())
        return "continue"
    if command == "remove":
        idx = int(_require_arg(args, 1, "index")) - 1
        _print_state(client.remove_cart_item(idx))
        return "continue"
    if command == "submit":
        _print_state(client.submit_order())
        return "continue"
    if command == "account":
        _, account = client.get_account()
        _print_account(account)
        return "continue"
    if command == "receipt":
        _, account, _ = client.get_receipt()
        _print_account(account)
        return "continue"
    if command == "call":
        target = args[1] if len(args) > 1 else "staff"
        result = client.call_dessert() if target == "dessert" else client.call_staff()
        print(result)  # noqa: T201
        return "continue"
    if command == "menu":
        _print_state(client.go_to_menu())
        return "continue"
    if command == "history":
        _print_state(client.go_to_history())
        return "continue"
    if command == "reorder":
        _print_state(client.reorder(_require_arg(args, 1, "code")))
        return "continue"
    if command == "alcohol":
        print(client.confirm_alcohol())  # noqa: T201
        return "continue"
    if command == "check":
        target = _require_arg(args, 1, "target")
        if target == "order":
            print(client.check_order_started())  # noqa: T201
        elif target == "last":
            print(client.check_last_order())  # noqa: T201
        elif target == "midnight":
            print(client.check_midnight())  # noqa: T201
        else:
            msg = "target must be order, last, or midnight"
            raise ValueError(msg)
        return "continue"

    msg = f"Unknown command: {command}"
    raise ValueError(msg)


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


def _cmd_start(args: list[str]) -> None:
    name = _require_arg(args, 0, "name")
    qr_url = _require_arg(args, 1, "qrurl")
    people_count = _parse_int_option(args, "--people")
    http = _make_http()
    try:
        client = SaizeriyaClient(
            qr_url_source=qr_url,
            people_count=people_count,
            http=http,
        )
    except Exception:
        http.close()
        raise

    created_at = int(time.time() * 1000)
    try:
        _save_session(name, http, client, created_at)
        _print_state(client.get_state())
        _run_repl(name, client, http, created_at)
    finally:
        with contextlib.suppress(Exception):
            http.close()


def _cmd_use(args: list[str]) -> None:
    name = _require_arg(args, 0, "name")
    sessions = _read_sessions()
    snapshot = sessions.get(name)
    if not snapshot:
        msg = f"Session not found: {name}"
        raise ValueError(msg)

    http = _make_http(snapshot.get("cookies", []))
    try:
        state = _state_from_dict(snapshot["state"])
        client = SaizeriyaClient(initial_state=state, http=http)
        _print_state(client.get_state())
        _run_repl(
            name,
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


def _cmd_rm(args: list[str]) -> None:
    name = _require_arg(args, 0, "name")
    sessions = _read_sessions()
    sessions.pop(name, None)
    _write_sessions(sessions)
    print(f"Removed {name}")  # noqa: T201


def _collect_repeat_option(args: list[str], name: str) -> list[str]:
    values: list[str] = []
    cursor = 0
    while cursor < len(args):
        if args[cursor] == name:
            if cursor + 1 >= len(args):
                msg = f"{name} requires a value"
                raise ValueError(msg)
            values.append(args[cursor + 1])
            cursor += 2
        else:
            cursor += 1
    return values


def _string_option(args: list[str], name: str) -> str | None:
    if name not in args:
        return None
    index = args.index(name)
    if index + 1 >= len(args):
        msg = f"{name} requires a value"
        raise ValueError(msg)
    return args[index + 1]


def _cmd_fetch_menu(args: list[str]) -> None:
    out_raw = _string_option(args, "--out")
    out = Path(out_raw) if out_raw is not None else fetch_menu.DEFAULT_OUTPUT
    max_code = _parse_int_option(args, "--max-code")
    if max_code is None:
        max_code = fetch_menu.DEFAULT_ITEM_CODE_COUNT
    table_no = _string_option(args, "--table-no") or fetch_menu.DEFAULT_TABLE_NO
    language = _string_option(args, "--lng") or fetch_menu.DEFAULT_LANGUAGE
    people = _string_option(args, "--people") or fetch_menu.DEFAULT_PEOPLE_COUNT
    shops = _collect_repeat_option(args, "--shop") or list(fetch_menu.SHOPS)
    shuffle = "--no-shuffle" not in args

    fetch_menu.crawl(
        shops=shops,
        out=out,
        item_code_count=max_code,
        table_no=table_no,
        language=language,
        people_count=people,
        shuffle=shuffle,
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] in ("help", "--help", "-h"):
        print(USAGE)  # noqa: T201
        return

    command, *rest = argv
    try:
        if command == "start":
            _cmd_start(rest)
        elif command == "use":
            _cmd_use(rest)
        elif command == "list":
            _cmd_list()
        elif command == "rm":
            _cmd_rm(rest)
        elif command == "fetch-menu":
            _cmd_fetch_menu(rest)
        else:
            msg = f"Unknown command: {command}"
            raise ValueError(msg)  # noqa: TRY301
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)  # noqa: T201
        sys.exit(1)


if __name__ == "__main__":
    main()
