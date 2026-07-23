#!/usr/bin/env python3
"""URDF forward-kinematics ghost replay for a LeRobot challenge dataset.

Loads observation.state for an episode, runs FK with the shipped Agibot G1 URDF,
and shows a 3D stick-figure skeleton next to the head-camera video. Graders use
this as the visual "does it look right?" check (the shapes-challenge equivalent).

Optional: pass --predictions path.npy (T, 8) to overlay a ghost trajectory from
a trained policy (bonus tier).

Usage:
    python replay_dataset.py path/to/dataset --episode 0
    python replay_dataset.py path/to/dataset --episode 0 --arm left --save replay.mp4
    python replay_dataset.py path/to/dataset --episode 0 --predictions preds.npy
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from fk import KinematicModel, state_to_joint_dict


def _repo_urdf() -> Path:
    return Path(__file__).resolve().parent / "urdf" / "agibot_g1.urdf"


def _load_parquet_episode(root: Path, episode: int):
    import pyarrow.parquet as pq
    import pyarrow as pa

    files = sorted((root / "data").rglob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet under {root / 'data'}")
    table = pa.concat_tables([pq.read_table(p) for p in files])
    ep = np.asarray(table.column("episode_index").to_pylist(), dtype=np.int64)
    mask = ep == episode
    if not mask.any():
        raise ValueError(f"Episode {episode} not found (max={ep.max() if len(ep) else 'n/a'})")

    def col_list(name: str):
        return [v for v, m in zip(table.column(name).to_pylist(), mask, strict=True) if m]

    states = np.asarray(col_list("observation.state"), dtype=np.float64)
    actions = np.asarray(col_list("action"), dtype=np.float64)
    return states, actions


def _find_episode_video(root: Path, episode: int, cam_key: str | None) -> Path | None:
    info_path = root / "meta" / "info.json"
    features = {}
    if info_path.is_file():
        features = json.loads(info_path.read_text()).get("features") or {}

    if cam_key is None:
        for key in (
            "observation.images.camera",
            "observation.images.head",
            "observation.images.ego_view",
        ):
            if key in features:
                cam_key = key
                break
        if cam_key is None:
            for key, meta in features.items():
                if key.startswith("observation.images.") and meta.get("dtype") == "video":
                    cam_key = key
                    break
    if cam_key is None:
        # Fall back to first videos/* dir
        videos = root / "videos"
        if videos.is_dir():
            sub = sorted([p for p in videos.iterdir() if p.is_dir()])
            if sub:
                cam_key = sub[0].name
    if cam_key is None:
        return None

    # Prefer episode parquet meta if present
    ep_parquet = root / "meta" / "episodes" / "chunk-000" / "file-000.parquet"
    if ep_parquet.is_file():
        try:
            import pyarrow.parquet as pq

            ep_table = pq.read_table(ep_parquet)
            names = ep_table.column_names
            ci_col = f"videos/{cam_key}/chunk_index"
            fi_col = f"videos/{cam_key}/file_index"
            if ci_col in names and fi_col in names:
                # Find row for episode
                ep_col = ep_table.column("episode_index").to_pylist()
                for i, e in enumerate(ep_col):
                    if int(e) == episode:
                        ci = int(ep_table.column(ci_col)[i].as_py())
                        fi = int(ep_table.column(fi_col)[i].as_py())
                        path = (
                            root
                            / "videos"
                            / cam_key
                            / f"chunk-{ci:03d}"
                            / f"file-{fi:03d}.mp4"
                        )
                        if path.is_file():
                            return path
        except Exception:
            pass

    # Fallback: nth mp4 under the camera folder
    cam_dir = root / "videos" / cam_key
    if cam_dir.is_dir():
        mp4s = sorted(cam_dir.rglob("*.mp4"))
        if 0 <= episode < len(mp4s):
            return mp4s[episode]
    return None


def _read_video_frames(path: Path, max_frames: int | None = None) -> list[np.ndarray]:
    try:
        import av
    except ImportError as e:
        raise SystemExit("PyAV (av) required for video replay — uv sync") from e

    frames: list[np.ndarray] = []
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        for i, frame in enumerate(container.decode(stream)):
            frames.append(frame.to_ndarray(format="rgb24"))
            if max_frames is not None and i + 1 >= max_frames:
                break
    return frames


def replay(
    dataset: Path,
    episode: int,
    arm: str,
    urdf: Path,
    predictions: Path | None,
    save: Path | None,
    stride: int,
    max_frames: int | None,
) -> int:
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    if not urdf.is_file():
        print(f"URDF not found: {urdf}", file=sys.stderr)
        return 1

    model = KinematicModel.from_urdf(urdf)
    states, actions = _load_parquet_episode(dataset, episode)
    n = len(states)
    print(f"Episode {episode}: {n} frames, arm={arm}")

    preds = None
    if predictions is not None:
        preds = np.load(predictions)
        if preds.ndim != 2 or preds.shape[1] < 7:
            print(f"predictions must be (T, >=7), got {preds.shape}", file=sys.stderr)
            return 1
        print(f"Loaded predictions {preds.shape}")

    video_path = _find_episode_video(dataset, episode, None)
    frames: list[np.ndarray] = []
    if video_path and video_path.is_file():
        print(f"Video: {video_path}")
        frames = _read_video_frames(video_path, max_frames=max_frames)
    else:
        print("No episode video found — skeleton-only replay")

    if max_frames is not None:
        n = min(n, max_frames)
        states = states[:n]
        if preds is not None:
            preds = preds[:n]

    indices = list(range(0, n, max(1, stride)))

    fig = plt.figure(figsize=(12, 5))
    ax3d = fig.add_subplot(1, 2, 1, projection="3d")
    aximg = fig.add_subplot(1, 2, 2)
    aximg.axis("off")
    aximg.set_title("head camera")

    def draw(i: int):
        ax3d.cla()
        ax3d.set_title(f"FK skeleton  frame={i}/{n - 1}")
        ax3d.set_xlabel("x")
        ax3d.set_ylabel("y")
        ax3d.set_zlabel("z")
        ax3d.set_xlim(-0.8, 0.8)
        ax3d.set_ylim(-0.8, 0.8)
        ax3d.set_zlim(0.0, 1.6)

        jd = state_to_joint_dict(states[i], arm=arm)
        for a, b in model.skeleton_segments(jd):
            ax3d.plot([a[0], b[0]], [a[1], b[1]], [a[2], b[2]], "b-", lw=1.5)

        if preds is not None and i < len(preds):
            jd_p = state_to_joint_dict(preds[i], arm=arm)
            for a, b in model.skeleton_segments(jd_p):
                ax3d.plot(
                    [a[0], b[0]],
                    [a[1], b[1]],
                    [a[2], b[2]],
                    "r--",
                    lw=1.0,
                    alpha=0.7,
                )

        grip = states[i, -1] if states.shape[1] > 7 else 0.0
        ax3d.text2D(0.05, 0.95, f"gripper={grip:.2f}", transform=ax3d.transAxes)

        aximg.cla()
        aximg.axis("off")
        if frames:
            fi = min(i, len(frames) - 1)
            aximg.imshow(frames[fi])
            aximg.set_title(f"camera frame {fi}")
        else:
            aximg.set_title("no video")
            # Show joint sparklines as fallback
            aximg.plot(states[: i + 1, :7])
            aximg.set_xlim(0, n)

    if save is not None:
        try:
            import av
        except ImportError:
            print("PyAV required to --save video", file=sys.stderr)
            return 1
        # Render frames to mp4 via matplotlib
        tmp_frames = []
        for i in indices:
            draw(i)
            fig.canvas.draw()
            w, h = fig.canvas.get_width_height()
            buf = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
            tmp_frames.append(buf)
        save.parent.mkdir(parents=True, exist_ok=True)
        container = av.open(str(save), mode="w")
        stream = container.add_stream("libx264", rate=max(1, int(10 / max(1, stride))))
        stream.width = tmp_frames[0].shape[1]
        stream.height = tmp_frames[0].shape[0]
        stream.pix_fmt = "yuv420p"
        for rgb in tmp_frames:
            frame = av.VideoFrame.from_ndarray(rgb, format="rgb24")
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
        container.close()
        print(f"Wrote {save}")
        plt.close(fig)
        return 0

    # Interactive: step with key presses
    state = {"idx": 0}

    def on_key(event):
        if event.key in ("n", "right", " "):
            state["idx"] = min(state["idx"] + 1, len(indices) - 1)
        elif event.key in ("p", "left"):
            state["idx"] = max(state["idx"] - 1, 0)
        elif event.key == "q":
            plt.close(fig)
            return
        draw(indices[state["idx"]])
        fig.canvas.draw_idle()

    fig.canvas.mpl_connect("key_press_event", on_key)
    draw(indices[0])
    print("Keys: n/→ next, p/← prev, q quit")
    plt.tight_layout()
    plt.show()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--episode", type=int, default=0)
    parser.add_argument("--arm", choices=("left", "right"), default="right")
    parser.add_argument("--urdf", type=Path, default=_repo_urdf())
    parser.add_argument("--predictions", type=Path, default=None, help="(T,8) .npy ghost overlay")
    parser.add_argument("--save", type=Path, default=None, help="Write mp4 instead of interactive")
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument("--max-frames", type=int, default=None)
    args = parser.parse_args(argv)
    # silence unused import warning for actions
    return replay(
        args.dataset,
        args.episode,
        args.arm,
        args.urdf,
        args.predictions,
        args.save,
        args.stride,
        args.max_frames,
    )


if __name__ == "__main__":
    raise SystemExit(main())
