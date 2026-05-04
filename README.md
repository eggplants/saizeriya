# saizeriya

[![PyPI](
  <https://img.shields.io/pypi/v/saizeriya?color=blue>
  )](
  <https://pypi.org/project/saizeriya/>
) [![Release Package](
  <https://github.com/eggplants/saizeriya/actions/workflows/release.yml/badge.svg>
  )](
  <https://github.com/eggplants/saizeriya/actions/workflows/release.yml>
) [![CI](
  <https://github.com/eggplants/saizeriya/actions/workflows/ci.yml/badge.svg>
  )](
  <https://github.com/eggplants/saizeriya/actions/workflows/ci.yml>
)

[![ghcr latest](
  <https://ghcr-badge.egpl.dev/eggplants/saizeriya/latest_tag?trim=major&label=latest>
 ) ![ghcr size](
  <https://ghcr-badge.egpl.dev/eggplants/saizeriya/size>
)](
  <https://github.com/eggplants/saizeriya/pkgs/container/saizeriya>
)

Unofficial [Saizeriya](https://www.saizeriya.co.jp/) Client, inspired by [saizeriya.js](https://www.npmjs.com/package/saizeriya.js)

## Installation

```sh
pip install saizeriya
# or, (CLI only)
pipx install saizeriya
```

## Usage

### CLI

```shellsession
$ saizeriya
usage: saizeriya [-h] <command> ...

Saizeriya order CLI.

positional arguments:
  <command>
    start       Start a new ordering session
    use         Resume a saved session
    list        List saved sessions
    rm          Remove a saved session
    fetch-menu  Crawl menu data for shops

options:
  -h, --help    show this help message and exit
```
To start session named `lunch` and ener REPL:

```bash
saizeriya start lunch "https://ioes03.saizeriya.co.jp/saizeriya3/?..."
```

After start/use, available commands in REPL:

```text
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
exit
```

### Library

```python
import saizeriya

# check version
print(saizeriya.__version__)

# create client instance
client = new SaizeriyaClient(
  qr_url_source="https://example.com/saizeriya3/qr",
  people_count=2,
)

# add new item to cart
in_cart_items = client.add_item('1202').cart

# check in-cart items
print(in_cart_items)
```

### Docker

```shellsession
docker run --rm -it ghcr.io/eggplants/saizeriya
```

## License

[MIT License](https://github.com/eggplants/saizeriya/blob/master/LICENSE)
