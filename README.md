# AI-Based Real-Time Multilingual Voice Translator

A desktop application that listens to speech, recognizes it, translates it into
a chosen target language, and speaks the translation back — built with Python
and Tkinter, using free cloud APIs.

> **Honesty note for viva:** this is an *API-orchestration* project. Speech
> recognition, translation, and speech synthesis are all performed by
> existing free Google services (Web Speech API, Google Translate, Google
> Text-to-Speech), called through Python libraries. No model is trained or
> fine-tuned in this project. Be ready to explain this distinction if asked.

---

## 1. Final Project Architecture

```
 Microphone
     │
     ▼
 speech_recognition_module.py  →  Google Web Speech API  →  recognized text
     │
     ▼
 translator.py  →  DeepL API (API key)  →  translated text
              │ unavailable
              ▼
            LibreTranslate API (fallback only)
     │
     ▼
 text_to_speech.py  →  gTTS  →  mp3 audio  →  afplay playback
     │
     ▼
 gui.py (Tkinter)  — displays every stage, runs the above in background
                      threads via a thread-safe queue, and never freezes
```

Design principles:
- **Separation of concerns** — each pipeline stage is its own module with a
  simple `(result, error, elapsed_time)` return contract. The GUI never
  calls a network/microphone API directly.
- **Never crash on a normal error** — every external call (mic access,
  Google Speech API, Google Translate, gTTS) is wrapped in `try/except` and
  turned into a friendly status message instead of an unhandled exception.
- **Responsive GUI** — long-running work (listening, translating, speaking)
  always runs in a `threading.Thread`; results are pushed onto a
  `queue.Queue` and the GUI thread drains it every 100 ms.

## 2. Folder Structure

```
project/
├── main.py                        # entry point
├── gui.py                         # Tkinter GUI + threading orchestration
├── speech_recognition_module.py   # microphone capture + speech-to-text
├── translator.py                  # text translation
├── text_to_speech.py              # text-to-speech + audio playback
├── utils.py                       # language table, history, logging, stopwatch
├── requirements.txt
└── README.md
```

This modular layout was requested directly and is used throughout — there is
no separate "single-file" version, since the modular version is not any less
reliable and is far easier to explain in a viva.

## 3. Complete Source Code

See the accompanying files: `main.py`, `gui.py`,
`speech_recognition_module.py`, `translator.py`, `text_to_speech.py`,
`utils.py`.

## 4. requirements.txt

```
SpeechRecognition>=3.10.0
deepl>=1.20.0
python-dotenv>=1.0.1
gTTS>=2.5.1
PyAudio>=0.2.14
```

`tkinter` ships with the standard Python installer on Windows/macOS. On
Linux, install it separately (see below).

## 5.1 DeepL API key

This project uses the DeepL API Developer/free plan. Create an account and
API key at https://www.deepl.com/your-account/keys. The official API
documentation is https://developers.deepl.com/docs/getting-started/quickstart.
The Developer plan currently includes a one-time 1,000,000-character credit;
you do not need to subscribe to a paid plan to test the application.

Create `/Users/jyotisah/Downloads/project-2/.env` with:

```text
TRANSLATION_API_KEY=PASTE_YOUR_REAL_KEY_HERE
```

The `.env` file is ignored by Git. Do not put the key in Python source files
or commit it.

DeepL is always tried first. LibreTranslate is only used as a fallback. The
default fallback endpoint is a local LibreTranslate server at
`http://127.0.0.1:5000/translate`. To use the fallback, keep LibreTranslate
running in another Terminal window. Install it into the same virtual
environment as the application first:

```bash
source venv/bin/activate
python -m pip install libretranslate
```

Then start it:

```bash
cd /Users/jyotisah/Downloads/project-2
source venv/bin/activate
libretranslate --host 127.0.0.1 --port 5000
```

The local fallback does not require an API key. LibreTranslate may need
internet access to download translation models. The project itself only calls
the LibreTranslate HTTP API; it does not start or import the server.

## 5. Installation Commands

