
import speech_recognition as sr

from kalliope.core import Utils
from kalliope.stt.Utils import SpeechRecognition

from requests import post


class Remote_fasterwhisper(SpeechRecognition):

    def __init__(self, callback=None, **kwargs):
        """
        Start recording the microphone and analyse audio with Remote Faster Whisper API
        :param callback: The callback function to call to send the text
        :param kwargs:
        """
        # give the audio file path to process directly to the mother class if exist
        SpeechRecognition.__init__(self, kwargs.get('audio_file_path', None))

        # callback function to call after the translation speech/tex
        self.main_controller_callback = callback
        self.uri = kwargs.get('uri', None)

        # set the callback that will process the audio stream
        self.set_callback(self.remote_fasterwhisper_callback)
        # start processing, record a sample from the microphone if no audio file path provided, else read the file
        self.start_processing()

    def remote_fasterwhisper_callback(self, recognizer, audio):
        """
        called from the background thread
        """
        try:
            files = {'audio_file': audio.get_wav_data()}
            resp = post(self.uri, files=files)
            json = resp.json()
            if resp.status_code != 200:
                raise ValueError(f"API returned status code {resp.status_code}: {json.get('message')}")

            # Here we manually lowercase the response and remove common punctuation to make parsing by
            # Kalliope neurons more sensible.
            # THIS IS NOT ROBUST! You should consider better solutions to fit your specific needs here,
            # and contributions are welcome!
            text = json.get("text").lower()
            text = text.replace(',', '')
            text = text.replace('.', '')
            text = text.replace('!', '')
            text = text.replace('?', '')

            captured_audio = text
            language = json.get("language")
            language_probability = json.get("language_probability")
            sample_duration = json.get("sample_duration")
            runtime = json.get("runtime")

            Utils.print_success("Remote Faster Whisper Speech Recognition thinks you said '%s' in language '%s' (probability %s, sample duration %ss, processing time %ss" % (captured_audio, language, language_probability, sample_duration, runtime))
            self._analyse_audio(audio_to_text=captured_audio)
        except sr.RequestError as e:
            Utils.print_danger("Could not request results from Remote Faster Whisper Speech Recognition service; {0}".format(e))
            # callback anyway, we need to listen again for a new order
            self._analyse_audio(audio_to_text=None)
        except AssertionError:
            Utils.print_warning("No audio caught from microphone")
            self._analyse_audio(audio_to_text=None)
        except Exception as e:
            Utils.print_warning("Remote Faster Whisper Speech Recognition encountered an error: {}".format(e))
            # callback anyway, we need to listen again for a new order
            self._analyse_audio(audio_to_text=None)

    def _analyse_audio(self, audio_to_text):
        """
        Confirm the audio exists and run it in a Callback
        :param audio_to_text: the captured audio
        """
        if self.main_controller_callback is not None:
            self.main_controller_callback(audio_to_text)
