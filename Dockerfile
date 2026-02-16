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

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
