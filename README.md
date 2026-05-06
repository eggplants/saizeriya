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

### Docker

```shellsession
docker run --rm -it ghcr.io/eggplants/saizeriya
```

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

available commands in start/use REPL:
   state
    Show current session state
   people <count>
    Set number of people at the table
   lookup <code>
    Look up an item by code
   add [--mod-id MOD_ID] [--mod-count MOD_COUNT] [--reorder] <code> [<count>]
    Add an item to the cart
   cart
    Show cart contents
   cart-page
    Navigate to the cart page
   remove <index>
    Remove an item from the cart by index
   submit
    Submit the current order
   account
    Show account summary
   receipt
    Show receipt
   call [{staff,dessert}]
    Call staff or dessert service
   menu
    Navigate to the menu page
   history
    Navigate to order history
   reorder <code>
    Reorder a previously ordered item
   alcohol
    Confirm alcohol order
   check {order,last,midnight}
    Check order/last-order/midnight status
   help
    Show this help message
   exit
    Exit the REPL
   quit
    Exit the REPL
```

To start session named `lunch` and ener REPL:

```bash
saizeriya start lunch "https://ioes03.saizeriya.co.jp/saizeriya3/?..."
```

### Library

```python
import saizeriya

# check version
print(saizeriya.__version__)

# create client instance
client = saizeriya.SaizeriyaClient(
  qr_url_source="https://ioes03.saizeriya.co.jp/saizeriya3/?...",
  people_count=2,
)

# add new item to cart
in_cart_items = client.add_item('1202').cart

# check in-cart items
print(in_cart_items)
```

### Mock server (`saizeriya._mock`)

```bash
pip install saizeriya[mock]
saizeriya-mock-server
```

Then, visit <http://localhost:8080/>.

## License

[MIT License](https://github.com/eggplants/saizeriya/blob/master/LICENSE)
