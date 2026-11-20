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

import av
import logging
import sys
import wave
from configargparse import ArgParser
from flask import Flask, Blueprint, request
from gunicorn.app.base import BaseApplication
from huggingface_hub.errors import LocalEntryNotFoundError
from werkzeug.exceptions import HTTPException
from faster_whisper import WhisperModel
from faster_whisper.utils import download_model
from os.path import exists, isdir
from os import makedirs
from time import time
from yaml import safe_load
import re
import numpy as np

# Log in the same format as Gunicorn's own error log; StreamHandler flushes after every
# record, so log output is never delayed by Python's output buffering
LOG_FORMAT = "%(asctime)s [%(process)d] [%(levelname)s] %(message)s"
LOG_DATEFMT = "[%Y-%m-%d %H:%M:%S %z]"

logger = logging.getLogger("remote_faster_whisper")

# The sample rate Whisper models expect
SAMPLE_RATE = 16000

# The maximum upload size; 20MB is comfortably more than 1 minute of uncompressed
# 48kHz 16-bit stereo audio (11.5MB)
MAX_UPLOAD_SIZE = 20 * 1024 * 1024

# Special transformations, in the order they are applied
SPECIAL_TRANSFORMATIONS = {
    "lower": str.lower,
    "casefold": str.casefold,
    "upper": str.upper,
    "title": str.title,
}


