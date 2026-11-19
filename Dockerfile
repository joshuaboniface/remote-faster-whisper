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

# Install the Python requirements, except torch: nothing imports it directly, and it
# pulls in several GB of CUDA libraries that may not match what CTranslate2 needs.
COPY requirements.txt .
RUN grep -vxF torch requirements.txt > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# CUDA 12 cuBLAS and cuDNN 9, as required by CTranslate2 4.x for GPU support; these
# are dlopen()'d at runtime so must be on the library path. CPU-only use ignores them.
# These versions are tested back to Pascal (compute capability 6.1) GPUs.
ARG CUBLAS_VERSION=12.8.5.5
ARG CUDNN_VERSION=9.28.1.4
RUN pip install "nvidia-cublas-cu12==${CUBLAS_VERSION}" "nvidia-cudnn-cu12==${CUDNN_VERSION}"
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.13/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.13/site-packages/nvidia/cudnn/lib

COPY remote_faster_whisper.py config.yaml.template /app/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && mkdir -p /config /models && chmod 1777 /models

VOLUME /models
EXPOSE 9876

ENTRYPOINT ["/entrypoint.sh"]
