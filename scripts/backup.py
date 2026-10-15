"""Backup the SQLite file (ticket: privacy and hardening).

Usage: .venv/bin/python scripts/backup.py [--db PATH] [--dir DIR]
Refuses nothing; always writes a new timestamped copy via the SQLite
backup API so a live writer cannot corrupt it.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.store import default_path  # noqa: E402


def backup(db_path: str, backup_dir: str) -> str:
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"no database at {db_path}")
    os.makedirs(backup_dir, exist_ok=True)
    dest = os.path.join(
        backup_dir, f"app-{time.strftime('%Y%m%d-%H%M%S')}.db"
    )
    src = sqlite3.connect(db_path)
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return dest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=default_path())
    parser.add_argument("--dir", default="backups")
    args = parser.parse_args()
    print(backup(args.db, args.dir))


if __name__ == "__main__":
    main()
