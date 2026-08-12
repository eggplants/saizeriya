"""Allow `python -m saizeriya.tui`, which is what `textual-serve` spawns."""

from __future__ import annotations

from . import main

if __name__ == "__main__":
    main()
