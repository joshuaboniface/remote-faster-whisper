FROM nvidia/cuda:12.9.1-cudnn-runtime-ubuntu22.04

RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    ln -sf /usr/bin/python3 /usr/bin/python && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

COPY entrypoint.sh /entrypoint.sh
COPY config.yaml.template /app/config.yaml.template

RUN chmod +x /entrypoint.sh

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

EXPOSE 9876

ENTRYPOINT ["/entrypoint.sh"]
