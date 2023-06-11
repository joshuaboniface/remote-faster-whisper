# Remote Faster Whisper API

<p align="center">
<a href="https://github.com/joshuaboniface/remote-faster-whisper"><img alt="License" src="https://img.shields.io/github/license/joshuaboniface/remote-faster-whisper"/></a>
<a href="https://github.com/psf/black"><img alt="Code style: Black" src="https://img.shields.io/badge/code%20style-black-000000.svg"/></a>
<a href="https://github.com/joshuaboniface/remote-faster-whisper/releases"><img alt="Release" src="https://img.shields.io/github/release-pre/joshuaboniface/remote-faster-whisper"/></a>
</p>

Remote Faster Whisper is a basic API designed to perform transcriptions of audio data with [Faster Whisper](https://github.com/guillaumekln/faster-whisper) over the network.

Our reference consumer is [Kalliope](https://github.com/kalliope-project/kalliope), a Python virtual assistant tool. Normally, Kalliope would run on a low-power, low-cost device such as a Raspberry Pi. While Faster Whisper can run on such a device, it can take a prohibitively long time to process the speech into text, especially on older or non-overclocked devices or when requiring better than `tiny` accuracy. Remote Faster Whisper exists to offload this processing onto a much faster machine, ideally one with a CUDA-supporting GPU, to more quickly transcribe the audio and return it in a reasonable time. This can also enable a small collection of such devices to use a single central transcription server to avoid using a lot of power individually, while still keeping the STT self-hosted on-network. An example STT plugin for Kalliope is provided in [the Kalliope folder](/kalliope).

## Installation & Usage

To install Remote Faster Whisper, clone this repository to your system and run `setup.sh` as root (e.g. `sudo ./setup.sh`). You will be prompted for several configuration details, including the path to install it to, whether to install a service unit for it or not, and what user to run it as (for service deploys only). It will then install Remote Faster Whisper inside a virtualenv in the specified path, (if chosen) install the systemd unit file into `/etc/systemd/system`, and then finally prompt you to edit the configuration file and start/enable the service.

Once running, you can HTTP `POST` binary audio file data (as `files` only!) to the `/api/v0/transcribe` endpoint, and receive a JSON response of the transcription text and details. For example using the `requests` library:

```
import requests

filename = "hello_world.wav"

files = {'file': open(filename, 'rb')}
resp = requests.post("http://localhost:9876/api/v0/transcribe", files=files)
print(resp.json())
```

The response will look something like:

```
{'language': 'en', 'language_probability': 0.9578803181648254, 'runtime': 0.30777573585510254, 'sample_duration': 1.7763125, 'text': 'Hello world'}
```

Remote Faster Whisper is currently very sparse. It is not a real Python module or package, it runs as a Flask development server, and it uses the `faster_whisper` library directly (rather than a wrapper such as `SpeechRecognition`). These deficiencies may change in the future; contributions welcome.

## Configuration Options

The configuration file `config.yaml` is divided into two main sections: `daemon:` controls the Flask API daemon itself, and `faster_whisper:` controls the Faster Whisper transcription library. The following options can be adjusted:

#### `daemon` -> `listen`

The IP address to listen on. Use `0.0.0.0` to listen on all interfaces.

#### `daemon` -> `port`

The port to listen on. We default to `9876` but this can be changed as desired to any high (>1024) port number.

#### `daemon` -> `base_url`

The base URL for the API. This defaults to `/api/v0` but this can be changed to anything or an empty value if desired.

#### `faster_whisper` -> `model_cache_dir`

The directory to cache Faster Whisper models. We recommend a RAM disk (`tmpfs`) for this to improve performance, though any path can be used.

Remote Faster Whisper will attempt to download the `model` below at startup if this path is not found; this may take some time with slow network connections. This is done at startup, rather than during the first transcription to improve the user experience. If the directory exists but the model is missing, it will be downloaded when the first transcription occurrs.

**Note**: When using a service install with a dynamic user (the default if no user is specified), this option **must** be set to a temporary directory (under `/tmp` or `/var/tmp`), and note that the model will be cached to an ephemeral directory valid only for the time the service is active. Thus the model will be redownloaded each time the daemon starts. To avoid this, use a real user for the daemon, or use a pre-configured cache containing the model you wish to use outside of these temporary paths.

#### `faster_whisper` -> `model`

The model to use for transcribing. Can be [any valid model that Faster Whisper supports](https://github.com/guillaumekln/faster-whisper/blob/master/faster_whisper/transcribe.py#L90).

#### `faster_whisper` -> `device`

The device to use for transcription processing. Can be one of `auto`, `cpu`, or `cuda`. Note that CUDA requires [nVidia libraries to operate correctly](https://github.com/guillaumekln/faster-whisper#gpu-support); these should be installed by `torch` on supported systems by default.

#### `faster_whisper` -> `device_id`

The device ID to use. Mostly relevant for `cuda` device support, to specify the GPU to use.

#### `faster_whisper` -> `compute_type`

The compute type to use; see [the CTranslate2 documentation](https://opennmt.net/CTranslate2/quantization.html) for details.

#### `faster_whisper` -> `beam_size`

The beam size for the transcriber to use. You should not ever need to change this unless you know why you need to.

#### `faster_whisper` -> `translate`

Whether or not to attempt translation on the incoming data to `language` (below). If false, the given language is always assumed. Leave as `no` if you plan to use a `.en` model.

#### `faster_whisper` -> `language`

The language to use, as a lowercase ISO language code (e.g. `en`, `fr`, `zh`, etc.). Leave empty (or remove) for automatic language selection.
