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
  exit
```

### Library

```python
import saizeriya

print(saizeriya.__version__)
```

### Docker

```shellsession
docker run --rm -it ghcr.io/eggplants/saizeriya
```

## License

[MIT License](https://github.com/eggplants/saizeriya/blob/master/LICENSE)
