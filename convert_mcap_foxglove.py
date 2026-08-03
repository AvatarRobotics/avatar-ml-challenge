#!/usr/bin/env python3
"""
Convert MCAP files with raw H.264 video to Foxglove-compatible format.

Rewrites /video/* channels from custom 'avatar/H264Frame' (encoding='raw')
to 'foxglove.CompressedVideo' (encoding='protobuf') which Foxglove Studio
can natively decode and display as video panels.

Non-video channels (ROS topics with JSON encoding) are copied as-is.

Usage (from this challenge repo):
    python convert_mcap_foxglove.py recordings/clip_01.mcap
    python convert_mcap_foxglove.py recordings/clip_01.mcap -o recordings/clip_01_foxglove.mcap

Requires optional deps: pip install '.[foxglove]'  (or: foxglove-schemas-protobuf protobuf)
Open the output in Foxglove Studio to watch camera topics.
"""

import argparse
import re
import sys
from pathlib import Path

__all__ = ["convert_mcap", "convert_mcap_file"]

try:
    from mcap.reader import make_reader
    from mcap.writer import Writer as McapWriter

    _MCAP_AVAILABLE = True
except ImportError:
    _MCAP_AVAILABLE = False
    make_reader = None  # type: ignore[assignment]
    McapWriter = None  # type: ignore[assignment]

try:
    from foxglove_schemas_protobuf.CompressedVideo_pb2 import CompressedVideo
    from google.protobuf.descriptor_pb2 import FileDescriptorSet

    _FOXGLOVE_AVAILABLE = True
except ImportError:
    _FOXGLOVE_AVAILABLE = False
    CompressedVideo = None  # type: ignore[assignment, misc]
    FileDescriptorSet = None  # type: ignore[assignment, misc]


_MSG_LINE_RE = re.compile(rb"^MSG: (\w+)/msg/(\w+)$", re.MULTILINE)
_SHORT_SEP = b"=" * 80


def _normalize_ros2msg_schema(data: bytes) -> bytes:
    """Normalize a ros2msg concatenated schema to MCAP spec format.

    Fixes two common issues in recorded schemas:
    - Rewrites ``MSG: pkg/msg/Name`` to ``MSG: pkg/Name`` so the header
      matches the field references inside .msg text (MCAP spec requires
      the short package-resource-name form).
    - Normalizes separator lines to exactly 80 ``=`` characters.

    Ref: https://mcap.dev/spec/registry (ros1msg / ros2msg sections)
    """
    if b"MSG: " not in data:
        return data
    out = _MSG_LINE_RE.sub(rb"MSG: \1/\2", data)
    out = re.sub(rb"^={3,}$", _SHORT_SEP, out, flags=re.MULTILINE)
    return out


def _check_deps() -> None:
    """Raise if required packages are missing (called at function entry, not import)."""
    if not _MCAP_AVAILABLE:
        raise ImportError("mcap not installed. Run: pip install mcap")
    if not _FOXGLOVE_AVAILABLE:
        raise ImportError(
            "foxglove-schemas-protobuf not installed. "
            "Run: pip install foxglove-schemas-protobuf protobuf"
        )


def build_proto_file_descriptor_set(message_class) -> bytes:
    """
    Build a serialized FileDescriptorSet for a protobuf message class,
    including all transitive dependencies. This is what MCAP needs as
    schema data for protobuf-encoded channels.
    """
    fds = FileDescriptorSet()
    seen = set()

    def _add_file_descriptor(fd):
        if fd.name in seen:
            return
        seen.add(fd.name)
        for dep in fd.dependencies:
            _add_file_descriptor(dep)
        fd_proto = fds.file.add()
        fd.CopyToProto(fd_proto)

    _add_file_descriptor(message_class.DESCRIPTOR.file)
    return fds.SerializeToString()


def is_video_channel(channel, schema) -> bool:
    """Check if a channel contains raw H.264 video data."""
    return (
        channel.message_encoding == "raw"
        and ("/video/" in channel.topic or "camera" in channel.topic.lower())
    )


