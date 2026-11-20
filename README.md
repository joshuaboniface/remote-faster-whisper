# Remote Faster Whisper API

<p align="center">
<a href="https://github.com/joshuaboniface/remote-faster-whisper"><img alt="License" src="https://img.shields.io/github/license/joshuaboniface/remote-faster-whisper"/></a>
<a href="https://github.com/psf/black"><img alt="Code style: Black" src="https://img.shields.io/badge/code%20style-black-000000.svg"/></a>
<a href="https://github.com/joshuaboniface/remote-faster-whisper/releases"><img alt="Release" src="https://img.shields.io/github/release-pre/joshuaboniface/remote-faster-whisper"/></a>
</p>

Remote Faster Whisper is a basic API designed to perform transcriptions of audio data with [Faster Whisper](https://github.com/guillaumekln/faster-whisper) over the network.

We have two main reference consumers: [Kalliope](https://github.com/kalliope-project/kalliope) and [HomeAssistant](https://github.com/home-assistant]) via my [Custom RFW Integration](https://github.com/joshuaboniface/HASS-RemoteFasterWhisper).

Normally, Kalliope would run on a low-power, low-cost device such as a Raspberry Pi. While Faster Whisper can run on such a device, it can take a prohibitively long time to process the speech into text, especially on older or non-overclocked devices or when requiring better than `tiny` accuracy. Remote Faster Whisper exists to offload this processing onto a much faster machine, ideally one with a CUDA-supporting GPU, to more quickly transcribe the audio and return it in a reasonable time. This can also enable a small collection of such devices to use a single central transcription server to avoid using a lot of power individually, while still keeping the STT self-hosted on-network. An example STT plugin for Kalliope is provided in [the Kalliope folder](/kalliope).

For HomeAssistant, RFW provides some additional functionality that the integrated Whisper component lacks, for instance off-machine GPU offloading, custom substitutions, and the ability to add it multiple times with unique prefixes. See the aforementioned integration for more details.

## Installation

You can run Remote Faster Whisper in two ways: via Docker, or via a direct installation with `setup.sh` and Systemd. For production use alongside e.g. Home Assistant, we recommend Docker.

### Docker

A Docker image is published to the GitHub Container Registry as `ghcr.io/joshuaboniface/remote-faster-whisper`, built from the [`Dockerfile`](/Dockerfile) on every push to `master` (tagged `latest`) and on every `v*` release tag. It includes the CUDA 12 cuBLAS and cuDNN 9 libraries needed for GPU support, so only the NVIDIA driver and [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) are needed on the host.

An example [`docker-compose.yaml`](/docker-compose.yaml) is provided. Copy it and `config.yaml` to a directory on the host, edit `config.yaml` as desired, and then run `docker compose up -d`. The example `config.yaml` defaults are suitable for Docker: it listens on `0.0.0.0` inside the container (choose the host address and port in the compose `ports:` mapping instead), and caches models in the `/models` volume, mapped to the `./models` directory. The configuration is mounted at `/config/config.yaml` in the container. For CPU-only operation, remove the `deploy:` section from the compose file.

Alternatively, if no configuration file is mounted, a basic one (without `transformations`) is generated from the following environment variables, shown with their defaults: `LISTEN` (`0.0.0.0`), `PORT` (`9876`), `BASE_URL` (`/api/v0`), `THREADS` (`4`), `TIMEOUT` (`120`), `MODEL_CACHE_DIR` (`/models`), `MODEL` (`small`), `DEVICE` (`auto`), `DEVICE_INDEX` (`0`), `COMPUTE_TYPE` (`int8`), `BEAM_SIZE` (`5`), `TRANSLATE` (`yes`), and `LANGUAGE` (empty, i.e. auto-detect).

To build the image locally instead, run `docker build -t remote-faster-whisper .` in this repository.

### Direct Installation

Clone this repository to your system and run `setup.sh` as root (e.g. `sudo ./setup.sh`). You will be prompted for several configuration details, including the path to install it to, whether to install the CUDA libraries for NVIDIA GPU support, whether to install a service unit for it or not, and what user to run it as (for service deploys only). It will then install Remote Faster Whisper and the dependencies from `requirements.txt` (and, if chosen, `requirements-cuda.txt`) inside a virtualenv in the specified path, (if chosen) install the systemd unit file into `/etc/systemd/system`, and then finally prompt you to edit the configuration file and start/enable the service. You can also perform these steps manually if you so choose.

`setup.sh` can be re-run on an existing installation to update or rebuild it, for instance after updating this repository or upgrading the system Python. An existing `config.yaml` is always preserved, and an existing systemd unit file is backed up if it would be changed.

## Usage

Once running, you can HTTP `POST` binary WAV audio file data to the `/api/v0/transcribe` endpoint, and receive a JSON response of the transcription text and details. A simple test client is provided as `send.py` to validate a running instance with a local `wav` file.

**Note**: You **must** `POST` the audio data as `files` with the name `audio_file` as shown in the [test client](/send.py#L28) or the [Kalliope STT example](/kalliope/remote_fasterwhisper/remote_fasterwhisper.py#L35), and the data **must** be valid PCM WAV data (not FLAC, mp3, or any other formats).

The JSON response will look something like:

```
{'language': 'en', 'language_probability': 0.9578803181648254, 'runtime': 0.30777573585510254, 'sample_duration': 1.7763125, 'text': 'Hello world'}
```

Remote Faster Whisper is currently very sparse. It is not a real Python module or package, and it uses the `faster_whisper` library directly (rather than a wrapper such as `SpeechRecognition`). These deficiencies may change in the future, and contributions are welcome.

## Configuration Options

The configuration file `config.yaml` is divided into three main sections: `daemon:` controls the API daemon itself; `faster_whisper:` controls the Faster Whisper transcription library; and `transformations:` which define transformations to make on the output text.

#### `daemon` -> `listen`

The IP address to listen on. Use `0.0.0.0` to listen on all interfaces.

#### `daemon` -> `port`

The port to listen on. We default to `9876` but this can be changed as desired to any high (>1024) port number.

#### `daemon` -> `base_url`

The base URL for the API. This defaults to `/api/v0` but this can be changed to anything or an empty value if desired.

#### `daemon` -> `threads`

The number of threads used to handle requests concurrently. Defaults to `4`.

The API is served by [Gunicorn](https://gunicorn.org/) with a single worker process, since each worker process would need its own copy of the model in (GPU) memory; concurrent requests are instead handled by these threads, sharing the one model instance.

#### `daemon` -> `timeout`

The Gunicorn worker timeout, in seconds. Defaults to `120`. This must also be long enough for the worker to load the model at startup, so you may need to increase it for very large models or slow storage.

#### `faster_whisper` -> `model_cache_dir`

The directory to cache Faster Whisper models. In Docker, this should be the `/models` volume (the default in the example `config.yaml`); for direct installations, `setup.sh` sets it to a `models` directory in the installation path when installing a new configuration.

Remote Faster Whisper will download the `model` below into this directory at startup if it is not already cached; this may take some time with slow network connections. This is done at startup, before the API starts accepting requests, rather than during the first transcription to improve the user experience.

**Note**: When using a service install with a dynamic user (the default if no user is specified), this option **must** be set to a temporary directory (under `/tmp` or `/var/tmp`), and note that the model will be cached to an ephemeral directory valid only for the time the service is active. Thus the model will be re-downloaded each time the daemon starts. To avoid this, use a real user for the daemon, or use a pre-configured cache containing the model you wish to use outside of these temporary paths.

#### `faster_whisper` -> `model`

The model to use for transcribing. Can be [any valid model that Faster Whisper supports](https://github.com/guillaumekln/faster-whisper/blob/master/faster_whisper/transcribe.py#L90).

#### `faster_whisper` -> `device`

The device to use for transcription processing. Can be one of `auto`, `cpu`, or `cuda`. Note that CUDA requires [nVidia libraries to operate correctly](https://github.com/guillaumekln/faster-whisper#gpu-support); these are installed from `requirements-cuda.txt` by `setup.sh` (if chosen) and are included in the Docker image.

#### `faster_whisper` -> `device_index`

The device index to use. Mostly relevant for `cuda` device support, to specify the GPU to use.

#### `faster_whisper` -> `compute_type`

The compute type to use; see [the CTranslate2 documentation](https://opennmt.net/CTranslate2/quantization.html) for details.

#### `faster_whisper` -> `beam_size`

The beam size for the transcriber to use. You should not ever need to change this unless you know why you need to.

#### `faster_whisper` -> `translate`

Whether or not to attempt translation on the incoming data to `language` (below). If false, the given language is always assumed. Leave as `no` if you plan to use a `.en` model.

#### `faster_whisper` -> `language`

The language to use, as a lowercase ISO language code (e.g. `en`, `fr`, `zh`, etc.). Leave empty (or remove) for automatic language selection.

#### `transformations`

This section is a list of tuple-lists, where the first element is a `re.sub` matching regex, and the second element is the replacement; e.g.

   ```yaml
   transformations:
     - ["(bunny|hare)", "rabbit"]
     - ["[Cc]ute", "fancy"]
   ```

After transcribing text with Faster Whisper, the text is run through these transformations in order, replacing the regex, if found in the text, with the corresponding string. Transformations build on each other, so a later transformation can alter the result of an earlier one.

For example, with the above transformations, speaking either "the cute bunny" or "The Cute hare" will actually return "the fancy rabbit".

This is a contrived example; the real reason to use transformations is to "fix up" common mishearings or misunderstandings in your environment.

As a more concrete example, you may say the phrase "lights on", but in your voice this is parsed as "light is on" or "light's on". **As long as** you don't expect "is on" to mean anything to your consumer, you could use a transformation here to force the "right" text, like:

   ```yaml
   transformations:
     - ["light is on", "lights on"]
   ```

This will ensure that the consumer gets something it expects even if the Whisper models don't quite understand you.

You could also generalize this a bit more and leverage the whitespace to your advantage:

   ```yaml
   transformations:
     - [" is on", "s on"]
   ```

This would replace both "light is on" with "lights on" as well as "speaker is on" with "speakers on", if both are common mishearings.

There are also 4 special transformations that can be used. These should be entered as simple list entries rather than a tuple-list.

* `lower` will convert the entire string to lowercase with `str.lower()`.

* `casefold` will convert the entire string to full lowercase with `str.casefold()`.

* `upper` will convert the entire string to uppercase with `str.upper()`.

* `title` will convert the entire string to title-case with `str.title()`.

**Note:** These special transformations are always applied **first**, before any other transformations, in the order given above. Using multiple special transformations is likely not very useful, but be mindful of this if you do.

Thus a full transformations example might look like:

   ```yaml
   transformations:
     - lower
     - ["[\\.,!?]", ""]  # Note the double-backslash for a literal '.'
     - [" is on", "s on"]
     - ["(keeter|peter)", "heater"]
   ```

This will ensure a fully-lowercase result, with no (common) punctuation, " is on" replaced by "s on", and "keeter" replaced with "heater"; hence speaking something that is transcribed as "Keeter is on." will return "heaters on".

**Note:** You should use this feature sparingly. A large number of transformations might slow down your transcription time considerably, and you must be mindful of the implications each transformation will have on all possible texts that are parsed. They work best with only a few common mishearings and when using relatively short text strings, for example in a voice command system.

**Note:** Regexes in the first field are normal strings, i.e. they are not treated as raw strings. Be mindful of complex regexes.
