FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/tmp

# envsubst, for generating a configuration from environment variables
RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext-base \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the Python requirements, and the CUDA 12 libraries for GPU support
# (ignored for CPU-only use); see requirements-cuda.txt
COPY requirements.txt requirements-cuda.txt ./
RUN pip install -r requirements.txt -r requirements-cuda.txt
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.13/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.13/site-packages/nvidia/cudnn/lib

COPY remote_faster_whisper.py healthcheck.py config.yaml.template /app/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && mkdir -p /config /models && chmod 1777 /models

VOLUME /models
EXPOSE 9876

# The start period allows time to download and load the model on first start
HEALTHCHECK --interval=30s --timeout=10s --start-period=5m --retries=3 \
    CMD ["python", "/app/healthcheck.py"]

ENTRYPOINT ["/entrypoint.sh"]
