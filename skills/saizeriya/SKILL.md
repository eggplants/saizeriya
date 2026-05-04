---
name: saizeriya
description: Use this skill when the user wants to place a Saizeriya order, browse a Saizeriya in-store menu via QR code, manage saved ordering sessions, or crawl Saizeriya per-shop menu data. Triggers include "サイゼリヤで注文", "Saizeriya order", "QRコードから注文", "メニューを取得", and references to the `saizeriya` CLI installed from this project.
---

# Saizeriya CLI

The `saizeriya` CLI (entry point: `saizeriya.cli:main`) is an unofficial client for Saizeriya's in-store QR ordering system. It pairs with a table's QR URL to drive the whole order flow — lookup, cart, submit, account, receipt — from the terminal, and can also crawl per-shop menus.

## When to use this skill

- The user wants to start, resume, list, or remove a Saizeriya ordering session.
- The user asks how to add items to the cart, submit an order, or look up an item code at a Saizeriya table.
- The user wants to crawl menu data via `fetch-menu`.
- The user mentions the `saizeriya` command, `SaizeriyaClient`, or QR-based ordering at Saizeriya.

Do **not** use this skill for general Python questions, logging refactors, or unrelated CLI work in this repo — only for the Saizeriya ordering workflow itself.

## Top-level commands

```
saizeriya start <name> <qr_url> [--people <count>]
saizeriya use <name>
saizeriya list
saizeriya rm <name>
saizeriya fetch-menu [--out <path>] [--shop <id>]... [--max-code <n>]
                     [--table-no <n>] [--people <n>] [--lng <n>]
                     [--no-shuffle]
```

- `start` — open a new ordering session under a friendly `<name>`, pointed at the table's QR URL. Drops into the REPL.
- `use` — resume a previously-saved session by name (cookies + state are persisted).
- `list` — print saved sessions (name, last-updated time, table number).
- `rm` — delete a saved session.
- `fetch-menu` — crawl per-shop item codes and append findings to a JSON file. Resumable; safe to interrupt.

Sessions are stored under `$SAIZERIYA_CLI_HOME` (default `~/.saizeriya-cli/sessions.json`).

## REPL commands (after `start` / `use`)

```
state                                       # current shop/table/page summary
people <count>                              # change people count
lookup <code>                               # query item by 4-digit code
add <code> [count] [--mod-id <id>]
                  [--mod-count <count>]
                  [--reorder]               # add to cart
cart                                        # show current cart
cart-page                                   # navigate to cart page
remove <index>                              # remove cart line by 1-based index
submit                                      # send the order
account                                     # current bill
receipt                                     # printable receipt
call [staff|dessert]                        # call staff (default staff)
menu                                        # navigate to menu page
history                                     # navigate to history page
reorder <code>                              # reorder a previously ordered item
alcohol                                     # confirm alcohol policy
check <order|last|midnight>                 # status checks
help                                        # show in-REPL usage
exit / quit                                 # leave REPL (state is auto-saved)
```

The REPL auto-saves the session after every successful command, so quitting (or `Ctrl-D`) will not lose progress.

## Typical flow

1. Scan the table's QR code, copy the URL (looks like `https://ioes.saizeriya.co.jp/saizeriya2/?...`).
2. `saizeriya start dinner "<qr_url>" --people 2`
3. In the REPL: `lookup 1402` to inspect an item, `add 1402 2` to put two in the cart, `cart` to review, `submit` to send.
4. Later: `saizeriya use dinner` to come back, or `account` to see the running tab, `receipt` when you're done.

## fetch-menu notes

`fetch-menu` POSTs to `ioes.saizeriya.co.jp/saizeriya2/src/cmd/get_item.php` for every (shop, item_code) pair and appends results to `data/menu-by-shop.json` by default. It:

- Reads the existing output file and skips item ids already discovered (resumable).
- Shuffles shop order by default; pass `--no-shuffle` for deterministic runs.
- Defaults `--max-code` to 10000 — narrow it (e.g. `--max-code 2000`) for quick smoke runs.
- Restrict to specific shops by repeating `--shop <code>` (4-digit shop codes are listed in `saizeriya/shops.py`).

Logging from the crawl goes through Python's `logging` module at `INFO` level; no `--verbose` flag is needed.

## Things to remind the user about

- The QR URL contains a **session token** — treat it like a credential. Do not paste it into shared chats or commit it.
- One QR URL is bound to one table. If the staff resets the table, you'll need a fresh URL via `start`.
- `submit` is **irreversible** — it actually sends the order to the kitchen. Confirm the cart with `cart` first.
- This is an **unofficial** client. Saizeriya may change the endpoint at any time; if requests start failing with HTML/redirects, the protocol probably changed.

## Source

- Entry point: `saizeriya/cli.py` (`main`)
- HTTP client: `saizeriya/client.py` (`SaizeriyaClient`)
- Crawler: `saizeriya/fetch_menu.py` (`crawl`, `fetch_item`)
- Shop directory: `saizeriya/shops.py`
