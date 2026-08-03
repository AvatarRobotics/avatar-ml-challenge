# MCAP Topic Reference

JSON-encoded ROS-like messages inside the challenge MCAPs. See `samples/` for
real payloads (fields may vary slightly across recording eras — handle aliases).

## Core topics (required for the challenge)

### `/hal/arm_joint_state` (~173 Hz)

Measured dual-arm joint positions.

- `name`: 14 strings — `left_arm_joint1`…`left_arm_joint7`, `right_arm_joint1`…`right_arm_joint7`
- `position`: 14 floats (radians)
- Sample: `samples/hal_arm_joint_state.json`

### `/wbc/arm_command` (control rate)

Commanded dual-arm joint targets.

- `name`: often `Joint1_l`…`Joint7_l`, `Joint1_r`…`Joint7_r` (naming differs from HAL)
- `position`: 14 floats (radians)
- Sample: `samples/wbc_arm_command.json`

Map left/right carefully — HAL and WBC use different name schemes.

### `/remote/vr_data` (VR rate)

VR controller state. Present on most clips, but **not always the pick gate**.

- `vr_controller_states[]` with `name` in `{left, right, head}`
- `index_trig`: float in `[0, 1]` — historically used as a vacuum / grasp proxy
  on some suction setups
- `hand_trig`: float — often held during active teleop
- Sample: `samples/remote_vr_data.json`

**Important:** Recent mid-shift production clips (gamma) typically **do not**
drive picks from `index_trig`. Inspect `/wbc/hand_command`, arm motion, and
other channels before committing to an episode heuristic.

### Camera topic aliases

Older clips often use `/video/camera_0` (head), `/video/camera_1` (right wrist),
`/video/camera_2` (left wrist). Newer clips may use `/video/Head`,
`/video/Hand_Left`, `/video/Hand_Right` (plus fisheye streams you can ignore).

### Video payload format

Video messages contain raw **Annex-B H.264** NAL units (`00 00 00 01` start
codes) — one or more NALs per message; the message `log_time` is your frame
timestamp reference. Because clips are cut from continuous recordings, the
stream usually starts **mid-GOP**: expect the first SPS/PPS + IDR keyframe up
to ~10 s in (they recur every few seconds), and handle undecodable leading
packets gracefully.

### `/wbc/hand_command` (control rate)

Finger / hand joint commands (more relevant for finger-gripper setups).

- Sample: `samples/wbc_hand_command.json`

### `/video/camera_0` (~30 Hz H.264)

Head camera. Payload is **not** JSON — raw / CompressedVideo H.264 access units.
Aliases seen in older recordings:

- `/video/Head_Camera`, `/video/Head`

Wrist cameras (bonus):

- Left wrist: `/video/camera_2` (aliases: `Hand_Left`, `Left_Wrist_Camera`)
- Right wrist: `/video/camera_1` (aliases: `Hand_Right`, `Right_Wrist_Camera`)

Use `inspect_mcap.py` to see which topics a given clip actually contains.

### Depth (when present)

Depth streams are included when the recording has them. Topic names differ by era:

- Newer clips: `/depth/raw_frames`
- Older clips: `/depth/compressed_frames`

Payloads are **not** JSON — treat them as opaque/binary depth frames and discover
encoding from the messages (or ignore depth if you do not need it).

## Optional / bonus topics

| Topic | Use |
|-------|-----|
| `/hal/left_arm_data`, `/hal/right_arm_data` | Per-motor force / velocity (see sample) |
| `/hal/left_ee_data`, `/hal/right_ee_data` | End-effector / finger state |
| `/hal/waist_state`, `/hal/neck_state` | Body 4-DoF state |
| `/wbc/joint_position_control` | Body command |
| `/depth/raw_frames`, `/depth/compressed_frames` | Depth (era alias; optional modality) |
| `/tf`, `/tf_static` | Present on Foxglove-prepared clips (FK already injected) |

## One example packing (NOT a requirement)

The dataset schema and control rate are your design decisions. Purely as an
illustration, one workable layout is:

| Feature | Shape | Source idea |
|---------|-------|-------------|
| `observation.state` | `(8,)` | 7 measured arm joints + a gripper channel |
| `action` | `(8,)` | 7 commanded arm joints + a gripper command |
| `observation.images.camera` | video | Head camera, remuxed to your control rate |

You may choose different features, dimensions, rates, single- or dual-arm,
extra modalities, etc. Whatever you choose, document it in `DATA_REPORT.md`.

## Alignment notes

Streams are multi-rate and may have small clock skew. Common approaches:

- Build a fixed-rate grid (you pick the rate) from `t0` to `t1`
- Nearest-neighbor or hold-last for joints
- Nearest video keyframe / PTS for images
- Interpolate joints only if you understand the units and wrap

There is no single correct method — explain yours in `DATA_REPORT.md`.

## Inspecting video in Foxglove

For visual inspection of the recordings, convert camera topics so Foxglove
Studio can play them. Camera topics ship as raw Annex-B H.264
(`avatar/H264Frame`), which Studio does not play natively:

```bash
pip install '.[foxglove]'
python convert_mcap_foxglove.py recordings/clip_01.mcap
```

Then open the `*_foxglove.mcap` output in Foxglove. For training pipelines you
can decode the original raw H.264 with PyAV without converting.
