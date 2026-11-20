#!/usr/bin/env bash
set -e

# Use a full configuration file if one is mounted (required for transformations);
# otherwise, generate a basic configuration from environment variables.
CONFIG_FILE="${RFW_CONFIG_FILE:-/config/config.yaml}"

if [[ ! -f ${CONFIG_FILE} ]]; then
    echo "No configuration file found at ${CONFIG_FILE}; generating one from environment variables"

    export LISTEN=${LISTEN:-0.0.0.0}
    export PORT=${PORT:-9876}
    export BASE_URL=${BASE_URL:-/api/v0}
    export THREADS=${THREADS:-4}
    export TIMEOUT=${TIMEOUT:-120}
    export MODEL_CACHE_DIR=${MODEL_CACHE_DIR:-/models}
    export MODEL=${MODEL:-small}
    export DEVICE=${DEVICE:-auto}
    export DEVICE_INDEX=${DEVICE_INDEX:-0}
    export COMPUTE_TYPE=${COMPUTE_TYPE:-int8}
    export BEAM_SIZE=${BEAM_SIZE:-5}
    export TRANSLATE=${TRANSLATE:-yes}
    export LANGUAGE=${LANGUAGE:-}

    CONFIG_FILE=/tmp/config.yaml
    envsubst < /app/config.yaml.template > "${CONFIG_FILE}"
fi

exec python /app/remote_faster_whisper.py -c "${CONFIG_FILE}"
