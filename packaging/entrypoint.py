"""Entry point frozen into the standalone binary by `packaging/saizeriya.spec`.

The console script declared in `pyproject.toml` is not usable here: PyInstaller
analyses a source file, not an installed entry point, and the project itself is
imported from the repo tree rather than pip-installed during the build.
"""

from __future__ import annotations

from saizeriya.cli import main

if __name__ == "__main__":
    main()
