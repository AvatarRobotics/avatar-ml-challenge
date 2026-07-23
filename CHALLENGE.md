# Machine Learning Engineer Code Challenge:
# Teleop Recording → Training-Ready Dataset

## Objective

Write software that takes raw humanoid teleoperation recordings (MCAP) and
produces a training-ready episodic dataset for imitation-learning /
behavior-cloning. You will work with real multi-modal data (multi-rate joints,
H.264 video, VR / hand commands). The core of the challenge is deciding — and
defending — what becomes observation vs action, how streams are aligned, and
where episodes begin and end.

## Setup

Follow the instructions in the README here:
https://github.com/AvatarRobotics/avatar-ml-challenge/blob/20260723/README.md

It covers Docker (or local Python), downloading the recordings, and exploring
clips. Alongside this doc you will receive a small zip (**links only**) named
like `avatar-ml-challenge-mcap-urls.zip` — place `manifest.json` at
`data/manifest.json` in the repo, then run `download_data.py` as described in
the README. If downloads return HTTP 403, ask for a refreshed zip.

## Core Requirements

- Convert the provided MCAPs into an episodic dataset suitable for imitation
  learning. [LeRobot](https://github.com/huggingface/lerobot) v3 is recommended
  (our helpers understand it); a documented equivalent is fine.
- You choose observations, actions, cameras, output rate, alignment, and
  episode boundaries. **Do not assume a single grasp signal exists** — the two
  recording eras gate picks differently; discover what the data supports and
  justify your heuristic.
- Ship:
  1. A runnable conversion pipeline
  2. `DATA_REPORT.md` covering design (features / shapes / rate), episode
     definition + counts, alignment tradeoffs, and how you handled messy /
     idle data

Topic schemas and samples live in the repo (`docs/TOPICS.md`, `samples/`).
Optional helpers (`inspect_mcap.py`, `validate_submission.py`,
`replay_dataset.py`) are available; use or ignore them.

## Additional Features (Bonus)

You may implement any of the following to demonstrate further skills:

- Idle / deadspace trimming
- Extra modalities (wrist cams, force, body joints)
- Auto success / failure labeling (justify the heuristic)
- One pipeline that handles both recording eras cleanly
- Train a small policy and compare to a naive baseline on held-out data
- Policy visualization (e.g. predicted-action overlay via `replay_dataset.py`)

## Submission

Submit a link to a GitHub (or similar) git repository with your pipeline,
`DATA_REPORT.md`, and reproduce instructions. In your README, also describe how
you thought about the problem, what decisions you made and why, and any
assumptions.

## Evaluation Criteria

We will assess submissions based on:

- **Judgment:** Are dataset design, alignment, and episode decisions sound for
  imitation learning, and well defended in `DATA_REPORT.md`?
- **Amount achieved:** How much works end-to-end, and how many (and how
  difficult) extras were implemented
- **Code quality:** Readability, organization, clarity of logic

There is no single hidden answer. Your dataset should load, be internally
consistent, and hold up under inspection.

You may use any references or AI tools you'd like, but we expect you to be able
to explain your code and decisions.

## Completion Time

We expect this challenge to take a few hours, though please use additional time
if you need. Focus on a working core solution first before attempting any
extras.
