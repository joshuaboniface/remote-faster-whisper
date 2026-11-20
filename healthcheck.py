#!/usr/bin/env python3

# Remote Faster Whisper Docker health check
# Queries the API's health endpoint, using the address from the configuration
#
#    Copyright (C) 2023 Joshua M. Boniface <joshua@boniface.me>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
###############################################################################

from os import environ
from os.path import isfile
from sys import exit
from urllib.request import urlopen
from yaml import safe_load

config_file = environ.get("RFW_CONFIG_FILE", "/config/config.yaml")
if not isfile(config_file):
    # Generated from environment variables by entrypoint.sh
    config_file = "/tmp/config.yaml"

with open(config_file, "r") as fh:
    daemon_config = (safe_load(fh) or {}).get("daemon") or {}

listen = daemon_config.get("listen") or "0.0.0.0"
if listen in ["0.0.0.0", "::"]:
    listen = "127.0.0.1"
elif ":" in listen and not listen.startswith("["):
    listen = f"[{listen}]"  # IPv6 address
port = daemon_config.get("port") or 9876
base_url = daemon_config.get("base_url", "/api/v0") or ""

try:
    with urlopen(f"http://{listen}:{port}{base_url}/health", timeout=5) as response:
        exit(0 if response.status == 200 else 1)
except Exception as e:
    print(f"Health check failed: {e}")
    exit(1)