def convert_mcap(
    input_path: Path,
    output_path: Path,
    group_window_ns: int,
    *,
    quiet: bool = False,
) -> dict:
    """
    Convert MCAP, rewriting raw video channels to foxglove.CompressedVideo.

    NAL units within group_window_ns of each other are concatenated into
    a single CompressedVideo message. This groups SPS+PPS+IDR NAL units
    that belong to the same keyframe into one access unit for proper
    Foxglove decoding.

    Set quiet=True to suppress progress/summary output (used when called
    from materialize_mcap which prints its own summary).

    Returns a stats dict with keys: video_channels_found, video_topics,
    total_channels, messages_in, messages_out, video_frames_out.
    Returns immediately (without writing output) if no video channels found.
    """
    _check_deps()
    _print = print if not quiet else (lambda *a, **k: None)
    proto_schema_data = build_proto_file_descriptor_set(CompressedVideo)

    with open(input_path, "rb") as f_in:
        reader = make_reader(f_in)
        summary = reader.get_summary()

        # Identify which channels are raw video
        video_channel_ids = set()
        if summary:
            for ch_id, channel in summary.channels.items():
                schema = summary.schemas.get(channel.schema_id)
                if is_video_channel(channel, schema):
                    video_channel_ids.add(ch_id)

        total_input_msgs = 0
        if summary and summary.statistics:
            total_input_msgs = summary.statistics.message_count

        _print(f"Input:  {input_path.name}")
        _print(f"  {len(summary.channels) if summary else '?'} channels, "
               f"{total_input_msgs:,} messages")
        _print(f"  {len(video_channel_ids)} video channel(s) to convert:")
        if summary:
            for ch_id in video_channel_ids:
                ch = summary.channels[ch_id]
                _print(f"    {ch.topic}")

        if not video_channel_ids:
            _print("\nNo raw video channels found. Nothing to convert.")
            return {
                "video_channels_found": 0,
                "video_topics": [],
                "total_channels": len(summary.channels) if summary else 0,
                "messages_in": total_input_msgs,
                "messages_out": 0,
                "video_frames_out": 0,
            }

        # Re-read from start for message iteration
        f_in.seek(0)
        reader = make_reader(f_in)

        with open(output_path, "wb") as f_out:
            writer = McapWriter(f_out)
            writer.start()

            # Copy metadata from original file
            if summary and summary.metadata_indexes:
                f_in.seek(0)
                meta_reader = make_reader(f_in)
                for metadata in meta_reader.iter_metadata():
                    writer.add_metadata(metadata.name, metadata.metadata)
                f_in.seek(0)
                reader = make_reader(f_in)

            # Register the foxglove.CompressedVideo schema once
            fox_schema_id = writer.register_schema(
                name="foxglove.CompressedVideo",
                encoding="protobuf",
                data=proto_schema_data,
            )

            # Mappings: old ID -> new ID
            channel_map = {}  # old channel_id -> new channel_id
            schema_map = {}   # old schema_id -> new schema_id

            # Buffer for grouping NAL units per video channel
            # ch_id -> {"data": bytes, "log_time": int, "publish_time": int}
            nal_buffers = {}

            msg_count = 0
            written_count = 0
            video_frames_out = 0

            def flush_nal_buffer(ch_id):
                nonlocal written_count, video_frames_out
                if ch_id not in nal_buffers or not nal_buffers[ch_id]["data"]:
                    return

                buf = nal_buffers[ch_id]
                ts_ns = buf["log_time"]

                msg = CompressedVideo()
                msg.timestamp.seconds = ts_ns // 1_000_000_000
                msg.timestamp.nanos = ts_ns % 1_000_000_000
                msg.frame_id = ""
                msg.data = buf["data"]
                msg.format = "h264"

                writer.add_message(
                    channel_id=channel_map[ch_id],
                    log_time=buf["log_time"],
                    publish_time=buf["publish_time"],
                    data=msg.SerializeToString(),
                )
                written_count += 1
                video_frames_out += 1
                nal_buffers[ch_id] = {"data": b"", "log_time": 0, "publish_time": 0}

            for schema, channel, message in reader.iter_messages():
                msg_count += 1

                if msg_count % 10000 == 0:
                    if total_input_msgs > 0:
                        pct = (msg_count / total_input_msgs) * 100
                        _print(f"\r  Processing... {msg_count:,}/{total_input_msgs:,} "
                               f"({pct:.0f}%)", end="", flush=True)
                    else:
                        _print(f"\r  Processing... {msg_count:,}", end="", flush=True)

                old_ch_id = channel.id

                # Register channel/schema on first encounter
                if old_ch_id not in channel_map:
                    if old_ch_id in video_channel_ids:
                        new_ch_id = writer.register_channel(
                            schema_id=fox_schema_id,
                            topic=channel.topic,
                            message_encoding="protobuf",
                            metadata=channel.metadata,
                        )
                        channel_map[old_ch_id] = new_ch_id
                    else:
                        if schema and schema.id not in schema_map:
                            schema_data = schema.data
                            if schema.encoding == "ros2msg":
                                schema_data = _normalize_ros2msg_schema(schema_data)
                            new_schema_id = writer.register_schema(
                                name=schema.name,
                                encoding=schema.encoding,
                                data=schema_data,
                            )
                            schema_map[schema.id] = new_schema_id

                        s_id = schema_map.get(schema.id, 0) if schema else 0
                        new_ch_id = writer.register_channel(
                            schema_id=s_id,
                            topic=channel.topic,
                            message_encoding=channel.message_encoding,
                            metadata=channel.metadata,
                        )
                        channel_map[old_ch_id] = new_ch_id

                if old_ch_id in video_channel_ids:
                    # Group NAL units by time proximity into access units
                    if old_ch_id not in nal_buffers or not nal_buffers[old_ch_id]["data"]:
                        nal_buffers[old_ch_id] = {
                            "data": message.data,
                            "log_time": message.log_time,
                            "publish_time": message.publish_time,
                        }
                    elif (message.log_time - nal_buffers[old_ch_id]["log_time"]
                          <= group_window_ns):
                        nal_buffers[old_ch_id]["data"] += message.data
                    else:
                        flush_nal_buffer(old_ch_id)
                        nal_buffers[old_ch_id] = {
                            "data": message.data,
                            "log_time": message.log_time,
                            "publish_time": message.publish_time,
                        }
                else:
                    writer.add_message(
                        channel_id=channel_map[old_ch_id],
                        log_time=message.log_time,
                        publish_time=message.publish_time,
                        data=message.data,
                    )
                    written_count += 1

            # Flush remaining buffered NAL units
            for ch_id in list(nal_buffers.keys()):
                flush_nal_buffer(ch_id)

            writer.finish()

    video_topics = []
    if summary:
        video_topics = [
            summary.channels[ch_id].topic for ch_id in video_channel_ids
            if ch_id in summary.channels
        ]

    _print(f"\r  Processed {msg_count:,} input messages                    ")
    _print(f"\nOutput: {output_path.name}")
    _print(f"  {written_count:,} messages written ({video_frames_out:,} video frames)")
    _print("  Video channels now use foxglove.CompressedVideo (protobuf)")
    _print("\nOpen in Foxglove Studio:")
    _print(f"  foxglove-studio {output_path}")

    return {
        "video_channels_found": len(video_channel_ids),
        "video_topics": video_topics,
        "total_channels": len(summary.channels) if summary else 0,
        "messages_in": msg_count,
        "messages_out": written_count,
        "video_frames_out": video_frames_out,
    }