**Windows**
```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
If `PyAudio` fails to install on Windows, install the prebuilt wheel instead:
```bat
pip install pipwin
pipwin install pyaudio
```

**macOS**
```bash
brew install python@3.12 python-tk@3.12 portaudio
$(brew --prefix python@3.12)/bin/python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Linux (Debian/Ubuntu)**
```bash
sudo apt-get install python3-tk portaudio19-dev python3-pyaudio
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 6. How to Run the Project

```bash
cd project
python main.py
```

A window opens with source/target language dropdowns, Start/Stop Listening
buttons, recognized-text and translated-text panels, and playback controls.

## 7. How Each Module Works

- **`utils.py`** — the single source of truth for the 15 supported
  languages (English, Hindi, Marathi, Bengali, Gujarati, Tamil, Telugu,
  Kannada, Malayalam, Punjabi, Urdu, French, German, Spanish, Japanese),
  each mapped to its speech-recognition locale code, translator code, and
  gTTS code. Also provides `TranslationHistory` (session log with per-step
  latency) and a shared logger that writes to `translator.log`.
- **`speech_recognition_module.py`** — opens the microphone, adjusts for
  ambient noise, listens for one phrase, and sends the audio to Google's
  Web Speech API via `recognize_google()`. Returns `(text, error, time)`
  and never raises — timeouts, unclear audio, no internet, and missing
  microphones are all converted into readable error strings.
- **`translator.py`** — sends recognized text to the DeepL API using
  `TRANSLATION_API_KEY` from `.env`, then makes one request to the configured
  LibreTranslate API only when DeepL cannot translate. It preserves the
  existing return contract and handles missing keys, quota errors, and network
  failures gracefully.
- **`text_to_speech.py`** — generates an mp3 with `gTTS`, plays it with
  built-in macOS `afplay`, and deletes the temp file afterwards (unless the caller
  asks to keep it for the "Replay" button).
- **`gui.py`** — builds the interface and coordinates everything above.
  Background work always runs in a `threading.Thread`; results are only
  ever applied to widgets from the main thread via the queue-polling loop
  `_poll_queue()`, which is the one Tkinter thread-safety rule this project
  depends on.
- **`main.py`** — creates the Tk root window, instantiates `VoiceTranslatorApp`,
  and starts the event loop.

## 8. Common Errors and Fixes

| Symptom | Cause | Fix |
|---|---|---|
| `OSError: No Default Input Device Available` | No microphone detected / OS blocked access | Check the OS microphone privacy setting; confirm a mic is plugged in; try `speech_recognition_module.list_microphones()` to see what's detected. |
| "Could not understand the audio" | Background noise, mumbled speech, wrong source language selected | Speak clearly, reduce background noise, double check the Source Language dropdown matches what you're speaking. |
| "Could not reach the speech recognition / translation service" | No internet connection, or the API is unavailable | Check your connection and retry. |
| "DeepL API key is missing" | `.env` is missing or still contains the placeholder | Add your DeepL key to `/Users/jyotisah/Downloads/project-2/.env`. |
| "The DeepL API key was rejected" | The key is invalid or disabled | Copy the active key from the DeepL account keys page. |
| `PyAudio` fails to build during `pip install` | Missing PortAudio system headers | Install `portaudio19-dev` (Linux) / `brew install portaudio` (macOS) / use `pipwin` (Windows) before retrying `pip install`. |
| No sound plays but no error shown | System output muted | Check system volume; check `translator.log` for errors. |
| GUI freezes | A blocking call was made outside a thread | Should not happen in this codebase — every network/mic call is already threaded. If you add a new feature, wrap it in `threading.Thread` too. |

## 9. Testing Procedure

1. **Unit-level, offline:** run `python -c "import utils; ..."` style checks
   on `utils.py` (language table, history) — no network needed.
2. **Translation-only:** call `translator.translate_text()` directly with a
   few fixed sentences per language pair and confirm sensible output.
3. **TTS-only:** call `text_to_speech.speak_text()` with sample translated
   text and confirm audio plays and the temp file is deleted afterward.
4. **End-to-end manual test:** run `main.py`, select a language pair, click
   *Start Listening*, speak a short sentence, and verify recognized text →
   translated text → spoken audio all appear correctly.
5. **Error-path testing:** turn off Wi-Fi and confirm the app shows a
   friendly network error instead of crashing; stay silent until the
   listening timeout and confirm the "no speech detected" message appears.

## 10. How to Demonstrate the Project During B.Tech Viva

- Start with the **pipeline diagram** (Section 1) so the panel sees the
  architecture before the demo.
- Demo **one clean success case** first (e.g. English → Hindi, a short
  clear sentence) so the happy path is visible.
- Then demo **one error case** on purpose (stay silent, or briefly disable
  Wi-Fi) to show the error handling actually works — panels respond well
  to seeing failure modes handled gracefully, not just the happy path.
- Show the **latency readout** at the bottom of the window and explain it
  ties directly to the project's stated research gap (Section 11 below).
- Be ready for the question **"where's the AI?"** — answer honestly: this
  project orchestrates three existing cloud APIs; the "AI" work (acoustic
  modeling, neural machine translation, neural TTS) happens inside Google's
  services, not in this codebase. If pushed further, mention the literature
  review found the same to be true of most lightweight desktop tools in
  this space (see Review-1 presentation, Literature Survey section).

## 11. Possible Future Improvements / Evaluation Methodology

Planned next-phase work, matching the research gap identified in Review-1:

- **Word Error Rate (WER)** for speech recognition: record a fixed set of
  sentences per language, get ground-truth transcripts, and compute
  `WER = (Substitutions + Deletions + Insertions) / Number of words in reference`
  using a library such as `jiwer`.
- **BLEU score** for translation quality: compare translated output against
  human reference translations of the same sentences using `sacrebleu` or
  `nltk.translate.bleu_score`.
- **Latency benchmarking**: this project already measures and logs
  recognition/translation/TTS/total time per utterance (see
  `TranslationHistory` in `utils.py` and the on-screen latency readout) —
  the next step is aggregating these into mean/median/95th-percentile
  numbers across many runs for the final report.
- Other improvements: continuous/streaming translation instead of
  utterance-by-utterance, offline fallback models, and tone/emotion-aware
  synthesis (all flagged as open problems in the literature survey).
