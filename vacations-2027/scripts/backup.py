"""Consistent backup of a live SQLite database. Does not overwrite existing files."""
import os
import sqlite3
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Использование: python scripts/backup.py ПУТЬ_КОПИИ.sqlite3")
    source = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[1] / "instance")) / "vacations.sqlite3"
    destination = Path(sys.argv[1]).resolve()
    if not source.is_file():
        raise SystemExit("База не найдена. Проверьте DATA_DIR.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    try:
        with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as src, sqlite3.connect(destination) as dst:
            src.backup(dst)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    print("Резервная копия создана.")


if __name__ == "__main__":
    main()
