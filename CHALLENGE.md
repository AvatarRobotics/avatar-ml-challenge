# Machine Learning Engineer Code Challenge:
# Teleop Recording → Training-Ready Dataset

## Objective

Write software that takes raw Agibot G1 teleoperation recordings (MCAP) and
produces a training-ready episodic dataset suitable for imitation-learning /
behavior-cloning policy training.

You will work with real multi-modal robot data: multi-rate joint streams,
H.264 camera video, VR controller data, and hand/gripper commands. The core of
the challenge is deciding — and defending — how raw teleop streams become
training data: what the observations and actions are, how streams are
synchronized, and where episodes begin and end.

## Setup

Follow the instructions in the challenge repository README:

> **Challenge repo:** https://github.com/AvatarRobotics/avatar-ml-challenge/blob/20260723/README.md

Quick path:

```bash
git clone https://github.com/AvatarRobotics/avatar-ml-challenge.git
cd avatar-ml-challenge
git checkout 20260723

docker pull ghcr.io/avatarrobotics/avatar-ml-challenge:20260723
docker run --rm -it --platform linux/amd64 \
  -v "$PWD":/work -w /work \
  ghcr.io/avatarrobotics/avatar-ml-challenge:20260723 bash
```

Alongside the repo link you will receive a small zip (**links only**, no MCAP
bytes) named like `avatar-ml-challenge-mcap-urls.zip` containing
`manifest.json` with time-limited download URLs. Place that manifest at
`data/manifest.json` in the challenge repo, then:

1. Install the Python environment if not using Docker (`uv sync` or `pip install -e .`)
2. `python download_data.py data/manifest.json --out recordings/`
3. Explore a recording: `python inspect_mcap.py recordings/clip_01.mcap`

A laptop with ~8 GB RAM is enough for the core task. A GPU is only needed for
the training bonus.

If downloads return HTTP 403, the URLs expired — ask for a refreshed zip.

## What you're given

- **~30 minutes of MCAP teleop recordings** across multiple clips from two
  recording eras / settings (different facilities, camera topic names, and
  end-effector behavior)
- **Topic schema docs** (`docs/TOPICS.md`) and sanitized message samples
- **Sanitized Agibot G1 URDF + meshes** for visualization / kinematics
- **Optional helper scripts** you may use or ignore: `inspect_mcap.py`
  (topic explorer), `validate_submission.py` (structural dataset checks),
  `replay_dataset.py` (URDF forward-kinematics viewer)

Clips also carry `/tf` and an embedded URDF so you can open them in
[Foxglove](https://foxglove.dev/) and watch the robot move before writing code.

## Core Requirements

Build a runnable pipeline that converts the provided MCAP recordings into an
episodic dataset ready for imitation-learning training.

### Input streams

The recordings contain (among others):

| Topic | Role |
|-------|------|
| `/hal/arm_joint_state` | Measured 14-DoF dual-arm joint positions |
| `/wbc/arm_command` | Commanded joint positions |
| `/wbc/hand_command` | Hand / finger joint commands |
| `/remote/vr_data` | VR controller state |
| `/video/camera_0` or `/video/Head` (+ wrist cams) | ~30 Hz H.264 video |

Topic names and behavior differ between the two recording eras — inspect the
data rather than assuming. See `docs/TOPICS.md` for message shapes.

### Output dataset — your design

The dataset design decisions are yours to make and justify:

- **Format:** we recommend [LeRobot](https://github.com/huggingface/lerobot)
  v3 (it is what our training stack consumes, and the helper tools understand
  it), but a documented equivalent is acceptable
- **Observations and actions:** you decide which streams become observation
  state, which become actions, which cameras to include, and the
  dimensionality of each
- **Control rate:** you decide the output rate and how multi-rate streams are
  aligned onto it
- **Episodes:** you decide what constitutes an episode, where the boundaries
  are, and how many there are. **Do not assume a single grasp signal exists.**
  The eras gate picks differently — on some clips VR trigger signals are
  meaningful, on others they are not. Discover what the data supports and
  justify your heuristic per era.

There is no single expected answer for any of these. We care about whether
your choices would produce data a behavior-cloning policy could actually
learn from, and whether you can explain why.

### Required artifacts

1. A runnable pipeline (CLI or script) that converts the provided MCAPs into
   your dataset
2. A `DATA_REPORT.md` covering:
   - Your dataset design: features, shapes, rate, and why
   - Episode definition and boundary heuristics per era, with counts and
     duration stats
   - Alignment strategy and its tradeoffs
   - What you dropped or skipped, and how you handled messy / idle segments

## Additional Features (Bonus)

You may implement any of the following to demonstrate further skills:

- **Idle / deadspace trimming** — detect and drop long stationary stretches
- **Additional modalities** — wrist cameras, force, body joints
- **Auto success / failure labeling** — with a heuristic you justify
- **Unified pipeline across both recording eras** — handle schema / topic
  alias differences cleanly in one code path
- **Train a small policy** — e.g. ACT / a tiny BC model (Colab-friendly) on
  your dataset and compare it against a naive "repeat last action" baseline
  in open-loop eval on held-out data
- **Policy visualization** — overlay predicted actions against ground truth
  (the provided `replay_dataset.py` FK viewer supports a `--predictions`
  ghost overlay, or build your own)

## Submission

Submit a link to a GitHub (or similar) git repository that contains:

- Your conversion pipeline and any supporting code
- `DATA_REPORT.md` as described above
- Instructions to reproduce your dataset from the provided clips
- (Optional) Training / eval code and metrics for the bonus tiers

In your README, please also describe:

- How you thought about the problem
- What decisions you made and why
- Any assumptions

## Evaluation Criteria

We will assess submissions based on:

- **Judgment:** Are your dataset design, alignment, and episode decisions
  sound for imitation learning, and are they well defended in
  `DATA_REPORT.md`? How did you handle the messy parts of the data?
- **Amount achieved:** How much of the pipeline works end-to-end, and how
  many (and how difficult) additional features were implemented
- **Code quality:** Readability, organization, clarity of logic

We do not grade against a hidden reference answer — recordings are messy and
reasonable people will produce different datasets. Your dataset should load,
be internally consistent, and hold up when we look at it (e.g. joint streams
that plausibly match the video).

You may use any references or AI tools you'd like, but we expect you to be
able to explain any parts of the code and why you chose to implement it the
way you did.

## Completion Time

We expect this challenge to take a few hours, though please use additional
time if you need. Focus on a working core solution first before attempting
any extras.
