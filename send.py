#!/usr/bin/env python3

# Remote Faster Whisper Example Client
# Sends a WAV file (first CLI argument) to the Remote Faster Whisper instance
# on http://localhost:9876 for testing purposes
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

from sys import argv
import requests

filename = argv[1]

files = {"audio_file": open(filename, "rb")}

r = requests.post("http://localhost:9876/api/v0/transcribe", files=files)
print(f"{r.status_code}: {r.json()}")
