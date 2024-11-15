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
from io import BytesIO
from os.path import exists
from os import makedirs
from time import time
from yaml import safe_load
from speech_recognition import Recognizer, AudioFile
from numpy import float32
from soundfile import read as sf_read
from re import sub, search


class FasterWhisperApi:
    def __init__(
        self,
        listen="127.0.0.1",
        port=9876,
        base_url="/api/v0",
        faster_whisper_config={},
        transformations={},
    ):
        """
        Initialize the API and Faster Whisper configuration
        """
        self.app = Flask(__name__)
        self.blueprint = Blueprint("api", __name__, url_prefix=base_url)

        self.listen = listen
        self.port = port

        self.transformations = transformations

        self.model_cache_dir = faster_whisper_config.get(
            "model_cache_dir", "/tmp/whisper-cache"
        )
        self.model = faster_whisper_config.get("model", "base")
        self.device = faster_whisper_config.get("device", "auto")
        self.device_index = faster_whisper_config.get("device_index", 0)
        self.compute_type = faster_whisper_config.get("compute_type", "int8")
        self.beam_size = faster_whisper_config.get("beam_size", 5)
        self.translate = faster_whisper_config.get("translate", False)
        self.language = faster_whisper_config.get("language", None)
        if not self.language:
            self.language = None

        self.save_audio = faster_whisper_config.get("debug", {}).get("save_audio")
        if self.save_audio:
            self.save_path = faster_whisper_config.get("debug", {}).get("save_path")

        if self.save_audio:
            if not exists(self.save_path):
                makedirs(self.save_path)

        @self.blueprint.route("/transcribe", methods=["POST"])
        def transcribe():
            try:
                f = request.files["audio_file"]
            except Exception:
                return {
                    "message": "Request data did not contain an 'audio_file' in its files"
                }, 400

            try:
                rec = Recognizer()
                with AudioFile(f) as source:
                    audio = rec.record(source)

                assert isinstance(audio, AudioData)
                data = audio.get_wav_data(convert_rate=16000)
                if self.save_audio:
                    runtime = time()
                    makedirs(f"{self.save_path}/{runtime}")
                    with open(f"{self.save_path}/{runtime}/audio.wav", "wb") as fh:
                        fh.write(data)

            except Exception:
                return {
                    "message": "The 'audio_file' must contain valid WAV audio data"
                }, 400

            return self.perform_faster_whisper_recognition(audio)

        self.app.register_blueprint(self.blueprint)

    def start(self):
        """
        Initialize the WhisperModel (including downloading the model files) and start the API
        """
        print("Initializing WhisperModel instance")
        self.whisper_model = WhisperModel(
            self.model,
            device=self.device,
            device_index=self.device_index,
            compute_type=self.compute_type,
            download_root=self.model_cache_dir,
        )

        print("Starting API")
        self.app.run(debug=False, host=self.listen, port=self.port)

    def perform_faster_whisper_recognition(self, audio_data):
        """
        Perform recognition on {audio_data} with model
        """
        print("Performing recognition on audio data")

        t_start = time()
        wav_bytes = audio_data.get_wav_data(convert_rate=16000)
        wav_stream = BytesIO(wav_bytes)
        audio_array, sampling_rate = sf_read(wav_stream)
        audio_array = audio_array.astype(float32)

        segments, info = self.whisper_model.transcribe(
            audio_array,
            beam_size=self.beam_size,
            language=self.language,
            task="translate" if self.translate else "transcribe",
        )

        found_text = list()
        for segment in segments:
            found_text.append(segment.text)
        text = " ".join(found_text).strip()

        # Perform transformations on text
        if 'lower' in self.transformations:
            text = text.lower()
        if 'casefold' in self.transformations:
            text = text.casefold()
        if 'upper' in self.transformations:
            text = text.upper()
        if 'title' in self.transformations:
            text = text.title()
        for tr in self.transformations:
            if not isinstance(tr, list):
                continue
            if search(tr[0], text):
                _text = text
                text = sub(tr[0], tr[1], text)
                print(f'Transforming "{tr[0]}" -> "{tr[1]}": pre "{_text}", post "{text}"')

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
    """
    Parse CLI arguments/environment variables (configuration file path)
    """
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
    """
    Parse YAML configuration into {config} dictionary
    """
    with open(configfile, "r") as fh:
        config = safe_load(fh)

    return config


def start_api():
    """
    Parse arguments, grab configuration, and initialize and start the API
    """
    options = parse_args()
    config = parse_config(options.config)
    api = FasterWhisperApi(
        **config["daemon"],
        faster_whisper_config=config["faster_whisper"],
        transformations=config.get("transformations", {}),
    )
    api.start()


# Main entrypoint
if __name__ == "__main__":
    start_api()
