#!/usr/bin/env python3
"""Optional structural checks for a LeRobot-v3-style dataset.

This tool does NOT enforce a particular schema, feature set, dimensionality,
or fps — those are your design decisions. It only checks that the dataset is
structurally sound and reports its shape so you can sanity-check your output.

Hard failures (things that would break any training loader):
  - meta/info.json missing or unparseable
  - no data parquet files
  - observation/action columns absent
  - NaN / Inf values in state or action
  - frame_index not monotonic within an episode
  - zero episodes

Everything else is reported as INFO or WARN.

Usage:
    python validate_submission.py path/to/dataset
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

MIN_EPISODE_FRAMES = 5


class CheckResult:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def note(self, msg: str) -> None:
        self.info.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errors


def _load_info(root: Path, result: CheckResult) -> dict | None:
    info_path = root / "meta" / "info.json"
    if not info_path.is_file():
        result.error(f"Missing {info_path.relative_to(root)}")
        return None
    try:
        return json.loads(info_path.read_text())
    except json.JSONDecodeError as e:
        result.error(f"Invalid meta/info.json: {e}")
        return None


def _find_parquet(root: Path) -> list[Path]:
    data_dir = root / "data"
    if not data_dir.is_dir():
        return []
    return sorted(data_dir.rglob("*.parquet"))


def _list_to_array(values, width_hint: int) -> np.ndarray:
    rows = []
    for v in values:
        if hasattr(v, "as_py"):
            v = v.as_py()
        if v is None:
            rows.append([np.nan] * width_hint)
        else:
            rows.append(list(v) if hasattr(v, "__len__") else [v])
    return np.asarray(rows, dtype=np.float64)


def validate(root: Path) -> CheckResult:
    result = CheckResult()
    root = root.resolve()
    if not root.is_dir():
        result.error(f"Not a directory: {root}")
        return result

    info = _load_info(root, result)
    if info is None:
        return result

    fps = info.get("fps")
    result.note(
        f"fps={fps}, total_episodes={info.get('total_episodes')}, "
        f"total_frames={info.get('total_frames')}"
    )
    if fps is None:
        result.warn("meta/info.json has no 'fps' — most training loaders need one")

    features = info.get("features") or {}
    state_keys = [k for k in features if "state" in k and k.startswith("observation")]
    action_keys = [k for k in features if k == "action" or k.startswith("action")]
    video_keys = [
        k for k, v in features.items()
        if (isinstance(v, dict) and v.get("dtype") == "video") or k.startswith("observation.images")
    ]
    for label, keys in (("state", state_keys), ("action", action_keys)):
        if keys:
            shapes = {k: (features[k].get("shape") if isinstance(features[k], dict) else None) for k in keys}
            result.note(f"{label} features: {shapes}")
        else:
            result.warn(f"No {label} feature declared in meta/info.json features")
    if video_keys:
        result.note(f"video features: {video_keys}")
        video_root = root / "videos"
        if video_root.is_dir():
            mp4s = list(video_root.rglob("*.mp4"))
            result.note(f"found {len(mp4s)} mp4 file(s)")
            if not mp4s:
                result.warn("videos/ exists but contains no .mp4 files")
        else:
            result.warn("video feature declared but no videos/ directory")
    else:
        result.warn("No video/image feature declared — most VLA/BC recipes want pixels")

    parquet_files = _find_parquet(root)
    if not parquet_files:
        result.error("No data/**/*.parquet files found")
        return result

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        table = pa.concat_tables([pq.read_table(p) for p in parquet_files])
    except Exception as e:
        result.error(f"Failed to read parquet: {e}")
        return result

    colnames = set(table.column_names)
    state_col = next((c for c in ("observation.state", *sorted(colnames)) if c in colnames and "state" in c and c.startswith("observation")), None)
    action_col = next((c for c in ("action", *sorted(colnames)) if c in colnames and c.startswith("action")), None)

    if state_col is None:
        result.error("parquet has no observation state column (e.g. 'observation.state')")
    if action_col is None:
        result.error("parquet has no action column (e.g. 'action')")
    if "episode_index" not in colnames:
        result.error("parquet missing 'episode_index'")
    if "frame_index" not in colnames:
        result.error("parquet missing 'frame_index'")
    if result.errors:
        return result

    states = _list_to_array(table.column(state_col), 1)
    actions = _list_to_array(table.column(action_col), 1)
    ep_idx = np.asarray(table.column("episode_index").to_pylist(), dtype=np.int64)
    frame_idx = np.asarray(table.column("frame_index").to_pylist(), dtype=np.int64)

    result.note(f"{state_col} width: {states.shape[1]}; {action_col} width: {actions.shape[1]}; rows: {len(ep_idx)}")

    if not np.isfinite(states).all():
        result.error(f"{state_col} contains NaN/Inf")
    if not np.isfinite(actions).all():
        result.error(f"{action_col} contains NaN/Inf")

    n_episodes = int(ep_idx.max()) + 1 if len(ep_idx) else 0
    if n_episodes < 1:
        result.error("No episodes found (empty episode_index)")
        return result

    lengths = [int((ep_idx == e).sum()) for e in range(n_episodes)]
    result.note(
        f"episodes: {n_episodes}  frames/episode min={min(lengths)} "
        f"median={int(np.median(lengths))} max={max(lengths)}"
    )
    short = sum(1 for n in lengths if n < MIN_EPISODE_FRAMES)
    if short:
        result.warn(f"{short}/{n_episodes} episodes shorter than {MIN_EPISODE_FRAMES} frames")

    for e in range(n_episodes):
        frames = frame_idx[ep_idx == e]
        if len(frames) and not np.all(np.diff(frames) >= 0):
            result.error(f"episode {e}: frame_index not monotonic")
            break

    if "timestamp" in colnames:
        ts_all = np.asarray(table.column("timestamp").to_pylist(), dtype=np.float64)
        for e in range(n_episodes):
            ts = ts_all[ep_idx == e]
            if len(ts) >= 2 and not np.all(np.diff(ts) >= -1e-6):
                result.warn(f"episode {e}: timestamp not monotonic")
                break

    # Informational: does any state channel look like a gripper (binary-ish)?
    variances = states.var(axis=0)
    flat = [i for i, v in enumerate(variances) if v < 1e-12]
    if flat:
        result.warn(f"state channels with zero variance: {flat} (intentional?)")

    declared = info.get("total_episodes")
    if declared is not None and int(declared) != n_episodes:
        result.warn(f"info.total_episodes={declared} but parquet has {n_episodes}")

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="Path to dataset root")
    args = parser.parse_args(argv)

    result = validate(args.dataset)
    print("=" * 60)
    print(f"Dataset: {args.dataset}")
    for msg in result.info:
        print(f"  INFO {msg}")
    for msg in result.warnings:
        print(f"  WARN {msg}")
    for msg in result.errors:
        print(f"  FAIL {msg}")
    print("=" * 60)
    if result.ok:
        print("RESULT: STRUCTURALLY SOUND")
        return 0
    print("RESULT: STRUCTURAL PROBLEMS FOUND")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
