# Machine Learning Engineer Code Challenge

We have created a Docker image and starter repository for converting real Agibot G1
teleoperation recordings (MCAP) into a training-ready episodic dataset. These are
instructions on how to install and run the environment on Ubuntu or macOS.

Windows hosts are not officially supported; WSL2 + Docker Desktop or an Ubuntu VM
usually works.

Full challenge brief: [`CHALLENGE.md`](CHALLENGE.md)

## Setup

### Ubuntu

1. Install Docker: https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository
2. Prefer running Docker as a non-root user: https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user
3. Check that Docker works: `docker run hello-world`
4. Install the challenge image (from the public GitHub Release):

```bash
curl -L -o avatar-ml-challenge.tar.gz \
  https://github.com/AvatarRobotics/avatar-ml-challenge/releases/download/20260723/avatar-ml-challenge-20260723-amd64.tar.gz
docker load -i avatar-ml-challenge.tar.gz
```

### macOS

1. Install Docker Desktop: https://docs.docker.com/desktop/setup/install/mac-install/
2. Check that Docker works: `docker run hello-world`
3. Install the challenge image:

```bash
curl -L -o avatar-ml-challenge.tar.gz \
  https://github.com/AvatarRobotics/avatar-ml-challenge/releases/download/20260723/avatar-ml-challenge-20260723-amd64.tar.gz
docker load -i avatar-ml-challenge.tar.gz
```

### Starting the container (Ubuntu and macOS)

Clone this repository, then start a container with your working copy mounted:

```bash
git clone https://github.com/AvatarRobotics/avatar-ml-challenge.git
cd avatar-ml-challenge
git checkout 20260723

docker run --rm -it \
  --name avatar-ml-challenge \
  --platform linux/amd64 \
  -v "$PWD":/work \
  -w /work \
  ghcr.io/avatarrobotics/avatar-ml-challenge:20260723 \
  bash
```

Inside the container the challenge dependencies are already installed. You can
also develop outside Docker with Python 3.11+:

```bash
pip install -e .
# or: uv sync
```

### Data download

Alongside the challenge you will receive a small zip (**links only**, no MCAP
bytes) named like `avatar-ml-challenge-mcap-urls.zip`. It contains
`manifest.json` with time-limited download URLs.

1. Place that file at `data/manifest.json` in this repository
2. Download the clips:

```bash
python download_data.py data/manifest.json --out recordings/
```

3. Explore a recording:

```bash
python inspect_mcap.py recordings/clip_01.mcap
python inspect_mcap.py recordings/clip_01.mcap --topic /hal/arm_joint_state --limit 1
```

If downloads return HTTP 403, the URLs expired — ask for a refreshed zip.

A laptop with ~8 GB RAM is enough for the core task. A GPU is only needed for
the optional training bonus.

## Repository layout

| Path | Purpose |
|------|---------|
| `CHALLENGE.md` | The challenge brief |
| `docs/TOPICS.md` | Message schemas + notes on era differences |
| `samples/` | Sanitized JSON topic samples |
| `urdf/` | Sanitized Agibot G1 URDF + meshes |
| `inspect_mcap.py` | Topic / rate explorer |
| `download_data.py` | Fetch clips from URL manifest |
| `validate_submission.py` | Optional structural dataset checks |
| `replay_dataset.py` | Optional FK skeleton + camera replay viewer |
| `fk.py` | URDF forward kinematics used by the replay viewer |
| `data/manifest.example.json` | Manifest schema example |
| `Dockerfile` | Image definition (also published as a release asset) |

## Developing

Build a runnable pipeline that converts the provided MCAPs into an episodic,
training-ready dataset, and write `DATA_REPORT.md` defending your design
(features, rate, alignment, episode definition, messy-data handling).

The dataset design (schema, control rate, episode boundaries, arm/camera
choices) is **yours to make and defend**. See `CHALLENGE.md` for evaluation
criteria and bonus tiers.

Optional helpers (use or ignore):

```bash
python validate_submission.py <dataset>
python replay_dataset.py <dataset> --episode 0
```

Clips also carry `/tf` and an embedded URDF so you can open them in
[Foxglove](https://foxglove.dev/) and watch the robot move before writing code.

## Submitting

Create a public GitHub (or similar) git repository with your solution code and a
`README.md` describing how to reproduce your dataset from the provided clips,
plus `DATA_REPORT.md` and any bonus training / eval artifacts.

You do not need to include the MCAP files or redistributed URLs. Optionally
include a Dockerfile; otherwise we will run your code from
`ghcr.io/avatarrobotics/avatar-ml-challenge:20260723`.

AI tools are allowed. You must be able to explain your code and decisions.

## Data notes

- Clips come from **two recording eras / settings**. Topic names, rates, and
  pick gating differ — inspect before assuming.
- Please do not redistribute the recordings outside this challenge.
