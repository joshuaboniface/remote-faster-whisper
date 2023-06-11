# Remote Faster Whisper API Kalliope STT plugin

Install the `remote_fasterwhisper` directory into the `stt` folder of your Kalliope instance, then configure it in `settings.yml` like so:

```
default_speech_to_text: "remote_fasterwhisper"
speech_to_text:                                            
  - remote_fasterwhisper:                                  
      uri: http://<myhost>:9876/api/v0/transcribe 
```
