#!/usr/bin/env bash
set -e

envsubst < /app/config.yaml.template > /app/config.yaml

exec python /app/remote_faster_whisper.py -c /app/config.yaml
