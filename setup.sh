#!/usr/bin/env bash

set -o errexit

if [[ $(whoami) != "root" ]]; then
    echo "This script must be run as root!"
    exit 1
fi

echo -n "Where should remote-faster-whisper be installed? > "
read dest_path

echo -n "Install as a service? [Y/n] > "
read service
case ${service} in
    n|N|no|No|NO|nO)
        service="false"
    ;;
    *)
        service="true"
    ;;
esac

if [[ ${service} == "true" ]]; then
    echo -n "Which user should remote-faster-whisper run as? User must exist if specified! [dynamic user] > "
    read username
    if [[ -z ${username} ]]; then
        user_entry="DynamicUser = yes"
    else
        user_entry="User = ${username}"
    fi
fi

echo "Installing..."

if ! test -d ${dest_path}; then
    mkdir -p ${dest_path}
fi

virtualenv --python=python3 ${dest_path}

${dest_path}/bin/pip install --requirement requirements.txt

cp remote_faster_whisper.py ${dest_path}/bin/remote_faster_whisper
cp config.yaml ${dest_path}/config.yaml

lib_path="$( dirname $( find ${dest_path}/lib -type f -name "libcudnn_ops_infer.so*" | head -1 ) )"

if [[ ${service} == "true" ]]; then
    cat <<EOF >/etc/systemd/system/remote-faster-whisper.service
[Unit]
Description = Remote Faster Whisper API daemon
After = network-online.target

[Service]
Type = simple
${user_entry}
WorkingDirectory = ${dest_path}
Restart = on-abort
Environment = LD_LIBRARY_PATH=${lib_path}:\$LD_LIBRARY_PATH
Environment = PYTHONUNBUFFERED=true
Environment = RFW_CONFIG_FILE=${dest_path}/config.yaml
ExecStart = ${dest_path}/bin/python ${dest_path}/bin/remote_faster_whisper

[Install]
WantedBy = multi-user.target
EOF
    systemctl daemon-reload
fi

cat <<EOF >${dest_path}/config.yaml
---
daemon:
  listen: 0.0.0.0
  port: 9876
  base_url: "/api/v0"

faster_whisper:
  model_cache_dir: /tmp/whisper-cache
  model: small
  device: cuda
  device_id: 1
  compute_type: int8
  beam_size: 5
  translate: yes
  language:
EOF

echo -n "Edit configuration file now? [Y/n] > "
read editconf
case ${editconf} in
    n|N|no|No|NO|nO)
        true
    ;;
    *)
        $EDITOR ${dest_path}/config.yaml
    ;;
esac
if [[ ${service} == "true" ]]; then
    echo -n "Enable and start remote-faster-whisper.service now? [Y/n] > "
    read startsvc
    case ${startsvc} in
        n|N|no|No|NO|nO)
            true
        ;;
        *)
            systemctl enable --now remote-faster-whisper.service
            sleep 3
            systemctl status --no-pager remote-faster-whisper.service
        ;;
    esac
fi