def setup_logging():
    """
    Configure the application logger to log to stderr
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATEFMT))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


class FasterWhisperApi:
    def __init__(
        self,
        base_url="/api/v0",
        faster_whisper_config={},
        transformations=[],
    ):
        """
        Initialize the API and Faster Whisper configuration
        """
        self.app = Flask(__name__)
        self.app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE
        self.blueprint = Blueprint("api", __name__, url_prefix=base_url)

        (
            self.special_transformations,
            self.regex_transformations,
        ) = compile_transformations(transformations)
        self.whisper_model = None

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
            except KeyError:
                return {
                    "message": "Request data did not contain an 'audio_file' in its files"
                }, 400

            audio = decode_audio(f)
            if audio is None:
                return {
                    "message": "The 'audio_file' must contain a valid audio format"
                }, 400
            if len(audio) == 0:
                return {"message": "The 'audio_file' does not contain any audio"}, 400

            if self.save_audio:
                save_dir = f"{self.save_path}/{time()}"
                makedirs(save_dir, exist_ok=True)
                save_wav(f"{save_dir}/audio.wav", audio)

            return self.perform_faster_whisper_recognition(audio)

        self.app.register_blueprint(self.blueprint)

        # Return errors as JSON, like the API's other responses, rather than HTML
        @self.app.errorhandler(HTTPException)
        def handle_http_error(e):
            return {"message": e.description}, e.code

        @self.app.errorhandler(Exception)
        def handle_error(e):
            logger.exception("Error processing request")
            return {"message": f"Internal error: {e}"}, 500

    def download_model(self):
        """
        Find the model files in the cache, downloading them if needed, and return their
        local path

        This is done in the main process before the Gunicorn worker starts, so that a
        slow download cannot exceed the worker timeout.
        """
        if isdir(self.model):
            return self.model

        try:
            model_path = download_model(
                self.model, cache_dir=self.model_cache_dir, local_files_only=True
            )
            logger.info(f"Using cached model '{self.model}' at {model_path}")
        except LocalEntryNotFoundError:
            logger.info(f"Downloading model '{self.model}' into {self.model_cache_dir}")
            model_path = download_model(self.model, cache_dir=self.model_cache_dir)
            logger.info(f"Model '{self.model}' downloaded to {model_path}")
        return model_path

    def load_model(self, model_path):
        """
        Initialize the WhisperModel instance from the local model files

        This must be done in the Gunicorn worker (i.e. after forking), as CUDA cannot be
        initialized before a fork.
        """
        logger.info(
            f"Initializing WhisperModel instance on device '{self.device}' "
            f"(index {self.device_index}) with compute type '{self.compute_type}'"
        )
        self.whisper_model = WhisperModel(
            model_path,
            device=self.device,
            device_index=self.device_index,
            compute_type=self.compute_type,
        )
        logger.info("WhisperModel instance initialized")

        # Run a test transcription of one second of silence. Libraries like cuBLAS and
        # cuDNN are only loaded on first use, so this catches a broken GPU setup now,
        # failing the worker at startup instead of every request; it also means that
        # one-time device setup doesn't delay the first real request.
        t_start = time()
        segments, _ = self.whisper_model.transcribe(
            np.zeros(SAMPLE_RATE, dtype=np.float32),
            beam_size=self.beam_size,
            language=self.language,
            task="translate" if self.translate else "transcribe",
        )
        list(segments)
        logger.info(f"WhisperModel warmed up in {time() - t_start:.2f}s")

    def perform_faster_whisper_recognition(self, audio):
        """
        Perform recognition on {audio} (16kHz mono float32 samples) with model
        """
        logger.info("Performing recognition on audio data")

        t_start = time()
        segments, info = self.whisper_model.transcribe(
            audio,
            beam_size=self.beam_size,
            language=self.language,
            task="translate" if self.translate else "transcribe",
        )

        # Each segment's text already begins with a space where one is needed
        text = "".join(segment.text for segment in segments).strip()

        text = self.apply_transformations(text)

        t_end = time()
        t_run = t_end - t_start

        result = {
            "text": text,
            "language": info.language,
            "language_probability": info.language_probability,
            "sample_duration": info.duration,
            "runtime": t_run,
        }

        logger.info(f"Result: {result}")
        return result

    def apply_transformations(self, text):
        """
        Apply the special transformations, then the regex transformations, to {text}
        """
        for name in self.special_transformations:
            text = SPECIAL_TRANSFORMATIONS[name](text)

        for pattern, replacement in self.regex_transformations:
            new_text, count = pattern.subn(replacement, text)
            if count:
                logger.info(
                    f'Transforming "{pattern.pattern}" -> "{replacement}": '
                    f'pre "{text}", post "{new_text}"'
                )
                text = new_text

        return text


def compile_transformations(transformations):
    """
    Validate and compile the configured {transformations}

    Returns the special transformations to apply (in the order they are applied), and
    a list of (compiled regex, replacement) tuples. Raises ValueError for an invalid
    transformation, so that a bad configuration is caught at startup.
    """
    special = set()
    regexes = []

    for idx, tr in enumerate(transformations or [], start=1):
        if isinstance(tr, str):
            if tr not in SPECIAL_TRANSFORMATIONS:
                raise ValueError(
                    f"transformation {idx}: unknown special transformation '{tr}' "
                    f"(expected one of: {', '.join(SPECIAL_TRANSFORMATIONS)})"
                )
            special.add(tr)
        elif isinstance(tr, list) and len(tr) == 2 and isinstance(tr[0], str):
            try:
                pattern = re.compile(tr[0])
            except re.error as e:
                raise ValueError(f"transformation {idx}: invalid regex '{tr[0]}': {e}")
            replacement = "" if tr[1] is None else str(tr[1])
            regexes.append((pattern, replacement))
        else:
            raise ValueError(
                f"transformation {idx}: expected a special transformation name or a "
                f"[regex, replacement] pair, not {tr!r}"
            )

    # Special transformations are always applied first, in a fixed order
    special = [name for name in SPECIAL_TRANSFORMATIONS if name in special]
    return special, regexes


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


def decode_audio(file):
    """
    Decode an uploaded audio {file} in any format supported by PyAV into the 16kHz
    mono float32 samples that Whisper expects; returns None if it can't be decoded
    """
    try:
        resampler = av.audio.resampler.AudioResampler(
            format="flt", layout="mono", rate=SAMPLE_RATE
        )
        audio_data = []
        with av.open(file.stream) as container:
            audio_stream = next(s for s in container.streams if s.type == "audio")
            for frame in container.decode(audio_stream):
                for resampled_frame in resampler.resample(frame):
                    audio_data.append(resampled_frame.to_ndarray().flatten())
        # Flush any samples still buffered in the resampler
        for resampled_frame in resampler.resample(None):
            audio_data.append(resampled_frame.to_ndarray().flatten())
    except Exception as e:
        logger.warning(f"Error decoding audio: {e}")
        return None

    if not audio_data:
        return np.array([], dtype=np.float32)
    return np.concatenate(audio_data)


def save_wav(path, audio):
    """
    Save {audio} (16kHz mono float32 samples) to {path} as a 16-bit PCM WAV file
    """
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(path, "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(SAMPLE_RATE)
        fh.writeframes(pcm.tobytes())


class GunicornApplication(BaseApplication):
    """
    Run a WSGI application with Gunicorn, using the given options
    """

    def __init__(self, app_loader, options):
        self.app_loader = app_loader
        self.options = options
        super().__init__()

    def load_config(self):
        for key, value in self.options.items():
            self.cfg.set(key, value)

    def load(self):
        return self.app_loader()


def start_api():
    """
    Parse arguments, grab configuration, fetch the model, and start the API
    """
    setup_logging()

    options = parse_args()
    config = parse_config(options.config) or {}
    daemon_config = config.get("daemon") or {}

    try:
        api = FasterWhisperApi(
            base_url=daemon_config.get("base_url", "/api/v0"),
            faster_whisper_config=config.get("faster_whisper") or {},
            transformations=config.get("transformations") or [],
        )
    except ValueError as e:
        logger.error(f"Invalid configuration: {e}")
        sys.exit(1)

    model_path = api.download_model()

    def app_loader():
        api.load_model(model_path)
        return api.app

    listen = daemon_config.get("listen") or "0.0.0.0"
    if ":" in listen and not listen.startswith("["):
        listen = f"[{listen}]"  # IPv6 address
    port = daemon_config.get("port") or 9876

    gunicorn_options = {
        "bind": f"{listen}:{port}",
        # A single worker process, as each worker would need its own copy of the model
        # in (GPU) memory; concurrent requests are instead handled by threads
        "workers": 1,
        "worker_class": "gthread",
        "threads": daemon_config.get("threads") or 4,
        # Must also allow enough time for the worker to load the model at startup
        "timeout": daemon_config.get("timeout") or 120,
        "proc_name": "remote-faster-whisper",
        "accesslog": "-",
        "errorlog": "-",
        "access_log_format": '%(t)s %(h)s "%(r)s" %(s)s %(b)s %(L)ss',
        "control_socket_disable": True,
    }
    # Avoid worker heartbeat stalls on slow (e.g. overlay) filesystems
    if isdir("/dev/shm"):
        gunicorn_options["worker_tmp_dir"] = "/dev/shm"

    logger.info(f"Starting API on {gunicorn_options['bind']}")
    GunicornApplication(app_loader, gunicorn_options).run()


# Main entrypoint
if __name__ == "__main__":
    start_api()
