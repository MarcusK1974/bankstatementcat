from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List


@dataclass
class S3SyncConfig:
    profile: str
    bucket: str
    prefix: str
    dest: Path
    include_globs: List[str]


def _run(cmd: List[str]) -> None:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n\n{proc.stdout}"
        )
    print(proc.stdout)


def _matches_include(rel_path: str, include_globs: List[str]) -> bool:
    for pattern in include_globs:
        if "/" in pattern:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
        else:
            if fnmatch.fnmatch(Path(rel_path).name, pattern):
                return True
    return False


def _build_inventory(cfg: S3SyncConfig) -> List[dict]:
    items: List[dict] = []
    prefix = cfg.prefix
    if prefix and not prefix.endswith("/"):
        prefix = f"{prefix}/"
    for path in sorted(cfg.dest.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(cfg.dest).as_posix()
        if not _matches_include(rel_path, cfg.include_globs):
            continue
        stat = path.stat()
        items.append(
            {
                "s3_key": f"{prefix}{rel_path}",
                "local_path": rel_path,
                "size_bytes": stat.st_size,
                "last_modified_utc": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            }
        )
    return items


def aws_s3_sync(cfg: S3SyncConfig) -> dict:
    cfg.dest.mkdir(parents=True, exist_ok=True)

    # Build include/exclude args: exclude everything then include requested globs.
    args: List[str] = [
        "aws",
        "s3",
        "sync",
        f"s3://{cfg.bucket}/{cfg.prefix}",
        str(cfg.dest),
        "--profile",
        cfg.profile,
    ]
    args += ["--exclude", "*"]
    for g in cfg.include_globs:
        args += ["--include", g]

    started = datetime.now(timezone.utc).isoformat()
    _run(args)
    finished = datetime.now(timezone.utc).isoformat()

    inventory = _build_inventory(cfg)
    total_bytes = sum(item["size_bytes"] for item in inventory)
    manifest = {
        "started_utc": started,
        "finished_utc": finished,
        "bucket": cfg.bucket,
        "prefix": cfg.prefix,
        "dest": str(cfg.dest),
        "profile": cfg.profile,
        "include_globs": cfg.include_globs,
        "file_count": len(inventory),
        "total_bytes": total_bytes,
        "files": inventory,
        "notes": "aws s3 sync is incremental; re-running downloads new/changed objects.",
    }
    return manifest


def main() -> None:
    p = argparse.ArgumentParser(description="Incremental S3 sync for BASIQ artifacts.")
    p.add_argument("--profile", required=True, help="AWS CLI profile name (SSO ok), e.g. billie")
    p.add_argument("--bucket", required=True, help="S3 bucket name, e.g. billie-applications-nonprod")
    p.add_argument("--prefix", required=True, help="Prefix under bucket, e.g. demo/")
    p.add_argument("--dest", default="data/raw_s3", help="Local destination folder")
    p.add_argument(
        "--include",
        action="append",
        default=["*.json", "*.html"],
        help="Glob to include (repeatable)",
    )
    p.add_argument(
        "--write-manifest",
        default="data/raw_s3/_sync_manifest.json",
        help="Where to write sync manifest JSON",
    )
    args = p.parse_args()

    cfg = S3SyncConfig(
        profile=args.profile,
        bucket=args.bucket,
        prefix=args.prefix,
        dest=Path(args.dest),
        include_globs=args.include,
    )

    manifest = aws_s3_sync(cfg)
    Path(args.write_manifest).parent.mkdir(parents=True, exist_ok=True)
    with open(args.write_manifest, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Wrote manifest: {args.write_manifest}")


if __name__ == "__main__":
    main()
