#!/usr/bin/env python3

# Remote Faster Whisper
# An API interface for Faster Whisper to parse audio over HTTP
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

from configargparse import ArgParser
from flask import Flask, Blueprint, request
from speech_recognition.audio import AudioData
from faster_whisper import WhisperModel
from faster_whisper.utils import download_model
from io import BytesIO
from time import time
from os.path import isdir
from os import makedirs
from yaml import safe_load
from speech_recognition import Recognizer, AudioFile
from numpy import float32
from soundfile import read as sf_read


class FasterWhisperApi:
    def __init__(
        self,
        listen="127.0.0.1",
        port=9876,
        base_url="/api/v0",
        faster_whisper_config={},
    ):
        self.app = Flask(__name__)
        self.blueprint = Blueprint("api", __name__, url_prefix=base_url)

        self.listen = listen
        self.port = port

        self.faster_whisper_config = faster_whisper_config

        @self.blueprint.route("/transcribe", methods=["POST"])
        def transcribe():
            f = request.files["file"]
            rec = Recognizer()
            with AudioFile(f) as source:
                audio = rec.record(source)

            assert isinstance(audio, AudioData), "Data must be audio data"
            return self.perform_faster_whisper_recognition(audio)

        self.app.register_blueprint(self.blueprint)

    def start(self):
        self.model_cache_dir = self.faster_whisper_config.get("model_cache_dir", "/tmp/whisper-cache")
        self.model = self.faster_whisper_config.get("model", "base")
        self.device = self.faster_whisper_config.get("device", "auto")
        self.device_index = self.faster_whisper_config.get("device_index", 0)
        self.compute_type = self.faster_whisper_config.get("compute_type", "int8")
        self.beam_size = self.faster_whisper_config.get("beam_size", 5)
        self.translate = self.faster_whisper_config.get("translate", False)
        self.language = self.faster_whisper_config.get("language", None)
        if not self.language:
            self.language = None

        if not isdir(self.model_cache_dir):
            print(f"Downloading model {self.model} to {self.model_cache_dir}")
            makedirs(self.model_cache_dir)
            download_model(
                self.model,
                local_files_only=False,
                cache_dir=self.model_cache_dir,
            )
        self.app.run(debug=True, host=self.listen, port=self.port)

    def perform_faster_whisper_recognition(self, audio_data):

        print("Performing recognition on audio data")

        t_start = time()
        whisper_model = WhisperModel(
            self.model,
            device=self.device,
            device_index=self.device_index,
            compute_type=self.compute_type,
            download_root=self.model_cache_dir,
        )

        wav_bytes = audio_data.get_wav_data(convert_rate=16000)
        wav_stream = BytesIO(wav_bytes)
        audio_array, sampling_rate = sf_read(wav_stream)
        audio_array = audio_array.astype(float32)

        segments, info = whisper_model.transcribe(
            audio_array,
            beam_size=self.beam_size,
            language=self.language,
            task="translate" if self.translate else "transcribe",
        )

        found_text = list()
        for segment in segments:
            found_text.append(segment.text)
        text = " ".join(found_text).strip()

        t_end = time()
        t_run = t_end - t_start

        result = {
            "text": text,
            "language": info.language,
            "language_probability": info.language_probability,
            "sample_duration": info.duration,
            "runtime": t_run,
        }

        print(f"Result: {result}")

        return result


def parse_args():
    p = ArgParser()
    p.add(
        "-c",
        "--config",
        env_var="RFW_CONFIG_FILE",
        help="Configuration file path",
        required=True,
    )
    options = p.parse_args()
    return options


def parse_config(configfile):
    with open(configfile, "r") as fh:
        config = safe_load(fh)

    return config


def start_api():
    options = parse_args()
    config = parse_config(options.config)
    api = FasterWhisperApi(
        **config["daemon"], faster_whisper_config=config["faster_whisper"]
    )
    api.start()


if __name__ == "__main__":
    start_api()
