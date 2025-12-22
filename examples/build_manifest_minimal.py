from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict, List


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(root: Path, include_hash: bool) -> Dict[str, object]:
    files: List[Dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(root).as_posix()
        entry = {
            "path": rel_path,
            "size_bytes": path.stat().st_size,
        }
        if include_hash:
            entry["sha256"] = _sha256(path)
        files.append(entry)

    manifest = {
        "root": str(root),
        "file_count": len(files),
        "files": files,
    }
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a deterministic manifest for a folder."
    )
    parser.add_argument("root", help="Root folder to scan")
    parser.add_argument("--out", default="manifest.json", help="Output manifest path")
    parser.add_argument("--hash", action="store_true", help="Include sha256 per file")
    args = parser.parse_args()

    root = Path(args.root)
    manifest = build_manifest(root, args.hash)
    Path(args.out).write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
