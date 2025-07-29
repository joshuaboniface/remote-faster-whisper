# CUDA/GPU Dockerfile (default)
FROM nvidia/cuda:12.9.1-cudnn-runtime-ubuntu22.04

RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    ln -sf /usr/bin/python3 /usr/bin/python && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

EXPOSE 9876

CMD ["python", "remote_faster_whisper.py", "-c", "config.yaml"]
