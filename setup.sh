#!/usr/bin/env bash

# Install or rebuild Remote Faster Whisper in a virtualenv. Re-running this script on an
# existing installation updates the code and dependencies but preserves the existing
# configuration file and model cache.

set -o errexit

if [[ $(whoami) != "root" ]]; then
    echo "This script must be run as root!"
    exit 1
fi

# Run from the repository directory so the relative paths below work from anywhere
cd "$( dirname "$( readlink -f "${BASH_SOURCE[0]}" )" )"

echo -n "Where should remote-faster-whisper be installed? > "
read -r dest_path
if [[ -z ${dest_path} ]]; then
    echo "An installation path is required!"
    exit 1
fi
dest_path="$( realpath -m "${dest_path}" )"

if [[ -f ${dest_path}/config.yaml ]]; then
    echo "Found an existing configuration at ${dest_path}/config.yaml; it will be preserved."
fi

echo -n "Install the CUDA libraries for NVIDIA GPU support? [Y/n] > "
read -r cuda
case ${cuda} in
    n|N|no|No|NO|nO)
        cuda="false"
    ;;
    *)
        cuda="true"
    ;;
esac

echo -n "Install as a service? [Y/n] > "
read -r service
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
    read -r username
    if [[ -z ${username} ]]; then
        user_entry="DynamicUser = yes"
    else
        user_entry="User = ${username}"
    fi
fi

echo "Installing..."

mkdir -p "${dest_path}"

# Creates the virtualenv, or updates it in place (e.g. after a Python upgrade)
virtualenv --python=python3 "${dest_path}"

"${dest_path}/bin/pip" install --upgrade --requirement requirements.txt

lib_path=""
if [[ ${cuda} == "true" ]]; then
    "${dest_path}/bin/pip" install --upgrade --requirement requirements-cuda.txt
    site_packages="$( "${dest_path}/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])' )"
    lib_path="${site_packages}/nvidia/cublas/lib:${site_packages}/nvidia/cudnn/lib"
fi

cp remote_faster_whisper.py "${dest_path}/bin/remote_faster_whisper"

# Only install the example configuration if there isn't one already
if [[ ! -f ${dest_path}/config.yaml ]]; then
    cp config.yaml "${dest_path}/config.yaml"
    new_config="true"
fi

if [[ ${service} == "true" ]]; then
    unit_file=/etc/systemd/system/remote-faster-whisper.service
    unit_tmp="$( mktemp )"
    cat <<EOF >"${unit_tmp}"
[Unit]
Description = Remote Faster Whisper API daemon
After = network-online.target

[Service]
Type = simple
${user_entry}
WorkingDirectory = ${dest_path}
Restart = on-abort
Environment = LD_LIBRARY_PATH=${lib_path}
Environment = PYTHONUNBUFFERED=true
Environment = RFW_CONFIG_FILE=${dest_path}/config.yaml
ExecStart = ${dest_path}/bin/python ${dest_path}/bin/remote_faster_whisper

[Install]
WantedBy = multi-user.target
EOF
    # Back up an existing unit file if this would change it
    if [[ -f ${unit_file} ]] && ! cmp -s "${unit_tmp}" "${unit_file}"; then
        backup="${unit_file}.bak-$( date +%Y%m%d%H%M%S )"
        echo "Existing unit file differs; backing it up to ${backup}"
        cp "${unit_file}" "${backup}"
    fi
    install -m 0644 "${unit_tmp}" "${unit_file}"
    rm -f "${unit_tmp}"
    systemctl daemon-reload
fi

if [[ ${new_config} == "true" ]]; then
    edit_prompt="[Y/n]"
else
    edit_prompt="[y/N]"
fi
echo -n "Edit configuration file now? ${edit_prompt} > "
read -r editconf
if [[ -z ${editconf} ]]; then
    [[ ${new_config} == "true" ]] && editconf="y" || editconf="n"
fi
case ${editconf} in
    y|Y|yes|Yes|YES)
        ${EDITOR:-vi} "${dest_path}/config.yaml"
    ;;
esac

if [[ ${service} == "true" ]]; then
    echo -n "Enable and (re)start remote-faster-whisper.service now? [Y/n] > "
    read -r startsvc
    case ${startsvc} in
        n|N|no|No|NO|nO)
            true
        ;;
        *)
            systemctl enable remote-faster-whisper.service
            systemctl restart remote-faster-whisper.service
            sleep 3
            systemctl status --no-pager remote-faster-whisper.service
        ;;
    esac
fi
