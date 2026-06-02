from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def split_file(input_path: Path, output_root: Path, chunk_mb: int) -> dict[str, object]:
    output_root.mkdir(parents=True, exist_ok=True)
    chunk_size = max(1, int(chunk_mb)) * 1024 * 1024
    chunks: list[dict[str, object]] = []
    with input_path.open("rb") as source:
        index = 0
        while True:
            data = source.read(chunk_size)
            if not data:
                break
            chunk_name = f"{input_path.name}.part{index:04d}"
            chunk_path = output_root / chunk_name
            chunk_path.write_bytes(data)
            chunks.append(
                {
                    "index": index,
                    "name": chunk_name,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
            index += 1
    manifest = {
        "input_path": str(input_path),
        "input_name": input_path.name,
        "input_bytes": input_path.stat().st_size,
        "input_sha256": sha256_file(input_path),
        "chunk_mb": chunk_mb,
        "chunk_count": len(chunks),
        "chunks": chunks,
    }
    (output_root / f"{input_path.name}.chunks.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Split a file into deterministic chunks with SHA256 manifest.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--chunk-mb", type=int, default=50)
    args = parser.parse_args()
    manifest = split_file(args.input, args.output_root, args.chunk_mb)
    print(json.dumps({"chunk_count": manifest["chunk_count"], "input_sha256": manifest["input_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
