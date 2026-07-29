# Machine Learning Engineer Code Challenge:
# Teleop Recording → Dataset Design

## Objective

Write software that takes raw humanoid teleoperation recordings (MCAP) and
turns them into a dataset for a task you choose and defend.

You will work with real multi-modal robot data. The core of the challenge is
**understanding the data and exercising judgment**: what problem is this data
good for, what should the dataset look like for that problem, and how do you
turn messy teleop streams into something consistent and usable.

## Setup

Follow the instructions in the README here:
https://github.com/AvatarRobotics/avatar-ml-challenge/blob/20260723/README.md

It covers Docker (or local Python), downloading the recordings, and exploring
clips. Alongside this doc you will receive a small zip (**links only**) named
like `avatar-ml-challenge-mcap-urls.zip` — place `manifest.json` at
`data/manifest.json` in the repo, then run `download_data.py` as described in
the README. If downloads return HTTP 403, ask for a refreshed zip.

## Core Requirements

- Inspect the recordings and decide what task they best support. That choice
  is yours — imitation learning / behavior cloning is one option, not a
  requirement.
- Design and produce a dataset for that task: features, labels / targets (if
  any), rate, alignment, and how you segment or structure examples. Document
  alternatives you considered.
- **Do not assume a single grasp or episode signal exists.** Topic names and
  behavior differ across the two recording eras — discover what the data
  supports and justify your approach.
- Ship:
  1. A runnable pipeline that builds your dataset from the provided MCAPs
  2. `DATA_REPORT.md` covering: the task you chose and why; dataset design;
     how you handled messy / idle / inconsistent data; and enough detail that
     we can check your outputs against your claims

We care about **data quality, logic, and consistency between your report and
what you produce** — more than about matching a prescribed schema. Topic
schemas and samples live in the repo (`docs/TOPICS.md`, `samples/`). Optional
helpers (`inspect_mcap.py`, `validate_submission.py`, `replay_dataset.py`) are
available; use or ignore them.

## Optional additions

Anything beyond the core is optional. You may add extras that strengthen your
solution (for example: cleaning heuristics, evaluation, visualization, or a
small model trained on your dataset) — or invent your own. Explain what you
added and why in `DATA_REPORT.md` or your README; we may award bonus credit
for strong optional work.

## Submission

Submit a link to a GitHub (or similar) git repository with your pipeline,
`DATA_REPORT.md`, and reproduce instructions. In your README, also describe how
you thought about the problem, what decisions you made and why, and any
assumptions.

## Evaluation Criteria

We will assess submissions based on:

- **Judgment:** Did you understand the data, pick a sensible task, and design
  a dataset that fits it — with a clear defense in `DATA_REPORT.md`?
- **Amount achieved:** How much works end-to-end, and how far did you take
  optional additions
- **Code quality:** Readability, organization, clarity of logic

There is no single hidden answer. Your dataset should load, be internally
consistent, and match what your report claims.

You may use any references or AI tools you'd like, but we expect you to be able
to explain your code and decisions.

## Completion Time

We expect this challenge to take a few hours, though please use additional time
if you need. Focus on a working core solution first before attempting any
extras.
