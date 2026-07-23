#!/usr/bin/env python3
"""Download challenge MCAP clips from a TorqueAGI-style URL manifest.

The challenge data package contains *links only* (presigned R2 URLs), not the
recordings themselves. URLs typically expire after 7 days — ask for a refresh
if downloads fail with 403.

Usage:
    python download_data.py data/manifest.json
    python download_data.py data/manifest.json --out ./recordings
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_manifest(path: Path) -> list[dict]:
    raw = json.loads(path.read_text())
    if isinstance(raw, dict) and "clips" in raw:
        return list(raw["clips"])
    if isinstance(raw, list):
        return list(raw)
    raise ValueError("Manifest must be a list of clips or {clips: [...]}")


def download(manifest_path: Path, out_dir: Path, overwrite: bool) -> int:
    try:
        import requests
    except ImportError:
        print("Install deps first:  uv sync", file=sys.stderr)
        return 1

    clips = _load_manifest(manifest_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    ua = {"User-Agent": "AvatarRobotics-MLChallenge/1.0"}

    ok = 0
    for clip in clips:
        name = clip.get("filename") or clip.get("id") or clip.get("key")
        url = clip.get("url") or clip.get("presigned_url")
        if not name or not url:
            print(f"Skipping malformed clip entry: {clip!r}", file=sys.stderr)
            continue
        dest = out_dir / Path(name).name
        if dest.exists() and not overwrite:
            print(f"[skip] {dest.name} (exists)")
            ok += 1
            continue
        print(f"[get ] {dest.name} ...")
        resp = requests.get(url, headers=ua, stream=True, timeout=120)
        if resp.status_code != 200:
            print(
                f"  FAILED HTTP {resp.status_code} — URL may have expired. "
                "Ask for a refreshed manifest.",
                file=sys.stderr,
            )
            continue
        tmp = dest.with_suffix(dest.suffix + ".partial")
        with tmp.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                if chunk:
                    fh.write(chunk)
        tmp.replace(dest)
        print(f"  -> {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
        ok += 1

    print(f"Done: {ok}/{len(clips)} clips in {out_dir}")
    return 0 if ok == len(clips) else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Path to manifest.json")
    parser.add_argument("--out", type=Path, default=Path("recordings"), help="Output directory")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    return download(args.manifest, args.out, args.overwrite)


if __name__ == "__main__":
    raise SystemExit(main())
