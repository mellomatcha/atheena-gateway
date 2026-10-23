#!/usr/bin/env python3
"""Create a private PostgreSQL backup; run as the deploy user on CT301."""

import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    backups = root / "backups"
    backups.mkdir(mode=0o700, exist_ok=True)
    os.chmod(backups, 0o700)
    now = datetime.now(timezone.utc)
    target = backups / ("atheena-" + now.strftime("%Y%m%dT%H%M%SZ") + ".dump")
    temporary = target.with_suffix(".partial")
    command = [
        "docker",
        "compose",
        "--env-file",
        str(root / ".env.production"),
        "-f",
        str(root / "deploy/docker-compose.yml"),
        "exec",
        "-T",
        "postgres",
        "pg_dump",
        "-U",
        "atheena",
        "-d",
        "atheena",
        "-Fc",
    ]
    try:
        with os.fdopen(
            os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
        ) as stream:
            subprocess.run(command, stdout=stream, check=True, timeout=300)
            stream.flush()
            os.fsync(stream.fileno())
        if temporary.stat().st_size < 1024:
            raise RuntimeError("Backup unexpectedly small")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    # Only expire files created by this script, after a successful replacement exists.
    cutoff = (now - timedelta(days=30)).timestamp()
    for previous in backups.glob("atheena-*.dump"):
        if (
            previous.is_file()
            and not previous.is_symlink()
            and previous.stat().st_mtime < cutoff
        ):
            previous.unlink()
    print("Database backup complete: " + target.name)


if __name__ == "__main__":
    main()
