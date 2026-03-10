FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    wget \
    unzip \
    build-essential \
    python3-dev \
    librdkafka-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir utils && cd utils \
&& git init \
&& git remote add origin https://github.com/ATNoG/pei-nwdaf-comms.git \
&& git fetch \
&& git checkout origin/main kafka/src/kmw.py \
&& mv kafka/src/kmw.py . \
&& rm -rf .git \
&& rmdir -p kafka/src

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

EXPOSE ${PORT:-8000}

CMD sh -c "uv run uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"