def convert_mcap_file(
    input_path: Path,
    output_path: Path | None = None,
    group_window_ms: float = 5.0,
    *,
    quiet: bool = False,
) -> tuple[Path, dict]:
    """Convert a raw MCAP to Foxglove-compatible format and return the output path.

    Importable convenience wrapper around convert_mcap().

    Args:
        input_path: Path to input MCAP with raw H.264 video channels.
        output_path: Destination path. Defaults to <input>_foxglove.mcap.
        group_window_ms: NAL unit grouping window in milliseconds.
        quiet: Suppress progress/summary output.

    Returns:
        Tuple of (output_path, stats_dict). If no video channels were found,
        the output file is NOT created and stats["video_channels_found"] == 0.
    """
    if output_path is None:
        output_path = input_path.with_name(input_path.stem + "_foxglove.mcap")
    group_window_ns = int(group_window_ms * 1_000_000)
    stats = convert_mcap(input_path, output_path, group_window_ns, quiet=quiet)
    return output_path, stats


def main():
    parser = argparse.ArgumentParser(
        description="Convert MCAP with raw H.264 video to Foxglove-compatible format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    ./convert_mcap_foxglove.py recording.mcap
    ./convert_mcap_foxglove.py recording.mcap -o foxglove_recording.mcap
    ./convert_mcap_foxglove.py recording.mcap --group-window-ms 5

The converted file can be opened directly in Foxglove Studio with
video panels for each /video/* topic.

Requirements:
    pip install mcap foxglove-schemas-protobuf protobuf
""",
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Input MCAP file with raw H.264 video channels",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output MCAP file path (default: <input>_foxglove.mcap)",
    )
    parser.add_argument(
        "--group-window-ms",
        type=float,
        default=5.0,
        help="Time window (ms) to group NAL units into single video frames. "
             "NAL units within this window are concatenated into one "
             "CompressedVideo message. Default: 5ms",
    )

    args = parser.parse_args()

    try:
        _check_deps()
    except ImportError as e:
        print(f"ERROR: {e}")
        return 1

    if not args.input.exists():
        print(f"ERROR: Input file not found: {args.input}")
        return 1

    output = args.output
    if output is None:
        output = args.input.with_name(args.input.stem + "_foxglove.mcap")

    group_window_ns = int(args.group_window_ms * 1_000_000)

    print(f"\n{'='*60}")
    print("MCAP -> Foxglove Converter")
    print(f"NAL grouping window: {args.group_window_ms}ms")
    print(f"{'='*60}\n")

    convert_mcap(args.input, output, group_window_ns)

    print(f"\n{'='*60}")
    print("Done!")
    print(f"{'='*60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
