"""Enable ``python -m wheeldb`` to run the CLI."""

from wheeldb.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
