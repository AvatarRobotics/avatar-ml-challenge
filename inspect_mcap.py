#!/usr/bin/env python3
"""List topics, message counts, and time ranges for a challenge MCAP clip.

This is a foothold, not a solution. Use it to explore the recordings before
writing your conversion pipeline.

Usage:
    python inspect_mcap.py path/to/clip.mcap
    python inspect_mcap.py path/to/clip.mcap --topic /hal/arm_joint_state --limit 2
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def _ns_to_sec(ns: int) -> float:
    return ns / 1e9


def inspect(path: Path, topic_filter: str | None, limit: int) -> int:
    try:
        from mcap.reader import make_reader
    except ImportError:
        print("Install deps first:  uv sync   (or pip install -e .)", file=sys.stderr)
        return 1

    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    counts: dict[str, int] = defaultdict(int)
    first_ns: dict[str, int] = {}
    last_ns: dict[str, int] = {}
    schemas: dict[str, str] = {}
    samples: dict[str, list[dict]] = defaultdict(list)

    with path.open("rb") as fh:
        reader = make_reader(fh)
        summary = reader.get_summary()
        if summary and summary.statistics:
            start = summary.statistics.message_start_time
            end = summary.statistics.message_end_time
            print(f"File: {path.name}")
            print(f"Duration: {_ns_to_sec(end - start):.2f}s")
            print(f"Message count (summary): {summary.statistics.message_count}")
            print()

        for schema, channel, message in reader.iter_messages():
            topic = channel.topic
            counts[topic] += 1
            if topic not in first_ns:
                first_ns[topic] = message.log_time
            last_ns[topic] = message.log_time
            if schema is not None:
                schemas[topic] = schema.name

            if topic_filter and topic == topic_filter and len(samples[topic]) < limit:
                try:
                    payload = json.loads(message.data)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    payload = {
                        "_binary_bytes": len(message.data),
                        "_note": "non-JSON payload (likely video / protobuf)",
                    }
                samples[topic].append(
                    {
                        "log_time_ns": message.log_time,
                        "publish_time_ns": message.publish_time,
                        "payload": payload,
                    }
                )

    print(f"{'TOPIC':<40} {'COUNT':>8} {'HZ~':>8} {'SCHEMA'}")
    print("-" * 90)
    for topic in sorted(counts.keys()):
        n = counts[topic]
        dt = _ns_to_sec(last_ns[topic] - first_ns[topic]) or 1e-9
        hz = n / dt
        schema = schemas.get(topic, "")
        print(f"{topic:<40} {n:>8} {hz:>8.1f} {schema}")

    if topic_filter:
        print()
        print(f"Samples for {topic_filter} (up to {limit}):")
        for i, sample in enumerate(samples.get(topic_filter, [])):
            print(f"--- sample {i} ---")
            print(json.dumps(sample, indent=2)[:4000])

    print()
    print("Tip: open Foxglove-converted clips in https://foxglove.dev/ to watch /tf + video.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mcap", type=Path, help="Path to an MCAP recording")
    parser.add_argument("--topic", default=None, help="Dump JSON samples for this topic")
    parser.add_argument("--limit", type=int, default=2, help="Samples to dump (default 2)")
    args = parser.parse_args(argv)
    return inspect(args.mcap, args.topic, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
