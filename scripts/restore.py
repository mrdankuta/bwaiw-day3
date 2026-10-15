"""Restore the SQLite file from a backup (ticket: privacy and hardening).

Usage: .venv/bin/python scripts/restore.py BACKUP [--db PATH] [--force]
Refuses to overwrite an existing database unless --force is given.
After restore, the app's boot migration brings old schemas forward.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.store import default_path  # noqa: E402


def restore(backup_path: str, db_path: str, *, force: bool = False) -> str:
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"no backup at {backup_path}")
    if os.path.exists(db_path) and not force:
        raise FileExistsError(
            f"database exists at {db_path}; pass --force to overwrite"
        )
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    shutil.copyfile(backup_path, db_path)
    return db_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup")
    parser.add_argument("--db", default=default_path())
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    print(restore(args.backup, args.db, force=args.force))


if __name__ == "__main__":
    main()
