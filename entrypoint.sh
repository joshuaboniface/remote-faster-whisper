#!/usr/bin/env bash
set -e

export LISTEN=${LISTEN:-0.0.0.0}
export PORT=${PORT:-9876}
export BASE_URL=${BASE_URL:-/api/v0}
export MODEL=${MODEL:-small}
export DEVICE=${DEVICE:-cuda}
export DEVICE_INDEX=${DEVICE_INDEX:-0}
export COMPUTE_TYPE=${COMPUTE_TYPE:-int8}
export BEAM_SIZE=${BEAM_SIZE:-5}
export TRANSLATE=${TRANSLATE:-yes}
export LANGUAGE=${LANGUAGE:-}

envsubst < /app/config.yaml.template > /app/config.yaml

exec python /app/remote_faster_whisper.py -c /app/config.yaml
