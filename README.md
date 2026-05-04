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
