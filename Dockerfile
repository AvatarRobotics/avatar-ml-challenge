FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/AvatarRobotics/avatar-ml-challenge"
LABEL org.opencontainers.image.description="Avatar Robotics ML Engineer code challenge environment"
LABEL org.opencontainers.image.licenses="MIT"

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        libglib2.0-0 \
        libgl1 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work

COPY pyproject.toml README.md CHALLENGE.md LICENSE ./
COPY inspect_mcap.py validate_submission.py replay_dataset.py download_data.py fk.py ./
COPY challenge_lib ./challenge_lib
COPY docs ./docs
COPY samples ./samples
COPY urdf ./urdf
COPY data ./data

RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -e .

CMD ["bash"]
